# WorldGuard Contracts

`GuardContract` checks one claim against one current explicit world model. `ModelMeshContract` adds multi-node topology, authority, freshness, handoffs, and coverage; read `model-mesh.md` only for that shape.

## Unit input

A contract needs `claim` and `inputs`; add `world_model` (`model_id`, `model_version`, `assumptions`, `scope_limits`). `contract_id` defaults to the claim id and `model_version` to `unversioned`; `schema_version`, `run_id`, `dependencies` and `output_requirements` have defaults. The claim carries `claim_id`, a descriptive `text` (never parsed), `asserts` (what the claim says, one check on the model per row; the row for each Guard is in [guard-inputs.md](guard-inputs.md)) and structured `requested_semantics` or `atoms` (each atom: `atom_id`, `text`, `requested_semantics`, `predictive_intent`). Supply the input fields consumed by each derived Guard, not every possible field:

| Guard | Current model/input family |
|---|---|
| EventGuard | Events, time/order, fluent changes; observations when predictive |
| AgentGuard | Agents, beliefs, intentions, knowledge |
| SpaceGuard | Spatial objects/relations |
| ResourceGuard | Resources, quantities, units and constraints |
| CausalGuard | Variables, graph/equations, scenarios and declared interventions/counterfactuals |
| ConflictGuard | Agents, actions, payoffs and conflict model |
| NormGuard | Norms, facts and rule priorities |

Field formats and copyable examples: [guard-inputs.md](guard-inputs.md). Missing consumed inputs produce typed gaps.

WorldGuard derives the Guards from the claim semantics and the kinds of `claim.asserts`. `claim.target_guards` is optional: it is reported back as `omitted_guards` / `unexpected_guards` but never shrinks or blocks the derived set. `claim.target_guard` is retired. Prediction derives EventGuard plus CausalGuard. Unknown semantics do not fall back to the caller's Guard list; they stay visible as `QUALIFICATION_SEMANTIC_UNMAPPED`.

Run a contract with `python <skill-root>/scripts/run_worldguard.py check --contract <file.yaml>`, or `run_worldguard(contract)` in Python.

## Results

Each Guard result keeps its exact `status`, missing slots, boundary findings, errors and counterexamples. Non-pass needs concrete evidence rather than narrative assertion. The report keeps `structural_status`, `semantic_status` and the final `status` separate; a final `PASS` requires every applicable axis to pass with zero gaps, including every claim assertion. A claim without `asserts` is `GAP` `CLAIM_NOT_BOUND` (claim not bound to the world model); a false assertion is `FAIL` `CLAIM_ASSERTION_FALSE`; an assertion naming something the model does not declare is `GAP` `CLAIM_ASSERTION_UNRESOLVED`. Structural pass alone is insufficient.

## Conditional work

Prediction/task revision fields, original and independent holdout observations, gap progression and finite stopping rules are in `task-local-model-deepening.md`. Fact-support transactions, four-valued states, previews and activation gates are in `fact-revision.md`. Load these only on their declared triggers. Reusable construction is in `template-packs.md`.
