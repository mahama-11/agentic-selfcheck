# V Frontend Quality Loop: First Concrete Application

## Context

The generic frontend quality process now lives at:

```text
docs/frontend-quality-loop.md
```

This document is the V workspace adapter/application of that generic process.

The previous ECOM frontend iteration produced repeated rework, high token/time cost, and weak confidence in visual/product quality. The root issue was not only implementation skill. It was the lack of a frontend-specific control loop before production React integration.

## External research anchors

- Storybook: frontend workshop for building UI components/pages in isolation — https://storybook.js.org/docs
- Component Driven UI: bottom-up component/screen development — https://www.componentdriven.org/
- Chromatic CDD / visual review — https://www.chromatic.com/blog/component-driven-development/
- Chromatic docs / CI / TurboSnap / Playwright integration — https://www.chromatic.com/docs/ , https://www.chromatic.com/docs/ci , https://www.chromatic.com/docs/turbosnap/ , https://www.chromatic.com/docs/playwright
- Playwright: browser E2E and visual snapshots — https://playwright.dev/docs/intro , https://playwright.dev/docs/test-snapshots
- Design Tokens Community Group format — https://tr.designtokens.org/format/
- Style Dictionary token pipeline — https://styledictionary.com/info/tokens/ , https://github.com/style-dictionary/style-dictionary
- Figma Code Connect / Dev Mode / variables — https://developers.figma.com/docs/code-connect/ , https://help.figma.com/hc/en-us/articles/15023202277399-Use-code-snippets-in-Dev-Mode , https://developers.figma.com/docs/rest-api/variables/
- GitHub Copilot custom instructions — https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot
- Claude Code memory/hooks — https://docs.anthropic.com/en/docs/claude-code/memory , https://docs.anthropic.com/en/docs/claude-code/hooks
- Cursor rules/context — https://docs.cursor.com/context/rules
- Chromatic AI frontend workflow — https://www.chromatic.com/frontend-workflow-for-ai/

## Diagnosis for V / ECOM frontend rework

The failed pattern:

```text
requirement -> agent writes React directly -> typecheck/build -> screenshot late -> user rejects visual/interaction -> patch loop -> review fatigue/cost
```

Why it fails:

1. design intent is not executable;
2. component reuse is not enforced;
3. agents optimize for compiling, not product feeling;
4. visual evidence arrives too late;
5. no stable visual baseline exists;
6. no component/page state matrix exists;
7. final verification sees code/test evidence, not design acceptance evidence.

## Target pattern

For complex frontend work, use this loop:

```text
Design Intake
-> Reuse/Token Discovery
-> Design-only Prototype / Storybook-first Component States
-> Visual Gate
-> Real React Integration
-> Browser + Playwright Runtime Gate
-> Visual Regression / Screenshot Evidence
-> PR / Final Verification
```

## Required gates

### 1. Design intake gate

Before implementation, produce:

```text
DESIGN_BRIEF.md
INTERACTION_MODEL.md
STATE_MATRIX.md
VISUAL_ACCEPTANCE_CHECKLIST.md
```

Must define:

- target users/tasks;
- route/page IA;
- user journey;
- required states: loading/empty/error/permission/long-text/mobile;
- visual direction;
- existing components to reuse;
- forbidden operations and no-fake-capability areas;
- API/data source per region;
- visual acceptance threshold.

### 2. Reuse/token discovery gate

Before creating new UI primitives:

```text
search existing components
search existing route/page patterns
search design tokens/theme files
search Storybook stories if present
```

Agent must answer:

```text
reuse / extend / create-new
```

Creating new primitives requires justification.

### 3. Storybook/component workshop gate

For reusable UI or critical page regions:

- add/modify Storybook stories;
- include main states;
- use deterministic data;
- cover desktop/tablet/mobile where relevant;
- capture screenshots.

If Storybook does not exist yet in a V frontend, the first engineering slice should add a minimal Storybook harness instead of letting major UI work proceed directly in route files.

### 4. Visual regression gate

Preferred:

```text
Chromatic + Storybook
```

Fallback when external service not yet configured:

```text
Playwright screenshot baselines under repo-controlled evidence directory
```

Rule:

```text
Any important UI change must produce before/after or baseline/current screenshots.
```

### 5. Integrated browser gate

After visual gate passes, integrate into real app and run:

```text
typecheck
build
browser route smoke
Playwright critical flow
console/network error check
real backend/API where available
```

For V workspace, mocks are not default. If a contract is missing, label `contract-needed` explicitly.

### 6. Final verification gate

Final verifier cannot PASS a complex frontend slice unless it sees:

```text
DESIGN_BRIEF / state matrix
component/story evidence or prototype evidence
visual screenshots
browser runtime evidence
real API / honest contract-needed evidence
user-visible review URL or screenshot package
```

## How this fits SelfCheck/Hermes

Add frontend-specific features/verifiers:

```text
features/v-frontend-design-intake.yaml
features/v-frontend-storybook-visual-gate.yaml
features/v-frontend-runtime-visual-qa.yaml
features/v-frontend-regression-baseline.yaml
```

Add events:

```text
v.frontend.changed.design
v.frontend.changed.component
v.frontend.changed.route
v.frontend.visual-review.requested
```

Add scripts:

```text
scripts/v_frontend_design_intake_check.py
scripts/v_frontend_component_inventory.py
scripts/v_frontend_visual_evidence_check.py
scripts/v_frontend_runtime_smoke.py
```

## Operating policy

For complex V frontend work:

1. If visual direction is not accepted, do not start production React implementation.
2. If route/page is product-critical, require design-only prototype or Storybook workshop first.
3. If implementation exists but visual evidence is missing, report `BLOCKED_BY_VISUAL_EVIDENCE`, not PASS.
4. If user rejects look/feel, return to design gate, not patch-loop blindly.
5. If agent changes UI without screenshot evidence, governance should flag it.

## First production slice to land next

`v-frontend-quality-loop`

Deliver:

1. SelfCheck feature contracts and verifiers for frontend visual gates.
2. Ecommerce frontend Storybook readiness audit.
3. Playwright screenshot capture baseline for current Product Center/Pricing/Home critical routes.
4. Workflow template for future frontend slices.
5. Final verifier rule: frontend slices need visual evidence package.

This is the direct response to the ECOM frontend rework problem.
