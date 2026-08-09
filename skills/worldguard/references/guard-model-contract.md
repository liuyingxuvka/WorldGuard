# Guard Model Contract

A WorldGuard model is meaningful only when it names the invalid claim class it
prevents. Wiring a model into the kernel is not evidence that the model blocks
anything.

## Family Baseline And Native Oracle Catalog

The table below is not a permanent purpose assignment for every future model.
It records the kinds of native reactions that the current WorldGuard family can
prove. A real task-model instance selects one or more relevant failures and
states its own purpose and boundary before construction.

| Guard | Prevents | Boundary it does not license |
| --- | --- | --- |
| EventGuard | Declared event/state/transition records with absent fields, contradictory fluents, or missing temporal/fluent axioms | Guard/effect truth, terminal reachability, continuous numeric dynamics, physical equations, causality, norms, and resource enablement |
| AgentGuard | BDI claims with absent/incomplete beliefs, desires, or intentions, or conflicting intentions | Payoff equilibrium, causal effects, resource tokens, and deontic permission |
| SpaceGuard | Qualitative spatial claims with missing, malformed, or inconsistent RCC8 relations | Metric geometry, sensor fusion, and continuous dynamics |
| ResourceGuard | Direct declared inventory validity or finite-resource claims without executable places/transitions, missing tokens, overflow, or combined over-consumption | Norms, permission, real physics, price, and causality |
| CausalGuard | Declared graph-only claims with malformed/cyclic edges or SCM claims with missing equations, unsafe expressions, or failed scalar rollout | Mechanism truth, temporal order alone, norms, resources, and game payoffs |
| ConflictGuard | Finite-game claims with incomplete games, invalid probabilities, missing payoffs, or policy contradictions | Deontic permission, physical enablement, and SCM causality |
| NormGuard | Deontic claims without applicable norms/facts or that contradict a prohibition | Physical enablement, resource availability, payoff optimality, and causal effects |

## Family Catalog Exhaustion Rule

`worldguard.guard_model_contract` discovers every literal error code in the
seven Guard runners and every per-Guard semantic finding code. The declared
inventory must equal that source-discovered set exactly.

For the current runtime:

- seven purposes are declared;
- every Guard has exactly one native good case, and both its unit runner and
  semantic executor must return `PASS`;
- 51 Guard-owned failure classes are protected;
- every protected failure class has exactly one native bad case;
- every bad case must emit exactly its expected status and single stable code;
- duplicate, missing, or extra failure cases block the contract.

`SEM_EXECUTOR_UNREGISTERED` and `SEM_PROVIDER_UNAVAILABLE` are intentionally
outside the individual-Guard inventory. They belong to mesh executor
registration and provider lifecycle respectively. Arbitrary unknown defects,
factual truth, installation parity, and release readiness are also outside this
specific receipt.

Run the native oracle from a source checkout with:

```powershell
python -m worldguard.guard_model_contract
```

Author-side maintenance may invoke a private adapter around this same native
oracle. That adapter must not duplicate or reinterpret WorldGuard purposes,
fixtures, failure classes, or oracles, and ordinary installed use does not
depend on it.

## Required Task-Model-Instance Declaration

Every parent `GuardContract` must contain exactly one
`guard_purpose_declarations` entry for every Guard child that may be derived
from the claim. Each entry contains:

- `declaration_id`, `task_contract_id`, `run_id`, `model_instance_id`, and
  `guard`;
- a plain-language `purpose` and explicit unsupported `boundary`;
- a non-empty, ordered, unique `selected_failure_ids` set;
- one task-local `known_good` with the WorldGuard native good oracle;
- exactly one task-local `known_bad_cases` row for every selected failure, with
  the exact native layer, expected status, stable code, inputs, and oracle id;
- `declaration_sequence: 1`, proving declaration precedes child construction.

The task may select one failure or several. Every selected failure is proved
separately. If a needed failure has no native oracle in the family catalog,
WorldGuard blocks until its runtime code, oracle, and family regression are
implemented. A downstream authoring tool cannot add that domain meaning.

`build_calibration_task_purpose_declaration` is deliberately named and scoped
for repository tests and packaged examples. Production code never calls it as
a fallback. A real input without its own declaration fails closed.

## Formal Candidate Binding

The seven-Guard/51-failure family oracle is necessary but does not by itself
authorize a real Guard proof. Before `GuardContract.for_guard` constructs a
formal child candidate, WorldGuard proves and freezes:

- the canonical family purpose-contract fingerprint;
- the exact task declaration fingerprint and proof-receipt fingerprint;
- all seven family Guard ids;
- the exact one-or-many failures selected by this task;
- the task, run, model instance, Guard, purpose, and boundary;
- the exact candidate contract id and the freeze-before-construction order.

The child carries that immutable snapshot as `guard_purpose_contract`.
`run_worldguard` and `execute_semantic` independently derive current
authority and compare it immediately before proof. They reject
`GUARD_CANDIDATE_PURPOSE_MISSING`, `GUARD_CANDIDATE_PURPOSE_STALE`,
`GUARD_CANDIDATE_PURPOSE_ORDER_INVALID`,
`GUARD_TASK_PURPOSE_DECLARATION_MISSING_OR_DUPLICATE`,
`GUARD_TASK_PURPOSE_FAILURE_UNIVERSE_EMPTY_OR_DUPLICATE`,
`GUARD_TASK_PURPOSE_NATIVE_ORACLE_UNKNOWN`,
`GUARD_TASK_PURPOSE_NATIVE_PROOF_FAILED`, and
`GUARD_TASK_PURPOSE_INSTANCE_MISMATCH` as applicable. A family-only binding,
an old fingerprint, an unknown oracle, an incomplete proof, or a copied fixture
cannot bypass those runtime gates.
