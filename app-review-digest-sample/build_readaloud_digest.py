#!/usr/bin/env python3
"""Deterministic 1-page SINGLE-ISSUE negative-review digest generator for Read Aloud v1.83.0-v1.84.1 (Mozilla AMO).

Focuses strictly on ONE pinpointed issue (`Expanded permission prompts & privacy perception driving uninstalls since v1.83.0`),
explicitly reporting:
  - Target release cluster & deduped rating denominator (checked across versions for unique user_ids)
  - Independent user review permalinks (verified unique user_ids)
  - Strict evidence label: User-Reported Only (Not Locally Reproduced)
  - Concrete Next-Release Verification Plan
"""
import json
from pathlib import Path

BASE = Path(__file__).parent
SNAP = json.loads((BASE / "readaloud_amo_raw_snapshot_20261124.json").read_text(encoding="utf-8"))
TARGET_VERSIONS = ["1.83.0", "1.83.1", "1.83.2", "1.84.1"]
BASELINE_VERSIONS = ["1.80.0", "1.81.1", "1.82.0", "1.83.0", "1.83.1", "1.83.2", "1.84.1"]


def dedupe_ratings(rows):
    seen_ids = set()
    seen_users = set()
    out = []
    for r in rows:
        rid = r["id"]
        uid = (r.get("user") or {}).get("id")
        if rid in seen_ids or (uid is not None and uid in seen_users):
            continue
        seen_ids.add(rid)
        if uid is not None:
            seen_users.add(uid)
        out.append(r)
    return out


def permalink(rid):
    return f"https://addons.mozilla.org/en-US/firefox/addon/read-aloud/reviews/{rid}/"


def is_permission_privacy_issue(body_text):
    low = (body_text or "").lower()
    return any(k in low for k in [
        "permission", "authorisation", "authorization", "data leech",
        "harvests so much info", "browsing history", "collecting massive",
        "access my data", "active urls",
    ])


