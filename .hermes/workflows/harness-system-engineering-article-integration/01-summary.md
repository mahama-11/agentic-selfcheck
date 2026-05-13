# Harness System Engineering Article Integration

## Scope

User provided three localmac WeChat article artifacts and asked to extract valuable design ideas, plan them into Hermes / Agentic SelfCheck / AI 状态账本, and land useful improvements.

## Source acquisition

Copied durable source artifacts from `localmac` into:

```text
.hermes/research/harness-system-engineering-20260512/raw/
```

Extracted text/meta into:

```text
.hermes/research/harness-system-engineering-20260512/extracted/
```

## Extracted system design lessons

See:

```text
docs/harness-system-engineering-lessons.md
```

Key conclusions:

- SelfCheck remains source of truth; Harness is a readable projection and enforceable workflow layer.
- Humans need to read the engineering system, not scattered files.
- Context must be tiered: always-loaded / phase-triggered / on-demand.
- Execution and judgment must stay separated.
- Vague expectations should become executable constraints.
- Pitfalls should become rules, skills, or verifiers.
- High-risk backend/product work needs risk-based and sometimes adversarial review.
- Feishu ledger should stay a human status projection, not an AI session dump.

## Landed implementation

Implemented `selfcheck harness` and `selfcheck init-workflow` in `selfcheck/__main__.py`.

Commands:

```bash
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format markdown
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format json
python3 -m selfcheck init-workflow --root . --feature <feature-id>
```

Generated outputs:

```text
reports/ecommerce-product-ai-pipeline/harness.json
reports/ecommerce-product-ai-pipeline/harness.md
.hermes/workflows/ecommerce-product-ai-pipeline/09-harness-report.md
```

Updated docs:

```text
docs/harness-visualization-integration.md
docs/harness-system-engineering-lessons.md
```

## Verification

```text
python3 -m py_compile selfcheck/__main__.py => PASS
python3 -m selfcheck validate --root . => PASS
python3 -m selfcheck audit --root . => PASS
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format json => PASS
python3 -m selfcheck harness --root . --feature ecommerce-product-ai-pipeline --format markdown => PASS
```

Sample report coverage:

```json
{
  "feature": "ecommerce-product-ai-pipeline",
  "machine_gates": 5,
  "evidence_present": 10,
  "evidence_required": 10,
  "workflow_present": 7,
  "workflow_total": 9,
  "events": 3
}
```

## Next slices

1. Pitfall feedback loop: `schemas/pitfall.schema.json`, `pitfalls/*.yaml`, `verifiers/pitfall-feedback-gate.yaml`, `selfcheck pitfall ...`.
2. Risk-based review trigger: feature `risk_dimensions` routed to required reviewer gates and machine verifiers.
3. Feishu ledger projection: show SelfCheck/Harness status and latest evidence links only for human-facing task mainlines.
