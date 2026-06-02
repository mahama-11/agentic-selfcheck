# Ecommerce Large Source Split Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Split Agent Ecommerce oversized source files into cohesive same-package / same-module files so repository governance can move from legacy allowlist to strict `<=800`-line enforcement without behavior, API, route, or i18n contract changes.

**Architecture:** This is a locality refactor, not a business rewrite. Backend files stay in their existing Go packages and move methods/helpers into cohesive files (`runtime`, `planner`, `generation`, `writeback`, `validation`, etc.). Frontend files keep public route/service exports stable while extracting domain helpers, hooks, view components, and i18n namespaces. Every batch removes or tightens the matching entry in `scripts/v_ecommerce_large_source_guard.py`.

**Tech Stack:** Go 1.25, Gin/Gorm service packages, React 19, TypeScript 6, Vite 8, Tailwind CSS v4, Agentic SelfCheck governance scripts.

---

## Non-negotiable constraints

- Do not change product behavior, public API JSON shape, routes, storage keys, auth assumptions, billing/runtime contracts, or frontend user-facing terminology.
- Do not cross package boundaries for Go splits; all extracted Go files use the same package as the original file.
- Do not convert i18n copy into runtime-generated strings; preserve keys and copy semantics.
- Each file-split batch must update the large-source guard allowlist when the target file drops below threshold.
- Completion means `scripts/v_ecommerce_large_source_guard.py --strict --format json` passes.

## Current oversized Ecommerce inventory

| Priority | File | Lines | Owner | Target split shape | Verification |
| --- | --- | ---: | --- | --- | --- |
| P0 | `ecommerce-backend/internal/modules/visualworkflow/service.go` | 5870 | backend | session/source, deconstruction runtime, intent/prompt planners, generation runtime/fanout, writeback, validation/sanitize helpers | `gofmt`, `go test ./internal/modules/visualworkflow -count=1` |
| P0 | `ecommerce-backend/internal/modules/visualworkflow/service_test.go` | 3333 | backend | fixtures/router, source tests, runtime callback tests, planner tests, generation/fanout tests, writeback tests | same package test |
| P1 | `ecommerce-backend/internal/modules/productcore/service.go` | 2351 | backend | product CRUD/assets, listing versions, export/download packages, validation/helpers | `gofmt`, `go test ./internal/modules/productcore -count=1` |
| P1 | `ecommerce-backend/internal/modules/imageruntime/service.go` | 1352 | backend | source/job lifecycle, prompt compilation, billing/charge, product asset archival, mapping helpers | `gofmt`, `go test ./internal/modules/imageruntime -count=1` |
| P1 | `ecommerce-frontend/src/services/production.ts` | 2031 | frontend | production API client, source parsing service, planner service, generation fanout service, local storage helpers, copy/mapper helpers | `npm run typecheck`, `npm run build` |
| P2 | `ecommerce-frontend/src/pages/production/SandboxPage.tsx` | 1510 | frontend | constants/options, prompt-plan helpers, wireframe preview, section components, page container | typecheck/build + lowlevel gate |
| P2 | `ecommerce-frontend/src/pages/production/PrepHubPage.tsx` | 1374 | frontend | upload zone, decision cards, attribute rows, localization helpers, page container | typecheck/build + lowlevel gate |
| P2 | `ecommerce-frontend/src/pages/GenericPage.tsx` | 1395 | frontend | page maps/data, decorative components, portal detail sections, route container | typecheck/build |
| P2 | `ecommerce-frontend/src/i18n/en.ts` | 1597 | frontend | split resource namespaces under `src/i18n/en/*.ts`, re-export aggregate object | typecheck/build |
| P2 | `ecommerce-frontend/src/i18n/zh.ts` | 1663 | frontend | split resource namespaces under `src/i18n/zh/*.ts`, re-export aggregate object | typecheck/build |
| P3 | `ecommerce-backend/internal/repository/template_center_repository.go` | 1123 | backend | split catalog/favorite/copy/use query helpers and mapping | package/full backend tests |
| P3 | `ecommerce-backend/internal/platform/client.go` | 887 | backend | split auth/session, runtime, billing/commercial client methods | package/full backend tests |
| P3 | `ecommerce-backend/internal/modules/productcore/handler_test.go` | 1244 | backend | split handler tests by product/assets/listing/export/download | productcore tests |
| P3 | `ecommerce-backend/internal/modules/imageruntime/handler_test.go` | 808 | backend | split handler tests by source/job/content callbacks | imageruntime tests |
| P3 | `ecommerce-backend/internal/modules/visualworkflow/types.go` | 814 | backend | split request/response DTOs by workflow domain | visualworkflow tests |
| P3 | `ecommerce-frontend/src/pages/AgentTemplateMarketPage.tsx` | 1165 | frontend | split filters/cards/detail drawer/page container | typecheck/build |
| P3 | `ecommerce-frontend/src/pages/ToolPage.tsx` | 1117 | frontend | split upload/runtime/history panels | typecheck/build |
| P3 | `ecommerce-frontend/src/pages/production/WorkshopPage.tsx` | 1135 | frontend | split controls/result grid/state helpers | typecheck/build + lowlevel gate |
| P3 | `ecommerce-frontend/src/pages/AssetCommercePage.tsx` | 981 | frontend | split asset list/order/download sections | typecheck/build |
| P3 | `ecommerce-frontend/src/pages/product/ProductDetailPage.tsx` | 977 | frontend | split product detail sections/hooks | typecheck/build + listing/export gate |
| P3 | `ecommerce-frontend/src/pages/product/components/ProductDetailTabs.tsx` | 866 | frontend | split tab panels by product domain | typecheck/build + listing/export gate |
| P3 | `ecommerce-frontend/src/pages/DesignWorkbenchPage.tsx` | 854 | frontend | split workbench panels/helpers | typecheck/build |
| P3 | `ecommerce-frontend/src/services/product.ts` | 837 | frontend | split product API service domains | typecheck/build + listing/export gate |

