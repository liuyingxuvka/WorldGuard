# WorldGuard Contracts

`GuardContract` checks one claim against one current explicit world model. `ModelMeshContract` adds multi-node topology, authority, freshness, handoffs, and per-node checks; read `model-mesh.md` only for that shape.

## Unit input

A contract needs `claim` and `inputs`; add `world_model` (`model_id`, `model_version`, `assumptions`, `scope_limits`). `contract_id` defaults to the claim id and `model_version` to `unversioned`; `schema_version`, `run_id`, `dependencies` and `output_requirements` have defaults. The claim carries `claim_id`, a descriptive `text` (never parsed), `asserts` (what the claim says, one check on the model per row; the row for each Guard is in [guard-inputs.md](guard-inputs.md)) and structured `requested_semantics` or `atoms` (each atom: `atom_id`, `text`, `requested_semantics`, `predictive_intent`). Supply the input fields consumed by each derived Guard, not every possible field:

| Guard | Current model/input family |
|---|---|
| EventGuard | Events, time/order, fluent changes and declared scenarios |
| AgentGuard | Agents, beliefs, intentions, knowledge |
| SpaceGuard | Spatial objects/relations |
| ResourceGuard | Resources, quantities, units and constraints |
| CausalGuard | Variables, graph/equations, scenarios and declared interventions/counterfactuals |
| ConflictGuard | Agents, actions, payoffs and conflict model |
| NormGuard | Norms, facts and rule priorities |

Field formats and copyable examples: [guard-inputs.md](guard-inputs.md). Missing consumed inputs produce typed gaps.

WorldGuard derives the Guards from the claim semantics and the kinds of `claim.asserts`. `claim.target_guards` is optional: it never shrinks or blocks the derived set; `derived_guards` names the executed set. `claim.target_guard` is retired. Prediction derives EventGuard plus CausalGuard. Unknown semantics do not fall back to the caller's Guard list; they stay visible as `QUALIFICATION_SEMANTIC_UNMAPPED`.

Run a contract with `python <skill-root>/scripts/run_worldguard.py check --contract <file.yaml>`, or `run_worldguard(contract)` in Python.

## Results

Each Guard runs its complete native checks once and returns `guard`, `status`, `errors`, `counterexamples` and `missing_slots`. Boundaries do not skip other checks. Aggregate status preserves the order `FAIL`, `GAP`, `BOUNDARY_EXCEEDED`, `PASS`.

The default summary contains `contract_id`, `status`, `checked`, `gaps` (one row per problem) and `scope_limits`. `checked` names the Guards and counts claim rows. Add `--json` for `guard_results`, `claim_binding`, `derived_guards` and `unmapped_semantics`. A missing assertion is `GAP` `CLAIM_NOT_BOUND`; a false assertion is `FAIL` `CLAIM_ASSERTION_FALSE`; an unresolved assertion is `GAP` `CLAIM_ASSERTION_UNRESOLVED`. Each problem carries its native code and its counterexample or missing slots. Legacy `dependencies` and `output_requirements` input mappings do not change the result.
