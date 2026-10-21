# WorldBlueprint

Load this reference only for the typed `world_blueprint` shape. A WorldBlueprint is WorldGuard's target-neutral model of a world, workflow, experiment, policy, operational system, or other behavior-bearing target: its parts, semantic dependencies, coarse-to-fine interfaces, and supporting material/evidence/checks. It is not a source-code inventory and assumes neither software nor a language. FlowGuard owns generic implementation/test topology; WorldGuard owns world-domain elements and relations.

## Select one operation

Every operation needs the exact target id/revision/boundary; operation-specific inputs are:

| `blueprint_operation` | Required input and result |
|---|---|
| `create` | caller-supplied target-material refs and authority; author one model without inventing target truth, then require native `check` before any qualification claim |
| `update` | current identity, change intent, changed ids; edit only those members, then require native `check` |
| `check` | current identity; qualify the complete denominator and report continuous depth/gaps |
| `impact` | current identity/fingerprint, request fingerprint, changed ids; return the exact affected closure |
| `trace` | current identity/fingerprint, request fingerprint, one target; reverse-trace exact support |

Missing, stale, unknown, or mixed identity blocks without widening or retry. `affected_guard_ids` may name only current Event/Agent/Space/Resource/Causal/Conflict/Norm Guard ids and controls conditional prompt loading only; it is not impact evidence. For the input fields of those Guards read `guard-inputs.md`.

## Canonical contract

`schema_version: worldguard.world_blueprint.v1` contains exact blueprint/target/revision/boundary identity, one root, complete node/element/binding/declared-input/declared-output inventories, one commitment replay reference/cache locator, optional typed gaps, and a content-derived fingerprint. Ordered inventories normalize before hashing; every governed member or boundary change changes identity, and any supplied fingerprint must match. Declared input/output ids point to exact node ports and are queryable objects, not labels. Unknown fields, kinds, relations, roles, freshness values, source/disposition kinds, or cardinalities fail closed; there is no generic relation, free-form source, parser alias, or fallback.

## Hierarchy and semantic graph

The hierarchy is one strict rooted tree: one depth-zero root, one parent per non-root, reciprocal parent/child declarations, child depth = parent + 1, full root reachability, and no cycle/orphan. Cross-branch semantics use separate registered element dependencies (`depends_on`, `caused_by`, `constrained_by`, `consumes`, `precedes`, `governed_by`, `conflicts_with`) and never add hierarchy parents.

The closed v1 element kinds are `entity`, `property`, `relation`, `event`, `state`, `transition`, `resource`, `causal_link`, `agent`, `conflict`, and `norm`. Each element has one stable id/owner node, typed ports, dependencies, one `native_semantic`, and contribution/role assertions.

One registered adapter replays one local request contract, its target material and its target-semantic authority. Every reference binds kind, safe locator/mode, target/revision, and observed hash. Semantic authority freezes element semantics, Guard/executor and binding responsibilities, N/A reasons, and complete material-leaf assertions.

Child-supported summaries freeze target element, owner node, derivation id, parent output port, and exact child/owned-output sources; derivation ids cannot cross elements. Replay reconciles current registries and regenerated cache bidirectionally, so candidate/cache rewrites cannot shrink, relabel, or manufacture N/A.

`native_domain_qualified` reports whether the candidate is internally consistent. It is not proof that the model covers the whole target.

`native_semantic` binds exact ids/fields/hash/boundary and, where a Guard applies, one purpose with a known-good and one known-bad per selected failure. Each case freezes `Input x PreState -> Output x PostState`, effects, failure, and oracle. `admission_bad` proves parser rejection only. Execution validates the target-local `BlueprintTaskPurpose` case/oracle identities, then follows parent declaration -> `for_guard` -> structural and semantic owners -> comparison of the current target output/poststate/effects/failure with its own oracle. These actual target behavior cases remain required; no author checker-calibration proof is inserted. `worldguard.blueprint_native_execution.v2` accounts every field; ownerless containers are `NOT_APPLICABLE`. Event ids appear only as `executed_event_ids`; fluent and state identities remain separate. Consumed input never proves reachability, effects, factual truth, resolution, or mechanism truth; causal receipts keep requested/evaluated/licensed scope separate.

## Typed interfaces

Ports bind stable id, canonical schema/version/refinement, and `one`/`optional`/`many`; display labels prove nothing. Every node input has one compatible producer and at least one consumer. Every element input maps from its owner-node input or a declared dependency output. Missing, duplicate, cross-wired, incompatible, decorative, or implicitly external ports block.

