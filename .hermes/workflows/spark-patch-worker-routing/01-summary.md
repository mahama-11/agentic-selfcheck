# Spark Patch Worker Routing

Status: PASS

## User request

Add GPT-5.3-Codex-Spark into the autonomy / verification system only for narrow, short-chain, strongly constrained, strongly verified work. Mark its weaknesses so it cannot be assigned architecture, complex implementation, review, QA, or final-verdict responsibilities.

## Changes

### Hermes profile

Created profile:

```text
spark-patch-worker
```

Model routing:

```text
provider: openai-codex
model: gpt-5.3-codex-spark
```

Profile guardrails are written in:

```text
/root/.hermes/profiles/spark-patch-worker/SOUL.md
```

The profile explicitly states it is not a main developer, architect, reviewer, QA, or final verifier.

### SelfCheck role-model routing

Updated:

```text
/root/work/agentic-selfcheck/role-model-routing/default-role-model-routing.yaml
/root/work/agentic-selfcheck/docs/role-model-routing.md
/root/work/agentic-selfcheck/scripts/role_model_routing_validate.py
```

Added model key:

```text
codex_spark_patch = openai-codex / gpt-5.3-codex-spark
```

Added role:

```text
spark-patch-worker -> codex_spark_patch, fallback high_capability_default
```

Allowed task classes:

```text
small-patch, lint-fix, typecheck-fix, i18n-fill, fixture-transform, report-normalization, reviewer-requested-repair, test-scaffold
```

Escalation / exclusion conditions include:

```text
architecture, ambiguous-requirement, cross-service-contract, auth, rbac, security-sensitive, billing, wallet, payment, order, subscription, quota, database-migration, production-data, prod-deploy, browser-ambiguity, final-verdict
```

### V workspace docs

Updated:

```text
/root/work/v/AGENTS.md
/root/work/v/docs/HERMES_ENGINEERING_WORKFLOW.md
```

These now list `spark-patch-worker` as a high-speed sub-role with explicit forbidden responsibilities.

## Verification

Commands run:

```bash
python3 scripts/role_model_routing_validate.py --root . --policy default-role-model-routing
python3 -m selfcheck run --root . --feature role-model-routing --groups static --timeout 300
hermes profile list | grep -E 'spark-patch-worker|Profile'
```

Results:

```text
role_model_routing_validate: PASS
SelfCheck role-model-routing static: PASS
Hermes profile visible: spark-patch-worker / gpt-5.3-codex-spark / stopped / alias spark-patch-worker
```

## Operational rule

Spark can speed up local execution, but cannot lower the verification bar. Every Spark diff must go through non-Spark review and/or QA before final PASS.
