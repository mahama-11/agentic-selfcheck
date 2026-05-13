# Frontend AI Quality System Roadmap

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task when turning roadmap phases into code slices.

**Goal:** Systematically absorb external AI frontend best practices into a reusable, project-agnostic frontend quality control plane, then apply it to concrete projects like V.

**Architecture:** Treat frontend quality as a layered system: upstream design context, prototype generation lanes, structured critique, implementation parity, and long-term visual regression. Generic controls live in Agentic SelfCheck; each product repo provides adapters for tokens, components, routes, Storybook/Playwright, and project rules.

**Tech Stack:** Agentic SelfCheck features/verifiers, Markdown templates, JSON schemas, Python gate scripts, browser screenshots, visual critique JSON, project adapters, optional Figma/v0/Lovable/Bolt/Storybook/Chromatic/Playwright.

---

## Strategic framing

External research shows AI frontend quality is not guaranteed by model taste. Mature workflows combine:

```text
reference/context
+ design system/tokens/components
+ persistent agent rules
+ multi-lane generation
+ screenshot/visual critique
+ visual regression
+ human acceptance for high-risk work
```

Our existing control plane already has:

- high-fidelity prototype gate;
- C/D risk thresholds;
- real image evidence requirement;
- structured visual critique JSON;
- scorecard materialization;
- D-risk design lanes and human sign-off requirement.

The missing long-term value layer is systematic upstream and downstream integration:

```text
Design Quality Pack before generation
+ Project Adapters around implementation
+ Visual Regression after implementation
+ Governance feedback loop after delivery
```

---

## Layered roadmap

### Layer 0: Risk classification and trigger policy

**Purpose:** Decide when heavy frontend flow applies.

**Rules:**

- A: tiny UI patch — no prototype required, screenshot required.
- B: component-level change — Storybook/component workshop preferred.
- C: page/flow-level change — high-fidelity prototype required.
- D: product-critical/brand-critical/commercially visible flow — multi-lane prototype, human sign-off, stricter score threshold.

**Deliverables:**

- `features/frontend-risk-classification.yaml`
- `templates/frontend/RISK_CLASSIFICATION.md`
- `scripts/frontend_risk_classifier.py`

---

### Layer 1: Design Quality Pack, before AI generation

**Purpose:** Prevent low-quality generation by constraining AI before it creates prototypes.

**Deliverables:**

- `templates/frontend/design-quality-pack/REFERENCE_PACK.md`
- `templates/frontend/design-quality-pack/AESTHETIC_DIRECTION.md`
- `templates/frontend/design-quality-pack/ANTI_PATTERNS.md`
- `templates/frontend/design-quality-pack/DESIGN_TOKENS_MAP.md`
- `templates/frontend/design-quality-pack/COMPONENT_INVENTORY.md`
- `templates/frontend/design-quality-pack/REFERENCE_SCREENSHOTS.md`
- `templates/frontend/design-quality-pack/PROJECT_FRONTEND_RULES.md`
- `schemas/frontend-design-quality-pack.schema.json`
- `scripts/frontend_design_quality_pack_gate.py`
- `features/frontend-design-quality-pack.yaml`

**Gate behavior:**

- C/D workflows cannot generate prototype lanes until Design Quality Pack exists.
- D workflows require at least 3 reference products/screenshots and explicit anti-patterns.
- Existing project components/tokens must be listed, or absence must be declared as `contract_needed`.

---

### Layer 2: Multi-lane AI prototype generation

**Purpose:** Raise prototype quality ceiling by making variants compete.

**Deliverables:**

- `templates/frontend/design-lanes/LANE_PROMPT_A_CONSERVATIVE.md`
- `templates/frontend/design-lanes/LANE_PROMPT_B_STRONG_FIT.md`
- `templates/frontend/design-lanes/LANE_PROMPT_C_DIVERGENT.md`
- `scripts/frontend_design_lane_orchestrator.py`
- `schemas/frontend-design-lane.schema.json`
- `features/frontend-design-lane-generation.yaml`

**Tool adapters:**

- generic HTML artifact lane;
- v0 prompt/export lane;
- Lovable prompt/knowledge lane;
- Bolt/StackBlitz lane;
- Figma/MCP lane when available;
- Storybook lane for component-first work.

**Gate behavior:**

- C: at least 1 lane; 2 recommended when taste uncertainty exists.
- D: at least 2 lanes, preferably 3.
- Each lane must produce artifact notes and screenshots.

---

### Layer 3: Structured critique and selection

**Purpose:** Make design judgment auditable.

**Existing assets:**

- `schemas/frontend-prototype-critique.schema.json`
- `scripts/frontend_visual_critic.py`
- `visual-critique.json`
- `PROTOTYPE_SCORECARD.md`

**Next deliverables:**

- `schemas/frontend-variant-comparison.schema.json`
- `scripts/frontend_variant_comparison.py`
- `templates/frontend/high-fidelity-prototype-gate/REFERENCE_COMPARISON.md`

**Gate behavior:**

- Critique must compare prototype against selected references, not only standalone quality.
- D-risk selected variant must beat alternatives or have explicit product reason to choose lower-score option.
- `REQUEST_CHANGES` / `REJECT_DIRECTION` blocks implementation.

---

### Layer 4: Prototype freeze and implementation contract

**Purpose:** Turn accepted prototype into an implementation contract.

**Existing assets:**

- `PROTOTYPE_PARITY_PLAN.md`
- `frontend_quality_gate.py`

**Next deliverables:**

- `schemas/frontend-prototype-freeze.schema.json`
- `templates/frontend/implementation-contract/PROTOTYPE_FREEZE.json`
- `templates/frontend/implementation-contract/COMPONENT_MAPPING.md`
- `templates/frontend/implementation-contract/API_STATE_MAPPING.md`
- `scripts/frontend_freeze_prototype.py`

