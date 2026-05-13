# Architecture Review: Continuous Governance Engineering

Verdict: **APPROVED**

## 结论

同意本 slice 以“SelfCheck 控制平面”方式落地连续治理，而不是做松散 cron/MVP。架构边界清晰：SelfCheck YAML 合约是事实源，`scripts/governance_audit.py` 是可执行治理探针，`reports/<feature>/` 与 Harness/workflow 文档是证据投影；本阶段不引入数据库、Feishu 写入、自动删代码/删 skill。

## 目标架构

```text
features/*.yaml                  # 治理能力合约：范围、must_pass、人工边界、证据要求
verifiers/*.yaml                 # 可执行门禁入口：统一调用治理脚本/CLI
scripts/governance_audit.py      # 五类治理扫描器，输出 json + markdown
schemas/pitfall.schema.json      # 踩坑记录结构约束
pitfalls/*.yaml                  # 踩坑事实源
selfcheck pitfall add/list/audit # 踩坑注册、查询、审计 CLI
reports/<feature>/*              # 每次治理运行证据
.hermes/workflows/.../*.md       # 人类可读工程流证据
```

核心原则：

1. **合约先行**：五个治理 feature 必须都进入 `features/`，通过 `python3 -m selfcheck validate --root .`。
2. **证据先行**：所有 PASS / PASS_WITH_NOTES 都必须落 json/markdown 证据，不能只靠口头总结。
3. **安全优先**：本 slice 只允许报告和极小安全修复；删除源代码、删除 skill、行为变更、Feishu 写入均进入 `human_required`。
4. **单一事实源**：SelfCheck 对象图 + pitfall registry 是事实源；Feishu/文档/报告只是投影。

## 必须新增/修改的文件

### Feature contracts

新增：

- `features/project-doc-governance.yaml`
- `features/project-code-health-governance.yaml`
- `features/hermes-self-governance.yaml`
- `features/skill-library-governance.yaml`
- `features/pitfall-feedback-loop.yaml`

每个 feature 建议字段：

```yaml
id: <feature-id>
project: agentic-selfcheck
description: <治理目标>
level_target: L3.5
repair_policy: default-repair-policy
depends_on:
  - selfcheck-static-verifiers
must_pass:
  static:
    - <feature>-contract-validate
  evidence:
    - <feature>-audit
reviewer_gates:
  - spec-review
  - quality-review
  - final-verification
human_required:
  - destructive cleanup
  - source deletion or broad refactor
  - skill deletion or merge
  - Feishu/Base writes
  - policy change or accepted risk
evidence_required:
  - reports/<feature>/audit.json
  - reports/<feature>/audit.md
```

项目文档/代码健康治理初期可以对宽范围 workspace 产生 `PASS_WITH_NOTES`，但不能空跑 PASS。

### Verifier contracts

新增治理 verifiers，建议至少：

- `verifiers/project-doc-governance-audit.yaml`
- `verifiers/project-code-health-governance-audit.yaml`
- `verifiers/hermes-self-governance-audit.yaml`
- `verifiers/skill-library-governance-audit.yaml`
- `verifiers/pitfall-feedback-gate.yaml`

Verifier 行为：

```yaml
kind: static 或 evidence
command: scripts/governance_audit.py --root . --feature <feature-id> --format both
```

约束：

- 命令必须走 `scripts/` 下专用 harness，符合当前 `selfcheck.__main__.resolve_harness_command` 的安全模型。
- 不允许 generic shell 任意执行。
- 输出必须包含：状态、scope、top findings、auto_fix 摘要、human_required 摘要、证据路径、next action。

### Executable audit script

新增：

- `scripts/governance_audit.py`

推荐 CLI：

```bash
scripts/governance_audit.py --root . --feature hermes-self-governance --format both
scripts/governance_audit.py --root . --feature all --format json
```

推荐输出：

- `reports/<feature>/audit.json`
- `reports/<feature>/audit.md`

统一 JSON 结构：

```json
{
  "feature": "hermes-self-governance",
  "status": "PASS|PASS_WITH_NOTES|NEEDS_REPAIR|NEEDS_HUMAN",
  "scope": "project|system|skills|pitfalls",
  "findings": [
    {
      "severity": "info|warn|error|human",
      "category": "docs|code-health|workflow|skill|pitfall|evidence",
      "path": "...",
      "message": "...",
      "recommended_action": "...",
      "human_required": false
    }
  ],
  "auto_fix": [],
  "human_required": [],
  "evidence": {
    "json": "reports/<feature>/audit.json",
    "markdown": "reports/<feature>/audit.md"
  }
}
```

Status 判定：

- `PASS`：无 error/human finding，证据齐全。
- `PASS_WITH_NOTES`：只有 warn/info，例如未配置具体项目 target、宽范围扫描、可后续增强。
- `NEEDS_REPAIR`：有可由工程修复的 error，例如缺报告、schema 不合法、workflow phase 缺失。
- `NEEDS_HUMAN`：涉及删除、skill 合并/删除、policy/产品承诺/Feishu 写入/accepted risk。

## 五类治理 verifier 行为

### 1. `project-doc-governance`

扫描对象：`README*`、`docs/**/*.md`、`.hermes/workflows/**/*.md`、项目配置文件。

检查：

