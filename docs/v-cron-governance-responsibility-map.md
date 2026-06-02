# V / SelfCheck Cron Governance Responsibility Map

Updated: 2026-05-22

Purpose: keep scheduled jobs non-overlapping. A job should either have a unique trigger boundary, a unique target surface, or a unique lifecycle stage. If two jobs share all three, remove or merge one.

## Responsibility boundaries

### Runtime / environment health

- `04925f44b90a` — `SelfCheck runtime service watchdog`
  - Cadence: every 120m
  - Target: `/root/work/agentic-selfcheck` runtime dependencies and V adapter dev services.
  - Owns: port/service recovery, workflow-health-loop rerun, routine transient recovery.
  - Does not own: V RepairTask backlog consumption or business-code governance.

- `da227e480d8a` — `AI 状态账本自动健康检查`
  - Cadence: every 30m
  - Target: AI state ledger / Life OS projection health.
  - Owns: ledger health, stale session normalization, safe state-ledger self-healing.
  - Does not own: V code quality, SelfCheck feature governance, RepairTask repair.

### Change-triggered business gates

- `5956a3339eb8` — `V working-tree business gate watchdog`
  - Cadence: every 30m, no-agent script.
  - Target: dirty working-tree changes under `/root/work/v`.
  - Owns: changed-file to business-gate selection after quiet window, gate execution, failure closed-loop ingestion.
  - Does not own: routine RepairTask backlog consumption or daily trend reporting.

- `945640f35643` — `Ecommerce V2 Prep/Sandbox SelfCheck watchdog`
  - Cadence: every 240m, no-agent script.
  - Target: fixed critical Ecommerce V2 Prep/Sandbox low-level feature gate.
  - Owns: fixed high-value business regression safety net.
  - Does not own: arbitrary dirty diff detection, RepairTask lifecycle, or broad governance audit.

### V workflow / RepairTask control plane

- `0e0a0b9e6bb2` — `v-workspace workflow gate self-healing audit`
  - Cadence: daily 09:30.
  - Target: `/root/work/v/.hermes/workflows` evidence state.
  - Owns: canonical workflow evidence debt repair only when QA + Final PASS make it safe.
  - Does not own: business code edits, Final BLOCKED overrides, or RepairTask backlog.

- `be41037f9ef4` — `V 2h lightweight RepairTask executor`
  - Cadence: every 120m.
  - Target: V RepairTask queue.
  - Owns: routine small safe RepairTask execution: plan, lease, bounded delegate, parent verification, closure.
  - Does not own: daily discovery/trend audit, weekly closure-quality audit, dirty working-tree gates.

- `71ea35e98beb` — `V daily discovery and repair-queue governance sweep`
  - Cadence: daily 10:35.
  - Target: V governance inputs and RepairTask control-plane health.
  - Owns: daily discovery, finding-to-RepairTask coverage, high-risk/reopened/verification_failed/stale/fake-closure/contract-gap detection.
  - Does not own: ordinary ready backlog consumption; that belongs to the 2h lightweight executor.

- `e3c95c6dfa5d` — `V weekly closure-quality audit`
  - Cadence: weekly Monday 11:20.
  - Target: RepairTask control-plane quality and long-term trends.
  - Owns: weekly trend, fake closure audit, stale lease audit, lane/contract completeness audit, human-decision boundary review.
  - Does not own: routine repair execution.

### SelfCheck repo governance

- `e72e4398fee8` — `SelfCheck repo daily governance sweep`
  - Cadence: daily 10:15.
  - Target: `/root/work/agentic-selfcheck` repository itself.
  - Owns: SelfCheck repo doc/code/skill/pitfall governance trigger and audit.
  - Does not own: V workspace RepairTask queue.

### Personal productivity

- `4d0eca6a6eac` — `灵感收集箱每日推进提醒`
  - Cadence: daily 09:00.
  - Target: Feishu Base idea inbox.
  - Owns: idea capture daily progress reminders.
  - Does not own: engineering quality governance.

## Deduplication rule

Remove or merge a cron job if it matches another job on all of the following:

1. Same target surface.
2. Same lifecycle stage.
3. Same trigger/cadence class.
4. Same action boundary.
5. Same notification contract.

If only target surface overlaps, split by lifecycle stage instead of deleting. Example: V RepairTask jobs are intentionally split into `2h executor`, `daily queue governance`, and `weekly closure-quality audit`.

## Notification contract

- PASS or routine PASS_WITH_NOTES with no user action: `[SILENT]`.
- Notify only for high-risk, reopened, verification_failed, stale lease/in_progress, fake closure, queue contract gap, delivery failure, or product/architecture/permission/secret/destructive-operation decision.
- Feishu/Lark delivery should fallback from rich post to plain text when the API returns either `content format of the post type is incorrect` or `[99992402] field validation failed`.
