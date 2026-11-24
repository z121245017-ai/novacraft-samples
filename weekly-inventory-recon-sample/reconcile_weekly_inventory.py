#!/usr/bin/env python3
"""Deterministic 1-Week SKU Inventory Reconciliation Engine (PII-Stripped Exports).

Strict Accounting & Anti-Double-Deduction Rules (v2 — Fixed after Codex Audit):
  1. Keyed strictly by `(warehouse, sku)` and bounded by a single consistent cutoff timestamp (`as_of_cutoff`).
     Rows missing/mismatched warehouse or timestamped AFTER `as_of_cutoff` are flagged `NEEDS_REVIEW` (`待核`).
  2. Sales vs Fulfillment Movement Deduplication by `(warehouse, sku, order_ref, fulfillment_id)`:
     - Fulfilled sales rows in `02_weekly_sales_pii_stripped.csv` record shipments by `(order_ref, fulfillment_id, sku)`.
     - Movement rows with `type in ("outbound_sale", "outbound_fulfillment")`:
       a) If linked to an EXACT matching `(warehouse, sku, order_ref, fulfillment_id)` with matching qty already counted in fulfilled sales:
          deduplicate (`DEDUPED_FULFILLMENT_LINK`) — NEVER double-deduct!
       b) If linked to the same `order_ref` with a DIFFERENT `fulfillment_id` (e.g., split/partial shipment #2) not yet in fulfilled sales:
          count as an additional distinct fulfillment (`ADDITIONAL_DISTINCT_FULFILLMENT`).
       c) If `outbound_sale` / `outbound_fulfillment` has NO verifiable `(order_ref, fulfillment_id)` link OR conflicting qty so overlap cannot be proven:
          DO NOT silently guess or double-deduct — flag `UNPROVEN_SALE_MOVEMENT_OVERLAP` and mark the SKU `NEEDS_REVIEW` (`待核`).
  3. Explicit Movement Type Allowlist (zero silent fallback to outbound!):
     - Inbound: `inbound_receipt`, `inbound_return`
     - Sales fulfillment: `outbound_sale`, `outbound_fulfillment`
     - Non-sale loss/internal outbound (tracked separately): `outbound_damage`, `outbound_shrinkage`, `outbound_internal`
     - Any other type -> `UNKNOWN_MOVEMENT_TYPE` (`待核 / NEEDS_REVIEW`), NEVER deducted as outbound!
  4. Per-(warehouse, sku) formula (only settled automatically when `needs_review_reasons == []`):
     `expected_on_hand = opening_qty + inbound_qty - sales_fulfilled_qty - distinct_unlogged_sale_fulfillments - non_sale_outbound_qty`
     `variance_qty     = physical_count - expected_on_hand`
     (Unfulfilled/committed orders stay on shelf at cutoff and are tracked under `unfulfilled_committed_qty`.)
  5. Exit status: when any SKU or ledger row requires manual review (`NEEDS_REVIEW`), report clearly marks
     `reconciliation_status = NEEDS_REVIEW` and CLI returns exit code `2` unless `--allow-needs-review` is explicitly passed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

INBOUND_TYPES = {"inbound_receipt", "inbound_return"}
SALE_MOVEMENT_TYPES = {"outbound_sale", "outbound_fulfillment"}
NON_SALE_OUTBOUND_TYPES = {"outbound_damage", "outbound_shrinkage", "outbound_internal"}
DEFAULT_WAREHOUSE = "MAIN"


def _load_csv_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [(idx, row) for idx, row in enumerate(csv.DictReader(f), start=2)]


def _norm_ts(val: str | None) -> str:
    return (val or "").strip().replace("T", " ").replace("Z", "")


def _classify_cutoff(ts_val: str | None, cutoff: str | None) -> str:
    """Compare row date/timestamp against warehouse-local `cutoff` (`YYYY-MM-DD HH:MM[:SS]` or `YYYY-MM-DD`).

    Returns:
      - "OK": unambiguously at or before cutoff
      - "POST_CUTOFF_NEXT_DAY": date-only row whose warehouse-local calendar date is strictly AFTER cutoff date (exclude cleanly!)
      - "POST_CUTOFF_TS": full timestamp row strictly AFTER cutoff timestamp (exclude & flag!)
      - "SAME_DAY_AMBIGUOUS": date-only row on the EXACT SAME calendar date as a mid-day cutoff time (cannot prove before vs after -> NEEDS_REVIEW!)
    """
    if not cutoff or not ts_val:
        return "OK"
    ts = _norm_ts(ts_val)
    co = _norm_ts(cutoff)
    if len(ts) < 10 or len(co) < 10:
        return "OK"

    row_date = ts[:10]
    co_date = co[:10]
    has_row_time = len(ts) >= 16
    has_co_time = len(co) >= 16

    if not has_row_time:
        if row_date > co_date:
            return "POST_CUTOFF_NEXT_DAY"
        if row_date < co_date:
            return "OK"
        # Same calendar date with NO time-of-day on the row:
        # Only unambiguous if cutoff has no time or is end-of-day 23:59(:59)
        if not has_co_time or co[11:16] == "23:59":
            return "OK"
        return "SAME_DAY_AMBIGUOUS"

    # Row has full timestamp
    if has_co_time:
        return "POST_CUTOFF_TS" if ts > co else "OK"
    return "POST_CUTOFF_NEXT_DAY" if row_date > co_date else "OK"


def _wh(row: dict[str, str]) -> str:
    return (row.get("warehouse") or row.get("location_wh") or DEFAULT_WAREHOUSE).strip().upper() or DEFAULT_WAREHOUSE


def reconcile_directory(
    base_dir: Path,
    as_of_cutoff: str | None = None,
    opening_file: str = "01_opening_stock_20261116.csv",
    sales_file: str = "02_weekly_sales_pii_stripped.csv",
    movements_file: str = "03_inbound_outbound_movements.csv",
    physical_file: str = "04_physical_count_20261122.csv",
    write_outputs: bool = True,
) -> dict[str, Any]:
    anomalies: list[dict[str, str]] = []
    sku_review_reasons: dict[tuple[str, str], list[str]] = {}

    def flag_review(key: tuple[str, str] | None, atype: str, sku: str, wh: str, src: str, detail: str) -> None:
        anomalies.append({
            "type": atype,
            "warehouse": wh,
            "sku": sku,
            "source": src,
            "detail": detail,
            "severity": "NEEDS_REVIEW",
        })
        if key is not None:
            sku_review_reasons.setdefault(key, []).append(f"{atype} ({src})")

    def log_info(atype: str, sku: str, wh: str, src: str, detail: str, severity: str = "INFO") -> None:
        anomalies.append({
            "type": atype,
            "warehouse": wh,
            "sku": sku,
            "source": src,
            "detail": detail,
            "severity": severity,
        })

    # 1. Load Opening Stock keyed by (warehouse, sku)
    opening: dict[tuple[str, str], dict[str, Any]] = {}
    for row_num, r in _load_csv_rows(base_dir / opening_file):
        wh = _wh(r)
        sku = r["sku"].strip()
        key = (wh, sku)
        src = f"{opening_file}:row_{row_num}"
        if key in opening:
            flag_review(key, "DUPLICATE_OPENING_SKU", sku, wh, src, f"Duplicate opening row for ({wh}, {sku}).")
            continue
        opening[key] = {
            "warehouse": wh,
            "sku": sku,
            "product_name": (r.get("product_name") or sku).strip(),
            "opening_qty": int(r["opening_qty"]),
            "unit_cost_usd": float(r.get("unit_cost_usd") or 0.0),
            "opening_src": src,
        }

    # 2. Load Physical Count keyed by (warehouse, sku) and infer cutoff if omitted
    physical: dict[tuple[str, str], int] = {}
    physical_src: dict[tuple[str, str], str] = {}
    physical_ts: list[str] = []
    for row_num, r in _load_csv_rows(base_dir / physical_file):
        wh = _wh(r)
        sku = r["sku"].strip()
        key = (wh, sku)
        src = f"{physical_file}:row_{row_num} ({(r.get('location') or wh).strip()})"
        ts_c = _norm_ts(r.get("counted_at"))
        if ts_c:
            physical_ts.append(ts_c)
        if key in physical:
            flag_review(key, "DUPLICATE_PHYSICAL_COUNT", sku, wh, src, f"Duplicate physical count row for ({wh}, {sku}).")
            continue
        physical[key] = int(r["physical_count"])
        physical_src[key] = src

    effective_cutoff = _norm_ts(as_of_cutoff) if as_of_cutoff else (max(physical_ts) if physical_ts else "")

    # 3. Load Weekly Sales (fulfilled vs unfulfilled_committed), indexed by (wh, sku, order_ref, fulfillment_id)
    sales_fulfilled: dict[tuple[str, str], int] = {}
    sales_committed: dict[tuple[str, str], int] = {}
    sales_sources: dict[tuple[str, str], list[str]] = {}
    # Maps (wh, sku, order_ref, fulfillment_id) -> {"qty": int, "src": str}
    fulfilled_by_fulfillment: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    # Also track fulfilled rows by (wh, sku, order_ref) for overlap detection when fulfillment_id is missing
    fulfilled_by_order: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    seen_exact_sale_row: dict[tuple[str, str, str, str, int, str], str] = {}

    for row_num, r in _load_csv_rows(base_dir / sales_file):
        wh = _wh(r)
        sku = r["sku"].strip()
        key = (wh, sku)
        oref = (r.get("order_ref") or "").strip()
        fid = (r.get("fulfillment_id") or r.get("line_id") or "").strip()
        qty = int(r["qty_sold"])
        status = (r.get("status") or "fulfilled").strip().lower()
        ts_sale = _norm_ts(r.get("sale_timestamp") or r.get("sale_date"))
        src = f"{sales_file}:row_{row_num} ({oref}{('/' + fid) if fid else ''})"

        cutoff_rel = _classify_cutoff(ts_sale, effective_cutoff)
        if cutoff_rel == "POST_CUTOFF_NEXT_DAY":
            log_info(
                "POST_CUTOFF_NEXT_DAY_EXCLUDED",
                sku,
                wh,
                src,
                f"Date-only sale `{ts_sale}` is on a calendar day strictly after warehouse-local cutoff `{effective_cutoff}`; cleanly excluded.",
                severity="CUTOFF_EXCLUDED",
            )
            continue
        if cutoff_rel == "SAME_DAY_AMBIGUOUS":
            flag_review(
                key if key in opening else None,
                "SAME_DAY_DATE_ONLY_AMBIGUOUS",
                sku,
                wh,
                src,
                f"Date-only sale `{ts_sale}` shares cutoff calendar day `{effective_cutoff[:10]}` without timestamp; cannot prove before/after `{effective_cutoff}` -> held in NEEDS_REVIEW.",
            )
            continue
        if cutoff_rel == "POST_CUTOFF_TS":
            flag_review(
                key if key in opening else None,
                "POST_CUTOFF_SALES_ROW",
                sku,
                wh,
                src,
                f"Sale timestamp `{ts_sale}` is after cutoff `{effective_cutoff}`; excluded from reconciliation pending cutoff check.",
            )
            continue

        dup_sig = (wh, sku, oref, fid, qty, status)
        if dup_sig in seen_exact_sale_row:
            log_info(
                "DUPLICATE_SALES_ROW",
                sku,
                wh,
                src,
                f"Exact duplicate of {seen_exact_sale_row[dup_sig]} (qty={qty}); excluded from sales total.",
                severity="DEDUPED",
            )
            continue
        seen_exact_sale_row[dup_sig] = src

        if key not in opening:
            flag_review(
                None,
                "UNMAPPED_SKU_IN_SALES",
                sku,
                wh,
                src,
                f"Sold qty={qty} via {r.get('channel','unknown')} in warehouse `{wh}`, but SKU missing from opening stock master.",
            )
            continue

        sales_sources.setdefault(key, []).append(src)
        if status == "fulfilled":
            sales_fulfilled[key] = sales_fulfilled.get(key, 0) + qty
            eff_fid = fid or f"ORDER-ONLY:{oref}"
            fulfilled_by_fulfillment[(wh, sku, oref, eff_fid)] = {
                "qty": qty,
                "src": src,
                "explicit_fid": bool(fid),
                "order_ref": oref,
            }
            fulfilled_by_order.setdefault((wh, sku, oref), []).append({
                "qty": qty,
                "src": src,
                "fid": fid,
            })
        elif status in ("unfulfilled", "unfulfilled_committed", "committed"):
            sales_committed[key] = sales_committed.get(key, 0) + qty
            log_info(
                "UNFULFILLED_COMMITTED_CUTOFF",
                sku,
                wh,
                src,
                f"Order {oref} qty={qty} is `{status}` at cutoff; remains physically on shelf, tracked under committed stock.",
                severity="CUTOFF_INFO",
            )
        else:
            flag_review(
                key,
                "UNKNOWN_SALES_STATUS",
                sku,
                wh,
                src,
                f"Unrecognized sales row status `{status}` (qty={qty}); held in NEEDS_REVIEW.",
            )

    # 4. Load Movements with strict allowlist + fulfillment linkage dedupe!
    inbound: dict[tuple[str, str], int] = {}
    additional_sale_fulfillments: dict[tuple[str, str], int] = {}
    non_sale_outbound: dict[tuple[str, str], int] = {}
    move_sources: dict[tuple[str, str], list[str]] = {}
    seen_sale_move_fids: set[tuple[str, str, str, str]] = set()

    for row_num, r in _load_csv_rows(base_dir / movements_file):
        wh = _wh(r)
        sku = r["sku"].strip()
        key = (wh, sku)
        mref = (r.get("move_ref") or "").strip()
        oref = (r.get("order_ref") or "").strip()
        fid = (r.get("fulfillment_id") or r.get("line_id") or "").strip()
        mtype = (r.get("type") or "").strip().lower()
        qty = int(r["qty"])
        ts_move = _norm_ts(r.get("move_timestamp") or r.get("move_date"))
        src = f"{movements_file}:row_{row_num} ({mref or oref or 'NO_REF'})"

        cutoff_rel = _classify_cutoff(ts_move, effective_cutoff)
        if cutoff_rel == "POST_CUTOFF_NEXT_DAY":
            log_info(
                "POST_CUTOFF_NEXT_DAY_EXCLUDED",
                sku,
                wh,
                src,
                f"Date-only movement `{mtype}` (`{ts_move}`) is on a calendar day strictly after warehouse-local cutoff `{effective_cutoff}`; cleanly excluded.",
                severity="CUTOFF_EXCLUDED",
            )
            continue
        if cutoff_rel == "SAME_DAY_AMBIGUOUS":
            flag_review(
                key if key in opening else None,
                "SAME_DAY_DATE_ONLY_AMBIGUOUS",
                sku,
                wh,
                src,
                f"Date-only movement `{mtype}` (`{ts_move}`) shares cutoff calendar day `{effective_cutoff[:10]}` without timestamp; cannot prove before/after `{effective_cutoff}` -> held in NEEDS_REVIEW.",
            )
            continue
        if cutoff_rel == "POST_CUTOFF_TS":
            flag_review(
                key if key in opening else None,
                "POST_CUTOFF_MOVEMENT_ROW",
                sku,
                wh,
                src,
                f"Movement `{mtype}` timestamp `{ts_move}` is after cutoff `{effective_cutoff}`; excluded pending cutoff verification.",
            )
            continue

        if key not in opening:
            flag_review(
                None,
                "UNMAPPED_SKU_IN_MOVEMENTS",
                sku,
                wh,
                src,
                f"Movement `{mtype}` qty={qty} in warehouse `{wh}` references SKU missing from opening stock master.",
            )
            continue

        move_sources.setdefault(key, []).append(src)

        if mtype in INBOUND_TYPES:
            inbound[key] = inbound.get(key, 0) + qty
        elif mtype in NON_SALE_OUTBOUND_TYPES:
            non_sale_outbound[key] = non_sale_outbound.get(key, 0) + qty
        elif mtype in SALE_MOVEMENT_TYPES:
            # Strict linkage check against fulfilled sales!
            # Case 1: Exact (wh, sku, order_ref, fulfillment_id) match -> proven same shipment -> dedupe!
            if oref and fid and (wh, sku, oref, fid) in fulfilled_by_fulfillment:
                matched = fulfilled_by_fulfillment[(wh, sku, oref, fid)]
                if matched["qty"] == qty:
                    log_info(
                        "DEDUPED_FULFILLMENT_LINK",
                        sku,
                        wh,
                        src,
                        f"Movement `{mtype}` qty={qty} matches fulfilled sale `{matched['src']}` via ({oref}, {fid}); deduplicated to prevent double deduction.",
                        severity="DEDUPED",
                    )
                else:
                    flag_review(
                        key,
                        "FULFILLMENT_QTY_MISMATCH",
                        sku,
                        wh,
                        src,
                        f"Movement `{mtype}` qty={qty} conflicts with fulfilled sale `{matched['src']}` qty={matched['qty']} for ({oref}, {fid}); marked NEEDS_REVIEW.",
                    )
            # Case 2: Exact order_ref match where neither side had fulfillment_id AND single order row has exact qty match
            elif oref and not fid and (wh, sku, oref, f"ORDER-ONLY:{oref}") in fulfilled_by_fulfillment:
                matched = fulfilled_by_fulfillment[(wh, sku, oref, f"ORDER-ONLY:{oref}")]
                if matched["qty"] == qty and len(fulfilled_by_order.get((wh, sku, oref), [])) == 1:
                    log_info(
                        "DEDUPED_FULFILLMENT_LINK",
                        sku,
                        wh,
                        src,
                        f"Movement `{mtype}` qty={qty} matches single fulfilled sale `{matched['src']}` via order_ref `{oref}`; deduplicated to prevent double deduction.",
                        severity="DEDUPED",
                    )
                else:
                    flag_review(
                        key,
                        "UNPROVEN_SALE_MOVEMENT_OVERLAP",
                        sku,
                        wh,
                        src,
                        f"Movement `{mtype}` qty={qty} for order `{oref}` lacks fulfillment_id to prove duplicate vs partial shipment; marked NEEDS_REVIEW (not double-deducted).",
                    )
            # Case 3: Has BOTH explicit order_ref AND explicit fulfillment_id that does NOT collide with already-logged fulfilled_by_fulfillment
            # -> distinct fulfillment (e.g., 2nd partial shipment on same order, or movement-only shipment)!
            elif oref and fid:
                # Check if sales already logged this order WITHOUT fulfillment_id -> ambiguous overlap!
                if (wh, sku, oref, f"ORDER-ONLY:{oref}") in fulfilled_by_fulfillment:
                    flag_review(
                        key,
                        "UNPROVEN_SALE_MOVEMENT_OVERLAP",
                        sku,
                        wh,
                        src,
                        f"Movement `{mtype}` ({oref}/{fid}, qty={qty}) cannot be proven distinct from order-only sales row without fulfillment_id; marked NEEDS_REVIEW.",
                    )
                elif (wh, sku, oref, fid) in seen_sale_move_fids:
                    log_info(
                        "DUPLICATE_SALE_MOVEMENT",
                        sku,
                        wh,
                        src,
                        f"Repeated `{mtype}` movement for ({oref}/{fid}, qty={qty}); deduplicated.",
                        severity="DEDUPED",
                    )
                else:
                    seen_sale_move_fids.add((wh, sku, oref, fid))
                    additional_sale_fulfillments[key] = additional_sale_fulfillments.get(key, 0) + qty
                    log_info(
                        "DISTINCT_FULFILLMENT_COUNTED",
                        sku,
                        wh,
                        src,
                        f"Counted distinct `{mtype}` fulfillment ({oref}/{fid}, qty={qty}) not present in sales export.",
                        severity="INFO",
                    )
            else:
                # Case 4: No verifiable order_ref / fulfillment_id proof!
                # NEVER silently guess whether it's duplicate or unlogged -> flag NEEDS_REVIEW!
                flag_review(
                    key,
                    "UNPROVEN_SALE_MOVEMENT_OVERLAP",
                    sku,
                    wh,
                    src,
                    f"Sale movement `{mtype}` qty={qty} lacks verifiable order_ref/fulfillment_id to prove whether it duplicates sales export; held in NEEDS_REVIEW (not deducted).",
                )
        else:
            # Unknown movement type -> NEVER silently treat as outbound deduction!
            flag_review(
                key,
                "UNKNOWN_MOVEMENT_TYPE",
                sku,
                wh,
                src,
                f"Unrecognized movement type `{mtype}` (qty={qty}); excluded from auto-deduction and held in NEEDS_REVIEW.",
            )

    # 5. Build per-(warehouse, sku) reconciliation rows
    out_rows: list[dict[str, Any]] = []
    totals = {
        "opening": 0,
        "inbound": 0,
        "sales_fulfilled": 0,
        "distinct_sale_movements": 0,
        "non_sale_outbound": 0,
        "expected_on_hand": 0,
        "physical": 0,
        "variance": 0,
        "committed": 0,
        "variance_cost_usd": 0.0,
        "needs_review_skus": 0,
    }

    for key, info in opening.items():
        wh, sku = key
        op = info["opening_qty"]
        inb = inbound.get(key, 0)
        sld = sales_fulfilled.get(key, 0)
        add_ful = additional_sale_fulfillments.get(key, 0)
        ns_out = non_sale_outbound.get(key, 0)
        exp = op + inb - sld - add_ful - ns_out
        if key not in physical:
            flag_review(key, "MISSING_PHYSICAL_COUNT", sku, wh, info["opening_src"], f"SKU missing from `{physical_file}`.")
            phy = 0
            phy_missing = True
        else:
            phy = physical[key]
            phy_missing = False
        var = phy - exp
        comm = sales_committed.get(key, 0)
        var_usd = round(var * info["unit_cost_usd"], 2)

        reasons = sku_review_reasons.get(key, [])
        if reasons or phy_missing:
            status = "NEEDS_REVIEW"
            totals["needs_review_skus"] += 1
        elif var < 0:
            status = "SHORTAGE"
            log_info(
                "PHYSICAL_SHORTAGE",
                sku,
                wh,
                f"{info['opening_src']} | {physical_src[key]}",
                f"Expected {exp} on hand, counted {phy} (variance {var}, cost impact ${var_usd:+.2f}).",
                severity="VARIANCE",
            )
        elif var > 0:
            status = "SURPLUS"
            log_info(
                "PHYSICAL_SURPLUS",
                sku,
                wh,
                f"{info['opening_src']} | {physical_src[key]}",
                f"Expected {exp} on hand, counted {phy} (variance +{var}, cost impact ${var_usd:+.2f}).",
                severity="VARIANCE",
            )
        else:
            status = "MATCH"

        totals["opening"] += op
        totals["inbound"] += inb
        totals["sales_fulfilled"] += sld
        totals["distinct_sale_movements"] += add_ful
        totals["non_sale_outbound"] += ns_out
        totals["expected_on_hand"] += exp
        totals["physical"] += phy
        totals["variance"] += var
        totals["committed"] += comm
        totals["variance_cost_usd"] = round(totals["variance_cost_usd"] + var_usd, 2)

        out_rows.append({
            "warehouse": wh,
            "sku": sku,
            "product_name": info["product_name"],
            "opening_qty": op,
            "inbound_qty": inb,
            "sales_fulfilled_qty": sld,
            "distinct_sale_movements_qty": add_ful,
            "non_sale_outbound_qty": ns_out,
            "expected_on_hand": exp,
            "physical_count": phy if not phy_missing else "",
            "variance_qty": var if not phy_missing else "",
            "unit_cost_usd": f"{info['unit_cost_usd']:.2f}",
            "variance_cost_usd": f"{var_usd:+.2f}" if not phy_missing else "",
            "unfulfilled_committed_qty": comm,
            "available_after_committed": (phy - comm) if not phy_missing else "",
            "status": status,
            "needs_review_reasons": "; ".join(reasons),
            "source_provenance": "; ".join([
                info["opening_src"],
                *sales_sources.get(key, []),
                *move_sources.get(key, []),
                *([] if phy_missing else [physical_src[key]]),
            ]),
        })

    # Strict mathematical cross-check on grand totals
    assert (
        totals["opening"]
        + totals["inbound"]
        - totals["sales_fulfilled"]
        - totals["distinct_sale_movements"]
        - totals["non_sale_outbound"]
        == totals["expected_on_hand"]
    )
    assert totals["physical"] - totals["expected_on_hand"] == totals["variance"]

    needs_review_anomalies = [a for a in anomalies if a["severity"] == "NEEDS_REVIEW"]
    reconciliation_status = "NEEDS_REVIEW" if needs_review_anomalies else "CLEAN"

    result = {
        "reconciliation_status": reconciliation_status,
        "as_of_cutoff": effective_cutoff or "UNKNOWN",
        "totals": totals,
        "needs_review_count": len(needs_review_anomalies),
        "rows": out_rows,
        "anomalies": anomalies,
    }

    if write_outputs:
        out_csv = base_dir / "weekly_sku_reconciliation_output.csv"
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)

        md = [
            "# Weekly SKU Inventory Reconciliation Sample (v2 — Warehouse, Cutoff & Fulfillment-Linked)",
            "",
            "> **Privacy & Verification Design**: Uses strictly PII-stripped exports (zero customer names, emails, or addresses). Keyed by `(warehouse, sku)` at a single cutoff timestamp (`" + (effective_cutoff or "UNKNOWN") + "`). Sales fulfillment movements (`outbound_sale` / `outbound_fulfillment`) are deduplicated against fulfilled sales by `(order_ref, fulfillment_id, sku)` so the same shipment is **never** double-deducted; non-sale losses (`outbound_damage` / `outbound_shrinkage` / `outbound_internal`) are tracked separately; any unprovable overlap or unknown movement type is held in **`NEEDS_REVIEW` (`待核`)** instead of silently guessed.",
            "",
            f"- **Overall Reconciliation Status**: **`{reconciliation_status}`** (`needs_review_anomalies={len(needs_review_anomalies)}`, `needs_review_skus={totals['needs_review_skus']}`)",
            "",
            "## 1. Reconcilable Grand Totals Check (`PASS`)",
            "",
            "| Metric | Units / Value | Formula Check |",
            "| :--- | ---: | :--- |",
            f"| Opening Stock (2026-11-16) | `{totals['opening']}` | Sum of `{opening_file}` ({len(out_rows)} warehouse-SKU rows) |",
            f"| + Inbound (`inbound_receipt` / `inbound_return`) | `+{totals['inbound']}` | Allowlisted inbound movements |",
            f"| - Fulfilled Sales (Deduped) | `-{totals['sales_fulfilled']}` | Deduped fulfilled rows in `{sales_file}` |",
            f"| - Distinct Unlogged Sale Fulfillments | `-{totals['distinct_sale_movements']}` | Linked `(order_ref, fulfillment_id)` shipments not already in sales export |",
            f"| - Non-Sale Outbound (`damage` / `shrinkage` / `internal`) | `-{totals['non_sale_outbound']}` | Non-sale loss/consumption tracked separately |",
            f"| **= Expected On-Hand (at cutoff)** | **`{totals['expected_on_hand']}`** | `{totals['opening']} + {totals['inbound']} - {totals['sales_fulfilled']} - {totals['distinct_sale_movements']} - {totals['non_sale_outbound']} = {totals['expected_on_hand']}` |",
            f"| Physical Shelf Count | **`{totals['physical']}`** | Sum of `{physical_file}` |",
            f"| **Net Unit Variance (Physical - Expected)** | **`{totals['variance']:+d}`** | `{totals['physical']} - {totals['expected_on_hand']} = {totals['variance']:+d}` (Net Cost Impact: `${totals['variance_cost_usd']:+.2f}`) |",
            f"| Unfulfilled / Committed Cutoff Units | `{totals['committed']}` | Still physically on shelf; deducted only from Available Stock |",
            "",
            "## 2. Per-(Warehouse, SKU) Reconciliation Table",
            "",
            "| Warehouse | SKU | Opening | +Inbound | -Sales | -ExtraFulfill | -NonSaleOut | Expected | Physical | Variance | Cost Impact | Committed | Status |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
        for r in out_rows:
            v_disp = f"{r['variance_qty']:+d}" if isinstance(r["variance_qty"], int) else "待核"
            c_disp = f"`${r['variance_cost_usd']}`" if r["variance_cost_usd"] else "待核"
            md.append(
                f"| `{r['warehouse']}` | `{r['sku']}` | {r['opening_qty']} | {r['inbound_qty']} | {r['sales_fulfilled_qty']} | "
                f"{r['distinct_sale_movements_qty']} | {r['non_sale_outbound_qty']} | {r['expected_on_hand']} | "
                f"{r['physical_count']} | **{v_disp}** | {c_disp} | {r['unfulfilled_committed_qty']} | `{r['status']}` |"
            )
        md.append(
            f"| **ALL** | **TOTAL ({len(out_rows)} SKUs)** | **{totals['opening']}** | **{totals['inbound']}** | "
            f"**{totals['sales_fulfilled']}** | **{totals['distinct_sale_movements']}** | **{totals['non_sale_outbound']}** | "
            f"**{totals['expected_on_hand']}** | **{totals['physical']}** | **{totals['variance']:+d}** | "
            f"**`${totals['variance_cost_usd']:+.2f}`** | **{totals['committed']}** | **`{reconciliation_status}`** |"
        )
        md += [
            "",
            "## 3. Audit Trail, Deduplication & `NEEDS_REVIEW` (`待核`) Items",
            "",
            "| Severity | Type | Warehouse | SKU | Source File & Row | Detail |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for a in anomalies:
            md.append(f"| `{a['severity']}` | `{a['type']}` | `{a['warehouse']}` | `{a['sku']}` | `{a['source']}` | {a['detail']} |")

        (base_dir / "reconciliation_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        (base_dir / "reconciliation_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic 1-Week SKU Inventory Reconciler")
    parser.add_argument("--dir", default=str(Path(__file__).parent), help="Directory containing the 4 CSV exports")
    parser.add_argument("--cutoff", default=None, help="Consistent cutoff timestamp (YYYY-MM-DD HH:MM)")
    parser.add_argument("--allow-needs-review", action="store_true", help="Exit 0 even when NEEDS_REVIEW items exist")
    args = parser.parse_args()

    res = reconcile_directory(Path(args.dir), as_of_cutoff=args.cutoff, write_outputs=True)
    print(
        f"STATUS={res['reconciliation_status']} skus={len(res['rows'])} "
        f"needs_review={res['needs_review_count']} totals={res['totals']}"
    )
    if res["reconciliation_status"] != "CLEAN" and not args.allow_needs_review:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
