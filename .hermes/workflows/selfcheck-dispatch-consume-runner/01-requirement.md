# Dispatch Consume Runner Requirement

Role: orchestrator

Requirement:
- Stop requiring user to approve every deterministic next step.
- Provide one-shot dispatch consumption: claim → owner executor/delegation → SelfCheck rerun → verified complete.
- Preserve boundary: SelfCheck does not silently self-fix; external executor is explicit opt-in.
- Stop only on PASS/PASS_WITH_NOTES/BLOCKED or human decision boundary.
