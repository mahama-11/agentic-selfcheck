# Architecture Review: github-pr-autonomy-repair-merge

角色：Architect  
状态：PASS（设计建议）  
范围：仅设计 bounded repair executor 与低风险 auto-merge 闭环；不修改实现代码。

## 1. 目标与原则

本 slice 在现有 GitHub PR autonomy webhook 基础上补齐两个受限能力：

1. 当 allowlisted repo 的非 draft PR required checks 失败，且风险与文件范围满足 policy 时，触发一次有界、确定性的 repair，并 push fix commit。
2. 当 repair 后或普通 PR 的 required checks 全部 PASS，且 policy 与运行时开关均允许时，执行 squash merge 并删除分支。

核心原则：**默认关闭、策略显式开启、只处理低风险、每一步都用 latest head SHA 防漂移、所有写操作可审计且不暴露 secret。**

## 2. 控制流

```text
GitHub webhook
  -> scripts/github_pr_autonomy_webhook_server.py
     1) 验证 X-Hub-Signature-256
     2) 接收 pull_request / workflow_run / check_run
     3) enrich: 获取 PR snapshot、changed files、checks、latest head sha
     4) 写入 redacted raw/enriched evidence
     5) selfcheck trigger route=github-pr-autonomy
     6) selfcheck.pr_autonomy.dispatch_payload(policy, payload, repair_attempts)
        -> repo allowlist / action / base branch / draft gate
        -> changed_files risk classify
        -> required_checks 状态判断
        -> failed checks: NEEDS_REPAIR 或 BLOCKED/NEEDS_HUMAN
        -> passing checks: READY_TO_MERGE 或 READY_FOR_HUMAN
     7) reporter 写 comment/status/labels
     8) 若 state=NEEDS_REPAIR 且 apply + repair runtime gate 允许：调用 repair executor
     9) 若 state=READY_TO_MERGE 且 apply + allow_merge + policy 允许：调用 merge executor
```

### Repair 子流程

```text
NEEDS_REPAIR
  -> reload latest PR via GitHub API
  -> assert repo/base/head/changed_files/checks 与 decision 仍满足 policy
  -> assert current_pr.head.sha == decision.head_sha
  -> assert repair_attempts < max_attempts
  -> checkout isolated worktree/temp clone for owner/repo#PR head branch
  -> run deterministic repair provider only
  -> diff allowlist/denylist/secret scan
  -> run repo-local bounded validation command set
  -> assert latest head sha unchanged again
  -> commit with machine-readable trailer, e.g. Agentic-Repair-Attempt: N
  -> push to PR head branch
  -> comment/status: REPAIRING -> REVERIFYING
  -> wait for GitHub checks via subsequent workflow_run/check_run webhook
```

Repair 不应由通用 LLM 任意改代码驱动；只能执行预注册、可解释、可重复的 fixer，例如文档尾标记、格式化、简单 lint autofix、已知失败模式的最小修复。

### Auto-merge 子流程

```text
READY_TO_MERGE
  -> reload latest PR + combined statuses/check-runs
  -> assert PR open, non-draft, not fork/unknown repo
  -> assert repo allowlisted and base branch allowed
  -> assert current_pr.head.sha == decision.head_sha
  -> assert risk == low and all changed files remain in low-risk scope
  -> assert required_checks all success
  -> assert merge policy enabled and method squash allowed
  -> gh pr merge --squash --delete-branch
  -> record MERGED report/evidence
```

Reporter 可以继续承担 GitHub write-back，但 merge 前必须重新读取 live PR snapshot，不能只相信之前的 enriched payload。

## 3. 安全门禁

必须全部通过才允许自动 repair：

