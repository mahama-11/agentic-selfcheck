# P0/P1 Failure Closed Loop Implementation Plan

> **For Hermes:** Implement directly in Agentic SelfCheck as a reusable control-plane feature; V is only the first adapter.

**Goal:** Turn SelfCheck/watchdog failures into deterministic repair dispatches and automatically escalate repeated failed repair loops into architecture review instead of unbounded patching.

**Architecture:** Add a generic failure closed-loop controller that ingests SelfCheck loop, event, trigger, or working-tree watchdog reports. It normalizes failures into incidents, classifies root-cause buckets, tracks repeated signatures in a durable ledger, writes owner dispatch cards for bounded repair, and writes architecture escalation capsules after repeated attempts. V watchdog calls this controller only on FAIL so PASS remains silent.

**Tech Stack:** Python stdlib, SelfCheck YAML feature/verifier contracts, JSON reports under `reports/v-failure-closed-loop/`.

---

## Slice 1: Failure classifier and durable ledger

Type: AFK

Acceptance criteria:
- `scripts/v_failure_closed_loop.py ingest --report <json>` parses loop/watchdog/trigger-shaped reports.
- Each failure gets a stable signature, bucket, owner, next action, and evidence path.
- Repeated same signature increments counts instead of creating duplicate noisy tasks.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
scripts/v_failure_closed_loop_smoke.py --root . --format json
```

Evidence path:
- `scripts/v_failure_closed_loop.py`
- `reports/v-failure-closed-loop/ledger.json`

## Slice 2: Repair dispatch cards

Type: AFK

Acceptance criteria:
- Non-escalated incidents write `.hermes/dispatch/v-failure-closed-loop/<incident>.md`.
- Dispatch includes failed feature/verifier/group, bucket, owner, evidence, required rerun, and anti-self-review rules.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
scripts/v_failure_closed_loop_smoke.py --root . --format json
```

Evidence path:
- `.hermes/dispatch/v-failure-closed-loop/`

## Slice 3: P1 architecture escalation guard

Type: AFK

Acceptance criteria:
- Same failure signature crossing 3 observations or explicitly exhausted attempts becomes `ESCALATE_ARCHITECTURE`.
- Controller writes `reports/v-failure-closed-loop/architecture-escalations/<incident>.md`.
- Escalation card says stop blind patching and review module/interface/seam.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
scripts/v_failure_closed_loop_smoke.py --root . --format json
```

Evidence path:
- `reports/v-failure-closed-loop/architecture-escalations/`

## Slice 4: Watchdog integration

Type: AFK

Acceptance criteria:
- Working-tree watchdog invokes the closed-loop controller only when business-gate execution fails.
- PASS remains silent for cron.
- FAIL output points to both watchdog latest report and failure closed-loop ledger.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck run --root . --feature v-failure-closed-loop --groups static --timeout 300
```

Evidence path:
- `scripts/v_working_tree_governance_watchdog.py`

## Human boundaries

- Actual code repair execution is still delegated to the correct owner lane; SelfCheck does not patch product implementation while acting as verifier.
- Architecture escalation is advisory/blocking evidence; irreversible refactors still need human approval.
