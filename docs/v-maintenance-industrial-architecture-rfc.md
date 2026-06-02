# V Maintenance Industrial Architecture RFC

Status: draft-to-implement
Owner: Hermes / Agentic SelfCheck
Target adapter: `/root/work/v`
Created: 2026-05-15

## Why this RFC exists

The user's correction is valid: a valuable engineering-maintenance system is not a cron that periodically lists problems, nor a queue that fixes one item per day. It should be an industrial control loop:

```text
observe -> classify -> decide -> repair/assign -> verify -> integrate -> learn
```

Every detected issue must get a decision at scan time:

- `repair_now`: deterministic and safe, fix immediately, then verify.
- `repair_batch`: safe but larger than a one-shot patch, schedule into an execution wave immediately.
- `delegate_now`: needs an engineering agent, create/launch a bounded task immediately.
- `human_decision`: blocked by product/architecture/destructive/secret/permission boundary.
- `accepted_or_false_positive`: record evidence and suppress future noise.
- `monitor`: only allowed with a concrete reason and an expiry/recheck date.

No finding should remain as "reported only".

---

## Priority reference: AI-native engineering systems

The primary reference is **AI engineering organization design**, not traditional static-analysis tooling. Traditional tools are still valuable, but mainly as analyzers, verifiers, and guardrails that feed an AI-native control loop.

### OpenAI Codex / Agents platform — background work, sandboxing, tools, evaluation

Sources:
- OpenAI Codex docs: `https://developers.openai.com/codex/`
- OpenAI Codex changelog: `https://developers.openai.com/codex/changelog/`

Observed pattern:
- agents run as background/autonomous workers, not just chat assistants;
- useful abstractions include sandboxed execution, shell/tools, apply-patch, file retrieval, background mode, webhooks, evaluation, guardrails, and structured state;
- the agent needs an execution contract: task, environment, permissions, verifier, and result state.

Implication for V:
- the maintenance system should model **agent jobs**, not only findings;
- every repair task needs a sandbox/worktree, tool permissions, verifier contract, and resumable state;
- cron/webhook/git events should create or resume agent jobs, not merely generate reports.

### Anthropic Claude Code — verify work, explore-plan-code, context files, subagents, hooks

Sources:
- Claude Code overview: `https://docs.anthropic.com/en/docs/claude-code/overview`
- Claude Code best practices: `https://www.anthropic.com/engineering/claude-code-best-practices`

Observed pattern:
- Claude Code is an agentic coding tool that reads code, edits files, runs commands, and integrates with terminal/IDE/web/Slack/CI;
- best practices emphasize: give the agent a way to verify its work; explore first, plan, then code; provide project instructions; configure permissions; use hooks; use subagents for investigation; manage context aggressively; run multiple sessions/fan out; avoid common failure patterns.

Implication for V:
- every maintenance finding should include a verifier before repair starts;
- AI repair should be staged: investigate -> plan -> patch -> verify -> review;
- repository-level instructions (`AGENTS.md`/workflow docs) are part of the system contract;
- subagents are not optional; they are how broad maintenance work scales while preserving review separation.

### Anthropic multi-agent research system — orchestrator + parallel specialists + evaluation

Source: `https://www.anthropic.com/engineering/built-multi-agent-research-system`

Observed pattern:
- open-ended work is path-dependent and benefits from multiple agents exploring in parallel;
- production multi-agent systems need coordination, evaluation, tool design, and reliability controls;
- an orchestrator plans and fans out specialist agents, then synthesizes results.

Implication for V:
- the control plane should have an **orchestrator** that decomposes findings into specialized lanes: doc repair, backend risk, frontend risk, contract drift, reviewer, verifier;
- agents should not all mutate code; some investigate, some implement, some review, some verify;
- reliability comes from role boundaries and verifier gates, not from trusting one agent's self-report.

### GitHub Copilot cloud/coding agent — issue/PR-native autonomous task completion

Source: GitHub Copilot cloud agent docs: `https://docs.github.com/en/copilot/concepts/coding-agent/coding-agent`

Observed pattern:
- the agent is integrated with GitHub issues, PRs, sessions, branch rollback, MCP/tools, and enterprise controls;
- task completion is tied to repository workflows, not a side-channel report;
- risks/mitigations, access management, custom agents, hooks, and session data are first-class concepts.

Implication for V:
- every delegated repair should look like an issue/PR/task card with branch/worktree/session/evidence links;
- rollback and access boundaries must be explicit;
- the system should track session data and allow resume/inspection.

### Cursor Background Agents — asynchronous coding agents near IDE context

