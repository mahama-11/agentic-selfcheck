# Platform Ops Visible Baseline Architecture Review

Role: Architect
Timestamp: 2026-05-07T03:46:59Z
Requirement: `01-requirement.md`

## 1. Decision Summary

This slice should be implemented as a **platform-owned visibility/projection baseline**, not as product workflow logic in Platform and not as a frontend-only mock.

- **Template Ops**: Ecommerce remains the owner of template marketplace/business fixture truth. Platform owns an idempotent `TemplateProjection` view that is populated from Ecommerce template-center APIs or an explicitly prepared local projection import. `/template-ops` must read Platform projections and show Ecommerce templates without requiring a human to manually create rows.
- **Catalog & Assets**: Platform owns shared commercial primitives: `Product`, `SKU`, `CommercialPackage`, `BillableItem`, `RateCard`, `AssetDefinition`, and entitlement/allowance policies. Ecommerce-specific rows are acceptable here only as product-scoped commercial catalog configuration, not as Ecommerce workflow state.
- **Frontend**: Platform frontend should consume existing platform APIs and render real rows. It should not synthesize Ecommerce templates or commercial rows client-side.
- **Gates**: Acceptance must verify semantic content/counts through APIs and browser screenshots, not just HTTP 200.

## 2. Current-State Findings

### 2.1 Template Ops path

Relevant modules/files:

- Backend routes: `/root/work/v/platform-backend/internal/router/router.go`
  - Admin APIs under `/api/v1/template-ops/*` require `platform.admin`.
  - Internal APIs expose `/internal/v1/template-ops/catalog` and detail.
- Backend service: `/root/work/v/platform-backend/internal/modules/templateops/service.go`
  - `ListCatalog` reads from `models.TemplateProjection` only.
  - `SyncFromUpstream` can fetch `menu` and `ecommerce` upstream template-center APIs and upsert `TemplateProjection` rows.
  - `listEcommerceCatalog` calls `{ecommerceBaseURL}/api/v1/template-center/catalog?locale=...&sortBy=recommended` and maps Ecommerce fields (`id`, `slug`, `name`, `summary`, `modality`, `series`, `capabilityType`, `coverAssetUrl`, tags, `recommendScore`) into platform projection fields.
  - Detail sync calls `{ecommerceBaseURL}/api/v1/template-center/catalog/{templateId}?locale=...` and stores the raw detail JSON.
- Frontend page: `/root/work/v/platform-frontend/src/modules/template-ops/pages/TemplateOpsPage.tsx`
  - Loads `platformClient.templateOpsCatalog({ limit: 200 })` from `/template-ops/catalog`.
  - Shows empty state when `items` is empty; it does not auto-sync upstream.
- Frontend API client: `/root/work/v/platform-frontend/src/shared/api/platformClient.ts`
  - Has existing methods for list/detail/sync/import/assets.
- Ecommerce backend contract:
  - Runtime worktree route: `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend/internal/router/router.go` exposes `/api/v1/ecommerce/template-center/catalog` and detail under an Ecommerce route group.
  - Platform `templateops` currently calls `/api/v1/template-center/catalog` without the `/ecommerce` segment. This route-shape mismatch is a likely cause of sync/import failure unless there is an additional compatibility route not found in the inspected router.
- Config:
  - `/root/work/v/platform-backend/config.local.yaml` sets Ecommerce product endpoint base URL to `http://v-ecommerce-backend-dev:8396`, but the local context says Ecommerce backend is available on `127.0.0.1:8396`. If Platform runs outside the docker network, this hostname may not resolve. The slice should ensure local config/runtime points to a reachable Ecommerce base URL for Template Ops sync.

Architecture implication: the empty `/template-ops` page is likely because Platform projection rows are absent and/or upstream sync cannot reach the Ecommerce route/base URL. The implementation should make projection population explicit, idempotent, and locally reliable.

### 2.2 Catalog & Assets path

Relevant modules/files:

