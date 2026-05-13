# Continuous Governance Discussion

User proposed two long-term governance needs:

1. For concrete projects:
   - scheduled review of documentation freshness, accuracy, and standardization;
   - scheduled review of code redundancy, garbage accumulation, dead code, and cleanup opportunities.
2. For Hermes / Agentic SelfCheck itself:
   - continuous governance of Hermes-produced documents;
   - continuous standardization and optimization of skills;
   - durable reuse of pitfalls as rules, skills, or verifiers.

Planned landing document:

```text
docs/continuous-governance-plan.md
```

Main design:

```text
Plane A: Project Governance
  - project-doc-governance
  - project-code-health-governance

Plane B: Self Governance
  - hermes-self-governance
  - skill-library-governance
  - pitfall-feedback-loop
```

Important constraints:

- scheduled jobs must not be notification spam;
- safe auto-fix is allowed;
- destructive cleanup or policy/product decisions require human confirmation;
- every loop produces compact evidence reports and can return `[SILENT]` when clean;
- Feishu ledger remains a human-readable projection, not AI/cron chatter storage.

Recommended first implementation slice:

```text
Slice 1: Governance feature contracts + placeholder verifiers + Harness reports.
Slice 2: Hermes self-governance MVP.
Slice 3: Project doc governance MVP for one active V project.
Slice 4: Project code-health MVP.
Slice 5: Pitfall registry enforcement.
```
