# Frontend Prototype Workflow: Redesign ecommerce Product Center workbench page

- Risk: C
- Project: unspecified

## Required sequence

```text
Design quality pack -> design lanes -> critique -> scorecard -> acceptance -> prototype freeze -> parity plan -> implementation
```

## Validate

```bash
python3 scripts/frontend_design_quality_pack_gate.py --root . --workflow .hermes/workflows/frontend-risk-routing-product-center-redesign --risk C --format json
python3 scripts/frontend_design_lane_gate.py --root . --workflow .hermes/workflows/frontend-risk-routing-product-center-redesign --risk C --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-risk-routing-product-center-redesign --risk C --format json
python3 scripts/frontend_prototype_freeze_gate.py --root . --workflow .hermes/workflows/frontend-risk-routing-product-center-redesign --risk C --format json
```

## Evidence dirs

- `prototype-artifacts/`: HTML/Figma exports/v0 output links captured as docs
- `prototype-screenshots/`: selected prototype screenshots
- `frozen-prototype/`: prototype-freeze gate output and implementation handoff artifacts
- `production-screenshots/`: implementation screenshots after build
- `visual-evidence/`: comparison notes/images
- `browser-evidence/`: Playwright/browser logs/screenshots
