# 03 Discovery：GitHub PR 自治 repair executor / auto-merge 代码缺口

角色：Discovery  
范围：只检查当前实现并给 repair executor 与 auto-merge 的修复执行者提供精确缺口；未实现代码。  
仓库：`/root/work/agentic-selfcheck`

## 检查方法

- 阅读 PR 自治核心：`selfcheck/pr_autonomy.py`
- 阅读 live webhook receiver：`scripts/github_pr_autonomy_webhook_server.py`
- 阅读 GitHub reporter：`scripts/github_pr_autonomy_report.py`
- 阅读 policy/schema/validator：
  - `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`
  - `schemas/pr-autonomy-policy.schema.json`
  - `scripts/github_pr_autonomy_policy_validate.py`
- 阅读 SelfCheck event/dispatch 基础设施：
  - `selfcheck/__main__.py`
  - `events/github-pr-autonomy.yaml`
  - `docs/dispatch-consume-runner.md`
- 阅读 webhook hook 同步脚手架：`scripts/github_pr_autonomy_sync_hooks.py`
- 运行验证：`python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace`，结果 PASS。

未读取或记录任何 secret；下文不包含 token/webhook secret/password/API key。

## 当前实现概览

### 1. 已有 flags / policy 开关

位置：`pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`

当前默认值：

```yaml
defaults:
  dry_run: true
  unknown_repo: ignored
  unknown_action: blocked
  high_risk_requires_human: true
  max_repair_attempts: 1
  auto_merge:
    enabled: false
    allowed_risks: [low]
    method: squash
```

每个 repo 当前都有：

```yaml
repair:
  enabled: false
  max_attempts: 1
  allowed_globs: [...]
  denied_globs: [...]
merge:
  auto_merge_enabled: false
  require_human_approval: true
  allowed_methods: [squash]
```

关键含义：

- repair 默认全关闭；即使核心会计算 `NEEDS_REPAIR`，现有真实 policy 不会触发。
- auto-merge 默认全关闭；干净 PR 会进入 `READY_FOR_HUMAN`。
- `dry_run: true` 仍写入 decision，并不阻止 reporter 在 `--apply` 时写 GitHub comment/status/label；它目前只是报告字段和 policy validator 的保守断言。

### 2. 已有 states

位置：`pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`、`selfcheck/pr_autonomy.py`

声明 states 包括：

- `RECEIVED`, `NORMALIZED`, `POLICY_MATCHED`, `SNAPSHOT_LOADED`, `RISK_CLASSIFIED`
- `WAITING_FOR_CHECKS`, `WAITING_FOR_AUTHOR`
- `AI_REVIEW_PENDING`, `AI_REVIEWED`, `VERIFYING`
- `NEEDS_REPAIR`, `REPAIRING`, `REVERIFYING`
- `READY_FOR_HUMAN`, `READY_TO_MERGE`
- `PASS`, `PASS_WITH_NOTES`, `NEEDS_HUMAN`, `BLOCKED`, `IGNORED`, `MERGED`

但当前核心实际只直接返回其中一部分：

- `IGNORED`
- `BLOCKED`
- `WAITING_FOR_AUTHOR`
- `NEEDS_HUMAN`
- `WAITING_FOR_CHECKS`
- `NEEDS_REPAIR`
- `READY_FOR_HUMAN`
- `READY_TO_MERGE`

`REPAIRING`、`REVERIFYING`、`MERGED` 已声明但没有被 live flow 写回为最终 decision state。`TERMINAL_STATES` 常量含 `MERGED`，但核心没有实际生成 `MERGED`。

### 3. 当前 decision/report 格式

核心 decision 由 `selfcheck/pr_autonomy.py::compute_next_action()` 返回，基础字段：

```json
{
  "policy_id": "github-pr-autonomy-v-workspace",
  "repo": "owner/repo",
  "pr": 42,
  "head_sha": "...",
  "dry_run": true,
  "actions": [],
  "state": "...",
  "terminal": true,
  "risk": "unknown or object",
  "reason": "..."
}
```

按状态追加字段：

- checks 缺失/等待：`missing_checks`, `pending_checks`
- checks 失败：`failed_checks`
- repair 相关：`repair_attempts`, `max_repair_attempts`, `denied_files`
- risk object：`{"level": "low|medium|high", "reasons": [...], "files": [...]}`

Reporter 输出位置默认：`reports/github-pr-autonomy/github-pr-autonomy-report.json`；live webhook 会传入每次事件专属路径：

```text
reports/github-pr-autonomy-live-webhook/reports/<event_id>.report.json
```

