# Developer Summary: Continuous Governance Triggering

## Implemented

This slice connected the already-landed continuous governance capabilities to real trigger surfaces so the system is used instead of sitting idle.

## Event routes

Added change-triggered routes:

```text
events/continuous-governance-docs-changed.yaml       -> governance.changed.docs      -> project-doc-governance
events/continuous-governance-hermes-changed.yaml     -> governance.changed.hermes    -> hermes-self-governance
events/continuous-governance-code-changed.yaml       -> governance.changed.code      -> project-code-health-governance
events/continuous-governance-skills-changed.yaml     -> governance.changed.skills    -> skill-library-governance
events/continuous-governance-pitfalls-changed.yaml   -> governance.changed.pitfalls  -> pitfall-feedback-loop
```

Added daily fallback fan-out routes:

```text
events/continuous-governance-daily-docs.yaml
events/continuous-governance-daily-code.yaml
events/continuous-governance-daily-hermes.yaml
events/continuous-governance-daily-skills.yaml
events/continuous-governance-daily-pitfalls.yaml
```

All daily routes listen to:

```text
governance.watchdog.daily
```

## Path-to-event mapper

Added:

```text
scripts/continuous_governance_trigger.py
```

It maps changed files to governance events:

```text
docs / README / .hermes/workflows        -> docs + hermes governance
features / verifiers / schemas / reports -> hermes governance
scripts / selfcheck / source files       -> code-health governance
skills / SKILL.md                         -> skill governance
pitfalls / pitfall schema                 -> pitfall + hermes governance
```

## Local hooks

Added installer:

```text
scripts/install_continuous_governance_hooks.py
```

Installed local git hooks:

```text
.git/hooks/pre-push
.git/hooks/post-merge
```

Behavior:

- `pre-push`: runs changed-file governance trigger and blocks if relevant gates fail.
- `post-merge`: runs changed-file governance trigger as a non-blocking refresh.

## Cron fallback

Created Hermes cron job:

```text
job_id: e72e4398fee8
name: Agentic SelfCheck continuous governance daily sweep
schedule: 15 10 * * *
workdir: /root/work/agentic-selfcheck
```

It runs:

```bash
python3 -m selfcheck trigger --root . --event governance.watchdog.daily --source cron --timeout 300
python3 -m selfcheck audit --root .
```

Silent policy:

- If all governance statuses are PASS/PASS_WITH_NOTES and no repair/human blocker exists, output `[SILENT]`.
- Escalate only on command failure, NEEDS_REPAIR, NEEDS_HUMAN, or actual user decision requirement.

## Safety

- No destructive cleanup.
- No source deletion.
- No skill deletion/merge.
- No Feishu Base writes.
- Governance outputs still pass through SelfCheck redaction and report boundaries.
