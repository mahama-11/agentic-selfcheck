# AI-Agent High-Fidelity Frontend Prototype Workflow

## User decision

User accepted high-fidelity prototype-first workflow and clarified:

- This is generic, not V-specific.
- V is only the first concrete implementation/application.
- Risk levels C and D should both require high-fidelity prototype before production implementation.
- There is no dedicated designer; therefore the prototype/design process itself must be engineered through AI agents.

## Research references

Checked current public references around AI/design/frontend delivery:

- Claude Artifacts: interactive UI/prototype artifacts.
- Claude Code: repo-aware implementation after acceptance.
- v0: React/Next/Tailwind/shadcn high-fidelity UI generation, design mode, design systems, Figma/GitHub integration.
- Lovable: agent mode, design guidance, design systems, browser testing, GitHub integration.
- Bolt/StackBlitz: browser-run prototype generation and Figma/GitHub integration.
- Figma Dev Mode / Figma MCP: design context into development tools.
- Storybook: component-driven development and state workshop.
- Chromatic: visual review/regression over Storybook.
- Playwright: route/flow screenshots and snapshots.
- Design Tokens / Style Dictionary: portable visual constraints.

## Landed generic control-plane assets

### Documentation

- `docs/frontend-quality-loop.md`
  - Generic project-agnostic process.
  - C/D require high-fidelity prototype.
  - Prototype is a visual contract, not inspiration.

### Templates

- `templates/frontend/high-fidelity-prototype-gate/DESIGN_BRIEF.md`
- `templates/frontend/high-fidelity-prototype-gate/INTERACTION_MODEL.md`
- `templates/frontend/high-fidelity-prototype-gate/STATE_MATRIX.md`
- `templates/frontend/high-fidelity-prototype-gate/VISUAL_ACCEPTANCE_CHECKLIST.md`
- `templates/frontend/high-fidelity-prototype-gate/PROTOTYPE_ACCEPTANCE.md`
- `templates/frontend/high-fidelity-prototype-gate/PROTOTYPE_PARITY_PLAN.md`
- `templates/frontend/high-fidelity-prototype-gate/VARIANT_COMPARISON.md`
- `templates/frontend/high-fidelity-prototype-gate/HUMAN_SIGNOFF.md`

### Script

- `scripts/frontend_quality_gate.py`
  - Validates generic template/doc presence.
  - Can validate a concrete workflow directory with `--workflow <dir> --risk C|D`.
  - D-risk requires variant comparison and human sign-off.
  - C/D concrete workflow requires screenshot/visual evidence directory.

### SelfCheck features

- `features/frontend-design-intake.yaml`
- `features/frontend-prototype-gate.yaml`
- `features/frontend-prototype-parity-gate.yaml`

### Verifier

- `verifiers/frontend-high-fidelity-prototype-gate.yaml`

## Verification

Executed:

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/frontend_quality_gate.py
python3 scripts/frontend_quality_gate.py --root . --format json
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root . --feature frontend-design-intake --strict-missing
python3 -m selfcheck audit --root . --feature frontend-prototype-gate --strict-missing
python3 -m selfcheck audit --root . --feature frontend-prototype-parity-gate --strict-missing
python3 -m selfcheck run --root . --feature frontend-design-intake --groups static
python3 -m selfcheck run --root . --feature frontend-prototype-gate --groups static
python3 -m selfcheck run --root . --feature frontend-prototype-parity-gate --groups static
```

Result:

- `selfcheck validate`: PASS
- generic feature audits: PASS
- all three generic frontend feature runs: PASS

## Operating rule

For future C/D frontend tasks:

```text
No accepted high-fidelity prototype -> no production implementation.
No prototype parity evidence -> no final verification PASS.
```
