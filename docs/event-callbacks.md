# Event Callback Wiring

Agentic SelfCheck should be **event-first, watchdog-backed**.

```text
Primary trigger: event callback
Fallback: low-frequency watchdog loop
```

## Why not only loops?

A blind time loop is useful as a safety net, but it is not the best primary autonomy mechanism:

- It burns compute when nothing changed.
- It detects failures late.
- It can repeatedly act on stale state.
- It makes cause/effect weak: a report says something failed, but not which change triggered it.

## Why event callbacks are better as the primary path

Callbacks fire when something meaningful happens:

```text
git commit / PR opened / CI failed / feature acceptance changed / reviewer requested changes / runtime alert
```

That gives:

- lower latency
- lower cost
- better causality
- smaller verifier scope
- easier escalation and idempotency

## Hybrid policy

```text
Event callback:
  Runs targeted verifier groups for the affected feature.

Watchdog loop:
  Runs periodically to catch missed events, stale evidence, dead services, or broken subscriptions.
```

## Local event dispatch

```bash
scripts/event-dispatch.sh . feature.changed.ecommerce-product-ai-pipeline
python3 -m selfcheck trigger --root . --event feature.changed.ecommerce-product-ai-pipeline --source local
```

Event routes can restrict `allowed_sources` and define `debounce_seconds`; `selfcheck trigger` enforces both before running verifiers.

## Watchdog fallback

```bash
scripts/workflow-health-loop.sh .
```

The existing Hermes cron job should run only the watchdog fallback, not replace event callbacks.

## Hermes webhook scaffold

`hermes` CLI is not currently on this server PATH, so the subscription was not created automatically. When available, create a webhook route like:

```bash
hermes webhook subscribe agentic-selfcheck-events \
  --events "push,pull_request,workflow_run" \
  --description "Route GitHub/CI events to Agentic SelfCheck" \
  --prompt "Run Agentic SelfCheck event routing for payload event {event}. Workdir: /root/work/agentic-selfcheck. Use: scripts/event-dispatch.sh . feature.changed.ecommerce-product-ai-pipeline" \
  --deliver origin
```

Do not embed webhook secrets in this repo. Store them in Hermes config/env or the external provider's secret store.
