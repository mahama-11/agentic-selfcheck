# Agentic SelfCheck

Agentic SelfCheck is a project-agnostic autonomy and acceptance control plane for AI-assisted software engineering.

It is not another coding agent. It defines the reusable governance layer around coding agents:

```text
product invariants → capability contracts → feature acceptance → verifiers → evidence → gates → loops/hooks
```

The `/root/work/v` workspace is the first validation field, not a hard-coded dependency.

## L3 / L3.5 target

```text
L3: machine-enforced acceptance gates before code is called done.
L3.5: lightweight recurring loops/hooks that detect missing gates, stale evidence, and failed verifiers, then escalate or trigger bounded repair.
```

## Project layout

```text
schemas/             JSON Schemas for governance files
invariants/          reusable cross-project truths
capabilities/        reusable capability contracts
projects/            per-project adapters: paths, commands, ports, auth hints
features/            versioned feature acceptance specs
verifiers/           verifier registry entries
loops/               hook/cron/webhook loop definitions
selfcheck/           Python CLI implementation
scripts/             wrapper scripts/hooks
examples/            optional examples
reports/             generated validation/evidence reports, ignored by git
```

## Quick start

```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck validate --root .
python3 -m selfcheck plan --root . --feature ecommerce-product-ai-pipeline
python3 -m selfcheck run --root . --feature ecommerce-product-ai-pipeline --dry-run
python3 -m selfcheck run --root . --feature ecommerce-product-ai-pipeline --groups static
python3 -m selfcheck audit --root .
```

## What v0 proves

- Governance files are schema-valid.
- Every feature references existing project/capability/verifier IDs.
- Every capability references existing verifier IDs.
- Human decision boundaries are explicit.
- Verifier commands can be planned and dry-run listed without being project-specific.
- Safe static verifiers can be executed through project adapters and emit JSON evidence under `reports/<feature>/`.
- Workflow-health audit can flag missing/stale evidence.

## Non-goals for v0

- Replacing Hermes, Claude Code, OpenHands, PR-Agent, Playwright, GitHub Actions, or CI.
- Deciding product quality without human boundaries.
- Silently approving release decisions.
