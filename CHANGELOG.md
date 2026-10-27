# Changelog

## Unreleased

- The input stage model requires checks to name every input file.
- check reports input_digests: the sha256 of every file the verdict read.

- Maintenance checks run on FlowGuard 0.70.13.

## v0.7.22 - 2026-10-24 - The whole world on the readback

### Readback

- `timeline` shows each claim row with its result, one line per declared agent, space, conflict and norm sub-model, the event steps, and every problem of the check, not only those on an event: causal problems are marked on their scenario's variables line and the rest are listed under `problems:`. `--json` adds `claims`, `submodels` and `problems`. Mesh timelines label each world by its node id.
- Mesh tree lines show each node's own status, its subtree status when that differs, each continues edge's result and codes, and `GAP planned` for a node without a contract; the root line now agrees with the overall status.

### Checks

- A single token's place must agree with the spatial relations declared at the same time: a contradiction fails with `WORLD_SPACE_TOKEN_MISMATCH` and an unrelated place is a GAP `WORLD_SPACE_TOKEN_UNRELATED`. The check runs whatever semantics the claim requests; worlds without spatial relations are unaffected.

### Skill

- The skill starts from the model: read an existing world or tree first, or build one in five steps (claim rows, the inputs they need, one known-bad variant per claim, a tree for chapters or days, contract-less planned nodes). The as-happened copy written by `compare --write-observed` is no longer called the target.

### Maintenance

- WorldGuard's own model tree is checked with FlowGuard 0.70.12 and gains a model of the seven Guards over their good and bad catalog cases.
- Runtime modules put one statement per line and use only public names across components; behaviour is unchanged.

## v0.7.21 - 2026-10-24 - One world format and one model tree

### New

- Check a connected model tree with one root. `parent_child` scopes parent assertions to descendants; `continues` compares real end/start state, event times, unique tokens and requested variables. Tree summaries retain every node's own result; independent failures remain visible when other information is missing.
- Declare `variants` on a whole tree. Contract files are embedded before applying finite in-memory edits; each bad tree must produce its declared status and code. Missing or ambiguous edit paths remain input errors.
- `timeline` prints readable text by default and accepts a world, a mesh or a portable example; `--json` retains the full structure. `mesh-check` includes a text tree. The story tree is packaged once with the portable skill.
- Compare a world or selected tree nodes with observations. Results name the compared `id` and, for a tree, its `node`. `--write-observed OUT` creates an independent embedded copy changing only the selected event times; it does not write variables, add scenarios or move later events, and never overwrites an existing file.
- A token transition in an eventful world must name its firing event; missing links produce `GAP RESOURCE_TRANSITION_UNLINKED`. Known same-name event fluents and token places must agree initially and after each complete event step, otherwise `FAIL WORLD_EVENT_TOKEN_MISMATCH`. Simultaneous unknown writes stay unknown until an actual later write resolves them.

### Changed

- Worlds use one contract form. Guards derive from `claim.requested_semantics` and `claim.asserts`; dead contract and mesh metadata are rejected by key presence with a migration instruction. A mesh uses only `model_id`, `contract`, `source` nodes and `from`/`to` edges of the two supported kinds.
- Native node, child and tree findings aggregate without hiding an independently known failure. Missing times remain gaps; malformed clock values remain typed input errors. Sources remain unchecked pointers to original text.
- The skill uses the shared seven-line description of structure, counterexamples, bad variants, real bindings, observation tests, readback and current/edited models. Component names and five modeled flows follow the actual runtime jobs.
- Maintenance checks of WorldGuard's own model tree now run on FlowGuard 0.70.11; pytest has an explicit minimum supported version.

### Removed

- The packaged fuel-cell toy example and its second world format. Start from `check --example scene|trip`, or `mesh-check --example story`.
- Runtime Guard catalogs, authority/port/freshness bookkeeping and alternative mesh relation types. The original good/bad Guard regression cases live in tests; native domain rules and failure classes remain.
- Three obsolete historical specifications and audit notes; active OpenSpec requirements and archived changes remain.

### Upgrade

