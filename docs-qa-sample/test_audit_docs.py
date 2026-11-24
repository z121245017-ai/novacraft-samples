#!/usr/bin/env python3
"""Unit tests for audit_docs.py."""
import tempfile
import unittest
from pathlib import Path

from audit_docs import audit_markdown_doc


class TestAuditDocs(unittest.TestCase):
    def test_clean_doc_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "guide.md").write_text("# Setup Guide\n\nSee [Authentication](#authentication).\n\n## Authentication\n\nPass `api_key` to `/v1/orders`.\n", encoding="utf-8")
            spec = {"paths": {"/v1/orders": {"get": {"parameters": [{"name": "api_key", "required": True}]}}}}
            res = audit_markdown_doc(root / "guide.md", docs_root=root, glossary_terms={"apikey": "api_key"}, openapi_spec=spec)
            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["errors"], 0)
            self.assertEqual(res["warnings"], 0)

    def test_broken_anchor_and_missing_file_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "guide.md").write_text("# Intro\n\nSee [Missing](#does-not-exist) and [Ref](missing.md).\n", encoding="utf-8")
            res = audit_markdown_doc(root / "guide.md", docs_root=root)
            cats = [f["category"] for f in res["findings"]]
            self.assertIn("broken_anchor", cats)
            self.assertIn("broken_file_link", cats)
            self.assertEqual(res["status"], "FAIL")

    def test_duplicated_word_and_terminology_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sop.md").write_text("# SOP\n\nCheck the the webhook using Webhook-Id header.\n", encoding="utf-8")
            res = audit_markdown_doc(root / "sop.md", docs_root=root, glossary_terms={"Webhook-Id": "X-Webhook-Id"})
            cats = [f["category"] for f in res["findings"]]
            self.assertIn("duplicated_word", cats)
            self.assertIn("terminology_drift", cats)
            self.assertEqual(res["status"], "WARN")

    def test_openapi_missing_required_param(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "api.md").write_text("# API\n\nCall `/v1/invoices` to fetch invoices.\n", encoding="utf-8")
            spec = {"paths": {"/v1/invoices": {"get": {"parameters": [{"name": "account_id", "required": True}]}}}}
            res = audit_markdown_doc(root / "api.md", docs_root=root, openapi_spec=spec)
            self.assertEqual(res["errors"], 1)
            self.assertEqual(res["findings"][0]["category"], "missing_required_param")

    def test_cross_file_anchor_valid_and_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.md").write_text("# Reference\n\n## Rate Limits\n\n60 req/min.\n", encoding="utf-8")
            (root / "index.md").write_text("# Home\n\n[OK](ref.md#rate-limits) | [Bad](ref.md#wrong)\n", encoding="utf-8")
            res = audit_markdown_doc(root / "index.md", docs_root=root)
            self.assertEqual(res["errors"], 1)
            self.assertEqual(res["findings"][0]["category"], "broken_cross_file_anchor")


if __name__ == "__main__":
    unittest.main()
