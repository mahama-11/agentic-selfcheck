# V Requirement Integration Requirement

Role: orchestrator

Requirement:
- Integrate Agentic SelfCheck into `/root/work/v` requirement delivery to improve implementation quality.
- Non-trivial requirements should enter SelfCheck after implementation through event/loop gates.
- Failures must dispatch to owner roles and rerun SelfCheck after repair.
- Do not embed project-specific governance logic into product code; keep SelfCheck as external reusable control plane.
