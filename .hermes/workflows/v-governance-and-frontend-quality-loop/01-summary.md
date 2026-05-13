# V Governance Connection and Frontend Rework Research

## V continuous governance connection

Connected `/root/work/v` to the Agentic SelfCheck continuous governance loop.

### Added SelfCheck objects

```text
features/v-project-doc-governance.yaml
features/v-project-code-health-governance.yaml
verifiers/v-project-doc-governance-audit.yaml
verifiers/v-project-code-health-governance-audit.yaml
events/v-continuous-governance-docs-changed.yaml
events/v-continuous-governance-code-changed.yaml
events/v-continuous-governance-daily-docs.yaml
events/v-continuous-governance-daily-code.yaml
```

### Added scripts

```text
scripts/v_continuous_governance_trigger.py
scripts/install_v_continuous_governance_hooks.py
```

### Installed hooks

Installed `pre-push` and `post-merge` hooks for:

```text
/root/work/v/platform-backend
/root/work/v/ecommerce-backend
/root/work/v/menu-backend
/root/work/v/kyc-backend
/root/work/v/platform-frontend
/root/work/v/ecommerce-frontend
/root/work/v/menu-frontend
/root/work/v/kyc-frontend
```

### Added cron

```text
job_id: 71ea35e98beb
name: V workspace continuous governance daily sweep
schedule: 35 10 * * *
```

### Verification

```text
selfcheck validate: PASS
V docs changed dry-run: PASS -> v.governance.changed.docs
V code changed dry-run: PASS -> v.governance.changed.code
V daily watchdog trigger: PASS
selfcheck audit v-project-doc-governance --strict-missing: PASS
selfcheck audit v-project-code-health-governance --strict-missing: PASS
```

Current V governance baselines:

```text
/root/work/v/reports/project-doc-governance/audit.json: PASS_WITH_NOTES, findings=20
/root/work/v/reports/project-code-health-governance/audit.json: PASS_WITH_NOTES, findings=30
reports/events/v.governance.watchdog.daily-latest.json: PASS
```

## Frontend rework research

External research sources summarized in:

```text
docs/v-frontend-quality-loop.md
```

Core conclusion:

Complex frontend work should not go directly from requirement to React implementation. The durable pattern is:

```text
Design Intake
-> Reuse/Token Discovery
-> Design-only Prototype / Storybook-first Component States
-> Visual Gate
-> Real React Integration
-> Browser + Playwright Runtime Gate
-> Visual Regression / Screenshot Evidence
-> PR / Final Verification
```

Recommended next slice:

```text
v-frontend-quality-loop
```

Land SelfCheck frontend-specific gates, Storybook/visual evidence readiness, Playwright screenshot baseline, and final-verifier visual evidence requirement.