- Remove retired contract and mesh keys, including null or empty declarations. Use `from` and `to` for node edges, add a true root for independent chapters, and place each resource transition under its real event. Keep resource-only worlds unchanged.
- FlowGuard references use the official GitHub tag. Installation, launcher paths and the original LogicWriting provider interfaces stay portable; LogicWriting's three eventful fixtures need an explicit `give_spare` event link when its own migration is applied.

## v0.7.20 - 2026-10-23 - Preserve failures when other evidence is incomplete

- Keep independently known event precondition failures when other event metadata is missing or simultaneous events have no declared order. Conflicting simultaneous fluent writes remain uncertain until a later definite write.
- Keep missing event times in a continued world tree as gaps with the native node reports. Preserve independently decidable handoff failures and reject `port_mappings` whenever it is supplied on a `continues` edge. Serialized continuations omit that field so a valid tree can be loaded again.
- Preserve typed native Guard gaps for malformed event or transition records when adding source references and trace context or checking an entity registry.

## v0.7.19 - 2026-10-23 - Stateful world trees and observation comparison

- Connect successive models with `continues`. Check final-to-initial fluents, forward event time, shared unique token locations and optional causal scenario variables. Missing variable values remain gaps; conflicting values fail.
- Use `parent_child` for containment without requiring ports. Parent `node:` assertion rows can read descendants, while every child keeps its own result. Mesh summaries include root counts.
- Load node contracts from YAML or JSON paths relative to the mesh file. Invalid `freshness_status` values are now input errors instead of silently becoming unknown.
- Compare plans with actual observations using `compare --contract --observed`. Expected times and scenario values come from the world; results name matches and mismatches with declared tolerances. ISO and clock time differences use minutes.
- Run the existing story and trip worlds with `check --example scene` or `--example trip`, including from an installed skill. Keep the fuel-cell toy example and use the new two-part story mesh as a starting point.
- Read a shorter skill entry and three runnable references: `guard-inputs.md`, `worldguard-contracts.md` and `model-mesh.md`. Authority and reporting guidance now live in the mesh reference.
- Model handoff rules with independent known-bad variants and native CLI replay; extend the world-check model to cover observation tolerances.

## v0.7.18 - 2026-10-23 - One clock, native problems and testable worlds

- Short summaries now contain `status`, `checked`, `gaps` and `scope_limits` (plus `contract_id` for a unit), with one row per problem. Full reports contain native `guard_results` and claim rows, or mesh `nodes`. Removed `structural_status`, `semantic_status`, `non_pass_guards`, parallel execution axes, result attestations and duplicate pointer findings. Exit codes and the four statuses keep their meanings; mesh `provider_availability` is now rejected as retired input.
- Each Guard owns its complete checks once. Native error codes lose the `SEM_` prefix; event contradiction/missing-axiom/missing-events become `EVENT_CONTRADICTORY_FLUENTS`, `EVENT_MISSING_INITIATION_AXIOM` and `EVENT_MISSING_EVENT_MODEL`. Space conflict, converse and reflexivity codes become their `SPACE_RCC8_*_CONTRADICTION` names; missing RCC8 becomes `SPACE_MISSING_RELATION`. Resource double consumption becomes `RESOURCE_CUMULATIVE_OVERCONSUMPTION`; missing resource, agent and norm models use `RESOURCE_MISSING_RESOURCE_MODEL`, `AGENT_MISSING_BELIEF` and `NORM_MISSING_NORM_MODEL`. Causal missing equations, rollout error and unevaluable constraints become `CAUSAL_MISSING_STRUCTURAL_EQUATION`, `CAUSAL_SCENARIO_UNEVALUABLE` and `CAUSAL_CONSTRAINT_UNEVALUABLE`; invalid conflict transitions become `CONFLICT_INVALID_PROBABILITY`. Removed structural/semantic qualification pointer codes. Claim and mesh problem codes remain stable.
- Use `t_<event_id>` in causal expressions, link resource transitions with `event`, and declare `resources.unique`, event `actor`/`with`/`action` and optional `world_model.entities`. Event times drive equations and token order directly. The first impossible token transfer is now `FAIL`; invalid inventory is `GAP` `RESOURCE_UNEVALUABLE_INVENTORY`. New problems identify `RESOURCE_UNIQUE_TOKEN_DUPLICATED`, `RESOURCE_EVENT_PARTICIPANT_UNNAMED`, `ENTITY_UNDECLARED` and `EVENT_SAME_TIME_ORDER_UNKNOWN`.
- Norms can use fluent conditions at the event time. Actual prohibited actions fail with `NORM_VIOLATED_BY_EVENT`; declared intentions without matching actor/action events produce `AGENT_INTENTION_UNREALISED`. Qualitative spatial checks use the complete RCC8 composition table on declared relations and their converses.
- Declare in-memory known-bad edits under `variants`; an unexpected status or missing expected code produces `VARIANT_NOT_CAUGHT`. Read a world with `timeline --contract`, retain original locations through `source`, and inspect event prefixes in full counterexamples. Both worked worlds ship with variants and use the shared native replay functions.
- Maintenance: extend the executable world-check model, its known-bad variants and native replay tests, and align the component map and installed skill checks.

