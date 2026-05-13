# Harness Report: ecommerce-product-ai-pipeline

- Feature: `ecommerce-product-ai-pipeline`
- Project: `v-ecommerce-worktree`
- Level target: `L3.5`
- Repair policy: `default-repair-policy`

## Coverage

- Machine gates: 5
- Role gates: 5
- Evidence present: 10/10
- Workflow phases present: 7/9
- Events / loops: 3 / 0

## Capabilities

- `frontend-runtime` — Frontend user workflow runtime capability. (capabilities/frontend-runtime.yaml)
- `ai-generation` — AI generation capability contract reusable across projects. (capabilities/ai-generation.yaml)
- `review-gates` — Independent review gate contract. (capabilities/review-gates.yaml)

## Machine Gates

- [ENFORCED_MACHINE_GATE] `static` / `frontend-typecheck` (static) — latest `PASS` reports/ecommerce-product-ai-pipeline/frontend-typecheck.json
- [ENFORCED_MACHINE_GATE] `static` / `frontend-build` (static) — latest `PASS` reports/ecommerce-product-ai-pipeline/frontend-build.json
- [ENFORCED_MACHINE_GATE] `api` / `api-readiness-smoke` (api) — latest `PASS` reports/ecommerce-product-ai-pipeline/api-readiness-smoke.json
- [ENFORCED_MACHINE_GATE] `browser` / `browser-login-surface-smoke` (browser) — latest `PASS` reports/ecommerce-product-ai-pipeline/browser-login-surface-smoke.json
- [ENFORCED_MACHINE_GATE] `evidence` / `evidence-gate` (evidence) — latest `PASS` reports/ecommerce-product-ai-pipeline/evidence-gate.json

## Role Gates

- [ROLE_GATE] `architect`
- [ROLE_GATE] `spec-review`
- [ROLE_GATE] `quality-review`
- [ROLE_GATE] `qa`
- [ROLE_GATE] `final-verification`

## Human Boundaries

- [HUMAN_BOUNDARY] AI Pipeline page information architecture is understandable to a target user.
- [HUMAN_BOUNDARY] Generated image/listing quality is acceptable for the product promise.
- [HUMAN_BOUNDARY] Release readiness and business tradeoffs are approved by the product owner.

## Evidence

- [EVIDENCE_REQUIRED] `reports/ecommerce-product-ai-pipeline/frontend-typecheck.json`
- [EVIDENCE_REQUIRED] `reports/ecommerce-product-ai-pipeline/frontend-build.json`
- [EVIDENCE_REQUIRED] `reports/ecommerce-product-ai-pipeline/api-readiness-smoke.json`
- [EVIDENCE_REQUIRED] `reports/ecommerce-product-ai-pipeline/browser-login-surface-smoke.json`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/01-requirement.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/02-architecture-review.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/05-spec-review-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/06-quality-review-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/07-qa-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/08-final-verification.md`

## Workflow Phases

- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/01-requirement.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/02-architecture-review.md`
- [MISSING_OR_STALE] `.hermes/workflows/ecommerce-product-ai-pipeline/03-implementation-plan.md`
- [MISSING_OR_STALE] `.hermes/workflows/ecommerce-product-ai-pipeline/04-implementation-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/05-spec-review-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/06-quality-review-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/07-qa-report.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/08-final-verification.md`
- [EVIDENCE_REQUIRED] `.hermes/workflows/ecommerce-product-ai-pipeline/09-harness-report.md`

## Events and Loops

- event `changed-ecommerce-ai-pipeline` groups=static,api,browser mode=event
- event `changed-v-ecommerce-requirement` groups=static,api,browser,evidence mode=event
- event `watchdog-ecommerce-ai-pipeline` groups=static,api,browser mode=watchdog

## Missing or Stale

- .hermes/workflows/ecommerce-product-ai-pipeline/03-implementation-plan.md
- .hermes/workflows/ecommerce-product-ai-pipeline/04-implementation-report.md

## Legend

- ENFORCED_MACHINE_GATE: verifier is connected to `must_pass`.
- ROLE_GATE: reviewer/QA/final-verifier handoff is required.
- HUMAN_BOUNDARY: product/human decision boundary is explicit.
- EVIDENCE_REQUIRED: evidence path exists or is declared.
- MISSING_OR_STALE: declared object/evidence is absent or unreadable.
