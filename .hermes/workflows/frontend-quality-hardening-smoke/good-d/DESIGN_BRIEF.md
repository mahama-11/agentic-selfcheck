# Design Brief

## Risk classification

- Risk level: C
- Reason: new dashboard-like frontend surface with non-trivial layout, task hierarchy, and interaction expectations.

## Product goal

Demonstrate how an AI agent should create and iterate a high-fidelity prototype before production implementation.

## Target users and jobs-to-be-done

A product/operator user wants to understand the state of AI/autonomy work, see blockers, and decide the next action quickly.

## Routes / surfaces affected

- Demo route: `/prototype-demo/autonomy-control-room`

## Visual direction

- Tone: modern control room, clear but premium.
- Density: medium-high, but not cluttered.
- Reference posture: Linear/Superhuman style precision, not generic admin.
- Forbidden: plain table-only admin, random gradient cards, fake metrics without action meaning.

## Existing design system constraints

Generic demo: use CSS variables as tokens; production adapters should map them to project tokens.

## Data and backend constraints

Prototype data is synthetic and explicitly marked demo-only.

## Acceptance bar

Prototype v2 should improve first-screen clarity, action hierarchy, and interaction affordances over v1.
