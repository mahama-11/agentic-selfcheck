# SelfCheck System Architecture and Project Adapter Framework

Agentic SelfCheck is a reusable quality-control module. It is not owned by `/root/work/v`; V is only the first concrete project adapter.

## 1. Core principle

```text
SelfCheck core = schemas + feature contracts + verifier registry + evidence model + loop/dispatch engine
Project adapter = project paths + services + commands + auth/runtime hints + project-specific verifier harnesses
Requirement gate = feature contract + selected verifier groups + event/loop evidence
```

A product workspace must not hard-code its rules into SelfCheck core. Instead it contributes:

- a `projects/<project-id>.yaml` adapter;
- one or more `features/<feature-id>.yaml` acceptance contracts;
- verifier registry entries under `verifiers/`;
- narrow scripts under `scripts/` when generic service commands are insufficient;
- optional event routes under `events/`;
- reports/evidence under `reports/<feature-id>/`.

## 2. Layering

| Layer | Portable across projects | Examples |
| --- | --- | --- |
| Core schemas | yes | `schemas/*.schema.json` |
| Capability contracts | yes | frontend runtime, review gates, AI generation |
| Project adapters | no, one per workspace/app | `projects/v-workspace.yaml`, future external project adapters |
| Feature contracts | mostly project-specific | `features/ecommerce-v2-prep-sandbox-lowlevel.yaml` |
| Verifier registry | reusable shape, project-specific execution | `verifiers/*` |
| Harness scripts | project-specific unless explicitly generic | `scripts/ecommerce_v2_*` |
| Loops/events | reusable mechanism, project-specific routing | `events/*.yaml`, cron/webhook/git-hook |

## 3. New project onboarding checklist

1. Create `projects/<project-id>.yaml` with root, services, commands, ports, and environment notes.
2. Add or reuse capabilities needed by the project.
3. Create feature contracts for high-risk flows before coding.
4. Add verifiers by group: `static`, `api`, `browser`, `evidence`, plus optional `runtime`/`unit`.
5. Keep generic checks in reusable scripts; keep product semantics in project harnesses.
6. Add event routes for requirement changes and CI/git-hook/webhook triggers.
7. Run:

```bash
python3 -m selfcheck validate --root .
scripts/requirement-gate.sh <feature> static,api,browser,evidence requirement.changed.<project>.<feature>
```

## 4. Feedback and iteration model

SelfCheck must improve whenever a low-level issue escapes or a requirement changes.

### Sources of feedback

- requirement changes from chat, Feishu, issue, PR, or webhook;
- verifier failures from local runs, CI, cron, or prod smoke;
- bug reports and low-level regressions found manually;
- reviewer/QA findings;
- deployment drift or stale evidence.

### Required update behavior

When a new issue is found:

1. classify it as product bug, contract gap, verifier gap, or process gap;
2. fix product code if needed;
3. add or strengthen a verifier so the same class fails automatically next time;
4. record the new rule in the feature contract or capability docs;
5. rerun the full feature gate, not only the new verifier;
6. if repeated or human-boundary, dispatch/escalate instead of silently looping.

## 5. Status semantics

- `PASS`: all requested groups passed and required evidence exists.
- `PASS_WITH_NOTES`: main gate passed but explicit non-blocking evidence/coverage limitation remains.
- `NEEDS_REPAIR`: SelfCheck generated dispatch artifacts; owner must fix and rerun.
- `BLOCKED`: human decision, missing permission/secret, repeated failure, or unsafe repair boundary.
- `PARTIAL_PASS`: allowed only outside the gate report when the agent did not run required runtime/browser/prod evidence.

## 6. V adapter example

V-specific rules belong in:

- `/root/work/v/docs/AGENTIC_SELFCHECK_INTEGRATION.md`
- `projects/v-*.yaml`
- `features/ecommerce-v2-prep-sandbox-lowlevel.yaml`
- `scripts/ecommerce_v2_*`

They must not be represented as universal SelfCheck behavior. Future projects should add their own adapter and feature contracts while reusing the same core loop/evidence/dispatch mechanism.
