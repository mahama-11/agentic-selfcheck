# V Control Plane Stabilization Implementation Plan

> **For Hermes:** Use subagent-driven-development skill for future multi-agent implementation. This pass lands the deterministic P0 stabilization pieces directly.

**Goal:** Stabilize the V/SelfCheck quality control plane so it is observable, non-overlapping, and safe to operate without relying on chat memory.

**Architecture:** Keep cron as trigger, RepairTask/finding ledgers as durable lifecycle, and SelfCheck feature/verifier contracts as truth. Add one small status projection script that reads existing ledgers/cron state and emits a compact JSON/Markdown status without mutating product code.

**Tech Stack:** Python stdlib, existing Agentic SelfCheck scripts, Hermes cron output/state files, V workspace RepairTask ledgers.

---

## Slice 1: Dirty-tree inventory

Type: AFK
Blocked by: none
User stories / behavior covered: An operator can see whether the control plane itself is clean or carrying uncommitted drift.
Acceptance criteria:
- Produce counts by git status category.
- Classify changes into control-plane source, contracts/verifiers, workflow evidence, generated reports, and unknown.
- Do not delete or modify any product code.
Verifier command: `python3 scripts/v_control_plane_status.py --selfcheck-root . --v-root /root/work/v --format json`
Evidence path: `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.json`
需要郭凯决策: false

## Slice 2: Unified control-plane status projection

Type: AFK
Blocked by: Slice 1
User stories / behavior covered: An operator can ask “现在系统怎么样” and get a compact, evidence-backed answer.
Acceptance criteria:
- Reads Hermes cron job list if available, otherwise degrades gracefully.
- Reads latest cron output files and detects `[SILENT]` vs report vs delivery error.
- Reads V RepairTask status JSON.
- Reads dirty-tree inventory.
- Emits JSON and Markdown.
Verifier command: `python3 scripts/v_control_plane_status.py --selfcheck-root . --v-root /root/work/v --format markdown`
Evidence path: `/root/work/agentic-selfcheck/reports/v-control-plane-status/latest.md`
需要郭凯决策: false

## Slice 3: SelfCheck contract for the projection

Type: AFK
Blocked by: Slice 2
User stories / behavior covered: The status projection itself becomes a checked control-plane capability, not an ad-hoc script.
Acceptance criteria:
- Add feature `v-control-plane-status`.
- Add verifier `v-control-plane-status-smoke`.
- Verifier runs the script and checks required fields.
Verifier command: `python3 -m selfcheck loop --root . --feature v-control-plane-status --groups smoke --timeout 120`
Evidence path: `reports/loops/v-control-plane-status/`
需要郭凯决策: false

## Slice 4: Stabilization report

Type: AFK
Blocked by: Slice 3
User stories / behavior covered: The current control-plane state has a written checkpoint and next-action list.
Acceptance criteria:
- Report current cron boundary map.
- Report active RepairTask counts.
- Report dirty control-plane risk.
- Report verification commands and results.
Verifier command: manual readback of generated report and SelfCheck PASS/PASS_WITH_NOTES.
Evidence path: final chat response + status reports.
需要郭凯决策: false
