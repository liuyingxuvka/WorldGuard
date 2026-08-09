## Context

See `proposal.md` for motivation. The current worktree already contains the converged unit/mesh qualification path, strict native `WorldBlueprint`, affected/reverse queries, and the source-to-portable-runtime projection under active peer development. Static inspection confirms that mesh now consumes node qualification reports instead of executing a second semantic loop. The remaining design gap is broader: WorldGuard's FlowGuard records still describe selected behaviors rather than one complete, independently inventoried repository self-blueprint.

`WorldBlueprint` is a product capability for modeling an arbitrary world, workflow, experiment, software behavior, or other target. It is not the root model of the WorldGuard repository itself. The repository self-DNA must place that capability beside qualification, mesh, task-local revision, templates, CLI and skill routing, validation, portable projection, installation, and release behavior under one software root, while preserving the seven Guards as distinct semantic subtrees.

The existing self-models and behavior ledger remain useful affected owners, but they cannot derive the whole-repository denominator from their own file lists. A complete self-DNA needs an independent inventory of code and non-code surfaces, one disposition and one primary owner per item, explicit `Input × State -> Set(Output × State)` behavior, code/test/intent/resource/topology bindings, the seven provider-neutral static-readiness layers, and deterministic affected/reverse indexes.

FlowGuard is maintained by a separate owner and may change while this WorldGuard worktree is active. The current project audit is therefore a hard gate rather than planning authority: projection, self-DNA materialization, cleanup, and release wait until one released package/schema, project record, managed rules, and observed model-system identity agree. This change consumes only that frozen released contract and does not name or depend on provisional provider fields.

## Goals / Non-Goals

**Goals:**

- Establish one qualification owner used by unit and mesh routes, with exactly-once structural and semantic execution and one complete result.
- Add a target-neutral WorldGuard domain blueprint for worlds and workflows, including strict hierarchy, typed ports, stable semantic elements, role-separated bindings, and evidence-derived depth.
- Provide deterministic affected-only impact analysis and reverse trace without target mutation, provider execution, or whole-blueprint loading.
- Project the stable native blueprint into FlowGuard's generic blueprint system without copying FlowGuard's inventories, bindings, or affected-neighborhood implementation.
- Demonstrate the vertical slice with one three-level non-code planning workflow fixture and known-bad mutations.
- Keep the ordinary skill route lightweight and enforce deterministic prompt-size ceilings.
- Build one complete WorldGuard repository self-DNA root with seven Guard subtrees and shared product/process subtrees, while keeping the native `WorldBlueprint` as one product subtree.
- Derive the repository denominator independently, cover Python and non-Python behavior surfaces as peers, and bind every modeled FunctionBlock to intent, topology, implementation, tests, resources, evidence, and oracles.
- Support affected-only daily maintenance and explicit whole-static-blueprint qualification through seven provider-neutral layers, plus a separately qualified canonical external materialization that cannot fingerprint itself.
- Let the exact current self-DNA drive proof-gated architecture contraction and keep every uncertain or deliberately distinct path visible.

**Non-Goals:**

- Executing a target build or validating implementation equivalence; blueprint qualification in this change is static and evidence-bound.
- Making FlowGuard a mandatory dependency of ordinary WorldGuard checks.
- Reimplementing FlowGuard's generic source inventory, implementation/test/resource binding, model topology, or affected-neighborhood reader inside WorldGuard.
- Adding language-specific parsers or assuming the target is software or Python.
- Broadly deepening all seven Guard semantic engines beyond the native fields needed by this slice; bounded direct-current input alignment and honest claim-scope reporting are in scope, while theorem proving, reachability, factual truth, and other broader semantics remain outside the evaluated scope.
- Adding compatibility readers, aliases, dual result schemas, or fallback relation/template behavior.
- Treating the three-level fixture as proof that every possible world domain is already fully modeled.
- Treating the native `WorldBlueprint` payload as the WorldGuard repository inventory or self-DNA root.
- Rebuilding WorldGuard, executing every test, or exporting the whole self-DNA during ordinary affected-only work unless an explicit completeness or release gate requires it.
- Removing public facades, evidence planes, Guard axes, or source projections merely because files are small, similar, or repeated.

## Decisions

### 1. Extend the current qualification owner instead of adding a parallel runtime

Add `worldguard/qualification.py` as the sole orchestration owner. It will accept a current `GuardContract` plus an explicit evaluation context containing node identity, provider availability/results, semantic inputs, and rollout/depth inputs. It will:

1. normalize the contract once;
2. derive the complete required Guard set from structured claim semantics;
3. preserve declared, omitted, unexpected, and unmapped semantics;
4. freeze and validate Guard-purpose ownership;
5. execute every required structural Guard once;
6. execute every required semantic owner once when its inputs are current;
7. retain unavailable or stale provider obligations as explicit non-pass states;
8. aggregate rollout/depth evidence when required; and
9. issue one content-addressed qualification result.

`worldguard/kernel.py` becomes a thin public entry into this owner. `worldguard/mesh.py` creates or receives the same evaluation context per node, consumes the resulting report read-only, and removes its second semantic loop. Existing native Guard runners and semantic executors remain the semantic owners; qualification coordinates them but does not reinterpret their findings.

Retain `GuardedReport` as the single public report surface and extend it with typed qualification axes rather than introducing both an old aggregate and a new public aggregate. This is an in-place current contract extension, not a fallback reader. The result includes contract and target fingerprints, declared/derived Guard inventories, unmapped atoms, structural results, semantic receipts, provider states, rollout/depth state, gaps, final status, and claim boundary.

**Alternative considered:** keep unit evaluation structural and let mesh add semantic closure. Rejected because the same contract can receive different qualifications and semantic owners can execute twice.

**Alternative considered:** add `QualificationReport` while preserving `GuardedReport` as a compatibility output. Rejected because it creates two current report authorities.