- Backend routes: `/root/work/v/platform-backend/internal/router/router.go`
  - `/api/v1/catalog/products`, `/skus`, `/packages`, `/billable-items`, `/rate-cards`, `/offerings`.
- Backend service: `/root/work/v/platform-backend/internal/modules/catalog/service.go`
  - `Offerings(productCode)` returns product, SKUs, packages, billable items, rate cards, asset definitions, allowance policies.
  - CRUD/list services already exist for all required commercial primitives.
- Seed/migrations:
  - `/root/work/v/platform-backend/internal/migration/ecommerce_offerings_seed.go` already defines Ecommerce product-scoped commercial seed data:
    - Product: `prd_ecommerce`, code `ecommerce`, name `Ecommerce`.
    - Asset definitions: cash, credit, promo credit, monthly allowance.
    - Billable item: `ecommerce.image.generate`.
    - SKUs/packages/rate cards: basic/pro/growth subscriptions, permanent pack, promo pack, plus billable-item overage rate card.
    - Quota grant policies for each package.
  - `/root/work/v/platform-backend/internal/migration/migration.go` includes `seed_ecommerce_offerings` and `refresh_ecommerce_offerings_product_links` steps.
- Frontend page: `/root/work/v/platform-frontend/src/modules/catalog/pages/CatalogPage.tsx`
  - Loads all products, then selected product's SKU/package/billable/rate-card/assets/policies through existing API client calls.
  - Initial selection is `nextProducts[0]` if no product is preselected. If `menu` sorts before `ecommerce`, a user may initially see Menu data; the acceptance should explicitly select/verify the Ecommerce product.

Architecture implication: the commercial model exists. If Ecommerce SKU/package/rate-card rows are empty in local runtime, likely causes are unapplied migrations, stale DB state, seed idempotency/upsert defects, or the frontend looking at the wrong selected product. The slice should repair seed idempotency/gate visibility, not redesign catalog modeling.

## 3. Layering Contract

### Platform-owned

- `TemplateProjection` records and Template Ops governance/ops metadata (`scope`, `managed_source`, publish status, asset bindings, local storage asset linkage).
- Shared commercial catalog primitives and product-scoped synthetic local rows:
  - Product/SKU/package/billable item/rate card.
  - Asset definitions and allowance/quota/capability policies.
- Local dev bootstrap and SelfCheck gates that make Platform visibly useful.

### Ecommerce-owned

- Template-center business truth: template IDs, localized names/summaries, tool bindings, examples, tags, recommendation order, product-side workflow semantics.
- Ecommerce runtime workflow state, listing/export/order/download flows.

### Explicit non-boundaries

- Do **not** copy Ecommerce workflow state machines into Platform.
- Do **not** create frontend fake rows to satisfy screenshots.
- Do **not** require direct DB sharing from Platform to Ecommerce.
- Do **not** add product-specific route names beyond existing `product_code=ecommerce` scoped projections/catalog rows.

## 4. Recommended Implementation Plan for Developer

### Step A — Confirm and fix Template Ops projection population

Owner: Platform backend, with possible local config adjustment.

Inspect/modify candidates:

- `/root/work/v/platform-backend/internal/modules/templateops/service.go`
  - Verify Ecommerce route path. If Ecommerce only exposes `/api/v1/ecommerce/template-center/catalog`, update Platform's Ecommerce upstream adapter to use that path or centralize product route prefix by product code.
  - Keep mapping generic to projection fields; do not leak Ecommerce workflow behavior.
  - Add/extend unit tests for Ecommerce list/detail mapping using httptest and the actual route shape.
- `/root/work/v/platform-backend/config.local.yaml` or local runtime config handling
  - Ensure local Platform can reach Ecommerce at the configured base URL. For the stated local setup, `http://127.0.0.1:8396` is the expected default unless both services run on a docker network.
- Optional but preferred for visible baseline reliability:
  - Add a dev/local-only idempotent bootstrap step that runs Template Ops sync for `ecommerce` when dev seed is enabled and product endpoint is reachable, or provide a deterministic SelfCheck precondition step that calls `POST /api/v1/template-ops/sync?product_code=ecommerce&locale=zh` before browser QA.
  - If auto-sync is added, it must be best-effort/non-fatal on upstream outage and must log actionable errors.

