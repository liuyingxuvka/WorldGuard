## Purpose

Define a target-neutral, hierarchical world or workflow blueprint whose layers, interfaces, semantic elements, bindings, and evidence-backed understanding depth can serve as the domain DNA for software-independent WorldGuard targets.

## ADDED Requirements

### Requirement: Target blueprint and repository self-DNA remain distinct
`WorldBlueprint` SHALL model an arbitrary declared target such as a world, workflow, experiment, document-supported behavior, or software behavior without assuming Python or even source code. When WorldGuard models itself, this product capability SHALL be one owned product subtree beneath the separate FlowGuard repository self-DNA root. A native `WorldBlueprint` payload MUST NOT claim to be the WorldGuard repository denominator, absorb the seven Guard subtrees, replace the seven provider-neutral static self-DNA layers, or independently certify test execution, external-resource availability, package, installation, Git/tag/GitHub Release, or release-asset completeness.

#### Scenario: WorldGuard models an external laboratory workflow
- **WHEN** the target consists of people, instruments, states, transitions, observations, checks, and outputs rather than source files
- **THEN** `WorldBlueprint` models those target behaviors directly and does not require a Python-specific adapter

#### Scenario: WorldGuard audits its own complete software DNA
- **WHEN** the requested static claim covers the whole WorldGuard repository, its seven Guards, code and non-code surfaces, test designs, projection contracts, and installation/release behavior contracts
- **THEN** the FlowGuard repository self-DNA owns that static denominator and includes `WorldBlueprint` only as one product feature subtree
- **AND** actual test execution, resource availability, installation, Git/tag/GitHub Release, and release assets remain independent gates outside static understanding depth

### Requirement: Target-neutral world element inventory
WorldGuard SHALL represent the complete declared world-domain denominator as stable typed elements. The supported element vocabulary SHALL include entity, property, relation, event, state, transition, resource, causal link, agent, conflict, and norm. Every element SHALL have one stable id, exactly one owning blueprint node, explicit dependencies, declared inputs and outputs, and one kind-specific native semantic object without assuming a programming language, source-code layout, or software runtime. WorldGuard SHALL load the exact observed native payload and delegate applicable checks to the current Event/Agent/Space/Resource/Causal/Conflict/Norm structural and semantic owner. The owner-issued terminal SHALL bind exact request, input, target, revision, executor/version, result, and receipt identities. Blueprint code MUST NOT issue native PASS; an ownerless container SHALL remain explicit `NOT_APPLICABLE` or unverified.

#### Scenario: Non-code workflow is modeled
- **WHEN** a planning workflow declares people, roles, tasks, state transitions, resources, constraints, and expected results
- **THEN** WorldGuard represents them as typed world elements without requiring Python modules, functions, classes, or files

#### Scenario: Element has duplicate or missing ownership
- **WHEN** a declared element is owned by zero nodes or more than one node
- **THEN** blueprint qualification fails with the element id and the conflicting or missing owner ids

#### Scenario: Static native copy is internally consistent but semantically invalid
- **WHEN** the model and observed native-result file contain the same current hashes but an event both terminates and initiates one fluent or another typed native invariant fails
- **THEN** WorldGuard records a failing native execution receipt and does not qualify the blueprint

### Requirement: Native adapters preserve semantic identities and bounded claims
WorldGuard SHALL pass the target's exact stable semantic identities into the applicable Guard owner and SHALL NOT replace them with adapter-local aliases or synthesized target facts. Every current native field SHALL have exactly one machine-readable disposition: owner input, owner input with broader semantics explicitly unverified, request control, unverified boundary, conditional owner input, or not applicable. Native qualification SHALL distinguish declared identities, referenced identities, and genuinely executed/reached identities. Merely preserving a field in `consumed_inputs` MUST NOT prove guard-expression truth, effect execution, terminal reachability, belief/fact truth, issue resolution, or another broader claim. The blueprint causal path SHALL evaluate the declared variable graph without synthesizing equations. A causal mechanism description SHALL remain a visible unverified boundary; `mechanism_claim_scope: graph_only` MAY produce a bounded PASS and `licensed_claim_scope: graph_only` for an otherwise valid acyclic graph, while `mechanism_claim_scope: mechanism_truth` SHALL keep the blueprint terminal at `GAP`, omit `licensed_claim_scope`, and MAY report `qualified_subscope: graph_only`. Event, Space, Conflict, and Norm owners SHALL reject their exact protected contradictions at both structural and semantic boundaries.