Source: Cursor background-agent docs: `https://docs.cursor.com/background-agent`

Observed pattern:
- background agents are useful when work can continue without blocking the developer;
- they need strong context, clear task boundaries, and integration with code review/branch workflows.

Implication for V:
- high-volume maintenance should not block chat; it should spawn resumable background repair lanes;
- user-facing messages should be compact status, not the main work surface.

### Amp / Sourcegraph-style agent workflows — subagents, oracle/review, thread sharing

Source: Amp manual: `https://ampcode.com/manual`

Observed pattern:
- AI coding environments expose subagents, review/oracle modes, CLI/non-interactive modes, permissions, plugins, shared threads, and prompts as reusable operating objects;
- examples include running tests and fixing failures, using multiple subagents, reviewing API designs, and inspecting blame/history.

Implication for V:
- maintenance control should use prompt/skill/role objects, not giant cron prompts;
- investigation, implementation, review, and verification should have distinct reusable lanes;
- thread/session sharing becomes evidence for why a repair was accepted.

### Devin-style autonomous engineering — delegate large migrations, but verify completion

Source: Devin public site/case material: `https://devin.ai/`

Observed pattern:
- AI agents are used for large repetitive migrations and refactors, not just local lint fixes;
- success claims are tied to delegation, verification by business units/engineers, and time saved.

Implication for V:
- long-lived code redundancy and migration work should become batch repair programs with measurable throughput;
- success metric is not "findings found" but verified closures, accepted patches, and saved engineering time.

### AI-native exposed failure points

Across AI coding agents, the recurring failure modes are:

- vague task boundaries: agents wander or over-edit;
- missing verification: agents report success without executable proof;
- context degradation: broad repos exceed useful context and agents miss constraints;
- unsafe autonomy: direct edits without sandbox/branch/permission gates;
- self-report trust: subagent says fixed, but parent never verifies;
- noisy delegation: many tasks created, few closed;
- non-resumable work: no stable task/session/evidence object;
- weak learning loop: false positives and rejected patches do not update rules.

Therefore the V system must be built around **AI task control**, not around reports:

```text
finding -> decision -> agent task -> sandbox/worktree -> patch -> verifier -> review -> ledger closure -> learned policy
```

Current implementation adjustment:
- The control-plane script now emits a first-class RepairTask source ledger: `/root/work/v/reports/maintenance-control-plane/repair-tasks.json` and `.md`.
- Each actionable finding becomes a stable `RT-*` task with `finding_id`, lane, project path, sandbox policy, permissions, verifier contract, evidence paths, and resume hint.
- The lifecycle controller `/root/work/agentic-selfcheck/scripts/v_repair_task_control.py` now provides `sync`, `plan`, `lease`, `update`, `verify`, and `status` actions.
- Durable lifecycle evidence is stored in `/root/work/v/reports/maintenance-control-plane/repair-task-ledger.json`, `repair-task-events.jsonl`, `repair-task-status.md`, `repair-task-plan.*`, and dispatch cards under `/root/work/agentic-selfcheck/.hermes/dispatch/v-maintenance-tasks/`.
- Verification is fail-closed: verifier commands passing is necessary but not sufficient; the original finding/RepairTask must also disappear from the latest scan source before `verified_resolved` can be set.
- Cron/webhook runs should treat lifecycle RepairTask as the execution unit; findings and repair queue are inputs, not the work surface.

---

## Traditional engineering systems as supporting layer

Traditional systems remain useful, but they are support infrastructure for the AI-native loop:

- Tricorder/Semgrep/CodeQL/SonarQube style analyzers produce findings.
- Renovate/Dependabot/OpenRewrite style bots provide recipe/autopatch patterns.
- reviewdog/PR comments provide code-adjacent feedback surfaces.
- CI/test/build tools provide verifier truth.

They should not be the whole architecture.

## Internet / industry patterns reviewed

This section summarizes traditional and hybrid systems that complement the AI-native design.

### Google Tricorder — analyzer ecosystem + reviewer workflow

Source: Google Research, "Tricorder: Building a Program Analysis Ecosystem"
`https://research.google/pubs/tricorder-building-a-program-analysis-ecosystem/`

Pattern:
- many static/dynamic analyzers share one review-facing ecosystem;
- findings are integrated into developer workflow, not sent as unactionable reports;
- analyzer quality matters: actionable signals beat volume.

V implication:
- SelfCheck should be the analyzer ecosystem and signal router;
- outputs should be normalized findings, not isolated report files;
- quality gates should suppress noisy/low-confidence findings until they are actionable.

