# Discovery Inventory — platform-template-media-association

## Summary

The current workspace does **not** contain the Ecommerce example image files referenced by the template asset manifest.

## Evidence

Current generated Platform real asset manifest:

- `/root/work/v/platform-backend/testdata/templateops/real-import/template_ops_real_asset_manifest.json`
- Items: `173`
- `missingAssets`: `173`
- All `assetRef` values use the prefix `infra/examples/...`.

Original Ecommerce asset manifest:

- `/root/work/v/ecommerce-backend/internal/modules/templatecenter/example_asset_manifest.json`
- Items: `173`
- It contains `assetRef` and `storageFileName`, but no local `sourcePath` values.

Representative entries:

```text
sourceRef: templates/changing-model/M1-T01/example-1
assetRef: infra/examples/Model/ModelSwap/欧美白人女模特.png
sourcePath: <missing>
storageFileName: changing-model/m1-t01-example-1.png
```

## File search results

Searched `/root/work/v` for images:

- PNG: only 16 unrelated frontend/KYC/Menu images found.
- JPG: only 3 unrelated KYC fixture images found.
- WEBP: none.
- `/root/work/v/infra` does not exist.

Searched broader `/root/work` for representative Ecommerce assets and directories:

- `欧美白人女模特.png`: not found.
- `亚洲女模特*`: not found.
- `ModelSwap`: not found.
- `infra`: not found.

## Interpretation

This is not only a path-resolution bug. The referenced media source tree is absent from the current server workspace.

Therefore the slice cannot honestly claim full media association/import of 173 Ecommerce template example images unless the source image files are supplied or restored.

## What can still be done now

- Keep manifest refs stable and auditable.
- Improve gates so they distinguish:
  - `MEDIA_READY`: sourcePath exists and prepared asset import is expected.
  - `MEDIA_SOURCE_MISSING`: referenced files are absent and import must be blocked/partial.
- Add a SelfCheck gate/report that enumerates missing source refs and expected paths.
- Optionally add placeholder/non-production generated images only if the user explicitly accepts synthetic placeholders. Current requirement does **not** authorize fabricating image assets.
