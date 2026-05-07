# 05 Spec Review Report：github-pr-autonomy-repair-merge

角色：Spec Reviewer  
状态：**PASS**  
仓库：`/root/work/agentic-selfcheck`  
复审时间：2026-05-07 22:58:21 CST

## 复审范围

本次为 Quality/Security Review BLOCK 后的 security fixes 复审。仅复核需求覆盖与报告，不编辑业务代码。已核对：

- `01-requirement.md`
- `04-developer-summary.md`
- `06-quality-review-report.md` 中列出的 BLOCK 项
- 当前工作区实现差异，重点文件：
  - `selfcheck/pr_autonomy.py`
  - `scripts/github_pr_autonomy_repair.py`
  - `scripts/github_pr_autonomy_report.py`
  - `scripts/github_pr_autonomy_webhook_server.py`
  - `scripts/github_pr_autonomy_policy_validate.py`
  - `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`
  - `schemas/pr-autonomy-policy.schema.json`

## 本地验证

已重新执行：

```text
python3 -m py_compile selfcheck/pr_autonomy.py scripts/github_pr_autonomy_webhook_server.py scripts/github_pr_autonomy_report.py scripts/github_pr_autonomy_repair.py scripts/github_pr_autonomy_policy_validate.py
python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace --report reports/github-pr-autonomy-repair-merge/spec-rereview-policy-validate.json
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
```

结果：全部 PASS。策略复审报告写入：`reports/github-pr-autonomy-repair-merge/spec-rereview-policy-validate.json`。

## Security fixes 复核结论

| 前序 BLOCK / Required fix | 复核结论 | 证据 |
|---|---:|---|
| Repair attempt limit 对失败尝试不生效，且并发可绕过限制 | PASS | `scripts/github_pr_autonomy_repair.py` 现对 `(repo, pr)` 使用 `fcntl.flock` 文件锁；在进入实际修复前写入 `STARTED` attempt state，并将 `attempts` 增加到 `attempts + 1`，因此失败尝试也会消耗额度；同一 PR 同时只有一个 repair 临界区，降低共享 worktree 竞态。 |
| 决策层未显式阻断 fork PR | PASS | `selfcheck/pr_autonomy.py` 增加 `head_repo` 归一化；`compute_next_action()` 在 base branch 之后、draft/check/risk/repair/merge 之前阻断 `head_repo != repo_id`，返回 `NEEDS_HUMAN` 且仅有 `COMMENT_ADVISORY`/`REQUEST_HUMAN_REVIEW`，不会产出 `CREATE_REPAIR_DISPATCH` 或 `MERGE_PR`。validator 增加 `fork_pr_needs_human` 覆盖并 PASS。 |
| `repair.execution_enabled` 字段未被执行器/决策使用 | PASS | 决策层在 failed checks repair 分支要求 `repair.enabled && repair.execution_enabled`，否则 `BLOCKED` 且不派发 repair；repair executor 也在执行前再次校验 `execution_enabled`，不满足则报错。validator 增加 `repair_execution_disabled_blocks` 覆盖并 PASS。 |

## Requirement Coverage

| Requirement / Acceptance | 覆盖结论 | 证据 |
|---|---:|---|
| Policy/schema 支持 repair execution 和 merge execution 的显式开关与 guard | PASS | schema/policy 保留并校验 `repair.execution_enabled`、`repair.fixers`、`repair.allowed_risks`、`merge.auto_merge_enabled`、`merge.allowed_methods`、`merge.delete_branch` 以及 defaults auto-merge 配置；validator PASS。此前关于 `execution_enabled` 未强制执行的 caveat 已修复。 |
| Receiver 能在 checks failed 且 policy 允许时触发 bounded repair | PASS | webhook receiver 只在 reporter decision 为 `NEEDS_REPAIR` 且 actions 包含 `CREATE_REPAIR_DISPATCH`、同时 runtime `allow_repair` 打开时调用 `scripts/github_pr_autonomy_repair.py`；由于决策层已纳入 fork 与 `execution_enabled` guard，触发条件仍受 policy 约束。 |
| Repair executor 能 checkout allowlisted repo PR branch、应用低风险修复、commit、push | PASS | repair executor 仍执行 live PR/files/checks reload、allowlisted repo policy lookup、same-repo/fork block、expected/latest head SHA guard、路径 allow/deny、低风险 deterministic fixer（`markdown-marker`/`gofmt`）、`git diff --check`、secret scan、commit/push；新增 per-PR lock 与失败尝试计数，保持 bounded repair 要求。 |
| Reporter 能在 PASS 条件满足且 policy 允许时执行 squash merge | PASS | reporter merge 前 live reload payload 并重新 `dispatch_payload`，要求 original/live head SHA 一致、open/non-draft/same-repo、live decision=`READY_TO_MERGE` 且 action=`MERGE_PR`，并校验 policy merge method；执行 `gh pr merge --squash --delete-branch`。fork PR 已在决策层与执行层双重阻断。 |
| 安全边界：allowlist、非 draft、低风险路径、禁止高风险路径、attempt 上限、latest SHA、防 fork/unknown repo、required checks PASS 后 merge | PASS | allowlist/unknown repo、draft、base branch、high/medium risk、changed-files snapshot、required checks、repair attempt exhausted、repair execution disabled、fork PR 等均由决策层或执行层覆盖；策略验证断言全部为 true。 |
| 真实 GitHub PR 验证 repair + merge 全链路 | PASS | 既有 live 证据仍有效：`mahama-11/platform-backend#3` 从 gofmt CI failure，经 repair commit `8d151c9abd536990de9d90e701c361f506513735` 后 checks PASS，并已 squash merge（merge commit `54066789f414cb07e005c952e093e15c89470d3b`）。本次安全修复未移除该能力，只加强 guard。 |
| SelfCheck validate/audit PASS | PASS | 本次复审重跑 `python3 -m selfcheck validate --root .` 与 `python3 -m selfcheck audit --root .`，均输出 `PASS: no issues`。 |

## Remaining notes / Caveats

1. **生产暴露面 caveat 仍需由 rollout/ops 接受**：webhook 仍建议置于 TLS/反向代理、来源限制、请求体大小限制与速率限制之后；这不改变本 slice 的需求覆盖结论。
2. **secret scan 仍是基础正则扫描**：当前满足“不输出、提交或记录 secret/token/password/API key”的基本控制，但生产级强制 gate 建议接入 gitleaks/trufflehog 或 GitHub secret scanning。
3. **live rollout policy 当前为 `dry_run: false` 且 repair/auto-merge enabled**：符合真实闭环验证目标，但上线范围应继续依赖 allowlisted repo、low-risk、checks、same-repo、runtime env gates 与最小权限 token 控制。
4. **repair failure report 主要写入 attempt state**：失败路径会消耗 attempt 并留下 `STARTED` state；如需更完整可观测性，可后续补充异常捕获并记录 final failure reason，但不阻塞 bounded requirement。

## Spec Reviewer Decision

**PASS**。安全修复后，原先 BLOCK 项从需求覆盖角度已补齐：失败尝试/并发 bounded repair、fork PR 决策层阻断、`repair.execution_enabled` 执行期强制均已覆盖并有 validator 断言。本 slice 对“自动修复并 push fix commit + policy-gated squash auto-merge”的核心需求仍保持覆盖，本地 py_compile、policy validate、SelfCheck validate/audit 均通过。
