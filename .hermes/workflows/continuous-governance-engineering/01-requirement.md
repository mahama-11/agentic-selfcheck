# Requirement: Continuous Governance Engineering

## User intent

用户明确要求不要停留在 MVP 或规划层，要工程化落地一个长期治理层，覆盖：

1. 项目级治理：
   - 定时/事件触发审查文档实时性、准确性、标准性；
   - 审查代码冗余、死代码、垃圾文件、浅模块、重复逻辑；
   - 支持 safe auto-fix，但删除源代码/行为变更/架构决策需要人确认。
2. 系统自身治理：
   - 治理 Hermes / SelfCheck 产出的 workflow/report/docs；
   - 持续标准化和优化 skills；
   - 踩坑复用：pitfall 必须沉淀为 rule / verifier / skill / doc / accepted risk。

## Scope for this engineering slice

Land the first production-shaped control-plane layer inside `/root/work/agentic-selfcheck`:

- SelfCheck feature contracts:
  - `project-doc-governance`
  - `project-code-health-governance`
  - `hermes-self-governance`
  - `skill-library-governance`
  - `pitfall-feedback-loop`
- Verifiers and executable harness scripts for all five features.
- Pitfall schema and SelfCheck CLI support for pitfall list/audit/add.
- Harness reports for governance features.
- Evidence reports under `reports/<feature>/`.
- Documentation update with commands and operating contract.

## Non-goals for this slice

- No destructive cleanup of source files.
- No automatic deletion of skills.
- No Feishu Base write unless explicitly needed later.
- No cron scheduling yet; first land verifiable feature contracts and executable gates.
- No separate database or second Harness truth source.

## Acceptance

Commands must pass:

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile selfcheck/__main__.py scripts/governance_audit.py
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck run --root . --feature hermes-self-governance --groups static,evidence
python3 -m selfcheck run --root . --feature skill-library-governance --groups static,evidence
python3 -m selfcheck run --root . --feature pitfall-feedback-loop --groups static,evidence
python3 -m selfcheck harness --root . --feature hermes-self-governance --format markdown
python3 -m selfcheck pitfall audit --root .
```

Project governance feature gates should be runnable and generate reports; they may initially PASS_WITH_NOTES when configured with broad workspace targets.

## Evidence paths

- `.hermes/workflows/continuous-governance-engineering/02-architecture-review.md`
- `.hermes/workflows/continuous-governance-engineering/04-developer-summary.md`
- `.hermes/workflows/continuous-governance-engineering/05-spec-review-report.md`
- `.hermes/workflows/continuous-governance-engineering/06-quality-review-report.md`
- `.hermes/workflows/continuous-governance-engineering/07-qa-report.md`
- `.hermes/workflows/continuous-governance-engineering/08-final-verification.md`
- `reports/hermes-self-governance/*`
- `reports/skill-library-governance/*`
- `reports/pitfall-feedback-loop/*`
- `docs/continuous-governance-plan.md`
