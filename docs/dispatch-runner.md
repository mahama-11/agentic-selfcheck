# Dispatch Runner

`selfcheck loop` creates owner dispatch artifacts when a verifier fails. `selfcheck dispatch` is the consumption interface for an orchestrator/Hermes runtime.

## Lifecycle

```text
OPEN
→ CLAIMED
→ owner fixes in correct role
→ selfcheck loop reruns
→ COMPLETED / CANCELLED
```

Commands:

```bash
# list open dispatches
python3 -m selfcheck dispatch list --root . --feature ecommerce-product-ai-pipeline

# produce a delegate_task-ready prompt for the first matching dispatch
python3 -m selfcheck dispatch plan --root . --feature ecommerce-product-ai-pipeline --owner developer

# claim before handing to an agent
python3 -m selfcheck dispatch claim --root . --path .hermes/dispatch/<feature>/<file>.md --actor orchestrator

# complete after fix + rerun evidence exists
python3 -m selfcheck dispatch complete \
  --root . \
  --path .hermes/dispatch/<feature>/<file>.md \
  --actor developer \
  --result "fixed; loop rerun passed" \
  --verified-report reports/loops/<feature>/latest.json
```

## Orchestrator integration

The CLI intentionally does not call model/tool APIs directly. The Hermes orchestrator should:

1. Run `selfcheck dispatch plan`.
2. Read `delegate_task_prompt` from JSON output.
3. Call `delegate_task` with the requested role/toolsets.
4. Verify the subagent result by running the requested `selfcheck loop` command itself.
5. Mark the dispatch `complete` only with `--verified-report` pointing to a PASS/PASS_WITH_NOTES loop report.

Lifecycle guards:
- `complete` requires a prior `CLAIMED` state unless forced.
- `complete` requires `--result` and `--verified-report` unless forced.
- closed dispatches are hidden by default.
- corrupt sidecar JSON is surfaced as `CORRUPT` instead of silently reopening.

## Boundary

SelfCheck remains the control plane. It may list, plan, claim, complete, and cancel dispatches. It must not silently patch implementation code while acting as verifier.