### CodeQL / code scanning — SARIF-like findings + alert lifecycle

Source: GitHub Docs, "About code scanning with CodeQL"
`https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql`

Pattern:
- code scanning produces tracked alerts;
- findings tie to locations, rules, severity, and history;
- alerts can be used in PR/merge gates.

V implication:
- finding ledger should be SARIF-inspired: `rule_id`, `fingerprint`, `location`, `severity`, `state`, `dismissal_reason`, `first_seen`, `fixed_by`, `verification`;
- recurring findings should be deduped by stable fingerprint;
- only verified fixes close findings.

### Semgrep CI / reviewdog — inline actionable review integration

Sources:
- Semgrep CI overview: `https://semgrep.dev/docs/semgrep-ci/overview`
- reviewdog: `https://github.com/reviewdog/reviewdog`

Pattern:
- run many linters/analyzers but surface findings close to the code/change;
- comments should be actionable and scoped;
- analysis tools are adapters, not the governance brain.

V implication:
- governance scanners should write normalized findings;
- repair agents should get file-scoped tasks and minimal context;
- noise suppression is a first-class feature.

### Renovate / Dependabot — autonomous PR generation with scheduling and policies

Sources:
- Renovate docs: `https://docs.renovatebot.com/`
- Dependabot version updates: `https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/about-dependabot-version-updates`

Pattern:
- autonomous bots do not just report outdated dependencies; they create PRs;
- policy controls noise: grouping, schedules, automerge rules, limits;
- tests/CI determine whether the bot's change is safe.

V implication:
- for safe maintenance classes, Hermes should generate branches/patches/PR-equivalent artifacts;
- batch/group similar findings by project/module;
- impose WIP/concurrency budgets, but decisions happen immediately.

### OpenRewrite / Moderne — recipe-based, large-scale automated refactoring

Source: OpenRewrite docs: `https://docs.openrewrite.org/`

Pattern:
- codified recipes perform repeatable automated refactors;
- large-scale changes are still controlled by recipes and tests;
- technical debt is reduced through executable transformations, not ad-hoc suggestions.

V implication:
- build a recipe library for deterministic V fixes: doc frontmatter normalization, evidence-link backfill, route docs regeneration, simple import cleanup;
- only recipe-backed changes qualify as `repair_now`/automerge candidates;
- broad refactors become `repair_batch` with design/review gates.

### SonarQube / quality gates / remediation-agent trend

Source: SonarQube Server docs: `https://docs.sonarsource.com/sonarqube-server/latest/`

Pattern:
- quality gates convert analysis into pass/fail policy;
- remediation is prioritized by severity, new-code policy, and maintainability/security risk.

V implication:
- don't try to fix all old debt equally;
- protect new/changed code aggressively;
- maintain a debt burndown policy for old issues.

### Meta SapFix / Getafix — generate fixes, propose to engineers, learn from accepted patches

Sources:
- SapFix: `https://engineering.fb.com/2018/09/13/developer-tools/finding-and-fixing-software-bugs-automatically-with-sapfix-and-sapienz/`
- Getafix: `https://engineering.fb.com/2018/11/06/developer-tools/getafix-how-facebook-tools-learn-to-fix-bugs-automatically/`

Pattern:
- automatic repair proposes patches for specific bugs;
- engineers approve or reject;
- accepted human fixes become learning data for future fixes.

V implication:
- repair lanes should generate candidate patches with evidence;
- acceptance/rejection/false-positive outcomes should update rules and routing;
- for high-risk code, Hermes proposes reviewed patches rather than silently mutating main.

---

## Target architecture

The core object is not `cron_job`. The core object is **AI-maintenance task state**.

```text
Finding
  -> Decision
  -> RepairTask
  -> AgentSession(s)
  -> Patch/Diff
  -> Verification
  -> Review
  -> Closure/Learning
```

Cron, webhooks, git hooks, and chat commands are only triggers that create/resume these objects.

### 0. AI task control plane

Required fields for each repair task:

```json
{
  "task_id": "MNT-TASK-...",
  "finding_ids": ["MNT-..."],
  "lane": "recipe|doc-agent|backend-agent|frontend-agent|contract-agent|reviewer|verifier",
  "status": "queued|running|blocked|verified_fixed|failed|needs_human",
  "worktree": "/root/work/v/.worktrees/...",
  "branch": "maintenance/...",
  "session_id": "Hermes/Codex/Claude session handle",
  "permissions": ["read", "edit_worktree", "run_tests"],
  "expected_verifiers": ["..."],
  "evidence_paths": ["..."],
  "owner": "Hermes/工程代理"
}
```

