# The invoice total matched. Two line items were wrong.

A receipt for two items shows $24.80 for labels and $42.00 for tape. An extractor attaches each amount to the other item. The resulting invoice still adds up to $66.80. If an importer accepts the document on that basis, a purchasing team can charge the wrong item and still balance its books.

I used a small purchase order as an independent reference. Each item appears once, quantity is one, and the invoice has no taxes, freight, or discounts. The first check compares the extracted line sum with the extracted invoice total. The second compares each item with its approved purchase-order line. The fixtures below start at the output of an extractor. You can run them with Python 3 and its standard library.

```python
from decimal import Decimal

order = {"labels": Decimal("24.80"), "tape": Decimal("42.00")}
cases = [
    ("clean",        "INV-17", "24.80",  "42.00", "66.80"),
    ("decimal slip", "INV-17", "248.00", "42.00", "66.80"),
    ("swapped rows", "INV-17", "42.00",  "24.80", "66.80"),
    ("invoice ID",   "INV-71", "24.80",  "42.00", "66.80"),
]

for name, invoice_id, labels, tape, printed_total in cases:
    extracted = {"labels": Decimal(labels), "tape": Decimal(tape)}
    total_ok = sum(extracted.values()) == Decimal(printed_total)
    changed = [item for item in order if extracted[item] != order[item]]
    result = ", ".join(changed) or "none"
    print(f"{name} | {invoice_id} | total={total_ok} | flagged items={result}")
```

```text
clean | INV-17 | total=True | flagged items=none
decimal slip | INV-17 | total=False | flagged items=labels
swapped rows | INV-17 | total=True | flagged items=labels, tape
invoice ID | INV-71 | total=True | flagged items=none
```

The swapped rows send a reviewer to two specific source lines. The decimal slip sends them to one. The last case illustrates the limit of both checks. Verifying the invoice ID requires its own reference, such as a supplier's dispatch record. On a real order with repeated SKUs, match on purchase-order line IDs. Reconcile taxes and credits separately according to the invoice terms.

*Independent, AI-assisted editorial sample. The records are synthetic. No customer documents or OCR service were used.*