Recommended stance: use the existing sync/projection mechanism rather than introducing a new Platform seed containing Ecommerce business fixture details. If a static prepared projection import is used for offline local demos, it must be explicitly labeled as a synthetic projection snapshot and generated from Ecommerce seed truth.

### Step B — Make Ecommerce commercial catalog rows present and visible

Owner: Platform backend primarily; frontend only if selection/visibility blocks acceptance.

Inspect/modify candidates:

- `/root/work/v/platform-backend/internal/migration/ecommerce_offerings_seed.go`
  - Verify all Ecommerce rows are idempotently upserted by stable `ID`/`Code` and linked to the actual `Product.ID` returned by `upsertProduct`.
  - Ensure SKU/package/rate-card/billable item counts survive reruns and stale product IDs.
  - Consider a new refresh migration only if existing migrations already marked applied in local DB before seed completeness was fixed.
- `/root/work/v/platform-backend/internal/migration/migration.go`
  - If local DBs can have the seed migration marked applied but missing rows, add a new `refresh_ecommerce_visible_baseline` migration that re-runs `seedEcommerceOfferings` and, if needed, entitlement policy refreshes. Do not mutate production-only data; this is synthetic dev-safe data.
- `/root/work/v/platform-backend/internal/modules/catalog/catalog_test.go`
  - Add semantic coverage that Ecommerce offerings include non-empty SKUs/packages/billable items/rate cards/assets/quota policies.
- `/root/work/v/platform-frontend/src/modules/catalog/pages/CatalogPage.tsx`
  - Only change if needed: make Product selection obviously accessible and ensure API failures are surfaced. Avoid hardcoding Ecommerce as default unless the requirement explicitly demands default selection.

### Step C — SelfCheck and browser gates

Owner: QA/SelfCheck/developer depending on lane conventions.

Likely locations to inspect/create:

- `/root/work/agentic-selfcheck/.hermes/workflows/platform-ops-visible-baseline/`
- Existing SelfCheck scripts under `/root/work/agentic-selfcheck/scripts/`.
- Existing Playwright/browser QA helpers if present in agentic-selfcheck.

Gate should authenticate as platform admin, then assert semantic payloads:

1. Login API succeeds and obtains token.
2. `POST /api/v1/template-ops/sync?product_code=ecommerce&locale=zh` succeeds if sync is the chosen seed mechanism.
3. `GET /api/v1/template-ops/catalog?product_code=ecommerce&limit=200` returns:
   - `total > 0`.
   - `items.length > 0`.
   - every sampled item has `product_code = ecommerce`, non-empty `template_ref`, `template_id`, `name`.
   - at least one sampled item has Ecommerce-specific projection fields such as `modality`, `series`, `capability_type`, or `cover_asset_url` when available.
4. `GET /api/v1/catalog/products` includes `code = ecommerce`.
5. For the Ecommerce product ID:
   - `/catalog/skus?product_id=...` count >= 3 (or exact expected count if stabilized).
   - `/catalog/packages?product_id=...` count >= 3.
   - `/catalog/billable-items?product_id=...` count >= 1 with code containing `ecommerce`.
   - `/catalog/rate-cards?product_id=...` count >= 3 and includes SKU-target rate cards and billable-item overage.
   - `/wallet/assets?product_code=ecommerce` count >= 1 and includes Ecommerce asset definitions.
   - quota/allowance/capability policies checked where applicable.
6. Browser QA:
   - Open `http://127.0.0.1:5173/login`, login.
   - `/template-ops` shows Ecommerce template cards/table rows and not `No templates returned from upstream products.`
   - `/catalog` shows Ecommerce product selectable/selected and non-empty SKU/package/billable/rate-card tabs.
   - Capture screenshots for Template Ops and Catalog & Assets.

## 5. Acceptance Criteria / Gates

### Must pass

