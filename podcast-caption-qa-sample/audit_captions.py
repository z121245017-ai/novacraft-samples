#!/usr/bin/env python3
"""Read-only SRT/VTT podcast caption & transcript QA validator."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TIME_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)
SPEAKER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 .'-]{1,24}):\s+")


def _to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_captions(text: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    for b in blocks:
        lines = [ln.rstrip("\r") for ln in b.splitlines() if ln.strip()]
        if not lines or lines[0].upper().startswith("WEBVTT"):
            continue
        time_idx = 0
        cue_id = None
        if not TIME_RE.match(lines[0]) and len(lines) > 1 and TIME_RE.match(lines[1]):
            cue_id = lines[0].strip()
            time_idx = 1
        m = TIME_RE.match(lines[time_idx])
        if not m:
            continue
        start_ms = _to_ms(*m.groups()[:4])
        end_ms = _to_ms(*m.groups()[4:])
        payload = lines[time_idx + 1 :]
        cues.append({
            "cue_id": cue_id or str(len(cues) + 1),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "start_str": lines[time_idx].split("-->")[0].strip(),
            "lines": payload,
            "text": "\n".join(payload),
        })
    return cues


def audit_captions(
    caption_path: Path,
    *,
    max_cps: float = 20.0,
    max_line_chars: int = 42,
    max_lines: int = 2,
    require_speaker_prefix: bool = False,
) -> dict[str, Any]:
    raw = caption_path.read_text(encoding="utf-8")
    cues = parse_captions(raw)
    findings: list[dict[str, Any]] = []
    prev_end = -1
    speakers: list[dict[str, str]] = []

    for cue in cues:
        cid = cue["cue_id"]
        s_ms, e_ms = cue["start_ms"], cue["end_ms"]
        if e_ms <= s_ms:
            findings.append({"severity": "error", "cue": cid, "category": "invalid_duration", "detail": "End time <= start time"})
        if s_ms < prev_end:
            findings.append({"severity": "error", "cue": cid, "category": "overlapping_timestamp", "detail": f"Starts at {s_ms}ms before previous cue ended at {prev_end}ms"})
        prev_end = max(prev_end, e_ms)

        if len(cue["lines"]) > max_lines:
            findings.append({"severity": "warning", "cue": cid, "category": "too_many_lines", "detail": f"{len(cue['lines'])} lines (limit {max_lines})"})
        for ln in cue["lines"]:
            if len(ln) > max_line_chars:
                findings.append({"severity": "warning", "cue": cid, "category": "line_too_long", "detail": f"{len(ln)} chars (limit {max_line_chars})"})

        dur_s = max((e_ms - s_ms) / 1000.0, 0.001)
        plain = re.sub(r"<[^>]+>", "", " ".join(cue["lines"])).strip()
        cps = len(plain) / dur_s
        if cps > max_cps:
            findings.append({"severity": "warning", "cue": cid, "category": "reading_speed_high", "detail": f"{cps:.1f} CPS exceeds {max_cps:.1f}"})

        sm = SPEAKER_RE.match(plain)
        if sm:
            speakers.append({"cue": cid, "time": cue["start_str"], "speaker": sm.group(1)})
        elif require_speaker_prefix:
            findings.append({"severity": "warning", "cue": cid, "category": "missing_speaker_label", "detail": "Expected 'Speaker:' prefix"})

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "file": caption_path.name,
        "cue_count": len(cues),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "speaker_turns": speakers,
        "status": "FAIL" if errors else ("WARN" if warnings else "PASS"),
    }


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Validate SRT/VTT podcast captions.")
    p.add_argument("caption_file", type=Path)
    p.add_argument("--require-speaker", action="store_true")
    args = p.parse_args()
    print(json.dumps(audit_captions(args.caption_file, require_speaker_prefix=args.require_speaker), indent=2))


if __name__ == "__main__":
    main()
