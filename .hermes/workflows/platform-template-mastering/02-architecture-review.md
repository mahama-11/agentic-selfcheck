# Architecture Review — platform-template-mastering

## Decision

Target architecture is **Platform master data -> published template catalog -> Ecommerce consumption**.

Platform should own template metadata, version/publish state, operations governance, and import gates. Agent Ecommerce should consume published Platform templates for catalog/runtime behavior and keep only product-owned workflow usage state. Ecommerce local seed/fixtures remain a transition fallback until the Platform import and consumption path is proven.

For the first implementation slice, keep the existing Platform `template_projections` table/model as the physical storage behind Template Ops, but treat records written by the real import as **Platform master records**. The naming is historically projection-oriented and not ideal, but the model already has the fields needed for the minimal metadata master slice: stable `template_ref`, `product_code`, `template_id`, publish status, scope, managed source, tags/platforms/detail/raw JSON, and asset refs. A larger schema rename/refactor should be a later compatibility-managed migration, not a prerequisite for this slice.

## Direct import readiness

Direct import is **not currently possible** in this workspace.

Evidence:

- No existing `.csv` template import artifact was found under `/root/work/v`.
- Structured JSON sources do exist:
  - Ecommerce: `/root/work/v/ecommerce-backend/internal/modules/templatecenter/generated_seed_definitions.json` with 173 templates.
  - Ecommerce asset manifest: `/root/work/v/ecommerce-backend/internal/modules/templatecenter/example_asset_manifest.json` with 173 items.
  - Menu seed: `/root/work/v/menu-backend/internal/modules/templatecenter/template_library.seed.json` with 14 templates.
- Platform has import/export endpoints:
  - `POST /api/v1/template-ops/import/csv/preview`
  - `POST /api/v1/template-ops/import/csv`
  - `POST /api/v1/template-ops/import/assets/prepared`
  - `GET /api/v1/template-ops/export/csv-real-sample`
- Platform exporter exists at `/root/work/v/platform-backend/scripts/export_real_template_ops_import.py`, but it assumes old source directories:
  - `v-menu-backend/...`
  - `v-ecommerce-backend/...`
- Current workspace directories are:
  - `menu-backend/...`
  - `ecommerce-backend/...`
- The observed exporter failure is `FileNotFoundError: /root/work/v/v-menu-backend/internal/modules/templatecenter/template_library.seed.json`.

Required first repair: make `export_real_template_ops_import.py` resolve current workspace names while preserving compatibility with the old names or explicit `--workspace-root` usage.

## Minimal implementation slice boundaries

### 1. Exporter path compatibility

Scope:

- Repair only the Platform exporter script path resolution.
- It should locate source files in the current workspace layout:
  - `/root/work/v/menu-backend/internal/modules/templatecenter/template_library.seed.json`
  - `/root/work/v/ecommerce-backend/internal/modules/templatecenter/generated_seed_definitions.json`
  - `/root/work/v/ecommerce-backend/internal/modules/templatecenter/example_asset_manifest.json`
- Prefer a small compatibility resolver that tries both new and old names rather than hard-coding only the new layout.
- Keep product semantics in source payloads/JSON; do not move product workflow behavior into Platform.

Out of scope:

- Changing generated ecommerce seed definitions.
- Reworking Ecommerce parser semantics.
- Changing Platform DB schema.

### 2. Generated Platform real-import artifacts

Scope:

- Generate Platform-ready artifacts from current structured JSON:
  - `template_ops_real_import.csv`
  - `template_ops_real_asset_manifest.json`
  - `template_ops_real_import_summary.json`
- Recommended output for repeatable dev/QA evidence:
  - either Platform testdata path already expected by handlers: `/root/work/v/platform-backend/testdata/templateops/real-import/`
  - or SelfCheck report path for non-product artifacts: `/root/work/agentic-selfcheck/reports/platform-template-mastering/`
- The CSV should contain 187 metadata rows if both Menu and Ecommerce sources are included: 173 ecommerce + 14 menu.
- The summary should capture counts and missing asset count.

Gate:

- Export command exits 0.
- Summary count matches source inventory.
- CSV columns match Platform import contract.

### 3. Platform import and publish gate

Scope:

- Use Platform Template Ops import APIs as the authoritative write path.
- Run CSV preview first; import only if preview has no blocking errors.
- Import metadata before prepared assets.
- Publish imported records through Template Ops publish behavior, or verify import path already sets an acceptable published state for real catalog visibility.
- Keep `managed_source` explicit, e.g. `seed_import`/real import source, so future migrations can distinguish imported master records from legacy external sync rows.

Gate:

- `POST /api/v1/template-ops/import/csv/preview` accepts generated CSV.
- `POST /api/v1/template-ops/import/csv` imports/updates expected records idempotently.
- Imported records are visible through Template Ops catalog/list/detail endpoints.
- Publish status is set/verified before Ecommerce consumes them as runtime catalog data.

### 4. Ecommerce consumption behavior

Scope:

- Ecommerce should read published Platform templates for catalog/runtime template selection.
- Local ecommerce seed remains fallback/bootstrap only during transition.
- The consumption path should be API/contract based, not direct Platform DB reads.
- Runtime/template lookup should preserve stable template identifiers:
  - Platform `template_ref` should be stable and derived from `product_code` + `template_id`.
  - Ecommerce business records should reference Platform template refs/codes rather than duplicating Platform master metadata.
