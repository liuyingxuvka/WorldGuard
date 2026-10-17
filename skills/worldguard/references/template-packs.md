# WorldGuard Validating Template Packs

Use this construction layer before manually assembling a new `GuardContract` or `ModelMeshContract`. It reduces repeated shape errors without becoming a Guard router or semantic executor.

## Fixed boundary

- WorldGuard owns every pack, applicability fact, field fragment, validator binding, and receipt meaning.
- A downstream authoring tool may validate the declared WorldGuard check but never selects a pack or interprets Guard semantics.
- A template does not derive required Guards, create behavior evidence, execute the claim, or license prediction.

## Selection

Call `builtin_template_registry().select(contract_kind, fact_ids)` before building:

- `no_match`: zero candidates matched; block with `TEMPLATE_SELECTION_NO_MATCH`. The shared base scaffold is never a selectable result.
- `selected`: exactly one candidate matched; compose it after the base scaffold.
- `ambiguous`: several candidates matched; show every candidate id and block. Do not use order, scores, filenames, or AI preference to choose.

For a Guard-specific child, pass one exact fact such as `guard:EventGuard` only after WorldGuard/caller context selected that Guard. For a ModelMesh coverage scaffold, pass `coverage:bounded` or `coverage:predictive`. Passing mutually matching facts is deliberately ambiguous.

## Built-in packs

| Contract kind | Base slots | Candidate fact and added slot |
|---|---|---|
| `guard_contract` | `contract_id`, `run_id`, `claim_id`, `claim_text`, `target_guards`, `requested_semantics`, `claim_atoms`, `model_id`, `model_version` | `guard:EventGuard` → `event_inputs`; `AgentGuard` → `agent_inputs`; `SpaceGuard` → `space_inputs`; `ResourceGuard` → `resource_inputs`; `CausalGuard` → `causal_inputs`; `ConflictGuard` → `conflict_inputs`; `NormGuard` → `norms` + `facts` |
| `model_mesh_contract` | `mesh_id`, `run_id`, `nodes`, `expected_model_node_ids` | `coverage:bounded` or `coverage:predictive` adds only the explicit coverage profile |

The Guard base is a non-selectable shared construction fragment. It is composed only after exactly one Guard candidate matches. Guard candidates add only the appropriate input slots. The caller supplies current claim, model and domain inputs.

## Build

Use:

```python
from worldguard import GUARD_CONTRACT_KIND, build_template_instance, builtin_template_registry

instance = build_template_instance(
    builtin_template_registry(),
    contract_kind=GUARD_CONTRACT_KIND,
    fact_ids=["guard:EventGuard"],
    slot_bindings={
        "contract_id": task_contract_id,
        "run_id": run_id,
        "claim_id": claim_id,
        "claim_text": claim_text,
        "target_guards": ["EventGuard"],
        "requested_semantics": ["event"],
        "claim_atoms": claim_atoms,
        "model_id": model_id,
        "model_version": model_version,
        "event_inputs": task_owned_events,
    },
)
```

Supply every discovered slot exactly once. Missing slots block with `TEMPLATE_SLOT_MISSING`; extra bindings block with `TEMPLATE_BINDING_UNUSED`. Callers cannot overlay arbitrary fields after composition because that would bypass field ownership and identity.

## Composition and freshness

Each fragment's `owned_field_ids` must exactly equal its payload leaves. Equal fields and ancestor/descendant overlaps block with `TEMPLATE_FIELD_OWNERSHIP_CONFLICT`; there is no last-writer-wins route. The manifest fingerprint covers its schema, applicability, fragments, validators, and claim boundary. A changed manifest or nested fragment with an old fingerprint is stale and rejected.

## Native validation and receipt

Guard instances run canonical GuardContract shape validation and complete claim-derived route validation. ModelMesh instances run canonical mesh validation and route validation for embedded Guard contracts. Unknown validator ids block; no fallback validator is selected.

Retain the receipt's registry, selection, pack, composition, binding, output, validator, and final instance fingerprints. Its claim boundary is construction integrity only. Continue through `run_worldguard` or `run_model_mesh` and target-native depth evaluation where required before making a broader conclusion.
