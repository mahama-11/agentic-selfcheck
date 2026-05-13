# Frontend Prototype Workflow: Design Quality Init Smoke

- Risk: C
- Project: demo

## Required sequence

```text
Context pack -> design lanes -> critique -> scorecard -> acceptance -> parity plan -> implementation
```

## Validate

```bash
python3 scripts/frontend_design_quality_pack_gate.py --root . --workflow .hermes/workflows/frontend-design-quality-init-smoke --risk C --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-design-quality-init-smoke --risk C --format json
```

## Evidence dirs

- `prototype-artifacts/`: HTML/Figma exports/v0 output links captured as docs
- `prototype-screenshots/`: selected prototype screenshots
- `production-screenshots/`: implementation screenshots after build
- `visual-evidence/`: comparison notes/images
- `browser-evidence/`: Playwright/browser logs/screenshots
