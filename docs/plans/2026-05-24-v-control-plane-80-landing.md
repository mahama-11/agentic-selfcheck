# V Control Plane 80+ Landing Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 把当前 V/SelfCheck 控制面从 `PASS_WITH_NOTES` 推进到可被口径化为“80 分以上”的状态：主巡检 PASS、控制面 notes 可解释且不阻断、关键产品 worktree 退出 quarantine 或明确 HITL 阻塞。

**Architecture:** 采用“两条线 + 一个总闸”：先修控制面可自动修复项（cron delivery、watchdog timeout、RepairTask backlog），再分批关闭产品 quarantine（CrossPlanet、Ecommerce V1 Listing），最后用 `v_control_plane_status.py` + workflow health loop 生成统一证据。任何产品语义/部署/破坏性动作必须 HITL，不自动越权。

**Tech Stack:** Agentic SelfCheck, Hermes cron, Feishu delivery, V product worktrees, Go backend tests, React/Vite frontend checks, SelfCheck feature/verifier reports.

---

## 当前基线

Generated from `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json` and fresh health loop run on 2026-05-24.

- 主巡检：`PASS`
  - Command: `scripts/workflow-health-loop.sh /root/work/agentic-selfcheck`
  - Event report: `reports/events/watchdog.every-2h-1779585293.json`
  - Feature: `ecommerce-product-ai-pipeline`
  - Groups: `static`, `api`, `browser`
- 控制面：`PASS_WITH_NOTES`
  - Command: `python3 scripts/v_control_plane_status.py --format markdown`
  - Evidence: `reports/v-control-plane-status/latest.json`
- 主要 notes / 扣分项：
  - RepairTask: `39 ready`
  - cron delivery errors: `2`
    - `be41037f9ef4` V 2h lightweight RepairTask executor: Feishu send failed `[99992402] field validation failed`
    - `e3c95c6dfa5d` V weekly closure-quality audit: Feishu send failed `[99992402] field validation failed`
  - watchdog timeout: `945640f35643` Ecommerce V2 Prep/Sandbox SelfCheck watchdog timed out after 120s
  - Product batches:
    - `batch_c_crossplanet`: `QUARANTINED`, dirty_total=14
    - `batch_d_v1_listing`: `QUARANTINED`, dirty_total=19

## 80+ 判定口径

`80+` 不是单个脚本分数，而是以下 release/control-plane stop conditions：

1. **硬门槛（必须全部满足）**
   - `workflow-health-loop.sh` returns `PASS`。
   - `v_control_plane_status.py` 不出现 `BLOCKED` / collection error / fail-open selector。
   - 工作树 watchdog 最近一次 silent/PASS。
   - 所有自动化报告路径存在且可读。

2. **控制面 notes 可接受**
   - cron delivery errors = 0，或已证明是目标平台字段兼容问题且有降级投递/本地证据路径，不阻断用户可见状态。
   - watchdog timeout = 0，或超时被改成可观测 `PASS_WITH_NOTES` / bounded retry，不能静默失败。
   - RepairTask ready 降到可解释集合：只剩 HITL、accepted risk、或非本轮 scope；自动可修复项应被消费或转 verified/blocked。

3. **产品 quarantine 处理完成**
   - `batch_c_crossplanet`、`batch_d_v1_listing`：至少各有明确状态之一：
     - `PASS` + evidence path + merge recommendation；或
     - `HITL_BLOCKED` + 需要郭凯决策的产品语义/部署风险；或
     - `QUARANTINED_WITH_DEDICATED_REPAIR_PLAN` + RepairTask/dispatch ID + 不影响当前 80+ 控制面口径。

4. **最终报告必须包含**
   - Feature / command / verifier groups / result / evidence paths。
   - 明确说明是否是 clean PASS 还是 `PASS_WITH_NOTES` 的 80+。

---

## Batch A — 修控制面可观测性与投递错误

### Task A1: 复现两个 Feishu delivery error

**Type:** AFK

**Objective:** 找到 `[99992402] field validation failed` 的真实原因，避免把 cron 成功误报为用户可见成功。

**Files:**
- Read: `/root/.hermes/cron/output/be41037f9ef4/2026-05-24_07-28-48.md`
- Read: `/root/.hermes/cron/output/e3c95c6dfa5d/2026-05-18_11-23-32.md`
- Inspect: Hermes gateway / send-message behavior if needed

**Steps:**
1. Read both latest output files and check for unsupported Feishu markdown/content shape: raw tables, too-long fields, invalid mentions, malformed media, or blank markdown table issue.
2. Send a short sanitized test message to the current Feishu origin only if it does not spam; otherwise use local delivery verification.
3. If the failure is output shape, update the two cron prompts or delivery formatter to avoid unsupported Feishu constructs.
4. Rerun the two jobs manually with `cronjob(action='run')` only after prompt/output shape is patched.