**Gate behavior:**

- Accepted screenshots become baseline.
- Component/API/state mapping must exist before implementation.
- If implementation intentionally deviates from prototype, deviation must be documented.

---

### Layer 5: Project adapter and persistent agent rules

**Purpose:** Make generic rules usable in real repos.

**Deliverables:**

- `scripts/frontend_project_adapter_init.py`
- `templates/frontend/project-adapter/CLAUDE_FRONTEND_SECTION.md`
- `templates/frontend/project-adapter/cursor-frontend-design.mdc`
- `templates/frontend/project-adapter/PROJECT_ADAPTER.yaml`
- `features/frontend-project-adapter.yaml`

**Adapters should define:**

- repo path;
- frontend framework;
- design token files;
- component directories;
- Storybook command;
- Playwright command;
- screenshot routes;
- dev server start command;
- build/typecheck/lint commands.

**Gate behavior:**

- C/D implementation agent must load project frontend rules.
- New raw colors/components are flagged unless approved.
- Project adapter can be absent only with explicit `contract_needed`.

---

### Layer 6: Production parity and visual regression

**Purpose:** Ensure implementation matches accepted prototype.

**Deliverables:**

- `scripts/frontend_capture_screenshots.py`
- `scripts/frontend_prototype_parity_report.py`
- `schemas/frontend-parity-report.schema.json`
- `features/frontend-production-parity.yaml`

**Integrations:**

- Playwright screenshot capture;
- Storybook visual tests;
- Chromatic when available;
- browser_vision prototype-vs-production critique.

**Gate behavior:**

- Production screenshots must exist.
- Prototype-vs-production comparison must exist.
- Major visual parity issues block final verification.
- Accepted deviations must be explicit.

---

### Layer 7: Long-term governance and learning loop

**Purpose:** Turn frontend mistakes into reusable prevention.

**Deliverables:**

- `features/frontend-quality-governance.yaml`
- `scripts/frontend_quality_governance_audit.py`
- frontend pitfall category/schema extension;
- trend reports for repeated UI defects.

**Gate behavior:**

- Repeated prototype/implementation issues require prevention action:
  - rule;
  - verifier;
  - design pack update;
  - component library update;
  - accepted risk.

---

## Suggested implementation sequence

### Slice 1: Design Quality Pack Gate

**Goal:** Add upstream quality constraints before prototype generation.

**Files:**

- Create templates under `templates/frontend/design-quality-pack/`.
- Create `schemas/frontend-design-quality-pack.schema.json`.
- Create `scripts/frontend_design_quality_pack_gate.py`.
- Create `features/frontend-design-quality-pack.yaml`.
- Add verifier `verifiers/frontend-design-quality-pack-gate.yaml`.
- Update `scripts/init_frontend_workflow.py` to include design quality pack files.

**Verification:**

- good pack PASS;
- missing references FAIL;
- missing anti-patterns FAIL for D;
- `selfcheck validate` PASS;
- feature run PASS.

### Slice 2: Multi-lane Orchestrator

**Goal:** Generate standardized lane prompts and validate lane artifacts.

**Files:**

- `scripts/frontend_design_lane_orchestrator.py`
- `schemas/frontend-design-lane.schema.json`
- `features/frontend-design-lane-generation.yaml`
- lane prompt templates.

**Verification:**

- C one-lane PASS;
- D two-lane PASS;
- D one-lane FAIL.

### Slice 3: Reference-aware Visual Critic

**Goal:** Make critique compare against reference pack and anti-patterns.

**Files:**

- Extend `schemas/frontend-prototype-critique.schema.json`.
- Extend `scripts/frontend_visual_critic.py`.
- Add `REFERENCE_COMPARISON.md`.

**Verification:**

- critique missing reference comparison FAIL;
- valid reference comparison PASS.

### Slice 4: Project Adapter Generator

**Goal:** Make rules portable to V and future frontend repos.

**Files:**

- `scripts/frontend_project_adapter_init.py`
- project adapter templates.
- `features/frontend-project-adapter.yaml`

**Verification:**

- generated adapter has commands/rules;
- missing project token/component declaration FAIL unless contract_needed.

### Slice 5: Prototype-to-Production Parity

**Goal:** Capture production screenshots and compare against frozen prototype.

**Files:**

- `scripts/frontend_capture_screenshots.py`
- `scripts/frontend_prototype_parity_report.py`
- `schemas/frontend-parity-report.schema.json`
- `features/frontend-production-parity.yaml`

**Verification:**

- missing production screenshot FAIL;
- comparison report PASS;
- severe parity finding FAIL.

### Slice 6: V Adapter Application

**Goal:** Apply generic frontend quality system to V as first concrete adapter.

**Files:**

- V project adapter config under Agentic SelfCheck.
- V frontend rules for platform/ecommerce/menu/kyc frontend.
- Playwright/browser screenshot commands per repo.

**Verification:**

- V C/D sample workflow initialized;
- design quality pack PASS;
- prototype gate PASS;
- production parity gate dry-run PASS or contract_needed.

---

## Success criteria

The system is successful when a new C/D frontend request can run through:

```text
risk classify
-> design quality pack
-> design lanes
-> visual critique
-> accepted prototype
-> frozen baseline
-> project adapter implementation
-> production screenshots
-> parity report
-> final verification
```

and low-quality work fails early with actionable findings.

---

## Key principle

The goal is not to copy v0/Lovable/Figma/Chromatic wholesale. The goal is to absorb their durable mechanisms into our control plane:

```text
context before generation
systems before style
variants before commitment
screenshots before acceptance
structured critique before implementation
baseline before production parity
pitfalls before repeated waste
```