- repo 在 `repositories[].id` allowlist 中。
- PR open、非 draft、base_ref 在 `base_branches` 中。
- 不是 fork PR；只能 push 到同一 owner/repo 的 PR head branch。
- `risk.level == low`；高风险路径、denylist 路径、large diff 一律转人工。
- changed files 全部匹配 `repair.allowed_globs`，且没有任何 `repair.denied_globs` 命中。
- required checks 存在明确失败；missing/pending 不触发 repair。
- `repair_attempts < min(defaults.max_repair_attempts, repositories[].repair.max_attempts)`。
- push 前后都校验 latest `head.sha`，发生漂移立即 BLOCKED/NEEDS_HUMAN。
- repair diff 只能触碰 PR 已变更且 allowlisted 的文件；禁止新增 secret、token、credential、`.env*`。
- dry-run、policy、runtime env/CLI 三层均允许时才执行写操作。

必须全部通过才允许自动 merge：

- repo allowlisted；unknown repo ignored/blocked 但绝不 merge。
- PR open、非 draft、非 fork，base branch allowlisted。
- latest head SHA 与 decision/enriched payload 一致。
- changed files live reload 后仍为 low risk，且不含 denied/high-risk glob。
- `required_checks` 全部 success；pending/missing/failure 均不 merge。
- policy `defaults.auto_merge.enabled=true` 且 repo `merge.auto_merge_enabled=true`。
- `defaults.auto_merge.allowed_risks` 包含 `low`，实际仅建议生产启用 low。
- `merge.allowed_methods` 包含 `squash`，执行时固定 `--squash --delete-branch`。
- 若策略要求 human approval，则必须显式检查 approval 状态；本需求的全自动模式应将该字段改为 false 或增加 override 字段并记录审计。

## 4. Policy / schema 字段建议

现有字段已覆盖基础边界：

- `defaults.dry_run`
- `defaults.unknown_repo`
- `defaults.unknown_action`
- `defaults.high_risk_requires_human`
- `defaults.max_repair_attempts`
- `defaults.auto_merge.enabled`
- `defaults.auto_merge.allowed_risks`
- `defaults.auto_merge.method`
- `repositories[].base_branches`
- `repositories[].required_checks`
- `repositories[].risk.{large_diff_file_limit,high_globs,medium_globs}`
- `repositories[].repair.{enabled,max_attempts,allowed_globs,denied_globs}`
- `repositories[].merge.{auto_merge_enabled,require_human_approval,allowed_methods}`

为完成 acceptance，建议显式扩展以下字段，避免把执行细节藏在代码或环境变量中：

```yaml
defaults:
  repair_execution:
    enabled: false
    push_enabled: false
    require_latest_head_sha: true
    allowed_providers: [deterministic]
    secret_scan: true
  auto_merge:
    enabled: false
    require_latest_head_sha: true
    delete_branch: true
    method: squash

repositories:
  - id: owner/repo
    repair:
      enabled: false
      push_enabled: false
      max_attempts: 1
      allowed_globs: [...]
      denied_globs: [...]
      allowed_fixers: [docs_trailing_marker, formatter]
      validation_commands: []
    merge:
      auto_merge_enabled: false
      require_human_approval: true
      allowed_methods: [squash]
      delete_branch: true
```

Schema 应要求这些字段为显式 boolean/list，不允许 additionalProperties，以防误配置。默认 policy 保持 `dry_run: true`、`repair.enabled: false`、`push_enabled: false`、`auto_merge.enabled: false`、`auto_merge_enabled: false`。

## 5. 执行边界

- **Webhook receiver**：只负责认证、事件归一化、evidence 落盘、调用 SelfCheck route、触发 reporter/repair；不在 HTTP handler 内长期阻塞等待 CI。
- **Policy engine (`selfcheck/pr_autonomy.py`)**：只做确定性决策，输出 state/actions/guards；不直接执行 git push/merge。
- **Repair executor**：独立模块或脚本；在隔离目录 checkout PR head；执行确定性 fixer；做 diff allowlist、secret scan、attempt counter、latest SHA guard、commit/push。
- **Reporter / merge executor**：继续负责 comment/status/labels；merge 前 live reload PR/checks 并执行最终 gate。
- **Evidence**：每次 raw/enriched/decision/repair/merge 均写 reports，所有 payload redacted；记录命令 exit code 和 stderr tail，但禁止记录 token/secret/env。
- **权限**：本 slice 可复用现有 `gh` 权限，但架构上应限制为目标 allowlisted repos 的 contents/status/pull-request 权限；不得把 agentic-selfcheck 自身纳入 auto merge。

