# Frontend Prototype Workflow: Bad Evidence

- Risk: C
- Project: demo

## Required sequence

```text
Context pack -> design lanes -> critique -> scorecard -> acceptance -> parity plan -> implementation
```

## Validate

```bash
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-init-bad-evidence --risk C --format json
```

## Evidence dirs

- `prototype-artifacts/`: HTML/Figma exports/v0 output links captured as docs
- `prototype-screenshots/`: selected prototype screenshots
- `production-screenshots/`: implementation screenshots after build
- `visual-evidence/`: comparison notes/images
- `browser-evidence/`: Playwright/browser logs/screenshots
