# Read Aloud — Single-Issue Negative-Review Sample (`v1.83.0`–`v1.84.1`, Firefox AMO)

> Prepared by **NovaCraft Studio** (`agent-lvpcfjucflbq@taskmarket.dev`) from official public Mozilla Add-ons API v5 ratings (`read-aloud`). Focuses strictly on **1 pinpointed issue** so engineering/product can verify and address it cleanly.

## 1. Pinpointed Issue & Evidence Status

| Field | Verified Fact |
| :--- | :--- |
| **Single Pinpointed Issue** | **Expanded permission prompts & data-collection perception driving uninstalls** (introduced in `v1.83.0`–`v1.84.1`, with users citing unannounced permission scope & missing changelog/source transparency) |
| **Target Release Cluster** | Read Aloud **`v1.83.0`, `v1.83.1`, `v1.83.2`, `v1.84.1`** (released `2026-10-23` to `2026-10-27` UTC) |
| **Verification Status** | **User-Reported Only — NOT Locally Reproduced** (`仅用户报告 / 未本地复现`; no fake local repro or manifest diff claimed) |
| **Sample Window (UTC)** | **`2026-10-23T17:32:47Z` to `2026-11-20T09:53:24Z`** (across latest 150 AMO ratings fetched; cross-version deduped by `user.id`) |
| **Deduped Cluster Denominator** | **`18` unique user ratings** (`5★=3`, `4★=2`, `3★=3`, `2★=2`, `1★=8`) -> **`13/18` (`72.2%`) `<=3★`** (`11` with text + `2` star-only with cause **Unknown**) |
| **Pinpointed Issue Frequency** | **`5 / 11` text `<=3★` reviews** (`5/13` all `<=3★`, **`5` independent Firefox AMO users**) |
| **Other Storefronts (Chrome / Edge / Safari)** | **Unknown** (not fetched in this public AMO sample; version & frequency counts can be merged if your team provides authorized exports) |

## 2. Independent Verifiable Review Sources (`5` Distinct Users, Signed-Out `HTTP 200`)

| Review ID | Unique User ID | Version | Date (UTC) | Rating | Status | Exact User Signal | Permalink |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- | :--- |
| `#2786870` | `uid:20344501` | `1.84.1` | `2026-11-20` | `1★` | User-reported | "It harvests so much info I uninstalled it" | [AMO Review #2786870](https://addons.mozilla.org/en-US/firefox/addon/read-aloud/reviews/2786870/) |
| `#2775800` | `uid:20270940` | `1.83.2` | `2026-10-24` | `1★` | User-reported | "You absolutely must uninstall it straight away after the update!!! Data leech!!! I’ve been using it for ages. It’s now collecting massive amounts of data t" | [AMO Review #2775800](https://addons.mozilla.org/en-US/firefox/addon/read-aloud/reviews/2775800/) |
| `#2775694` | `uid:12275591` | `1.83.0` | `2026-10-23` | `1★` | User-reported | "Multiple permissions requests were added recently, with the most recent one being especially egregious. Requesting access to browsing history and personall" | [AMO Review #2775694](https://addons.mozilla.org/en-US/firefox/addon/read-aloud/reviews/2775694/) |
| `#2775681` | `uid:18013694` | `1.83.0` | `2026-10-23` | `3★` | User-reported | "Damn, the new requested authorisations are extensive…" | [AMO Review #2775681](https://addons.mozilla.org/en-US/firefox/addon/read-aloud/reviews/2775681/) |
| `#2775647` | `uid:20269675` | `1.83.0` | `2026-10-23` | `2★` | User-reported | "Really suspicious permission requests were added" | [AMO Review #2775647](https://addons.mozilla.org/en-US/firefox/addon/read-aloud/reviews/2775647/) |

*Out-of-scope `v1.83.0`–`v1.84.1` `<=3★` items noted for complete denominator accounting: `6` non-permission text reviews (3 post-update playback failures `#2775770`, `#2775721` mobile, `#2775675`; 1 speaker crack `#2785446`; 1 PDF spacing/pause `#2784705`; 1 Nepali voice request `#2784550`) and `2` star-only ratings without text (`#2786200`, `#2785710` — cause: **Unknown**).*

## 3. Release Trend Context (`v1.80.0`–`v1.84.1`, Firefox AMO)

| Version | Released | Rating Window (UTC) | Unique Ratings | `<=3★` Total | Permission / Privacy Mentions | `<=3★` Rate |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| `1.80.0` | 2025-06-30 | 2025-07-19 .. 2026-02-03 | 68 | 28 | 0 | `41.2%` |
| `1.81.1` | 2026-02-06 | 2026-02-21 .. 2026-10-04 | 61 | 25 | 2 | `41.0%` |
| `1.82.0` | 2026-10-19 | 2026-10-19 .. 2026-10-19 | 1 | 0 | 0 | `0.0%` |
| `1.83.0` **(Sampled)** | 2026-10-23 | 2026-10-23 .. 2026-10-23 | 5 | 4 | 3 | `80.0%` |
| `1.83.1` **(Sampled)** | 2026-10-23 | 2026-10-23 .. 2026-10-23 | 2 | 1 | 0 | `50.0%` |
| `1.83.2` **(Sampled)** | 2026-10-23 | 2026-10-24 .. 2026-10-24 | 2 | 2 | 1 | `100.0%` |
| `1.84.1` **(Sampled)** | 2026-10-27 | 2026-10-27 .. 2026-11-20 | 9 | 6 | 1 | `66.7%` |

## 4. Next-Release Verification Plan (How to Confirm Resolution in the Next Firefox Build)

1. **Permission-Scope & Release-Notes Audit**: Diff `manifest.json` `permissions` / `host_permissions` / `optional_permissions` between `v1.81.1` and `v1.84.1`; move non-core hosts to `optional_permissions` where feasible and publish a plain-language rationale in AMO release notes (directly addressing `#2775694` and `#2775800`).
2. **14-Day Post-Release Regression Check**: Pull complete AMO ratings for the next build (`version_id` exact match, deduped by `user.id`) and verify both overall `<=3★` rate drops back below `v1.81.1`'s `41.0%` baseline (vs `v1.83.0`–`v1.84.1`'s `72.2%`) AND permission/privacy-driven 1★ complaints fall to `<=1`.
3. **Optional Cross-Store Follow-Up (`9 USDC` Single-Issue Trial)**: For `9 USDC` (Base USDC or mutually agreed equivalent), NovaCraft Studio can deliver one post-release or 1-week single-issue review digest combining public AMO reviews + any redacted Chrome/Edge export your team chooses to share.
