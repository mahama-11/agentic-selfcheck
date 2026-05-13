# Requirement: Continuous Governance Triggering

## User intent

用户明确指出：治理能力已经准备好，就必须在合适的位置接入使用，不能“准备了 10 个菜没人吃”。

目标是把已落地的 continuous governance 能力打通闭环：

1. 变更事件能触发相关治理 feature；
2. 本地 git hooks 能在合适阶段触发轻量治理；
3. 低频 cron 做兜底巡检；
4. 触发必须防噪音：能 silent 的 silent，需要人决策才通知；
5. 不做破坏性清理，不写 Feishu Base，不输出 secrets。

## Scope

落地：

- `events/continuous-governance-*.yaml` 事件路由；
- `scripts/continuous_governance_trigger.py` 变更路径到治理事件映射；
- `scripts/install_continuous_governance_hooks.py` 安装本地 git hooks；
- 本地 hooks：`pre-push` / `post-merge` 触发治理；
- cron 兜底：每日 compact governance sweep；
- 验证报告与触发证据。

## Acceptance

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/continuous_governance_trigger.py scripts/install_continuous_governance_hooks.py
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 scripts/continuous_governance_trigger.py --root . --changed-file docs/continuous-governance-plan.md --source local --dry-run
python3 scripts/continuous_governance_trigger.py --root . --changed-file scripts/governance_audit.py --source local --dry-run
python3 scripts/continuous_governance_trigger.py --root . --changed-file pitfalls/pit-20260512-sensitive-output-redaction.yaml --source local --dry-run
python3 scripts/continuous_governance_trigger.py --root . --changed-file docs/continuous-governance-plan.md --source local
```

Evidence:

- `.hermes/workflows/continuous-governance-triggering/04-developer-summary.md`
- `.hermes/workflows/continuous-governance-triggering/07-qa-report.md`
- `reports/events/governance.changed.*-latest.json`
- cron job id in final summary
