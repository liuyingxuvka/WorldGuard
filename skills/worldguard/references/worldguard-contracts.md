# WorldGuard Contracts

`GuardContract` checks one claim against one current explicit world model. `ModelMeshContract` adds multi-node topology, authority, freshness, handoffs, and coverage; read `model-mesh.md` only for that shape.

## Unit input

Keep `contract_id`, `schema_version`, `run_id`, `claim`, `world_model`, `inputs`, `dependencies`, and `output_requirements`. The claim carries id/text and structured `requested_semantics` or atoms; atoms retain stable ids, text, semantics, and predictive intent. `world_model` records model id/version, entities, relations, assumptions, and scope limits. Supply the input fields consumed by each derived Guard, not every possible field:

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

Use `derive_guard_requirements(claim)` as the single semantics-to-Guard authority. Its denominator, unmapped semantics, and canonical fingerprint are shared by unit, mesh, and prompt audit. `claim.target_guards` must exactly reconcile with the denominator. Omitted derived Guards make the aggregate `GAP`; the native owner may still execute the derived set to provide diagnostics. Unexpected declared Guards block execution. `claim.target_guard` is retired. Prediction derives EventGuard plus CausalGuard. Unknown semantics do not fall back to the caller's Guard list.

Existing contracts run directly: `run_worldguard(contract)`. `for_guard` creates a read-only child retaining task/run/model, claim, inputs, and upstream identities. Ordinary contracts do not carry `guard_purpose_declarations` or `guard_purpose_contract`. The author-owned 7-good/81-bad catalog is a regression check, not a per-use admission step. Domain-specific BlueprintTaskPurpose still binds actual blueprint behavior cases; see the blueprint reference when selected.

## Results and qualification

Each `GuardResult` retains `result_id`, `contract_id`, `guard`, exact `status`, supported/rejected claims, missing slots, boundary findings, errors, counterexamples, ledgers, assumptions, scope limits, and `consumed_inputs`. Non-pass needs concrete evidence rather than narrative assertion.

`GuardedReport` reconciles the full derived Guard set and executes the current structural and semantic owners. Mesh consumes this same node report read-only instead of repeating semantics. Keep these axes separate:

- declared/derived/effective/omitted/unexpected Guards, unmapped semantics and derivation fingerprint;
- native results and semantic receipts;
- structural, semantic, provider, rollout/depth, predictive-license and final statuses;
- exact target/contract/provider identities, content fingerprints and claim boundary;
- gaps, read-only ledgers, scope limits and final qualification fingerprint.

A supplied provider envelope must exactly match the active executor/capability, target/revision, contract, boundary and current semantic content/receipt fingerprints. Missing or mismatched identity is `STALE` with semantic `NOT_RUN`; no field is invented from a fallback. Without an external envelope, the current native execution supplies its own identity. A final `PASS` requires all applicable axes and zero gaps. Structural pass alone is insufficient.

Ledger entries retain run/claim/Guard, channel, status impact, payload, source refs, step and `read_only_for_downstream`. Each obligation retains its own typed `evidence_ref` and the exact lowercase current-owner content hash; an aggregate pass cannot replace it.

## Conditional work

Prediction/task revision fields, original and independent holdout observations, depth bindings, gap progression and finite stopping rules are in `task-local-model-deepening.md`. Fact-support transactions, four-valued states, previews and activation gates are in `fact-revision.md`. Load these only on their declared triggers. Hierarchical blueprint behavior/census/trust is in `world-blueprint.md`; reusable construction is in `template-packs.md`.
