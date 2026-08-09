# Model Authority

Model authority defines what a model node is allowed to support.

For a `WorldBlueprint`, authority is also structural: every domain element has one node owner; every contribution crosses a schema-bound port; every element output is consumed, derived, or explicitly terminal; and every public behavior/output comes from replaying exact current request/target inputs through a closed-registry commitment adapter rather than trusting caller-selected blueprint branches or a cached inventory. Whole-object completeness has a second owner: an external census source is derived from the frozen raw request/target material without reading the candidate, and an independently produced signed census plus current discovery receipt states and binds the expected nodes, elements, Guard owners, role dispositions, and derivations. WorldGuard validates and compares those records but does not create their trust.

## ModelAuthority Fields

- `owns`: semantics this model can support.
- `excludes`: semantics this model must not support.
- `scope_limits`: human-readable claim boundaries.

## Rules

- A model can only support claims inside its declared authority.
- If a claim requests a semantic in `excludes`, return `BOUNDARY_EXCEEDED`.
- If a model is silent about a needed semantic, return `GAP` unless another current, allowed handoff provides it.
- Do not use narrative plausibility to expand authority.
- Do not infer authority from hierarchy depth alone. Depth says how far current evidence is continuous; ownership, typed interfaces, derivations, and current bindings say what that depth can support.
- A blueprint binding may support only its declared role (`target_material`, `evidence`, `test_check`, or `native_result`) for the exact target id/revision, provider/version/capability, lowercase SHA-256 content and receipt identities, owner, and claim boundary. One role never substitutes for another, and an identity-only external binding never proves observed content. An external test role closes only after the registered Guard/semantic owner executes the exact target-local input and oracle contract; an evidence role closes only when its supports, observation, owner, source, target/revision, boundary, and freshness all align semantically.
- A `provider_content` binding requires a current registry entry plus the registered execution owner's exact request/input/result/terminal attestation. Caller-authored provider identity and hash fields are not provider authority.
- A blueprint coordinates native checks but cannot issue native PASS. The current domain Guard owner signs an executed terminal; a container without such an owner is explicit `NOT_APPLICABLE`.
- A declared blueprint gap narrows the qualified boundary and the deepest continuous layer. It is not erased by a passing sibling or parent.
- `native_domain_qualified` licenses candidate consistency only. `object_dna_qualified` additionally requires an independent census source, a current discovery receipt bound to that source and the frozen raw target inputs, exact census coverage, integrated-target claim kind, current external-test execution, semantically aligned evidence, and caller trust in the exact census authority or producer descriptor. Producer trust never licenses a later revision without its own matching discovery receipt. A capability fixture, unsigned/stale census, untrusted signer, coherent candidate shrink, candidate-authored N/A, hash-only test, or misaligned evidence cannot cross that boundary.

## Examples

- A resource model can support token, capacity, and transition enablement.
- A resource model cannot support permission, legality, market truth, or causal proof.
- A norm model can support obligation, permission, prohibition, and violation.
- A norm model cannot support token availability, physical enablement, payoff optimality, or structural causality.
- An event model can support declared events and fluent persistence.
- An event model cannot support continuous dynamics, legal permission, or causal intervention.

## Adapter Boundary

Upper-layer adapters may use domain labels, but they must translate them into core authority semantics before calling WorldGuard. A behavior-commitment adapter is authoritative only when its exact id/version/capability is in the closed current registry, its required local inputs match target/revision/content, and its owner/executor replay produces the exact cached result and terminal receipt. An external identity, caller-recomputed cache hash, or unregistered OpenSpec/Spark/changelog extractor cannot establish commitment authority.

Blueprint element kinds and dependency relations are a closed, target-neutral vocabulary. Unknown kinds or relations are visible schema errors; adapter labels remain opaque metadata and never create a new semantic owner.