This is what prevents AI work from becoming invisible, unverifiable chat.

### 1. Project registry

Canonical file: `config/v-project-registry.yaml`

Each project declares:

- code roots and doc roots;
- project type: Go backend, React frontend, docs, infra;
- commands: typecheck, build, unit tests, smoke tests;
- risk boundaries;
- ownership and allowed autonomous repair classes;
- service/runtime metadata if runtime QA is needed.

This registry is the inventory source, not the cron prompt.

### 2. Signal sources

Use multiple triggers with different cost profiles.

```text
Event-driven:
- git hooks, post-merge, pre-push, changed-file SelfCheck events;
- highest priority because it prevents new debt.

High-frequency light:
- every 2h fallback;
- refresh ledger, process new/reopened/high-risk, avoid full workspace builds.

Daily deep:
- full doc/code governance scan;
- detects slow drift, redundancy, stale docs, broader structural issues.

Weekly review:
- not a delayed repair planner;
- audits whether repair decisions actually closed, got delegated, or have valid reasons.
```

### 3. Analyzer layer

Analyzers are plugins. They produce normalized raw findings.

Initial analyzer groups:

- code size/locality: large files, large functions/components, module density;
- duplication: repeated names, duplicate code blocks, repeated services/types;
- logic risk: build/typecheck/test failures, panic/null-risk patterns, unreachable code;
- contract drift: backend routes/schema vs frontend clients/docs;
- doc standards: missing owners/status/evidence, broken links, stale commands;
- doc redundancy: similar docs, conflicting claims, duplicate plans;
- workflow evidence: role/gate closure evidence (separate from project maintenance).

Analyzer output should be SARIF-like:

```json
{
  "rule_id": "v.code.large_file",
  "fingerprint": "stable hash",
  "project_id": "ecommerce-frontend",
  "location": {"path": "...", "start_line": 1},
  "severity": "info|warn|error|human",
  "confidence": "low|medium|high",
  "message": "...",
  "autofix_recipe": null,
  "evidence": ["..."]
}
```

### 4. Policy / decision engine

A scan is incomplete until every finding has a decision.

Decision fields:

```json
{
  "finding_id": "MNT-...",
  "decision": "repair_now|repair_batch|delegate_now|human_decision|accepted_or_false_positive|monitor",
  "decision_reason": "why this route",
  "risk_level": "low|medium|high",
  "repair_class": "recipe|agent_patch|refactor_batch|human",
  "expected_verifier": ["npm run build", "go test ./..."],
  "decision_expires_at": "2026-..."
}
```

Important rule: `monitor` is not a lazy queue. It requires a reason and expiry.

### 5. Repair orchestration

There should be no fixed "one repair per day" rule.

Instead use industrial WIP limits:

```text
Immediate recipe lane:
- deterministic low-risk fixes;
- can execute multiple per run;
- must verify and close or revert.

Agent patch lane:
- local scoped code/doc fixes;
- launch bounded parallel repair tasks by project/module;
- require isolated branch/worktree for code changes.

Batch refactor lane:
- groups related redundancy/debt findings;
- requires architecture note and slice plan;
- may run over days, but is created immediately.

Human decision lane:
- only for irreversible, product/architecture, contract, secret/permission, destructive decisions.
```

WIP budgets should be dynamic, not arbitrary:

- max parallel project lanes: e.g. 2-3;
- max risky code branches per project: 1;
- max low-risk doc recipe fixes per run: many, until verifier budget;
- stop on failing verifier or dirty unsafe state;
- prioritize new/high-risk/reopened/changed-code findings over old backlog.

### 6. Verification gates

A finding is not resolved because a patch exists. It is resolved only when the expected verifier passes.

Verification evidence should include:

- command run;
- exit code;
- relevant output path;
- diff/branch/worktree path;
- before/after finding state;
- reviewer/final gate when code behavior changed.

Resolution states:

```text
open -> decided -> repairing -> verified_fixed -> resolved
open -> decided -> accepted_risk / false_positive
open -> needs_human
repairing -> failed_verification -> open/retry_later
resolved -> reopened
```

### 7. Evidence and observability

Required artifacts:

```text
/root/work/v/reports/maintenance-control-plane/findings-ledger.json
/root/work/v/reports/maintenance-control-plane/latest.json
/root/work/v/reports/maintenance-control-plane/repair-queue.json
/root/work/v/reports/maintenance-control-plane/repair-queue.md
/root/work/v/reports/maintenance-control-plane/decisions.jsonl
/root/work/v/reports/maintenance-control-plane/repairs.jsonl
/root/work/v/reports/maintenance-control-plane/verifications.jsonl
/root/work/agentic-selfcheck/.hermes/dispatch/v-maintenance/*.md
```