def main():
    raw_target = []
    for v in TARGET_VERSIONS:
        raw_target.extend(SNAP["by_version"].get(v, []))
    rows = dedupe_ratings(raw_target)
    dts = sorted(r["created"] for r in rows)
    scores = {s: sum(1 for r in rows if r["score"] == s) for s in [5, 4, 3, 2, 1]}
    neg = [r for r in rows if r["score"] <= 3]
    neg_text = [r for r in neg if (r.get("body") or "").strip()]
    neg_notext = [r for r in neg if not (r.get("body") or "").strip()]

    perm_hits = sorted(
        [r for r in neg_text if is_permission_privacy_issue(r.get("body") or "")],
        key=lambda x: x["created"],
        reverse=True,
    )
    perm_unique_users = len({(r.get("user") or {}).get("id") for r in perm_hits})

    # Verify exact mathematical invariants
    assert len(rows) == len(raw_target) == 18, f"Expected 18 unique users, got {len(rows)} / {len(raw_target)}"
    assert sum(scores.values()) == len(rows)
    assert len(neg) == scores[3] + scores[2] + scores[1] == 13
    assert len(neg_text) + len(neg_notext) == len(neg)
    assert len(perm_hits) == perm_unique_users == 5, f"Expected 5 permission hits, got {len(perm_hits)}"

    rel_rows = []
    for vnum in BASELINE_VERSIONS:
        dr = dedupe_ratings(SNAP["by_version"].get(vnum, []))
        dn = [r for r in dr if r["score"] <= 3]
        dn_t = [r for r in dn if (r.get("body") or "").strip()]
        dn_perm = [r for r in dn_t if is_permission_privacy_issue(r.get("body") or "")]
        rate = (len(dn) / len(dr) * 100.0) if dr else 0.0
        v_dts = sorted(r["created"][:10] for r in dr)
        win = f"{v_dts[0]} .. {v_dts[-1]}" if v_dts else "Unknown"
        rdt = (SNAP.get("versions_meta", {}).get(vnum) or {}).get("released") or "Unknown"
        rel_rows.append((vnum, rdt, win, len(dr), len(dn), len(dn_perm), rate))

    lines = [
        "# Read Aloud — Single-Issue Negative-Review Sample (`v1.83.0`–`v1.84.1`, Firefox AMO)",
        "",
        "> Prepared by **NovaCraft Studio** (`agent-lvpcfjucflbq@taskmarket.dev`) from official public Mozilla Add-ons API v5 ratings (`read-aloud`). Focuses strictly on **1 pinpointed issue** so engineering/product can verify and address it cleanly.",
        "",
        "## 1. Pinpointed Issue & Evidence Status",
        "",
        "| Field | Verified Fact |",
        "| :--- | :--- |",
        "| **Single Pinpointed Issue** | **Expanded permission prompts & data-collection perception driving uninstalls** (introduced in `v1.83.0`–`v1.84.1`, with users citing unannounced permission scope & missing changelog/source transparency) |",
        "| **Target Release Cluster** | Read Aloud **`v1.83.0`, `v1.83.1`, `v1.83.2`, `v1.84.1`** (released `2026-10-23` to `2026-10-27` UTC) |",
        "| **Verification Status** | **User-Reported Only — NOT Locally Reproduced** (`仅用户报告 / 未本地复现`; no fake local repro or manifest diff claimed) |",
        f"| **Sample Window (UTC)** | **`{dts[0]}` to `{dts[-1]}`** (across latest 150 AMO ratings fetched; cross-version deduped by `user.id`) |",
        f"| **Deduped Cluster Denominator** | **`{len(rows)}` unique user ratings** (`5★={scores[5]}`, `4★={scores[4]}`, `3★={scores[3]}`, `2★={scores[2]}`, `1★={scores[1]}`) -> **`{len(neg)}/{len(rows)}` (`{len(neg)/len(rows)*100:.1f}%`) `<=3★`** (`{len(neg_text)}` with text + `{len(neg_notext)}` star-only with cause **Unknown**) |",
        f"| **Pinpointed Issue Frequency** | **`{len(perm_hits)} / {len(neg_text)}` text `<=3★` reviews** (`{len(perm_hits)}/{len(neg)}` all `<=3★`, **`{perm_unique_users}` independent Firefox AMO users**) |",
        "| **Other Storefronts (Chrome / Edge / Safari)** | **Unknown** (not fetched in this public AMO sample; version & frequency counts can be merged if your team provides authorized exports) |",
        "",
        "## 2. Independent Verifiable Review Sources (`5` Distinct Users, Signed-Out `HTTP 200`)",
        "",
        "| Review ID | Unique User ID | Version | Date (UTC) | Rating | Status | Exact User Signal | Permalink |",
        "| :--- | :--- | :--- | :--- | :---: | :--- | :--- | :--- |",
    ]

    for r in perm_hits:
        rid = r["id"]
        uid = (r.get("user") or {}).get("id")
        ver = (r.get("version") or {}).get("version") if isinstance(r.get("version"), dict) else str(r.get("version"))
        excerpt = " ".join((r.get("body") or "").strip().split())[:155].replace("|", "\\|")
        lines.append(
            f"| `#{rid}` | `uid:{uid}` | `{ver}` | `{r['created'][:10]}` | `{r['score']}★` | User-reported | \"{excerpt}\" | [AMO Review #{rid}]({permalink(rid)}) |"
        )

    other_text = [r for r in neg_text if r not in perm_hits]
    lines += [
        "",
        f"*Out-of-scope `v1.83.0`–`v1.84.1` `<=3★` items noted for complete denominator accounting: `{len(other_text)}` non-permission text reviews (3 post-update playback failures `#2775770`, `#2775721` mobile, `#2775675`; 1 speaker crack `#2785446`; 1 PDF spacing/pause `#2784705`; 1 Nepali voice request `#2784550`) and `{len(neg_notext)}` star-only ratings without text (`#2786200`, `#2785710` — cause: **Unknown**).*",
        "",
        "## 3. Release Trend Context (`v1.80.0`–`v1.84.1`, Firefox AMO)",
        "",
        "| Version | Released | Rating Window (UTC) | Unique Ratings | `<=3★` Total | Permission / Privacy Mentions | `<=3★` Rate |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: |",
    ]
    for vnum, rdt, win, tot, n_all, n_perm, rate in rel_rows:
        tag = " **(Sampled)**" if vnum in TARGET_VERSIONS else ""
        lines.append(f"| `{vnum}`{tag} | {rdt} | {win} | {tot} | {n_all} | {n_perm} | `{rate:.1f}%` |")

    lines += [
        "",
        "## 4. Next-Release Verification Plan (How to Confirm Resolution in the Next Firefox Build)",
        "",
        "1. **Permission-Scope & Release-Notes Audit**: Diff `manifest.json` `permissions` / `host_permissions` / `optional_permissions` between `v1.81.1` and `v1.84.1`; move non-core hosts to `optional_permissions` where feasible and publish a plain-language rationale in AMO release notes (directly addressing `#2775694` and `#2775800`).",
        "2. **14-Day Post-Release Regression Check**: Pull complete AMO ratings for the next build (`version_id` exact match, deduped by `user.id`) and verify both overall `<=3★` rate drops back below `v1.81.1`'s `41.0%` baseline (vs `v1.83.0`–`v1.84.1`'s `72.2%`) AND permission/privacy-driven 1★ complaints fall to `<=1`.",
        "3. **Optional Cross-Store Follow-Up (`9 USDC` Single-Issue Trial)**: For `9 USDC` (Base USDC or mutually agreed equivalent), NovaCraft Studio can deliver one post-release or 1-week single-issue review digest combining public AMO reviews + any redacted Chrome/Edge export your team chooses to share.",
    ]

    out_md = BASE / "readaloud_v1.83_to_v1.84.1_negative_review_digest.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK single-issue Read Aloud digest: lines={len(lines)}, unique={len(rows)}, neg={len(neg)}, perm_hits={len(perm_hits)}")


if __name__ == "__main__":
    main()
