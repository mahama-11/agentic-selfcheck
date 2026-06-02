# V Workspace Maintenance Control Plane Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. This plan is production-shaped: the cron must become a durable maintenance control plane, not a noisy report-only watchdog.

**Goal:** Build a scheduled, evidence-backed maintenance system for `/root/work/v` that continuously finds, tracks, prioritizes, and safely repairs code redundancy, code logic risks, documentation redundancy, documentation staleness, documentation updates, and documentation standard issues.

**Architecture:** Keep `/root/work/agentic-selfcheck` as the reusable control plane. Treat `/root/work/v` as the first project adapter. Existing governance audits remain scanners; this plan adds project registration, stable finding IDs, a long-lived ledger, safe repair routing, and weekly/human-facing summaries.

**Tech Stack:** Python harness scripts, YAML project registry, JSON/Markdown reports under `/root/work/v/reports/maintenance-control-plane`, SelfCheck features/events/verifiers, Hermes cron job `71ea35e98beb`.

---

## Current state

There are currently two different jobs that should not be confused:

- `0e0a0b9e6bb2` / `v-workspace workflow gate self-healing audit`: checks only `/root/work/v/.hermes/workflows` role evidence. It is a workflow evidence gate, not project maintenance.
- `71ea35e98beb` / `V workspace continuous governance daily sweep`: triggers `v-project-doc-governance` and `v-project-code-health-governance`. This is the right starting point, but currently it mostly produces capped scan reports and does not yet maintain a durable issue lifecycle.

Existing scanner outputs:

- `/root/work/v/reports/project-doc-governance/audit.json`
- `/root/work/v/reports/project-code-health-governance/audit.json`

Existing scanner limitations:

- no project registry / ownership / cadence model;
- no stable finding IDs across days;
- no first_seen / last_seen / age / status lifecycle;
- no auto-fix routing beyond scanner recommendations;
- limited code logic coverage; current code-health mostly detects large files, repeated filenames, temp files;
- notifications are not yet based on trend, severity, and human-decision need.

---

## Target object model

### Project registry

File: `config/v-project-registry.yaml`

Each project entry defines:

```yaml
id: ecommerce-backend
path: /root/work/v/ecommerce-backend
kind: go-backend
active: true
owners: [Hermes]
docs:
  - docs
  - README.md
commands:
  test: go test ./...
  build: go test ./...
risk_boundaries:
  destructive_requires_human: true
  source_deletion_requires_human: true
```

Initial registry covers:

- `platform-backend`
- `platform-frontend`
- `ecommerce-backend`
- `ecommerce-frontend`
- `menu-backend`
- `menu-frontend`
- `kyc-backend`
- `kyc-frontend`
- workspace docs root `/root/work/v/docs`

### Finding ledger

Path: `/root/work/v/reports/maintenance-control-plane/findings-ledger.json`

Each finding has stable lifecycle fields:

```json
{
  "finding_id": "MNT-...",
  "project_id": "ecommerce-backend",
  "type": "code_redundancy | code_logic_risk | docs_redundancy | docs_staleness | docs_standard | evidence_gap",
  "severity": "info | warn | error | human",
  "path": "ecommerce-backend/internal/modules/productcore/service.go",
  "message": "Large source file ...",
  "recommended_action": "Review for deep module seams...",
  "first_seen": "2026-05-15T...+08:00",
  "last_seen": "2026-05-15T...+08:00",
  "seen_count": 1,
  "status": "open | resolved | accepted_risk | repairing | needs_human",
  "auto_fixable": false,
  "human_required": false,
  "evidence": ["reports/project-code-health-governance/audit.json"]
}
```

### Maintenance summary

Paths:

- `/root/work/v/reports/maintenance-control-plane/latest.json`
- `/root/work/v/reports/maintenance-control-plane/latest.md`
- `/root/work/v/reports/maintenance-control-plane/repair-queue.json`
- `/root/work/v/reports/maintenance-control-plane/repair-queue.md`

Summary must include:

- total open findings;
- new findings since last run;
- resolved findings since last run;
- aged findings over threshold;
- top projects by debt count;
- top human-required items;
- direct safe repair count;
- delegated repair count;
- recommended next action owner.

### Cadence model

Do not use one frequency for everything.

