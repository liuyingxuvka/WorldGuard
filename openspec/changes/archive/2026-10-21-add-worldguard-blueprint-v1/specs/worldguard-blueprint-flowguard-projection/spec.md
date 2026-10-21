## Purpose

Project a qualified WorldGuard domain blueprint into the current FlowGuard provider-neutral blueprint system while keeping domain semantics in WorldGuard and generic topology, implementation, test, and affected-neighborhood mechanics in FlowGuard.

## ADDED Requirements

### Requirement: Projection has an explicit current toolchain gate
The FlowGuard projection SHALL become an advertised current route only after the repository and installed toolchain identify one supported FlowGuard package and blueprint schema, the project adoption record matches that identity, and projection contract tests pass. Before that gate closes, projection requests SHALL return a visible boundary and MUST NOT select an older schema, alias, local substitute, or compatibility path.

#### Scenario: Project record and installed FlowGuard disagree
- **WHEN** the WorldGuard project record names an older FlowGuard package than the active projection toolchain
- **THEN** projection remains unavailable with both observed identities and the required project-upgrade action

#### Scenario: Stable current toolchain is qualified
- **WHEN** package, schema, project record, provider contract, and projection tests all identify the same supported FlowGuard toolchain
- **THEN** WorldGuard may advertise that exact projection route as current

### Requirement: WorldGuard and FlowGuard retain distinct semantic ownership
WorldGuard SHALL own world element types, domain relations, native Guard semantics, world-level gaps, and domain impact or reverse-trace meaning. FlowGuard SHALL own generic target inventory, parent-child topology mechanics, implementation or workflow surface bindings, test and oracle inventory, understanding layers, and generic affected-neighborhood projection. Neither side SHALL duplicate or reinterpret the other side's owned semantics.

#### Scenario: Projection receives a domain relation
- **WHEN** a WorldGuard causal or normative relation is projected
- **THEN** the projection preserves its WorldGuard semantic identity while FlowGuard records only the generic node, port, binding, and dependency structure needed by the target blueprint

#### Scenario: Generic implementation inventory is absent from WorldGuard
- **WHEN** full blueprint qualification requires a code, workflow, resource, or project-test denominator
- **THEN** WorldGuard references the current FlowGuard-owned inventory and reports a boundary if it is unavailable rather than deriving a second denominator

### Requirement: Projection is content-addressed and lossless for declared scope
A projection SHALL bind a stable provider id, provider version, target id and revision, WorldGuard blueprint fingerprint, exact capability ids, normalized payload ids, parent-child port mappings, domain binding references, and projection fingerprint. Every required source id SHALL have one terminal projected or explicitly unresolved disposition.

#### Scenario: Three-level non-code blueprint is projected
- **WHEN** a qualified three-level planning workflow is projected
- **THEN** FlowGuard receives the same root, child identities, abstraction depths, typed port mappings, element ownership, and domain binding references with matching source dispositions

#### Scenario: Required source element disappears
- **WHEN** the projection payload omits a required WorldGuard element or port mapping
- **THEN** projection fails with the unresolved source id and does not issue a complete provider result

### Requirement: Projection consumes frozen inputs and performs no hidden work
The projection SHALL consume only caller-supplied, fingerprinted WorldGuard blueprint results and declared FlowGuard project inputs. It MUST NOT discover providers, execute target tools, mutate the target, synthesize missing bindings, or broaden an affected query.

#### Scenario: Provider evidence is not supplied
- **WHEN** a projection request requires a provider capability whose frozen result is absent
- **THEN** the projection reports the missing capability as a boundary and performs no provider execution or fallback

### Requirement: Ordinary WorldGuard evaluation remains independent
Unit contract checks, mesh checks, task-local revision, template construction, native blueprint qualification, impact, and reverse trace SHALL remain usable without importing or initializing FlowGuard. Only an explicit projection or full cross-artifact qualification request SHALL enter the FlowGuard boundary.

#### Scenario: Bounded WorldGuard check has no projection intent
- **WHEN** a caller requests an ordinary world contract or native blueprint check without cross-artifact projection
- **THEN** WorldGuard completes its native route without loading FlowGuard or claiming generic implementation/test closure

### Requirement: WorldGuard self-DNA has one independently inventoried software root
The WorldGuard repository self-DNA SHALL have exactly one software root and seven distinct EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard semantic subtrees. Qualification, mesh, task-local revision, templates, CLI and skill routing, validation, portable projection, installation, release, and the target-neutral `WorldBlueprint` capability SHALL appear as separately owned product or process subtrees beneath that software root. `WorldBlueprint` SHALL remain the arbitrary-target product feature and MUST NOT serve as the repository self-DNA root or derive the repository denominator from its own payload.

The denominator SHALL be inventoried independently of existing FlowGuard model membership and SHALL cover code, public APIs, CLI and facade behavior, prompts, references, configuration, documentation, data, fixtures, tests, scripts, workflows, package and portable projections, installation, and release surfaces without treating Python as the only behavior medium. Every inventoried item SHALL have exactly one terminal disposition and one primary owner. Every modeled FunctionBlock SHALL define `Input × State -> Set(Output × State)` and bind its intent, topology, implementation or target behavior, tests/checks, resources, evidence, and oracles without merging structural and semantic axes or source and generated-bundle identities.