- If Platform is unavailable or no published Platform templates are available, Ecommerce may fall back to local seed temporarily, but this should be logged/observable and removable after acceptance.

Gate:

- With imported/published Platform records, Ecommerce catalog returns Platform-backed templates for the same stable IDs/slugs expected by current frontend/runtime flows.
- Fallback can be disabled in a controlled test or config path after Platform data is present.
- No new product-specific workflow logic is introduced into Platform.

## Media/image association policy

Defer deeper media/image association handling to a follow-up slice.

Must still be represented now:

- `cover_asset_id` and `cover_asset_url` CSV columns, even if empty.
- Example/source refs inside `raw_json` and `detail_json`.
- Prepared asset manifest entries with:
  - `productCode`
  - `category`
  - `sourceType`
  - `sourceRef`
  - `assetRef`
  - `storageFileName`
  - `title`
  - `description`
  - `tags`
  - `metadata.templateID` / external code / example id where available
  - `sourcePath` only when the local file can be resolved
- `missingAssets` in the generated manifest/summary so the asset gap is visible and auditable.

Deferred:

- Resolving all local image paths.
- Upload/storage migration of every template example image.
- Cover image selection policy.
- CDN/public preview URL policy.
- Rich media lifecycle, replacement, deduplication, or moderation workflows.

This allows metadata mastering to proceed without blocking on asset completeness, while preserving enough references for a later prepared-asset import slice.

## Verification gates

### Architect -> Developer handoff gate

Developer should receive this plan plus the discovery inventory and implement only the minimal repair/import/consumption slice. Product code changes should be limited to the assigned developer slice; this architecture review does not modify product code.

### Developer gates

1. Exporter compatibility:
   - Run the exporter from `/root/work/v/platform-backend`.
   - Verify it works with current `menu-backend` and `ecommerce-backend` names.
   - Verify generated summary count is 187 total templates if both products are included.
2. Platform import contract:
   - Run relevant Template Ops unit tests.
   - Preview generated CSV through Platform API or service-level test path.
   - Import idempotently and verify no duplicate/unstable refs.
3. Publish/catalog visibility:
   - Verify imported records can be listed and fetched by Template Ops catalog endpoints.
   - Verify publish status is correct for records intended for Ecommerce consumption.
4. Ecommerce consumption:
   - Add or update a small integration/service test showing Platform-published template data is preferred over local seed.
   - Preserve seed fallback until the Platform-backed path is proven.

### QA gates

- Smoke Platform Template Ops preview/import/list/detail/publish flow with generated artifacts.
- Smoke Ecommerce template center catalog/detail with Platform-backed data available.
- Smoke fallback behavior by making Platform catalog unavailable/empty, if fallback remains enabled.
- Check counts, stable IDs/slugs, and representative fields: name, summary, tags, platform tags, modality, capability type, raw/detail JSON.
- Confirm media gaps do not fail metadata import and are visible in manifest summary.

### Reviewer gate

- Confirm Platform remains the master for template metadata and publish state.
- Confirm Ecommerce does not directly read Platform DB and does not continue treating local seed as authoritative when Platform data exists.
- Confirm `template_projections` is documented/understood as transitional storage, not the long-term domain name.
- Confirm no product workflow semantics were moved into Platform beyond shared template catalog metadata/operations.

## Risks and follow-up decisions

### `template_projections` naming/model risk

Risk: the current name suggests data projected from product backends, which conflicts with the target Platform-master direction.

Decision for this slice: keep it as current storage because it already supports import, publish state, catalog operations, and stable refs. Treat records imported via Template Ops as Platform-owned master records. Use fields such as `managed_source`, `publish_status`, `scope`, and `template_ref` to distinguish source and lifecycle.

Follow-up: design a larger schema/domain refactor only after the import and Ecommerce consumption path is proven. Possible future work:

- Rename model/table to a Platform-master name such as `template_catalog_records` or `template_master_records`.
- Introduce explicit version table if template versioning needs first-class history rather than JSON payload overwrite.
- Add migration/backfill compatibility for existing `template_projections` rows.
- Preserve API compatibility or provide versioned Template Ops APIs during migration.

### Data provenance risk

The first slice imports structured JSON derived from Ecommerce/Menu seeds. That is acceptable as bootstrap material, but after import, Platform should be the source of truth for maintenance and publishing. Future edits should happen through Platform Ops/import APIs, not by re-seeding Ecommerce as authority.

### Asset completeness risk

Prepared asset manifest may contain missing local paths. This should not block metadata import, but must remain visible in `missingAssets`/summary and be handled by a later media-association slice.

### Runtime contract risk

Ecommerce runtime may currently assume local seed/detail shape. Consumption should map Platform `raw_json`/`detail_json` to the existing Ecommerce contract carefully, with tests around representative templates, rather than changing frontend/runtime shapes opportunistically.

## Recommended next implementation order

1. Repair Platform exporter path compatibility.
2. Generate real import CSV, asset manifest, and summary from current JSON sources.
3. Preview and import metadata through Platform Template Ops APIs/service tests.
4. Verify/publish Platform catalog visibility.
5. Add Ecommerce consumption path that prefers published Platform templates and retains local seed fallback.
6. Add smoke/integration coverage and hand off to QA.
7. Defer full media association and `template_projections` schema rename to later slices.
