# Role Model Routing

SelfCheck roles can use different models. The default routing policy is:

```text
role-model-routing/default-role-model-routing.yaml
```

## Model tiers

```text
high_capability_default = openai-codex / gpt-5.5
minimax_highspeed      = minimax-cn / MiniMax-M2.7-highspeed
codex_spark_patch      = openai-codex / gpt-5.3-codex-spark
```

Credentials are stored outside this repository in Hermes environment configuration. Never commit provider keys.

## Routing principle

Use low-cost fast models for deterministic, evidence-reading, checklist, reporting, and status-routing work. Keep high-capability models for architecture, implementation, ambiguous debugging, security-sensitive review, and cross-service decisions.

Use `codex_spark_patch` only as a narrow patch worker: short, low-risk, strongly constrained code edits or mechanical transformations that will be rechecked by a non-Spark reviewer/QA gate. Spark must not own final correctness.

## Default role mapping

```text
orchestrator      -> high_capability_default, fallback minimax_highspeed
architect         -> high_capability_default
developer         -> high_capability_default
spec-reviewer     -> minimax_highspeed, fallback high_capability_default
quality-reviewer  -> high_capability_default, fallback minimax_highspeed
qa                -> minimax_highspeed, fallback high_capability_default
final-verifier    -> minimax_highspeed, fallback high_capability_default
reporter          -> minimax_highspeed, fallback high_capability_default
spark-patch-worker -> codex_spark_patch, fallback high_capability_default
```

## Spark patch worker boundary

`GPT-5.3-Codex-Spark` is admitted only as `spark-patch-worker`. It is intentionally a sub-role, not a replacement for `developer`.

Allowed examples:

```text
- reviewer-requested small patch
- typecheck/lint/format fix
- i18n key fill
- small component extraction under existing design
- CSV/JSON fixture transform
- report normalization / redaction
- test scaffold draft
```

Hard exclusions:

```text
- architecture or domain boundary decisions
- auth/RBAC/security-sensitive work
- billing/wallet/payment/order/subscription/quota logic
- database migration or production data mutation
- prod deploy or rollback decision
- spec/quality/QA/final verification verdicts
- ambiguous debugging or cross-service contract design
```

Admission checklist:

```text
changed_files <= 5
expected_runtime <= 20 minutes
explicit target files and forbidden changes
explicit validation command
non-Spark reviewer or QA must recheck
safe rollback path exists
```

If any checklist item fails, route to `developer` or `high_capability_default` instead.

## Escalation examples

Low-cost roles must escalate to high-capability model when:

```text
- evidence is missing or contradictory
- requirement is ambiguous
- PR is high risk
- task touches auth/payment/billing/production config/secrets
- human product decision is required
```

## Validation

```bash
python3 scripts/role_model_routing_validate.py --root . --policy default-role-model-routing
python3 -m selfcheck run --root . --feature role-model-routing --groups static --timeout 300
```
