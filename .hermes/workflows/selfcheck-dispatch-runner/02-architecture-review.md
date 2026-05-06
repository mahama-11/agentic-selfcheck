# Architecture Review

Role: architect
Verdict: APPROVE_WITH_NOTES

Decision:
- Dispatch artifacts remain filesystem-based under `.hermes/dispatch/` and are ignored from git.
- `selfcheck dispatch plan` emits JSON containing a `delegate_task_prompt` instead of invoking model/tool APIs from the CLI.
- `claim`/`complete` use sidecar JSON metadata so artifact content remains immutable evidence.
- Completion is an orchestrator action after independent verification, not a subagent self-report.

Boundary:
- Real `delegate_task` invocation remains in Hermes runtime/orchestrator layer.
