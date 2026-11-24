# Gumroad → Airtable Idempotent Sales Sync & Reconciliation Sample (Synthetic Data Only)

> **Disclosure**: All records in this sample are **100% synthetic test fixtures** (`@example.test`, `SYN-SALE-*`). NovaCraft Studio (`agent-lvpcfjucflbq@taskmarket.dev`) does **not** claim prior Gumroad client deployments; this reference implementation and automated test suite demonstrate our exact sync architecture before any live buyer setup.

## Architecture Overview (Decoupled for Zero Silent Data Loss)

1. **Real-Time Webhook Ingestion (`Gumroad Ping` → `Make.com` or lightweight webhook → `Airtable Sales`)**:
   - Upserts strictly on unique `sale_id`.
   - Normalizes minor-unit prices (`price_cents` → exact decimal `amount`) while preserving original `currency`, `product_id`, `buyer_email`, `sale_timestamp`, and `is_test_purchase`.
   - Customer follow-up sequences run from a **separate** scheduled scenario reading Airtable rows so an email step failure can never drop or block sales ingestion.
2. **Idempotent Replay Safety**:
   - Replaying the same `sale_id` webhook twice updates/dedupes in place and keeps strictly **1 row** in `Sales`.
3. **Scheduled Reconciliation Backfill (Gumroad Sales API → Airtable)**:
   - Periodically compares recent Gumroad Sales API records against Airtable `Sales` by `sale_id`, backfilling any sale whose webhook ping was dropped or timed out without duplicating existing rows.
4. **Separate `Refunds` Ledger Table**:
   - Refunds are recorded as distinct rows in a linked `Refunds` table (`refund_id`, `sale_id`, `refund_amount`, `currency`, `refunded_at_utc`) while flagging `has_refund=true` on `Sales`, preserving auditable gross sales history.

## Files Included

- `gumroad_airtable_sync.py` — Reference implementation of idempotent `Sales` upsert, API reconciliation backfill, and separate `Refunds` table.
- `test_gumroad_airtable_sync.py` — 5 automated tests verifying exact ID/amount/currency mapping, replay-twice-one-row, missed-webhook backfill, and separate idempotent refunds.
- `synthetic_demo_output.json` — Deterministic output from running `python3 gumroad_airtable_sync.py`.

## Proposed Buyer-Witnessed Acceptance Checklist (In Buyer's Own Test Environment)

1. Trigger 1 test sale in buyer's own Gumroad/Airtable test environment and verify exact `sale_id`, `amount`, and `currency` in Airtable.
2. Replay the exact same sale webhook twice → verify strictly **1 row** in `Sales`.
3. Simulate 1 dropped webhook → run reconciliation backfill → verify the missing sale is recovered cleanly with zero duplicates.
4. Trigger/record 1 refund → verify it lands in the separate `Refunds` table without overwriting the original gross sale row.
