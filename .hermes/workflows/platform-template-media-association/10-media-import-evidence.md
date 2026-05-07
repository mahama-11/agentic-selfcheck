# Media Import Evidence — platform-template-media-association

## Status

`MEDIA_READY_AND_IMPORTED`

This supersedes the earlier `PASS_AS_BLOCKED_WITH_EVIDENCE` state after the real media source files were found on `ssh prod` and copied into the local workspace.

## Source restoration

Remote source found:

```text
prod:/data/storage/examples/Model/ModelSwap/...
```

Local target restored:

```text
/root/work/v/infra/examples/...
```

Copy result:

```text
local png_count: 230
representative file: /root/work/v/infra/examples/Model/ModelSwap/欧美白人女模特.png
```

The Platform manifest expects asset refs under `infra/examples/...`, so the restored local layout allows `assetRef` to resolve under source root `/root/work/v`.

## Manifest regeneration

Command run from `/root/work/v/platform-backend`:

```bash
python3 scripts/export_real_template_ops_import.py
```

Observed:

```json
{
  "templateCount": 187,
  "assetManifestItemCount": 173,
  "missingAssetCount": 0,
  "sourcePathPresent": 173
}
```

First resolved source path:

```text
/root/work/v/infra/examples/Model/ModelSwap/欧美白人女模特.png
```

## Media readiness gate

Command run from `/root/work/agentic-selfcheck`:

```bash
python3 scripts/platform_template_media_association_gate.py --require-ready --report reports/platform-template-media-association/platform-template-media-association-gate.json
```

Observed:

```json
{
  "status": "MEDIA_READY",
  "assetManifestItemCount": 173,
  "resolvedAssetCount": 173,
  "missingAssetCount": 0,
  "manifestMissingAssetCount": 0
}
```

## Platform prepared asset import API

Platform backend was started locally on `http://127.0.0.1:8195` and `/healthz` returned HTTP 200.

API used:

```text
POST /api/v1/template-ops/import/assets/prepared
```

Authentication used local dev admin credentials from config, but no password/token is persisted in evidence.

First import observed:

```json
{
  "manifest_path": "testdata/templateops/real-import/template_ops_real_asset_manifest.json",
  "imported_count": 173,
  "skipped_count": 0,
  "failed_count": 0
}
```

Idempotency rerun observed:

```json
{
  "imported_count": 0,
  "skipped_count": 173,
  "failed_count": 0
}
```

Full API report:

```text
/root/work/agentic-selfcheck/reports/platform-template-media-association/platform-template-media-import-api.json
```

## Sample Template Ops asset binding

API checked:

```text
GET /api/v1/template-ops/catalog/ecommerce:tpl_m1_t01/assets
```

Observed:

```json
{
  "items": 1,
  "ready": 1,
  "source_ref": "templates/changing-model/M1-T01/example-1",
  "storage_key": "ecommerce/template-examples/m1-t01-example-1.png",
  "mime_type": "image/png",
  "status": "ready"
}
```

## SelfCheck

Final checks:

```bash
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
```

Observed:

```text
PASS: no issues
PASS: no issues
```

## Remaining notes

- The copied files are local development/media seed sources, not secrets.
- The final media state is no longer blocked by missing source files.
- A browser/frontend visual pass can be added next if we want Platform Console screenshots for template image preview rendering.
