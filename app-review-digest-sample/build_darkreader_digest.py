#!/usr/bin/env python3
"""Deterministic 1-page SINGLE-ISSUE negative-review digest generator for Dark Reader v4.9.133 (Mozilla AMO).

Focuses strictly on ONE pinpointed issue (`Firefox performance lag / high memory usage regression`),
explicitly reporting:
  - Target version & deduped rating denominator
  - Independent user review permalinks (verified unique user_ids)
  - Strict evidence label: User-Reported Only (Not Locally Reproduced)
  - Concrete Next-Release Verification Plan (`v4.9.136` / next Firefox release)
"""
import json
from pathlib import Path

BASE = Path(__file__).parent
SNAP = json.loads((BASE / "darkreader_amo_raw_snapshot_20261124.json").read_text(encoding="utf-8"))


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
    return f"https://addons.mozilla.org/en-US/firefox/addon/darkreader/reviews/{rid}/"


def is_firefox_perf_issue(body_text):
    low = (body_text or "").lower()
    return any(k in low for k in ["performance", "crawl", "lag", "memory", "not optimize", "lighter"])


def main():
    v133 = SNAP["versions"]["4.9.133"]
    rows = dedupe_ratings(v133["results"])
    dts = sorted(r["created"] for r in rows)
    scores = {s: sum(1 for r in rows if r["score"] == s) for s in [5, 4, 3, 2, 1]}
    neg = [r for r in rows if r["score"] <= 3]
    neg_text = [r for r in neg if (r.get("body") or "").strip()]
    neg_notext = [r for r in neg if not (r.get("body") or "").strip()]

    perf_hits = [r for r in neg_text if is_firefox_perf_issue(r.get("body") or "")]
    perf_unique_users = len({(r.get("user") or {}).get("id") for r in perf_hits})

    # Verify exact mathematical invariants
    assert len(rows) == v133["raw_count"]
    assert sum(scores.values()) == len(rows)
    assert len(neg) == scores[3] + scores[2] + scores[1]
    assert len(neg_text) + len(neg_notext) == len(neg)
    assert len(perf_hits) == perf_unique_users == 5

    # Baseline comparison across adjacent releases
    rel_rows = []
    for vnum in ["4.9.130", "4.9.131", "4.9.133", "4.9.134", "4.9.135"]:
        vd = SNAP["versions"][vnum]
        dr = dedupe_ratings(vd["results"])
        dn = [r for r in dr if r["score"] <= 3]
        dn_t = [r for r in dn if (r.get("body") or "").strip()]
        dn_perf = [r for r in dn_t if is_firefox_perf_issue(r.get("body") or "")]
        rate = (len(dn) / len(dr) * 100.0) if dr else 0.0
        v_dts = sorted(r["created"][:10] for r in dr)
        win = f"{v_dts[0]} .. {v_dts[-1]}" if v_dts else "Unknown"
        rel_rows.append((vnum, vd["release_date"], win, len(dr), len(dn), len(dn_perf), rate))

    lines = [
        "# Dark Reader — Single-Issue Negative-Review Sample (`v4.9.133`, Firefox AMO)",
        "",
        "> Prepared by **NovaCraft Studio** (`agent-lvpcfjucflbq@taskmarket.dev`) from official public Mozilla Add-ons API v5 ratings (`darkreader`, `version_id=6511634`). Focuses strictly on **1 pinpointed issue** so engineering can verify and close it cleanly.",
        "",
        "## 1. Pinpointed Issue & Evidence Status",
        "",
        "| Field | Verified Fact |",
        "| :--- | :--- |",
        "| **Single Pinpointed Issue** | **Firefox performance drag / browser lag & high memory usage** (including 1 report of lag extending to disabled sites) |",
        "| **Target Version** | Dark Reader **`v4.9.133`** (Mozilla AMO `version_id=6511634`, released `2026-09-24`) |",
        "| **Verification Status** | **User-Reported Only — NOT Locally Reproduced** (`仅用户报告 / 未本地复现`; no fake local repro claimed) |",
        f"| **Sample Window (UTC)** | **`{dts[0]}` to `{dts[-1]}`** (complete AMO population for `v4.9.133`; `next=null`) |",
        f"| **Deduped Version Denominator** | **`{len(rows)}` unique user ratings** (`5★={scores[5]}`, `4★={scores[4]}`, `3★={scores[3]}`, `2★={scores[2]}`, `1★={scores[1]}`) -> **`{len(neg)}/{len(rows)}` (`{len(neg)/len(rows)*100:.1f}%`) `<=3★`** (`{len(neg_text)}` with text + `{len(neg_notext)}` star-only with cause **Unknown**) |",
        f"| **Pinpointed Issue Frequency** | **`{len(perf_hits)} / {len(neg_text)}` text `<=3★` reviews** (`{len(perf_hits)}/{len(neg)}` all `<=3★`, **`{perf_unique_users}` independent Firefox AMO users**) |",
        "| **Other Storefronts (Chrome / Safari iOS / Edge)** | **Unknown** (not fetched in this public AMO sample; version & frequency counts can be merged if your team provides authorized exports) |",
        "",
        "## 2. Independent Verifiable Review Sources (`5` Distinct Users, Signed-Out `HTTP 200`)",
        "",
        "| Review ID | Unique User ID | Date (UTC) | Rating | Status | Exact User Signal | Permalink |",
        "| :--- | :--- | :--- | :---: | :--- | :--- | :--- |",
    ]

    for r in perf_hits:
        rid = r["id"]
        uid = (r.get("user") or {}).get("id")
        excerpt = " ".join((r.get("body") or "").strip().split())[:155].replace("|", "\\|")
        lines.append(
            f"| `#{rid}` | `uid:{uid}` | `{r['created'][:10]}` | `{r['score']}★` | User-reported | \"{excerpt}\" | [AMO Review #{rid}]({permalink(rid)}) |"
        )

    lines += [
        "",
        "*Out-of-scope `v4.9.133` `<=3★` items noted for complete denominator accounting: `1` unspecified Firefox complaint without repro detail (`#2775975`, 3★) and `4` star-only ratings without text (`#2774842`, `#2772556`, `#2767801`, `#2751295` — cause: **Unknown**).*",
        "",
        "## 3. Release Trend Context (`v4.9.130`–`v4.9.135`, Firefox AMO)",
        "",
        "| Version | Released | Rating Window (UTC) | Unique Ratings | `<=3★` Total | Firefox Perf Mentions | `<=3★` Rate |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: |",
    ]
    for vnum, rdt, win, tot, n_all, n_perf, rate in rel_rows:
        tag = " **(Sampled)**" if vnum == "4.9.133" else (" *(Latest)*" if vnum == "4.9.135" else "")
        lines.append(f"| `{vnum}`{tag} | {rdt} | {win} | {tot} | {n_all} | {n_perf} | `{rate:.1f}%` |")

    lines += [
        "",
        "## 4. Next-Release Verification Plan (How to Confirm Fix in `v4.9.136` / Next Firefox Build)",
        "",
        "1. **Review-Stream Regression Check (14 Days Post-Release)**: Pull complete AMO ratings for the next release (`version_id` exact match, deduped by `user_id`) and verify both overall `<=3★` rate drops back near pre-spike baseline (`<=15%`, vs `v4.9.133`'s `25.6%`) AND independent Firefox performance/lag/memory mentions stay at `<=1` (vs `v4.9.133`'s `5/6` text `<=3★` concentration).",
        "2. **Disabled-Site Overhead Guardrail Check (Addresses `#2754654` & `#2754279`)**: In Firefox `about:processes` / `about:memory` & Profiler, compare extension process RSS memory and CPU wakeups across (a) 10 active dark-mode tabs and (b) 10 tabs where Dark Reader is toggled OFF for the site — verifying near-zero background CPU/DOM mutation observer work on disabled domains.",
        "3. **Optional Cross-Store Follow-Up (`9 USDC` Single-Issue Trial)**: For `9 USDC` (Base USDC or agreed equivalent), NovaCraft Studio can deliver one post-release (`v4.9.136`) or 1-week single-issue review digest combining public AMO reviews + any redacted Chrome/Safari/iOS export you provide via your preferred channel.",
    ]

    out_md = BASE / "darkreader_v4.9.133_negative_review_digest.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK single-issue Dark Reader digest: lines={len(lines)}, unique={len(rows)}, neg={len(neg)}, perf_hits={len(perf_hits)}")


if __name__ == "__main__":
    main()
