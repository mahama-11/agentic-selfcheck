# Dev Seed Baseline Requirement

Role: Orchestrator
Timestamp: 2026-05-07T02:58:08.386075Z

## Goal
Establish a verified local dev seed baseline for `/root/work/v` so Agent Ecommerce can be logged into and exercised without empty-data dead ends. This is the first strict-autonomy L4 lane trial.

## Layering contract
- Platform owns common, reusable primitives: identity, organization, membership, RBAC, platform-level commercial/quota/capability primitives.
- Product backends own product/business fixtures: ecommerce template catalog, product-specific permissions/fixtures, business smoke paths.
- Do not copy production data into dev. Use synthetic, minimal, idempotent seeds.

## Acceptance
- Platform dev admin exists and can login in local dev.
- Platform RBAC seed is least-privilege, idempotent, and does not overgrant viewer/developer.
- Dev seed has explicit local/dev guardrails.
- Ecommerce local templates are seeded even when platform projection is enabled.
- Ecommerce template list -> detail -> favorite/copy/use works when platform catalog projection is empty.
- SelfCheck gate asserts semantics, not only row counts or HTTP 200.
- Workflow evidence includes architecture, developer summary, spec review, quality review, QA report, final verification.

## Non-goals
- No direct production data cloning.
- No production release.
- No broad platform identity redesign beyond seed baseline hardening.
