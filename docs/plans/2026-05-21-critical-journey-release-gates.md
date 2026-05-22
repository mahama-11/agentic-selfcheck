# Critical Journey Release Gates Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a generic SelfCheck critical-journey framework and a V/Ecommerce adapter that can block release unless SKU lifecycle and production workflow journeys are healthy.

**Architecture:** SelfCheck stays generic: it owns journey schemas, a safe journey runner, secret-fixture loading/redaction, and evidence/report plumbing. V/Ecommerce is an adapter: it declares the journey config and implements product-specific API/browser checks under adapter scripts. The generic runner never imports V code or hardcodes V paths; it resolves project roots through project adapters and executes repo-local adapter commands with env vars.

**Tech Stack:** Python stdlib, YAML schemas, existing `python3 -m selfcheck` loop/verifier execution, V project adapter `/root/work/v`.

---

## Non-coupling boundary

- Generic SelfCheck files:
  - `schemas/critical-journey.schema.json`
  - `journeys/*.yaml` schema support
  - `scripts/critical_journey_gate.py`
  - generic smoke tests for config safety/reporting/redaction
- V/Ecommerce adapter files:
  - `journeys/v-ecommerce-critical-sku-production.yaml`
  - `scripts/adapters/v_ecommerce_critical_journey.py`
  - `features/ecommerce-critical-journey-release-gate.yaml`
  - `verifiers/ecommerce-critical-journey-*.yaml`
  - `events/release-v-ecommerce.yaml`
- SelfCheck core must not hardcode SKU, Ecommerce URLs, V routes, or product payloads.

## Slice 1: Generic journey runner

Type: AFK
Blocked by: none
Behavior covered: load journey config, resolve project root, run safe adapter command, write redacted report.
Acceptance criteria:
- `python3 scripts/critical_journey_gate_smoke.py` PASS.
- Unsafe absolute/parent-traversal adapter commands are rejected.
- Report contains journey id, project root, phase, status, child report path; no secret values.
Verifier command:
- `python3 scripts/critical_journey_gate_smoke.py`
Evidence path:
- `reports/critical-journeys/<journey>/<phase>.json`
需要郭凯决策: false

## Slice 2: V/Ecommerce critical journey contract mode

Type: AFK
Blocked by: none
Behavior covered: verify the V/Ecommerce release journey contract without mutating live data: auth fixture exists, router exposes required protected routes, frontend contains SKU/production route language, reports are emitted under `/root/work/v/reports/...`.
Acceptance criteria:
- Contract mode passes without requiring live backend.
- It blocks if auth fixture is missing, route contract is missing, or frontend no longer exposes SKU production path indicators.
Verifier command:
- `scripts/requirement-gate.sh ecommerce-critical-journey-release-gate static,api,browser,evidence release.v.ecommerce`
Evidence path:
- `/root/work/v/reports/ecommerce-critical-journey-release-gate/*.json`
需要郭凯决策: false

## Slice 3: V/Ecommerce live API journey

Type: HITL if credentials/environment fail
Blocked by: reachable dev/prod endpoints and valid account.
Behavior covered: login, create SKU/product, get/list SKU, create visual workflow session, stage-view, prompt planner blocked/ready where supported, delete SKU/cleanup.
Acceptance criteria:
- `ECOM_CRITICAL_JOURNEY_MODE=live` fails closed on 401/route mismatch.
- All created test data uses run id and cleanup metadata.
- Reports redact token/password and include request status per step.
Verifier command:
- `ECOM_CRITICAL_JOURNEY_MODE=live scripts/critical_journey_gate.py --journey v-ecommerce-critical-sku-production --phase api`
Evidence path:
- `/root/work/v/reports/ecommerce-critical-journey-release-gate/api.json`
需要郭凯决策: true only if supplied account lacks permissions or endpoints differ.

## Slice 4: V/Ecommerce authenticated browser journey

Type: HITL if UI selectors or auth flow differ.
Blocked by: Playwright/browser runtime and stable login selectors.
Behavior covered: login page, SKU creation UI, production workflow entry, protected page not redirecting to login, console/network capture, cleanup through API.
Acceptance criteria:
- Browser journey reuses the same secret fixture and writes storage state only to ignored reports dir.
- Critical screenshots and console/network failures are captured.
Verifier command:
- `ECOM_CRITICAL_JOURNEY_MODE=live scripts/critical_journey_gate.py --journey v-ecommerce-critical-sku-production --phase browser`
Evidence path:
- `/root/work/v/reports/ecommerce-critical-journey-release-gate/browser.json`
需要郭凯决策: true if selector/product UX semantics are ambiguous.

## Slice 5: Release integration

Type: AFK
Blocked by: Slice 1-2; live blocking after Slice 3-4 are stable.
Behavior covered: any Ecommerce release runs `ecommerce-critical-journey-release-gate` regardless of diff paths.
Acceptance criteria:
- Event route `release.v.ecommerce` targets the critical journey feature with strict audit.
- Existing change-specific gates remain separate from release-wide gates.
Verifier command:
- `scripts/requirement-gate.sh ecommerce-critical-journey-release-gate static,api,browser,evidence release.v.ecommerce`
Evidence path:
- `reports/loops/ecommerce-critical-journey-release-gate/latest.json`
需要郭凯决策: false

## Immediate implementation scope

This landing implements Slices 1, 2, and 5 plus live-mode scaffolding for Slice 3. Full live browser automation remains a named next slice because endpoint/auth/UI behavior must be confirmed against the actual environment.
