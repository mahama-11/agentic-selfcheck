# Harness System Engineering Lessons for Hermes / Agentic SelfCheck

Source artifacts:

- Article 1: `Harness 工程可视化：在 Vibe Coding 中重建工程可控性`
  - Extracted: `.hermes/research/harness-system-engineering-20260512/extracted/article0_visualization.txt`
- Article 2: `Harness Engineering：耗时一周，我是如何将应用的 AI Coding 率提升至 90% 的`
  - Extracted: `.hermes/research/harness-system-engineering-20260512/extracted/article1_90pct_ai_coding.txt`
- Article 3: `Harness Engineering：AI 能在真正“出事会炸”的后端系统里写代码吗？`
  - Extracted: `.hermes/research/harness-system-engineering-20260512/extracted/article2_backend_blast_radius.txt`
- Existing integration note: `docs/harness-visualization-integration.md`

## Core judgment

Do not build a parallel Harness product first. Agentic SelfCheck is already our control-plane source of truth. The useful landing is to make SelfCheck more readable, enforceable, and self-improving:

```text
SelfCheck contracts/verifiers/evidence = source of truth
Harness renderer/report               = human-readable projection
Workflow folders                       = durable change/audit trail
Pitfall registry                       = recurrence-prevention loop
Feishu state ledger                    = human status projection only
```

## Design lessons worth absorbing

### 1. Humans must read the system, not only files

Article 1's strongest point is not visualization aesthetics. It is the shift from "read scattered config files" to "read the engineering system": lifecycle stages, rules, gates, evidence, events, loops, and missing coverage need to be visible in one graph/report.

SelfCheck mapping:

```text
Routa lifecycle view      → `selfcheck harness` report
Spec / ADR / hooks        → features / capabilities / verifiers / events / loops
Review Trigger            → reviewer_gates + risk dimensions + verifier groups
Fitness                   → coverage score: gates/evidence/role handoffs/events/loops
Feedback                  → reports + workflow evidence + repair dispatch + pitfall updates
```

### 2. Context must be tiered, not dumped

Article 2's L1/L2/L3 context architecture maps cleanly to Hermes:

```text
L1 Always Loaded   → AGENTS.md, stable invariants, durable user preferences, project adapter
L2 Phase Triggered → role skills: architect, developer, spec reviewer, quality reviewer, QA, final verifier
L3 On Demand       → docs/wiki/references/code/runtime reports loaded only when the stage requires them
```

This reinforces current skill loading and role pipeline rules. It also explains why SelfCheck should render paths and source objects instead of copying everything into a giant prompt.

### 3. Execution and judgment must remain separate

All three articles converge on this: agents cannot reliably evaluate their own work. Our existing strict role pipeline is aligned:

```text
Developer != Spec Reviewer != Quality Reviewer != QA != Final Verifier
```

The next improvement is not "more self-confidence"; it is better machine gates, risk routing, and evidence-based final verification.

### 4. Vague expectations do not constrain agents

Article 3's examples are directly applicable:

```text
Weak:  写高质量代码 / 注意安全 / 记得测试
Strong: billing changes require quota/metering verifier; tests must have total_tests > 0; high-risk backend changes require quality-review + QA + final-verification evidence.
```

SelfCheck must prefer executable gates over prose. Documentation-only rules should be labeled `DOCUMENTED_ONLY`, not treated as enforced control.

### 5. Pitfalls must become rules, skills, or verifiers

The reusable loop is:

```text
failure observed
→ pitfall record with evidence
→ root cause classification
→ preventive rule/verifier/skill/doc update
→ rerun affected gate
→ final verifier confirms recurrence is blocked
```

This is the most valuable long-term design from the articles. It prevents repeated AI mistakes from becoming tribal memory.

### 6. High-risk backend/product work needs adversarial review

For security, billing/quota, auth/RBAC, data migration, public API, runtime callbacks, storage/assets, and cross-service boundaries, single-pass review is not enough. SelfCheck should route those dimensions to stricter reviewer/verifier groups and optionally multi-model/adversarial review.

### 7. Watch the meta-failure modes

Article 3 explicitly names risks we also have:

- document explosion: too many generated files for humans to read;
- AI confidence contagion: polished reports can lower scrutiny;
- false positives: more review does not automatically mean better signal;
- skill/rule bloat: every rule should justify its enforcement value.

Therefore Harness reports should summarize coverage and missing gates, not generate another wall of prose.

## Landing priorities

### P0 landed now: readable SelfCheck Harness projection

Implemented commands:

```bash
python3 -m selfcheck harness --root . --feature <feature-id> --format markdown
python3 -m selfcheck harness --root . --feature <feature-id> --format json
python3 -m selfcheck init-workflow --root . --feature <feature-id>
```

Generated files:

```text
reports/<feature-id>/harness.json
reports/<feature-id>/harness.md
.hermes/workflows/<feature-id>/09-harness-report.md   # if workflow dir exists
```

The report labels:

- `ENFORCED_MACHINE_GATE`
- `ROLE_GATE`
- `HUMAN_BOUNDARY`
- `EVIDENCE_REQUIRED`
- `MISSING_OR_STALE`

### P1 next: pitfall registry and gate

Add:

```text
schemas/pitfall.schema.json
pitfalls/*.yaml
verifiers/pitfall-feedback-gate.yaml
selfcheck pitfall add/list/audit
```

Acceptance:

- repeated failure without prevention action fails/downgrades final verification;
- each pitfall links evidence, root cause, preventive action, rerun report;
- valid prevention actions: rule, verifier, skill, doc, accepted-risk.

### P1 next: risk-based review trigger

Add `risk_dimensions` to feature contracts, with dimensions such as:

```text
security, billing, quota, metering, auth, rbac, data-migration, public-api,
runtime-callback, asset-storage, cross-service-boundary, deployment, production-data
```

Acceptance:

- high-risk dimensions require specific reviewer gates and machine verifiers;
- generic review cannot pass sensitive product/backend changes;
- final verifier cites the risk-triggered evidence.

### P2: Feishu ledger as Harness projection

Feishu Base should show human-readable task state and latest harness/evidence links. It must not become another source of truth and must not record AI automation chatter as user tasks.

### P2: anti-document-explosion summarizer

Add compact report summaries and stale/missing evidence views so humans see control gaps first, not every generated paragraph.

## Non-goals

- Do not clone Routa UI before the object model and report are useful.
- Do not store a second truth copy outside SelfCheck.
- Do not treat generated docs as evidence unless they are connected to a gate.
- Do not expand Feishu ledger back into AI session logging.