Reporter report 当前格式：

```json
{
  "status": "PASS",
  "decision": { ... },
  "applied": [ ... ],
  "apply": true,
  "allow_merge": false
}
```

`applied` 会记录 comment/status/label/merge 的 exit code 与 stderr tail。注意：stderr tail 可能含 GitHub CLI 错误上下文；目前没有统一 redaction 函数用于 reporter report。

### 4. 当前 webhook trigger flow

位置：`scripts/github_pr_autonomy_webhook_server.py`

HTTP：

- `GET /health` 返回健康状态。
- `POST /github-pr-autonomy` 或 `/webhooks/github-pr-autonomy` 接 GitHub webhook。
- 需要 `GITHUB_PR_AUTONOMY_WEBHOOK_SECRET`；使用 `X-Hub-Signature-256` 做 HMAC 校验。
- 支持 env/CLI：
  - `GITHUB_PR_AUTONOMY_ROOT` / `--root`
  - `GITHUB_PR_AUTONOMY_HOST` / `--host`
  - `GITHUB_PR_AUTONOMY_PORT` / `--port`
  - `GITHUB_PR_AUTONOMY_APPLY` / `--apply`，默认 true
  - `GITHUB_PR_AUTONOMY_ALLOW_MERGE` / `--allow-merge`，默认 false

事件映射：

- `pull_request`：忽略 `labeled`、`unlabeled`、`closed`，其他 PR action enrich。
- `workflow_run`：尝试从 workflow run 关联 PR，合成 `synchronize` payload。
- `check_run`：尝试从 check run 关联 PR，合成 `synchronize` payload。

Enrichment 会通过 `gh api` 获取：

- PR 当前对象
- PR changed files
- commit check-runs
- legacy statuses
- labels
- latest head sha

处理主流程：

```text
收到 webhook
→ 写 raw redacted payload：reports/github-pr-autonomy-live-webhook/events/*.raw.redacted.json
→ enrich payload，写 *.enriched.json
→ python3 -m selfcheck trigger --event github.pull_request --route github-pr-autonomy ...
→ python3 scripts/github_pr_autonomy_report.py --apply --labels [--allow-merge]
→ 返回 result；失败时另写 *.failure.json
```

`selfcheck trigger` 对 github-pr-autonomy route 会把 `dispatch_payload()` decision 写入 event route report，但不执行 repair，也不执行 merge；实际 GitHub side effect 在 reporter。

Hook 同步脚手架：`scripts/github_pr_autonomy_sync_hooks.py`

- allowlisted repos 硬编码为四个 V workspace repo。
- webhook events：`pull_request`, `workflow_run`, `check_run`。
- secret 从 `GITHUB_PR_AUTONOMY_WEBHOOK_SECRET` 读取，不进 repo。

### 5. Reporter 当前 GitHub 能力

位置：`scripts/github_pr_autonomy_report.py`

已有能力：

- 根据 decision 生成 Markdown comment，marker 为 `## AI PR Autonomy Decision`。
- `--apply` 时 upsert PR comment。
- `--apply` 时写 commit status：context 为 `AI Review / PR Autonomy`。
- `--labels` 时维护 labels：
  - `ai-reviewed`
  - `ai-state:<state>`
  - `risk:<level>`
  - `ai-needs-human` / `ai-waiting-checks` / `ai-needs-repair`
- `--allow-merge` 时，在 `state == READY_TO_MERGE` 且 actions 包含 `MERGE_PR_PLANNED_ONLY` 时执行：

```bash
gh pr merge <pr> --repo <repo> --squash --delete-branch
```

当前 merge 能力的限制：

- 没有二次读取 PR latest head sha 并与 decision/head_sha 比较。
- 没有二次读取 required checks/branch protection/mergeability 状态。
- 没有检查 policy merge method 是否等于实际命令。
- 没有检查 `dry_run`；即 policy `dry_run: true` 时，如果 policy 被打开并传 `--allow-merge`，reporter 代码路径仍可能 merge。
- merge 后 report 仍是 `status: PASS`，不会把 decision state 更新成 `MERGED`。
- 固定 `--squash`，没有按 `defaults.auto_merge.method` 或 repo `allowed_methods` 做映射。

## Repair executor 精确代码缺口

### Gap R1：PR autonomy 的 `CREATE_REPAIR_DISPATCH` 只是 planned action，没有任何执行器消费

位置：`selfcheck/pr_autonomy.py:127-138`

当前 failed checks 且 repair enabled/policy allowed 时只返回：

