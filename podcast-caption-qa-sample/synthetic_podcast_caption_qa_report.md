# Synthetic Podcast Caption & Transcript QA Sample Report

> **Disclosure**: 100% synthetic episode excerpt created for demonstration (`NovaCraft Studio`, overseen by Fan Zhu). Zero client audio or confidential scripts included.

## Scope & Checks Run
- **Target**: `synthetic_ep12_draft.srt` (6-cue synthetic dialogue excerpt)
- **Automated Checks** (`audit_captions.py`, `5/5` unit tests passing):
  1. Monotonic non-overlapping cue timestamps (`SRT` & `WebVTT`)
  2. Reading-speed ceiling (`<= 20.0 CPS`) and 2-line / 42-char broadcast wrap check
  3. Speaker-attribution consistency and show-notes timestamp index extraction

## Summary Verdict: `FAIL (1 error, 3 warnings)`

| Cue | Severity | Category | Finding | Suggested Fix |
| :--- | :--- | :--- | :--- | :--- |
| 3 | `error` | `overlapping_timestamp` | Starts at `00:00:11,500` before Cue 2 ended at `00:00:12,100` | Snap Cue 3 start to `00:00:12,150` or trim Cue 2 end to `00:00:11,450` |
| 2 | `warning` | `line_too_long` | 53 chars (limit 42) | Split at clause boundary into 2 balanced lines |
| 4 | `warning` | `reading_speed_high` | `24.8 CPS` exceeds `20.0 CPS` | Extend out-cue by `400ms` into pause or tighten filler phrasing |
| 5 | `warning` | `missing_speaker_label` | Expected `Speaker:` prefix | Prepend `Guest:` to match Cues 1–4 |

## Reproducible Verification
```bash
python3 -m unittest test_audit_captions.py
```