---

## Phase 0: Governance guard landed before broad refactor

**Objective:** Stop new or growing Ecommerce large source files while the existing legacy list is being burned down.

**Files:**
- Create: `/root/work/agentic-selfcheck/scripts/v_ecommerce_large_source_guard.py`
- Create: `/root/work/agentic-selfcheck/scripts/v_ecommerce_large_source_guard_smoke.py`
- Modify: `/root/work/agentic-selfcheck/config/v-business-gate-selector.yaml`

**Acceptance criteria:**
- New non-allowlisted Ecommerce source files over 800 lines fail.
- Existing allowlisted files pass only as `PASS_WITH_NOTES` and cannot grow beyond their baseline line count.
- `--strict` mode fails until all large files are split; this becomes the final burn-down proof.
- Business gate selector attaches `ecommerce-large-source-locality-guard` to Ecommerce changes.

**Verifier commands:**

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_ecommerce_large_source_guard_smoke.py
python3 scripts/v_ecommerce_large_source_guard.py --format json
python3 scripts/v_ecommerce_large_source_guard.py --strict --format json  # expected FAIL until split backlog is cleared
python3 scripts/v_business_gate_selector.py --changed-file ecommerce-backend/internal/modules/visualworkflow/service.go --run --format json
```

---

## Phase 1: Visual Workflow backend service split

### Task 1.1: Split session/source/core lifecycle

**Objective:** Keep `service.go` as constructor + thin top-level orchestration, move session/source CRUD into cohesive files.

**Files:**
- Modify: `ecommerce-backend/internal/modules/visualworkflow/service.go`
- Create: `ecommerce-backend/internal/modules/visualworkflow/session.go`
- Create: `ecommerce-backend/internal/modules/visualworkflow/sources.go`

**Move groups:**
- `CreateSession`, `ListSessions`, `GetSession`, `UpdateSession`, `CancelSession`
- `CreateSourceReference`, `ListSourceReferences`, `ArchiveSourceReference`, `UpdateSourceReference`
- related source metadata helpers only if needed for locality

**Verifier:**

```bash
cd /root/work/v/ecommerce-backend
gofmt -w internal/modules/visualworkflow/*.go
go test ./internal/modules/visualworkflow -count=1
```

### Task 1.2: Split runtime capability, billing, and manifest helpers

**Files:**
- Create: `ecommerce-backend/internal/modules/visualworkflow/runtime_capability.go`
- Create: `ecommerce-backend/internal/modules/visualworkflow/runtime_billing.go`
- Create: `ecommerce-backend/internal/modules/visualworkflow/runtime_manifest.go`

**Move groups:**
- capability readiness helpers
- runtime charge session / idempotency helpers
- `platformRuntimeInputManifest*`, source asset manifest builders, safe manifest sanitizers

**Verifier:** same package test.

### Task 1.3: Split deconstruction and planner jobs

**Files:**
- Create: `deconstruction_runtime.go`
- Create: `planner_intent.go`
- Create: `planner_prompt.go`
- Create: `planner_strategy.go`

**Move groups:**
- deconstruction job creation/internal callback/result paths
- intent planner job and callback paths
- prompt planner direct/fallback paths
- strategy report job and result paths

**Verifier:** same package test plus fixed Prep/Sandbox lowlevel gate after this task.

### Task 1.4: Split generation, fanout, and writeback

**Files:**
- Create: `generation_versions.go`
- Create: `generation_fanout.go`
- Create: `generation_runtime.go`
- Create: `writeback.go`

**Move groups:**
- generation version CRUD/select/list/update
- runtime callback/result ingestion
- fanout prompt/template/provider config helpers
- selected generation asset writeback and relation metadata sanitation

**Verifier:** same package test + lowlevel gate.

### Task 1.5: Split validation/sanitize/map helpers

**Files:**
- Create: `validation.go`
- Create: `sanitize.go`
- Create: `mapping.go`
- Create: `ids.go`

**Move groups:**
- vocabulary validators
- forbidden metadata key scanners
- `buildID`, JSON encode/decode, int/string helper extraction
- DTO/projection helpers that are not specific to one runtime lane

**Acceptance:** original `service.go` below 800 lines and all new files below 800 lines. Remove visualworkflow service allowlist entry.

---

## Phase 2: Visual Workflow tests split

**Objective:** Keep test behavior identical while matching source split domains.

**Files:**
- Modify: `ecommerce-backend/internal/modules/visualworkflow/service_test.go`
- Create: `service_test_helpers_test.go`
- Create: `source_reference_test.go`
- Create: `deconstruction_runtime_test.go`
- Create: `planner_jobs_test.go`
- Create: `generation_runtime_test.go`
- Create: `generation_fanout_test.go`
- Create: `writeback_test.go`

**Rules:**
- Move fixtures (`setupVisualWorkflowTest`, mock runtime, router, seed helpers) first.
- Preserve test names so historical `go test -run TestName` commands still work.
- Do not merge or delete assertions during movement.

**Verifier:**

```bash
cd /root/work/v/ecommerce-backend
gofmt -w internal/modules/visualworkflow/*_test.go
go test ./internal/modules/visualworkflow -count=1
```

---

## Phase 3: ProductCore and ImageRuntime backend split

### Task 3.1 ProductCore split

**Files:**
- `service.go` remains constructor + shared dependencies
- Create `products.go`, `assets.go`, `listing_versions.go`, `export_tasks.go`, `download_packages.go`, `validation.go`, `activity.go`

**Verifier:**

```bash
cd /root/work/v/ecommerce-backend
gofmt -w internal/modules/productcore/*.go
go test ./internal/modules/productcore -count=1
go test ./... -count=1
```

### Task 3.2 ImageRuntime split

**Files:**
- `service.go` remains constructor + public high-level service shape
- Create `source_assets.go`, `jobs.go`, `runtime_callbacks.go`, `prompt_compiler.go`, `billing.go`, `product_assets.go`, `mapping.go`

**Verifier:**

```bash
cd /root/work/v/ecommerce-backend
gofmt -w internal/modules/imageruntime/*.go
go test ./internal/modules/imageruntime -count=1
go test ./... -count=1
```

---

## Phase 4: Frontend production service split

**Objective:** Preserve the `src/services/production.ts` public export surface while moving implementation into domain modules.

**Files:**
- Modify: `ecommerce-frontend/src/services/production.ts`
- Create directory: `ecommerce-frontend/src/services/production/`
- Create: `client.ts`, `session.ts`, `sources.ts`, `parsing.ts`, `decisionTree.ts`, `intents.ts`, `generation.ts`, `fanout.ts`, `versions.ts`, `refinement.ts`, `localStorage.ts`, `mappers.ts`, `types.ts`

**Rules:**
- Keep existing imports working by re-exporting from `production.ts`.
- Avoid user-facing backend/runtime terms in new copy.
- Do not change API paths or response handling semantics.

**Verifier:**

```bash
cd /root/work/v/ecommerce-frontend
npm run typecheck
npm run build
```

---

## Phase 5: Frontend production page splits

### Task 5.1 SandboxPage split

**Files:**
- Keep `SandboxPage.tsx` as route container.
- Create `src/pages/production/sandbox/constants.ts`, `promptPlan.ts`, `WireframePreview.tsx`, `SectionCard.tsx`, `resultPreload.ts`.

### Task 5.2 PrepHubPage split

**Files:**
- Keep `PrepHubPage.tsx` as route container.
- Create `src/pages/production/prepHub/localization.ts`, `UploadZone.tsx`, `DecisionStepCard.tsx`, `AttributeRow.tsx`, `decisionMapping.ts`.

### Task 5.3 GenericPage split

**Files:**
- Keep `GenericPage.tsx` as route container.
- Create `src/pages/generic/decorations.tsx`, `pageMap.ts`, `portalDetailMap.ts`, `sections.tsx`.

**Verifier:** frontend typecheck/build plus lowlevel gate for production pages.

---

## Phase 6: i18n namespace split

**Objective:** Keep `en` and `zh` aggregate exports stable while moving large literal objects into namespace files.

**Files:**
- Modify: `src/i18n/en.ts`, `src/i18n/zh.ts`
- Create: `src/i18n/en/common.ts`, `portal.ts`, `production.ts`, `account.ts`, `commerce.ts`, `errors.ts`
- Create: `src/i18n/zh/common.ts`, `portal.ts`, `production.ts`, `account.ts`, `commerce.ts`, `errors.ts`

**Verifier:**

```bash
cd /root/work/v/ecommerce-frontend
npm run typecheck
npm run build
```

---

## Phase 7: Residual Ecommerce guard burn-down

**Objective:** Clear every remaining P3 allowlist entry discovered by the full-tree guard so strict mode becomes the normal baseline rather than a future aspiration.

**Backend files:**
- `ecommerce-backend/internal/repository/template_center_repository.go`: split template catalog queries, favorite/copy/use mutations, row scanners/mappers.
- `ecommerce-backend/internal/platform/client.go`: split platform auth/session, runtime, wallet/billing/commercial methods while preserving one client type.
- `ecommerce-backend/internal/modules/productcore/handler_test.go`: split handler tests by product/assets/listing/export/download route families.
- `ecommerce-backend/internal/modules/imageruntime/handler_test.go`: split handler tests by source assets, job lifecycle, content proxy, callbacks.
- `ecommerce-backend/internal/modules/visualworkflow/types.go`: split DTOs by source, deconstruction, planner, generation, writeback.

**Frontend files:**
- `AgentTemplateMarketPage.tsx`: extract filter state, cards, detail drawer, and use-now action panel.
- `ToolPage.tsx`: extract upload/source/runtime/history sections.
- `WorkshopPage.tsx`: extract controls, result grid, prompt summary, fanout status helpers.
- `AssetCommercePage.tsx`: extract asset list, commerce order, delivery/download panels.
- `ProductDetailPage.tsx` and `ProductDetailTabs.tsx`: extract hooks and tab panels by product domain.
- `DesignWorkbenchPage.tsx`: extract workbench panels/helpers.
- `services/product.ts`: split product/listing/export/download API service domains and re-export stable API.

**Verifier:** backend package tests, frontend typecheck/build, listing/export gate for product surfaces, lowlevel gate for production surfaces.

---

## Final acceptance checklist

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_ecommerce_large_source_guard.py --strict --format json
python3 scripts/v_ecommerce_large_source_guard_smoke.py
python3 scripts/v_business_gate_selector.py --changed-file ecommerce-frontend/src/services/production.ts --run --format json
scripts/v-requirement-gate.sh ecommerce-v2-prep-sandbox-lowlevel static,api,browser,evidence requirement.changed.v.ecommerce-v2-prep-sandbox-lowlevel
scripts/requirement-gate.sh ecommerce-v1-listing-export-gate static requirement.changed.v.ecommerce-v1-listing-export
scripts/requirement-gate.sh ecommerce-critical-journey-release-gate static,api,browser,evidence release.v.ecommerce

cd /root/work/v/ecommerce-backend
go test ./... -count=1

cd /root/work/v/ecommerce-frontend
npm run typecheck
npm run build
```

**Done when:** strict guard returns `PASS`, all changed source files are below 800 lines, ecom backend tests pass, frontend typecheck/build pass, and required SelfCheck gates report PASS/PASS_WITH_NOTES with report paths captured.