### 2. Use a strict tree for abstraction and a separate graph for domain dependencies

Create `worldguard/blueprint.py` with one cohesive v1 schema:

- `WorldBlueprintContract`: target identity/revision/boundary, root, complete node and element inventories, declared external inputs/outputs, one behavior-commitment replay reference with exact typed inputs and a cache locator, and canonical fingerprint inputs.
- `WorldBlueprintNode`: stable id, abstraction depth, optional single parent, ordered child ids, owned element ids, typed input/output ports, child-input source mappings, owned-element input mappings, child-output dispositions, and output derivations.
- `WorldElement`: stable id, one owner node, one registered domain kind, dependencies, inputs, outputs, and normalized target-native payload.
- role-specific lightweight references for target material, evidence, tests/checks, and native Guard results.
- `WorldBlueprintReport`: axis results, layer results, deepest continuously proven layer, first unresolved layer/gap, claim boundary, and fingerprints.

The hierarchy is a strict rooted tree: one parent per non-root node, no cycles, no orphan. Cross-cutting causal, temporal, normative, resource, or other domain dependencies live in a separate typed graph and may cross branches. This keeps “which coarse model owns this child?” deterministic while still representing real feedback and cross-branch relations.

Every node and element input has exactly one typed source owner: a declared external input, compatible parent input, compatible sibling output, parent-owned element output, owner-node input, or explicitly declared dependency output as allowed by its mapping kind. Port compatibility uses schema id/version and explicit refinement plus cardinality; `value_type` is not proof. Every child output maps to one compatible parent input, one exposed parent output, or one explicit internal terminal. Every element output is consumed by an element input, participates in its owner-node derivation, or has one reasoned internal terminal. Parent outputs declare their exact sources. Unknown, missing, duplicate, or mixed dispositions are validation errors, never fallback.

**Alternative considered:** permit multiple hierarchy parents. Rejected for v1 because it makes abstraction ownership, depth, child evidence roll-up, and change reattachment ambiguous. Cross-cutting dependency edges cover the legitimate multi-node relationship.

**Alternative considered:** extend `ModelMesh` until it carries every blueprint concern. Rejected because execution topology and a durable domain blueprint have different public contracts; the blueprint may describe a non-executable world while mesh remains an evaluation graph.

### 3. Bind by stable identity and fingerprint, not by embedding payloads

WorldGuard owns domain-role references:

- target material identifies the observation, document, dataset, workflow surface, configuration, or other target-native source;
- evidence identifies a factual or declared support object;
- test/check identifies an executable or reviewable validation object;
- native result identifies the applicable Guard or semantic receipt.

Each reference carries a stable id, role, owner, locator, provider/version/capability, target revision and freshness identity, content and observation-receipt fingerprints, observation mode, and bounded claim relation. A `local_content` reference is resolved safely beneath the blueprint root and hashed from observed bytes. A `provider_content` reference is accepted only when a current registry owns that provider/version/capability and the registered execution owner attests exact request/input/result/terminal fingerprints. `external_identity` retains identity only and stays `content_not_verified`. Missing, unregistered, partial, foreign, stale, unsafe, or caller-self-signed observations remain gaps.

Every element also carries a kind-specific `NativeSemanticRef`. Qualification loads the exact local payload, maps applicable kinds to the current Event/Agent/Space/Resource/Causal/Conflict/Norm owner, and calls that owner's current structural runner and pure semantic executor. The receipt binds owner/executor, request/input/result identities and terminal status; blueprint code cannot issue native PASS. Generic container kinds are explicit `NOT_APPLICABLE`.

Native adapters preserve the target's stable semantic identities instead of replacing them with adapter-local aliases or synthesized facts. A complete field-disposition partition records whether each field is an owner input, an owner input whose broader truth remains unverified, a request control, an unverified boundary, a conditional owner input, or not applicable. Event time and initiate/terminate/release axioms are passed directly. Event rollout emits event ids only through `executed_event_ids` and fluent identities only through fluent-specific declared/initiated/terminated/released/reached/active/final fields; declared state ids, declared transition ids, transition-referenced state ids, and true reached/executed state-machine ids remain independent. Because this static slice does not execute declared transition specifications, declaration-only state/transition reachability and execution outputs stay empty. Negative resource quantity and non-binary RCC8 relations are rejected before adaptation; BDI, game, norm-fact, and causal inputs come only from the target record. In particular, a causal link is checked with its declared cause and effect ids, so an exact self-edge remains visible to `CausalGuard`, and the blueprint path does not fabricate structural equations. A caller selects `mechanism_claim_scope: graph_only` for a bounded licensed result or `mechanism_truth` for the broader claim; the latter remains `GAP`, carries only `qualified_subscope: graph_only` when the graph passed, and has no licensed scope for mechanism truth. The owner contracts also reject four exact contradictions at both structural and semantic boundaries: an Event cannot both terminate and initiate the same fluent, an RCC8 relation on one object must be `EQ`, a Conflict cannot repeat a participant identity, and a Norm must use a supported modality.

Predictive semantic coverage applies the same identity separation through a closed eight-axis disposition table. State, transition, event, fluent, branch, perturbation, intervention, and counterfactual each have exactly one `required` or `not_applicable` row. Required rows bind a non-empty expected-id set to an axis-compatible native observation field and a claim boundary. Not-applicable rows carry a reason and boundary but no expected ids or observation field, and they close only when the native domain is also empty. Event binds only `executed_event_ids`; fluent binds one of `reached_fluent_ids`, `active_fluent_ids`, or normalized `final_fluent_ids_by_scenario`. Thus the static Event exercise records reasoned state/transition non-applicability without inventing execution evidence, while empty arrays, crossed event/fluent mappings, and observed ids on an inapplicable axis all fail closed.

