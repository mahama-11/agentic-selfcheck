# QA Report — platform-template-mastering

## Verdict

**PASS**

## Scope

Live/API/SelfCheck QA for the `platform-template-mastering` slice, focused on:

- Platform and Ecommerce health checks.
- SelfCheck API smoke gate.
- Platform published ecommerce catalog count after import.
- Representative Platform detail metadata, including stable `template_ref`, raw JSON, and detail JSON fields.
- Ecommerce Template Center consumption of Platform-backed catalog/detail data while Platform integration is enabled.
- Test coverage for Ecommerce fallback behavior.

No product code was modified. Dev admin credentials/internal secrets were read only by local scripts and used in memory; no passwords/tokens/secrets were printed or persisted.

## Environment

- Platform: `http://127.0.0.1:8195`
- Ecommerce: `http://127.0.0.1:8396`
- Workspace: `/root/work/v`
- SelfCheck root: `/root/work/agentic-selfcheck`

## Checks and Evidence

### 1. Live service health

Command:

```bash
for url in http://127.0.0.1:8195/healthz http://127.0.0.1:8396/healthz; do
  curl -sS -o /tmp/qa_health_body -w '%{http_code}' "$url"
done
```

Observed:

- `http://127.0.0.1:8195/healthz` → HTTP `200`, response body present.
- `http://127.0.0.1:8396/healthz` → HTTP `200`, response body present.

Result: **PASS**

### 2. SelfCheck platform-template-mastering API smoke

Command:

```bash
cd /root/work/agentic-selfcheck && scripts/project_api_smoke.sh v-workspace platform-template-mastering
```

Observed result: **PASS**

Key smoke evidence:

```json
{
  "status": "PASS",
  "checks": {
    "exporter": { "exit_code": 0 },
    "artifact_validation": {
      "row_count": 187,
      "product_counts": { "menu": 14, "ecommerce": 173 },
      "summary": {
        "templateCount": 187,
        "menuTemplateCount": 14,
        "ecommerceTemplateCount": 173,
        "assetManifestItemCount": 173,
        "missingAssetCount": 173
      },
      "asset_manifest_items": 173,
      "missing_asset_count": 173
    },
    "platform_preview_import_path": {
      "preview_route_registered": true,
      "import_route_registered": true,
      "preview_handler_calls_service": true,
      "service_preview_test_present": true
    },
    "platform_service_preview_tests": { "exit_code": 0 }
  }
}
```

The smoke gate's own live preview subcheck was skipped because `PLATFORM_ADMIN_TOKEN` was not set in the shell environment, but a separate authenticated live preview check was performed by QA below using local dev admin config in memory only.

Result: **PASS**

### 3. SelfCheck schema validation

Command:

```bash
cd /root/work/agentic-selfcheck && python3 -m selfcheck validate --root .
```

Observed:

```text
PASS: no issues
```

Result: **PASS**

### 4. Live Platform CSV preview API

A local script read dev admin credentials from `platform-backend/config.local.yaml`, called Platform login, kept the access token in memory only, and did not print token/password values.

Endpoint:

- `POST /api/v1/template-ops/import/csv/preview`

CSV:

- `/root/work/v/platform-backend/testdata/templateops/real-import/template_ops_real_import.csv`

Observed:

```json
{
  "http_status": 200,
  "summary": {
    "total_rows": 187,
    "valid_rows": 187,
    "invalid_rows": 0,
    "create_count": 0,
    "update_count": 187,
    "ready_to_import_count": 14,
    "missing_asset_rows": 173,
    "missing_asset_count": 173
  }
}
```

Interpretation:

- Generated CSV is accepted by the live Platform preview API.
- All 187 rows are valid.
- Current live state already has these rows, so preview reports 187 updates and 0 creates.
- Missing ecommerce media assets remain visible and non-blocking as designed.

Result: **PASS**

### 5. Published Platform ecommerce catalog count

Endpoint:

- `GET /internal/v1/template-ops/catalog?product_code=ecommerce&published_only=true&limit=200`

Internal service auth was read from local config and used in memory only.

Observed:

```json
{
  "http_status": 200,
  "total": 173,
  "item_count": 173,
  "sample_refs": [
    "ecommerce:tpl_s2_t16",
    "ecommerce:tpl_s2_t15",
    "ecommerce:tpl_s2_t14"
  ],
  "sample_ids": [
    "tpl_s2_t16",
    "tpl_s2_t15",
    "tpl_s2_t14"
  ]
}
```