#### Scenario: Bounded causal graph passes with actual target ids
- **WHEN** a causal link declares distinct stable cause and effect ids, a valid acyclic graph, and `mechanism_claim_scope: graph_only`
- **THEN** CausalGuard receives those exact ids, the graph check may PASS, the receipt licenses only `graph_only`, and the mechanism description remains an explicit unverified boundary

#### Scenario: Causal self-edge is not hidden by adapter aliases
- **WHEN** one causal link names the same stable id as both cause and effect
- **THEN** CausalGuard receives the exact self-edge and returns `CAUSAL_CYCLE`

#### Scenario: Broader causal mechanism truth is requested
- **WHEN** an otherwise valid causal link declares `mechanism_claim_scope: mechanism_truth`
- **THEN** structural and semantic graph checks may remain PASS, the blueprint terminal is `GAP` with `WORLD_BLUEPRINT_CAUSAL_MECHANISM_UNVERIFIED`, `qualified_subscope` MAY be `graph_only`, and no `licensed_claim_scope` is issued for the requested mechanism-truth claim

#### Scenario: Native owner contradiction is present
- **WHEN** an Event both terminates and initiates one fluent, an RCC8 self-relation is not `EQ`, a Conflict repeats a participant identity, or a Norm uses an unknown modality
- **THEN** the applicable structural and semantic owner returns its exact typed FAIL instead of allowing the blueprint adapter to normalize the contradiction away

#### Scenario: State and transition declarations are not execution evidence
- **WHEN** a state is both declared initial and terminal or a transition has the same source and target state
- **THEN** the declaration is not inherently contradictory; state ids, transition ids, source/target references, guard, and effect remain exact, while terminal reachability and guard/effect truth remain explicit unverified semantics and no declaration-only id appears as executed or reached

#### Scenario: Event rollout preserves five identity domains
- **WHEN** one observed event initiates, terminates, or releases fluents while the same owner input also contains declared state and transition specifications
- **THEN** only the event id appears in `executed_event_ids`; fluent identities appear only in fluent-specific outputs; declared transition ids, referenced state ids, and declared state ids remain separate; and no id appears in `executed_transition_ids`, `executed_state_ids`, or `reached_state_ids` unless actual state-machine execution independently proves it

#### Scenario: Invalid resource quantity or RCC8 arity is supplied
- **WHEN** a resource quantity is negative or non-finite, or an RCC8 relation names any participant count other than exactly two
- **THEN** native semantic admission rejects the whole object atomically and does not normalize the quantity or truncate participant identities

#### Scenario: Agent, Conflict, and Norm facts are absent
- **WHEN** an Agent omits actual BDI fields, a Conflict omits its actual action/transition/payoff model, or a Norm condition lacks the supplied matching fact
- **THEN** the adapter does not invent beliefs, desires, intentions, conflict actions, probabilities, payoffs, or a true condition fact, and the applicable admission or owner result remains non-PASS

### Requirement: Every applicable native element carries task-local purpose and behavior-case contracts
Before an applicable Event/Agent/Space/Resource/Causal/Conflict/Norm element can contribute a native terminal, its blueprint SHALL carry one task-local purpose declaration and a closed behavior-case set for that exact target element and boundary. The case set SHALL contain exactly one native known-good case and exactly one native known-bad or counterexample for every selected protected failure. Every case SHALL bind stable case and failure identities, `Input x PreState`, expected `Output x PostState`, effects, expected terminal/failure class, source-independent oracle id, claim boundary, and exact input fingerprint. The blueprint owner SHALL construct the parent `GuardContract` with that declaration, call the standard `GuardContract.for_guard` path, verify the frozen candidate-purpose contract, and only then call the current structural and semantic owners. It MUST NOT call a Guard runner or semantic executor directly from an undeclared parent contract, copy a family fixture as target evidence, infer an oracle from the production result, or convert a missing/failed purpose proof into GAP/PASS.

