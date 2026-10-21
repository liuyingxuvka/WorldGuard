# Model Authority

Model authority defines what a model node is allowed to support.

## ModelAuthority Fields

- `owns`: semantics this model can support.
- `excludes`: semantics this model must not support.
- `scope_limits`: human-readable claim boundaries.

## Rules

- A model can only support claims inside its declared authority.
- If a claim requests a semantic in `excludes`, return `BOUNDARY_EXCEEDED`.
- If a model is silent about a needed semantic, return `GAP` unless another current, allowed handoff provides it.
- Do not use narrative plausibility to expand authority.

## Examples

- A resource model can support token, capacity, and transition enablement.
- A resource model cannot support permission, legality, market truth, or causal proof.
- A norm model can support obligation, permission, prohibition, and violation.
- A norm model cannot support token availability, physical enablement, payoff optimality, or structural causality.
- An event model can support declared events and fluent persistence.
- An event model cannot support continuous dynamics, legal permission, or causal intervention.

## Adapter Boundary

Upper-layer adapters may use domain labels, but they must translate them into core authority semantics before calling WorldGuard.
