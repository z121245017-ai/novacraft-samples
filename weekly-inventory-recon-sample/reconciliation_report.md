# Weekly SKU Inventory Reconciliation Sample (v2 — Warehouse, Cutoff & Fulfillment-Linked)

> **Privacy & Verification Design**: Uses strictly PII-stripped exports (zero customer names, emails, or addresses). Keyed by `(warehouse, sku)` at a single cutoff timestamp (`2026-11-22 21:00`). Sales fulfillment movements (`outbound_sale` / `outbound_fulfillment`) are deduplicated against fulfilled sales by `(order_ref, fulfillment_id, sku)` so the same shipment is **never** double-deducted; non-sale losses (`outbound_damage` / `outbound_shrinkage` / `outbound_internal`) are tracked separately; any unprovable overlap or unknown movement type is held in **`NEEDS_REVIEW` (`待核`)** instead of silently guessed.

- **Overall Reconciliation Status**: **`CLEAN`** (`needs_review_anomalies=0`, `needs_review_skus=0`)

## 1. Reconcilable Grand Totals Check (`PASS`)

| Metric | Units / Value | Formula Check |
| :--- | ---: | :--- |
| Opening Stock (2026-11-16) | `517` | Sum of `01_opening_stock_20261116.csv` (8 warehouse-SKU rows) |
| + Inbound (`inbound_receipt` / `inbound_return`) | `+37` | Allowlisted inbound movements |
| - Fulfilled Sales (Deduped) | `-65` | Deduped fulfilled rows in `02_weekly_sales_pii_stripped.csv` |
| - Distinct Unlogged Sale Fulfillments | `-2` | Linked `(order_ref, fulfillment_id)` shipments not already in sales export |
| - Non-Sale Outbound (`damage` / `shrinkage` / `internal`) | `-46` | Non-sale loss/consumption tracked separately |
| **= Expected On-Hand (at cutoff)** | **`441`** | `517 + 37 - 65 - 2 - 46 = 441` |
| Physical Shelf Count | **`441`** | Sum of `04_physical_count_20261122.csv` |
| **Net Unit Variance (Physical - Expected)** | **`+0`** | `441 - 441 = +0` (Net Cost Impact: `$-2.20`) |
| Unfulfilled / Committed Cutoff Units | `3` | Still physically on shelf; deducted only from Available Stock |

## 2. Per-(Warehouse, SKU) Reconciliation Table

| Warehouse | SKU | Opening | +Inbound | -Sales | -ExtraFulfill | -NonSaleOut | Expected | Physical | Variance | Cost Impact | Committed | Status |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `WH-MAIN` | `KIT-MUG-350-BLK` | 48 | 20 | 8 | 2 | 0 | 58 | 58 | **+0** | `$+0.00` | 0 | `MATCH` |
| `WH-MAIN` | `KIT-MUG-350-WHT` | 32 | 2 | 7 | 0 | 0 | 27 | 25 | **-2** | `$-13.00` | 0 | `SHORTAGE` |
| `WH-MAIN` | `CHG-GAN-65W-US` | 60 | 15 | 12 | 0 | 0 | 63 | 63 | **+0** | `$+0.00` | 0 | `MATCH` |
| `WH-MAIN` | `CBL-USBC-2M-NYL` | 120 | 0 | 25 | 0 | 0 | 95 | 95 | **+0** | `$+0.00` | 0 | `MATCH` |
| `WH-MAIN` | `PET-BOWL-SS-M` | 25 | 0 | 8 | 0 | 1 | 16 | 16 | **+0** | `$+0.00` | 0 | `MATCH` |
| `WH-MAIN` | `PET-LEASH-6FT-RED` | 18 | 0 | 5 | 0 | 0 | 13 | 15 | **+2** | `$+10.80` | 0 | `SURPLUS` |
| `WH-MAIN` | `PKG-BOX-300X200` | 200 | 0 | 0 | 0 | 45 | 155 | 155 | **+0** | `$+0.00` | 0 | `MATCH` |
| `WH-MAIN` | `KIT-FILTER-4PK` | 14 | 0 | 0 | 0 | 0 | 14 | 14 | **+0** | `$+0.00` | 3 | `MATCH` |
| **ALL** | **TOTAL (8 SKUs)** | **517** | **37** | **65** | **2** | **46** | **441** | **441** | **+0** | **`$-2.20`** | **3** | **`CLEAN`** |

## 3. Audit Trail, Deduplication & `NEEDS_REVIEW` (`待核`) Items

| Severity | Type | Warehouse | SKU | Source File & Row | Detail |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `DEDUPED` | `DUPLICATE_SALES_ROW` | `WH-MAIN` | `CHG-GAN-65W-US` | `02_weekly_sales_pii_stripped.csv:row_6 (ORD-8804/FUL-8804-1)` | Exact duplicate of 02_weekly_sales_pii_stripped.csv:row_5 (ORD-8804/FUL-8804-1) (qty=12); excluded from sales total. |
| `CUTOFF_INFO` | `UNFULFILLED_COMMITTED_CUTOFF` | `WH-MAIN` | `KIT-FILTER-4PK` | `02_weekly_sales_pii_stripped.csv:row_10 (ORD-8808)` | Order ORD-8808 qty=3 is `unfulfilled_committed` at cutoff; remains physically on shelf, tracked under committed stock. |
| `DEDUPED` | `DEDUPED_FULFILLMENT_LINK` | `WH-MAIN` | `KIT-MUG-350-BLK` | `03_inbound_outbound_movements.csv:row_3 (SHP-8801-1)` | Movement `outbound_sale` qty=6 matches fulfilled sale `02_weekly_sales_pii_stripped.csv:row_2 (ORD-8801/FUL-8801-1)` via (ORD-8801, FUL-8801-1); deduplicated to prevent double deduction. |
| `INFO` | `DISTINCT_FULFILLMENT_COUNTED` | `WH-MAIN` | `KIT-MUG-350-BLK` | `03_inbound_outbound_movements.csv:row_4 (SHP-8802-B)` | Counted distinct `outbound_sale` fulfillment (ORD-8802/FUL-8802-B, qty=2) not present in sales export. |
| `VARIANCE` | `PHYSICAL_SHORTAGE` | `WH-MAIN` | `KIT-MUG-350-WHT` | `01_opening_stock_20261116.csv:row_3 | 04_physical_count_20261122.csv:row_3 (Main Shelf A2)` | Expected 27 on hand, counted 25 (variance -2, cost impact $-13.00). |
| `VARIANCE` | `PHYSICAL_SURPLUS` | `WH-MAIN` | `PET-LEASH-6FT-RED` | `01_opening_stock_20261116.csv:row_7 | 04_physical_count_20261122.csv:row_7 (Shelf C2)` | Expected 13 on hand, counted 15 (variance +2, cost impact $+10.80). |
