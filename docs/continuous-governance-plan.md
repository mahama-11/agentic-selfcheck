# Continuous Governance Plan for Projects and Hermes/SelfCheck

## Goal

Build a durable governance loop that continuously maintains:

1. project stability and cleanliness;
2. documentation freshness and standardization;
3. codebase redundancy / dead-code control;
4. Hermes / Agentic SelfCheck output quality;
5. skill library standardization and pitfall reuse.

This is not a notification-only cron system. Each loop must classify findings, auto-fix safe issues, create evidence, and escalate only when a human decision is truly required.

## Two governance planes

### Plane A: Project Governance

Applies to concrete projects such as `/root/work/v/platform-backend`, `/root/work/v/ecommerce-*`, and later other V workspace projects.

Questions it should answer regularly:

```text
Are docs still accurate against code and runtime behavior?
Are docs written in the expected standard structure?
Are old assumptions, TODOs, stale endpoints, fake examples, or obsolete commands still present?
Is code accumulating dead modules, pass-through wrappers, duplicated logic, unused exports, abandoned fixtures, or generated garbage?
Are there shallow modules that reduce AI navigability and human locality?
Are tests/verifiers still covering the real runtime path?
```

### Plane B: Self Governance

Applies to Hermes / Agentic SelfCheck / skills / workflow reports / Feishu state ledger projection.

Questions it should answer regularly:

```text
Are Hermes-generated docs multiplying without becoming useful evidence?
Are workflow folders complete, fresh, and linked to Harness reports?
Are skills duplicated, stale, over-broad, or missing pitfalls discovered during work?
Are recurring failures being converted into rules/verifiers/skills?
Is Feishu ledger still human-first, or drifting back into AI session noise?
Are SelfCheck verifiers and Harness reports themselves still accurate?
```

## Core object model

Add governance as first-class SelfCheck features, not as loose cron prompts.

```text
features/project-doc-governance.yaml
features/project-code-health-governance.yaml
features/hermes-self-governance.yaml
features/skill-library-governance.yaml
features/pitfall-feedback-loop.yaml
```

Each feature should have:

```text
must_pass groups        static / docs / code-health / evidence / harness
reviewer_gates         spec-review + quality-review + final-verification for policy changes
human_required         destructive cleanup, broad refactor, skill deletion, accepted risk
evidence_required      reports + proposed patch summary + affected paths
repair_policy          safe auto-fix only, bounded attempts, no destructive deletion without approval
```

## Governance loops

### 1. Project Doc Governance Loop

Frequency:

```text
weekly per active project
on-demand when a feature touches public APIs, architecture, deployment, pricing/billing, auth/RBAC, or runtime contracts
```

Checks:

```text
- README / docs command freshness against package scripts, Makefile, deploy scripts, and actual service ports.
- API docs vs route definitions/OpenAPI/handler names.
- Architecture docs vs current modules and DB migrations.
- Workflow docs vs current SelfCheck feature contracts and verifiers.
- Stale TODO/FIXME/temporary wording older than threshold.
- Docs that claim PASS/success without linked evidence.
```

Outputs:

```text
reports/<project>-doc-governance/doc-freshness.json
reports/<project>-doc-governance/doc-freshness.md
.hermes/workflows/<project>-doc-governance/01-summary.md
```

Auto-fix policy:

```text
Allowed: update generated command lists, fix dead links, replace stale report links, normalize headings.
Needs human: remove product commitments, change architecture decisions, delete docs, rewrite public contract claims.
```

### 2. Project Code Health Governance Loop

Frequency:

```text
weekly for active projects
monthly for inactive projects
on-demand after large AI-generated changes
```

Checks:

```text
- unused exports/imports where language tooling supports it;
- duplicated files/functions and near-identical helper logic;
- dead routes/pages not referenced by router/menu/tests;
- orphaned fixtures/seeds/assets;
- pass-through modules that fail the deletion test;
- high-churn files with low/no tests;
- generated garbage: temp files, stale screenshots, old reports in source tree;
- code smells that reduce AI navigability: giant files, ambiguous naming, hidden global state.
```

Outputs:

```text
reports/<project>-code-health/code-health.json
reports/<project>-code-health/code-health.md
```

Auto-fix policy:

```text
Allowed: remove clearly unused generated temp files outside source, format/lint safe fixes, delete unreachable local reports if ignored.
Needs human: delete source modules, change interfaces, broad refactor, DB/schema migration, behavior-affecting cleanup.
```

### 3. Hermes Output Governance Loop

Frequency:

```text
weekly
plus after long autonomous engineering runs
```

Checks:

