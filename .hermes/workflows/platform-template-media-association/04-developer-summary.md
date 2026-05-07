# Developer Summary — platform-template-media-association

## Implementation

Added a SelfCheck media readiness gate for `platform-template-media-association` that reads the generated Platform Template Ops real asset manifest and resolves every `assetRef` against deterministic source roots.

The gate is intentionally readiness/reporting only:

- no placeholder images are generated;
- no Platform DB asset rows are written;
- no media import is attempted when sources are missing;
- the current workspace status is reported honestly as `MEDIA_SOURCE_MISSING`.

## Gate behavior

Command:

```bash
scripts/project_api_smoke.sh v-workspace platform-template-media-association
```

Dispatches to:

```bash
python3 scripts/platform_template_media_association_gate.py --project v-workspace --feature platform-template-media-association
```

Input manifest:

```text
/root/work/v/platform-backend/testdata/templateops/real-import/template_ops_real_asset_manifest.json
```

Output report:

```text
/root/work/agentic-selfcheck/reports/platform-template-media-association/platform-template-media-association-gate.json
```

Source root configuration:

- repeatable CLI: `--asset-source-root /path/to/root`
- env: `TEMPLATE_ASSET_SOURCE_ROOTS=/path/one:/path/two`
- deterministic defaults currently include:
  - `/root/work/v`
  - `/root/work/v/platform-backend`
  - `/root/work/agentic-selfcheck`
  - current working directory when distinct

Future strict/ready mode:

- CLI: `--require-ready`
- env: `TEMPLATE_MEDIA_REQUIRE_READY=true`
- exits nonzero unless every manifest item resolves to a real file.

## Current gate result

Canonical non-strict SelfCheck evidence exits `0` because it successfully proves the expected blocked-with-evidence condition.

```json
{
  "status": "MEDIA_SOURCE_MISSING",
  "assetManifestItemCount": 173,
  "resolvedAssetCount": 0,
  "missingAssetCount": 173,
  "manifestMissingAssetCount": 173,
  "importAttempted": false,
  "importBlockedReason": "source_files_missing"
}
```

The JSON report includes a full `missingAssets` list for all 173 entries. Each missing entry includes:

- `sourceRef`
- `assetRef`
- `storageFileName`
- `templateRef` when available
- all `candidatePaths` checked
- `reason: source_file_not_found`

Representative missing asset:

```json
{
  "sourceRef": "templates/changing-model/M1-T01/example-1",
  "assetRef": "infra/examples/Model/ModelSwap/欧美白人女模特.png",
  "storageFileName": "changing-model/m1-t01-example-1.png",
  "templateRef": "tpl_m1_t01",
  "candidatePaths": [
    "/root/work/v/infra/examples/Model/ModelSwap/欧美白人女模特.png",
    "/root/work/v/platform-backend/infra/examples/Model/ModelSwap/欧美白人女模特.png",
    "/root/work/agentic-selfcheck/infra/examples/Model/ModelSwap/欧美白人女模特.png"
  ],
  "reason": "source_file_not_found"
}
```

## Verification run

```bash
python3 -m py_compile scripts/platform_template_media_association_gate.py
python3 -m selfcheck validate --root .
scripts/project_api_smoke.sh v-workspace platform-template-media-association
python3 scripts/platform_template_media_association_gate.py --require-ready
```

Results:

- `py_compile`: PASS
- `selfcheck validate --root .`: PASS (`PASS: no issues`)
- project API smoke: PASS as blocked-with-evidence (`MEDIA_SOURCE_MISSING`, 173 missing)
- strict mode: expected failure with exit code `1` under current missing sources (`MEDIA_SOURCE_MISSING`, 173 missing)

## Blocker

Full media association/import remains blocked because the real source image tree referenced by `infra/examples/...` is absent from the current workspace. Once real files are restored under a configured source root, the same gate can report `MEDIA_READY`; a later slice should then run supported Platform import/binding verification without direct DB writes.
