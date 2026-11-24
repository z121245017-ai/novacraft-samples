#!/usr/bin/env python3
"""Regression test suite for Weekly SKU Inventory Reconciliation (v2).

Covers all Codex-flagged invariants:
  1. 10 -> 8 repro: opening 10, fulfilled sale 2, matching outbound_sale 2, physical 8
     -> expected 8, variance 0, MATCH, exit code 0 (zero double-deduction / false surplus!).
  2. Two distinct fulfillments on the same order (split shipment FUL-A + FUL-B)
     -> both counted (never collapsed).
  3. Unproven sale-movement overlap (missing order_ref / fulfillment_id)
     -> flagged NEEDS_REVIEW (`UNPROVEN_SALE_MOVEMENT_OVERLAP`), never silently double-deducted, exit code 2.
  4. Unknown movement type (`mystery_transfer`)
     -> flagged NEEDS_REVIEW (`UNKNOWN_MOVEMENT_TYPE`), never silently deducted as outbound, exit code 2.
  5. Warehouse isolation & post-cutoff timestamp detection.
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reconcile_weekly_inventory import reconcile_directory

SCRIPT = Path(__file__).parent / "reconcile_weekly_inventory.py"


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _setup_fixture(
    tmp: Path,
    opening: list[dict],
    sales: list[dict],
    movements: list[dict],
    physical: list[dict],
) -> None:
    _write_csv(
        tmp / "01_opening_stock_20261116.csv",
        opening,
        ["warehouse", "sku", "product_name", "opening_qty", "unit_cost_usd", "snapshot_date"],
    )
    _write_csv(
        tmp / "02_weekly_sales_pii_stripped.csv",
        sales,
        ["warehouse", "order_ref", "fulfillment_id", "sale_timestamp", "channel", "sku", "qty_sold", "status"],
    )
    _write_csv(
        tmp / "03_inbound_outbound_movements.csv",
        movements,
        ["warehouse", "move_ref", "order_ref", "fulfillment_id", "move_timestamp", "type", "sku", "qty", "note"],
    )
    _write_csv(
        tmp / "04_physical_count_20261122.csv",
        physical,
        ["warehouse", "sku", "physical_count", "counted_at", "location"],
    )


class WeeklyInventoryReconRegressionTests(unittest.TestCase):
    def test_01_repro_10_to_8_same_order_fulfilled_and_outbound_sale_no_double_deduction(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[{"warehouse": "WH-MAIN", "sku": "SKU-A", "product_name": "Widget A", "opening_qty": 10, "unit_cost_usd": "5.00", "snapshot_date": "2026-11-16"}],
                sales=[{"warehouse": "WH-MAIN", "order_ref": "ORD-100", "fulfillment_id": "FUL-100-1", "sale_timestamp": "2026-11-18 10:00", "channel": "Shopify Online", "sku": "SKU-A", "qty_sold": 2, "status": "fulfilled"}],
                movements=[{"warehouse": "WH-MAIN", "move_ref": "MOV-100", "order_ref": "ORD-100", "fulfillment_id": "FUL-100-1", "move_timestamp": "2026-11-18 10:05", "type": "outbound_sale", "sku": "SKU-A", "qty": 2, "note": "Shipped ORD-100"}],
                physical=[{"warehouse": "WH-MAIN", "sku": "SKU-A", "physical_count": 8, "counted_at": "2026-11-22 21:00", "location": "Shelf A1"}],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=True)
            self.assertEqual(res["reconciliation_status"], "CLEAN")
            self.assertEqual(res["needs_review_count"], 0)
            row = res["rows"][0]
            self.assertEqual(row["expected_on_hand"], 8)
            self.assertEqual(row["physical_count"], 8)
            self.assertEqual(row["variance_qty"], 0)
            self.assertEqual(row["status"], "MATCH")
            self.assertTrue(any(a["type"] == "DEDUPED_FULFILLMENT_LINK" for a in res["anomalies"]))

            proc = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--cutoff", "2026-11-22 21:00"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_02_two_distinct_fulfillments_for_same_order_both_counted(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[{"warehouse": "WH-MAIN", "sku": "SKU-B", "product_name": "Widget B", "opening_qty": 10, "unit_cost_usd": "4.00", "snapshot_date": "2026-11-16"}],
                sales=[
                    {"warehouse": "WH-MAIN", "order_ref": "ORD-200", "fulfillment_id": "FUL-200-A", "sale_timestamp": "2026-11-18 09:00", "channel": "Shopify Online", "sku": "SKU-B", "qty_sold": 1, "status": "fulfilled"},
                ],
                movements=[
                    # Same fulfillment as sales -> deduped
                    {"warehouse": "WH-MAIN", "move_ref": "MOV-200A", "order_ref": "ORD-200", "fulfillment_id": "FUL-200-A", "move_timestamp": "2026-11-18 09:10", "type": "outbound_sale", "sku": "SKU-B", "qty": 1, "note": "Split shipment 1"},
                    # Second distinct fulfillment of same order -> must ALSO be counted!
                    {"warehouse": "WH-MAIN", "move_ref": "MOV-200B", "order_ref": "ORD-200", "fulfillment_id": "FUL-200-B", "move_timestamp": "2026-11-19 11:00", "type": "outbound_sale", "sku": "SKU-B", "qty": 1, "note": "Split shipment 2"},
                ],
                physical=[{"warehouse": "WH-MAIN", "sku": "SKU-B", "physical_count": 8, "counted_at": "2026-11-22 21:00", "location": "Shelf B1"}],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=False)
            self.assertEqual(res["reconciliation_status"], "CLEAN")
            row = res["rows"][0]
            self.assertEqual(row["sales_fulfilled_qty"], 1)
            self.assertEqual(row["distinct_sale_movements_qty"], 1)
            self.assertEqual(row["expected_on_hand"], 8)
            self.assertEqual(row["variance_qty"], 0)
            self.assertEqual(row["status"], "MATCH")

    def test_03_unproven_duplicate_sale_movement_flagged_needs_review_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[{"warehouse": "WH-MAIN", "sku": "SKU-C", "product_name": "Widget C", "opening_qty": 10, "unit_cost_usd": "6.00", "snapshot_date": "2026-11-16"}],
                sales=[{"warehouse": "WH-MAIN", "order_ref": "ORD-300", "fulfillment_id": "FUL-300-1", "sale_timestamp": "2026-11-18 14:00", "channel": "Shopify POS", "sku": "SKU-C", "qty_sold": 2, "status": "fulfilled"}],
                movements=[{"warehouse": "WH-MAIN", "move_ref": "MOV-NO-ORDER", "order_ref": "", "fulfillment_id": "", "move_timestamp": "2026-11-18 14:05", "type": "outbound_sale", "sku": "SKU-C", "qty": 2, "note": "Missing order_ref & fulfillment_id"}],
                physical=[{"warehouse": "WH-MAIN", "sku": "SKU-C", "physical_count": 8, "counted_at": "2026-11-22 21:00", "location": "Shelf C1"}],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=True)
            self.assertEqual(res["reconciliation_status"], "NEEDS_REVIEW")
            self.assertEqual(res["needs_review_count"], 1)
            row = res["rows"][0]
            self.assertEqual(row["status"], "NEEDS_REVIEW")
            # Must NOT silently double-deduct to 6 and scream SURPLUS +2!
            self.assertEqual(row["expected_on_hand"], 8)
            self.assertIn("UNPROVEN_SALE_MOVEMENT_OVERLAP", row["needs_review_reasons"])

            proc = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--cutoff", "2026-11-22 21:00"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)

    def test_04_unknown_movement_type_flagged_needs_review_not_silently_deducted(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[{"warehouse": "WH-MAIN", "sku": "SKU-D", "product_name": "Widget D", "opening_qty": 10, "unit_cost_usd": "3.00", "snapshot_date": "2026-11-16"}],
                sales=[],
                movements=[{"warehouse": "WH-MAIN", "move_ref": "MOV-UNK-1", "order_ref": "", "fulfillment_id": "", "move_timestamp": "2026-11-19 16:00", "type": "mystery_reclass", "sku": "SKU-D", "qty": 3, "note": "Unknown ERP code"}],
                physical=[{"warehouse": "WH-MAIN", "sku": "SKU-D", "physical_count": 10, "counted_at": "2026-11-22 21:00", "location": "Shelf D1"}],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=True)
            self.assertEqual(res["reconciliation_status"], "NEEDS_REVIEW")
            row = res["rows"][0]
            self.assertEqual(row["status"], "NEEDS_REVIEW")
            self.assertEqual(row["non_sale_outbound_qty"], 0)
            self.assertEqual(row["expected_on_hand"], 10)
            self.assertIn("UNKNOWN_MOVEMENT_TYPE", row["needs_review_reasons"])

            proc = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--cutoff", "2026-11-22 21:00"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)

    def test_05_warehouse_isolation_and_post_cutoff_movement_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[
                    {"warehouse": "SHOP-NORTH", "sku": "SKU-X", "product_name": "Leash", "opening_qty": 10, "unit_cost_usd": "5.00", "snapshot_date": "2026-11-16"},
                    {"warehouse": "SHOP-SOUTH", "sku": "SKU-X", "product_name": "Leash", "opening_qty": 6, "unit_cost_usd": "5.00", "snapshot_date": "2026-11-16"},
                ],
                sales=[
                    {"warehouse": "SHOP-NORTH", "order_ref": "ORD-N1", "fulfillment_id": "FUL-N1", "sale_timestamp": "2026-11-20 12:00", "channel": "Shopify POS", "sku": "SKU-X", "qty_sold": 2, "status": "fulfilled"},
                ],
                movements=[
                    {"warehouse": "SHOP-SOUTH", "move_ref": "DMG-S1", "order_ref": "", "fulfillment_id": "", "move_timestamp": "2026-11-20 13:00", "type": "outbound_damage", "sku": "SKU-X", "qty": 1, "note": "Damaged in South"},
                    {"warehouse": "SHOP-NORTH", "move_ref": "LATE-1", "order_ref": "", "fulfillment_id": "", "move_timestamp": "2026-11-22 22:30", "type": "inbound_receipt", "sku": "SKU-X", "qty": 5, "note": "Arrived after 21:00 cutoff"},
                ],
                physical=[
                    {"warehouse": "SHOP-NORTH", "sku": "SKU-X", "physical_count": 8, "counted_at": "2026-11-22 21:00", "location": "North Shelf"},
                    {"warehouse": "SHOP-SOUTH", "sku": "SKU-X", "physical_count": 5, "counted_at": "2026-11-22 21:00", "location": "South Shelf"},
                ],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=False)
            rows_by_wh = {r["warehouse"]: r for r in res["rows"]}
            # South is completely clean (6 - 1 damage = 5 == physical 5)
            self.assertEqual(rows_by_wh["SHOP-SOUTH"]["status"], "MATCH")
            self.assertEqual(rows_by_wh["SHOP-SOUTH"]["expected_on_hand"], 5)
            # North flags post-cutoff movement without corrupting expected=8
            self.assertEqual(rows_by_wh["SHOP-NORTH"]["expected_on_hand"], 8)
            self.assertEqual(rows_by_wh["SHOP-NORTH"]["status"], "NEEDS_REVIEW")
            self.assertIn("POST_CUTOFF_MOVEMENT_ROW", rows_by_wh["SHOP-NORTH"]["needs_review_reasons"])

    def test_06_date_only_next_day_inbound_and_sales_cleanly_excluded_10_to_10(self):
        """Codex repro: physical count 10 at 2026-11-22 21:00, opening 10, date-only inbound 2 on 2026-11-23
        (and date-only sale on 2026-11-23) MUST be excluded cleanly -> expected 10, variance 0, MATCH, exit 0!"""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[{"warehouse": "WH-MAIN", "sku": "SKU-DATE-1", "product_name": "Item Date", "opening_qty": 10, "unit_cost_usd": "5.00", "snapshot_date": "2026-11-16"}],
                sales=[{"warehouse": "WH-MAIN", "order_ref": "ORD-NEXTDAY", "fulfillment_id": "FUL-ND-1", "sale_timestamp": "2026-11-23", "channel": "Shopify Online", "sku": "SKU-DATE-1", "qty_sold": 3, "status": "fulfilled"}],
                movements=[{"warehouse": "WH-MAIN", "move_ref": "PO-NEXTDAY", "order_ref": "", "fulfillment_id": "", "move_timestamp": "2026-11-23", "type": "inbound_receipt", "sku": "SKU-DATE-1", "qty": 2, "note": "Next day delivery date-only"}],
                physical=[{"warehouse": "WH-MAIN", "sku": "SKU-DATE-1", "physical_count": 10, "counted_at": "2026-11-22 21:00", "location": "Shelf 1"}],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=True)
            self.assertEqual(res["reconciliation_status"], "CLEAN")
            self.assertEqual(res["needs_review_count"], 0)
            row = res["rows"][0]
            self.assertEqual(row["inbound_qty"], 0)
            self.assertEqual(row["sales_fulfilled_qty"], 0)
            self.assertEqual(row["expected_on_hand"], 10)
            self.assertEqual(row["physical_count"], 10)
            self.assertEqual(row["variance_qty"], 0)
            self.assertEqual(row["status"], "MATCH")
            excl = [a for a in res["anomalies"] if a["type"] == "POST_CUTOFF_NEXT_DAY_EXCLUDED"]
            self.assertEqual(len(excl), 2)

            proc = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--cutoff", "2026-11-22 21:00"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_07_date_only_same_day_as_midday_cutoff_flagged_needs_review(self):
        """Date-only sales/movements on the EXACT same local calendar day (2026-11-22) as a 21:00 count
        cannot be proven before vs after 21:00 -> MUST be marked NEEDS_REVIEW and exit 2!"""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _setup_fixture(
                d,
                opening=[
                    {"warehouse": "WH-MAIN", "sku": "SKU-SAME-MOV", "product_name": "SameDay Mov", "opening_qty": 10, "unit_cost_usd": "5.00", "snapshot_date": "2026-11-16"},
                    {"warehouse": "WH-MAIN", "sku": "SKU-SAME-SALE", "product_name": "SameDay Sale", "opening_qty": 10, "unit_cost_usd": "5.00", "snapshot_date": "2026-11-16"},
                ],
                sales=[{"warehouse": "WH-MAIN", "order_ref": "ORD-SD-1", "fulfillment_id": "FUL-SD-1", "sale_timestamp": "2026-11-22", "channel": "Shopify POS", "sku": "SKU-SAME-SALE", "qty_sold": 2, "status": "fulfilled"}],
                movements=[{"warehouse": "WH-MAIN", "move_ref": "PO-SD-1", "order_ref": "", "fulfillment_id": "", "move_timestamp": "2026-11-22", "type": "inbound_receipt", "sku": "SKU-SAME-MOV", "qty": 2, "note": "Date-only on count day"}],
                physical=[
                    {"warehouse": "WH-MAIN", "sku": "SKU-SAME-MOV", "physical_count": 10, "counted_at": "2026-11-22 21:00", "location": "Shelf 1"},
                    {"warehouse": "WH-MAIN", "sku": "SKU-SAME-SALE", "physical_count": 10, "counted_at": "2026-11-22 21:00", "location": "Shelf 2"},
                ],
            )
            res = reconcile_directory(d, as_of_cutoff="2026-11-22 21:00", write_outputs=True)
            self.assertEqual(res["reconciliation_status"], "NEEDS_REVIEW")
            self.assertEqual(res["needs_review_count"], 2)
            by_sku = {r["sku"]: r for r in res["rows"]}
            for sku in ("SKU-SAME-MOV", "SKU-SAME-SALE"):
                self.assertEqual(by_sku[sku]["status"], "NEEDS_REVIEW")
                self.assertIn("SAME_DAY_DATE_ONLY_AMBIGUOUS", by_sku[sku]["needs_review_reasons"])
                self.assertEqual(by_sku[sku]["expected_on_hand"], 10)

            proc = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--cutoff", "2026-11-22 21:00"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