- Platform frontend login works at `http://127.0.0.1:5173/login`.
- `/template-ops` shows non-empty Ecommerce template projections.
- `/catalog` shows `Agent Ecommerce`/`Ecommerce` product and non-empty Ecommerce SKU/package/billable/rate-card data.
- Platform APIs return semantic data, not just HTTP 200.
- Browser screenshots provide visual evidence for Template Ops and Catalog & Assets.
- SelfCheck validate/audit passes after evidence is recorded.

### Suggested concrete thresholds

- Template Ops Ecommerce projections: `total >= 1`; if the local Ecommerce seed is expected to expose the full catalog, prefer `total >= 100` or exact `173` only if stable and not environment-dependent.
- Commercial rows for Ecommerce:
  - Products: includes `ecommerce`.
  - SKUs: `>= 5` based on current seed.
  - Packages: `>= 5` based on current seed.
  - Billable items: `>= 1`.
  - Rate cards: `>= 6` based on current seed.
  - Asset definitions: `>= 4` based on current seed.
  - Quota policies: `>= 5` if policy endpoint is in gate scope.

## 6. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Platform Template Ops adapter path does not match Ecommerce route prefix | Sync returns zero/error; UI empty | Test and align to `/api/v1/ecommerce/template-center/catalog` or verified compatibility route |
| Local Platform config points to docker hostname while services run on localhost | Upstream unreachable | Use reachable local base URL or document docker-network requirement in config/gate |
| Projection population relies on manual button click | Fresh local review still empty | Gate should call sync or dev bootstrap should run best-effort sync |
| Existing local DB has migrations marked applied before seed completeness | Catalog remains empty despite code seed | Add refresh migration or idempotent repair command/gate |
| Frontend initially selects Menu product | Reviewer may think Ecommerce data missing | Browser gate must explicitly select Ecommerce or assert Ecommerce product section/tabs |
| Overfitting exact row counts | Brittle as template seed grows | Use lower-bound thresholds unless exact count is requirement-stable |

## 7. Files/Modules for Implementation Ownership

### Platform backend

- `internal/modules/templateops/service.go` — upstream sync adapter, projection mapping, tests.
- `internal/modules/templateops/handler.go` — existing sync/list endpoints; likely no contract change needed.
- `internal/modules/templateops/service_test.go` — mapping/sync/idempotency tests.
- `internal/modules/catalog/service.go` and `handler.go` — existing commercial APIs; inspect if list/filter semantics fail.
- `internal/migration/ecommerce_offerings_seed.go` — Ecommerce commercial seed truth in Platform.
- `internal/migration/migration.go` — add refresh migration only if required.
- `config.local.yaml` / `config.dev.yaml` — product endpoint reachability.

### Platform frontend

- `src/modules/template-ops/pages/TemplateOpsPage.tsx` — visibility only; avoid fake data.
- `src/modules/catalog/pages/CatalogPage.tsx` — product selection/tabs/API error visibility.
- `src/shared/api/platformClient.ts` and `src/shared/types/platform.ts` — verify existing API contracts; avoid raw fetch in pages.

### Ecommerce backend

- `internal/router/router.go` — authoritative route prefix for template-center APIs.
- `internal/modules/templatecenter/handler.go`, `service.go`, `seed.go` — source template catalog contract; no Platform ownership of business truth.
- Use runtime worktree `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend` if that is the active process serving port `8396`.

## 8. Architecture Recommendation

Approve the slice with this implementation direction:

1. **Use Platform TemplateProjection as the visible ops view.** Populate it via existing upstream sync from Ecommerce, with route/config fixes and idempotent semantics.
2. **Use existing Platform commercial catalog seed/model for Ecommerce pricing primitives.** Repair or refresh seed data only; do not redesign catalog.
3. **Make gates semantic and visual.** API checks must assert counts/content and browser QA must prove the console is useful.
4. **Keep ownership boundaries explicit.** Ecommerce owns template/business truth; Platform owns projection, governance metadata, and shared commercial primitives.

No product workflow logic should move into Platform, and no frontend mock should be introduced to satisfy visibility.
