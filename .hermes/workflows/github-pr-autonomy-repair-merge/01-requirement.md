# Requirement: github-pr-autonomy-repair-merge

Role: Orchestrator
Status: OPEN

## User ask
完善 GitHub PR 自治闭环中最后两个能力：

1. 自动修复并 push fix commit。
2. 自动 merge。

## Scope
- 在 agentic-selfcheck 控制面内实现 bounded repair executor。
- 在 live webhook receiver 中接入 repair trigger。
- 在 GitHub reporter 中接入低风险 auto-merge gate。
- 更新 V workspace policy，使能力默认仍受严格安全边界控制。
- 用真实 GitHub PR 验证：失败 PR -> 自动修复 commit -> CI 重新跑 -> 自动 squash merge。

## Safety boundaries
- 仅 allowlisted repos。
- 仅非 draft PR。
- 仅低风险文件范围。
- 禁止 workflow、auth、secret、billing/payment、migration、prod config 等高风险路径自动修复/合并。
- repair attempt 有上限，默认 1 次。
- 只修复确定性、低风险、可脚本化类别，例如 docs trailing marker / formatting / simple known CI failures。
- repair 必须基于 latest head SHA；push 前检查 PR head 未漂移。
- auto-merge 必须在 required checks PASS、risk=low、policy enabled、latest head 一致、不是 fork/unknown repo 情况下才允许。
- merge method: squash；合并后删除分支。
- 不输出、提交或记录任何 secret/token/password/API key。

## Acceptance
- Policy/schema 支持 repair execution 和 merge execution 的显式开关与 guard。
- Receiver 能在 checks failed 且 policy 允许时触发 bounded repair。
- Repair executor 能 checkout allowlisted repo PR branch、应用低风险修复、commit、push。
- Reporter 能在 PASS 条件满足且 policy 允许时执行 squash merge。
- 真实 PR 验证 repair + merge 全链路。
- Spec Review、Quality/Security Review、QA、Final Verification 均 PASS。
- SelfCheck validate/audit PASS。

## Non-goals
- 不开放任意 LLM 自由改代码。
- 不对高风险文件自动修复或合并。
- 不将 agentic-selfcheck 自身纳入自动 merge。
- 不处理生产级 GitHub App 最小权限迁移；本 slice 仅在现有 gh 权限基础上闭环。
