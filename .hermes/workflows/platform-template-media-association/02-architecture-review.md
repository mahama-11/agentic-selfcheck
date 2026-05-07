# Architecture Review — platform-template-media-association

## Verdict

**BLOCKED_WITH_EVIDENCE for full media import.**

The implementation must **not** attempt or claim full Ecommerce template media association/import in the current workspace because the local source image tree is absent. The correct architecture for this slice is an honest gate/report that preserves the existing metadata/mastering success while making the media dependency explicit and automatically recoverable once the image files are restored or supplied.

This is not a product-code approval to fabricate placeholder images or silently skip media. The current acceptable outcome is the requirement's second acceptance path: **Asset source BLOCKED_WITH_EVIDENCE**.

## Evidence basis

Reviewed inputs:

- `01-requirement.md`
- `03-discovery-inventory.md`
- Prior context: `../platform-template-mastering/09-final-verification.md`

Relevant established state:

- Platform template metadata mastering already passed.
- Platform imported/published `187` templates through API.
- Ecommerce published catalog count is `173`.
- Prepared asset manifest item count is `173`.
- Current missing asset count is `173`.
- Original Ecommerce asset manifest contains `assetRef` and `storageFileName`, but no source-local `sourcePath`.
- Current workspace does not contain `/root/work/v/infra/examples/...`.
- Broader `/root/work` search did not find representative source assets/directories such as:
  - `欧美白人女模特.png`
  - `亚洲女模特*`
  - `ModelSwap`
  - `infra`

Therefore the issue is not merely a wrong path prefix. The source media files themselves are unavailable in the local workspace.

## Architecture decision

### 1. Do not perform full media import now

Full media import requires source bytes for each prepared asset. Because all `173` asset sources are missing, a successful Platform asset import cannot be proven and must not be represented as complete.

The implementation should terminate the media-import path before upload/import when required source files cannot be resolved. The output should be a deterministic blocked report, not a false PASS.

Expected current status:

```text
MEDIA_SOURCE_MISSING / BLOCKED_WITH_EVIDENCE
assetManifestItemCount: 173
missingAssetCount: 173
importAttempted: false, or importedAssetCount: 0 with explicit source-missing reason
```

### 2. Implement valuable minimal work now: readiness gate/report

Developer work should focus on a reproducible SelfCheck gate/report that evaluates the generated real asset manifest and source-root configuration.

The gate should:

- Read the current generated Platform real asset manifest.
- Preserve and report stable identifiers:
  - `sourceRef`
  - `assetRef`
  - `template_ref` / template reference when present
  - `storageFileName`
- Resolve candidate local source paths using configured source roots.
- Enumerate every missing file with:
  - expected relative `assetRef`
  - source ref
  - storage file name
  - candidate absolute path(s) checked
  - reason: `source_file_not_found`
- Distinguish statuses clearly:
  - `MEDIA_READY`: all required source files resolve and import verification can run.
  - `MEDIA_SOURCE_MISSING`: one or more required source files are absent.
  - `MEDIA_IMPORT_FAILED`: source files existed but Platform import/binding verification failed.
- Fail/block media-association acceptance when any required source file is missing.
- Avoid marking the overall media slice PASS unless either:
  - all files resolve and import/binding verification passes, or
  - the slice is explicitly closed as `BLOCKED_WITH_EVIDENCE` under the requirement's acceptance path 2.

The report should be machine-readable where practical, with a concise human summary. Recommended generated evidence fields:

```json
{
  "status": "MEDIA_SOURCE_MISSING",
  "assetManifestItemCount": 173,
  "resolvedAssetCount": 0,
  "missingAssetCount": 173,
  "sourceRootsChecked": ["..."],
  "missingAssets": [
    {
      "sourceRef": "templates/changing-model/M1-T01/example-1",
      "assetRef": "infra/examples/Model/ModelSwap/欧美白人女模特.png",
      "storageFileName": "changing-model/m1-t01-example-1.png",
      "candidatePaths": ["<root>/infra/examples/Model/ModelSwap/欧美白人女模特.png"],
      "reason": "source_file_not_found"
    }
  ]
}
```

For human readability, the report may include all missing entries in a JSON artifact and a sampled list in Markdown, but acceptance evidence must make it possible to audit all `173` missing assets.

### 3. Configurable source roots for future assets

Do not hardcode personal, machine-specific, or historical absolute paths such as `/root/work/v/infra/examples` as the only source. The resolver should support configurable roots and deterministic defaults.

Recommended source-root order:

1. Explicit CLI argument, for example:
   - `--asset-source-root /path/to/workspace-or-media-root`
   - repeatable if multiple roots are needed.
2. Environment variable override, for example:
   - `TEMPLATE_ASSET_SOURCE_ROOTS=/path/one:/path/two`
3. Repository/workspace-relative defaults, if present:
   - current repository root
   - workspace root, e.g. `/root/work/v` when running in this workspace
   - any documented testdata/media root if later added to the repo

Resolution rule:

```text
candidatePath = sourceRoot + "/" + assetRef
```

