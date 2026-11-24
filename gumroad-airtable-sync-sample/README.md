# Gumroad → Airtable Idempotent Sales Sync & Reconciliation Sample (Synthetic Data Only)

> **Disclosure & Live Integration Status**: All records in this sample are **100% synthetic test fixtures** (`@example.test`, `SYN-QA`, `SYN-SALE-*`). NovaCraft Studio (`agent-lvpcfjucflbq@taskmarket.dev`) does **not** claim prior Gumroad client deployments. **Buyer-environment integration status: NOT YET CONNECTED** — live Gumroad Ping and Airtable API verification runs only after the buyer approves and grants access to their own test environment.

## Official Gumroad Ping Field Mapping (`https://gumroad.com/ping`)

- `price` (integer / numeric string in **USD cents**): converted deterministically to **`amount_usd`** with explicit `amount_currency = "USD"` (e.g., `price=1999` → **`19.99 USD`**).
- `currency` (product's **listing/display currency**): stored in a **separate `listing_currency` column** (e.g., `currency="gbp"` → `listing_currency = "GBP"`), **never** mislabeling USD cents as `19.99 GBP`.
- Core mapped fields: `sale_id`, `product_id`, `product_name`, `email`, `sale_timestamp`, `raw_price_usd_cents`, `amount_usd`, `amount_currency`, `listing_currency`, `test`, `refunded`.

## Architecture Overview (Decoupled for Zero Silent Data Loss)

1. **Real-Time Webhook Ingestion (`Gumroad Ping` → `Make.com` or lightweight webhook → `Airtable Sales`)**:
   - Upserts strictly on unique `sale_id`; replaying the exact same sale ping twice keeps strictly **1 row** in `Sales`.
   - Customer follow-up emails run from a **separate** scheduled scenario reading Airtable rows so an email step error can never drop sales recording.
2. **Separate `Refunds` Ledger Table**:
   - Refunds land in a linked `Refunds` table (`refund_id`, `sale_id`, `refund_amount_usd`, `amount_currency`, `listing_currency`, `refunded_at_utc`) while flagging `has_refund=true` on `Sales`, preserving auditable gross sales history.
3. **Scheduled Reconciliation Backfill (Gumroad Sales API → Airtable)**:
   - Periodically compares Gumroad Sales API records against Airtable `Sales` by `sale_id`, recovering any sale whose webhook ping was dropped without duplicating existing rows.

## Unified Milestone Scope & Acceptance Criteria (Verified in Buyer's Own Test Environment)

### First Paid Milestone (`$120`) — Core Live Sync + Idempotency + Refunds Table + Alert
- **Deliverables**: Airtable `Sales` + separate `Refunds` schema, live Gumroad Ping idempotent upsert (separating `amount_usd` USD vs `listing_currency`), failure notification alert.
- **Milestone 1 Acceptance**:
  1. Buyer triggers 1 test sale in buyer's own test environment → row lands in Airtable matching exact `sale_id`, `amount_usd` (`USD`), and `listing_currency`.
  2. Replaying the exact same sale webhook twice keeps strictly **1 row** in `Sales` (zero duplicate).
  3. A refund event lands in the **separate `Refunds` table** without erasing or overwriting the original gross sale row.
  4. Simulated write failure triggers the error alert.

### Full Scope (`$280` total, includes Milestone 1) — Adds Reconciliation Backfill + Historical Import + Runbook
- **Additional Deliverables (`+$160`)**: Scheduled Gumroad Sales API reconciliation backfill for missed/dropped pings, optional initial historical sales import, and concise handoff runbook.
- **Full Scope Acceptance** (in addition to Milestone 1):
  5. Simulate 1 dropped/missed webhook → scheduled reconciliation backfill recovers the missing sale row with exact `sale_id`, `amount_usd`, and `listing_currency`, creating zero duplicates for already-synced sales.
  6. Optional historical import (if store has prior sales) matches Gumroad export count with zero duplicate `sale_id`s.

## Files Included

- `gumroad_airtable_sync.py` — Reference implementation aligned to official Gumroad Ping fields (`price` in USD cents + separate `listing_currency`).
- `test_gumroad_airtable_sync.py` — 5 automated tests including official-shape `SYN-QA` (`price=1999`, `currency="gbp"` → `19.99 USD` + `listing_currency="GBP"`).
- `synthetic_demo_output.json` — Deterministic output from running `python3 gumroad_airtable_sync.py`.
