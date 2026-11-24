#!/usr/bin/env python3
"""Unit tests for audit_captions.py."""
import tempfile
import unittest
from pathlib import Path

from audit_captions import audit_captions


class TestAuditCaptions(unittest.TestCase):
    def test_valid_srt_passes(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:04,500\nHost: Welcome back to the show.\n\n"
            "2\n00:00:05,000 --> 00:00:08,500\nGuest: Thanks for having me today.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ep01.srt"
            p.write_text(srt, encoding="utf-8")
            res = audit_captions(p, require_speaker_prefix=True)
            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["cue_count"], 2)
            self.assertEqual(len(res["speaker_turns"]), 2)

    def test_overlapping_and_invalid_duration_fail(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:05,000\nFirst cue.\n\n"
            "2\n00:00:04,000 --> 00:00:03,500\nOverlaps and ends early.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.srt"
            p.write_text(srt, encoding="utf-8")
            res = audit_captions(p)
            cats = {f["category"] for f in res["findings"]}
            self.assertIn("overlapping_timestamp", cats)
            self.assertIn("invalid_duration", cats)
            self.assertEqual(res["status"], "FAIL")

    def test_line_length_and_cps_warnings(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\n"
            "This single line is far too long for comfortable reading on mobile screens.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fast.srt"
            p.write_text(srt, encoding="utf-8")
            res = audit_captions(p)
            cats = {f["category"] for f in res["findings"]}
            self.assertIn("line_too_long", cats)
            self.assertIn("reading_speed_high", cats)
            self.assertEqual(res["status"], "WARN")

    def test_missing_speaker_prefix_flagged(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:04,000\nUnattributed line.\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "nospeaker.srt"
            p.write_text(srt, encoding="utf-8")
            res = audit_captions(p, require_speaker_prefix=True)
            self.assertEqual(res["warnings"], 1)
            self.assertEqual(res["findings"][0]["category"], "missing_speaker_label")

    def test_webvtt_header_supported(self) -> None:
        vtt = "WEBVTT\n\n00:00:00.500 --> 00:00:03.500\nHost: Starting episode notes.\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ep01.vtt"
            p.write_text(vtt, encoding="utf-8")
            res = audit_captions(p, require_speaker_prefix=True)
            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["cue_count"], 1)


if __name__ == "__main__":
    unittest.main()
