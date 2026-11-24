# Supplier Invoice Cost-Change & Two-Shop Shelf-Label Repricing Checklist (Synthetic Sample, 8/20 SKUs)

> **Owner-Review-Only Deliverable (Never Auto-Edits Live Store)**: Prepared from 1 redacted synthetic supplier invoice (`<=20 SKUs`), current Shopify unit costs, and owner target margins. Explicitly normalizes pack units (`case/box/carton -> single unit`) and VAT basis (`ex-VAT` vs `inc-VAT`, 20% standard vs 0% zero-rated). Store owner approves before updating Shopify POS or printing shelf labels.

- **SKUs Audited**: `8` (scope cap: `<=20 SKUs / invoice`)
- **SKUs Requiring Reprice**: `7` | **Hold Price**: `1`
- **Shelf Labels to Print**: Shop 1 = `6` labels | Shop 2 = `6` labels

## 1. Per-SKU Cost Change & Suggested Retail Price (Owner Approval Table)

| SKU | Pack Unit | Invoice Tax Basis | Old Cost (ex-VAT) | New Cost (ex-VAT) | Cost Delta | Cur Retail (inc-VAT) | Margin If Unchanged | Target Margin | Suggested Retail (inc-VAT / ex-VAT) | Action | Source Invoice Line |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| `DOG-FOOD-SALMON-2KG` | case_of_6 (6 units) | ex_vat (VAT 20%) | £7.10 | £7.80 | **+0.70 (+9.9%)** | £14.99 | 37.6% | 42.0% | **£16.49** (£13.74) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_2 (L01)` |
| `DOG-TREAT-DUCK-200G` | box_of_12 (12 units) | ex_vat (VAT 20%) | £2.05 | £2.30 | **+0.25 (+12.2%)** | £4.99 | 44.7% | 50.0% | **£5.99** (£4.99) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_3 (L02)` |
| `CAT-LITTER-CLUMP-10L` | single_bag (1 units) | inc_vat (VAT 20%) | £5.50 | £6.00 | **+0.50 (+9.1%)** | £11.99 | 39.9% | 45.0% | **£13.49** (£11.24) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_4 (L03)` |
| `DOG-LEASH-REFLECT-M` | pack_of_4 (4 units) | ex_vat (VAT 20%) | £5.00 | £5.00 | **+0.00 (+0.0%)** | £11.99 | 50.0% | 50.0% | **£11.99** (£9.99) | `HOLD_PRICE` | `01_supplier_invoice_redacted_sample.csv:row_5 (L04)` |
| `CAT-WAND-FEATHER` | carton_of_20 (20 units) | ex_vat (VAT 20%) | £1.45 | £1.70 | **+0.25 (+17.2%)** | £3.99 | 48.9% | 55.0% | **£4.99** (£4.16) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_6 (L05)` |
| `DOG-SHAMPOO-OAT-500ML` | case_of_6 (6 units) | ex_vat (VAT 20%) | £3.90 | £4.40 | **+0.50 (+12.8%)** | £8.99 | 41.3% | 48.0% | **£10.49** (£8.74) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_7 (L06)` |
| `WILD-BIRD-SEED-5KG` | single_sack (1 units) | ex_vat (VAT 0%) | £4.80 | £5.40 | **+0.60 (+12.5%)** | £8.49 | 36.4% | 40.0% | **£9.49** (£9.49) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_8 (L07)` |
| `PET-BOWL-SS-MED` | pack_of_10 (10 units) | ex_vat (VAT 20%) | £2.80 | £3.10 | **+0.30 (+10.7%)** | £6.99 | 46.8% | 50.0% | **£7.49** (£6.24) | `REPRICE_AND_RELABEL` | `01_supplier_invoice_redacted_sample.csv:row_9 (L08)` |

## 2. Two-Shop Shelf-Label Swap Checklists

### Shop 1 — Shelf Labels to Replace

| SKU | Description | Old Shelf Price (inc-VAT) | Proposed Shelf Price (inc-VAT) | Source Line | Owner Approved [ ] |
| :--- | :--- | ---: | ---: | :--- | :---: |
| `DOG-FOOD-SALMON-2KG` | Grain-Free Salmon Dog Food 2kg | £14.99 | **£16.49** | `01_supplier_invoice_redacted_sample.csv:row_2 (L01)` | [ ] |
| `DOG-TREAT-DUCK-200G` | Duck Jerky Treats 200g | £4.99 | **£5.99** | `01_supplier_invoice_redacted_sample.csv:row_3 (L02)` | [ ] |
| `CAT-LITTER-CLUMP-10L` | Clumping Plant Cat Litter 10L | £11.99 | **£13.49** | `01_supplier_invoice_redacted_sample.csv:row_4 (L03)` | [ ] |
| `DOG-SHAMPOO-OAT-500ML` | Oatmeal Sensitive Dog Shampoo 500ml | £8.99 | **£10.49** | `01_supplier_invoice_redacted_sample.csv:row_7 (L06)` | [ ] |
| `WILD-BIRD-SEED-5KG` | Wild Bird Seed Mix 5kg (Zero-Rated) | £8.49 | **£9.49** | `01_supplier_invoice_redacted_sample.csv:row_8 (L07)` | [ ] |
| `PET-BOWL-SS-MED` | Non-Slip Stainless Bowl Medium | £6.99 | **£7.49** | `01_supplier_invoice_redacted_sample.csv:row_9 (L08)` | [ ] |

### Shop 2 — Shelf Labels to Replace

| SKU | Description | Old Shelf Price (inc-VAT) | Proposed Shelf Price (inc-VAT) | Source Line | Owner Approved [ ] |
| :--- | :--- | ---: | ---: | :--- | :---: |
| `DOG-FOOD-SALMON-2KG` | Grain-Free Salmon Dog Food 2kg | £14.99 | **£16.49** | `01_supplier_invoice_redacted_sample.csv:row_2 (L01)` | [ ] |
| `DOG-TREAT-DUCK-200G` | Duck Jerky Treats 200g | £4.99 | **£5.99** | `01_supplier_invoice_redacted_sample.csv:row_3 (L02)` | [ ] |
| `CAT-WAND-FEATHER` | Interactive Feather Wand Toy | £3.99 | **£4.99** | `01_supplier_invoice_redacted_sample.csv:row_6 (L05)` | [ ] |
| `DOG-SHAMPOO-OAT-500ML` | Oatmeal Sensitive Dog Shampoo 500ml | £8.99 | **£10.49** | `01_supplier_invoice_redacted_sample.csv:row_7 (L06)` | [ ] |
| `WILD-BIRD-SEED-5KG` | Wild Bird Seed Mix 5kg (Zero-Rated) | £8.49 | **£9.49** | `01_supplier_invoice_redacted_sample.csv:row_8 (L07)` | [ ] |
| `PET-BOWL-SS-MED` | Non-Slip Stainless Bowl Medium | £6.99 | **£7.49** | `01_supplier_invoice_redacted_sample.csv:row_9 (L08)` | [ ] |