```json
{
  "state": "NEEDS_REPAIR",
  "actions": ["COMMENT_ADVISORY", "CREATE_REPAIR_DISPATCH"]
}
```

缺口：

- 没有生成 PR 专用 repair dispatch artifact。
- 没有 checkout PR branch。
- 没有执行 bounded repair。
- 没有 commit/push。
- 没有记录 repair run id、base/head sha、attempt、changed files、commit sha。
- 没有把 repair attempt 与 webhook 后续事件持久化关联。

### Gap R2：已有 `selfcheck dispatch consume` 是 SelfCheck feature-loop dispatch，不适配 GitHub PR failed check repair

位置：`selfcheck/__main__.py:465-829`

已有 dispatch consume 生命周期很完整：OPEN/CLAIMED/COMPLETED、executor command、prompt artifact、SelfCheck loop rerun。但它的数据模型来自 `selfcheck loop` 的 verifier failure，而不是 GitHub PR autonomy decision。

缺口：

- `NEEDS_REPAIR` decision 不会调用 `write_dispatch_artifacts()`。
- PR decision 中只有 GitHub `failed_checks`，没有 SelfCheck feature loop failure object，因此无法直接复用当前 artifact parser。
- 当前 consume rerun 的 verification boundary 是 `python3 -m selfcheck loop --feature ... --groups ...`，不是 GitHub PR required checks pass。
- 现有 executor 不具备 git checkout/push PR branch 的参数与 guard。

可复用部分：

- `run_external_executor()` 的 no-shell argv 模式。
- dispatch run artifact 目录 `.hermes/dispatch-runs/...`。
- prompt/env var 模式。
- CLAIMED/COMPLETED meta 思路。

### Gap R3：policy/schema 没有表达 repair executor 类型、允许命令、branch/head guard、commit/push guard

位置：`schemas/pr-autonomy-policy.schema.json`、`pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`

当前 repair schema 只有：

```json
enabled, max_attempts, allowed_globs, denied_globs
```

缺口字段建议由执行者补齐（命名可调整，但需要显式 schema guard）：

- `execution_enabled`：区别“可判定 NEEDS_REPAIR”和“允许真的执行修复”。
- `executor_command` 或 `repair_strategies`：只允许白名单脚本/策略，避免任意 LLM 自由改代码。
- `allowed_failure_patterns` / `allowed_check_names`：只修已知低风险失败类别。
- `require_clean_worktree`。
- `require_head_sha_match`。
- `push_enabled`。
- `commit_message_prefix`。
- `max_changed_files_after_repair`。
- `post_repair_wait_for_ci` 或明确“不等待，由 webhook check_run/workflow_run 回调 re-evaluate”。

### Gap R4：缺少 PR repair attempt 持久化

当前 `repair_attempts` 只从 payload 读取：`payload.get("repair_attempts", 0)`。

live webhook enrichment 不会读取或更新 attempt count，因此真实 webhook 每次失败 check 回调都可能看起来是 attempt 0。

需要插入持久化：

- 位置建议：`reports/github-pr-autonomy-live-webhook/state/` 或 `.hermes/pr-autonomy-state/`。
- key 建议：`repo#pr#head_sha` 或 `repo#pr` 加 latest head sha 字段。
- 记录：attempt count、last repair run id、last repaired head sha、last pushed sha、terminal reason、timestamps。
- 新 commit 后 head sha 会变化，需定义 attempts 是按 PR 累计还是按 failing head 累计；更安全是 PR 累计 + head sha 记录。

### Gap R5：缺少安全 git 操作边界

必须补齐：

- clone/fetch 目标只能是 allowlisted `repo`。
- 禁止 fork PR 或至少要求 `head.repo.full_name == base.repo.full_name`；当前 normalizer 没有暴露 fork/head repo 信息。
- checkout 前确认 PR `state=open`、非 draft、base branch 允许、head sha 等于 decision sha。
- repair 后 `git diff --name-only` 必须仍在 allowed globs 内，且不碰 denied/high-risk globs。
- push 前再次查询 PR latest head sha，确认未漂移。
- commit message 不含 secret/大段日志。
- stdout/stderr/report 统一 redaction。

### Gap R6：webhook receiver 没有 repair trigger 插入点

最安全插入点：`scripts/github_pr_autonomy_webhook_server.py::handle_event()` 中 reporter 之前或之后都可以，但推荐：

```text
enrich payload
→ dispatch_payload 得到 decision
→ 如果 decision.state == NEEDS_REPAIR 且 actions 包含 CREATE_REPAIR_DISPATCH
   → 调用 bounded PR repair executor
   → 写 repair report
   → reporter comment/label/status 更新
→ 否则原流程
```

