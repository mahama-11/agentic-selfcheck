# Platform Ops Visible Baseline Requirement

Role: Orchestrator
Timestamp: 2026-05-07T03:45:25.026786Z

## Goal
Make the Platform Operations Console useful for local Agent Ecommerce admin/ops review by seeding and verifying platform-visible operational data, not only product-side business fixtures.

## User-facing problem
The user can login to Ecommerce and Platform, but Platform Template Ops shows empty catalog and Catalog & Assets lacks Ecommerce SKU/Package/RateCard/BillableItem price data.

## Scope
- Platform Template Ops must show Ecommerce template projections derived from the existing ecommerce template seed.
- Platform Catalog & Assets must show minimum Ecommerce commercial configuration: Product, SKU, Package, BillableItem, RateCard, Asset Definition / Allowance where applicable.
- Data must be synthetic, local/dev-safe, idempotent, and mainstream commercial modeling oriented.
- Add/extend SelfCheck gate for API semantics and Platform frontend visibility.

## Layering contract
- Ecommerce remains owner of business template fixture truth.
- Platform owns platform-visible projection/governance view and commercial catalog/price primitives.
- Platform must not absorb ecommerce workflow logic beyond projection/ops metadata and commercial catalog primitives.

## Acceptance
- Platform frontend login works on `http://127.0.0.1:5173/login`.
- `/template-ops` shows Ecommerce templates, not empty state.
- `/catalog` shows Agent Ecommerce product and non-empty Ecommerce SKU/Package/BillableItem/RateCard data.
- Semantic API gate asserts counts/content, not just HTTP 200.
- Browser QA captures screenshot and confirms Template Ops + Catalog & Assets visible data.
- SelfCheck validate/audit passes after final evidence.

## Non-goals
- No production data cloning.
- No real payment provider integration.
- No broad platform commercial model redesign unless required for this seed baseline.
- No public exposure of backend/admin ports; frontend-only tunnel is enough for human review.
