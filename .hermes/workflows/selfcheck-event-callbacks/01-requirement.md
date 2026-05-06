# SelfCheck Event Callback Routing

Role: orchestrator

Requirement:
- Continue beyond timer-based loop.
- Decide whether loop is a good primary mechanism.
- Add an event-callback-first routing model with watchdog fallback.
- Keep external webhook setup secret-free and explicit.
