# Architecture Review

Role: Architect

## Decision

Add a router/gate layer above the existing frontend prototype pipeline. The router does not replace design-quality, design-lane, prototype coverage, freeze, or parity gates; it decides when those gates are mandatory.

## Components

- `scripts/frontend_risk_router.py`
  - Classifies task JSON into frontend/non-frontend and A/B/C/D risk.
  - Enforces feature-contract routing for C/D production frontend implementation.
  - Can initialize a prototype workflow via existing `init_frontend_workflow.py`.
- `scripts/frontend_risk_routing_smoke.py`
  - Regression harness for routing and fail-closed behavior.
- `verifiers/frontend-risk-routing-gate.yaml`
  - SelfCheck static verifier.
- `features/frontend-risk-routing.yaml`
  - Feature contract and required C/D production gates.

## Required C/D production route

1. Design Quality Pack
2. Design Lane Generation
3. High-fidelity Prototype Coverage Gate
4. Prototype Freeze before implementation
5. Prototype Parity after implementation

## Safety

Low-risk B frontend changes remain lightweight and do not require full prototype-first chain.
