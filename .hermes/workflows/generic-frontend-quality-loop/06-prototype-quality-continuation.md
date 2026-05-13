# Prototype Quality Continuation

## Verdict

PASS

## What was added after hardening

### 1. Workflow initializer

Added:

```text
scripts/init_frontend_workflow.py
```

Usage:

```bash
python3 scripts/init_frontend_workflow.py \
  --root . \
  --name <workflow-name> \
  --risk C|D \
  --project <project-name> \
  --title '<human title>'
```

It creates:

```text
.hermes/workflows/<workflow-name>/
```

with all high-fidelity prototype templates and evidence directories:

```text
prototype-artifacts/
prototype-screenshots/
production-screenshots/
visual-evidence/
browser-evidence/
```

### 2. Real image evidence enforcement

Updated:

```text
scripts/frontend_quality_gate.py
```

It now distinguishes evidence buckets:

```text
prototype
production
visual
browser
other
```

and only counts real image evidence:

```text
.png
.jpg
.jpeg
.webp
```

`.gitkeep` and text placeholders no longer satisfy visual evidence.

C/D workflows now require at least one prototype screenshot image. D-risk requires at least two prototype screenshot/variant images.

### 3. AI design agent playbook

Added:

```text
templates/frontend/high-fidelity-prototype-gate/AI_DESIGN_AGENT_PLAYBOOK.md
```

It defines reusable roles:

```text
Product/UX Decomposer
Design Lane Agents
Design Critic Agent
Frontend Architect Agent
Human/Product Acceptance Boundary
```

## Verification

Executed:

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/frontend_quality_gate.py scripts/init_frontend_workflow.py
python3 scripts/init_frontend_workflow.py --root . --name frontend-init-smoke-d --risk D --project demo --title 'D Risk Init Smoke' --force
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-init-smoke-d --risk D --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/good-c --risk C --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/good-d --risk D --format json
python3 scripts/init_frontend_workflow.py --root . --name frontend-init-bad-evidence --risk C --project demo --title 'Bad Evidence' --force
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-init-bad-evidence --risk C --format json
python3 -m selfcheck validate --root .
python3 -m selfcheck run --root . --feature frontend-prototype-gate --groups static
```

Results:

- Initialized D workflow can pass after populated with valid artifacts.
- Good C remains PASS.
- Good D remains PASS.
- Bad evidence workflow FAILS as expected even with good scores, because it has no real prototype image.
- `selfcheck validate`: PASS.
- `frontend-prototype-gate` static run: PASS.

Evidence:

```text
/tmp/frontend-quality-continuation/init-filled-d.json
/tmp/frontend-quality-continuation/good-c.json
/tmp/frontend-quality-continuation/good-d.json
/tmp/frontend-quality-continuation/bad-evidence.json
/tmp/frontend-quality-continuation/validate.txt
/tmp/frontend-quality-continuation/run-prototype-gate.txt
```

## Updated rule

```text
No real image evidence -> no prototype gate PASS.
```

This prevents placeholder files or text-only evidence from satisfying a visual gate.