#### Scenario: Non-Python route is part of the repository behavior
- **WHEN** a prompt route, reference, JSON contract, workflow, fixture, packaging rule, or release asset changes without changing a Python module
- **THEN** the independent denominator includes that item, assigns one disposition and primary owner, and connects its affected behavior and validation obligations to the self-DNA

#### Scenario: Existing models omit a repository item
- **WHEN** the independent repository inventory finds an item absent from all current model memberships
- **THEN** implementation inventory reports the missing disposition/owner as a layer-two gap, downstream static layers cannot pass, and the denominator is not shrunk to the already modeled set

### Requirement: Static self-DNA readiness is continuous, indexed, and provider-neutral
Static self-DNA qualification SHALL report the following ordered seven-layer path: (1) evidence qualification for the frozen provider registry, target snapshot, evidence identity, freshness, boundary, and admissible role; (2) implementation inventory for the complete independently derived code and non-code denominator and one disposition per item; (3) bidirectional traceability to one primary owner, intent or commitment, public callers, topology, affected edges, and reverse edges; (4) independent `Input × State -> Set(Output × State)` semantics including ports, dependencies, state, effects, errors, order, retry, timeout, decision, completion, and parent/child interface meaning; (5) model-code-test binding to exact implementation or target-behavior surfaces, CodeContracts or equivalent boundaries, test/check designs, cases, assertions, and current test-inventory identities; (6) resource-oracle binding to required build/runtime/config/schema/data/asset/service resources and behavioral oracles; and (7) static blueprint readiness as exact-current closure of layers 1-6, the normalized canonical projection, deterministic affected/reverse indexes, and the first unresolved gap.

Every static layer SHALL use the frozen released FlowGuard contract's one exact current status schema, preserve each distinct incomplete, stale, blocked, boundary, unverified, or not-run cause without project-local relabeling, and derive the deepest proven layer as the longest continuous passing prefix. WorldGuard MUST NOT introduce a second layer-status enumeration, compatibility mapper, or caller-authored summary status. Actual test or oracle execution, current external-resource availability, native-directory identity, installation, Git commit or tag, GitHub Release, and release-asset verification SHALL remain independent evidence or lifecycle gates. None of those results MAY promote static depth, and layer-seven readiness MUST NOT license any of those independent claims.

Ordinary maintenance SHALL evaluate only the requested or changed affected closure. Whole-static-blueprint qualification SHALL run only for an explicit initialization, completeness, architecture-reduction, toolchain-replacement, or release-prerequisite task fact. Affected-only success MUST NOT be promoted to whole-repository static readiness, and selecting whole-static scope MUST NOT itself execute tests, access external resources, install, or release anything.

#### Scenario: One Guard leaf changes during daily maintenance
- **WHEN** a current leaf or bound non-code surface changes and the caller requests ordinary maintenance
- **THEN** WorldGuard selects the deterministic affected and reverse closure, preserves unrelated sibling subtrees as not run for that request, and makes no whole-DNA claim

#### Scenario: Release requests whole-DNA evidence
- **WHEN** a release gate requests the complete repository static self-DNA as a prerequisite
- **THEN** all seven provider-neutral static layers are evaluated against the independent denominator and the first unresolved item blocks static blueprint readiness
- **AND** test execution, external resources, native-directory identity, installation, Git/tag/GitHub Release, and release assets remain separately evaluated lifecycle gates

### Requirement: Self-DNA stays in one native directory and in memory
The WorldGuard self-DNA check SHALL inventory the exact native repository directory and compose its FlowGuard software model in memory. It MUST NOT export, materialize, copy, package, or expose a standalone self-DNA directory or archive. The in-memory report SHALL include the native-directory content fingerprint, the seven static layers, and separate claim boundaries for tests, installation, Git, GitHub, and release; no output destination or copied bytes may enter the native denominator.

#### Scenario: Native directory is audited twice
- **WHEN** the same native directory and FlowGuard toolchain are checked twice without source changes
- **THEN** the in-memory native-directory fingerprint and static-layer identities remain deterministic and no new file is created

#### Scenario: A self-DNA export is requested
- **WHEN** a caller supplies an external self-DNA destination
- **THEN** the route fails closed as native-directory-only without creating or modifying the destination

### Requirement: Architecture reduction is self-DNA and proof gated
Architecture contraction SHALL occur only after the current self-DNA closes the candidate's observable contract, callers, inputs, outputs, state transitions, evidence subjects, parity oracle, target action, and affected revalidation owner. A proof-ready candidate MAY be replaced or removed only with behavior-preserving equivalence evidence. An uncertain candidate SHALL remain an explicit pending gap and MUST NOT be collapsed through an alias, compatibility reader, fallback, or similarity-only judgment. Mesh aggregation and unit execution, the kernel public facade and its owner, structural and semantic axes, native-directory and installed-runtime identities, and distinct evidence subjects SHALL remain separate unless their own complete evidence proves equivalence.

#### Scenario: Similar paths have different evidence subjects
- **WHEN** two handlers or checks look structurally similar but bind different callers, schemas, or evidence claims
- **THEN** cleanup retains both as explicitly distinct and records the missing equivalence evidence instead of merging them