The same declaration MAY additionally carry an `admission_bad` case for one exact malformed `world_element`. Such a case SHALL bind the expected parser rejection status/code, required error-detail subset, parser-owned oracle, and claim boundary. The sole current `WorldElement` parser SHALL replay it before Guard construction. Admission cases MUST NOT count toward, replace, or weaken the Guard-native known-bad denominator. A portable behavior-case query SHALL return its exact replay observation and native-execution receipt fingerprint without a matrix-specific parser or bundle format.

#### Scenario: Parser counterexample remains part of target DNA
- **WHEN** a target declares invalid RCC8 participant cardinality or negative resource quantity as an `admission_bad` case
- **THEN** qualification replays the malformed element, matches the rejection code/detail subset, and blocks if the parser accepts it or reports different evidence

#### Scenario: Blueprint omits its task-local purpose declaration
- **WHEN** an applicable native element has typed semantic fields and current bindings but no exact task-local purpose/case contract
- **THEN** native execution is blocked before the Guard runner, the report names the purpose/case gap, and the element cannot contribute PASS

#### Scenario: Task-local counterexample does not trigger its declared oracle
- **WHEN** one selected failure's known-bad case returns a different status or code from its independent oracle
- **THEN** candidate-purpose proof fails, the current target element is not executed, and the mismatch remains visible in the native receipt

#### Scenario: Purpose proof closes and target behavior is evaluated
- **WHEN** one exact declaration has one passing known-good and one passing counterexample per selected failure
- **THEN** `for_guard` freezes the purpose before child construction, the child carries the current purpose binding, and structural/semantic execution evaluates the target element only after that proof

### Requirement: Behavior cases preserve state-transition and oracle meaning
The behavior-case contract SHALL be target-neutral and SHALL NOT assume Python or source files. For transition-bearing behavior, `pre_state`, `post_state`, and effects SHALL be explicit and the current native owner SHALL either execute the declared transition and compare the observed output/state/effect against the oracle or return a typed `not_run`, gap, or boundary identifying the unsupported transition semantics. A structural field match, a consumed input, or an expected-output assertion SHALL NOT prove state movement or effects. Non-transition behavior SHALL carry an explicit reasoned not-applicable state/effect disposition rather than empty fields presented as execution.

#### Scenario: Transition output passes but post-state differs
- **WHEN** the native owner returns the expected output while the reached state or effect differs from the case oracle
- **THEN** the case remains non-pass and reports the exact post-state/effect mismatch

#### Scenario: Static element has no state transition
- **WHEN** a property or other non-transition element has no meaningful state movement
- **THEN** its case records a reasoned state/effect not-applicable disposition and does not invent pre/post-state execution

### Requirement: Strict hierarchical blueprint topology
A qualified blueprint SHALL have exactly one root, one parent for every non-root node, an explicit abstraction depth for every node, no hierarchy cycle, and no orphan node. Cross-cutting semantic dependencies SHALL remain separate from the parent-child hierarchy and SHALL NOT create additional hierarchy parents.

#### Scenario: Three-level hierarchy closes
- **WHEN** a workflow blueprint declares a root objective, middle-level coordination nodes, and leaf transition nodes with one parent per non-root node
- **THEN** WorldGuard accepts the hierarchy only when every node is reachable from the root and each declared depth agrees with its parent chain

#### Scenario: Cross-cutting dependency is mistaken for parentage
- **WHEN** a leaf element depends on an element in another branch
- **THEN** WorldGuard records a dependency edge without giving the leaf a second hierarchy parent

