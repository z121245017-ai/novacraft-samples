#!/usr/bin/env python3
"""Deterministic Supplier Invoice Cost-Change & Two-Shop Shelf-Label Repricing Checklist (<=20 SKUs).

Synthetic-data sample inspired by independent UK multi-location retail shops (e.g., two pet shops
on Shopify POS): takes 1 sanitized/redacted supplier invoice + current unit costs + owner target
margin (<=20 SKUs), and outputs ONLY an owner-reviewable checklist (NEVER auto-edits live store
prices) with:
  - Pack unit conversion (case/pack/bag -> single retail sellable unit)
  - Explicit VAT basis (ex-VAT vs inc-VAT at UK 20% / 0% zero-rated)
  - Exact original invoice line provenance (`invoice_file:row_num`)
  - Unit cost delta (GBP & %), suggested new retail price (ex-VAT & inc-VAT), and Shop 1 / Shop 2
    shelf-label swap checklist.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

BASE = Path(__file__).parent

SYNTHETIC_INVOICE = [
    {"invoice_line": "L01", "supplier_code": "PET-DRY-2KG", "sku": "DOG-FOOD-SALMON-2KG", "description": "Grain-Free Salmon Dog Food 2kg", "pack_unit": "case_of_6", "units_per_pack": 6, "pack_price_gbp": "46.80", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "20", "notes": "Supplier Oct price rise"},
    {"invoice_line": "L02", "supplier_code": "PET-TRT-200", "sku": "DOG-TREAT-DUCK-200G", "description": "Duck Jerky Treats 200g", "pack_unit": "box_of_12", "units_per_pack": 12, "pack_price_gbp": "27.60", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "20", "notes": ""},
    {"invoice_line": "L03", "supplier_code": "CAT-LIT-10L", "sku": "CAT-LITTER-CLUMP-10L", "description": "Clumping Plant Cat Litter 10L", "pack_unit": "single_bag", "units_per_pack": 1, "pack_price_gbp": "7.20", "invoice_tax_basis": "inc_vat", "vat_rate_pct": "20", "notes": "Invoice quotes inc-VAT!"},
    {"invoice_line": "L04", "supplier_code": "DOG-LSH-6FT", "sku": "DOG-LEASH-REFLECT-M", "description": "Reflective Nylon Dog Leash 6ft", "pack_unit": "pack_of_4", "units_per_pack": 4, "pack_price_gbp": "20.00", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "20", "notes": "Unchanged cost"},
    {"invoice_line": "L05", "supplier_code": "CAT-TOY-FTH", "sku": "CAT-WAND-FEATHER", "description": "Interactive Feather Wand Toy", "pack_unit": "carton_of_20", "units_per_pack": 20, "pack_price_gbp": "34.00", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "20", "notes": "Promo ended"},
    {"invoice_line": "L06", "supplier_code": "PET-SHM-500", "sku": "DOG-SHAMPOO-OAT-500ML", "description": "Oatmeal Sensitive Dog Shampoo 500ml", "pack_unit": "case_of_6", "units_per_pack": 6, "pack_price_gbp": "26.40", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "20", "notes": "New bottle price"},
    {"invoice_line": "L07", "supplier_code": "BRD-SD-5KG", "sku": "WILD-BIRD-SEED-5KG", "description": "Wild Bird Seed Mix 5kg (Zero-Rated)", "pack_unit": "single_sack", "units_per_pack": 1, "pack_price_gbp": "5.40", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "0", "notes": "UK 0% VAT agricultural/bird feed"},
    {"invoice_line": "L08", "supplier_code": "PET-BWL-SSM", "sku": "PET-BOWL-SS-MED", "description": "Non-Slip Stainless Bowl Medium", "pack_unit": "pack_of_10", "units_per_pack": 10, "pack_price_gbp": "31.00", "invoice_tax_basis": "ex_vat", "vat_rate_pct": "20", "notes": "Steel surcharge"},
]

SYNTHETIC_CURRENT_CATALOG = [
    {"sku": "DOG-FOOD-SALMON-2KG", "old_unit_cost_ex_vat_gbp": "7.10", "current_retail_inc_vat_gbp": "14.99", "target_margin_pct": "42", "shop1_stocked": "yes", "shop2_stocked": "yes"},
    {"sku": "DOG-TREAT-DUCK-200G", "old_unit_cost_ex_vat_gbp": "2.05", "current_retail_inc_vat_gbp": "4.99", "target_margin_pct": "50", "shop1_stocked": "yes", "shop2_stocked": "yes"},
    {"sku": "CAT-LITTER-CLUMP-10L", "old_unit_cost_ex_vat_gbp": "5.50", "current_retail_inc_vat_gbp": "11.99", "target_margin_pct": "45", "shop1_stocked": "yes", "shop2_stocked": "no"},
    {"sku": "DOG-LEASH-REFLECT-M", "old_unit_cost_ex_vat_gbp": "5.00", "current_retail_inc_vat_gbp": "11.99", "target_margin_pct": "50", "shop1_stocked": "yes", "shop2_stocked": "yes"},
    {"sku": "CAT-WAND-FEATHER", "old_unit_cost_ex_vat_gbp": "1.45", "current_retail_inc_vat_gbp": "3.99", "target_margin_pct": "55", "shop1_stocked": "no", "shop2_stocked": "yes"},
    {"sku": "DOG-SHAMPOO-OAT-500ML", "old_unit_cost_ex_vat_gbp": "3.90", "current_retail_inc_vat_gbp": "8.99", "target_margin_pct": "48", "shop1_stocked": "yes", "shop2_stocked": "yes"},
    {"sku": "WILD-BIRD-SEED-5KG", "old_unit_cost_ex_vat_gbp": "4.80", "current_retail_inc_vat_gbp": "8.49", "target_margin_pct": "40", "shop1_stocked": "yes", "shop2_stocked": "yes"},
    {"sku": "PET-BOWL-SS-MED", "old_unit_cost_ex_vat_gbp": "2.80", "current_retail_inc_vat_gbp": "6.99", "target_margin_pct": "50", "shop1_stocked": "yes", "shop2_stocked": "yes"},
]


def round_to_99(price: float) -> float:
    """Round up to clean retail .49 or .99 ending so margin target is preserved."""
    whole = math.floor(price)
    if price <= whole + 0.49:
        return round(whole + 0.49, 2)
    return round(whole + 0.99, 2)


def main() -> None:
    inv_path = BASE / "01_supplier_invoice_redacted_sample.csv"
    cat_path = BASE / "02_current_costs_and_margins_sample.csv"
    with inv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(SYNTHETIC_INVOICE[0].keys()))
        w.writeheader()
        w.writerows(SYNTHETIC_INVOICE)
    with cat_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(SYNTHETIC_CURRENT_CATALOG[0].keys()))
        w.writeheader()
        w.writerows(SYNTHETIC_CURRENT_CATALOG)

    cat_map = {r["sku"]: r for r in SYNTHETIC_CURRENT_CATALOG}
    out_rows = []
    shop1_labels = []
    shop2_labels = []

    for row_num, inv in enumerate(SYNTHETIC_INVOICE, start=2):
        sku = inv["sku"]
        c = cat_map[sku]
        units = int(inv["units_per_pack"])
        pack_price = float(inv["pack_price_gbp"])
        vat_rate = float(inv["vat_rate_pct"]) / 100.0
        basis = inv["invoice_tax_basis"]

        # Normalize unit cost strictly to EX-VAT GBP per single retail unit
        raw_unit = pack_price / units
        if basis == "inc_vat":
            new_cost_ex_vat = round(raw_unit / (1.0 + vat_rate), 4)
        else:
            new_cost_ex_vat = round(raw_unit, 4)

        old_cost_ex_vat = float(c["old_unit_cost_ex_vat_gbp"])
        cost_delta = round(new_cost_ex_vat - old_cost_ex_vat, 4)
        cost_delta_pct = (cost_delta / old_cost_ex_vat * 100.0) if old_cost_ex_vat else 0.0

        cur_retail_inc_vat = float(c["current_retail_inc_vat_gbp"])
        cur_retail_ex_vat = cur_retail_inc_vat / (1.0 + vat_rate)
        margin_at_cur_price_pct = ((cur_retail_ex_vat - new_cost_ex_vat) / cur_retail_ex_vat * 100.0) if cur_retail_ex_vat else 0.0
        target_margin = float(c["target_margin_pct"]) / 100.0

        # Required ex-VAT retail price to hold owner target gross margin
        req_ex_vat = new_cost_ex_vat / (1.0 - target_margin)
        req_inc_vat = req_ex_vat * (1.0 + vat_rate)
        suggested_inc_vat = round_to_99(req_inc_vat) if cost_delta > 0.005 and margin_at_cur_price_pct < float(c["target_margin_pct"]) else cur_retail_inc_vat
        suggested_ex_vat = round(suggested_inc_vat / (1.0 + vat_rate), 2)
        new_margin_pct = ((suggested_ex_vat - new_cost_ex_vat) / suggested_ex_vat * 100.0) if suggested_ex_vat else 0.0

        reprice_needed = suggested_inc_vat > cur_retail_inc_vat
        src_ref = f"{inv_path.name}:row_{row_num} ({inv['invoice_line']})"

        rec = {
            "sku": sku,
            "description": inv["description"],
            "source_invoice_line": src_ref,
            "pack_unit": f"{inv['pack_unit']} ({units} units)",
            "invoice_tax_basis": f"{basis} (VAT {inv['vat_rate_pct']}%)",
            "old_unit_cost_ex_vat_gbp": f"{old_cost_ex_vat:.2f}",
            "new_unit_cost_ex_vat_gbp": f"{new_cost_ex_vat:.2f}",
            "cost_delta_gbp": f"{cost_delta:+.2f}",
            "cost_delta_pct": f"{cost_delta_pct:+.1f}%",
            "current_retail_inc_vat_gbp": f"{cur_retail_inc_vat:.2f}",
            "margin_if_unchanged_pct": f"{margin_at_cur_price_pct:.1f}%",
            "target_margin_pct": f"{float(c['target_margin_pct']):.1f}%",
            "suggested_retail_ex_vat_gbp": f"{suggested_ex_vat:.2f}",
            "suggested_retail_inc_vat_gbp": f"{suggested_inc_vat:.2f}",
            "margin_at_suggested_pct": f"{new_margin_pct:.1f}%",
            "reprice_action": "REPRICE_AND_RELABEL" if reprice_needed else "HOLD_PRICE",
            "shop1_relabel": "YES" if (reprice_needed and c["shop1_stocked"] == "yes") else "NO",
            "shop2_relabel": "YES" if (reprice_needed and c["shop2_stocked"] == "yes") else "NO",
        }
        out_rows.append(rec)
        if rec["shop1_relabel"] == "YES":
            shop1_labels.append(rec)
        if rec["shop2_relabel"] == "YES":
            shop2_labels.append(rec)

    out_csv = BASE / "repricing_review_table.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    md = [
        "# Supplier Invoice Cost-Change & Two-Shop Shelf-Label Repricing Checklist (Synthetic Sample, 8/20 SKUs)",
        "",
        "> **Owner-Review-Only Deliverable (Never Auto-Edits Live Store)**: Prepared from 1 redacted synthetic supplier invoice (`<=20 SKUs`), current Shopify unit costs, and owner target margins. Explicitly normalizes pack units (`case/box/carton -> single unit`) and VAT basis (`ex-VAT` vs `inc-VAT`, 20% standard vs 0% zero-rated). Store owner approves before updating Shopify POS or printing shelf labels.",
        "",
        f"- **SKUs Audited**: `{len(out_rows)}` (scope cap: `<=20 SKUs / invoice`)",
        f"- **SKUs Requiring Reprice**: `{sum(1 for r in out_rows if r['reprice_action'] == 'REPRICE_AND_RELABEL')}` | **Hold Price**: `{sum(1 for r in out_rows if r['reprice_action'] == 'HOLD_PRICE')}`",
        f"- **Shelf Labels to Print**: Shop 1 = `{len(shop1_labels)}` labels | Shop 2 = `{len(shop2_labels)}` labels",
        "",
        "## 1. Per-SKU Cost Change & Suggested Retail Price (Owner Approval Table)",
        "",
        "| SKU | Pack Unit | Invoice Tax Basis | Old Cost (ex-VAT) | New Cost (ex-VAT) | Cost Delta | Cur Retail (inc-VAT) | Margin If Unchanged | Target Margin | Suggested Retail (inc-VAT / ex-VAT) | Action | Source Invoice Line |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- | :--- |",
    ]
    for r in out_rows:
        md.append(
            f"| `{r['sku']}` | {r['pack_unit']} | {r['invoice_tax_basis']} | £{r['old_unit_cost_ex_vat_gbp']} | "
            f"£{r['new_unit_cost_ex_vat_gbp']} | **{r['cost_delta_gbp']} ({r['cost_delta_pct']})** | £{r['current_retail_inc_vat_gbp']} | "
            f"{r['margin_if_unchanged_pct']} | {r['target_margin_pct']} | **£{r['suggested_retail_inc_vat_gbp']}** (£{r['suggested_retail_ex_vat_gbp']}) | "
            f"`{r['reprice_action']}` | `{r['source_invoice_line']}` |"
        )

    md += [
        "",
        "## 2. Two-Shop Shelf-Label Swap Checklists",
        "",
        "### Shop 1 — Shelf Labels to Replace",
        "",
        "| SKU | Description | Old Shelf Price (inc-VAT) | Proposed Shelf Price (inc-VAT) | Source Line | Owner Approved [ ] |",
        "| :--- | :--- | ---: | ---: | :--- | :---: |",
    ]
    for r in shop1_labels:
        md.append(f"| `{r['sku']}` | {r['description']} | £{r['current_retail_inc_vat_gbp']} | **£{r['suggested_retail_inc_vat_gbp']}** | `{r['source_invoice_line']}` | [ ] |")

    md += [
        "",
        "### Shop 2 — Shelf Labels to Replace",
        "",
        "| SKU | Description | Old Shelf Price (inc-VAT) | Proposed Shelf Price (inc-VAT) | Source Line | Owner Approved [ ] |",
        "| :--- | :--- | ---: | ---: | :--- | :---: |",
    ]
    for r in shop2_labels:
        md.append(f"| `{r['sku']}` | {r['description']} | £{r['current_retail_inc_vat_gbp']} | **£{r['suggested_retail_inc_vat_gbp']}** | `{r['source_invoice_line']}` | [ ] |")

    (BASE / "repricing_review_checklist.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"OK supplier-invoice-repricing-demo: skus={len(out_rows)}, shop1_labels={len(shop1_labels)}, shop2_labels={len(shop2_labels)}")


if __name__ == "__main__":
    main()
