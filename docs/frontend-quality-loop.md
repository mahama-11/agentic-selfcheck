# Generic Frontend Quality Loop

## Purpose

This is a project-agnostic frontend delivery process for any frontend project where visual quality, interaction quality, product comprehension, and implementation reliability matter.

It generalizes the lessons from V/ECOM but is not V-specific. V is only the first concrete application.

## Core thesis

Complex frontend work should not go directly from requirement to production implementation.

The default loop should be:

```text
Product / UX brief
-> High-fidelity prototype or Storybook/component workshop
-> Visual / interaction acceptance
-> Production implementation
-> Prototype parity review
-> Runtime / API / accessibility verification
-> Visual regression baseline
-> Final verification
```

This avoids the expensive failed loop:

```text
requirement
-> agent writes production React directly
-> build/typecheck passes
-> user dislikes visual/UX
-> patch loop
-> cost explodes
```

## Two classes of frontend quality

### 1. System consistency quality

This is about standardization:

- design tokens;
- typography scale;
- color system;
- spacing/radius/shadow system;
- component reuse;
- accessibility baseline;
- responsive rules;
- Storybook/component states;
- visual regression;
- no ad-hoc raw styles;
- no duplicate UI primitives.

This answers:

```text
Does the frontend fit the project's design system and engineering standards?
```

### 2. Product experience quality

This is about whether the result actually feels good and makes sense:

- page information architecture;
- visual hierarchy;
- first-screen story;
- route choreography;
- interaction model;
- task flow clarity;
- density and rhythm;
- empty/loading/error states;
- motion and transition semantics;
- whether the user immediately understands what to do next.

This answers:

```text
Even if the UI is consistent and functional, is it pleasant, clear, and convincing?
```

The second class cannot be solved by lint/build/typecheck. It needs a design gate.

## Recommended process

### Gate 0: classify the frontend work

Classify each frontend task:

```text
A. tiny UI patch
B. component-level change
C. page/flow change
D. product-critical or commercial-facing redesign
E. new product surface
```

Rules:

- A can go directly to implementation with screenshot evidence.
- B should use component/story evidence where available.
- C requires UX brief + state matrix + browser screenshots.
- D/E require high-fidelity prototype or design-only lane before production code.

### Gate 1: product / UX brief

Before coding, produce:

```text
DESIGN_BRIEF.md
INTERACTION_MODEL.md
STATE_MATRIX.md
VISUAL_ACCEPTANCE_CHECKLIST.md
```

Must specify:

- target user and task;
- route/page IA;
- primary and secondary actions;
- data source per region;
- state machine/status vocabulary;
- empty/loading/error/permission/mobile states;
- visual direction;
- reference patterns;
- what must be preserved if implementation differs;
- what is explicitly forbidden.

### Gate 2: high-fidelity prototype / design-only phase

For page/flow/product-critical work, build a high-fidelity prototype before production implementation.

Prototype can be:

```text
self-contained HTML
Figma prototype
Storybook page/component composition
local design artifact
```
Prototype requirements:

```text
- show real route/page structure, not just one hero screen;
- include main interactions: drawers, modals, tabs, hover/selected states, command/search if relevant;
- cover critical states;
- use realistic data shape;
- be visually close enough that the user can judge taste and interaction;
- avoid fake product claims or fake backend capabilities.
```

Completeness mechanism:

```text
PROTOTYPE_COVERAGE.md is mandatory. It maps every required route/surface and core interaction to a prototype artifact and screenshot. The frontend quality gate fails if this matrix is missing, still contains placeholders, or marks core coverage as missing/blocked.
```

The prototype is not throwaway decoration. It is the visual contract.
### Gate 3: user / design acceptance

The user or design reviewer accepts one of:

```text
ACCEPTED
ACCEPTED_WITH_NOTES
REQUEST_CHANGES
REJECTED_DIRECTION
```

If REQUEST_CHANGES/REJECTED_DIRECTION, do not start production implementation. Iterate prototype first.

### Gate 4: implementation plan from prototype

After prototype acceptance, produce a parity plan:

```text
PROTOTYPE_PARITY_PLAN.md
```

It must map:

```text
prototype route -> production route
prototype component -> existing/new production component
prototype interaction -> production state/API
prototype token/style -> design system token
prototype fake data -> real API or contract-needed
accepted compromise -> explicit note
```

### Gate 5: production implementation

Now implement in the real project.

Rules:

- reuse existing components/tokens first;
- create new components only with justification;
- preserve accepted visual hierarchy and route choreography;
- wire real APIs where available;
- mark missing backend as `contract-needed` honestly;
- do not reinterpret the accepted prototype into a visually different existing admin shell.

### Gate 6: prototype parity review

Before PR/final review, compare implementation against accepted prototype.

Evidence:

```text
prototype screenshots
production screenshots
route-by-route parity checklist
known deviations
```

Suggested threshold:

```text
80%+ visual/interaction parity for complex work
```

The remaining 20% must be explained by real production constraints, not developer convenience.

### Gate 7: runtime verification

Run:

