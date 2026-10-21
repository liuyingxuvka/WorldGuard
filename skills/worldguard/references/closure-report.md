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
- Did every expected semantic-rollout node supply a contract, and does every skipped node/child have a typed reason and coverage impact?
- Were all current mesh nodes discovered before applying the caller expected list, and do discovered = declared + closed exclusions with exclusions contributing to neither execution nor claim scope?
- For predictive work, did both normal and holdout scenarios execute across a non-degenerate horizon with the effective square-root representative timepoint floor, required coverage ratio, native early/middle/late coverage, acceptable maximum normalized time gap, states, transitions, branches, perturbations, interventions, and counterfactuals for every expected model node rather than only in aggregate?
- For every exposed variable or signal, did its own temporal child universe independently meet the native dynamic count and early/middle/late floors, and is that per-object floor present in the WorldGuard report without a conflicting fixed ratio?
- Are any old, stale, replaced, or superseded models still being used without disposition?
- For `impact`, were only the deterministic dependency/interface descendants returned, with unaffected siblings excluded and path reasons preserved? For `trace`, did every reverse hop end in a declared input or current binding, with cycles and broken hops reported?

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
- One event, one or two convenient timepoints, enough points concentrated in only one phase, a rich aggregate with one shallow child, one equation, or one convenient scenario may pass a
  local bounded check, but cannot license prediction. Predictive closure needs
  `predictive_claim_licensed: true` in the current mesh report.
- A blueprint query proves only read-only impact or provenance for the supplied current blueprint and canonical request fingerprints. It does not execute a provider, mutate a target, widen to the whole blueprint, prove a target implementation, or establish external facts.

## Report Shape

Return:

- conclusion status;
- mesh summary;
- node report summary;
- handoff findings;
- authority findings;
- freshness findings;
- cycle findings;
- component statuses and, for predictive work, the predictive license and gaps;
- missing fields and stale evidence, if any;
- for blueprint work: target id/revision, qualified depth, first unresolved layer, affected-only paths or reverse provenance, and declared gaps.

Do not copy adapter-specific terms into the core closure report unless they appear only as opaque labels supplied by an upstream adapter.
