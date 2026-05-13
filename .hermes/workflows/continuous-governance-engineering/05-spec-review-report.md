# Spec Review Report: Continuous Governance Engineering

## 结论

**Verdict: APPROVE**

本次复审确认上一轮两个规格阻塞项均已闭合：治理 verifier 已具备 fail-closed 门禁语义，pitfall contract 已显式采用并要求 `pitfall_id`。当前实现满足 continuous-governance-engineering 的规格要求，可进入后续最终验收/合并流程。

## 复审范围

- `verifiers/project-doc-governance-audit.yaml`
- `verifiers/project-code-health-governance-audit.yaml`
- `verifiers/hermes-self-governance-audit.yaml`
- `verifiers/skill-library-governance-audit.yaml`
- `verifiers/pitfall-feedback-gate.yaml`
- `schemas/pitfall.schema.json`
- `selfcheck/__main__.py` 中 pitfall add/list/audit 相关逻辑
- `pitfalls/*.yaml` 新增样例记录
- `scripts/governance_audit.py` 的 `--fail-on-needs` 行为

## 阻塞项复核

### Blocker 1：治理 verifier 未使用 `--fail-on-needs`

**状态：已解决。**

五个治理 verifier command 均已追加 `--fail-on-needs`：

- `project-doc-governance-audit`
- `project-code-health-governance-audit`
- `hermes-self-governance-audit`
- `skill-library-governance-audit`
- `pitfall-feedback-gate`

验证结果：在临时副本中构造合法但会产生 `NEEDS_REPAIR` 的 pitfall 记录后运行：

```bash
python3 -m selfcheck run --root <tmp-repo> --feature pitfall-feedback-loop --groups static --timeout 300
```

结果为 `FAIL: pitfall-feedback-gate` 且退出码非 0，确认 governance report 的 `NEEDS_REPAIR` 已能阻断 SelfCheck gate。

### Blocker 2：pitfall schema 缺少必需字段 `pitfall_id`

**状态：已解决。**

`schemas/pitfall.schema.json` 现在同时要求：

- `id`
- `pitfall_id`

且 `pitfall_id` 已定义字符串 pattern。`selfcheck pitfall add` 会同时写入 `id` 与 `pitfall_id`。新增的三条 pitfall 记录均包含 `pitfall_id`：

- `pit-20260512-governance-verifier-fail-closed`
- `pit-20260512-pitfall-id-contract`
- `pit-20260512-sensitive-output-redaction`

验证结果：在临时副本中删除 pitfall 记录的 `pitfall_id` 后，SelfCheck run 会因 schema required 校验失败而非 0 退出，确认字段已成为强制 contract。

## 回归验证

在 `/root/work/agentic-selfcheck` 执行以下命令，均通过：

```bash
python3 -m py_compile selfcheck/__main__.py scripts/governance_audit.py
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck pitfall audit --root .
python3 -m selfcheck run --root . --feature pitfall-feedback-loop --groups static,evidence --timeout 300
python3 -m selfcheck run --root . --feature project-doc-governance --groups static,evidence --timeout 300
python3 -m selfcheck run --root . --feature project-code-health-governance --groups static,evidence --timeout 300
python3 -m selfcheck run --root . --feature hermes-self-governance --groups static,evidence --timeout 300
python3 -m selfcheck run --root . --feature skill-library-governance --groups static,evidence --timeout 300
```

当前五个治理 feature 的 SelfCheck verifier 均 PASS。

## 规格判断

| 需求点 | 复审结果 | 说明 |
| --- | --- | --- |
| 五个治理 feature contracts | 通过 | feature/verifier/report 链路存在并可运行。 |
| 可执行 gates | 通过 | `--fail-on-needs` 已接入治理 verifier，`NEEDS_REPAIR` / `NEEDS_HUMAN` 可转为门禁失败。 |
| pitfall schema contract | 通过 | `pitfall_id` 已 required，CLI add 会写入该字段。 |
| pitfall 样例与反馈闭环 | 通过 | 已新增三条 pitfall 记录，并通过 pitfall audit。 |
| 证据报告 | 通过 | governance audit 与 SelfCheck run 均生成报告证据。 |
| 安全边界 | 通过 | 未发现自动删除源代码/skill 或 Feishu/Base 写入行为。 |

## 最终判断

**APPROVE**

上一轮规格阻塞项已修复并完成回归验证。当前实现满足 continuous-governance-engineering 的工程化门禁、pitfall contract 与证据链要求。