### Requirement: Typed parent-child interface closure
Every blueprint node and input-bearing element SHALL declare typed input and output ports with schema id/version, explicit refinements, and cardinality. Compatibility SHALL require exact schema identity or declared source refinement plus equal cardinality; matching `value_type` text alone MUST NOT prove compatibility. Every input SHALL have exactly one allowed source owner and every node input at least one consumer. Every child output SHALL map exactly to a parent input, parent output, or reasoned internal terminal. Every element output SHALL feed an element input, its owner-node derivation, or one explicit internal terminal. Missing, duplicate, mixed, decorative, unknown, incompatible, or cross-wired dispositions SHALL block qualification.

#### Scenario: Declared input feeds the complete child path
- **WHEN** one declared external root input is mapped through compatible parent-child inputs and then into each input-bearing leaf element
- **THEN** reverse trace reaches that declared input as a real terminal and every intermediate input mapping contributes to interface closure

#### Scenario: Child input has no exact source owner
- **WHEN** a child input is unmapped, mapped more than once, names an unknown source, or has incompatible type or cardinality
- **THEN** WorldGuard reports the exact child input and source-owner defect and stops proven depth at that interface

#### Scenario: Child outputs account for parent result
- **WHEN** all child outputs are mapped to compatible parent ports and the parent result identifies its contributing child outputs
- **THEN** the parent-child interface is closed and may contribute to the proven understanding depth

#### Scenario: Child output disappears at the parent boundary
- **WHEN** a child output is neither consumed, exposed, nor explicitly internalized
- **THEN** WorldGuard reports a typed interface gap and stops the proven depth at that boundary

#### Scenario: Mapping and derivation name different contributors
- **WHEN** a child output is disposed to one parent output but that parent output's derivation consumes a different child or owned-element output
- **THEN** WorldGuard reports the exact unmatched mapping and derivation identities and blocks interface closure

#### Scenario: Declared input is never consumed
- **WHEN** a node input has one valid producer but feeds no child or owned element input
- **THEN** WorldGuard reports a decorative-input gap instead of counting the declaration as useful interface coverage

### Requirement: Domain bindings are explicit and role-separated
WorldGuard SHALL resolve one exact behavior-commitment adapter id/version/capability from a closed current registry. The registration SHALL bind its execution owner/executor and required/supported input kinds. WorldGuard SHALL safely observe each exact local input reference by kind, mode, locator, target/revision, and content fingerprint; replay the current request contract against current target material; and derive the required output and contributor elements plus a terminal owner receipt. The inventory file SHALL be an exact cache of the replay result, not a self-hashed authority. Declared outputs SHALL close replayed commitments bidirectionally, recursive lineage SHALL retain every committed contributor branch, and each derived contributor SHALL bind independently to target material, evidence, tests/checks, and native Guard results. Caller-authored outputs, caches, contribution flags, and role fields MUST NOT shrink the denominator. Missing, stale, external-only, unregistered, mismatched, or unsupported inputs SHALL remain typed gaps with no fallback extractor.

The same sole registered adapter SHALL also replay one exact target-semantic authority input and emit the target-specific semantic candidate. That candidate SHALL name the exact required node and element ids, element kinds and owners, applicable Guard-owner set, actual registered executor identities, native provider identities, binding/source responsibilities, claim boundary, and every task behavior as `Input x PreState -> Output x PostState` with effects and protected failures. It SHALL retain locator/value provenance into the observed target inputs and exhaust every required target-material leaf. The blueprint element/native-semantic/purpose/binding declarations SHALL exact-match that owner output in both directions. Content hashes establish input identity only; neither candidate fields, caller subsets, recomputed caches/receipts, nor blueprint-local fingerprints may define or shrink the denominator.

Object-DNA completeness SHALL have a separate authority boundary. The adapter SHALL require one external object-census record produced and signed outside the WorldGuard runtime. Its signed authority SHALL freeze the exact target/revision/boundary, target claim kind, required nodes, per-element kind/owner/Guard/support-mode/four-role applicability/derivation identities, applicable Guard set, and exact request-contract, target-material, and target-semantic-authority content fingerprints. Runtime resources SHALL contain no private signing key and no built-in trusted producer. Signature validation proves only record integrity; object-DNA qualification additionally requires the caller to trust the exact census-authority fingerprint or exact producer-descriptor fingerprint. Missing, invalid, untrusted, incomplete, or non-integrated census state SHALL remain directly queryable as candidate consistency but MUST NOT be reported as object-DNA qualified.