## v0.7.17 - 2026-10-22 - Simpler world checks with strict clocks and honest outcomes

- Event times are now strict: use numbers, one label prefix such as `t1`, ISO dates/times with one timezone convention, or quoted `HH:MM[:SS]` clocks. Unknown or mixed formats and duplicate `event_id` values within one scenario exit 2. Replace informal times with one supported format, quote YAML clocks, and select `scenario` when event ids repeat across scenarios. Missing times remain gaps without hiding known failures in independent scenarios.
- Scenario and holdout assignments replace equations for those variables. Write interventions as a list with unique ids, a declared scenario and numeric assignments; interventions also run on empty scenarios and participate in constraints and claim assertions. Completed runs keep their real outcomes when another run is incomplete.
- A declared unsupported boundary of a derived Guard returns `BOUNDARY_EXCEEDED`; a boundary owned only by an unselected Guard remains a gap. Real failures and missing inputs keep priority.
- Removed the `blueprint` and `task-model` commands, fact and task-local revision, template packs, mesh `semantic_coverage` and the separate prediction license. Edit the explicit contract and run `check` or `mesh-check` again; copy a shipped example to start a model. A `compare` command is planned for a later version.
- Maintenance: stop tracking the work log, check excess blank lines, model the core check path with known-bad variants and real CLI replay, layer the self-map, and run a strict map check in CI.

## v0.7.16 - 2026-10-21 - Claims bound to the world model; slim/2026-10

