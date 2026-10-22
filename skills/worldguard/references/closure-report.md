# Closure Report

Optional checklist when reporting a multi-model (mesh) WorldGuard check.

## Closure Questions

- Did every required node load?
- Did every required edge connect existing nodes?
- Did each node stay inside model authority?
- Did every current-required handoff use current source evidence?
- Did downstream nodes avoid forbidden use?
- Did the mesh avoid dependency cycles?
- Were child `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED` statuses preserved?
- Did structural, semantic, provider, and rollout status remain distinct?
- Did every node supply a contract and run its derived Guards, with missing contracts and unavailable providers reported as gaps?
- Are any old, stale, replaced, or superseded models still being used without disposition?

## Status Rules

- Any hard contradiction, forbidden handoff, dependency cycle, or unknown required node/edge error can make the mesh `FAIL`.
- Any unresolved missing node, missing target, missing source, stale required source, or missing model field can make the mesh `GAP`.
- Any authority overreach or unsupported semantic can make the mesh `BOUNDARY_EXCEEDED`.
- Only when all child reports and mesh findings are pass-compatible may the mesh be `PASS`.
- Structural-only work must remain `BOUNDARY_ONLY`/`NOT_RUN` for semantic
  closure; it cannot be described as simulated or semantically validated.
- Provider-unavailable and unevaluable semantic cases fail closed even when
  every required input field is present.
- Ordinary unit/mesh closure requires the complete derived Guard set and
  current native results within the stated scope; missing task evidence
  remains a gap. A partially defined SCM is `GAP`, not `PASS`.

## Report Shape

Return:

- conclusion status;
- mesh summary;
- node report summary;
- handoff findings;
- authority findings;
- freshness findings;
- cycle findings;
- component statuses and native gaps;
- missing fields and stale evidence, if any.

Do not copy adapter-specific terms into the core closure report unless they appear only as opaque labels supplied by an upstream adapter.
