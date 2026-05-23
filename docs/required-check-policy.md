# Required check policy

This policy defines the required GitHub PR checks and the temporary Platform evidence gate while the V workspace does not yet have a self-hosted runner with access to `/root/work/v`.

## Required PR checks

Configure branch protection for protected branches (currently `main`) to require these checks before merge:

1. `Validate SelfCheck control plane`
   - Source: `.github/workflows/ci.yml` job `selfcheck`.
   - Scope: validates SelfCheck registry, verifier definitions, Python import/compile health, and auditability.

2. `Requirement trace adoption fixture gate`
   - Source: `.github/workflows/ci.yml` job `requirement-trace-adoption`.
   - Scope: runs the requirement trace ledger smoke against committed fixtures.
   - Important: this is a fixture PR check only. It proves the SelfCheck control plane can enforce trace adoption on a synthetic V root; it does **not** prove live `/root/work/v` Platform evidence.

3. Local/live Platform evidence gate for Platform code changes, until a self-hosted runner exists.
   - Required for changes touching Platform code, docs, contracts, or SelfCheck verifiers that govern Platform paths.
   - Current command:
     ```bash
     cd /root/work/agentic-selfcheck
     python3 -m selfcheck run --root . --feature platform-core-engineering-baseline --groups static --timeout 120
     ```
   - The verifier command targets live `/root/work/v` and writes the real Platform evidence report under `/root/work/v/reports/platform-core-engineering-baseline/platform-core-engineering-baseline.json`.
   - Merge evidence must cite the exact command result and report path in the PR or workflow evidence note.

## Fixture versus real evidence

- Fixture evidence: `Requirement trace adoption fixture gate` runs on GitHub-hosted CI against `tests/fixtures/requirement-trace-v-root`. It is safe, repeatable, and required for SelfCheck control-plane changes, but it is not a substitute for Platform code evidence.
- Real Platform evidence: local/live gate output produced from `/root/work/v`. It is required when Platform files are changed because GitHub-hosted CI cannot currently see that workspace.

## Exact branch protection settings

In GitHub repository settings for protected branches:

- Enable `Require a pull request before merging`.
- Enable `Require status checks to pass before merging`.
- Select required checks:
  - `Validate SelfCheck control plane`
  - `Requirement trace adoption fixture gate`
- Enable `Require branches to be up to date before merging` when the repo uses merge queues or fast-forward discipline.
- Until a self-hosted runner is available, require reviewers/maintainers to verify the local/live Platform evidence gate in the PR conversation for Platform code changes. Do not mark fixture evidence as live `/root/work/v` evidence.

## Future self-hosted runner migration

When a self-hosted runner can access `/root/work/v`, add a dedicated required check named `Platform live evidence gate` that runs the live Platform SelfCheck command above. At that point, replace the manual local/live evidence requirement with that required check.