Dashboards should track:

- new / resolved / reopened per day;
- mean time to decision;
- mean time to verified fix;
- false-positive rate by analyzer;
- verifier failure rate by repair class;
- backlog age by project/type/severity;
- human-decision count and age.

### 8. Notification policy

Notifications are not the control plane.

Notify 郭凯 only when:

- human decision required;
- high-risk finding newly appears or reopens;
- automatic repair succeeded in a meaningful way;
- repair failed after safe retries;
- trend is deteriorating despite automation.

Routine scan/repair churn should be silent but auditable.

---

## What is wrong with the current implementation

Current state after the first bootstrap:

- good: project registry exists;
- good: stable finding ledger exists;
- good: repair queue exists;
- good: cron jobs are wired;
- insufficient: repair execution is still mostly dispatch-card generation;
- insufficient: no recipe library yet;
- insufficient: no structured decision/repair/verification event log yet;
- insufficient: analyzer coverage is shallow for logic risk and doc staleness;
- insufficient: no dynamic WIP/concurrency controller;
- insufficient: no verified fix loop that closes findings automatically after repair evidence.

The correct next step is not more cron prompts. It is implementing the policy/repair/verifier loop as code.

---

## Implementation roadmap

### Slice A — Decision engine v1

Add `decisions.jsonl` and require every open finding to have:

- decision;
- reason;
- risk level;
- expected verifier;
- expiry/recheck date;
- owner lane.

Acceptance:

- every scan has `evaluated == open_findings`;
- no finding lacks a decision;
- `monitor` entries have non-empty reason and expiry.

### Slice B — Recipe repair lane

Implement deterministic repairs first:

- broken local Markdown link when target is obvious;
- generated index/table-of-contents refresh;
- missing evidence link when exact report/workflow evidence exists;
- doc metadata normalization;
- stale report path correction.

Acceptance:

- repair writes diff/evidence;
- verifier reruns;
- finding becomes `verified_fixed` or remains open with failure evidence.

### Slice C — Agent patch lane

Implement immediate dispatch + bounded parallel execution:

- group findings by project and risk;
- launch small number of isolated repair tasks;
- each task must produce patch + verifier evidence;
- update ledger from actual verification, not self-report.

Acceptance:

- no fixed one-per-day limit;
- WIP controlled by project/risk budget;
- code changes never touch main directly.

### Slice D — Analyzer expansion

Add deeper analyzers:

- Go/React build/test/typecheck failure capture;
- function/component duplication fingerprints;
- route/client/doc contract drift;
- doc similarity/conflict detector;
- stale command/path detector.

Acceptance:

- each analyzer has false-positive tracking;
- noisy rules can be disabled or confidence-gated.

### Slice E — Control dashboard and SLOs

Add machine-readable and human-readable views:

- debt trend;
- mean time to decision/fix;
- stale decisions;
- human-decision queue;
- top projects/types.

Acceptance:

- weekly digest is generated from event logs, not from vibes;
- system proves long-term value through closure trends.

---

## Revised cron roles

### Event-driven hooks

Purpose: protect changed code/docs immediately.

Behavior:

- scan changed files;
- decide every finding;
- repair_now or delegate_now immediately;
- block/notify only when verification fails or human decision is needed.

### Every 2h light run

Purpose: fallback triage and active repair-progress watchdog.

Behavior:

- no full expensive scans;
- process new/reopened/high-risk/action-expired items;
- continue/retry bounded repair work if safe;
- notify only on meaningful outcome or human need.

### Daily 10:35 deep run

Purpose: full discovery and repair orchestration.

Behavior:

- run full analyzers;
- decide every finding;
- execute all safe recipes;
- launch bounded repair batches;
- verify and close what is fixed;
- leave explicit reasons for anything not fixed now.

### Weekly digest

Purpose: governance review.

Behavior:

- audit whether decisions are stale;
- check closure trend;
- detect noisy analyzers;
- escalate only real structural blockers.

---

## Design principle

A real AI-native engineering maintenance system should optimize for:

```text
clear task boundary, autonomous repair, executable verification, resumable state, reviewed closure, learning over time
```

Traditional static analysis contributes signals, but the differentiator is the AI control loop:

```text
agent does useful work -> proves it -> records evidence -> learns from outcome
```

Not:

```text
scan often, report often, accumulate queues, ask user to manage backlog, trust agent self-reports
```