For every independently required target semantic element, the target-semantic authority SHALL also declare an exact four-role closure matrix. Each of `target_material`, `evidence`, `test_check`, and `native_result` SHALL have exactly one disposition: either one exact binding responsibility or typed `not_applicable` with a non-empty target-specific reason. A role MUST NOT be both bound and not applicable, and the candidate binding set MUST exact-match every applicable authority responsibility. Parent, summary, aggregate, and state elements SHALL NOT be exempt merely because they do not directly contribute to the selected root output. If their meaning is derived, the applicable authority responsibility SHALL identify the exact child output or parent-output derivation that supports it; remaining roles MAY be reasoned not applicable. Missing, duplicate, unknown, or candidate-only responsibilities block qualification.

#### Scenario: Target material is rebound while candidate semantics stay unchanged
- **WHEN** observed target material changes actor, role, task, state transition, or another bound semantic value while the blueprint keeps the prior semantic fields and all candidate/cache/receipt fingerprints are recomputed
- **THEN** adapter replay reports the exact target-value provenance mismatch and native qualification cannot pass

#### Scenario: Required Guard element is removed coherently
- **WHEN** a caller removes one target-required element, its root ownership, resource, binding, and all candidate-derived identities together
- **THEN** the unchanged signed census reports the missing node/element/Guard/binding responsibility and does not accept the smaller candidate as object DNA, even if the caller recomputes every candidate/cache fingerprint

#### Scenario: Candidate rewrites its semantic authority and census together
- **WHEN** a caller removes an element or changes a role to `not_applicable`, regenerates the semantic authority and census content, and recomputes all public hashes without the independently trusted signing key
- **THEN** signature or trust validation fails and object-DNA qualification remains false; no candidate-carried producer descriptor becomes trusted merely by being carried in the candidate

#### Scenario: Binding owner is relabelled away from the native owner
- **WHEN** a CausalGuard-owned target semantic keeps its actual CausalGuard receipt but its blueprint binding owner is changed to EventGuard
- **THEN** qualification reports an owner mismatch against both the target-semantic commitment and current registered native execution owner/executor

#### Scenario: Different targets have different applicable Guard sets
- **WHEN** one target authority requires all seven Guards and another exact target authority requires only its actually applicable subset
- **THEN** the adapter enforces each target's complete exact set without hardcoding seven Guards as a universal denominator or expanding a bounded target to unrelated owners

#### Scenario: Normal target revision changes model consistently
- **WHEN** target material and its independent semantic authority advance together and the blueprint updates every affected semantic, behavior, owner, binding, and provenance row consistently
- **THEN** replay and qualification may pass only under a new input, adapter-result, blueprint, and native-receipt identity

#### Scenario: Leaf has complete support bindings
- **WHEN** a leaf transition binds its source material, empirical or declared evidence, test or executable check, and applicable native Guard result
- **THEN** those exact identities and fingerprints contribute independently to leaf qualification

#### Scenario: Summary or state element was previously outside the output-contributor set
- **WHEN** an independently required parent, summary, aggregate, or state element does not directly feed the selected declared output
- **THEN** WorldGuard still requires all four authority-owned role dispositions and checks its exact child-output or derivation support instead of automatically exempting it

#### Scenario: One support role is genuinely inapplicable
- **WHEN** the signed, caller-trusted census fixes one element role as `not_applicable`, the exact target-semantic authority carries the matching target-specific reason, and no candidate binding exists for that role
- **THEN** that exact role closes as reasoned non-applicability without creating fake material, evidence, test, or native-result identities

