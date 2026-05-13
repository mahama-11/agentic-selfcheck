# Harness Articles Integration into Agentic SelfCheck

## Scope

This document integrates three WeChat articles the user shared into the existing Hermes / Agentic SelfCheck / V workspace engineering system.

The three articles are:

1. **Harness 工程可视化：在 Vibe Coding 中重建工程可控性**
   - Focus: Routa Desktop Harness visualization, lifecycle view, distributed governance objects, feedback loops, Review Trigger, Fitness.
2. **Harness Engineering：耗时一周，我是如何将应用的 AI Coding 率提升至 90% 的**
   - Focus: `.harness/` physical asset layout, Application Owner Agent, rules/skills/wiki/changes, ten-stage execution, phase-triggered skills, machine quality gates.
3. **Harness Engineering：AI 能在真正“出事会炸”的后端系统里写代码吗？**
   - Focus: high-risk backend AI coding, strict context/constraint/feedback, anti-hallucination, pitfall journal, rule/skill evolution, task blocking, adversarial multi-model CR.

## Decision

Do **not** create a new Harness system.

Agentic SelfCheck is already the reusable control plane:

```text
product invariants → capability contracts → feature acceptance → verifiers → evidence → gates → loops/hooks → repair → final verification
```

Harness becomes the readable, enforceable, and evolvable layer on top of this system:

```text
SelfCheck object model = source of truth
Harness View          = graph/projection/report of the source of truth
Harness Assets        = reusable rules, skills, templates, pitfall patterns, phase workflows
Feishu Ledger         = human-readable status projection, not a second source of truth
```

## What Each Article Contributes

### Article 1: Visualization and System Readability

Use this article to improve **visibility**.

It answers:

```text
Where are the rules?
Which gates are actually connected to delivery?
Which feedback loops exist?
Which paths are uncovered?
Can humans read the engineering system, not just files?
```

Mapping to our system:

```text
Routa Lifecycle       → selfcheck harness feature graph
Spec / ADR / Hooks    → features / capabilities / verifiers / project assets
Review Trigger        → verifier groups + reviewer_gates + dispatch owner rules
Fitness               → inventory + evidence coverage + verifier health score
Feedback              → events / loops / reports / dispatch artifacts
```

Required landing:

```bash
python3 -m selfcheck harness --root . --feature <feature-id> --format markdown
python3 -m selfcheck harness --root . --feature <feature-id> --format json
```

The output must show:

```text
feature → project → capabilities → verifier groups → verifier commands → evidence files → role gates → events/loops → repair policy → latest reports
```

### Article 2: Reusable Harness Assets and Phase Workflow

Use this article to improve **repeatable execution**.

It contributes these concrete assets:

```text
.harness/agents     → Hermes profiles / role prompts / long-lived role definitions
.harness/rules      → AGENTS.md + SelfCheck invariants + review rules
.harness/skills     → Hermes skills and project-local procedural skills
.harness/changes    → .hermes/workflows/<feature>/ evidence folders
.harness/wiki       → project knowledge base / domain glossary / references
phase workflow      → feature acceptance + role gates + evidence_required
machine gates       → verifiers with command-level pass/fail criteria
```

Key principle from the article:

```text
Context is tiered:
L1 Always Loaded     = agent charter, rules, stable project constraints
L2 Phase-triggered   = skills loaded for request analysis, coding, unit test, CI, deploy, review
L3 On-demand         = wiki/domain docs/references loaded only when needed
```

Mapping to our system:

```text
L1 → AGENTS.md, root project adapter, invariants/*.yaml, durable memories
L2 → Hermes skills selected by role/stage, SelfCheck reviewer_gates
L3 → docs, wiki, references, code search, domain files, runtime evidence
```

Required landing:

- Normalize `.hermes/workflows/<feature>/` as our equivalent of `.harness/changes/<change>/`.
- Require every non-trivial feature to have phase evidence files:

```text
01-requirement.md
02-architecture-review.md
03-implementation-plan.md
04-implementation-report.md
05-spec-review-report.md
06-quality-review-report.md
07-qa-report.md
08-final-verification.md
09-harness-report.md
```

- Make `evidence-gate` check these files for existence and, later, freshness/content markers.

### Article 3: Hard Constraints, Pitfall Evolution, and Adversarial Review

Use this article to improve **safety and quality in high-risk engineering**.

It contributes these concrete rules:

```text
Vague expectations are weak.
Executable constraints are strong.
Pitfalls must evolve into rules and skills.
High-risk backend work needs adversarial review, not single-model confidence.
Tasks must have blocking relationships; tests/reviews cannot be skipped.
```

