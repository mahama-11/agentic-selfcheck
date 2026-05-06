# Developer Summary

Role: developer

Changed:
- `selfcheck/__main__.py`: API/browser harness execution through safe `scripts/` path resolution.
- `scripts/project_api_smoke.sh` and `scripts/ecommerce_api_smoke.py`.
- `scripts/project_browser_smoke.sh` and `scripts/ecommerce_browser_smoke.py`.
- `.githooks/pre-commit`.
- `scripts/pre-final-gate.sh`.
- `scripts/workflow-health-loop.sh`.
- `features/ecommerce-product-ai-pipeline.yaml` evidence updated.
- Added workflow evidence for ecommerce-product-ai-pipeline and selfcheck-runtime-loops.

Behavior:
- Static/API/browser groups now execute and emit JSON reports.
- Browser artifacts include screenshot and DOM dump.
- Pre-final gate runs selected groups and strict evidence audit.