Each non-root child output has one parent disposition: `parent_input`, `parent_output`, or reasoned `internal_terminal`. Node derivations exactly match child/owned-element contributors. Every element output is consumed, owner-derived, or one reasoned internal terminal. Mixed, duplicated, or prose-only wiring blocks.

## Role-separated bindings

Four roles never substitute: `target_material`, `evidence`, `test_check`, and `native_result`. A binding fixes subject/resource/owner/locator, provider/version/capability, mode, target/revision/freshness/boundary, and content/receipt hashes. Every element gives each role exactly one current responsibility or one independently declared typed N/A reason; never both. Output contributors need all four bindings, while child-supported summaries also need exact derivation support. Candidate role lists are assertions, not the denominator. A matching hash proves only bytes: `test_check` additionally requires a real target-local execution receipt from the registered Guard and semantic owner with exact inputs, oracle, outputs, effects, and terminal; `evidence` additionally requires a current alignment receipt whose support ids and observations match the exact subject and target boundary.

Observation modes are exact:

- `local_content`: safe relative path/optional selector, observed hash, matching receipt.
- `provider_content`: current registered provider/capability/owner and complete v2 receipt chain.
- `external_identity`: preserves identity but reports `content_not_verified` and closes no content role.

These rules are provider- and language-neutral. WorldGuard checks identity/content closure without reinterpreting a payload as another Guard's conclusion.

## Understanding depth

`check` reports inventory, hierarchy, interfaces, semantics, bindings, and native checks separately as `proven`, `gap`, `boundary`, or `not_run`.

`deepest_continuously_proven_layer` is the uninterrupted root-to-leaf prefix; `first_unresolved_layer` stops the continuous claim and makes deeper layers `not_run` for it. `partial_model_usable` may name a sound prefix, but no parent claim borrows unproven child depth.

## Native commands

```bash
python <skill-root>/scripts/run_worldguard.py blueprint check --blueprint <blueprint>
python <skill-root>/scripts/run_worldguard.py blueprint impact --blueprint <blueprint> --blueprint-fingerprint <sha256> --request-fingerprint <sha256> --changed-id <id>
python <skill-root>/scripts/run_worldguard.py blueprint trace --blueprint <blueprint> --blueprint-fingerprint <sha256> --request-fingerprint <sha256> --target-id <id>
```

Unreadable input/query errors exit 2; a valid trace with gaps exits 1. The model stays in memory; no export, bundle, copied resource, or standalone package exists.

## Impact semantics

`impact` indexes before traversing and materializes only the selected closure. Every stable public id is a seed: blueprint/target, commitment inventory/behavior/commitment, node, port, mapping, derivation, element, native semantic, dependency, binding/resource, declared input/output, or gap. It follows declared semantic/interface/ownership effects only, retaining one deterministic path and admitting edge per member.

Unrelated siblings remain absent unless a declared dependency or interface path connects them. If any requested id is unknown, including one unknown mixed with known ids, the whole query blocks before traversal. Stale fingerprints also block. The operation does not mutate the blueprint, run a provider, discover new material, synthesize a binding, or repair a gap.

## Reverse trace semantics

`trace` accepts only an exact node, node/element port, element, declared output, role binding, or material resource. Blueprint containers, targets, mappings, dependencies, native-semantic declarations, declared gaps, and other administrative ids are not trace targets. It walks exact producer, dependency, child-input source, child-output disposition, derivation, material, evidence, test, native execution receipt, and native-result edges backward. It terminates only at stable declared external input ids, binding ids, and binding resources. The declared input is reached through its actual port/mapping path; merely listing an input-port name is not terminal evidence. Every hop names its source, target, relation, and stable edge id.

A repeated dependency produces a deterministic cycle witness and is not followed forever. Any visited member that is not an explicit terminal and has no producer lineage becomes a typed dead-end gap. A missing input source, producer, child-output mapping, binding role, or dependency endpoint likewise becomes a typed broken-hop gap tied to the declared claim boundary. A trace with a visible gap is useful provenance, not complete lineage and therefore cannot return `PASS`.

## Claim boundary

WorldBlueprint qualification proves only current model closure for the declared target boundary. `create` structures caller-supplied material and authority; neither WorldGuard nor an AI generates the target's truth merely by writing a blueprint. Qualification does not by itself prove factual truth beyond the executed contracts, external implementation equivalence beyond the bound observations, installation state, Git state, release state, or future behavior.