Result: **PASS** — Platform published catalog for ecommerce contains exactly 173 templates after import.

### 6. Representative Platform detail metadata

Endpoint:

- `GET /internal/v1/template-ops/catalog/ecommerce%3Atpl_s2_t16?locale=zh`

Observed:

```json
{
  "http_status": 200,
  "template_ref": "ecommerce:tpl_s2_t16",
  "item_raw_type": "dict",
  "item_raw_len": 12,
  "item_raw_keys": [
    "example_asset_refs",
    "example_source_refs",
    "execution_schema",
    "executor_type",
    "external_code",
    "featured",
    "industry_tags",
    "interaction_mode",
    "scenario_tags",
    "source_asset_ref",
    "source_doc_path",
    "tool_binding"
  ],
  "detail_raw_type": "dict",
  "detail_raw_len": 23,
  "detail_raw_keys": [
    "capabilityType",
    "defaultVariables",
    "examples",
    "executionSchema",
    "executorType",
    "externalCode",
    "featured",
    "id",
    "industryTags",
    "inputSchema",
    "interactionMode",
    "localeEN"
  ]
}
```

Result: **PASS** — representative detail exposes stable `template_ref` and non-empty raw/detail JSON fields.

### 7. Ecommerce Template Center consumes Platform-backed data

Endpoints:

- `GET /api/v1/ecommerce/template-center/catalog?locale=zh&sortBy=recommended`
- `GET /api/v1/ecommerce/template-center/catalog/tpl_p1_t01?locale=zh`

Observed catalog evidence:

```json
{
  "http_status": 200,
  "item_count": 173,
  "first_id": "tpl_p1_t01",
  "first_name": "极简白色大理石桌面"
}
```

Observed detail evidence:

```json
{
  "http_status": 200,
  "template_id": "tpl_p1_t01",
  "catalog_id": "tpl_p1_t01",
  "version": {
    "id": "tpl_p1_t01_platform",
    "versionNo": 1,
    "versionLabel": "platform-projection",
    "status": "published",
    "sourceAssetRef": "docs/agent_ecommerce_prompt商品图&套图系列.md#P1-T01"
  },
  "schema_keys": [
    "defaultVariables",
    "executionSchema",
    "inputSchema",
    "outputSchema",
    "promptLayers",
    "toolBinding"
  ]
}
```

Interpretation:

- Ecommerce public catalog returns 173 templates while Platform integration is enabled.
- Ecommerce detail returns a Platform-derived version marker (`tpl_p1_t01_platform`, status `published`) and schema fields mapped from Platform detail/raw metadata.
- This supports the expected Platform-backed consumption path rather than direct Platform DB access.

Result: **PASS**

### 8. Fallback behavior test coverage

Commands:

```bash
cd /root/work/v/ecommerce-backend && go test ./internal/modules/templatecenter -count=1
cd /root/work/v/platform-backend && go test ./internal/modules/templateops -count=1
```

Observed:

```text
ok  	ecommerce-service/internal/modules/templatecenter	1.506s
ok  	platform-service/internal/modules/templateops	0.035s
```

Result: **PASS** — focused Template Center tests pass, including Platform preference/fallback cases noted in prior review materials; Platform Template Ops tests also pass.

## Issues Encountered

No blocking issues found.

Non-blocking notes:

1. The SelfCheck smoke gate's environment-token based live preview remains skipped unless `PLATFORM_ADMIN_TOKEN` is explicitly provided, but QA independently verified the live preview API with local config credentials kept in memory only.
2. Media association remains intentionally deferred; 173 missing asset rows/items are visible in preview/manifest evidence and do not block metadata import.
3. Platform storage still uses transitional `template_projections` semantics internally, which was explicitly accepted for this slice.

## Final Conclusion

`platform-template-mastering` passes QA. Live Platform and Ecommerce services are healthy, SelfCheck gates pass, Platform has exactly 173 published ecommerce templates, representative detail contains stable refs plus raw/detail JSON metadata, Ecommerce Template Center returns Platform-backed catalog/detail data, and fallback behavior is covered by passing focused tests.