```text
Event-driven / on change:
- Trigger: git hooks / SelfCheck events.
- Use for: changed files, PR/pre-push/doc updates, frontend risk routing.
- Expected output: [SILENT] unless verifier fails or high-risk finding appears.

High-frequency lightweight / every 2h:
- Use for: ledger refresh, reopened/new high-risk triage, active repair queue health.
- Do not run expensive full builds for every project.
- Do not spam historical backlog.

Daily deep sweep / 10:35:
- Use for: full V doc/code governance audit, ledger update, repair queue generation.
- Existing canonical cron: `71ea35e98beb`.

Scan-time repair orchestration:
- Every scan must evaluate every finding immediately.
- If deterministic and safe: repair now, rerun verifier, then resolve with evidence.
- If actionable but not safe for direct patch: create dispatch immediately and start bounded repair/verification work in that same run where tool budget allows.
- If not repaired: record the reason explicitly, e.g. human decision required, broad refactor risk, false-positive validation needed, missing reproducer, or accepted architecture.
- No separate “one finding per day” worker; that design was removed as too weak.

Weekly digest and repair planning / Monday late morning:
- Use for: trend report, aged debt review, repair batching, safe delegated work planning.
- This is where routine known backlog becomes prioritized work, not daily noise.
```

### Handling model: not analysis-only

Every finding must choose one route:

```text
direct_safe_repair:
- Only deterministic, low-risk fixes with clear evidence.
- Examples: generated index refresh, broken local markdown link where target is obvious, report metadata normalization.

delegate_repair:
- Default for code redundancy, logic risk, evidence gap, semantic doc staleness, contract drift.
- Creates dispatch cards under `.hermes/dispatch/v-maintenance/`.
- Follow-up agents must use isolated branch/worktree, tests/build/review/final evidence before marking resolved.

human_decision:
- Only for destructive cleanup, source/doc deletion or merge, broad refactor, schema/contract/product decision, missing secret/permission.
```

---

## Implementation slices

### Slice 1: Registry + ledger bootstrap

**Type:** AFK

**Blocked by:** none

**Behavior covered:** Existing V governance audit findings become stable maintenance ledger rows with first_seen / last_seen / status.

**Acceptance criteria:**

- `config/v-project-registry.yaml` exists and includes all current V subprojects.
- `scripts/v_maintenance_control_plane.py` can ingest existing doc/code governance reports.
- Script writes `findings-ledger.json`, `latest.json`, `latest.md`.
- Re-running the script preserves `first_seen` and increments `seen_count` instead of creating duplicates.

**Verifier command:**

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_maintenance_control_plane.py --selfcheck-root . --v-root /root/work/v
python3 scripts/v_maintenance_control_plane.py --selfcheck-root . --v-root /root/work/v --format json
```

**Evidence path:** `/root/work/v/reports/maintenance-control-plane/latest.md`

**需要郭凯决策:** false

### Slice 2: Cron integration

**Type:** AFK

**Blocked by:** Slice 1

**Behavior covered:** Daily V governance cron becomes the maintenance control-plane entrypoint rather than only raw scanner report.

**Acceptance criteria:**

- Cron `71ea35e98beb` runs:
  1. `selfcheck trigger --event v.governance.watchdog.daily`
  2. doc/code governance audits
  3. `scripts/v_maintenance_control_plane.py`
- Cron final output follows:
  - `[SILENT]` when only routine known debt remains;
  - concise report when new high severity / needs human / repeated unrepaired problem appears.

**Verifier command:**

```bash
hermes cron run 71ea35e98beb
```

**Evidence path:** `/root/work/v/reports/maintenance-control-plane/latest.md`

**需要郭凯决策:** false

### Slice 3: Scanner expansion — code redundancy and logic risks

**Type:** AFK first, HITL for broad refactor decisions

**Blocked by:** Slice 1

**Behavior covered:** Improve findings beyond giant-file warnings.

**Add detectors:**

- Go: `go test ./...` failure capture per backend; optionally `go vet ./...` where clean enough.
- Frontend: `npm run typecheck` / `npm run build` failure capture per frontend.
- Duplicate/near-duplicate source detection using normalized function/component signatures.
- Unused frontend exports/imports when project tooling supports it.
- Dead routes/pages: frontend router references vs pages/components.
- Contract drift: backend route list/OpenAPI vs frontend service clients for V high-value modules.

**Acceptance criteria:**

- New findings are typed as `code_logic_risk`, `code_redundancy`, or `contract_drift`.
- Expensive build/test commands are bounded by per-project timeout and can be skipped for inactive projects.
- Any behavior-affecting fix is routed to isolated worktree/branch; cron never edits main directly.

**Verifier command:**

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_maintenance_control_plane.py --selfcheck-root . --v-root /root/work/v --include-runtime-checks --timeout 180
```

