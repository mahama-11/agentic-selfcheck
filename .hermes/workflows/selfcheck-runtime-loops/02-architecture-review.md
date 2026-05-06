# Architecture Review

Role: architect
Verdict: APPROVE_WITH_NOTES

Design:
- Generic SelfCheck runner now allows API/browser verifier execution only through harness scripts under `scripts/`.
- Ecommerce API harness checks live backend health/ready and frontend availability.
- Ecommerce browser harness launches `/usr/bin/chromium` headless, captures screenshot and DOM evidence for the login surface.
- Hooks:
  - `.githooks/pre-commit` runs schema/reference validation.
  - `scripts/pre-final-gate.sh` runs selected feature groups and strict evidence audit.
  - `scripts/workflow-health-loop.sh` runs recurring validation + ecommerce static/api/browser smoke.

Limit:
- No internal secrets or browser auth credentials are embedded.
