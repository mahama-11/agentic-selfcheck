# Frontend Autonomy Long Lane Implementation Plan

> **For Hermes:** Use subagent-driven-development and strict-autonomy-role-pipeline. Do not stop after each slice when the next deterministic gate is known.

**Goal:** Turn C/D-risk frontend work into a durable autonomous chain from design context to production parity, with hard gates, evidence, reviews, and final verification.

**Architecture:** Agentic SelfCheck remains the control-plane source of truth. Each capability is a feature contract + schema + script/verifier + smoke fixtures + workflow evidence. The orchestrator may continue through deterministic slices without asking the user for a new “continue”, stopping only for destructive changes, external credentials, cost/risk expansion, or required human product sign-off.

**Tech Stack:** Python stdlib validators, SelfCheck feature/verifier YAML, `.hermes/workflows/*` evidence, generic frontend templates.

---

## Autonomy Rule

When the user asks to “继续落地 / 猛猛干 / 不要每步等我”, the lane proceeds automatically through the following backlog until one of these occurs:

- Final Verifier PASS for the whole current tranche.
- A blocker needs human decision: accepted visual direction, destructive migration, credentials, external SaaS setup, or conflicting product semantics.
- Tool/runtime limit requires a durable continuation job/workflow checkpoint.
- A reviewer returns BLOCKED after repair budget is exhausted.

The assistant should report completed tranches, not use every tranche boundary as a permission checkpoint.

## Current completed gates

1. `frontend-design-quality-pack` — generation preflight context.
2. `frontend-design-lane-generation` — multi-lane high-fidelity prototype exploration.
3. `frontend-reference-aware-visual-critic` — critique against references/aesthetic/tokens/components/project rules.

## Remaining long-lane backlog

### Task 1: Prototype Freeze / Implementation Contract

**Objective:** Freeze the accepted prototype as a contract before production implementation starts.

**Create:**
- `templates/frontend/prototype-freeze/PROTOTYPE_FREEZE.md`
- `templates/frontend/prototype-freeze/COMPONENT_MAPPING.md`
- `templates/frontend/prototype-freeze/API_STATE_MAPPING.md`
- `templates/frontend/prototype-freeze/IMPLEMENTATION_CONTRACT.md`
- `schemas/frontend-prototype-freeze.schema.json`
- `scripts/frontend_prototype_freeze_gate.py`
- `scripts/frontend_prototype_freeze_smoke.py`
- `features/frontend-prototype-freeze.yaml`
- `verifiers/frontend-prototype-freeze-gate.yaml`

**Modify:**
- `scripts/init_frontend_workflow.py` to scaffold freeze templates and dirs.
- `scripts/frontend_quality_gate.py` to require freeze only at implementation-readiness/parity phase, not at earlier prototype acceptance unless explicitly requested.

**Acceptance:**
- C/D workflow must record accepted prototype artifact, selected lane, frozen screenshots, component mapping, API/state mapping, implementation constraints, allowed deviations, forbidden reinterpretations, and owner/date.
- Missing selected lane, missing frozen screenshot, unapproved material deviation, or component/API mapping gaps fail closed.
- Smoke positive/negative fixtures pass.
- SelfCheck validate/audit/run pass.

### Task 2: Project Adapter Bootstrap

**Objective:** Generate project-local persistent frontend rules so accepted gates are actually used in a real repo.

**Create:**
- `scripts/frontend_project_adapter_init.py`
- `schemas/frontend-project-adapter.schema.json`
- templates for `PROJECT_ADAPTER.yaml`, `.cursor/rules/frontend-design.mdc`, `CLAUDE.md` frontend section, Playwright/Storybook command registry.
- feature/verifier/smoke.

**Acceptance:** adapter can be initialized for arbitrary project root without overwriting existing human-authored rules unless `--force` is set.

### Task 3: Prototype-to-Production Parity Gate

**Objective:** Compare accepted prototype screenshots and production screenshots with explicit parity score/report.

**Create:**
- `schemas/frontend-parity-report.schema.json`
- `scripts/frontend_prototype_parity_gate.py`
- `templates/frontend/prototype-parity/PARITY_REPORT.md`
- smoke fixtures for PASS, below-80, missing screenshots, unapproved deviations.

**Acceptance:** C/D final verification cannot PASS without parity report and real production screenshots or honest `contract-needed` exception accepted by human.

### Task 4: Browser Evidence Capture Harness

**Objective:** Standardize screenshot capture commands and evidence paths for arbitrary frontend projects.

**Create:** capture command templates, Playwright/browser evidence manifest, feature/verifier.

**Acceptance:** no final frontend QA PASS without concrete screenshot manifest.

### Task 5: V Workspace Adapter

**Objective:** Apply the generic chain to `/root/work/v` frontend projects as adapters, not hardcoded rules.

**Acceptance:** V frontend projects have adapter manifests, persistent rules, and one sample C/D workflow passing up to the appropriate human sign-off boundary.

## Verification discipline

Every tranche must end with:

```bash
python3 -m py_compile <changed scripts>
python3 <smoke script> --root . --format json
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root . --feature <feature> --strict-missing
python3 -m selfcheck run --root . --feature <feature> --groups static
```

Then spec review, quality/security review, QA evidence, and final verifier.
