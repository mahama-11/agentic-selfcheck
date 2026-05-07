# Spec Review Report — platform-template-mastering

## Verdict

**APPROVE**

## Review scope

Reviewed the platform-template-mastering implementation against the stated requirement, architecture review, discovery inventory, developer summary, and live API evidence. I inspected the requested implementation surfaces without editing product code:

- `/root/work/v/platform-backend/scripts/export_real_template_ops_import.py`
- `/root/work/v/platform-backend/testdata/templateops/real-import/`
- `/root/work/v/platform-backend/internal/modules/templateops/service_test.go`
- `/root/work/v/ecommerce-backend/internal/modules/templatecenter/service.go`
- `/root/work/v/ecommerce-backend/internal/modules/templatecenter/handler_test.go`
- `/root/work/agentic-selfcheck/features/platform-template-mastering.yaml`
- `/root/work/agentic-selfcheck/scripts/platform_template_mastering_gate.py`
- `/root/work/agentic-selfcheck/verifiers/platform-template-mastering-gate.yaml`

## Acceptance assessment

### 1. Move from legacy business -> Platform sync toward Platform import/mastering

**Pass.** The implemented slice establishes a Platform-owned import/mastering path using Template Ops CSV preview/import APIs. The live evidence shows the generated CSV was previewed and imported through Platform API, with `publish: true`, instead of bypassing Platform or relying only on Ecommerce-origin projection sync.

The implementation still uses the transitional `template_projections` model/table as planned by architecture, but records are imported with explicit `managed_source: seed_import`, stable product/template identifiers, and publish state controlled in Platform.

### 2. Exporter repair supports current and old paths

**Pass.** `export_real_template_ops_import.py` now uses a compatibility resolver that tries current workspace paths first:

- `menu-backend/...`
- `ecommerce-backend/...`

and legacy paths second:

- `v-menu-backend/...`
- `v-ecommerce-backend/...`

The repair preserves `--workspace-root` semantics and reports attempted paths if sources are missing.

### 3. 187 rows generated and imported via Platform API

**Pass.** Generated artifact summary reports:

- `templateCount`: 187
- `ecommerceTemplateCount`: 173
- `menuTemplateCount`: 14
- `assetManifestItemCount`: 173
- `missingAssetCount`: 173

I independently checked the generated CSV: 187 rows, 173 ecommerce rows, 14 menu rows, and no duplicate `(product_code, template_id)` pairs.

Live API evidence reports:

- Preview: HTTP 200, `total_rows: 187`, `valid_rows: 187`, `invalid_rows: 0`
- Import: HTTP 200, `imported_count: 187`, `published_count: 187`
- Published ecommerce catalog visibility: `total: 173`

### 4. Ecommerce consumes Platform-published data preferentially while retaining fallback

**Pass.** Ecommerce Template Center now queries Platform via API/client contract with `PublishedOnly: true` for ecommerce template catalog data. It does not directly read the Platform DB.

Local seed fallback is retained when Platform is unavailable or yields no usable published catalog/detail data, with warning logs for unavailable Platform paths. Tests cover Platform-backed preference over local seed and fallback behavior for empty/not-found/unavailable Platform responses.

One implementation detail to note: fallback for an empty Platform catalog is performed inside `listPlatformCatalog`, so the top-level `ListCatalog` sees a successful local result. This is acceptable for the transition behavior, but a follow-up could make the empty-catalog fallback more explicitly observable if operations needs stronger telemetry.

### 5. Media gaps explicitly deferred but visible

**Pass.** The generated asset manifest includes prepared asset items and `missingAssets`; the summary reports `missingAssetCount: 173`. This matches the architecture decision to defer full media/storage association while keeping asset gaps auditable.

### 6. Stable IDs/refs preserved

**Pass.** Platform refs are derived from product code plus template id (`ecommerce:<template_id>` / `menu:<template_id>`). Ecommerce detail lookup uses the stable Platform template ref form (`ecommerce:` + local template id), while the ecommerce API-facing template ID remains the stable template id expected by current runtime/frontend flows.

CSV generation preserves stable source identifiers, including product code, template id, slug, source refs in JSON payloads, and manifest metadata such as `templateID`, `externalCode`, `sourceRef`, and `assetRef`.

## Verification performed

Commands run during review:

```bash
cd /root/work/agentic-selfcheck && scripts/project_api_smoke.sh v-workspace platform-template-mastering
cd /root/work/v/platform-backend && go test ./internal/modules/templateops -count=1
cd /root/work/v/ecommerce-backend && go test ./internal/modules/templatecenter -count=1
```

Results:

- SelfCheck platform-template-mastering gate: **PASS**
- Platform Template Ops tests: **PASS**
- Ecommerce Template Center tests: **PASS**

The SelfCheck gate re-ran the exporter, validated CSV columns/counts/JSON columns, validated artifact counts, confirmed preview/import route wiring, and ran focused Template Ops preview/loading tests. Live preview in the static gate was skipped due to missing `PLATFORM_ADMIN_TOKEN`, but the separate live evidence file documents successful authenticated preview/import/publish.

## Issues / risks

No blocking issues found.

Non-blocking notes:

1. Generated Platform real-import files are under `platform-backend/testdata/templateops/real-import/`, which appears to be ignored/untracked in the Platform repo. This is acceptable for the current gate because the exporter and SelfCheck gate regenerate and validate them, but final packaging should ensure the intended artifact persistence policy is explicit.
2. The transitional `template_projections` naming remains architecturally awkward, but this was explicitly accepted for the slice and is properly treated as a future schema/domain refactor.
3. Full media association remains deferred by design; the current implementation makes the gap visible rather than hiding it.

## Conclusion

The implementation satisfies the platform-template-mastering acceptance focus: it repairs the real import exporter, generates/imports/publishes the 187-row Platform catalog through Platform APIs, makes Ecommerce prefer published Platform data while retaining fallback, preserves stable identifiers/refs, and keeps media gaps visible for a later slice.