A separate closed registry owns behavior-commitment adapter identity, capability, execution owner/executor, and accepted input kinds. The current adapter safely observes exact local request-contract, target-material, and target-semantic-authority locators, checks target/revision/content fingerprints, derives required outputs/contributor branches and the complete target-specific semantic denominator, and issues one replay result plus terminal owner receipt. The target-semantic result carries exact node/element ids, kinds/owners, applicable Guards, registered executors, native providers, binding/source responsibilities, claim boundary, target locator/value provenance, and `Input x PreState -> Output x PostState`/effect/protected-failure rows. Required target-material leaves must be exhausted by those provenance assertions. Blueprint declarations then exact-match the adapter result bidirectionally and native bindings must agree with the actual registered Guard receipt owner/executor. The inventory file is only an exact cache of a compact replay projection; it carries no self-hash authority. Coupled blueprint/cache/receipt edits therefore cannot shrink, relabel, or semantically rebind the replayed denominator. The adapter remains target-neutral: the frozen planning target independently requires all seven Guards, while a different authority may require another exact applicable set. `external_identity` remains non-replayable. OpenSpec, Spark, and changelog are recognized source kinds only; each needs its own current registered extractor before it can establish commitment authority, with no fallback to the request-contract adapter. Declared outputs must close the replayed commitments bidirectionally, required roles derive from that lineage, and caller fields remain assertions.

Generic code, workflow-surface, implementation-resource, project-test, and oracle inventories remain FlowGuard-owned. WorldGuard may reference their current ids through projection but does not derive a competing denominator.

**Alternative considered:** embed complete source, evidence, and test contents in every blueprint. Rejected because it duplicates authority, makes fingerprints unstable, and creates avoidable prompt cost.

### 4. Derive understanding depth from continuous layer closure

Blueprint qualification evaluates, in order, identity/inventory, hierarchy, interfaces, domain semantics, role bindings, native checks, and optional cross-artifact projection. A layer may be `proven`, `gap`, `boundary`, or `not_run`. `deepest_proven_layer` is the deepest continuous prefix with current evidence; `first_unresolved_layer` identifies the next blocking layer and its exact gaps.

A parent summary can remain useful when a child is incomplete, but it cannot claim the child's depth. `native_domain_qualified` applies only when the native inventory through native checks closes for the exact target revision and boundary. `full_domain_qualified` additionally requires the separately owned cross-artifact projection to be proven; the native checker leaves that layer `not_run` and cannot self-promote it. Empirical implementation parity remains a separate, explicitly requested experiment.

**Alternative considered:** ask the AI to label its own understanding as shallow, medium, or deep. Rejected because the label is not evidence and cannot reveal the first missing interface or binding.

### 5. Qualify once, then implement impact and reverse trace as deterministic read-only graph queries

After the supplied blueprint fingerprint matches, one shared query preflight runs the current native blueprint qualification before any query index is built. A non-PASS or non-native-qualified source is rejected as `WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED` with the qualification-report fingerprint and exact source gap ids; content identity alone never licenses a derived closure. The blueprint compiler then builds sorted identity, commitment, owner, parent, input-source, output-disposition, derivation, dependency, declared-gap/output, and binding indexes only from a qualified source. Every stable public id, including commitment inventory/behavior/commitment ids, is an admissible impact seed. A changed dependency or declared-output relation reaches both endpoints before following the affected closure. `impact(changed_ids)` rejects mixed known/unknown requests atomically and returns only declared effects. `reverse_trace(target_id)` walks producer, input-source, dependency, native-owner execution, and support edges to explicit terminals; any query-specific non-terminal dead end is a typed gap.

Queries use deterministic ordering and a visited set. A repeated dependency edge is reported as a cycle witness; it is not followed indefinitely. A required trace that cannot reach a declared terminal ends at a typed gap. Each successful result binds the blueprint fingerprint, request ids, traversed edge ids, materialized member ids, gaps, and result fingerprint. The preflight report is reused within that query instead of running a second qualification path. Qualification and traversal never mutate the blueprint, execute external providers, or repair gaps.

**Alternative considered:** load and narratively inspect the entire blueprint for every change. Rejected because it produces imprecise affected scope and unnecessary token use.

### 5A. Put the native purpose gate and behavior cases inside each applicable target element

An applicable native element does not call `GUARD_RUNNERS` or `EXECUTOR_REGISTRY` from a bare parent contract. Its model carries one task-local purpose declaration plus one known-good and one known-bad/counterexample per selected protected failure. Each `BehaviorCaseContract` records `Input x PreState -> Output x PostState`, effects, failure class, oracle, and boundary. WorldGuard validates those case records, builds the parent contract with the declaration, calls `for_guard`, verifies the frozen child purpose binding, and only then executes the current owners on the target element. The purpose proof and target execution are separate receipts: passing the family calibration does not make the target behavior pass, and a target result cannot author its own oracle.

Transition-bearing cases require observed state/effect comparison when the native owner supports it. Unsupported state/effect semantics remain explicit `not_run`, gap, or boundary. Non-transition cases declare a reasoned not-applicable disposition rather than using empty state fields as evidence.

**Alternative considered:** rely on the seven-family oracle matrix outside each blueprint. Rejected because it proves reusable Guard machinery but does not freeze what one target element is intended to prevent.

### 5B. Consume optional cross-artifact evidence and export a replayable handoff bundle

`cross_artifact_projection` becomes an optional typed input whose independent owner, source/report fingerprints, complete projected/unresolved id sets, normalized payload, and receipt are validated. Absence remains `not_run`; it is not a defect in ordinary native use. A supplied current proven result can close the final projection layer only after native qualification closes.

