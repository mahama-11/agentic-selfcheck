# QA Report — platform-template-media-association

## Verdict

**PASS_AS_BLOCKED_WITH_EVIDENCE**

This is **not** a full media-association PASS. QA confirms the readiness gate correctly reports the current workspace as blocked because all referenced Ecommerce template media source files are absent, while preserving auditable evidence for all expected assets.

## Scope

Reviewed prior workflow inputs:

- `01-requirement.md`
- `02-architecture-review.md`
- `03-discovery-inventory.md`
- `04-developer-summary.md`
- `05-spec-review-report.md`
- `06-quality-review-report.md`

Validated the implemented SelfCheck/media readiness gate and generated report:

- Gate command: `scripts/project_api_smoke.sh v-workspace platform-template-media-association`
- Report JSON: `reports/platform-template-media-association/platform-template-media-association-gate.json`

## Checks run

From `/root/work/agentic-selfcheck`:

```bash
python3 -m selfcheck validate --root .
scripts/project_api_smoke.sh v-workspace platform-template-media-association
python3 scripts/platform_template_media_association_gate.py --require-ready --report /tmp/platform-template-media-association-strict-qa.json
```

Additional QA audit parsed the report JSON and checked representative candidate paths with `os.path.exists`. I also ran a temporary source-root resolver smoke using one fake file under `/tmp`; the temporary directory was removed after the test and no product artifacts/placeholders were created.

## Results

### SelfCheck validate

**PASS**

```text
PASS: no issues
```

### Project API smoke / canonical readiness gate

**PASS as blocked-with-evidence** with current source files missing.

Observed report fields:

```json
{
  "status": "MEDIA_SOURCE_MISSING",
  "assetManifestItemCount": 173,
  "resolvedAssetCount": 0,
  "missingAssetCount": 173,
  "manifestMissingAssetCount": 173,
  "importAttempted": false,
  "importBlockedReason": "source_files_missing",
  "requireReady": false
}
```

The gate exits `0` in non-strict mode because it successfully produces the expected blocked-with-evidence state; it does not claim full media association.

### Report JSON audit

Confirmed from `reports/platform-template-media-association/platform-template-media-association-gate.json`:

- `missingAssets` length: `173`
- `resolvedAssets` length: `0`
- Every sampled missing entry has stable refs and `reason: source_file_not_found`.
- Sample candidate paths point to absent files.

Representative samples checked:

```text
sourceRef: templates/changing-model/M1-T01/example-1
assetRef: infra/examples/Model/ModelSwap/欧美白人女模特.png
candidate paths:
  /root/work/v/infra/examples/Model/ModelSwap/欧美白人女模特.png                  exists=false
  /root/work/v/platform-backend/infra/examples/Model/ModelSwap/欧美白人女模特.png exists=false
  /root/work/agentic-selfcheck/infra/examples/Model/ModelSwap/欧美白人女模特.png  exists=false
reason: source_file_not_found

sourceRef: templates/changing-model/M1-T02/example-1
assetRef: infra/examples/Model/ModelSwap/亚洲女模特（东亚）.png
candidate paths all absent
reason: source_file_not_found

sourceRef: templates/changing-model/M1-T03/example-1
assetRef: infra/examples/Model/ModelSwap/非裔欧美女模特.png
candidate paths all absent
reason: source_file_not_found
```

### Strict mode

**Expected failure confirmed.**

Command:

```bash
python3 scripts/platform_template_media_association_gate.py --require-ready --report /tmp/platform-template-media-association-strict-qa.json
```

Observed:

```text
status: MEDIA_SOURCE_MISSING
resolvedAssetCount: 0
missingAssetCount: 173
STRICT_EXIT_CODE=1
```

This verifies strict/ready mode blocks when sources are absent.

### Temporary source-root resolver smoke

To prove future resolver behavior without altering product artifacts, QA created one fake file only under a temporary `/tmp/media-assoc-qa-*` source root matching the first `assetRef`, ran the gate with `--asset-source-root`, and let the temp directory auto-remove.

Observed:

```text
TEMP_ROOT_EXIT_CODE 0
TEMP_ROOT_STATUS MEDIA_SOURCE_MISSING
TEMP_ROOT_RESOLVED 1
TEMP_ROOT_MISSING 172
TEMP_ROOT_FIRST_RESOLVED_PATH /tmp/media-assoc-qa-*/infra/examples/Model/ModelSwap/欧美白人女模特.png
TEMP_ROOT_EXISTS_DURING_TEST True
TEMP_ROOT_REMOVED True
```

This confirms source-root override can resolve restored files and reduce missing count, without fabricating production placeholders.

## Acceptance assessment

Requirement acceptance path 1, **Asset association PASS**, is **not satisfied** because source media files are absent and no Platform media import/binding verification can honestly run.

Requirement acceptance path 2, **Asset source BLOCKED_WITH_EVIDENCE**, is satisfied:

- Local image files are demonstrably absent for sampled candidate paths.
- The gate reports `MEDIA_SOURCE_MISSING` with exact counts: `173` manifest items, `0` resolved, `173` missing.
- Full `missingAssets` list contains all `173` entries with stable refs/candidate paths/reasons.
- `importAttempted` is `false`; missing sources block import instead of silently skipping or claiming success.
- Strict mode exits nonzero in the missing-source state.
- Source-root override behavior is ready for future restored media.

## Issues

No QA-blocking issues found for the current blocked-with-evidence readiness gate.

## Final decision

**PASS_AS_BLOCKED_WITH_EVIDENCE** — the implementation correctly gates media association readiness, avoids false media association PASS, and provides complete evidence for the current blocker: the 173 referenced source media files are absent from the workspace.