```text
typecheck / build / lint
Storybook build or component workshop check if present
Playwright route/flow smoke
console/network error check
accessibility smoke
real backend/API check where applicable
```

### Gate 8: visual regression baseline

Add or refresh baseline evidence:

```text
Storybook/Chromatic if available
Playwright screenshot baseline fallback
before/after screenshots for affected routes
```

### Gate 9: final verification

Final verifier cannot pass product-critical frontend work without:

```text
brief + interaction model + state matrix
accepted prototype or story/component evidence
prototype parity evidence
production screenshots
runtime/browser/API evidence
known deviations list
```

## When to use high-fidelity prototypes

Use high-fidelity prototype first when:

- user taste/visual acceptance matters;
- previous implementation suffered rework;
- page is commercial/public-facing;
- route/IA is changing;
- interaction model is non-trivial;
- feature spans multiple pages/states;
- agents have low design confidence;
- user says current output is rough, awkward, generic, or only a small tweak.

Do not overuse for tiny fixes:

- typo;
- one button state;
- simple spacing bug;
- accessibility label;
- obvious responsive overflow.

## Mainstream fit

This process matches mainstream high-quality frontend practice:

- design/prototype before engineering for high-impact UI;
- component-driven development through Storybook;
- design tokens and design systems;
- visual regression with Chromatic or screenshot baselines;
- Playwright for integrated flows;
- Figma Dev Mode / Code Connect where Figma is the source;
- human visual approval for important diffs.

The AI-specific adaptation is stricter:

```text
AI agents must not decide visual taste implicitly inside production code.
They should produce reviewable visual artifacts first, then implement the accepted artifact with parity evidence.
```

## Portable workflow template

For any future frontend request, start with:

```text
1. Classify frontend risk level with `scripts/frontend_risk_router.py`.
2. If C/D/E: create design brief + high-fidelity prototype before production code.
3. Get visual/interaction acceptance.
4. Implement accepted direction in real project.
5. Run parity review + runtime verification.
6. Final verification requires visual evidence, not just build evidence.
```

## Concrete artifacts to standardize in SelfCheck

Future generic SelfCheck features:

```text
frontend-design-quality-pack
frontend-design-lane-generation
frontend-risk-routing
frontend-prototype-gate
frontend-prototype-parity-gate
frontend-runtime-visual-qa
frontend-visual-regression-baseline
```

Future generic scripts:

```text
scripts/frontend_design_intake_check.py
scripts/frontend_prototype_evidence_check.py
scripts/frontend_parity_check.py
scripts/frontend_visual_evidence_check.py
```

Future project adapters then map these generic gates to concrete projects such as V, Ecommerce, Menu, KYC, or any non-V frontend.


## Prototype quality hardening: not a single-agent MVP

The baseline path `AI agent -> standalone HTML -> screenshot` is useful as a portable fallback, but it must not be the default ceiling for C/D frontend work.

For production-quality frontend work, the prototype stage must be treated as an engineered design process:

```text
Context Pack
-> Independent Design Lanes
-> Design Critic Review
-> Prototype Quality Rubric
-> Variant Comparison
-> Human Acceptance Boundary
-> Frozen Prototype Contract
-> Production Parity Plan
```

### Required prototype quality gates

C-risk frontend work requires:

- complete context pack;
- at least one high-fidelity prototype;
- explicit visual/interaction critique;
- quality scorecard;
- screenshot evidence;
- accepted or accepted-with-notes decision.

D-risk frontend work requires:

- complete context pack;
- at least two independent design lanes or tool outputs;
- variant comparison;
- design critic review;
- quality scorecard;
- human sign-off;
- screenshot evidence for selected direction;
- explicit rejection notes for discarded variants.

### Recommended design lane sources

Use the strongest available tool per project:

```text
Figma / Figma Dev Mode / Figma MCP
v0
Lovable
Bolt / StackBlitz
Claude Artifacts / standalone HTML
Storybook component workshop
Existing product screenshots and design tokens
```

A standalone HTML prototype is acceptable only when it passes the same rubric and evidence rules. It is not automatically sufficient just because it exists.

### Prototype quality rubric

Score each prototype from 1-5 on:

1. product comprehension;
2. information architecture;
3. visual hierarchy;
4. interaction clarity;
5. state coverage;
6. design-system fit;
7. feasibility against real APIs/components;
8. accessibility/responsiveness baseline;
9. distinctiveness / non-generic quality;
10. implementation parity readiness.

Suggested thresholds:

```text
C-risk: average >= 3.8 and no dimension below 3
D-risk: average >= 4.2 and no dimension below 3.5, plus human sign-off
```

If the prototype fails the rubric, do not enter production implementation. Iterate prototype or restart design lanes.

### Anti-low-quality rules

Reject prototypes that are:

- generic admin card/table layouts with no product-specific IA;
- only color/theme changes over existing UI;
- one-screen fake tabs without route/state coverage;
- visually attractive but impossible to implement with real data;
- missing empty/loading/error/permission states for relevant flows;
- disconnected from project tokens/components;
- accepted only because build/code would be easier.