The native capability also provides one deterministic portable bundle. The bundle carries the normalized blueprint, purpose/case contracts, exact replay resources, optional cross-artifact projection input, and a compact verification manifest. The manifest freezes fingerprints, counts, qualification status, first gap, and claim boundary for the reproducible qualification report, impact/reverse indexes, and handoff projection; it does not duplicate those complete derived payloads beside the blueprint. Isolated verification materializes resources under a temporary root, reruns qualification through the same purpose-gated path, recomputes every derived projection, and compares its fingerprint and denominator with the manifest. The physical destination never enters the logical fingerprint.

The public bundle entry is layered and all three bundle operations are first-class members of the same eight-operation blueprint route. `bundle-export` requires a native-qualified blueprint plus explicit destination and proves deterministic portable materialization only. `bundle-verify` requires the bundle plus an isolated materialization root and returns only a compact integrity/native-replay identity/status/count summary. `bundle-query` requires that verified bundle context plus one exact query kind/member id and returns only that slice after the same full source qualification. There is no default all-details response and no second interpretation path: complete detail remains recoverable from the one normalized blueprint plus deterministic queries. None of these operations independently proves target factual truth, cross-artifact projection, runtime equivalence, installation, or release. For the frozen three-level qualification fixture, the bundle and default verification output have explicit byte budgets; larger real targets report their sizes and remain queryable rather than silently truncating semantics. This is an explicit handoff qualification, not a routine reconstruction step.

### 5C. Close every meaningful target element without pretending every role is applicable

The external-object DNA denominator is every independently required target semantic element, not only the leaves that happen to contribute to one declared root output. Candidate blueprints and target-semantic payloads can establish deterministic internal consistency, but they cannot license their own completeness. One portable external-object census therefore freezes and signs the exact nodes, per-element kind/owner/Guard/support-mode/four-role applicability/derivation identities, Guard set, target boundary, and request/material/semantic input fingerprints. Production contains only public verification and accepts no built-in producer as trusted. The caller must supply the exact trusted authority or producer-descriptor fingerprint; otherwise the result remains a useful candidate model but not qualified object DNA.

For each census-required element and each of the four support roles—target material, evidence, test/check, and native result—the signed census fixes whether the role is applicable. The exact target-semantic payload carries the matching binding identity or `not_applicable` reason and is itself bound by the signed census fingerprint. A candidate cannot author or shrink this matrix. Qualification requires the census, semantic payload, and candidate binding set to match bidirectionally, and it rejects a role that is both bound and marked not applicable.

Parent, summary, aggregate, and state elements are not automatically exempt. When their meaning is derived rather than independently observed, the authority binds the target element id, its owning node, one output port, and the exact child/owned-element sources. Qualification requires the derivation owner to equal the element owner and forbids one derivation identity from supporting multiple elements. This makes semantic lineage checkable without inventing fake evidence or duplicate tests. The seven-Guard native-owner matrix remains an oracle-carrying capability fixture: it proves reusable Guard execution and bundle transport, but detached zero-interface cases are not presented as an integrated seven-Guard object and cannot satisfy the planning target's DNA denominator.

To prove target neutrality, a second fixture uses a materially different policy-enforcement target and raw target material. It runs the same authoring/cache compiler, parser, qualification, impact, reverse trace, bundle export, isolated verification, and by-id query owners. It demonstrates that the schema and route can model a second domain; it does not claim that WorldGuard or an AI discovered factual truth automatically.

The portable bundle excludes the deterministic commitment-cache body. It carries the three authoritative adapter inputs, the normalized blueprint's cache reference identity, and one expected regenerated-cache fingerprint; isolated verification recompiles the cache from those inputs before ordinary qualification. The manifest similarly replaces catalog member arrays with one catalog fingerprint while retaining exact counts; query membership is rebuilt from the qualified blueprint. Authoritative replay resources use one frozen transport codec, `worldguard.replay-resource.zlib-rfc1950-base64.v1`: RFC1950, level 9, window bits 15, RFC4648 base64, and a 16 MiB decoded-resource ceiling. Compressed bytes are transport-only; the authoritative semantic identity is the decoded byte length plus decoded-byte SHA-256, so no encoder-version-dependent compressed byte claim is made. Codec mismatch, truncated/tampered streams, decoded-size mismatch, and decompression overflow fail closed. There is one current format and one replay path—no uncompressed or legacy cache reader, dual manifest, fallback, or retry interpretation.

The frozen canonical UTF-8 size ledger records the same 20-element seven-Guard semantic target at 331,273 bytes with the former duplicate cache/catalog bodies, 276,898 bytes after removing those derived bodies but before resource compression, and 143,228 bytes in the current codec form. The current form therefore has 118,916 bytes of headroom below the 262,144-byte ceiling. The current 13-element planning target is 82,084 bytes with 180,060 bytes of headroom, and the independent 3-element policy target is 30,105 bytes with 232,039 bytes of headroom. These measurements preserve all modeled elements and bindings; they do not license semantic truncation as a size strategy.

### 6. Delay the FlowGuard adapter until the native model and toolchain are stable

Implement native qualification, hierarchy, bindings, impact, trace, and the three-level fixture first. After those contracts and tests are stable:

1. wait for the separately owned FlowGuard work to publish one supported released package/schema contract;
2. run the current project audit and require that package, schema, managed rules, project record, and sole observed model-system identity agree;
3. freeze only the released provider capabilities and projection fixture, without copying provisional field names into WorldGuard; and
4. add `worldguard/flowguard_projection.py` as a lazy, explicit integration boundary.

The adapter emits a content-addressed FlowGuard provider result with capability ids for world elements, topology, semantics, and domain bindings. It preserves WorldGuard ids and fingerprints and maps them to FlowGuard's generic topology/binding objects. It does not discover or execute a provider. If FlowGuard is absent, stale, unsupported, or project identity is mismatched, the explicit projection returns a visible boundary. Ordinary WorldGuard imports and native routes never import or initialize FlowGuard.

