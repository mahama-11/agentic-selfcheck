# Prototype Quality Hardening Implementation

## Verdict

PASS

## What changed

The generic frontend high-fidelity prototype gate was hardened from a baseline plumbing check into a quality gate.

Before:

```text
required docs + any screenshot directory -> PASS
```

Now:

```text
context pack
+ design critique
+ prototype scorecard
+ acceptance decision
+ screenshot evidence
+ C/D score thresholds
+ D-risk multi-lane and human sign-off
-> PASS
```

## Added / updated artifacts

### Documentation

- `docs/frontend-quality-loop.md`
  - Added “Prototype quality hardening: not a single-agent MVP”.
  - Explicitly states that standalone HTML is a fallback, not the quality ceiling.
  - C/D frontend tasks require quality scoring and critique.

### Templates

Added:

- `templates/frontend/high-fidelity-prototype-gate/CONTEXT_PACK.md`
- `templates/frontend/high-fidelity-prototype-gate/DESIGN_LANES.md`
- `templates/frontend/high-fidelity-prototype-gate/DESIGN_CRITIQUE.md`
- `templates/frontend/high-fidelity-prototype-gate/PROTOTYPE_SCORECARD.md`

Existing templates remain:

- `DESIGN_BRIEF.md`
- `INTERACTION_MODEL.md`
- `STATE_MATRIX.md`
- `VISUAL_ACCEPTANCE_CHECKLIST.md`
- `PROTOTYPE_ACCEPTANCE.md`
- `PROTOTYPE_PARITY_PLAN.md`
- `VARIANT_COMPARISON.md`
- `HUMAN_SIGNOFF.md`

### Gate script

Updated:

- `scripts/frontend_quality_gate.py`

New behavior:

- Validates base templates.
- Validates concrete workflow artifacts.
- Parses `PROTOTYPE_SCORECARD.md` numeric scores.
- Enforces C threshold:
  - average >= 3.8
  - no dimension below 3.0
- Enforces D threshold:
  - average >= 4.2
  - no dimension below 3.5
  - at least two design lanes
- Requires `DESIGN_CRITIQUE.md` to contain PASS/PASS_WITH_NOTES.
- Requires `PROTOTYPE_ACCEPTANCE.md` to contain ACCEPTED/ACCEPTED_WITH_NOTES.
- Requires screenshot/visual evidence files.

### SelfCheck features

Updated:

- `features/frontend-design-intake.yaml`
- `features/frontend-prototype-gate.yaml`
- `features/frontend-prototype-parity-gate.yaml`

Added governance metadata:

- `prototype_quality_hardened: true`
- `not_mvp: true`
- C/D quality thresholds.

## Verification

Executed:

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/frontend_quality_gate.py
python3 scripts/frontend_quality_gate.py --root . --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/good-c --risk C --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/good-d --risk D --format json
python3 scripts/frontend_quality_gate.py --root . --workflow .hermes/workflows/frontend-quality-hardening-smoke/bad-low-score --risk C --format json
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root . --feature frontend-design-intake --strict-missing
python3 -m selfcheck audit --root . --feature frontend-prototype-gate --strict-missing
python3 -m selfcheck audit --root . --feature frontend-prototype-parity-gate --strict-missing
python3 -m selfcheck run --root . --feature frontend-design-intake --groups static
python3 -m selfcheck run --root . --feature frontend-prototype-gate --groups static
python3 -m selfcheck run --root . --feature frontend-prototype-parity-gate --groups static
```

Results:

- Base gate: PASS
- Good C workflow: PASS, average 3.88, min 3.4
- Good D workflow: PASS, average 4.24, min 3.8, design lanes 2
- Bad low-score workflow: FAIL as expected, average 2.48, min 2.0
- `selfcheck validate`: PASS
- Feature audits: PASS
- Feature static runs: PASS

Evidence files:

```text
/tmp/frontend-quality-hardening/base.json
/tmp/frontend-quality-hardening/good-c.json
/tmp/frontend-quality-hardening/good-d.json
/tmp/frontend-quality-hardening/bad-low-score-rerun.json
/tmp/frontend-quality-hardening/validate.txt
/tmp/frontend-quality-hardening/run-design-intake.txt
/tmp/frontend-quality-hardening/run-prototype-gate.txt
/tmp/frontend-quality-hardening/run-parity.txt
```

## Operating rule

```text
A low-quality prototype cannot pass just because files/screenshots exist.
```

For C/D frontend work:

```text
No quality scorecard pass -> no production implementation.
No design critique pass -> no production implementation.
No accepted prototype -> no production implementation.
No parity plan -> no final verification PASS.
```
