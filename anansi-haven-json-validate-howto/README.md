# Validate an invoice payload with Anansi Haven

An automated billing handoff should catch two common mistakes before it reaches the next system. Amounts can arrive as strings or zero, and a payload can include a field the receiver does not understand. The Haven `json_validate` tool checks those conditions against a JSON Schema and gives the calling agent a field path for each failure.

The example uses a fictional invoice. Its schema requires a string invoice ID and an integer amount in cents. The integer must be at least one. Setting `additionalProperties` to `false` makes the handoff strict, so an extra field can be caught before the receiving system has to deal with it. There is no API key for this free tool. Use synthetic values if your real payload contains customer details.

## Check the expected payload

```sh
curl -sS https://anansi-haven.anansidata.workers.dev/v1/free/json_validate \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "schema": {
      "type":"object",
      "properties":{
        "invoice_id":{"type":"string"},
        "amount_cents":{"type":"integer","minimum":1}
      },
      "required":["invoice_id","amount_cents"],
      "additionalProperties":false
    },
    "data":{"invoice_id":"INV-103","amount_cents":400}
  }'
```

The response includes `"valid": true` and `"errors": []`. In this example, 400 cents is four dollars. Keeping the amount in cents also makes the integer requirement easy to satisfy. Preserve the validated amount when copying it into later steps, because a conversion after validation can introduce another error.

## Test a failure before using the check

```sh
curl -sS https://anansi-haven.anansidata.workers.dev/v1/free/json_validate \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "schema": {
      "type":"object",
      "properties":{
        "invoice_id":{"type":"string"},
        "amount_cents":{"type":"integer","minimum":1}
      },
      "required":["invoice_id","amount_cents"],
      "additionalProperties":false
    },
    "data":{"invoice_id":"INV-103","amount_cents":0,"currency":"USD"}
  }'
```

The service returns HTTP 200 for this request and reports the validation failure in the body. The observed fields were:

```json
{
  "valid": false,
  "errors": [
    {"path":"/amount_cents","message":"< minimum 1"},
    {"path":"/currency","message":"additional property not allowed"}
  ]
}
```

Have the calling agent check `valid` after a successful HTTP response. If validation fails, carry the error paths into its report. In the second example, the caller checks the amount at its source and checks the receiver's schema before deciding where to carry the currency. It should ask for a corrected amount when none is available. A failed validation is never a reason to manufacture one.

We tested both calls against the live service on November 25, 2026, using synthetic invoice payloads with no real customer data. NovaCraft Studio drafted this guide and ran the live command checks with AI assistance under the operator's authorized publishing workflow. The examples show only the validation fields. The API can also return service metadata and an optional passport token. Leave those fields out of build logs and any shared report.

Schema validation gives you a check for expected type, shape and range. Check the original invoice separately if you also need to verify that its amount is accurate.

[Haven tool reference](https://anansi-haven.anansidata.workers.dev/llms.txt)

