# SelfCheck Repair Loop

Role: orchestrator

Requirement:
- SelfCheck failures must route to responsible owners instead of being fixed by the verifier itself.
- Fixes must re-enter SelfCheck after implementation/review/QA.
- Loop must continue until PASS/PASS_WITH_NOTES/BLOCKED/ESCALATE.
- Dead-loop guards are mandatory.
