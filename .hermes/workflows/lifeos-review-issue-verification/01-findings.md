# LifeOS review issue verification — 2026-05-12

Source Base: https://my.feishu.cn/base/JSFUbtW0BafG3csC6hmc0ldvnhh?table=tblrbgJ7n3od02HY&view=vewv1XoUP3

## Scope

Verify whether the review findings exist:

1. Ambient selfcheck frequency too high, 143/day; reduce to every 2-4h or event driven.
2. Frontend implementation required repeated rework; user required 80% fidelity but actual gap was large.
3. Watchdog repeatedly alerted the same expired SESSION while self-healing was not effective.

## Sources checked

Feishu Base records:
- daily:2026-05-09
- daily:2026-05-10
- week:2026-W19

Local Mac source files:
- `/Users/bytedance/.hermes/lifeos/daily/2026-05-09.md`
- `/Users/bytedance/.hermes/lifeos/daily/2026-05-10.md`
- `/Users/bytedance/.hermes/lifeos/daily/2026-05-10.json`
- `/Users/bytedance/.hermes/lifeos/week/2026-W19.md`

Server/session evidence:
- `/root/.hermes/state.db`
- `/root/.hermes/cron/output/da227e480d8a/`
- `/root/.hermes/scripts/state_ledger.py health`
- `/root/.hermes/scripts/state_ledger_watchdog.py`
- `/root/work/v/.hermes/workflows/ecommerce-product-center-*`

## Findings

### 1. Ambient selfcheck frequency too high

Status: EXISTS historically; still partially present as schedule design.

Evidence:
- Feishu Base daily:2026-05-10 summary says `Ambient selfcheck frequency too high (143/day)`.
- Local daily JSON marks `Ambient selfcheck low-value polling` as 112 minutes, high confidence, source `Hermes session count`.
- Server session DB on 2026-05-10:
  - `cli`: 94 sessions, 188 messages, 0 tools.
  - `cron`: 61 sessions, 244 messages, 61 tools.
- First CLI messages show repeated pairs:
  - `你好`
  - `继续状态账本无感控制面这个事，只输出 AMBIENT_SELFCHECK_OK`
- State-ledger watchdog cron output count on 2026-05-10: 47 runs, all `[SILENT]`.
- `94 cli ambient pair sessions + 47 watchdog runs = 141 low-value ambient sessions`, very close to the review's 143/day figure. The exact review figure likely came from the LifeOS aggregation script with a slightly different inclusion rule.
- Current cron state still has `AI 状态账本自动健康检查` scheduled `every 30m`, while `Agentic SelfCheck 工作流健康巡检` is already `every 120m`.

Assessment:
- The issue is real for 2026-05-10/11.
- Current notification noise is mostly mitigated by `[SILENT]`, but compute/session churn remains because the 30m state-ledger watchdog still runs.

### 2. Frontend implementation required repeated rework / fidelity gap

Status: EXISTS.

Evidence:
- Local daily:2026-05-09: `前端复刻程度未达预期引发多次返工`.
- Local weekly: `Product Center frontend re-creation persistent rework is main friction source`.
- Weekly high severity item: `Kimi prototype recreation persistently below standard: 40%-50% gap, multiple rewrites`.
- Workflow folder shows multiple repair stages:
  - `05-visual-parity-failure-and-repair-brief.md`
  - `06-visual-parity-repair-status.md`
  - `07-one-shot-visual-parity-plan.md`
  - `08-one-shot-preview-status.md`
  - `09-style-consistency-repair-status.md`
  - `10-prototype-parity-replan.md`
  - `11-prototype-parity-repair-status.md`
  - `14-prototype-parity-repair-sku-listing-delivery.md`
  - `15-top-nav-workflow-overflow-fix.md`
  - `17-ecommerce-shell-fusion-pricing-order.md`
  - `18-shared-dynamic-public-pricing.md`
- Git history shows repeated Product Center/frontend follow-up commits and PRs around the same landing:
  - `feat: land product center mission control UI`
  - `fix: integrate product center shell with ecommerce chrome`
  - `fix: share dynamic public pricing cards`
  - `fix: Solution icon upgrade + nginx cache fallback + AGENTS.md restore`
  - `fix: remove unused solution icon import`

Assessment:
- The rework problem is clearly real.
- It is not merely model failure; it is process failure: implementation moved to PR/review before user visual acceptance/style gate was strong enough.
- Mitigation already exists in docs/skills: style gate before review, design-only prototype acceptance, Kimi design vs Hermes implementation split.

### 3. Watchdog repeatedly alerted same expired SESSION; self-healing ineffective

Status: EXISTS historically; now mostly fixed.

Evidence:
- Weekly review states: `watchdog repeatedly alerts same SESSION expired: SESSION-20260507_151007 from 15:37 to 22:55`.
- Cron output confirms repeated handling of `SESSION-20260507_151007_eae9f9` on 2026-05-07:
  - `2026-05-07_17-28-32.md`: reported stale active/blocked session heartbeat.
  - `2026-05-07_19-57-45.md`: attempted gateway restart, systemd bus failed, refreshed session heartbeat, health passed but still reported partial failure.
  - `2026-05-07_21-36-32.md`: AUTO_FIXED, refreshed session, health PASS, SelfCheck PASS.
  - `2026-05-07_22-39-00.md`: refreshed same session again and reported PASS.
- Current scripts now include automatic stale heartbeat refresh logic and strict `[SILENT]` rules.
- Current health check result:
  - `state_ledger.py health --heartbeat-sla-minutes 60`: ok true, no stale heartbeat.
  - `state_ledger_watchdog.py`: `[SILENT]`.

Assessment:
- The issue was real on 2026-05-07.
- It is currently not reproducing as an active failure.
- Remaining problem: the watchdog still runs every 30m, so if a future recoverable stale heartbeat appears, it may still consume cycles unless moved to event-driven or 2-4h cadence.

## Recommended actions

1. Reduce `AI 状态账本自动健康检查` from every 30m to every 2h or 4h unless actively debugging.
2. Keep `Agentic SelfCheck 工作流健康巡检` at every 120m as a fallback, not primary path.
3. Make event/callback triggers the primary SelfCheck path for changed requirements, PRs, deployments, and workflow updates.
4. For frontend work, enforce: design/prototype accepted visually before PR; Product Center pages must hit user-visible style gate first.
5. Keep watchdog outputs silent for routine self-healing and only escalate when a user decision/permission/destructive action is required.

## Current live status

- State ledger health: PASS.
- Watchdog script: `[SILENT]`.
- Historical findings: valid.
- Active residual risk: 30m state-ledger watchdog frequency remains higher than necessary.