Mapping to our system:

```text
Anti-hallucination       → verifiers requiring source evidence / runtime evidence
Strict search scope      → project adapter allowed paths + role instructions
Task blocking            → feature stage state + reviewer_gates + evidence-gate
Pitfall journal          → docs/pitfalls/*.md or SelfCheck pitfall registry
Pitfall → Rule → Skill   → update invariants/verifiers/Hermes skills after failures
Adversarial CR           → spec-reviewer + quality-reviewer + final-verifier, optionally multi-model
```

Required landing:

- Add a pitfall feedback loop:

```text
failure observed
→ record pitfall with evidence
→ classify root cause
→ update rule/verifier/skill
→ rerun affected feature
→ final verifier confirms recurrence is prevented
```

- For high-risk V backend/product work, mark features with risk dimensions:

```text
security
billing/quota/metering
auth/RBAC
runtime callback
data migration
asset/storage
public API contract
cross-service boundary
```

- Use those dimensions to route review and verifier requirements.

## Current State: What We Already Have

Agentic SelfCheck already has most of the control-plane primitives:

```text
schemas/             JSON schemas for control objects
invariants/          stable engineering/product truths
capabilities/        reusable capability contracts
projects/            project adapters and commands
features/            feature acceptance contracts
verifiers/           executable/static/manual gates
loops/               recurring/event feedback loops
events/              trigger routes
repair-policies/     bounded repair policy
role-model-routing/  role/model routing rules
reports/             verifier evidence
.hermes/workflows/   role handoff evidence
.hermes/dispatch/    repair dispatch artifacts
```

The current concrete sample is:

```text
Feature: features/ecommerce-product-ai-pipeline.yaml
Project: projects/v-ecommerce-worktree.yaml
Capabilities: frontend-runtime, ai-generation, review-gates
Machine gates: frontend-typecheck, frontend-build, api-readiness-smoke, browser-login-surface-smoke, evidence-gate
Role gates: architect, spec-review, quality-review, qa, final-verification
Gate script: scripts/v-requirement-gate.sh ecommerce-product-ai-pipeline static,api,browser,evidence requirement.changed.v.ecommerce-product-ai-pipeline
```

Validation currently passes:

```bash
python3 -m selfcheck validate --root .
```

## Current Gaps

### Gap 1: Readable Harness View Missing

The system can plan/run/audit, but humans cannot yet see the entire control graph in one report.

Landing target:

```bash
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format markdown
```

### Gap 2: Enforced vs Documented Rules Not Explicit

The report must label each item:

```text
ENFORCED_MACHINE_GATE   appears in must_pass and has executable verifier
ROLE_GATE               required reviewer/QA/final verifier handoff
HUMAN_BOUNDARY          declared human_required decision
EVIDENCE_REQUIRED       declared evidence file/report
DOCUMENTED_ONLY         known rule but not connected to a gate
MISSING_OR_STALE        required but absent/stale evidence
```

### Gap 3: `.hermes/workflows` Is Not Yet Treated as a Formal Change Folder

We have role evidence files, but the flow should explicitly treat them as the durable change/audit folder equivalent to `.harness/changes`.

Landing target:

```text
.hermes/workflows/<feature>/
├── 01-requirement.md
├── 02-architecture-review.md
├── 03-implementation-plan.md
├── 04-implementation-report.md
├── 05-spec-review-report.md
├── 06-quality-review-report.md
├── 07-qa-report.md
├── 08-final-verification.md
└── 09-harness-report.md
```

### Gap 4: Pitfall → Rule → Skill Loop Is Not Formalized

We patch issues, but recurrence-prevention is not yet a required SelfCheck artifact.

Landing target:

```text
.hermes/workflows/<feature>/pitfalls.md
or
pitfalls/<pitfall-id>.yaml
```

Each pitfall should record:

```text
symptom
evidence
root cause
preventive rule
updated verifier/skill/doc
rerun evidence
```

### Gap 5: Feishu Ledger Is Not Yet a Full SelfCheck Projection

The ledger should not be a separate control system. It should show the SelfCheck/Harness state:

```text
feature id
current status
failed verifier group
latest evidence path/report
repair owner
human boundary required
next action
final verification status
```

## Integrated Flow for Non-Trivial V Work

The flow should become:

```text
需求进入
→ create/update feature acceptance contract
→ isolated branch/worktree implementation
→ phase workflow folder under .hermes/workflows/<feature>/
→ architect/developer/spec-review/quality-review/QA/final-verifier produce evidence
→ SelfCheck run/loop executes machine gates
→ Harness report renders control graph and evidence coverage
→ Feishu ledger projects status and next action
→ repair dispatch if failing
→ pitfall recorded if recurrence-prevention is needed
→ rule/verifier/skill updated
→ rerun SelfCheck
→ final verification cites Harness report + raw evidence
```

