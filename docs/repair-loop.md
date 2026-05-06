# Repair Loop

Agentic SelfCheck is a verifier/control plane, not the implementation worker.

```text
run verifiers
→ classify failures
→ dispatch owner assignment
→ owner fixes in implementation role
→ reviewer/QA gates rerun
→ selfcheck loop reruns
→ PASS / PASS_WITH_NOTES / BLOCKED / ESCALATE
```

## Command

```bash
python3 -m selfcheck loop \
  --root . \
  --feature ecommerce-product-ai-pipeline \
  --groups static,api,browser \
  --strict-audit \
  --timeout 300
```

## Terminal states

```text
PASS
  All required verifier groups and strict evidence audit pass. Loop state resets.

PASS_WITH_NOTES
  Selected verifier groups pass, but this was a partial rerun or strict audit was not requested. This does not clear full feature loop state.

NEEDS_REPAIR
  Failure is bounded and dispatch artifacts were created for the responsible owner.

BLOCKED
  Attempts exhausted, repeated same failure, human boundary, secret/permission/product tradeoff, or other escalation condition.
```

## Dispatch artifacts

Failures are written to:

```text
.hermes/dispatch/<feature-id>/<timestamp>-attempt-<n>-<owner>.md
```

The dispatch file tells the owner:
- which verifier failed
- where evidence is stored
- why it failed
- what role owns the next action
- which reviews must run after the fix

## Anti-self-review rule

SelfCheck may classify and dispatch, but must not patch implementation code while acting as verifier.

Developer fixes must return through:

```text
spec-reviewer → quality-reviewer → QA → final-verifier
```

## Loop guards

Defined in `repair-policies/default-repair-policy.yaml`:

```text
max_attempts: 3
same_failure_limit: 2
```

When guards trip, SelfCheck stops with `BLOCKED` instead of looping forever.

Empty group selections are rejected. A partial group rerun cannot produce full-feature `PASS`.
