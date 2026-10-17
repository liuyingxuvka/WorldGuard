# WorldGuard Field Lifecycle Review

Route: `field_lifecycle_mesh`

## Field Boundary

Boundary: public runtime dataclass/dict fields, fixture fields, CLI payload fields, and Codex skill prompt contract fields introduced for the WorldGuard MVP.

## Contract Fields

| Field id | Owner | Readers | Writers | Lifecycle | Projection |
|---|---|---|---|---|---|
| `contract_id` | `worldguard.contracts` | Kernel, tests, CLI | contract loader | new | behavior-bearing identity |
| `schema_version` | `worldguard.contracts` | validators, tests | contract loader | current-only | exact schema validation; retired shapes fail visibly |
| `run_id` | `worldguard.contracts` | ledgers, reports | contract loader | new | traceability |
| `claim.claim_id` | `worldguard.contracts` | all Guards, ledgers | contract loader | new | behavior-bearing |
| `claim.text` | `worldguard.contracts` | all Guards | contract loader | new | behavior-bearing |
| `claim.target_guards` | `worldguard.contracts` | Kernel, mesh coverage audit | contract loader | preserved | declared dispatch routes; not the coverage authority |
| `claim.target_guard` | none in normal runtime | upgrade AI only | no product writer | retired and rejected | old files must be migrated directly to `target_guards` before normal use |
| `claim.requested_semantics` | `worldguard.contracts` | Guards | contract loader | new | boundary checks |
| `claim.atoms.*` | `worldguard.contracts` | route derivation, native depth receipt | contract loader | new | structured claim identity, semantics, and predictive intent |
| `world_model.*` | `worldguard.contracts` | Guards, examples | contract loader | new | model inputs |
| `inputs.*` | `worldguard.contracts` | Guards | contract loader | new | model inputs |
| `dependencies.upstream_results` | `worldguard.contracts` | Kernel, downstream Guards | Kernel | new | handoff |
| `dependencies.read_only` | `worldguard.contracts` | Kernel, tests | contract loader/Kernel | new | mutation guard |
| `output_requirements.*` | `worldguard.contracts` | validators, tests | contract loader | new | result validation |

## Result And Ledger Fields

| Field id | Owner | Readers | Writers | Lifecycle | Projection |
|---|---|---|---|---|---|
| `result_id` | `worldguard.reports` | Kernel, tests | Guard runners | new | traceability |
| `status` | `worldguard.reports` | Kernel, CLI, tests | Guard runners | new | aggregate behavior |
| `missing_slots` | `worldguard.reports` | tests, CLI | Guard runners | new | GAP evidence |
| `boundary_exceeded` | `worldguard.reports` | tests, CLI | Guard runners | new | BOUNDARY evidence |
| `errors` | `worldguard.reports` | tests, CLI | Guard runners | new | non-pass evidence |
| `counterexamples` | `worldguard.reports` | Kernel, tests | Guard runners | new | FAIL/GAP evidence |
| `ledgers` | `worldguard.reports` | Kernel, tests | Guard runners | new | traceability |
| `read_only_for_downstream` | `worldguard.ledgers` | Kernel, tests | ledger helpers | new | handoff invariant |

## Task-Local Prediction And Revision Fields

