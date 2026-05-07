# Role Model Routing

SelfCheck roles can use different models. The default routing policy is:

```text
role-model-routing/default-role-model-routing.yaml
```

## Model tiers

```text
high_capability_default = openai-codex / gpt-5.5
minimax_highspeed      = minimax-cn / MiniMax-M2.7-highspeed
```

Credentials are stored outside this repository in Hermes environment configuration. Never commit provider keys.

## Routing principle

Use low-cost fast models for deterministic, evidence-reading, checklist, reporting, and status-routing work. Keep high-capability models for architecture, implementation, ambiguous debugging, security-sensitive review, and cross-service decisions.

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
```

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
