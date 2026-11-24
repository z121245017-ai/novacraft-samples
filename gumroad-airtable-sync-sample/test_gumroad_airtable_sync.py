#!/usr/bin/env python3
"""Unit tests for the synthetic Gumroad -> Airtable sync & reconciliation demo (official Ping schema)."""
import unittest
from gumroad_airtable_sync import MockAirtableBase, run_synthetic_demo


class GumroadAirtableSyncTests(unittest.TestCase):
    def test_01_official_gumroad_ping_price_is_usd_cents_separate_from_listing_currency_gbp(self):
        """Official Gumroad Ping (https://gumroad.com/ping): `price=1999` is 19.99 USD; `currency='gbp'`
        is the product listing currency (GBP) — MUST be separated, NEVER stored as 19.99 GBP!"""
        base = MockAirtableBase()
        base.upsert_sale(
            {
                "sale_id": "SYN-QA",
                "product_id": "PROD-UK-1",
                "product_name": "UK Listed Guide",
                "email": "buyer.qa@example.test",
                "sale_timestamp": "2026-11-24T05:00:00Z",
                "price": 1999,
                "currency": "gbp",
                "test": "true",
            },
            source_channel="gumroad_ping",
        )
        self.assertEqual(len(base.sales), 1)
        row = base.sales["SYN-QA"]
        self.assertEqual(row.sale_id, "SYN-QA")
        self.assertEqual(row.raw_price_usd_cents, 1999)
        self.assertAlmostEqual(row.amount_usd, 19.99)
        self.assertEqual(row.amount_currency, "USD")
        self.assertEqual(row.listing_currency, "GBP")
        self.assertTrue(row.is_test_purchase)

    def test_02_replay_twice_produces_strictly_one_row(self):
        base = MockAirtableBase()
        payload = {
            "sale_id": "SYN-DUP-002",
            "product_id": "PROD-1",
            "email": "repeat@example.test",
            "sale_timestamp": "2026-11-24T05:05:00Z",
            "price": "2500",
            "currency": "usd",
        }
        r1 = base.upsert_sale(payload, "gumroad_ping")
        r2 = base.upsert_sale(payload, "gumroad_ping_replay")
        self.assertEqual(r1, "inserted")
        self.assertEqual(r2, "updated_existing")
        self.assertEqual(len(base.sales), 1)
        self.assertEqual(base.sales["SYN-DUP-002"].ingest_count, 2)
        self.assertAlmostEqual(base.sales["SYN-DUP-002"].amount_usd, 25.00)
        self.assertEqual(base.sales["SYN-DUP-002"].amount_currency, "USD")

    def test_03_missed_webhook_recovered_by_reconciliation_backfill(self):
        base = MockAirtableBase()
        s1 = {
            "sale_id": "SYN-REC-001",
            "product_id": "PROD-1",
            "email": "a@example.test",
            "sale_timestamp": "2026-11-24T05:10:00Z",
            "price": 1500,
            "currency": "usd",
        }
        s2_missed = {
            "sale_id": "SYN-REC-002",
            "product_id": "PROD-2",
            "email": "b@example.test",
            "sale_timestamp": "2026-11-24T05:12:00Z",
            "price": 3250,
            "currency": "eur",
        }
        base.upsert_sale(s1, "gumroad_ping")
        stats = base.reconcile_from_api_snapshot([s1, s2_missed])
        self.assertEqual(stats["backfilled_sales"], 1)
        self.assertEqual(stats["already_present"], 1)
        self.assertEqual(len(base.sales), 2)
        self.assertAlmostEqual(base.sales["SYN-REC-002"].amount_usd, 32.50)
        self.assertEqual(base.sales["SYN-REC-002"].amount_currency, "USD")
        self.assertEqual(base.sales["SYN-REC-002"].listing_currency, "EUR")
        self.assertEqual(base.sales["SYN-REC-002"].source_channel, "reconciliation_backfill")

    def test_04_refund_logged_in_separate_table_without_overwriting_gross_sale(self):
        base = MockAirtableBase()
        base.upsert_sale(
            {
                "sale_id": "SYN-REF-SALE-1",
                "product_id": "PROD-9",
                "email": "c@example.test",
                "sale_timestamp": "2026-11-24T05:20:00Z",
                "price": 4900,
                "currency": "gbp",
            },
            "gumroad_ping",
        )
        base.upsert_refund(
            {
                "sale_id": "SYN-REF-SALE-1",
                "refund_id": "REF-9001",
                "price": 4900,
                "currency": "gbp",
                "refunded_at": "2026-11-24T06:00:00Z",
            },
            "gumroad_refund_event",
        )
        # Replaying same refund must not create a second refund row
        base.upsert_refund(
            {
                "sale_id": "SYN-REF-SALE-1",
                "refund_id": "REF-9001",
                "price": 4900,
                "currency": "gbp",
                "refunded_at": "2026-11-24T06:00:00Z",
            },
            "gumroad_refund_replay",
        )
        self.assertEqual(len(base.sales), 1)
        self.assertEqual(len(base.refunds), 1)
        self.assertAlmostEqual(base.sales["SYN-REF-SALE-1"].amount_usd, 49.00)
        self.assertEqual(base.sales["SYN-REF-SALE-1"].amount_currency, "USD")
        self.assertEqual(base.sales["SYN-REF-SALE-1"].listing_currency, "GBP")
        self.assertTrue(base.sales["SYN-REF-SALE-1"].has_refund)
        self.assertAlmostEqual(base.refunds["REF-9001"].refund_amount_usd, 49.00)
        self.assertEqual(base.refunds["REF-9001"].amount_currency, "USD")
        self.assertEqual(base.refunds["REF-9001"].listing_currency, "GBP")

    def test_05_full_synthetic_demo_invariants(self):
        out = run_synthetic_demo()
        self.assertEqual(out["sales_row_count"], 3)
        self.assertEqual(out["refunds_row_count"], 1)
        self.assertEqual(out["reconciliation_stats"]["backfilled_sales"], 1)
        qa_row = next(r for r in out["sales"] if r["sale_id"] == "SYN-QA")
        self.assertAlmostEqual(qa_row["amount_usd"], 19.99)
        self.assertEqual(qa_row["amount_currency"], "USD")
        self.assertEqual(qa_row["listing_currency"], "GBP")


if __name__ == "__main__":
    unittest.main()