#### Scenario: Candidate invents or deletes a role responsibility
- **WHEN** the candidate adds a binding for an authority-declared non-applicable role, omits an applicable binding, or rewrites the authority responsibility identity
- **THEN** qualification fails on the exact element and role even if every cache, receipt, and candidate fingerprint is recomputed

#### Scenario: Seven-Guard calibration is not planning-target material
- **WHEN** the reusable seven-Guard owner matrix is run beside the planning-workflow fixture
- **THEN** it remains an explicitly identified oracle-carrying capability fixture, cannot add elements, owners, evidence, tests, or qualification depth to the planning-workflow DNA, and cannot claim to be an integrated seven-Guard object while its cases have no parent/child interfaces, dependencies, or claim contribution

#### Scenario: Derivation is rebound across elements
- **WHEN** a derived element points at a derivation owned by another node or another element reuses the same derivation identity
- **THEN** qualification reports the exact owner/element/port/source mismatch and cross-element reuse instead of accepting the matching derivation text

#### Scenario: A different policy-enforcement target uses the same route
- **WHEN** raw policy-enforcement material and its independent semantic authority are authored through the current compiler and then checked, impacted, traced, and queried in memory
- **THEN** the same target-neutral owners succeed under distinct target/input/blueprint identities without claiming that the model generated factual truth automatically

#### Scenario: Test reference is replaced by narrative evidence
- **WHEN** an executable-check role is required but the element contains only a prose evidence reference
- **THEN** WorldGuard preserves the evidence binding and reports the test role as an unresolved typed gap

#### Scenario: Caller narrows the required role list
- **WHEN** a declared-output contributor lists only `native_result` and omits target material, evidence, and test/check bindings
- **THEN** WorldGuard derives all four obligations from the output graph, reports the assertion mismatch, and keeps the omitted roles unresolved

#### Scenario: Caller preserves the output name but deletes a committed branch
- **WHEN** a caller removes one required contributor branch from the output derivation while retaining the same declared output id
- **THEN** WorldGuard reports `WORLD_BLUEPRINT_REQUIRED_COMMITMENT_OUTPUT_MISSING` against the independently committed port and does not qualify the blueprint

#### Scenario: Caller shrinks blueprint and cache together
- **WHEN** a caller removes a contributor branch from both the blueprint and cached inventory and recomputes every cache-local fingerprint
- **THEN** WorldGuard replays unchanged exact request/target inputs, reports the cache/result mismatch or missing replayed branch, and does not qualify the blueprint

#### Scenario: Commitment input is external, stale, or unregistered
- **WHEN** a commitment input is identity-only, its observed content differs, or the named adapter capability is absent from the closed registry
- **THEN** WorldGuard preserves the exact typed replay gap and does not use the cache, another source kind, or a fallback extractor as authority

#### Scenario: OpenSpec, Spark, or changelog supplies intent
- **WHEN** one of those source kinds is named without its own current registered adapter and exact replayable inputs
- **THEN** WorldGuard does not reinterpret it through the request-contract adapter and leaves commitment authority unresolved

#### Scenario: Binding declares current with invented content identity
- **WHEN** a local binding declares `current` and a syntactically valid hash but the safe resolved resource bytes, JSON selector, or receipt do not match
- **THEN** WorldGuard reports the exact observation defect and excludes that binding from current role closure

#### Scenario: Registered external provider observes content
- **WHEN** a current registered provider capability supplies its registered execution owner's exact request/input/result/terminal attestation and observation receipt
- **THEN** WorldGuard may count the provider-content observation without requiring the target itself to be a local file

#### Scenario: Caller invents provider identity and signs its own JSON
- **WHEN** a caller supplies an unregistered provider/version/capability or lacks the registered execution-owner attestation
- **THEN** WorldGuard preserves a provider-content gap and excludes that result from current closure

#### Scenario: Only an external identity is available
- **WHEN** a binding identifies an external resource but supplies no independently verifiable content result
- **THEN** WorldGuard preserves the identity, reports `content_not_verified`, and does not close a content obligation