**Verifier command:**
```bash
python3 scripts/v_control_plane_status.py --format markdown
```

**Acceptance criteria:**
- `delivery_errors` becomes `0`, or each remaining error is downgraded to explicit `delivery_degraded_with_local_artifact` with latest local output path.
- No duplicate noisy notification is sent.

**Evidence path:**
- `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`

**需要郭凯决策:** false

### Task A2: 修 Ecommerce Prep/Sandbox watchdog timeout

**Type:** AFK

**Objective:** `945640f35643` 不再以 120s timeout 失败；长任务要有 bounded timeout、阶段输出和 fail-closed 状态。

**Files:**
- Read/Modify: `/root/.hermes/scripts/v_ecommerce_lowlevel_selfcheck_watchdog.sh`
- Read: related feature/verifier config under `/root/work/agentic-selfcheck/features/` and `/root/work/agentic-selfcheck/config/`

**Steps:**
1. Run the script manually with a higher timeout and capture which sub-command exceeds 120s.
2. Split slow checks into bounded stages with clear output: service readiness, static gate, API gate, browser gate.
3. If the cron no_agent timeout is too low for the legitimate gate, update cron schedule/script timeout strategy; do not hide failures.
4. Ensure script stdout is empty only on clean PASS; otherwise emits concise Chinese failure summary.

**Verifier command:**
```bash
/root/.hermes/scripts/v_ecommerce_lowlevel_selfcheck_watchdog.sh
python3 scripts/v_control_plane_status.py --format markdown
```

**Acceptance criteria:**
- Latest cron status for `945640f35643` is `ok` or explicit non-timeout `PASS_WITH_NOTES` with evidence.
- No silent timeout remains.

**Evidence path:**
- `/root/.hermes/cron/output/945640f35643/`
- `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`

**需要郭凯决策:** false

---

## Batch B — 消费/归类 39 个 ready RepairTasks

### Task B1: 生成 ready RepairTask 分桶

**Type:** AFK

**Objective:** 将 39 个 ready 分成可自动修、需产品决策、需部署/权限、可接受风险四类。

**Files:**
- Read: `/root/work/v/reports/maintenance-control-plane/repair-task-ledger.json`
- Read: `/root/work/v/reports/maintenance-control-plane/repair-task-status.md`

**Steps:**
1. Parse all `status=ready` tasks.
2. Group by `lane`, `project`, failure bucket, evidence age, and whether requires human/product decision.
3. Produce a markdown triage table under reports, not source code.
4. Select 5-10 low-risk AFK tasks for automatic closure batch.

**Verifier command:**
```bash
python3 scripts/v_repair_task_control.py --help >/dev/null
python3 scripts/v_control_plane_status.py --format markdown
```

**Acceptance criteria:**
- Every ready task has one of: `auto_repair_candidate`, `hitl_product_decision`, `deployment_required`, `accepted_risk_candidate`, `blocked_external`.
- No task is silently dropped.

**Evidence path:**
- `/root/work/v/reports/maintenance-control-plane/repair-task-status.md`

**需要郭凯决策:** false

### Task B2: 自动关闭低风险 ready 批次

**Type:** AFK

**Objective:** 只处理文档/证据路径/陈旧状态等低风险 RepairTasks，降低 ready 数量且不改产品逻辑。

**Files:**
- Modify only safe docs/evidence/control-plane records selected from B1
- Do not modify product code unless a dedicated product batch owns it

**Steps:**
1. For each selected low-risk task, verify current evidence first.
2. If already resolved, transition to `verified_resolved` with evidence.
3. If false positive, mark `accepted_false_positive` with reason.
4. If stale but unresolved, leave ready and attach blocker.
5. Rerun maintenance/control-plane status.

**Verifier command:**
```bash
python3 scripts/v_control_plane_status.py --format markdown
```

**Acceptance criteria:**
- Ready count decreases or every non-decreased item has explicit blocker.
- No product behavior changed in this batch.

**Evidence path:**
- `/root/work/v/reports/maintenance-control-plane/repair-task-ledger.json`
- `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`

**需要郭凯决策:** false

---

## Batch C — CrossPlanet quarantine 出口

### Task C1: CrossPlanet backend/frontend dedicated gate smoke

**Type:** AFK unless product semantics conflict appears

**Objective:** 判断 `batch_c_crossplanet` 是否能从 quarantine 进入 PASS，或是否必须 HITL。