Do not add a mandatory FlowGuard dependency to the core package in this change. The supported maintenance environment provides the exact installed toolchain; distribution packaging for the optional integration can be revisited only if a real consumer requirement demands it.

**Alternative considered:** copy FlowGuard blueprint classes into WorldGuard. Rejected because it creates schema drift and two generic blueprint authorities.

**Alternative considered:** make FlowGuard mandatory at package import time. Rejected because WorldGuard must remain useful for target-native and non-software world checks.

### 7. Use one three-level non-code fixture as the vertical proof slice

Add a planning-workflow fixture under `tests/fixtures/world_blueprint/`. It has:

Keep `seven_guard_native_owner_matrix.json` and its portable handoff as a distinct validation fixture. Its matrix cases calibrate all seven Guard owners and must never be counted as observed planning-workflow material, evidence, tests, or semantic elements. Add a separate policy-enforcement target fixture whose raw material and authority are independently named, and use it to exercise the complete public authoring and portable-handoff route.

- root: the plan's externally visible objective, inputs, constraints, and outcome;
- middle: task allocation, scheduling/state coordination, and resource/norm handling;
- leaves: concrete task transitions with actor/role, preconditions, inputs, outputs, evidence, and checks.

The fixture contains no module, class, function, or programming-language assumptions. Focused tests derive known-bad variants for duplicate owner, hierarchy cycle, missing or incompatible input source, duplicate input owner, missing output disposition, unknown relation, missing test binding, stale fingerprint, rejected unqualified query sources, a complete stable-id impact-seed matrix, and an affected leaf whose unrelated sibling must remain excluded. A separate compact native-owner matrix proves all seven Guard owners execute without making the primary hierarchy fixture wider. That matrix stores the raw observed semantic object and literal positive and negative oracles for every owner; the test independently hashes the raw observation and compares the production adapter and execution outputs against the frozen oracle instead of asking production receipt code to regenerate its own expected value. The same complete three-level fixture becomes the projection contract test after the FlowGuard gate closes.

**Alternative considered:** use the existing fuel-cell software fixture as the only proof. Rejected because it would not demonstrate that the blueprint is target-neutral or suitable for ordinary workflows.

### 8. Keep skill routing compact and enforce prompt ceilings

Add one conditional `world_blueprint` task shape with prompt operations `create`, `update`, `check`, `impact`, and `trace`; do not add operation-specific installed skills or query aliases. Create/update author the model then require its native check; the runtime CLI remains the exact check/impact/trace executor. `SKILL.md` remains the thin entry. A new `references/world-blueprint.md` owns the domain blueprint contract, while existing entry-routing, contracts, mesh, authority, and closure references are updated only where their current responsibility changes.

Enforce these deterministic UTF-8 byte ceilings:

- always-loaded `skills/worldguard/SKILL.md`: 12,000 bytes;
- any individual newly selected blueprint reference: 16,000 bytes, with at least 1,000 bytes of maintained headroom (therefore no more than 15,000 bytes at validation time);
- one complete selected blueprint operation bundle, including entry, blueprint reference, operation guidance, and affected Guard references: 70,000 bytes.

Validation reports all included components, reference size, and remaining reference headroom. Exceeding a ceiling or dropping below the 1,000-byte maintenance headroom fails the prompt check; required semantics are structurally compressed or conditionally loaded, never silently truncated. These byte ceilings are stable testable proxies for model-token cost. Human-facing reports may additionally show an estimated token count, but tokenizer variance cannot weaken the byte gate.

### 9. Build one repository self-DNA root, not a second product blueprint

The WorldGuard self-blueprint has one repository root representing the complete maintained software boundary. Seven required child subtrees preserve the EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard semantic owners. Shared qualification, mesh, task-local revision, templates, CLI/API, skill/prompt routing, native `WorldBlueprint`, validation, portable projection, installation, and release behavior remain explicit sibling or supporting subtrees under the same root. `WorldBlueprint` is therefore a product-feature subtree that can model arbitrary external targets; it never supplies the repository denominator or becomes a fallback self-DNA root.

Each leaf FunctionBlock is modeled as `Input × State -> Set(Output × State)`, including success, fail, gap, boundary, not-run, stale, and invalid-input terminals. Parent models consume the declared child inputs and outputs and may summarize them, but cannot invent a child terminal, hide an unresolved child, or become a second structural or semantic owner. The seven Guard subtrees retain distinct structural and semantic axes even where they share a pure predicate or status projection.

The existing current-input and behavior commitments are extended or attached beneath this root according to their current ownership. No second current-input commitment, parallel self-blueprint root, product-blueprint-derived repository inventory, or whole-repository fallback owner is added.

### 10. Derive a complete repository denominator and bind every surface once

An independent repository inventory defines the self-DNA denominator before model matching. It covers source modules, public APIs and CLIs, adapters and facades, skill prompts and references, configuration and schemas, documentation that carries behavior or intent, data and fixtures, tests and oracles, scripts and workflows, packaging, projection, installation, and release surfaces. Python source is one surface class, not the denominator; non-Python workflows, prompts, documents, configuration, data, assets, and externally observable target behavior are first-class inventory inputs.

Every inventory item receives exactly one terminal disposition and one primary owner. A row may be modeled and bound, a one-way generated projection, an explicit external-authority reference, a reasoned exclusion, or unresolved; it cannot disappear, inherit ownership from filename similarity, or be accepted by a fallback owner. Every modeled item binds the relevant intent or commitment, parent/child topology, implementation or behavior surface, tests/checks, resources/evidence/oracles, side effects, and public entrypoint. Missing, duplicate, ambiguous, stale, or unbound rows block whole-repository completeness while leaving bounded affected work available.

Source under `worldguard/` remains the sole author runtime. The bundled runtime remains a one-way generated projection and receives a derived-projection disposition rather than a second semantic owner. SkillGuard author records, validation receipts, caches, and generated release material retain separate process or evidence dispositions and never refresh source authority.

