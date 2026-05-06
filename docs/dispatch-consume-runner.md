# Dispatch Consume Runner

`selfcheck dispatch consume` is the one-shot orchestration boundary for a pending repair dispatch.

It performs:

```text
find OPEN/CLAIMED dispatch
→ claim it
→ write delegate prompt to .hermes/dispatch-runs/<feature>/<run>/delegate_task_prompt.md
→ optionally run an explicit external owner executor command
→ rerun affected SelfCheck groups with strict audit
→ complete only when latest loop report is PASS/PASS_WITH_NOTES
```

Command:

```bash
python3 -m selfcheck dispatch consume \
  --root . \
  --feature ecommerce-product-ai-pipeline \
  --owner developer \
  --actor orchestrator \
  --executor-command 'python3 scripts/test_dispatch_executor.py' \
  --executor-timeout 60 \
  --loop-timeout 300
```

Safety model:

```text
- No shell execution: executor command is parsed with shlex and run as argv.
- No default self-fix: --executor-command is required unless explicit test-only --allow-no-executor is set.
- Prompt/result artifacts are runtime evidence under .hermes/dispatch-runs/ and ignored from git.
- Verification is always SelfCheck loop rerun, not executor self-report.
- Completion requires PASS/PASS_WITH_NOTES verified loop report.
- Runtime path components are sanitized.
- Executor exceptions are converted to structured failure reports instead of silently completing.
```

Hermes integration:

```text
Current Hermes Agent can consume `delegate_task_prompt.md` and call `delegate_task` directly.
A future Hermes CLI runner can be plugged in through --executor-command, provided it reads:
- SELFCHECK_PROMPT_FILE
- SELFCHECK_DISPATCH_PATH
- SELFCHECK_FEATURE
- SELFCHECK_OWNER
- SELFCHECK_ROOT
```

Boundary:

The consume runner makes the lifecycle one-shot and deterministic, but it still preserves role separation: SelfCheck verifies and dispatches; the external executor/Hermes owner performs the fix.
