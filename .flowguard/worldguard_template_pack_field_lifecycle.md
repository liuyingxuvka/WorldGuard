# WorldGuard Template-Pack Field Lifecycle

Route: `field_lifecycle_mesh`

Boundary: WorldGuard-owned template manifest, selection, composition, slot, validator, instance-receipt fields introduced by `add-worldguard-template-pack-builder`. No field has an ordinary UI reader, so no UI Flow Structure admission row is required.

## Parent Groups

| Parent group | Owner | Readers | Writers | Lifecycle |
|---|---|---|---|---|
| `template_pack_manifest` | `worldguard.template_packs` | registry, selector, composer | WorldGuard pack authors/builders | new |
| `template_selection` | `worldguard.template_packs` | builder, receipt | selector only | new per build |
| `template_instance_receipt` | `worldguard.template_packs` | caller, tests | native builder only | immutable per build |

## Leaf Inventory

| Field id | Owner | Readers | Writers | Behavior projection / disposition |
|---|---|---|---|---|
| `manifest.schema_version` | `worldguard.template_packs` | registry validator | manifest builder | exact current schema; unknown/old blocks |
| `manifest.pack_id` | WorldGuard pack author | selector, receipt | manifest builder | stable pack identity |
| `manifest.pack_version` | WorldGuard pack author | registry, receipt | manifest builder | explicit content version |
| `manifest.contract_kind` | `worldguard.template_packs` | base lookup, composition, validator | manifest builder | `guard_contract` or `model_mesh_contract`; mismatch blocks |
| `manifest.is_base` | `worldguard.template_packs` | base lookup, selector | manifest builder | exactly one base per kind |
| `manifest.required_fact_ids` | WorldGuard pack author | selector | manifest builder | explicit applicability conjuncts; does not derive Guard semantics |
| `manifest.excluded_fact_ids` | WorldGuard pack author | selector | manifest builder | explicit negative applicability |
| `manifest.fragments[]` | WorldGuard pack author | composer | manifest builder | reusable scaffold only |
| `fragment.fragment_id` | WorldGuard pack author | ownership diagnostics | fragment builder | stable fragment identity |
| `fragment.owned_field_ids` | WorldGuard pack author | manifest validator, composer | fragment builder | exact equality with discovered payload leaves |
| `fragment.payload` | WorldGuard pack author | composer, slot resolver | fragment builder | canonical JSON-like scaffold |
| `manifest.native_validator_ids` | WorldGuard runtime | registry, validator runner | manifest builder | every id resolves in WorldGuard registry; every validator stays native |
| `manifest.claim_boundary` | WorldGuard pack author | receipt, docs | manifest builder | construction-only boundary |
| `manifest.manifest_fingerprint` | `worldguard.template_packs` | registry, selection, receipt | canonical manifest builder | content hash; mismatch is stale |
| `selection.contract_kind` | caller request | selector, receipt | build request | selects only the contract family |
| `selection.fact_ids` | existing WorldGuard/caller context | selector, receipt | build request | normalized explicit facts; never inferred by template scoring |
| `selection.candidate_pack_ids` | selector | builder, diagnostics | selector | exact sorted 0/1/many set |
| `selection.outcome` | selector | builder, receipt | selector | `no_match`, `selected`, or `ambiguous`; only `selected` may compose, while zero and many candidates block visibly |
| `selection.selection_fingerprint` | `worldguard.template_packs` | builder, receipt | selector | binds registry, facts, candidates, and outcome |
| `slot.$slot` | WorldGuard pack author | slot resolver | fragment payload | task-local placeholder; never supplies its own value |
| `build.slot_bindings` | caller/AI task workflow | slot resolver, receipt | caller | task identity/evidence values; missing or unused blocks |
| `receipt.registry_fingerprint` | `worldguard.template_packs` | receipt consumer | builder | exact admitted registry identity |
| `receipt.pack_fingerprints` | `worldguard.template_packs` | receipt consumer | builder | exact base/selected pack identities |
| `receipt.binding_fingerprint` | `worldguard.template_packs` | receipt consumer | builder | exact task slot values |
| `receipt.output_fingerprint` | `worldguard.template_packs` | native validator, receipt consumer | builder | exact resolved contract dictionary |
| `receipt.validator_receipts` | WorldGuard native validator registry | receipt consumer | native validators | construction validation only |
| `receipt.instance_fingerprint` | `worldguard.template_packs` | caller, tests | builder | final content identity; any governed change stales it |


## Domain ownership and handoff

`claim.*` and Guard derivation remain owned by `worldguard.contracts`; template facts cannot shrink the derived set. `semantic_coverage` remains owned by `worldguard.mesh`; construction does not license prediction. Actual semantic execution and evidence stay with their native world owners. Templates carry only current task claim, model and inputs through explicit slots; no checker-purpose declarations are required.

The executable selection/composition/validation model is `.flowguard/worldguard_template_pack_builder.py`, registered by `.flowguard/template_selection/run_checks.py` in `.flowguard/map.json`. Native stale/ownership/slots/no-match/ambiguous/validator cases are in `tests/test_template_packs.py`. The old neutral supervision transport is retired; no projected catalog or central seal is needed.
