# 07 QA Report — dev-seed-baseline

Role: QA
Timestamp: 2026-05-07T03:20:06Z
Verdict: PASS

## Scope

QA ran live/static/SelfCheck/browser evidence for the `dev-seed-baseline` workflow. No product code was modified. Sensitive values were not printed in this report; the semantic gate notes that password/token values are used only in memory and not emitted.

## Evidence Summary

| Area | Command / Evidence | Result |
| --- | --- | --- |
| Platform targeted tests | `cd /root/work/v/platform-backend && go test ./internal/modules/devseed ./internal/modules/access` | PASS |
| Ecommerce targeted tests — root repo | `cd /root/work/v/ecommerce-backend && go test ./internal/modules/templatecenter` | PASS |
| Ecommerce targeted tests — runtime worktree | `cd /root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend && go test ./internal/modules/templatecenter` | PASS |
| SelfCheck validate/audit | `cd /root/work/agentic-selfcheck && python3 -m selfcheck validate --root . && python3 -m selfcheck audit --root .` | PASS command exit 0; initial audit warned this QA report/final verification evidence were missing; post-write rerun only warns later `08-final-verification.md` is missing |
| Semantic gate | `cd /root/work/agentic-selfcheck && mkdir -p reports/dev-seed-baseline && scripts/project_api_smoke.sh v-workspace dev-seed-baseline \| tee reports/dev-seed-baseline/dev-seed-baseline-gate.json` | PASS |
| Browser smoke | `http://127.0.0.1:5181/` via browser snapshot/console/vision | PASS page + login surface loaded; no fatal JS errors |

## Detailed Results

### 1. Platform targeted tests

Command:

```bash
cd /root/work/v/platform-backend && go test ./internal/modules/devseed ./internal/modules/access
```

Observed result:

```text
ok  	platform-service/internal/modules/devseed	(cached)
ok  	platform-service/internal/modules/access	(cached)
```

Assessment: PASS. Dev seed and access/RBAC targeted packages pass.

### 2. Ecommerce targeted tests

Root repo command:

```bash
cd /root/work/v/ecommerce-backend && go test ./internal/modules/templatecenter
```

Observed result:

```text
ok  	ecommerce-service/internal/modules/templatecenter	(cached)
```

Runtime worktree command:

```bash
cd /root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend && go test ./internal/modules/templatecenter
```

Observed result:

```text
ok  	ecommerce-service/internal/modules/templatecenter	0.809s
```

Assessment: PASS. Template center targeted tests pass in both root repo and runtime worktree.

### 3. SelfCheck validate/audit

Command:

```bash
cd /root/work/agentic-selfcheck && python3 -m selfcheck validate --root . && python3 -m selfcheck audit --root .
```

Observed result:

```text
PASS: no issues
WARN: .hermes/workflows/dev-seed-baseline/07-qa-report.md: missing required evidence for feature dev-seed-baseline
WARN: .hermes/workflows/dev-seed-baseline/08-final-verification.md: missing required evidence for feature dev-seed-baseline
```

Assessment: PASS_WITH_NOTES for this command. Exit code was 0 and validate passed. The QA-report warning was expected because this file had not yet been written when the audit command ran; final verification is owned by a later workflow step.

### 4. Semantic gate

Command:

```bash
cd /root/work/agentic-selfcheck
mkdir -p reports/dev-seed-baseline
scripts/project_api_smoke.sh v-workspace dev-seed-baseline | tee reports/dev-seed-baseline/dev-seed-baseline-gate.json
```

Evidence path:

```text
/root/work/agentic-selfcheck/reports/dev-seed-baseline/dev-seed-baseline-gate.json
```

Observed top-level result:

```json
{
  "project": "v-workspace",
  "feature": "dev-seed-baseline",
  "status": "PASS",
  "scope": "platform-common-and-ecommerce-business-dev-seed-baseline"
}
```

Key semantic checks verified from the gate output:

- `platform_login`: HTTP 200, `ok: true`
- `token_obtained`: `true`
- `platform_admin_rows`: `ok: true`, value `1`
- `platform_permissions`: `ok: true`, value `15`
- `platform_role_grants`: `ok: true`
  - `owner`: required grants present; forbidden grants absent
  - `admin`: required grants present; forbidden grants absent
  - `developer`: required grants present; forbidden grants absent
  - `viewer`: required grants present; forbidden grants absent
- `ecommerce_local_template_catalogs`: `ok: true`, value `173`
- `ecommerce_template_catalog_api`: HTTP 200, `ok: true`, `item_count: 173`, first template id `tpl_p1_t01`
- `ecommerce_template_detail_api`: HTTP 200, `ok: true`
- `ecommerce_template_use_api`: HTTP 200, `ok: true`
- `ecommerce_template_favorite_api`: HTTP 201, `ok: true`
- `ecommerce_template_copy_api`: HTTP 201, `ok: true`

Assessment: PASS. The semantic gate validates login/token presence, RBAC required/forbidden grants, and Ecommerce catalog list/detail/use/favorite/copy behavior.

### 5. Browser smoke

Target:

```text
http://127.0.0.1:5181/
```

Observed:

- Page title: `Agent Ecommerce`
- Landing page loaded with main hero: `AI-Powered Cross-Border E-Commerce Visual Engine`
- Header links/buttons rendered, including `Log In` and `Free Trial`
- Clicking `Log In` opened the login page/surface
- Login surface contained:
  - `Welcome Back`
  - email input placeholder `Enter your email`
  - password input placeholder `Enter your password`
  - `Reset Password`
  - primary `Log In` button
  - Google/GitHub social buttons
- Browser console contained only Vite/React/i18next informational messages; no JavaScript errors were reported.

Screenshot evidence:

```text
/root/.hermes/cache/screenshots/browser_screenshot_db710c61c31b4944998191446fd7cbde.png
```

Assessment: PASS. Frontend page and login surface are accessible and no obvious fatal console errors were observed.

## Acceptance Mapping

| Acceptance item | QA finding |
| --- | --- |
| Platform dev admin exists and can login in local dev | PASS — semantic gate `platform_login` HTTP 200 and `token_obtained: true`; admin row count `1` |
| Platform RBAC seed is least-privilege, idempotent, and does not overgrant viewer/developer | PASS — targeted tests pass; semantic gate required/forbidden grants clean for owner/admin/developer/viewer |
| Dev seed has explicit local/dev guardrails | PASS by targeted devseed tests and prior approved spec/quality review context; not re-reviewed as code in QA |
| Ecommerce local templates are seeded even when platform projection is enabled | PASS — semantic gate local template catalog count `173` |
| Ecommerce template list -> detail -> favorite/copy/use works when platform catalog projection is empty | PASS — gate validates catalog list, detail, use, favorite, copy |
| SelfCheck gate asserts semantics, not only row counts or HTTP 200 | PASS — gate reports semantic RBAC required/forbidden grants and Ecommerce content/action checks |
| Workflow evidence includes QA report | PASS — this file created |

## Issues / Notes

- SelfCheck audit emitted expected warnings before this report existed: missing `07-qa-report.md` and missing later `08-final-verification.md`. The command still exited 0.
- Browser smoke did not submit credentials through the UI to avoid exposing or logging password/token values. API semantic gate covered login/token acquisition without printing sensitive values.
- No code fixes were made by QA.

## Final QA Verdict

PASS — live targeted tests, SelfCheck validate/audit, semantic API gate, and browser smoke all support accepting `dev-seed-baseline` for QA handoff. The only note is the expected SelfCheck audit warning for evidence files not yet present at the moment the audit was executed.
