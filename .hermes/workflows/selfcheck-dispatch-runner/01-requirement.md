# Dispatch Runner Requirement

Role: orchestrator

Requirement:
- Continue after bounded repair loop by adding a consumption interface for dispatch artifacts.
- SelfCheck should list/plan/claim/complete dispatches.
- The CLI must not directly call Hermes tools or silently patch implementation code.
- Orchestrator must verify fixes by rerunning SelfCheck before marking completion.