Because current `assetRef` values already include `infra/examples/...`, the source root should normally be the workspace/repository root that contains `infra/`, not the `infra/examples` directory itself. The gate may optionally accept roots pointing directly at an examples tree, but this must be explicit and documented to avoid ambiguity.

If multiple roots contain the same `assetRef`, the resolver should either choose the first configured root deterministically and report it, or fail with an ambiguity warning if byte-for-byte identity cannot be established. For this slice, deterministic first-root behavior is sufficient if clearly reported.

### 4. Prepared asset import architecture once files exist

Once sources are restored, the flow should become:

```text
existing Ecommerce asset manifest
  -> generated Platform prepared asset manifest with resolved sourcePath
  -> Platform prepared asset import API/service path
  -> Template Ops asset records and bindings
  -> Template Ops preview/detail exposes associated media
  -> SelfCheck verifies counts and no hidden missing assets
```

Import must use the Platform-supported API/service path. It must not write asset records or template bindings directly into the database.

Required verification after files exist:

- Manifest readiness:
  - `assetManifestItemCount == 173`
  - `resolvedAssetCount == 173`
  - `missingAssetCount == 0`
  - all resolved paths exist and are regular files
  - file extensions and MIME/content sniffing are acceptable for import
- Import result:
  - import endpoint/service returns success
  - `importedAssetCount == 173` or exactly equals the number of available assets if the run is intentionally partial
  - no failed rows hidden as warnings
  - stable `assetRef` and `storageFileName` are preserved
- Binding result:
  - each expected `sourceRef`/template example has a Platform asset association
  - Template Ops template preview/detail responses expose the associated asset metadata/records
  - Ecommerce Platform-backed catalog/detail can consume/display the published associated media where the contract exposes it
- Idempotency:
  - rerunning import does not create duplicate logical assets or duplicate template bindings
  - unchanged files produce unchanged associations
- Evidence:
  - SelfCheck report captures counts, endpoint/service path used, and sampled/summarized binding checks
  - no credentials, tokens, or secret values are persisted in artifacts

### 5. Acceptance model

Current acceptance for this workspace:

**BLOCKED_WITH_EVIDENCE is acceptable and expected** if the gate proves:

- local image files are absent;
- all missing assets are enumerated with stable refs and candidate paths;
- no media import/binding PASS is claimed;
- the report is reproducible and will change to `MEDIA_READY` when source files are restored under configured roots.

Future **Asset association PASS** requires evidence that:

- all expected source paths resolve, or the exact intended subset is declared;
- Platform prepared asset import succeeds through supported Platform path;
- Template Ops asset bindings are present and visible in preview/detail;
- Ecommerce-facing Platform template metadata exposes associated example/cover assets as expected;
- SelfCheck validates counts with `missingAssetCount: 0` for full import.

## Developer handoff

Implement only the minimal media readiness/reporting work unless the real source files are supplied during development.

Developer tasks:

1. Add or extend a SelfCheck/media readiness command.
2. Load the generated Platform real asset manifest.
3. Add source-root configuration via CLI and/or environment variable.
4. Resolve `assetRef` values against roots without hardcoding personal absolute paths.
5. Emit deterministic machine-readable evidence and concise Markdown/log summary.
6. Return/record `MEDIA_SOURCE_MISSING` when files are absent.
7. Ensure media import is skipped or blocked when source readiness fails.
8. If files are later present, run Platform prepared asset import and binding verification through supported API/service paths.

Do not:

- generate synthetic placeholder images;
- copy arbitrary production images into the repo;
- write asset rows directly into Platform DB tables;
- hide missing rows as warnings while reporting PASS;
- couple the resolver to a single developer's local path.

## Review / QA handoff

Spec review should verify:

- the gate status semantics are explicit and match the requirement;
- source-root configuration is portable;
- all missing assets are auditable;
- no false PASS path exists when source files are missing.

Quality/security review should verify:

- no secret/token persistence in reports;
- no destructive media/database operations;
- no unsafe path traversal from manifest values;
- output paths and candidate paths are deterministic and safe to disclose for local test evidence.

QA should run two scenarios where possible:

1. **Absent-source scenario** in the current workspace:
   - expect `MEDIA_SOURCE_MISSING` / `BLOCKED_WITH_EVIDENCE`;
   - expect `assetManifestItemCount: 173`;
   - expect `missingAssetCount: 173`;
   - expect all missing refs/candidate paths in report;
   - expect no media association PASS.
2. **Restored-source scenario** when real files are supplied:
   - configure source root containing `infra/examples/...`;
   - expect `MEDIA_READY` before import;
   - run Platform prepared asset import;
   - verify import count, bindings, preview/detail exposure, and idempotency.

## Final architecture conclusion

The correct architecture under the present workspace state is to **gate and report**, not import. The media slice should close this phase as **BLOCKED_WITH_EVIDENCE** unless the missing image files are supplied. The developer work remains valuable because it prevents false positives, makes the exact missing dependency auditable, and creates a portable path to automatic PASS once the real `infra/examples/...` source tree is restored.