**Files:**
- Backend: `/root/work/v-worktrees/crossplanet-listing-strategy-backend`
- Frontend: `/root/work/v-worktrees/crossplanet-listing-strategy-frontend`
- Changed files listed in status projection lines 298-329

**Steps:**
1. Verify git status and diff are exactly the quarantined 14 entries.
2. Run backend focused tests around `productcore` and `template_center_repository`.
3. Run frontend typecheck/build for changed pages/services.
4. Run or create CrossPlanet listing strategy input gate if it already exists; do not invent a fake PASS.
5. If blocker is product semantics, produce HITL question with concrete options, not code guess.

**Verifier command:**
```bash
# backend worktree
# run existing Go targeted tests for changed packages
# frontend worktree
# run existing package manager typecheck/build scripts
python3 /root/work/agentic-selfcheck/scripts/v_control_plane_status.py --format markdown
```

**Acceptance criteria:**
- Either `batch_c_crossplanet` becomes `PASS`, or remains quarantined with exact HITL blocker and required decision.
- No merge recommendation without gate evidence.

**Evidence path:**
- product worktree test output artifacts
- `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`

**需要郭凯决策:** only if listing strategy input semantics/copy must be chosen

---

## Batch D — Ecommerce V1 Listing quarantine 出口

### Task D1: Dedicated listing/export gate completion

**Type:** AFK unless deployment/prod approval needed

**Objective:** `batch_d_v1_listing` 当前 dirty_total=19，必须用 listing/export dedicated gate 证明或继续 quarantine。

**Files:**
- Backend: `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend`
- Frontend: `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-frontend`
- Feature/report: `/root/work/agentic-selfcheck/reports/ecommerce-v1-listing-export-gate/`

**Steps:**
1. Run backend targeted tests: `imageruntime`, `productcore`, `templatecenter`, repository/migration impacted packages.
2. Run frontend typecheck/build for changed `ProductDetailPage`, services, i18n, vite config.
3. Run listing/export static gate and any API/browser gate available.
4. Confirm no user-facing copy exposes backend/runtime/provider/prompt_plan/prompt_id/ready terminology.
5. If public bundle/prod deploy evidence is required, stop at HITL; do not deploy without approval.

**Verifier command:**
```bash
python3 /root/work/agentic-selfcheck/scripts/v_control_plane_status.py --format markdown
```

**Acceptance criteria:**
- Listing/export gate no longer reports merge-blocking `QUARANTINED_UNTIL_DEDICATED_GATE_FULLY_PASSES`, or the remaining blocker is explicit deployment/HITL.
- Backend + frontend evidence paths are recorded.

**Evidence path:**
- `/root/work/agentic-selfcheck/reports/ecommerce-v1-listing-export-gate/`
- `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`

**需要郭凯决策:** true only for prod deploy/public bundle approval or product semantics

---

## Batch E — Final 80+ evidence gate

### Task E1: Run final status projection and health loop

**Type:** AFK

**Objective:** 生成最终可发给郭凯的 80+ 证据包。

**Files:**
- Read: `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`
- Read: latest `reports/events/*.json`

**Steps:**
1. Run `python3 scripts/v_control_plane_status.py --format markdown`.
2. Run `scripts/workflow-health-loop.sh /root/work/agentic-selfcheck`.
3. Check status against 80+ 判定口径.
4. Produce concise Feishu report with `Feature`, `Command`, `Verifier groups`, `Result`, `Important notes / blind spots`, `Clean PASS or 80+ PASS_WITH_NOTES`.

**Verifier command:**
```bash
python3 scripts/v_control_plane_status.py --format markdown
scripts/workflow-health-loop.sh /root/work/agentic-selfcheck
```

**Acceptance criteria:**
- Final answer can honestly say one of:
  - `达成 80+：PASS_WITH_NOTES，但 notes 均为非阻断/已隔离/HITL`；or
  - `未达成：剩余阻断项为 ...`。

**Evidence path:**
- `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`
- latest `/root/work/agentic-selfcheck/reports/events/*.json`

**需要郭凯决策:** false unless Batch C/D surfaced HITL blocker

---

## Execution order

1. Batch A first：修投递与 timeout，因为这是控制面可信度问题。
2. Batch B second：降低 RepairTask ready 噪声，避免“分数看似高但债务堆积”。
3. Batch C/D parallelizable：两个 product quarantine 独立，但都需要 dedicated gate evidence。
4. Batch E last：只做最终证据汇总，不再引入新修复。

## Stop conditions

Stop and ask 郭凯 only when:

- Need prod deploy/public bundle approval.
- Need product semantic decision for CrossPlanet listing strategy input.
- A fix requires destructive data migration/reset.
- Credentials or external service permission is missing.
- Evidence shows implementation regression that cannot be safely auto-fixed.