**Evidence path:** `/root/work/v/reports/maintenance-control-plane/latest.md`

**需要郭凯决策:** only for broad refactor/delete/schema/contract decisions

### Slice 4: Scanner expansion — document redundancy, freshness, and standards

**Type:** AFK first, HITL for deletion/merge decisions

**Blocked by:** Slice 1

**Behavior covered:** Detect docs that are duplicate, stale, missing required standards, or contradict code.

**Add detectors:**

- README/AGENTS/docs index link validation by project.
- Stale commands: docs mention scripts/ports/routes that no longer exist.
- Stale API docs: documented routes missing in backend router/OpenAPI.
- Redundant docs: high-similarity Markdown files with overlapping title/scope.
- Standard structure: owner/status/evidence/last reviewed/related code paths required for long-lived docs.

**Acceptance criteria:**

- Low-risk doc standard fixes can be auto-proposed or patched.
- Deleting/merging docs always becomes `needs_human` or PR review, never silent cron deletion.

**Verifier command:**

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_maintenance_control_plane.py --selfcheck-root . --v-root /root/work/v --docs-deep
```

**Evidence path:** `/root/work/v/reports/maintenance-control-plane/latest.md`

**需要郭凯决策:** only for deletion/merge/product-commitment rewrites

### Slice 5: Safe repair lanes

**Type:** AFK for low-risk, HITL for source-impacting changes

**Blocked by:** Slices 1-4

**Behavior covered:** Findings become actionable work, not a growing report.

**Routing rules:**

- `docs_standard`, low risk: auto patch in branch, run doc verifier, attach diff.
- `evidence_gap`: link existing report if deterministically known; otherwise create repair task.
- `code_redundancy`: create worktree task with architect review before refactor.
- `code_logic_risk`: reproduce via test/smoke, minimal fix, regression test, spec/quality/final verification.
- `needs_human`: notify 郭凯 only if product/architecture/deletion/secret/destructive decision is required.

**Acceptance criteria:**

- Ledger status can move `open -> repairing -> resolved` with evidence.
- Repair output writes to `.hermes/workflows/maintenance-<finding_id>/`.
- No destructive cleanup occurs without explicit approval.

**Verifier command:**

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_maintenance_control_plane.py --selfcheck-root . --v-root /root/work/v --repair-safe --dry-run
```

**Evidence path:** `.hermes/workflows/maintenance-*/`

**需要郭凯决策:** only for HITL rules above

### Slice 6: Weekly digest and trend value

**Type:** AFK

**Blocked by:** Slice 1

**Behavior covered:** The system shows long-term value, not one-off alerts.

**Acceptance criteria:**

- Weekly report includes trend: new/resolved/aged/repeated by project/type.
- Daily cron remains `[SILENT]` unless there is new high-risk or human-required work.
- Weekly digest can be delivered to Feishu with concise bullets and evidence paths.

**Verifier command:**

```bash
cd /root/work/agentic-selfcheck
python3 scripts/v_maintenance_control_plane.py --selfcheck-root . --v-root /root/work/v --weekly
```

**Evidence path:** `/root/work/v/reports/maintenance-control-plane/weekly.md`

**需要郭凯决策:** false unless digest contains HITL items

---

## Notification policy

Do not notify for ordinary known backlog every day.

Notify only when:

- new `error`/`human` severity finding appears;
- a finding becomes older than the configured aging threshold and blocks active project work;
- automatic safe repair fails repeatedly;
- deletion/merge/refactor/schema/contract/product decision is needed;
- build/test/runtime smoke fails on an active project.

Message shape:

```text
状态：...
结论：...
需要郭凯决策：是/否
新增/恶化：最多 3 条
已自动处理：N 项，如有
证据：reports/maintenance-control-plane/latest.md
下一步：Hermes/工程代理处理 | 需要郭凯决策
```

---

## Done definition

This project is considered landed when:

1. `71ea35e98beb` uses the maintenance control-plane summary as its canonical output.
2. A ledger exists and survives reruns with stable IDs.
3. At least doc/code existing governance findings are tracked per project/type.
4. Daily notifications are quiet unless actionable.
5. There is a concrete path from finding to repair lane / worktree / evidence / resolved status.
6. The old `0e0a0b9e6bb2` is explicitly documented as workflow evidence gate only, not project maintenance.