## Implementation Roadmap

### Slice 1: `selfcheck harness` Renderer

Files:

```text
selfcheck/__main__.py
reports/<feature>/harness.json
reports/<feature>/harness.md
```

Acceptance:

- Reads feature/project/capability/verifier/event/loop/repair policy objects.
- Emits markdown and JSON.
- Labels enforced machine gates, role gates, human boundaries, required evidence, missing evidence.
- Does not introduce a new DB or separate source of truth.

### Slice 2: Formal Workflow Folder Template

Files:

```text
selfcheck/__main__.py
schemas/feature.schema.json          # only if evidence defaults need schema support
```

Command target:

```bash
python3 -m selfcheck init-workflow --root . --feature <feature-id>
```

Acceptance:

- Creates missing `.hermes/workflows/<feature>/` files from template.
- Does not overwrite existing evidence.
- `evidence-gate` can audit the folder.

### Slice 3: Pitfall Feedback Loop

Files:

```text
schemas/pitfall.schema.json
pitfalls/*.yaml
selfcheck/__main__.py
verifiers/pitfall-feedback-gate.yaml
```

Acceptance:

- A failed gate can be linked to a pitfall record.
- Pitfall record must cite prevention action: rule, verifier, skill, doc, or explicit accepted risk.
- Final verification fails or downgrades if repeated pitfall has no prevention action.

### Slice 4: Risk-Based Review Trigger

Files:

```text
schemas/feature.schema.json
features/*.yaml
role-model-routing/default-role-model-routing.yaml
verifiers/review-trigger-gate.yaml
```

Acceptance:

- Features can declare risk dimensions.
- Risk dimensions require specific reviewer/verifier groups.
- Sensitive contract/governance/security/billing/runtime changes cannot pass with only generic review.

### Slice 5: Feishu Ledger Projection

Files:

```text
/root/.hermes/scripts/state_ledger.py
/root/.hermes/scripts/state_ledger_* 
features/ai-state-ledger-closed-loop.yaml
scripts/state_ledger_health_harness.py
```

Acceptance:

- Ledger shows SelfCheck feature state without requiring session IDs.
- Ledger row links to latest harness report and raw evidence.
- Health verifier confirms natural-language task resolution still points to human-readable TASK/LEDGER records.

## Where to Put the Three Article Lessons

### In Agentic SelfCheck

Put durable governance and verification here:

```text
feature contracts
capabilities
verifiers
risk dimensions
harness renderer
pitfall registry
repair loop
workflow evidence gate
```

### In Hermes Skills / Profiles

Put procedural know-how here:

```text
wechat article extraction
role-specific execution playbooks
pitfall-derived procedures
review checklists
high-risk backend constraints
```

### In V Workspace Docs

Put project-specific boundaries and runtime contracts here:

```text
AGENTS.md
REAL_RUNTIME_CONTRACT_QA.md
AGENTIC_SELFCHECK_INTEGRATION.md
subproject AGENTS/docs
```

### In Feishu Ledger

Put human status projection here:

```text
current feature state
failed gate
repair owner
next action
human decision required
latest harness/evidence links
```

## Non-Goals

- Do not build a separate Routa clone first.
- Do not create a second source of truth for specs/gates/evidence.
- Do not make visual cards that imply unenforced control.
- Do not replace role review or final verification with visualization.
- Do not turn every project-specific lesson into global memory; reusable procedures become skills, project facts stay in project docs/SelfCheck.

## Immediate Implementation Status

Slice 1 has landed as a first readable projection of the existing SelfCheck control graph:

```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format markdown
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format json
python3 -m selfcheck init-workflow --root . --feature <feature-id>
```

Generated outputs:

```text
reports/<feature>/harness.json
reports/<feature>/harness.md
.hermes/workflows/<feature>/09-harness-report.md   # populated when the workflow folder exists
```

The report currently labels:

```text
ENFORCED_MACHINE_GATE
ROLE_GATE
HUMAN_BOUNDARY
EVIDENCE_REQUIRED
MISSING_OR_STALE
```

Next implementation slices:

```text
1. Pitfall feedback loop: pitfall schema + registry + verifier + recurrence-prevention gate.
2. Risk-based review trigger: feature risk dimensions route required reviewers/verifiers.
3. Feishu ledger projection: show Harness/SelfCheck status and latest evidence link as human-readable status, not as a second truth source.
```
