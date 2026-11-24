#!/usr/bin/env python3
"""Synthetic-Data Demo: Idempotent Gumroad -> Airtable Sales Sync, Reconciliation & Refunds Ledger.

STRICTLY SYNTHETIC DATA ONLY — zero real customer PII, zero fake client claims.
Demonstrates the exact reliability architecture proposed for Gumroad -> Airtable:
  1. Webhook ingestion (Gumroad Ping) with strict idempotent upsert keyed by `sale_id`:
     replaying the exact same sale payload twice produces strictly ONE row in `Sales`.
  2. Exact currency & amount preservation (`sale_id`, `amount`, `currency`, `product_id`, `buyer_email`).
  3. Scheduled reconciliation backfill against Gumroad Sales API:
     recovers any dropped/missed webhook event without duplicating existing rows.
  4. Separate `Refunds` table (never silently mutating/erasing gross sale figures):
     records refund events linked by `sale_id` and marks `has_refund=True` on the Sales row.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class SaleRow:
    sale_id: str
    product_id: str
    product_name: str
    buyer_email: str
    sale_timestamp_utc: str
    amount: float
    currency: str
    is_test_purchase: bool
    source_channel: str
    has_refund: bool = False
    ingest_count: int = 1


@dataclass
class RefundRow:
    refund_id: str
    sale_id: str
    refund_amount: float
    currency: str
    refunded_at_utc: str
    reason: str
    source_channel: str


class MockAirtableBase:
    """In-memory Airtable-compatible store with explicit `Sales` and `Refunds` tables."""

    def __init__(self) -> None:
        self.sales: dict[str, SaleRow] = {}
        self.refunds: dict[str, RefundRow] = {}
        self.audit_log: list[dict[str, Any]] = []

    def upsert_sale(self, payload: dict[str, Any], source_channel: str) -> str:
        sale_id = str(payload["sale_id"]).strip()
        if not sale_id:
            raise ValueError("Missing required sale_id")

        currency = str(payload.get("currency") or "USD").strip().upper()
        # Gumroad sends price in cents (minor units) or decimal depending on endpoint;
        # normalize explicitly and never drop currency!
        if "price_cents" in payload:
            amount = round(int(payload["price_cents"]) / 100.0, 2)
        else:
            amount = round(float(payload["amount"]), 2)

        is_refund_flag = bool(payload.get("refunded") or payload.get("is_refund_event"))

        if sale_id in self.sales:
            existing = self.sales[sale_id]
            existing.ingest_count += 1
            if is_refund_flag:
                existing.has_refund = True
            self.audit_log.append({
                "action": "DEDUPED_UPSERT_NO_NEW_ROW",
                "table": "Sales",
                "sale_id": sale_id,
                "source_channel": source_channel,
                "ingest_count": existing.ingest_count,
            })
            action = "updated_existing"
        else:
            row = SaleRow(
                sale_id=sale_id,
                product_id=str(payload["product_id"]).strip(),
                product_name=str(payload.get("product_name") or "").strip(),
                buyer_email=str(payload["email"]).strip().lower(),
                sale_timestamp_utc=str(payload["sale_timestamp"]).strip(),
                amount=amount,
                currency=currency,
                is_test_purchase=bool(payload.get("test", False)),
                source_channel=source_channel,
                has_refund=is_refund_flag,
                ingest_count=1,
            )
            self.sales[sale_id] = row
            self.audit_log.append({
                "action": "INSERTED_NEW_ROW",
                "table": "Sales",
                "sale_id": sale_id,
                "amount": amount,
                "currency": currency,
                "source_channel": source_channel,
            })
            action = "inserted"

        if is_refund_flag:
            self.upsert_refund(payload, source_channel=source_channel)
        return action

    def upsert_refund(self, payload: dict[str, Any], source_channel: str) -> str:
        sale_id = str(payload["sale_id"]).strip()
        refund_id = str(payload.get("refund_id") or f"REF-{sale_id}").strip()
        currency = str(payload.get("currency") or "USD").strip().upper()
        if "refund_amount_cents" in payload:
            ref_amt = round(int(payload["refund_amount_cents"]) / 100.0, 2)
        elif "refund_amount" in payload:
            ref_amt = round(float(payload["refund_amount"]), 2)
        elif "price_cents" in payload:
            ref_amt = round(int(payload["price_cents"]) / 100.0, 2)
        else:
            ref_amt = round(float(payload.get("amount", 0.0)), 2)

        if sale_id in self.sales:
            self.sales[sale_id].has_refund = True

        if refund_id in self.refunds:
            self.audit_log.append({
                "action": "DEDUPED_REFUND_NO_NEW_ROW",
                "table": "Refunds",
                "refund_id": refund_id,
                "sale_id": sale_id,
                "source_channel": source_channel,
            })
            return "deduped"

        self.refunds[refund_id] = RefundRow(
            refund_id=refund_id,
            sale_id=sale_id,
            refund_amount=ref_amt,
            currency=currency,
            refunded_at_utc=str(payload.get("refunded_at") or payload.get("sale_timestamp") or "").strip(),
            reason=str(payload.get("refund_reason") or "gumroad_refund").strip(),
            source_channel=source_channel,
        )
        self.audit_log.append({
            "action": "INSERTED_REFUND_ROW",
            "table": "Refunds",
            "refund_id": refund_id,
            "sale_id": sale_id,
            "refund_amount": ref_amt,
            "currency": currency,
            "source_channel": source_channel,
        })
        return "inserted"

    def reconcile_from_api_snapshot(self, api_sales: list[dict[str, Any]]) -> dict[str, int]:
        """Backfill any sales missed by dropped webhooks and sync refunds separately."""
        stats = {"checked": 0, "backfilled_sales": 0, "already_present": 0, "backfilled_refunds": 0}
        for s in api_sales:
            stats["checked"] += 1
            sid = str(s["sale_id"]).strip()
            existed = sid in self.sales
            self.upsert_sale(s, source_channel="reconciliation_backfill")
            if existed:
                stats["already_present"] += 1
            else:
                stats["backfilled_sales"] += 1
            if s.get("refunded"):
                ref_id = str(s.get("refund_id") or f"REF-{sid}").strip()
                # check if refund was inserted during this reconcile call
                if any(
                    ev.get("action") == "INSERTED_REFUND_ROW"
                    and ev.get("refund_id") == ref_id
                    and ev.get("source_channel") == "reconciliation_backfill"
                    for ev in self.audit_log[-2:]
                ):
                    stats["backfilled_refunds"] += 1
        return stats

    def summary(self) -> dict[str, Any]:
        return {
            "sales_row_count": len(self.sales),
            "refunds_row_count": len(self.refunds),
            "sales": [asdict(v) for v in self.sales.values()],
            "refunds": [asdict(v) for v in self.refunds.values()],
            "audit_log": self.audit_log,
        }


def run_synthetic_demo() -> dict[str, Any]:
    base = MockAirtableBase()

    # Synthetic Sale #1 (delivered via Ping webhook)
    ping_1 = {
        "sale_id": "SYN-SALE-1001",
        "product_id": "PROD-SYN-A",
        "product_name": "Synthetic Digital Pack A",
        "email": "buyer1@example.test",
        "sale_timestamp": "2026-11-24T01:00:00Z",
        "price_cents": 2900,
        "currency": "USD",
        "test": True,
        "refunded": False,
    }
    # 1) Initial Ping + 2) Exact duplicate replay of Ping #1
    base.upsert_sale(ping_1, source_channel="gumroad_ping")
    base.upsert_sale(ping_1, source_channel="gumroad_ping_replay")

    # Synthetic Sale #2 (GBP currency, refunded separately)
    ping_2 = {
        "sale_id": "SYN-SALE-1002",
        "product_id": "PROD-SYN-B",
        "product_name": "Synthetic Digital Pack B",
        "email": "buyer2@example.test",
        "sale_timestamp": "2026-11-24T01:15:00Z",
        "price_cents": 4500,
        "currency": "GBP",
        "test": False,
        "refunded": False,
    }
    base.upsert_sale(ping_2, source_channel="gumroad_ping")
    base.upsert_refund(
        {
            "sale_id": "SYN-SALE-1002",
            "refund_id": "SYN-REF-2001",
            "refund_amount_cents": 4500,
            "currency": "GBP",
            "refunded_at": "2026-11-24T02:00:00Z",
            "refund_reason": "customer_requested_refund",
        },
        source_channel="gumroad_refund_event",
    )

    # Synthetic Sale #3: DROPPED Ping (never reached webhook), recovered via Gumroad Sales API reconciliation!
    api_snapshot = [
        ping_1,
        {**ping_2, "refunded": True, "refund_id": "SYN-REF-2001", "refund_amount_cents": 4500, "refunded_at": "2026-11-24T02:00:00Z"},
        {
            "sale_id": "SYN-SALE-1003",
            "product_id": "PROD-SYN-A",
            "product_name": "Synthetic Digital Pack A",
            "email": "buyer3@example.test",
            "sale_timestamp": "2026-11-24T01:40:00Z",
            "price_cents": 1950,
            "currency": "EUR",
            "test": False,
            "refunded": False,
        },
    ]
    rec_stats = base.reconcile_from_api_snapshot(api_snapshot)

    out = {"reconciliation_stats": rec_stats, **base.summary()}
    out_dir = Path(__file__).parent
    (out_dir / "synthetic_demo_output.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    res = run_synthetic_demo()
    print(
        f"OK synthetic demo: sales_rows={res['sales_row_count']}, "
        f"refunds_rows={res['refunds_row_count']}, "
        f"backfilled={res['reconciliation_stats']['backfilled_sales']}"
    )
