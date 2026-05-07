# Requirement — github-pr-autonomy-live-webhook

## 背景
V workspace 已完成基础 branch -> PR -> CI -> squash merge 流程。现在需要把 GitHub PR 事件接入 Hermes/SelfCheck 控制面，形成可观测、可回写、可逐步开启 repair/auto-merge 的自治闭环。

## Scope
- 在 agentic-selfcheck 中补齐 live webhook dispatcher/reporter 缺口。
- 配置 Hermes webhook/gateway，使 GitHub pull_request / workflow_run 事件能触发 SelfCheck PR autonomy route。
- 为 V workspace 4 个业务 repo 配置 GitHub webhooks：platform-backend、ecommerce-backend、platform-frontend、ecommerce-frontend。
- 启用 PR comment/status/label 回写，默认仍保守：高风险/缺文件/未知 action 人审；repair/auto-merge 仅在 policy 明确允许时执行。
- 提供本地 dry-run、apply-safe、GitHub webhook 配置验证、SelfCheck validate/audit 证据。

## Non-goals
- 不把 agentic-selfcheck 自身纳入强制 PR 审查。
- 不默认放开所有 PR 的自动 merge。
- 不输出或提交任何 webhook secret、GitHub token、API key。
- 不对高风险文件自动修复/合并。

## Acceptance
- Hermes webhook/gateway route 存在且健康检查通过，或如果外部 URL 不可达则有明确可执行的 pending evidence；不得伪称 live。
- 4 个业务 repo GitHub webhook 已创建/更新，事件覆盖 pull_request 与 workflow_run/check 相关触发。
- 对测试 PR/event，SelfCheck dispatcher 能产出 pr_autonomy_decision。
- reporter 能对 GitHub PR 写入 comment/status/labels，且可 dry-run 验证 action plan。
- CI failed 且 policy 允许时进入 bounded repair；不允许时 block/needs human。
- CI success + AI/SelfCheck PASS + policy allow 时才可能 merge；当前默认可保持 auto_merge disabled，但能力 gate 必须可验证。
- SelfCheck validate/audit 与相关 feature gates PASS。

## Safety
- Secret 只存本机 env/config/GitHub webhook secret，不进入 repo。
- 所有日志/报告如涉及 secret 统一写 `[REDACTED]`。
- 先以 V 4 repo 为 allowlist；unknown repo/action block/ignore。
- 所有 GitHub destructive action 需要 policy + CLI explicit flag 双门控。

## Evidence paths
- `.hermes/workflows/github-pr-autonomy-live-webhook/02-architecture-review.md`
- `.hermes/workflows/github-pr-autonomy-live-webhook/04-developer-summary.md`
- `.hermes/workflows/github-pr-autonomy-live-webhook/05-spec-review-report.md`
- `.hermes/workflows/github-pr-autonomy-live-webhook/06-quality-review-report.md`
- `.hermes/workflows/github-pr-autonomy-live-webhook/07-qa-report.md`
- `.hermes/workflows/github-pr-autonomy-live-webhook/08-final-verification.md`
- `reports/github-pr-autonomy-live-webhook/*.json`
