# Discovery Inventory — platform-template-mastering

## Current finding

There is no existing `.csv` template import file under `/root/work/v`.

There are existing structured JSON sources and import/export code:

- Ecommerce structured template JSON:
  - `/root/work/v/ecommerce-backend/internal/modules/templatecenter/generated_seed_definitions.json`
  - Count: 173 templates.
- Ecommerce example asset manifest:
  - `/root/work/v/ecommerce-backend/internal/modules/templatecenter/example_asset_manifest.json`
  - Count: 173 items.
- Menu seed JSON:
  - `/root/work/v/menu-backend/internal/modules/templatecenter/template_library.seed.json`
  - Count: 14 templates.
- Ecommerce source parser:
  - `/root/work/v/ecommerce-backend/scripts/generate_template_center_seed.py`
  - Parses markdown docs + local example images into structured JSON and asset manifest.
- Platform CSV exporter:
  - `/root/work/v/platform-backend/scripts/export_real_template_ops_import.py`
  - Intended output files:
    - `template_ops_real_import.csv`
    - `template_ops_real_asset_manifest.json`
    - `template_ops_real_import_summary.json`
- Platform Template Ops import APIs:
  - `POST /api/v1/template-ops/import/csv/preview`
  - `POST /api/v1/template-ops/import/csv`
  - `POST /api/v1/template-ops/import/assets/prepared`
  - `POST /api/v1/template-ops/import/assets/upload`
  - `GET /api/v1/template-ops/export/csv`
  - `GET /api/v1/template-ops/export/csv-template`
  - `GET /api/v1/template-ops/export/csv-real-sample`

## Direct import readiness

Not directly ready yet.

Reason: `export_real_template_ops_import.py` currently assumes old workspace subdirectory names:

- `v-menu-backend/...`
- `v-ecommerce-backend/...`

Current workspace uses:

- `menu-backend/...`
- `ecommerce-backend/...`

Attempted command:

```bash
cd /root/work/v/platform-backend
python3 scripts/export_real_template_ops_import.py --output-dir /root/work/agentic-selfcheck/reports/platform-template-mastering/discovery
```

Observed failure:

```text
FileNotFoundError: /root/work/v/v-menu-backend/internal/modules/templatecenter/template_library.seed.json
```

## Interpretation

The user's remembered pipeline exists in pieces:

```text
local docs/assets
  -> ecommerce generate_template_center_seed.py
  -> generated_seed_definitions.json + example_asset_manifest.json
  -> platform export_real_template_ops_import.py
  -> template_ops_real_import.csv + real asset manifest
  -> platform Template Ops CSV/assets import APIs
```

But the CSV artifact itself is not currently present, and the exporter needs path compatibility repair before direct import.

## Media/image association note

The asset side is already modeled through source refs and prepared asset manifests, but actual local image path resolution depends on the examples directory being present at the expected workspace-relative paths. Media association can be deferred as a follow-up slice after the metadata import path is fixed and gated.