```text
- .hermes/workflows folders have required phase files or clearly state why not.
- 09-harness-report.md exists and matches current SelfCheck object graph.
- generated docs have owner/status/evidence, not vague self-praise.
- reports are not duplicating large raw logs without summaries.
- Feishu state ledger contains human task mainlines, not cron/delegate/selfcheck noise.
- obsolete local cron outputs/session artifacts are summarized/archived, not promoted to product docs.
```

Outputs:

```text
reports/hermes-self-governance/output-governance.json
reports/hermes-self-governance/output-governance.md
```

Auto-fix policy:

```text
Allowed: regenerate Harness reports, initialize missing workflow placeholders, archive duplicate generated docs, clean Feishu non-human ledger rows according to policy.
Needs human: delete historical evidence, remove skills, change governance policy.
```

### 4. Skill Library Governance Loop

Frequency:

```text
weekly lightweight scan
monthly deeper standardization review
after every complex task that discovered a reusable workflow or skill gap
```

Checks:

```text
- duplicate skills with overlapping trigger conditions;
- skills missing trigger / steps / pitfalls / verification sections;
- skills that reference stale commands or obsolete project paths;
- overly broad skills that pollute unrelated sessions;
- pitfalls in workflow reports that have not been converted into skill patches;
- pinned or external skills requiring manual review before edits.
```

Outputs:

```text
reports/skill-library-governance/skill-health.json
reports/skill-library-governance/skill-health.md
```

Auto-fix policy:

```text
Allowed: patch local unpinned skills with missing pitfalls or corrected commands after verified evidence.
Needs human: delete skill, merge skills, change pinned skills, install external skills.
```

### 5. Pitfall Feedback Loop

Frequency:

```text
triggered by final-verifier FAIL/PASS_WITH_NOTES, repeated repair, user correction, or production-like incident
```

Record schema:

```text
pitfall_id
scope: project | hermes | skill | verifier | docs
symptom
evidence_path
root_cause
prevention_action: rule | verifier | skill | doc | accepted_risk
updated_artifact
rerun_evidence
status: open | prevented | accepted_risk | obsolete
```

Rule:

```text
Repeated pitfall + no prevention action => governance gate should fail or downgrade final verification.
```

## Reporting contract

Each loop should produce a compact Chinese report:

```text
状态：PASS / PASS_WITH_NOTES / NEEDS_REPAIR / NEEDS_HUMAN
范围：project/system/skills
发现：top 3 only
已自动处理：safe fixes only
需要郭凯决策：only if destructive/product/policy decision is needed
证据：report path + harness path
下一步：owner + action
```

If everything is clean and no user decision is needed, cron returns `[SILENT]`.

## Landing roadmap

### Slice 1: Governance feature contracts and report shape

Create SelfCheck feature contracts and placeholder verifiers for:

```text
project-doc-governance
project-code-health-governance
hermes-self-governance
skill-library-governance
pitfall-feedback-loop
```

Acceptance:

```text
python3 -m selfcheck validate --root .
python3 -m selfcheck harness --root . --feature hermes-self-governance --format markdown
```

### Slice 2: Hermes self-governance MVP

Implement first because it governs the governance system itself.

Checks:

```text
- workflow folder phase completeness;
- Harness report existence/freshness;
- Feishu ledger non-human noise count;
- skill references to known stale commands/paths;
- generated docs without evidence links.
```

Acceptance:

```text
python3 -m selfcheck run --root . --feature hermes-self-governance --groups static,evidence
```

### Slice 3: Project doc governance MVP for one active project

Start with `/root/work/v/ecommerce-frontend` or current active V project.

Checks:

```text
- package scripts vs README commands;
- routes/API docs freshness;
- docs with stale PASS claims without evidence;
- dead links and old local paths.
```

### Slice 4: Project code-health MVP

Use language-native tooling first, then AI review only for synthesis.

Examples:

```text
Go: go test, go vet, staticcheck if available, unused if available
Node/TS: typecheck, eslint if available, depcheck/ts-prune only if installed or explicitly added
Generic: file age, duplicate report names, route/page reference scans
```

### Slice 5: Pitfall registry enforcement

Add schema + CLI + verifier:

```text
selfcheck pitfall add/list/audit
verifiers/pitfall-feedback-gate.yaml
```

## Design principles

- Governance should be evidence-first, not opinion-first.
- Safe auto-fix is encouraged; destructive cleanup requires human decision.
- The system should reduce future review burden, not create a wall of reports.
- Docs are useful only if linked to live code, gates, or evidence.
- Skills are living SOPs; recurring mistakes must patch skills or verifiers.
- Feishu ledger is a human-readable projection, not a storage place for AI chatter.