### 11. Qualify seven static-readiness layers and keep materialization and lifecycle evidence separate

Static self-DNA readiness is the following continuous provider-neutral seven-layer proof:

1. **evidence qualification:** freeze and qualify the provider registry, target snapshot, evidence identities, freshness, boundaries, and admissible evidence roles without claiming that tests have executed or external resources are currently available;
2. **implementation inventory:** independently enumerate the complete code and non-code denominator and give every item one terminal disposition;
3. **traceability:** bind every item bidirectionally to one primary owner, intent/commitment, public caller, topology position, affected edge, and reverse edge;
4. **independent semantics:** specify every behavior-bearing FunctionBlock as `Input × State -> Set(Output × State)` with ports, dependencies, effects, errors, order, retry, timeout, decisions, completion, and parent/child interface meaning independent of source text;
5. **model-code-test binding:** bind each model obligation and semantic rule to its exact implementation or target-behavior surface, CodeContract or equivalent boundary, test/check design, cases, assertions, and test-inventory identity without treating execution receipts as static design;
6. **resource-oracle binding:** bind required build/runtime/config/schema/data/asset/service resources and behavioral oracles, while keeping actual resource availability and oracle/test execution as independent evidence; and
7. **static blueprint readiness:** close layers 1-6 for one exact current revision, normalized canonical projection, deterministic affected/reverse indexes, and explicit first gap.

Each layer is `proven`, `gap`, `boundary`, or `not_run`; the deepest proven layer is the continuous prefix and the first unresolved item remains explicit. A static model, a passing child, file presence, self-reported confidence, test execution receipt, available external service, installed copy, Git commit/tag, GitHub Release, or release asset cannot promote a later static layer. Those runtime and lifecycle facts keep their own evidence identities and may block their own claims even when layer seven is proven.

One deterministic affected index and one reverse index are built from a frozen inventory/model snapshot and contribute to traceability and final static readiness. Ordinary maintenance starts from the changed intent, behavior, code, prompt, test, resource, or topology id and materializes only the affected neighborhood plus required ancestors and evidence. Whole-static-blueprint qualification requires an explicit initialization, completeness, model-authority replacement, architecture-reduction, toolchain/schema-upgrade, export-prerequisite, or release-prerequisite task fact. It refreshes the static denominator and affected layer evidence only; it does not rebuild WorldGuard, execute tests, prove external resources available, install software, or perform release work.

The canonical self-DNA export is an independent materialization result of that same static blueprint. It is written only to an explicit location outside the governed repository and outside every inventoried source/projection root. Its logical fingerprint is computed from the normalized static blueprint before physical export, so the export file, its digest, and later release packaging cannot enter their own denominator or fingerprint. An isolated import must reproduce the root, seven Guard subtrees, shared product/process subtrees, complete dispositions, seven static layer rows, and affected/reverse indexes without consulting the original checkout. Export success proves materialization equivalence only: it does not change `deepest_proven_layer`, and it does not prove test execution, external-resource availability, installation, Git/tag/GitHub Release, or release-asset publication.

### 12. Let self-DNA evidence gate architecture reduction

Architecture reduction consumes the exact current self-blueprint, independent repository inventory, observable contracts, affected/reverse indexes, and model-code-test evidence. Every candidate names its stable intent, public entrypoints, outputs, state, side effects, primary owner, proof status, target action, and required tests. Only current observable equivalence or proven public-facade delegation can make a candidate ready; everything else remains an unresolved maintenance obligation.

The current static audit provides this starting classification:

- **A1 — semantic-to-Guard status projection:** the identical mappings in qualification and mesh plus the equivalent blueprint terminal lattice are the only currently proof-ready contraction. It is still implemented only after the self-DNA denominator and bindings are current, then becomes one pure status-projection owner without changing priority or terminals.
- **A2 — public `run_worldguard` versus directly exported qualification entry; A3 — blueprint owner dispatch versus ordinary qualification; A4 — repeated prompt-budget calculation; A5 — CLI exit semantics; A6 — portable runtime loaders; A7/A8 — the two historical SkillGuard verification entry scripts:** each remains blocked until self-DNA and caller evidence identify the public contract, primary path, external callers, and exact affected tests. A blocked candidate is not silently retained as an alternate success path and is not deleted by assumption.

The mesh aggregator, thin kernel public facade, structural/semantic dual evidence axes, source/bundle projection boundary, and distinct topology, blueprint-integrity, portable-projection, native-depth, SkillGuard, installation, and release evidence subjects are deliberate separations, not contraction candidates. Relation parsing has one current owner per schema boundary; ModelMesh and `WorldBlueprint` vocabularies are not merged merely because both contain relation labels. Negative rejection tests remain evidence, not legacy runtime readers.

After native source and self-model tests are stable, update the WorldGuard SkillGuard contract source, then compile generated authorities only after every parallel source identity freezes. Keep evidence subjects independent and assign exactly one execution owner to each. The FlowGuard contract export proves only its declared maintenance process and never stands in for World domain, runtime, projection, installation, or release evidence. SkillGuard supervises target-owned checks and clean consumer projection; it does not own world semantics.

The documented `run_worldguard_check.py` surface remains a facade unless current caller evidence supports direct retirement. It delegates to the sole package CLI and owns no independent Guard, mesh, result, or exit decision. Any generic portable launcher shares the same bundled-origin verification owner; a foreign preloaded package blocks rather than triggering unload, retry, or fallback.

### 13. Delegate installation currentness to the one installed SkillGuard consumer authority