原因：

- receiver 已经有 enriched payload 路径、repo/pr/head_sha、report dir。
- receiver 已经持有 `apply` flag，可作为 live side effect 总开关。
- repair 执行后需要 reporter 通知 PR 状态。

注意：当前 `handle_event()` 先跑 `selfcheck trigger`，再跑 reporter；如果 repair 插在 reporter 后，PR 上会先标 `ai-needs-repair`，随后 push commit，下一轮 webhook 再更新。若插在 reporter 前，可在同一事件 report 中包含 repair attempt，但仍应让 push 后的新 CI webhook 再决定 merge。

## Auto-merge 精确代码缺口

### Gap M1：核心只返回 `MERGE_PR_PLANNED_ONLY`，没有 live merge action

位置：`selfcheck/pr_autonomy.py:140-148`

当 auto_merge policy 打开且 risk allowed 时返回：

```json
{
  "state": "READY_TO_MERGE",
  "actions": ["COMMENT_ADVISORY", "MERGE_PR_PLANNED_ONLY"],
  "reason": "eligible for future auto-merge phase"
}
```

这保守但不完整：执行层目前靠 reporter 特判 `MERGE_PR_PLANNED_ONLY` 来 merge。

缺口：

- action 名仍是 planned-only，语义与真实 merge 不一致。
- 没有 `MERGE_PR` 执行动作和 policy validator 新断言。
- merge 后没有把 final report 标成 `MERGED`。

### Gap M2：reporter merge gate 太薄

位置：`scripts/github_pr_autonomy_report.py:154-158`

当前只检查三件事：

```python
args.allow_merge
state == "READY_TO_MERGE"
"MERGE_PR_PLANNED_ONLY" in decision["actions"]
```

缺少必须 guard：

- `args.apply` 必须为 true；help 文案说 requires `--apply`，代码没有强制。虽然没有 `--apply` 时 merge block 不进入外层 `if args.apply`，但建议显式断言，避免未来重构踩坑。
- `decision.dry_run` 必须 false 或 policy 有独立 `merge.execution_enabled: true`。
- live 读取 PR：open、非 draft、base/head 未漂移。
- live 读取 latest head sha == decision head_sha。
- live 读取 required checks 全 pass；不能只信 payload/enriched snapshot。
- risk 必须为 low 且没有 high-risk files。
- repo policy `merge.auto_merge_enabled` 与 defaults `auto_merge.enabled` 均 true。
- `require_human_approval` 当前 true；如果仍 true 应禁止 auto-merge，或 schema/policy 要明确 auto-merge 下必须 false。
- merge method 必须在 repo `allowed_methods` 中。
- branch protection/mergeability 未确认；至少在 gh merge 失败时不要吞错，并写明确 BLOCKED/FAIL report。

### Gap M3：schema/policy 没有足够 merge execution guard

当前 merge schema：

```json
auto_merge_enabled, require_human_approval, allowed_methods
```

缺口字段建议：

- `execution_enabled` 或 `live_merge_enabled`：与 eligibility 分离。
- `require_latest_head_sha_match`。
- `require_required_checks_pass`。
- `require_selfcheck_status_context`。
- `delete_branch`。
- `method` per repo 或明确继承 defaults。
- `allowed_actors` / `allowed_sources`（至少限定 receiver source）。
- `block_forks`。

### Gap M4：policy validator 目前强制“merge disabled everywhere”，需要随实现更新

位置：`scripts/github_pr_autonomy_policy_validate.py:110-112`

当前断言：

```python
"merge_disabled_everywhere": policy["defaults"]["auto_merge"]["enabled"] is False and all(r["merge"]["auto_merge_enabled"] is False for r in policy["repositories"]),
"no_live_merge_action": all(action != "MERGE_PR" ...),
"dry_run_enabled": all(result.get("dry_run") is True ...),
```

实施 auto-merge 时必须改测试策略：

- 默认 policy 仍可 disabled，但需要 fixture policy 覆盖低风险可 merge 路径。
- 新增 negative tests：high risk、pending checks、failed checks、draft、wrong base、unknown repo、head drift、dry_run true 均不 merge。
- 新增 reporter dry-run tests：没有 `--apply` 或没有 `--allow-merge` 不 merge。
- 新增 action 语义测试：如果引入 `MERGE_PR`，必须仅在 execution-enabled fixture 中出现。

## Safest insertion points

### A. Policy/schema