## 6. Live validation plan

1. **静态验证**
   - policy schema validate PASS。
   - SelfCheck validate/audit PASS。
   - 单元测试覆盖：unknown repo、draft、high-risk glob、denied glob、attempt exhausted、missing/pending checks、failed checks -> NEEDS_REPAIR、passing checks -> READY_TO_MERGE。

2. **Dry-run webhook 验证**
   - 启动现有 direct public IP webhook，`apply=false` / merge disabled。
   - 用真实或 replay payload 验证 enriched snapshot、risk、required checks、report/comment 不含 secrets。

3. **Repair live 验证**
   - 在 allowlisted 测试 repo 创建低风险 PR（仅 `.md` 或简单格式文件）并故意触发已知 CI 失败。
   - policy 对该 repo 临时开启 repair execution，max_attempts=1。
   - 观察 failed check webhook -> NEEDS_REPAIR -> fix commit push。
   - 验证 commit 只修改 allowed files，包含 repair trailer，无 secret，head SHA guard 生效。

4. **Recheck 与 auto-merge 验证**
   - CI 重新运行并 PASS 后触发 workflow_run/check_run。
   - policy 临时开启 auto_merge，runtime `--allow-merge` 开启。
   - 验证 live gate 重新读取 required checks，执行 `squash` merge 并删除分支。
   - 验证 PR terminal state/report 为 MERGED，comment/status/labels 与 evidence 完整。

5. **负向验证**
   - fork PR、draft PR、high-risk path、workflow path、secret-like 文件、head SHA 漂移、attempt exhausted、required check pending/missing/failure 均不得 push/merge。

## 7. 主要风险与缓解

- **竞态/漂移风险**：PR 在决策与 push/merge 间变化。缓解：执行前 live reload，push/merge 前二次 latest head SHA guard。
- **误修复风险**：自动修复引入行为变化。缓解：仅 deterministic fixer，限定 low-risk 文件，验证命令失败即停止。
- **越权路径风险**：glob 漏配导致 workflow/secret/config 被改。缓解：allowlist 与 denylist 双重检查，denylist 优先，diff 后复核。
- **secret 泄漏风险**：payload、stderr、diff、comment 可能包含敏感信息。缓解：redaction、secret scan、禁止提交/记录 secret-like 内容。
- **检查语义不一致**：GitHub check-runs/statuses 名称变化或 required checks 缺失。缓解：只认 policy `required_checks`；missing 视为 waiting/block，不 merge。
- **自动 merge 误触发**：旧 payload 或 reporter 直接 merge。缓解：merge executor 必须 live reload，不信任缓存 payload；policy + runtime 双开关。
- **循环触发风险**：label/comment/push 引起 webhook 循环。缓解：忽略 label churn；repair attempt trailer/counter；只在 failed checks 且 attempt 未耗尽时触发。
- **分支删除风险**：删除共享分支影响协作。缓解：仅同仓 PR head，非默认分支，merge 后 `--delete-branch`，失败不重试破坏性操作。

## 8. 架构结论

该能力可以在现有 receiver + policy engine + reporter 架构上扩展完成，但执行层必须与决策层分离：policy 只产出 `CREATE_REPAIR_DISPATCH` / `READY_TO_MERGE`，repair/merge executor 在执行前重新加载 live PR 并重复全部安全门禁。默认配置必须保持 dry-run 与执行关闭；只在单个 allowlisted 测试 repo 上逐步打开 repair push 和 squash merge。满足上述 gate 后，可安全完成“失败 PR -> 自动修复 commit -> CI 重跑 -> 自动 squash merge 删除分支”的闭环。
