# Architecture Review

Role: architect
Verdict: APPROVE_WITH_NOTES

Decision:
- Add `selfcheck dispatch consume` as the deterministic outer lifecycle runner.
- The runner claims one open dispatch, writes a delegate prompt, optionally invokes an explicit executor command, reruns affected SelfCheck groups with strict audit, and completes only with verified PASS/PASS_WITH_NOTES evidence.
- Executor command is opt-in and executed as argv without shell.

Boundary:
- The CLI can run an external executor, but the acceptance authority remains SelfCheck rerun evidence, not executor self-report.
