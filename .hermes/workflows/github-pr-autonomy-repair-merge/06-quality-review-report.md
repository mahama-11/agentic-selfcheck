# 06 Quality/Security Re-review Report

结论：**PASS**

复审范围：针对上一轮 Quality/Security Review 的 3 个 BLOCK 项进行定向复核；未修改业务代码，仅生成本报告。

## 复核结果

### 1. 修复尝试次数未计入失败尝试 / 并发绕过

**状态：PASS**

证据：

- `scripts/github_pr_autonomy_repair.py` 在 `repair()` 中使用按 repo/PR 状态文件派生的 `.lock` 文件，并通过 `fcntl.flock(..., LOCK_EX)` 将同一 PR 的修复流程串行化。
- `_repair_locked()` 在进入实际 worktree/修复/提交/推送前读取 attempts，并先写入 `STARTED` 状态，`attempts = attempts + 1`，随后才执行可能失败的变更操作。
- 成功路径继续以同一 attempts 值保存 PASS 结果；因此成功与失败后的重试都会消耗同一预算，避免“失败不计数”。
- 决策层仍以 `repair_attempts >= max_attempts` 返回 `BLOCKED`，验证脚本覆盖 `repair_exhausted_blocked`。

### 2. fork PR 未在决策层阻断

**状态：PASS**

证据：

- `selfcheck/pr_autonomy.py` 的 `PRAutonomyInput` 已加入 `head_repo`，事件归一化从 `pull_request.head.repo.full_name` 或 `payload.head_repo` 读取。
- `compute_next_action()` 在 base branch 校验后、draft/风险/检查/repair/merge 前执行 fork 判断：当 `head_repo` 存在且不等于目标 `owner/repo` 时返回 `NEEDS_HUMAN`、`terminal: true`，并只给出 advisory / human review 动作。
- 修复执行层也保留二次防线：`scripts/github_pr_autonomy_repair.py` 在执行前校验 `pr.head.repo.full_name == repo`，否则抛出 `fork PR repair is not allowed`。
- 验证脚本新增并通过 `fork_pr_needs_human` 断言。

### 3. `repair.execution_enabled` 未强制执行

**状态：PASS**

证据：

- `selfcheck/pr_autonomy.py` 在 failed checks 且 `repair.enabled` 为 true 时，先检查 `repair.execution_enabled`；为 false 时直接返回 `BLOCKED`，动作仅为 `COMMENT_ADVISORY`，不会生成 repair dispatch。
- `scripts/github_pr_autonomy_repair.py` 在执行层再次检查 `repair_cfg.get("execution_enabled", False)`；为 false 时抛出 `repair execution is disabled by policy`。
- schema 已接受 `repair.execution_enabled` 字段，当前 policy 中默认修复配置显式设置 `execution_enabled: true`。
- 验证脚本新增并通过 `repair_execution_disabled_blocks` 断言。

## 实际验证

已执行：

```bash
python3 scripts/github_pr_autonomy_policy_validate.py --root /root/work/agentic-selfcheck --policy github-pr-autonomy-v-workspace
python3 -m py_compile selfcheck/pr_autonomy.py scripts/github_pr_autonomy_repair.py scripts/github_pr_autonomy_policy_validate.py
systemctl --no-pager --type=service --all | grep -i 'pr-autonomy\|github'
```

结果：

- policy validate：**PASS**，全部断言为 true，包括：
  - `fork_pr_needs_human`
  - `repair_execution_disabled_blocks`
  - `repair_exhausted_blocked`
  - `repairable_path_dispatches`
- Python 编译检查：**PASS**。
- 服务状态：`agentic-selfcheck-github-webhook.service` 为 `loaded active running`。
- 额外定向探针确认：fork -> `NEEDS_HUMAN`，attempt 0 -> `NEEDS_REPAIR`，attempt 1/max=1 -> `BLOCKED`，execution disabled -> `BLOCKED`。

## 残余 caveats / 风险说明

- 并发保护基于本机 `fcntl.flock` 和本地文件系统；这能覆盖当前单机 systemd 服务形态，但若未来扩展为多主机/容器多副本，需要外部一致性锁或共享状态存储。
- `STARTED` 预写会按设计消耗失败尝试预算；若失败发生在预写之后但未生成详细 failure report，排障主要依赖 repair-state 文件与服务日志。
- fork 判断依赖 webhook/API payload 中 `pull_request.head.repo.full_name` 的准确性；执行层已有同样校验作为纵深防御。
- 本次复审为静态代码检查 + 本地验证脚本/探针验证，未对真实 GitHub PR 进行端到端破坏性演练。

## 最终结论

上一轮 3 个 BLOCK 项均已修复并有验证覆盖。当前无新的阻断性质量或安全问题。

**最终状态：PASS**
