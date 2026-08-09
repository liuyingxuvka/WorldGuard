# Closure Report

Use closure reports before claiming a multi-model WorldGuard check is complete.

## Closure Questions

- Did every required node load?
- Did every required edge connect existing nodes?
- Did each node stay inside model authority?
- Did every current-required handoff use current source evidence?
- Did downstream nodes avoid forbidden use?
- Did the mesh avoid dependency cycles?
- Were child `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED` statuses preserved?
- Were child ledgers preserved in the aggregate ledger?
- Did structural, semantic, provider, and rollout status remain distinct?
- Did every required semantic child run through a declared typed binding?
- Does every invoked Guard have a declared prevention purpose and unsupported boundary?
- Did the source-discovered finite Guard-owned failure inventory exactly match the declared inventory, with one native good per Guard, one native bad per failure class, and an exact status/code oracle reaction?
- Were required Guards derived from structured claim atoms rather than accepted from the caller's target list alone?
- Do unit, mesh, and prompt composition expose the same canonical Guard denominator and derivation fingerprint from `worldguard.contracts.derive_guard_requirements`?
- Did every expected semantic-rollout node supply a contract, and does every skipped node/child have a typed reason and coverage impact?
- Were all current mesh nodes discovered before applying the caller expected list, and do discovered = declared + closed exclusions with exclusions contributing to neither execution nor claim scope?
- For predictive work, did both normal and holdout scenarios execute across a non-degenerate horizon with the effective square-root representative timepoint floor, required coverage ratio, native early/middle/late coverage, acceptable maximum normalized time gap, states, transitions, branches, perturbations, interventions, and counterfactuals for every expected model node rather than only in aggregate?
- For every exposed variable or signal, did its own temporal child universe independently meet the native dynamic count and early/middle/late floors, and is that per-object floor present in the WorldGuard receipt without a conflicting fixed ratio?
- Does the native depth receipt list executed and skipped children, provider
  states, claim/route coverage, quantitative coverage, mesh/coverage fingerprints, predictive gaps, license decision, findings, and the aggregate claim boundary?
- Are any old, stale, replaced, or superseded models still being used without disposition?
- For a WorldBlueprint, did one closed-registry adapter replay the exact local request-contract and target-material inputs for the current target/revision, issue its owner/executor-bound terminal receipt, match the cache exactly, close declared outputs in both directions, and retain every required contributing branch?
- Did it first validate an external census source derived only from frozen raw request/target inputs, then validate one separately produced signed object census and current matching discovery receipt, compare exact census input/node/element/Guard/role/derivation denominators, and keep discovery, signature validity, caller trust, claim kind, and candidate coverage as separate facts?
- Did every commitment input bind its kind, observation mode, safe locator, target/revision, and observed content hash; remain a visible gap when external or stale; and avoid any unregistered or fallback extractor?
- Is every port connection backed by schema identity/refinement plus cardinality proof, and is every element output consumed, owner-derived, or reasoned as one internal terminal?
- Are target-material, evidence, test/check, and native-result bindings present only where required, non-substituting, and bound to the exact target id/revision, provider/version/capability, lowercase SHA-256 content and receipt identities, owner, and claim boundary? For external roles, did the registered owners actually execute the test contract and semantically align the evidence rather than merely compare hashes?
- Was each local binding observed beneath the blueprint root, or backed by a registered provider capability and its registered execution-owner attestation? Is every identity-only external binding still `content_not_verified`?
- Does every typed native semantic object link to the exact current `native_result` observation and a terminal signed by the applicable domain Guard owner, with ownerless containers explicit `NOT_APPLICABLE`?
- Does every applicable native element carry one target-local purpose, one known-good, and one known-bad per selected failure; pass through parent declaration -> `for_guard` -> frozen purpose verification before execution; and compare target output/post-state/effects/failure against its own oracle afterward?
- Does the report state the deepest continuously qualified layer and the first unresolved layer, and keep `native_domain_qualified`, `object_dna_qualified`, and `full_domain_qualified` separate while absent cross-artifact projection is `not_run`?
- If a cross-artifact result was supplied, did a currently registered independent producer own it; did exact source blueprint/native-report/set/payload identities and immutable receipt bytes match; and did it leave native qualification unchanged?
- For an explicit portable handoff, did bundle-only replay reproduce embedded resource hashes, blueprint/report/query/handoff identities, preserve the caller's census trust context, and keep `native_handoff_qualified`, `object_dna_handoff_qualified`, and `full_cross_artifact_handoff_qualified` separate?
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
- A connected Guard whose purpose, finite failure inventory, good/bad
  cardinality, or native reaction oracle is missing or stale cannot support
  closure. In particular, a partially defined SCM is `GAP`, not `PASS`.
- One event, one or two convenient timepoints, enough points concentrated in only one phase, a rich aggregate with one shallow child, one equation, or one convenient scenario may pass a
  local bounded check, but cannot license prediction. Predictive closure needs
  `predictive_claim_licensed: true` on the current target receipt.
- Static repository regressions prove engine health only; missing or stale
  per-target receipt evidence remains `NOT_RUN`/`GAP`.
- A blueprint query proves only read-only impact or provenance for the supplied current blueprint and canonical request fingerprints. It does not execute a provider, mutate a target, widen to the whole blueprint, prove a target implementation, or establish external facts.
- A portable bundle may prove deterministic native-model handoff inside the blueprint boundary while object-DNA trust or cross-artifact projection remains unresolved. It may claim object-DNA handoff only when replay reproduces the external census source, current matching discovery receipt, exact integrated census, current external-test execution and evidence-alignment receipts, receives caller-trusted census authority/producer identity, and native qualification passes. Only a real registered external projection producer receipt can support full cross-artifact handoff; bundle self-consistency cannot manufacture discovery, execution, evidence, or trust.

## Report Shape

Return:

- conclusion status;
- mesh summary;
- node report summary;
- handoff findings;
- authority findings;
- freshness findings;
- cycle findings;
- child and mesh ledger evidence;
- component statuses, semantic receipts, and the native depth receipt;
- missing fields and stale evidence, if any.
- for blueprint work, target id/revision, blueprint and request fingerprints, qualified depth, first unresolved layer, affected-only paths or reverse provenance, role-separated bindings, declared gaps, separate native/object-DNA/full qualification, independent-discovery status and receipt fingerprint, census authority/producer fingerprints, trust status, claim kind, coverage, external-test design/execution status, evidence design/alignment status, unmapped ids, and first census gap.

Do not copy adapter-specific terms into the core closure report unless they appear only as opaque labels supplied by an upstream adapter.