- 文档命令是否能对应 `package.json` scripts、Makefile、常见启动脚本。
- 文档中的本地路径/报告链接是否存在。
- `PASS`/成功声明是否有证据链接。
- stale/TODO/FIXME/temporary 文案是否需要处理。

本 slice 不要求理解所有业务 API；允许先输出 `PASS_WITH_NOTES`，但必须列出覆盖范围和盲区。

### 2. `project-code-health-governance`

扫描对象：代码树、配置文件、报告/临时文件位置。

检查：

- 明显垃圾文件、重复报告、源目录内临时产物。
- 大文件/浅模块/高风险命名等 AI 可导航性问题。
- 若语言工具存在，只调用已安装命令；不得自动安装依赖。

禁止：删除源代码、改接口、做大重构。此类发现标为 `NEEDS_HUMAN` 或 `NEEDS_REPAIR` 并给证据。

### 3. `hermes-self-governance`

扫描对象：`.hermes/workflows/`、`reports/`、SelfCheck feature/verifier object graph。

检查：

- workflow phase 文件是否完整或有明确缺省理由。
- Harness/report 是否存在、是否和 feature contract 对齐。
- 生成文档是否有 owner/status/evidence，而不是空泛自夸。
- Feishu ledger 仅作为未来投影；本 slice 不写 Feishu。

这是本 slice 的第一优先级，应满足：

```bash
python3 -m selfcheck run --root . --feature hermes-self-governance --groups static,evidence
python3 -m selfcheck harness --root . --feature hermes-self-governance --format markdown
```

### 4. `skill-library-governance`

扫描对象：本地 skill 目录/引用文档/工作流中提到的 skill gap。

检查：

- skill 是否缺 trigger/steps/pitfalls/verification 等基本段落。
- 是否有明显重复或过宽触发范围。
- 是否引用不存在路径或陈旧命令。
- workflow 中 pitfall 是否未沉淀到 skill/rule/verifier/doc。

禁止自动删除/合并 skill；本 slice 可允许给未 pin、本地 skill 追加 pitfall 建议，但默认先只报告。

### 5. `pitfall-feedback-loop`

新增事实源：

- `schemas/pitfall.schema.json`
- `pitfalls/*.yaml`

Schema 必须包含：

```yaml
pitfall_id: string
scope: project|hermes|skill|verifier|docs
symptom: string
evidence_path: string
root_cause: string
prevention_action: rule|verifier|skill|doc|accepted_risk
updated_artifact: string
rerun_evidence: string
status: open|prevented|accepted_risk|obsolete
```

CLI：

```bash
python3 -m selfcheck pitfall list --root .
python3 -m selfcheck pitfall audit --root .
python3 -m selfcheck pitfall add --root . --scope hermes --symptom ... --evidence-path ... --root-cause ... --prevention-action verifier --updated-artifact ... --rerun-evidence ...
```

Gate 行为：

- schema 不合法：`NEEDS_REPAIR`。
- `open` pitfall 没有 prevention action / evidence：`NEEDS_REPAIR`。
- 重复 pitfall 仍无预防动作：final verification 必须 fail 或降级。
- `accepted_risk` 必须有人类决策证据，否则 `NEEDS_HUMAN`。

## 接入当前 SelfCheck CLI 的建议

当前 CLI 已支持 `validate/audit/plan/run/trigger/loop/dispatch/harness/init-workflow`。本 slice 应最小侵入：

1. 保持 `features/` + `verifiers/` 接入 `run`/`harness`。
2. 在 `selfcheck/__main__.py` 增加 `pitfall` 子命令，不影响现有命令。
3. 将治理探针放在 `scripts/governance_audit.py`，通过安全 harness 路径执行。
4. `python3 -m selfcheck audit --root .` 继续负责 evidence_required 存在性；治理脚本负责内容质量扫描。

## 验收命令

必须通过：

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

项目级治理也必须可运行并生成报告；若未配置具体业务项目，可 `PASS_WITH_NOTES`，但不能因为无 target 直接 PASS。

## 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 治理脚本过度主观 | 误报/噪音 | 只做可证据化规则，top 3 findings，宽范围扫描标注 notes |
| 自动清理越权 | 误删代码/skill | 本 slice 默认不删除； destructive/skill deletion 全部 human_required |
| 报告膨胀 | 产生新的 AI 垃圾 | 固定 compact report；raw log 只保留 tail/路径 |
| Feishu 成为第二事实源 | 状态分叉 | 暂不写 Feishu；未来只做 projection |
| pitfall 只登记不闭环 | 复发无法防 | audit gate 要求 prevention_action + rerun_evidence；重复无预防降级/fail |
| verifier 空跑 PASS | 虚假安全 | 所有治理脚本必须输出覆盖范围；无 target 为 PASS_WITH_NOTES |

## 架构审查意见

可以进入开发实现。开发时请优先落地：

1. 五个 feature contract + verifier contract；
2. `scripts/governance_audit.py` 可执行报告；
3. pitfall schema + `selfcheck pitfall list/audit/add`；
4. 运行验收命令并把证据写入 `reports/*` 与后续 workflow phase 文件。

不得在本 slice 做：自动删源代码、自动删/合并 skill、Feishu 写入、读取/写入 secrets、引入第二数据库事实源。
