# Frontend Prototype Workflow: Lane init smoke

- Risk: D
- Project: smoke

## Required sequence

```text
Design quality pack -> design lanes -> critique -> scorecard -> acceptance -> parity plan -> implementation
```

## Validate

```bash
python3 scripts/frontend_design_quality_pack_gate.py --root . --workflow .hermes/workflows/frontend-design-lane-init-smoke --risk D --format json
python3 scripts/frontend_design_lane_gate.py --root . --workflow .hermes/workflows/frontend-design-lane-init-smoke --risk D --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-design-lane-init-smoke --risk D --format json
```

## Evidence dirs

- `prototype-artifacts/`: HTML/Figma exports/v0 output links captured as docs
- `prototype-screenshots/`: selected prototype screenshots
- `production-screenshots/`: implementation screenshots after build
- `visual-evidence/`: comparison notes/images
- `browser-evidence/`: Playwright/browser logs/screenshots