### Requirement: Understanding depth is derived from closure evidence
The native target `WorldBlueprint` report SHALL record its declared domain layers as proven, gap, boundary, or not run; SHALL identify the deepest continuously proven native layer and the first unresolved native layer; and SHALL distinguish native-domain qualification, useful partial status, and full cross-artifact qualification. These product-domain layers do not rename or replace the separate seven provider-neutral FlowGuard static self-DNA layers. A model-authored confidence label, file presence, parent summary, or native self-claim MUST NOT prove child or projection closure.

#### Scenario: Overview is sound but leaf bindings are incomplete
- **WHEN** the root and middle layers close but one required leaf lacks a test binding
- **THEN** WorldGuard reports the middle layer as the deepest proven layer, names the leaf binding gap, and does not claim full domain-DNA qualification

#### Scenario: All required layers close
- **WHEN** the complete declared element denominator, hierarchy, ports, bindings, native checks, and claim boundaries are current and closed but cross-artifact projection was not run
- **THEN** WorldGuard may set native-domain qualification for that exact target revision and boundary, but keeps full-domain qualification false and projection `not_run`

### Requirement: Cross-artifact qualification is supplied and validated rather than fixed
`cross_artifact_projection` SHALL be an optional separately owned qualification input, not a hard-coded report value. When absent it remains `not_run`. When supplied it SHALL bind its provider id/version/capability/execution owner, source blueprint and report fingerprints, complete required/projected/unresolved source-id sets, normalized payload fingerprint, terminal receipt, target/revision/boundary, and one exact `proven`, `gap`, or `boundary` status. WorldGuard SHALL validate set closure, identity freshness, and receipt integrity before consuming the status. A missing, stale, self-inconsistent, caller-shrunk, or unregistered projection remains a visible non-pass and MUST NOT alter native-domain qualification.

#### Scenario: Independently owned projection closes every required source id
- **WHEN** a registered projection owner returns a current receipt whose projected ids exactly equal the required source denominator and whose unresolved set is empty
- **THEN** the projection layer may be `proven` and full-domain qualification may close only if native-domain qualification also passes

#### Scenario: No projection was requested
- **WHEN** native blueprint qualification runs without an external projection input
- **THEN** the projection layer is `not_run`, native results remain usable within their boundary, and no gap is fabricated merely because optional projection did not run

### Requirement: Target-object DNA remains a native-directory in-memory audit
WorldGuard SHALL compose and validate the complete target-neutral model, exact authoritative source bindings, external object census, native execution, external-test execution, evidence alignment, and optional FlowGuard projection in memory under the current native directory. It MUST NOT export a target-object bundle, copy replay resources, create a materialization root, write a standalone package, or expose a transport/retrieval route. The native directory and its source/resource locators remain the only authority; a terminal receipt SHALL be an in-memory typed value whose payload and fingerprint are validated directly.

#### Scenario: Audit is complete without a transport artifact
- **WHEN** a qualified target blueprint is checked and an optional FlowGuard projection closes every required source id
- **THEN** WorldGuard reports native/object/projection status and exact in-memory identities while the source directory has no new receipt, bundle, copied resource, or materialized directory

#### Scenario: Projection payload is semantically narrowed
- **WHEN** a projection omits or changes one node, port, element, binding, declared input/output, commitment, or source disposition while retaining a refreshed payload hash
- **THEN** projection validation reports a lossless-payload mismatch and does not close the cross-artifact layer

### Requirement: Blueprint identity is deterministic and current
A blueprint and its qualification report SHALL have canonical content fingerprints bound to the target id/revision/boundary, independent commitment reference, complete elements/nodes, schema-bound interfaces, output dispositions/derivations, bindings, and qualification inputs. Any governed change SHALL change the affected identity or be rejected as stale.

#### Scenario: Exact blueprint is repeated
- **WHEN** the same normalized blueprint content and qualification inputs are evaluated again
- **THEN** WorldGuard produces the same blueprint and report fingerprints

#### Scenario: Leaf dependency changes
- **WHEN** a leaf element changes one dependency while retaining an old blueprint fingerprint
- **THEN** WorldGuard rejects the stale identity before qualification
