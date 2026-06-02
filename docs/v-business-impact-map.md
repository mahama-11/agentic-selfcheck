# V Business Impact Map

This map is the operator-facing bridge between changed files, product journeys, and SelfCheck gates. It prevents generic code governance from being mistaken for business QA.

Status: initial control-plane map. Ecommerce critical paths are blocking; other domains start as advisory until a feature gate exists and has verified evidence.

## Principles

- A changed file is not the risk; the affected user journey is the risk.
- Generic build/typecheck/governance is not enough for product-critical journeys.
- Blocking gates must be runnable, evidence-backed, and reviewed for false PASS/false FAIL before entering selector rules.
- Draft gates stay quarantined until script permissions, roots, evidence paths, and product worktrees are aligned.
- Release-wide journeys run for release/deploy surfaces even if the diff path looks unrelated.

## Domain map

### Change Impact Selector pipeline

The live selector is `config/v-business-gate-selector.yaml`, executed by `scripts/v_business_gate_selector.py`, `scripts/v_continuous_governance_trigger.py`, and `scripts/v_working_tree_governance_watchdog.py`. It now covers PR/push/manual trigger and dirty-tree watchdog paths. High-risk unmatched product source changes fail closed instead of becoming generic-governance PASS.


### Ecommerce Prep / Sandbox / Visual Workflow

Changed paths:
- `ecommerce-frontend/src/pages/production/**`
- `ecommerce-frontend/src/services/production.ts`
- `ecommerce-frontend/src/store/productionStore.ts`
- `ecommerce-frontend/src/i18n/**`
- `ecommerce-backend/internal/modules/visualworkflow/**`

Critical journeys:
- Fixed Prep choices -> image plan composition.
- SKU/reference/deconstruction/intent inputs reach prompt composition.
- Runtime callback updates stage/result state without leaking backend/provider wording.
- Source refs and prompt snapshots remain observable and regression-testable.

Required gates:
- `ecommerce-v2-prep-sandbox-lowlevel` — blocking.
- `ecommerce-critical-journey-release-gate` — blocking for release-critical surfaces.

Evidence standard:
- Static/API/browser/evidence groups all run.
- Reports include request/root evidence from the intended V adapter.
- No user-facing copy exposes backend/runtime/provider/contract terms.

### Ecommerce SKU / Listing / Export

Changed paths:
- `ecommerce-backend/internal/modules/productcore/**`
- `ecommerce-backend/internal/modules/templatecenter/**`
- `ecommerce-frontend/src/pages/product/**`
- `ecommerce-frontend/src/services/product.ts`
- `ecommerce-frontend/src/services/templateCenter.ts`
- account downloads/templates pages.

Critical journeys:
- SKU/product lifecycle.
- ListingVersion create/update/batch.
- Template Center catalog/instance metadata used by the UI.
- Export/download/history paths.

Current gate state:
- Covered indirectly by `ecommerce-critical-journey-release-gate` for release-critical changes.
- CrossPlanet/List Strategy draft gates are quarantined and not mainline blocking.

Gap:
- Need a mature listing/export journey gate before selector can block on all listing/template changes.

### Platform Runtime / Provider / Storage

Changed paths:
- `platform-backend/internal/modules/runtime/**`
- `platform-backend/internal/modules/storage/**`
- provider adapter files and tests.

Critical journeys:
- Provider selection and fallback.
- Runtime task submission and callback.
- Output manifest/source asset preservation.
- Safe error mapping and secret redaction.

Required gates:
- `ecommerce-critical-journey-release-gate` — blocking when Ecommerce consumes the runtime path.

Gap:
- Provider-live checks should remain nightly/manual until credentials and external availability are stable.
- Anti-fake provider contract gate should be added before widening blocking coverage.

### Commercial / Billing / Wallet / Metering

Changed paths:
- `platform-backend/internal/modules/wallet/**`
- `platform-backend/internal/modules/metering/**`
- `platform-backend/internal/modules/billing/**`
- `ecommerce-backend/internal/modules/commercial/**`

Critical journeys:
- Reservation/charge/ledger consistency.
- Runtime cost attribution.
- Commercial entitlement checks.

Required gates:
- `ecommerce-critical-journey-release-gate` — blocking for release-critical changes.

Gap:
- Need dedicated commercial ledger journey before this area can be called fully covered.

### Auth / Account / Permissions

Changed paths:
- `platform-backend/internal/modules/auth/**`
- `platform-frontend/**` auth shell/package/runtime entry changes.
- Ecommerce frontend auth guards.

Critical journeys:
- Protected Ecommerce pages do not silently redirect incorrectly.
- Auth token and user context reach downstream services.

Current gate state:
- `ecommerce-critical-journey-release-gate` covers parts of authenticated journey.

Current gate state:
- Platform frontend service/build/runtime changes select Platform baseline/ops gates.
- Unmapped high-risk Platform source changes fail closed until a precise gate exists.

### Menu

Changed paths:
- `menu-backend/**`
- `menu-frontend/**`

Critical journeys:
- Menu admin/product operations.
- Public menu/order surfaces if applicable.

Current gate state:
- No mature Menu business journey gate is available yet.
- High-risk Menu backend/frontend source changes now fail closed as `UNMAPPED_HIGH_RISK_CHANGE` instead of passing generic code governance.

Gap:
- Add Menu project adapter and at least one critical journey before treating Menu changes as controlled.
- `.env` deletion must be reviewed as environment hygiene, not auto-fixed by product gates.

### KYC

Changed paths:
- `kyc-backend/**`
- `kyc-frontend/**`

Critical journeys:
- KYC submission/review/status.
- Sensitive document handling and permission checks.

Current gate state:
- No mature KYC business journey gate is available yet.
- High-risk KYC backend/frontend source changes now fail closed as `UNMAPPED_HIGH_RISK_CHANGE` instead of passing generic code governance.

Gap:
- Fix repository ownership/safe-directory discovery and add KYC project adapter / critical journey gate before treating KYC changes as controlled.

### Deploy / Release / Runbooks

Changed paths:
- `**/PROD_DEPLOY_RUNBOOK.md`
- `tools/prod/**`
- `Dockerfile*`
- release event YAMLs.

Critical journeys:
- Release commands preserve config/secrets.
- Deployed app still passes Ecommerce critical journey.

Required gates:
- `ecommerce-critical-journey-release-gate` — blocking for Ecommerce/platform release surfaces.

Current gate state:
- Deploy scripts, Docker/gateway config, PROD_DEPLOY_RUNBOOK, and release events select release/stability gates.

Gap:
- Production execution still requires real topology/public-content/runtime evidence; selector wiring alone is not prod closure.

## Selector maturity

Blocking now:
- Ecommerce Prep/Sandbox low-level.
- Ecommerce release-wide critical journey for core backend/runtime/deploy surfaces.
- Platform baseline/stability/financial/runtime gates for mapped shared Platform surfaces.
- Fail-closed unmapped high-risk Menu/KYC/Product source changes.

Advisory / not yet fully covered:
- Menu and KYC have fail-closed selectors but still need mature business journey gates.
- Full Pact/Broker-style can-i-deploy is not yet implemented; current contract coverage is OpenAPI/DTO/consumer-sweep oriented.
- Platform frontend tooling.
- CrossPlanet/List Strategy drafts.
- Provider-live external checks.

## Next selector changes

1. Add deploy/Dockerfile tooling patterns to release-critical surfaces.
2. Add platform frontend package/runtime changes as advisory or release-critical depending on package scope.
3. Add menu and KYC only after project adapters and smoke gates exist.
4. Promote listing/export gate only after draft gate issues are resolved and product worktrees are reviewed.
