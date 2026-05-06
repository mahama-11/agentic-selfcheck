# Architecture Review

Role: architect
Verdict: APPROVE_WITH_NOTES

Decision:
- Pure time loop is not the primary autonomy mechanism.
- Use event callbacks for causality and low latency.
- Keep a low-frequency watchdog loop to catch missed callbacks and stale evidence.

Implemented model:
```text
events/*.yaml -> selfcheck trigger -> feature verifier groups -> reports/events/* -> strict audit
```

Boundary:
- External Hermes webhook subscription is documented but not auto-created because `hermes` CLI is not on PATH in this runtime.
- No webhook secret is stored in repo.
