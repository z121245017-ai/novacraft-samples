# Synthetic API & SOP Documentation QA Sample Report

> **Disclosure**: 100% synthetic documentation fixture created for demonstration (`NovaCraft Studio`, overseen by Fan Zhu). Zero proprietary or client files included.

## Scope & Checks Run
- **Target**: `api_orders_guide.md` + `openapi_orders.json` (synthetic v1.2 release candidate)
- **Automated Checks** (`audit_docs.py`, `5/5` unit tests passing):
  1. Internal heading anchors and cross-file Markdown link integrity
  2. Duplicated-word / prose hygiene scan
  3. Glossary & canonical header/parameter casing consistency
  4. Required OpenAPI parameter & endpoint coverage check

## Summary Verdict: `FAIL (2 errors, 2 warnings)`

| Line | Severity | Category | Finding | Suggested Fix |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `error` | `missing_required_param` | Required parameter `idempotency_key` for `POST /v1/orders` missing from docs | Document `idempotency_key` header in Request Parameters table |
| 14 | `error` | `broken_anchor` | Missing heading anchor `#error-codes` | Update link to `#http-status-and-errors` or add `## Error Codes` |
| 9 | `warning` | `duplicated_word` | Duplicated word `the the` | Replace `the the` with `the` |
| 11 | `warning` | `terminology_drift` | Use canonical term `X-Webhook-Signature` instead of `Webhook-Sig` | Standardize header name to `X-Webhook-Signature` |

## Reproducible Verification
```bash
python3 -m unittest test_audit_docs.py
```