- Done: WG-01 to WG-60. Skipped: none.
- Claims are bound to the world model: each `claim.asserts` row (a fluent at a time, event order, tokens in a
  place, a variable value, an agent's belief/desire/intention, a spatial relation, an active norm, a payoff) is
  evaluated on the model. A false row is `FAIL` (`CLAIM_ASSERTION_FALSE`, with the observed value), a row naming
  something the model does not declare is `GAP` (`CLAIM_ASSERTION_UNRESOLVED`), and a claim without `asserts` is
  `GAP` (`CLAIM_NOT_BOUND`), in unit checks and in every mesh node. The claim text is never read.
- Model language: EventGuard checks `events[].requires` (`EVENT_PRECONDITION_UNMET`); CausalGuard checks
  `causal_model.constraints` (`CAUSAL_CONSTRAINT_VIOLATED`). Template packs have a `claim_asserts` slot.
- Fixed: verdicts that depended on words in the claim text, fixture strings in Guards, the missing NormGuard
  conflict rule, the fuel-cell example, crashes on minimal contracts, event time order, exit codes (0 PASS,
  1 non-pass, 2 input error), the README mesh example, empty `intentions`. Default output is a short JSON
  summary; `--json` prints the full report.
- Removed SkillGuard-era proof machinery: self-DNA, the execution-depth bridge, route capsules, provider receipt
  replay, sealed task-local receipts, mesh depth replay, blueprint request fingerprints, the signed object census,
  the blueprint completeness and projection layers, template construction fingerprints, retired ledgers and
  tautology self-models. The portable runtime copy is made by `scripts/install_skill.py` instead of committed.
- The three self-models are FlowGuard contract models in `.flowguard/models/` (`MODEL_ID`, `COMPONENTS`,
  `IMPLEMENTED_BY`, `TESTED_BY`, `build_explorer()`, `broken_variants()`, `conformance()`): each explores its
  design, carries known-bad variants that must fail, replays every case on the real code, and passes with
  FlowGuard 0.70.6 and 0.70.7. The template model and a unit test cover a pack that misses a claim-derived
  Guard route.
- Cross-repo pass: XR-04; skipped none. Details in the cross-repo action list.
- Malformed contract or mesh shapes (for example `claim: null` or a node that is not a mapping) exit with code 2 and `WORLDGUARD_INPUT_INVALID` instead of a Python error.
- A causal constraint that divides by zero or compares a non-number is reported as `CAUSAL_CONSTRAINT_UNEVALUABLE` instead of crashing.

## v0.7.15 - 2026-10-18

- Evaluate pending SCM equations without stale endogenous scenario seeds, preserving identity roots, exogenous inputs and explicit do overrides regardless of variable declaration order.
- Define resource transitions as the existing finite ordered CPN firing trace and make semantic replay carry produced tokens into later consumption; no scheduler or time simulation is inferred.
- Retain real semantic execution sources in native depth receipts and rederive all nested predictive coverage and license values with the existing native assessment. Task closure rejects unsupported older receipts without these sources, shallow summary overrides and sources from different candidate inputs.
- Require native semantic receipt bodies for original/holdout revalidation, bound to current candidate inputs and actually executed scopes. A recorded batch covering both scopes may be reused; the two empirical observations must still have independent identities, sources, evidence and content, and construction evidence cannot substitute for a holdout.
- Preserve seven default models and ordinary native refusal paths; clarify the task-local model runner executes finite scenarios without nesting native tests. Synchronize the portable runtime from canonical source.

## v0.7.14 - 2026-10-18

- Align ordinary closure instructions with derived Guards and direct native execution while retaining target-local blueprint oracles and SCM gaps.
- Preserve claim boundaries, explicit model/test `not_run` fields and actionable gaps in compact repository self-DNA reports.
- Remove three historical requirements sketches (`hierarchical_model_mesh`, `model_test_code_alignment`, `test_evidence_mesh`) from the default map registry; retain their compatibility files. Their Boolean sketches do not validate native implementations. The seven remaining models and all ordinary test bindings remain active.
- Synchronize the portable runtime from canonical source and publish one frozen patch identity.

## v0.7.13 - 2026-10-17

- Partition the living map into native responsibilities while keeping canonical and generated runtime files together under each logical owner.
- Preserve all 33 ordinary test-file bindings and 10 existing model runners; explicitly share the runtime-identity regression across every canonical owner so dynamic byte scans remain selected.
- Narrow template changes to their caller closure and template model without changing domain implementation or removing native checks.
- Synchronize the portable runtime from the canonical patch-version authority.

## v0.7.12 - 2026-10-17

- Remove retired SkillGuard supervision, contracts and transport; use plain native checks, current map bindings and ordinary pytest owners.
- Run existing world models directly without per-task checker-purpose proofs. Preserve all seven Guards, native predictive depth, task/candidate binding, blueprint behavior cases, independent tests and signed census trust.
- Keep task/fact/blueprint/template details conditional; retire unused neutral template interchange and repeated author-wrapper execution.
- Load public API owners and CLI features on demand. Preserve portable launcher, native statuses and public object identities.
- Report the optional FlowGuard target-blueprint projection as a complete-denominator gap until an independent provider exists; native checks remain available.
- Synchronize the portable runtime from canonical source and publish this patch from the same main/tag/Release commit.

## v0.7.11 - 2026-08-12

- Keep the native WorldGuard directory, models, code/test bindings, and
  current evidence as the DNA authority.
- Refresh the self-model and portable consumer projection for the current
  FlowGuard authority without adding a standalone DNA bundle or routine
  reconstruction step.

## v0.7.10 - 2026-08-12

- Repair the current FlowGuard authority chain from the last complete verified head.
- Keep the native directory/model/code/test binding as the DNA; remove no alternate compatibility path.
- Refresh the release-gate and bundled-runtime version bindings to `0.7.10`.

## v0.7.9 - 2026-08-12

- Keep the native WorldGuard directory as the DNA authority, including
  models, code/test bindings, and current evidence; no standalone self-DNA
  package is produced.
- Remove the retired self-bundle route while preserving explicit target-owned
  object projections for external WorldBlueprint work.
- Refresh the WorldGuard model authority and portable consumer projection for
  this patch identity.

## v0.7.8 - 2026-08-11

- Keep the native WorldGuard directory as the DNA authority, including models,
  code/test bindings, and current evidence; no standalone DNA transport file
  is produced.
- Refresh the self-model, object-DNA qualification, and internal guard
  topology for the current provider and patch identity.
- Synchronize the source package and consumer projection without touching
  parallel model-mesh work.

## v0.7.7 - 2026-08-11

- Keep WorldGuard DNA in its native directory: model files, code bindings, and
  test evidence remain first-class and no standalone transport bundle is
  emitted.
- Refresh the native self-model and consumer projection after the FlowGuard
  0.68.11 upgrade.

## v0.7.6 - 2026-08-10
- Synchronize the WorldGuard package and portable consumer projection with
  the provider-neutral FlowGuard software-DNA boundary.
- Refresh WorldGuard self-DNA, external-object qualification, code/test
  bindings, model mesh, and regression identities for this patch release.

## v0.7.5 - 2026-08-10
- Synchronize the WorldGuard package and portable consumer projection to the
  patch release without rewriting the parallel model-mesh work.
- Preserve the current ten-model DNA authority and its explicit coverage gaps;
  historical model receipts remain immutable.

## v0.7.4 - 2026-08-10

- Refresh the WorldGuard package, portable runtime, and model-regression identities.
- Keep target-object DNA qualification bounded to its declared target and evidence boundary.
- Regenerate the clean consumer projection from the current source version.

## v0.7.3 - 2026-08-09

- Complete the WorldGuard self-DNA spine with current model, code, test,
  target-material, and installation bindings.
- Keep object-blueprint qualification bounded to the declared world target
  and its own evidence boundary.

## v0.7.2 - 2026-08-08

- Synchronized the current WorldGuard package, portable runtime projection, and model-regression identities for the patch release.
- Preserved the strict WorldBlueprint object-DNA qualification boundary and its visible external-authority gaps.

## v0.7.1 - 2026-08-01

- Contracted the always-loaded WorldGuard prompt into one task-shape entry and
  conditional route references while preserving all seven internal Guards and
  complete multi-Guard claim-derived coverage.
- Added machine-checkable task-shape and Guard capsules, prompt load-graph and
  budget checks, and explicit predictive deepening without understanding
  levels, keyword authority, caller-subset authority, retry, or fallback.
- Moved the existing evidence-derived task-local deepening protocol behind the
  EventGuard/CausalGuard predictive trigger and repaired the governed OpenSpec
  input to its stable main specification.

## v0.7.0 - 2026-07-31

- Replaced former shallow task-local prediction/revision shapes with one strict
  current schema binding task purpose, independent coverage, assumptions,
  unknowns, exact iteration predecessor, and later-iteration prior gap ids
  bound to their current fingerprint.
- Added content-addressed observation, native execution-depth, semantic
  rollout, original-scenario, and real-holdout receipts; candidate closure now
  derives seven predictive gap classes and evidence independence instead of
  accepting caller-authored gap, progress, or `PASS` strings.
- Made fact activation an intermediate same-task/same-owner revalidation
  handoff. It can no longer emit `model_closed_for_task`.
- Added exact stall, iteration-limit, external-input, tamper, holdout-alias,
  rejection, rollback, and multi-evidence regression coverage, and extended
  FlowGuard/SkillGuard ownership for the task-local closure check.

## v0.6.0 - 2026-07-31

- Added task-local world-model deepening with explicit prediction, gap
  transitions, next actions, progress, and terminal reasons.
- Added evidence-bound fact-revision lifecycle fields and synchronized the
  bundled consumer runtime with the source implementation.

## v0.5.0 - 2026-07-30

- Added task-local four-valued fact revision with independent positive and
  negative support, visible contradictions, strict-rule closure, and no
  explosion into unrelated facts.
- Added immutable revision previews and evidence-bound activation with exact
  base/preview identity, preservation checks, contradiction acknowledgement,
  current regression and holdout evidence, and duplicate transaction blocking.
- Added the native CLI, Codex skill route, target-owned semantic check,
  FlowGuard regression model, and behavior-commitment ownership for the new
  revision path.
- Restored current source/package/bundled-runtime identity and expanded the
  author-side SkillGuard contract from five to six exact target checks.

## v0.4.1 - 2026-07-22

- Adopt SkillGuard 0.4 bounded evidence lifecycle without changing WorldGuard's target-owned semantic checks.
- Remove copied FlowGuard author-control surfaces from the consumer repository and keep one WorldGuard maintenance unit.
- Preserve exact consumer projection parity and fail closed on stale installation evidence.

## v0.4.0 - 2026-07-19

- Corrected release-readiness validation so author-side SkillGuard control stays
  in the source repository while the installed consumer contains zero
  `.skillguard` paths.
- Added exact source/manifest/installed consumer inventory and hash checks.
- Removed normal-runtime readers for retired claim, claim-atom, world-model,
  and semantic-coverage aliases; old files now require direct upgrade migration.
- Synchronized package metadata, bundled runtime, installed consumer, Git tag,
  and GitHub Release identity for the release.

## v0.3.0 - 2026-07-18

Single-entry internal-Guard source candidate. This source heading does not by
itself assert a Git tag, hosted GitHub Release, or installed projection.

- Kept `worldguard` as the sole public Codex skill and package console.
- Formalized EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard,
  ConflictGuard, and NormGuard as seven complete internal routes with their own
  expectation/prediction boundary, native response, semantic validation, and
  visible terminal behavior.
- Added exact root/bundled runtime parity and source-version identity checks.
- Removed current authority from the retired `worldguard/skillguard_depth.py`
  validation path without adding an alias, fallback, or compatibility reader.
- Treats the public child-entrypoint contraction as the breaking minor step
  appropriate for the pre-1.0 package line.

## v0.2.0 - 2026-07-15

Purpose-declared world-claim and model-mesh release.

- Required each WorldGuard model to declare the concrete impossible,
  inconsistent, underspecified, conflicting, or unsupported world state it is
  intended to block for the current task.
- Added purpose, boundary, witness, counterexample, safe-claim, and closure
  evidence across unit contracts and model meshes while preserving the
  existing Event, Agent, Space, Resource, Causal, Conflict, and Norm families.
- Strengthened mesh ownership, handoff, freshness, cycle, field lifecycle,
  sibling impact, and ledger-preservation checks for multi-model claims.
- Replaced former SkillGuard authorities with target-owned declared checks
  under generic immutable-receipt supervision and fixed enforced closure.
- Updated package code, examples, tests, OpenSpec records, FlowGuard evidence,
  and the maintained WorldGuard skill.

## v0.1.2 - 2026-07-07

- Added `python -m worldguard` as a thin wrapper around the existing CLI.
- Hardened the WorldGuard SkillGuard contract boundary so duplicate SkillGuard-owned execution paths are invalid.
- Added OpenSpec/FlowGuard release tracking for simulation readiness and local install synchronization.

## v0.1.1 - 2026-06-27

- Added SkillGuard runtime-contract governance for the installed WorldGuard Codex skill materials.
- Synchronized installed skill copies with accepted source material and local git evidence.
- Recorded release-scope validation so route selection, evidence gates, quality floors, and closure boundaries remain visible before completion claims.

## v0.1.0 - 2026-06-22

First source-only release.

### Added

- Installable Python package `worldguard`.
- CLI checks for unit contracts and model meshes.
- Seven guard families: Event, Agent, Space, Resource, Causal, Conflict, and Norm.
- `GuardContract` runtime for unit-level world-claim checks.
- `ModelMeshContract` runtime for multi-model authority, handoff, freshness, cycle, and ledger-preservation checks.
- Toy fuel-cell fixture for regression checks.
- Generic model-mesh example fixture.
- Repository copy of the WorldGuard Codex skill.
- OpenSpec and FlowGuard records for the MVP and ModelMesh work.

### Boundaries

- This release does not claim real fuel-cell physics, legal compliance, safety certification, deployment readiness, market truth, or business-strategy proof.
- This release is source-only and does not include binary installers or packaged desktop assets.