`scripts/verify_guard_simulation_readiness.py` must not parse `consumer-release.json`, recalculate its manifest or release hashes, or independently classify consumer files. Those rules already belong to SkillGuard. The WorldGuard readiness audit dynamically loads the exact current installed `skillguard_v2/consumer_distribution.py` beneath one absolute active Codex installation, validates that the Codex root, scripts directory, package, entry module, and every relative dependency resolve to the declared non-link path, suppresses bytecode writes while loading, and accepts only callable `consumer_distribution_plan` and `audit_consumer_distribution` interfaces. An empty `CODEX_HOME` selects the normal user installation; a relative, linked, escaped, missing, malformed, or incompatible authority is a visible installation-currentness blocker. Package, source-authority, consumer-API, malformed-result, and serialization failures all produce one canonical blocked JSON terminal; there is no traceback-only machine result, repository checkout, alias, older module, or local algorithm fallback.

The read-only audit first requires one version identity across `pyproject.toml`, `VERSION`, the canonical source package, the imported distribution, and the bundled portable runtime. It compares source with the actually imported distribution directly, but calls the exact repository `audit_projection()` owner once for source-to-bundled-runtime inventory and byte parity. A missing, foreign, malformed, or self-inconsistent canonical result blocks before further package comparison; there is no second bundled scan, hash recomputation, or fallback. It then loads WorldGuard's current compiled author contract, requires maintenance unit `unit:worldguard` and exactly one external member `worldguard`, asks SkillGuard to derive the current source consumer plan, asks SkillGuard to audit the installed tree, and compares the returned skill id, release id, and complete file path/hash inventory. It never calls build, prepare, activate, smoke, native checks, or validation owners. Owning-checker finding codes for projection drift, symlinks, unexpected files, author-control paths, malformed manifests, and byte drift remain visible in the WorldGuard result.

The author contract source declares the whole `skills/worldguard/.skillguard` subtree as `source_only`. Therefore an author-only contract, test-plan, receipt, or model edit does not stale `projection:installation`, while a new or changed consumer file does. The source contract now declares ten distinct execution owners and the source-level contract tests are current. The compiled contract and check manifest remain deliberately pending and are not hand-edited; they must be rebuilt once from this source declaration after all parallel source work freezes. That later recompile, affected SkillGuard execution, local installation, patch-version update, full validation, and release remain separate pending gates.

Release assets have their own frozen manifest and do not become installation authority by proximity. The package or source artifact, clean consumer skill distribution, canonical external self-DNA export, checksums, and release notes each have one declared role, version, content digest, and public/private disposition. The public self-DNA asset contains only portable logical identities and bounded references; author-only SkillGuard state, private receipts, mutable caches, local absolute paths, and transient validation payloads are excluded. Installation currentness continues to compare the consumer projection only, while release verification independently checks that every declared public asset belongs to the same frozen release candidate.

## Source and Test Boundaries

Planned source additions:

- `worldguard/qualification.py`
- `worldguard/blueprint.py`
- `worldguard/flowguard_projection.py` after the toolchain gate

Planned source updates:

- `worldguard/kernel.py`
- `worldguard/mesh.py`
- `worldguard/reports.py`
- `worldguard/cli.py`
- `worldguard/__init__.py`
- only those contract/semantic helpers required to expose the canonical current input

Focused test additions and updates:

- `tests/test_qualification.py`
- `tests/test_world_blueprint.py`
- `tests/test_blueprint_impact_trace.py`
- `tests/test_flowguard_blueprint_projection.py` after the projection gate
- `tests/fixtures/world_blueprint/planning_workflow_three_level.yaml`
- existing unit/mesh parity cases in `tests/test_kernel_handoff.py`, `tests/test_claim_derived_coverage.py`, `tests/test_semantic_rollout.py`, and `tests/test_cli_module.py`
- evidence-qualification, implementation-inventory, traceability, independent-semantics, model-code-test, resource-oracle, static-blueprint-readiness, affected/reverse-index, isolated external-materialization import, public-entry parity, and architecture-reduction equivalence cases selected from the released FlowGuard contract after its toolchain gate closes

Prompt and maintenance updates occur only after source behavior is green:

- `skills/worldguard/SKILL.md`
- `skills/worldguard/references/world-blueprint.md`
- affected current references and route manifest
- `skills/worldguard/agents/openai.yaml`
- `skills/worldguard/.skillguard/contract-source.json`
- `.flowguard/current_input_authority/**`
- `.flowguard/world_blueprint/**`
- `.flowguard/behavior_commitment_ledger/**`
- `.flowguard/model-regression-manifest.json`

The independent repository inventory and self-blueprint records use only the paths and schemas supplied by the frozen released FlowGuard toolchain. This plan does not invent a parallel local schema. The canonical self-DNA export has no repository source path: tests write it to an isolated external destination and release packaging later consumes that frozen output as a separately identified asset.

## Risks / Trade-offs