1. 先扩展 `schemas/pr-autonomy-policy.schema.json`。
2. 再扩展 `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`，默认仍关闭 live execution。
3. 更新 `scripts/github_pr_autonomy_policy_validate.py`，保持默认 policy conservative，同时增加临时 copy policy fixture 覆盖 repair/merge enabled 分支。

### B. Core decision

位置：`selfcheck/pr_autonomy.py`

- 扩展 `PRAutonomyInput`：建议加入 `head_repo`, `base_repo`, `author_association` 或最少 `head_repo_full_name`，用于 block fork。
- `compute_next_action()`：
  - repair：保留 eligibility；如新增 execution flag，只有 execution enabled 才输出 executable action，否则仍 planned/comment。
  - merge：将 `MERGE_PR_PLANNED_ONLY` 与真实 `MERGE_PR` 分离。
  - 输出结构增加 `guards` 或 `required_live_checks`，让 reporter/executor 可逐项记录。

### C. Receiver

位置：`scripts/github_pr_autonomy_webhook_server.py::handle_event()`

推荐新增步骤：

```text
trigger/audit 后
→ decision = dispatch_payload(root, policy, enriched)
→ maybe_run_repair(decision, enriched, root, event_id, apply)
→ reporter(...)
```

或者为避免双算 decision，可让 reporter 接收 `--decision-file`，但当前没有该接口。

### D. Repair executor

建议新增独立脚本，避免塞进 reporter：

```text
scripts/github_pr_autonomy_repair.py
```

输入：`--root`, `--policy`, `--payload-file`, `--decision-file/inline decision`, `--repo`, `--pr`, `--apply`。

输出 report：

```text
reports/github-pr-autonomy-live-webhook/repairs/<event_id>.repair.json
```

最小安全顺序：

```text
load policy + decision
→ assert state NEEDS_REPAIR + action CREATE_REPAIR_DISPATCH
→ assert apply + execution_enabled + not dry_run
→ gh pr view / api live PR
→ assert allowlisted same-repo PR, open, non-draft, head sha unchanged
→ prepare isolated worktree under reports/tmp or /tmp
→ fetch checkout PR head
→ run only allowlisted deterministic repair strategy
→ inspect git diff names against allowed/denied/high-risk globs
→ commit
→ pre-push live head sha recheck
→ push to PR head branch
→ write redacted report
```

### E. Reporter merge

位置：`scripts/github_pr_autonomy_report.py`

建议把 merge 逻辑抽函数：

```python
maybe_merge(repo, pr, decision, payload, policy, root, apply, allow_merge)
```

并在函数里重新读取 live PR/checks，而不是信任 payload。

## 优先级建议

1. **先修 schema/policy/validator**：增加显式 execution guard，但默认 false。
2. **实现 repair attempt state**：没有 attempt 持久化就不能安全闭环，容易无限 repair。
3. **实现 bounded repair executor 独立脚本**：只支持一种或少数确定性低风险策略。
4. **receiver 接入 repair executor**：只在 `NEEDS_REPAIR` 且 apply/execution enabled 时调用。
5. **加厚 reporter merge gate**：live head/checks/risk/dry_run/method/fork 全检查。
6. **最后打开受控 policy fixture 做真实 PR 验证**；默认 V policy 可继续关闭，按验收 PR 再局部启用。

## 主要风险

- 当前 `repair_attempts` 不持久化是 repair 闭环最大风险。
- 当前 reporter merge gate 没有 latest-head/live-check 二次确认，是 auto-merge 最大风险。
- 当前 policy `dry_run: true` 与 webhook `--apply` 默认 true 语义混合：comment/status/labels 已经 live；merge/repair 必须单独检查 dry_run 或 execution flag。
- 当前 normalizer 没有 fork/head repo 字段；自动 push/merge 前必须补。
- Reporter report 没有统一 redaction；执行 repair/merge 前应复用或抽出 webhook server 的 `redact()`。

## 发现结论

现有实现已经有 PR 事件接收、payload enrichment、policy decision、comment/status/label reporter、planned repair/merge states，以及通用 SelfCheck dispatch consume runner。但 **repair executor 尚未接入 PR autonomy**，`CREATE_REPAIR_DISPATCH` 只是计划动作；**auto-merge 只有薄 reporter 命令路径**，缺少最新 SHA、checks、dry-run、fork、method、branch protection 等关键 guard。最安全修复方向是新增独立 PR repair executor，扩展 policy/schema execution guard，并把 receiver 作为 repair 调度点、reporter 作为最终 merge gate。