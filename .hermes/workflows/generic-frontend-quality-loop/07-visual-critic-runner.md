# Visual Critic Runner Deepening

## Verdict

PASS

## Purpose

Prototype quality should not depend on manually written critique/scorecard documents. This slice adds structured visual critique as a first-class artifact and materializes gate files from that structured output.

## Added artifacts

### Schema

```text
schemas/frontend-prototype-critique.schema.json
```

Defines structured critic output:

- risk;
- workflow;
- image evidence;
- verdict;
- ten numeric score dimensions;
- findings;
- required changes;
- acceptance decision;
- human review requirement.

### Runner

```text
scripts/frontend_visual_critic.py
```

Capabilities:

```bash
# Generate a strict critic prompt
python3 scripts/frontend_visual_critic.py \
  --workflow <workflow> \
  --risk C \
  --print-prompt

# Validate structured critic JSON
python3 scripts/frontend_visual_critic.py \
  --workflow <workflow> \
  --risk C \
  --input-json <workflow>/visual-critique.json

# Materialize gate artifacts from structured critic JSON
python3 scripts/frontend_visual_critic.py \
  --workflow <workflow> \
  --risk C \
  --input-json <workflow>/visual-critique.json \
  --write-artifacts
```

Writes:

```text
DESIGN_CRITIQUE.md
PROTOTYPE_SCORECARD.md
PROTOTYPE_ACCEPTANCE.md
```

### Template doc

```text
templates/frontend/high-fidelity-prototype-gate/VISUAL_CRITIQUE_JSON.md
```

### Gate integration

Updated:

```text
scripts/frontend_quality_gate.py
```

Concrete workflows now require:

```text
visual-critique.json
```

in addition to markdown artifacts and image evidence.

## Demo execution

Used real image evidence:

```text
.hermes/workflows/frontend-prototype-demo/prototype-screenshots/prototype-v2.png
```

Vision critic reviewed the image and produced structured judgment:

- average score: 3.84
- min score: 3.1
- verdict: PASS_WITH_NOTES
- acceptance decision: ACCEPTED_WITH_NOTES
- conclusion: passes C threshold narrowly, but needs operational hardening before implementation handoff.

Stored as:

```text
.hermes/workflows/frontend-prototype-demo/visual-critique.json
```

Then materialized:

```text
.hermes/workflows/frontend-prototype-demo/DESIGN_CRITIQUE.md
.hermes/workflows/frontend-prototype-demo/PROTOTYPE_SCORECARD.md
.hermes/workflows/frontend-prototype-demo/PROTOTYPE_ACCEPTANCE.md
```

## Verification

Executed:

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/frontend_visual_critic.py scripts/frontend_quality_gate.py scripts/init_frontend_workflow.py
python3 scripts/frontend_visual_critic.py --workflow .hermes/workflows/frontend-prototype-demo --risk C --input-json .hermes/workflows/frontend-prototype-demo/visual-critique.json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-prototype-demo --risk C --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/good-c --risk C --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/good-d --risk D --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-critic-missing-json --risk C --format json
python3 scripts/frontend_visual_critic.py --workflow .hermes/workflows/frontend-prototype-demo --risk C --input-json /tmp/frontend-visual-critic-verify/invalid-critique.json
python3 -m selfcheck validate --root .
python3 -m selfcheck run --root . --feature frontend-prototype-gate --groups static
```

Results:

- valid visual critique JSON: PASS
- demo gate: PASS
- good C: PASS
- good D: PASS
- missing `visual-critique.json`: FAIL as expected
- invalid critic JSON: FAIL as expected
- selfcheck validate: PASS
- frontend-prototype-gate static run: PASS

Evidence:

```text
/tmp/frontend-visual-critic-verify/critic-valid.json
/tmp/frontend-visual-critic-verify/demo-gate.json
/tmp/frontend-visual-critic-verify/good-c-gate.json
/tmp/frontend-visual-critic-verify/good-d-gate.json
/tmp/frontend-visual-critic-verify/missing-json-gate.json
/tmp/frontend-visual-critic-verify/invalid-critic-result.json
/tmp/frontend-visual-critic-verify/validate.txt
/tmp/frontend-visual-critic-verify/run-prototype-gate.txt
```

## New hard rule

```text
No structured visual critique JSON -> no prototype gate PASS.
```

This reduces hand-written scorecard drift and makes design critique auditable.
