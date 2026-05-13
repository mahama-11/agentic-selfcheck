# Requirement

Status: IN_PROGRESS

## Goal

Make C/D-risk frontend work automatically route into the existing prototype-first chain instead of relying on agent memory or manual discipline.

## Scope

- Add executable frontend risk router.
- Classify task payloads into A/B/C/D.
- For C/D frontend tasks, emit required prototype-first route and gates.
- For production-implementation feature contracts, fail closed if C/D frontend work omits required prototype-first gates.
- Provide smoke cases for good, bad, low-risk, task classification, and workflow initialization.

## Non-goals

- No new design process family.
- No product UI implementation in V yet.
- No cron/hook install in this slice.

## Acceptance

- `scripts/frontend_risk_routing_smoke.py --root . --format text` PASS.
- `scripts/frontend_risk_router.py --root . --scan-features --format text` PASS.
- SelfCheck validate and `frontend-risk-routing` static run PASS.