| Field id | Owner | Readers | Writers | Lifecycle | Projection |
|---|---|---|---|---|---|
| `task_id` / `purpose` | `worldguard.task_local_world_revision` | prediction freezer, candidate evaluator, fact handoff | current task author | required current | binds every receipt to one finite question instead of an AI self-report |
| `coverage_universe_*` / `coverage_ids` | independent task coverage inventory | prediction freezer, comparisons, native-depth binding | independent coverage owner | required current | fingerprint is recomputed and ids must exactly equal declared expectation ids |
| `assumptions` / `unknowns` | current task author | prediction and claim-boundary reviewers | current task author | required non-empty | makes the model boundary explicit without recording an understanding level |
| `predecessor_iteration_fingerprint` | task-local revision owner | later iteration evaluator | prior terminal receipt owner | `root` at iteration zero, content hash later | preserves exact lineage |
| `prior_gap_ids` / `prior_gap_fingerprints` | task-local revision owner | gap transition evaluator | prior terminal receipt owner | empty at iteration zero; exact ids plus bound fingerprint later | replaces caller-authored progress and transition maps |
| `observation_evidence_fingerprint` | observation provider | comparison and revalidation | canonical observation hasher | required current | binds ids, source, sequence, values, relations, and external inputs |
| `observation_content_fingerprint` | comparison owner | holdout independence check | canonical content hasher | derived current | detects renamed original/holdout content aliases |
| `native_depth_receipt` | WorldGuard native-depth owner | candidate evaluator | task-local depth binder | exact `worldguard.native_depth.v2` only | binds task, candidate, coverage, seven-category gaps, quantitative coverage, and predictive license |
| `required_revalidation_ids` | task-local revision owner | candidate evaluator | current candidate plan | exactly original plus real holdout | rejects renamed or extra pseudo-checks |
| `semantic_receipt` / `empirical_comparison` | WorldGuard semantic and empirical owners | candidate evaluator | typed binding helpers | current content-addressed | replaces a bare `PASS` string |
| `terminal_reason` | task-local revision owner | caller and fact handoff | deterministic evaluator | derived only | only this owner can emit `model_closed_for_task` |

## Native execution depth

| Field id | Owner | Readers | Writers | Lifecycle | Projection |
|---|---|---|---|---|---|
| `native_minimum_timepoint_count` | WorldGuard temporal-depth policy | per-node/per-variable assessment, native floor receipt | `ceil(sqrt(horizon_steps))`, bounded by the horizon and raised only by stricter target policy | replaces the weaker logarithmic default | prevents a very long horizon from passing with a token handful of points |
| `max_normalized_timepoint_gap` | WorldGuard temporal-depth assessment | predictive license, per-object receipt, diagnostics | exact sorted observed coordinates plus horizon boundaries | current per run and per model-node/variable child | blocks count-complete samples that leave a large unobserved temporal hole |
| `allowed_max_normalized_timepoint_gap` | WorldGuard temporal-depth policy | predictive license and receipt consumer | `min(0.5, 2.5 / max(observed_count - 1, 1))` | current target-native policy | lets a complete three-point early/middle/late short horizon pass while tightening quickly for larger samples and preventing clustered sampling |
| `native_obligation_evidence` | WorldGuard native depth receipt | native closure, report | exact semantic-child inputs/outputs, per-node/per-variable temporal rows, scenario/holdout portfolio, predictive axes, native policy, and claim routes | current per run; every observation is content-addressed | prevents counts, names, or a whole-receipt digest from substituting for exact per-obligation proof |

## Old Field Disposition

- `claim.target_guard`: rejected in normal runtime. Upgrade AI must rewrite old files directly to `claim.target_guards` before activation.
- `claim.target_guards`: current execution declaration. Structured semantics own required-route derivation; missing semantic structure or derived routes fails closed.
- Root `evidence/` fixture paths: preserved as historical input sources, copied into `examples/fuel_cell/` for productized use, and excluded from Git/package core surface.
- Former optional task fields, `remaining_predictive_gap_ids`, caller-authored transition maps, and boolean progress fields: rejected in normal runtime; no compatibility reader or migration fallback exists.
- Fact activation `model_closed_for_task`: retired. Current activation emits only `task_local_revalidation_required` to the same task owner.

## Handoffs

- Field projections feed `tests/test_contracts.py`, `tests/test_kernel_handoff.py`, and the Codex skill prompt contract.
- Retired public fields may be read only inside a bounded transactional upgrade that rewrites them directly to the current schema and removes all residuals before activation.