- **[Qualification convergence changes report shape]** → Extend one current `GuardedReport`, update all callers and fixtures in the same change, and do not retain a legacy result adapter.
- **[Moving semantic execution can lose mesh depth receipts]** → Freeze unit/one-node-mesh parity and native depth receipt identities before deleting the second loop; require exact receipt preservation tests.
- **[Strict relation rejection exposes formerly accepted inputs]** → Treat every unknown relation as a visible migration defect, update maintained fixtures directly, and do not add a compatibility parser.
- **[A strict hierarchy cannot represent every cross-cutting world relation as parentage]** → Keep hierarchy ownership single-parent and represent cross-cutting semantics in the separate typed dependency graph.
- **[Optional FlowGuard integration can drift]** → Gate route availability on exact current project/toolchain/schema identities and content-addressed projection tests; fail visibly on drift.
- **[The vertical fixture could be mistaken for universal completeness]** → Bind every qualification statement to the fixture target revision and declared boundary and keep broader semantic deepening as future work.
- **[Reference growth increases model-token cost]** → Keep one conditional blueprint reference, affected-only Guard loading, deterministic byte budgets, and compact identity projections instead of embedding payloads.
- **[Source and bundled runtime can diverge]** → Keep one executable source-to-bundle projection owner with complete raw-byte inventory, explicit read-only check and transactional sync; freeze source first and verify source, bundle, and install identities separately.
- **[A skill helper can become a second dispatcher]** → Preserve only its public argument surface, require bundled-runtime origin proof, and translate into the sole package CLI with conformance coverage for JSON, stderr, and exit status.
- **[WorldGuard can drift from SkillGuard's consumer rules]** → Keep no local manifest/hash classifier, load only the path-validated installed current API, and compare its complete source plan with its installed-tree audit.
- **[Author-only maintenance edits can cause needless reinstall work]** → Classify the complete `.skillguard/**` subtree as `source_only`; only `projection:installation` members participate in currentness.
- **[OpenSpec main specs currently contain conflicting structural-only and template fallback language]** → This change adds final qualification semantics and fully modifies the two conflicting template requirements; archive only after strict validation and implementation verification.
- **[A partial self-model can falsely certify its own completeness]** → Derive the repository denominator independently of existing FlowGuard model membership, require one terminal disposition and one primary owner for every inventoried item, and keep every missing or duplicate owner as a visible readiness gap.
- **[An external-object candidate can shrink its authority and all hashes together]** → Require a signed object census produced outside runtime, bind exact target inputs and every semantic/role/derivation denominator member, separate signature integrity from caller trust, and expose candidate consistency separately from object-DNA qualification.
- **[Exporting the canonical self-DNA inside the repository creates a self-fingerprint loop]** → Compute the logical static-blueprint snapshot first, write the canonical materialization only to an isolated external destination, validate isolated equivalence separately, and never use export success to deepen static readiness.
- **[Architecture cleanup can collapse intentionally separate semantics]** → Contract only proof-ready candidates after the self-DNA is current; retain mesh aggregation, the kernel facade, structural and semantic axes, source and bundle identities, per-schema parsers, and distinct evidence subjects unless equivalence and caller evidence prove a safe replacement.
- **[A full-DNA audit on every task would waste time and tokens]** → Keep ordinary maintenance affected-only through deterministic forward and reverse indexes, and reserve whole-DNA qualification/export for explicit completeness, architecture-reduction, and release gates.
- **[Lifecycle success can be mistaken for deeper software understanding]** → Keep test execution, external-resource availability, installation, Git/tag/GitHub Release, and release-asset verification as independent evidence/lifecycle gates that neither contribute to nor replace the seven static layers.
- **[Release proximity can blur asset and installation authority]** → Give the package/source artifact, consumer skill, external self-DNA materialization, checksums, and notes separate manifest roles and verify each independently against one frozen release candidate.

## Migration Plan

1. Validate these planning artifacts strictly; do not archive the two older complete changes until their implementation and supersession boundaries are verified.
2. In an authorized implementation turn, wait for the separately owned FlowGuard work to publish one supported released package/schema, then freeze that exact package, project record, managed rules, provider contracts, and observed model-system identity. Run `project-audit` and stop visibly if any identity disagrees; do not invent local or provisional schema fields.
3. Freeze peer ownership and the exact current WorldGuard source snapshot. Reconfirm which native qualification, mesh, blueprint, impact/trace, CLI, prompt, portable projection, SkillGuard, and release obligations are already complete versus still pending.
4. Close any remaining native product behavior and the explicit FlowGuard projection against the frozen released contract. Keep ordinary WorldGuard use independent of FlowGuard and preserve `WorldBlueprint` as the arbitrary-target product subtree rather than the repository self-DNA root.
5. Derive the complete repository denominator independently of current model membership, including Python and non-Python behavior surfaces. Give every item exactly one terminal disposition and one primary owner, then build one WorldGuard software-DNA root with seven distinct Guard subtrees and separate shared runtime, product, process, validation, projection, installation, and release subtrees.
6. Model every owned FunctionBlock as `Input × State -> Set(Output × State)` and close evidence qualification, implementation inventory, traceability, independent semantics, model-code-test bindings, resource-oracle bindings, and static blueprint readiness. Publish deterministic affected and reverse indexes as static traceability/readiness obligations.
7. Prove affected-only daily maintenance separately from explicit whole-static-blueprint qualification. Compute the frozen logical fingerprint before writing the canonical materialization outside the repository, then validate isolated import equivalence without local paths, private receipts, caches, or transient evidence payloads; do not let this materialization result change static depth.
8. Use that current self-DNA to classify architecture-reduction candidates. Implement the shared semantic-status projection only after self-DNA closure; keep every other audited candidate pending until its observable contract, callers, parity evidence, action, and revalidation owner are proven. Do not merge deliberately distinct parsers, axes, facades, aggregators, source projections, or evidence subjects.
9. Update the behavior commitment ledger, model-regression ownership, prompts, conditional references, prompt-budget checks, source-to-bundle projection, and SkillGuard contract from the frozen self-DNA. Run only affected owners while source identities are still changing.
10. After source, toolchain, model, projection, and execution-owner identities freeze, run the affected model checks and one explicit full repository validation as separate execution evidence. Re-audit static self-DNA readiness, architecture reduction, no-fallback residuals, SkillGuard supervision, and OpenSpec implementation evidence without feeding lifecycle success back into static depth.
11. Build the release-asset manifest with independent package/source, clean consumer skill, external canonical self-DNA, checksum, and release-note roles; exclude author-only SkillGuard state and local/private evidence.
12. Synchronize the local installed skill/runtime, verify source, bundle, installed projection, external self-DNA import, Git/tag, and release assets independently, then publish only the next patch release after all identities agree.

Rollback before release is one direct revert of the unreleased change and its generated projections. No runtime fallback, dual report, old relation reader, or alternate projection remains active. After release, any corrective change follows a new OpenSpec change and patch release rather than reactivating retired behavior.
