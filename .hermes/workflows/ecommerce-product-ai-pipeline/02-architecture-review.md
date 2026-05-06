# Architecture Review

Role: architect
Verdict: APPROVE_WITH_NOTES

Decision:
- Keep generic SelfCheck runner project-agnostic.
- Bind Ecommerce through `projects/v-ecommerce-worktree.yaml` and feature `target_services`.
- API/browser harnesses are project scripts under `scripts/`, executed by SelfCheck as evidence-producing verifiers.

Boundary:
- Browser harness currently proves live headless Chromium rendering of login surface, not full authenticated Product Detail pipeline.
