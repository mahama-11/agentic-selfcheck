# Live API Import Evidence — platform-template-mastering

## Runtime

- Platform backend: `http://127.0.0.1:8195`
- Ecommerce backend: `http://127.0.0.1:8396`
- Both health checks returned HTTP 200 before the live import attempt.

## Method

A local script read the dev admin credentials from `platform-backend/config.local.yaml` and used them only in memory to call Platform auth. No password or token was printed or persisted.

The generated CSV was read from:

`/root/work/v/platform-backend/testdata/templateops/real-import/template_ops_real_import.csv`

## Results

### Preview

Endpoint:

`POST /api/v1/template-ops/import/csv/preview`

Result:

```json
{
  "http_status": 200,
  "summary": {
    "total_rows": 187,
    "valid_rows": 187,
    "invalid_rows": 0,
    "create_count": 41,
    "update_count": 146,
    "ready_to_import_count": 14,
    "missing_asset_rows": 173,
    "missing_asset_count": 173
  }
}
```

Interpretation:

- CSV contract and JSON columns are accepted by the live Platform API.
- All 187 rows are valid.
- 173 ecommerce rows have missing media assets, which is expected and intentionally visible for the deferred media association slice.

### Import + Publish

Endpoint:

`POST /api/v1/template-ops/import/csv`

Payload used `publish: true`.

Result:

```json
{
  "http_status": 200,
  "imported_count": 187,
  "published_count": 187,
  "row_results": 187
}
```

Interpretation:

- Platform Template Ops import path is not bypassed.
- All generated metadata rows are imported/updated idempotently through Platform API.
- All imported rows are published.

### Published ecommerce catalog visibility

Endpoint:

`GET /api/v1/template-ops/catalog?product_code=ecommerce&published_only=true&limit=1`

Result:

```json
{
  "total": 173,
  "first_template_ref": "ecommerce:tpl_s2_t16"
}
```

Interpretation:

- Published Platform-owned ecommerce template catalog is visible after import.
- Ecommerce template metadata now has a Platform import/mastering path independent from legacy upstream sync.

## Status

PASS.
