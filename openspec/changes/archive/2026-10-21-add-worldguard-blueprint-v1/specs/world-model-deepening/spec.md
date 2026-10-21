## ADDED Requirements

### Requirement: Domain deepening follows blueprint layers and evidence gaps
WorldGuard SHALL deepen a world model from overview to affected intermediate and leaf nodes according to explicit parent-child topology, claim importance, current counterexamples, affected scope, and the first unresolved interface, semantic, material, evidence, test, or native-result gap. It MUST NOT infer sufficient understanding from a model-authored depth label or load the whole blueprint when an affected closure is available.

#### Scenario: Root summary is sufficient for a bounded explanation
- **WHEN** a request asks only for a bounded overview and no unresolved claim or counterexample requires child material
- **THEN** WorldGuard returns the root summary with its proven boundary without materializing unrelated child payloads

#### Scenario: Changed leaf exposes an unresolved parent interface
- **WHEN** impact analysis identifies one changed leaf and its input source, child-output disposition, or parent derivation is incomplete
- **THEN** deepening loads that exact source-to-leaf-to-parent closure, reports the interface as the first unresolved gap, and excludes unaffected sibling branches

### Requirement: Parent understanding is derived from child closure
A parent layer SHALL summarize its children but SHALL NOT claim a deeper proven understanding than the continuous closed child path and required bindings beneath it. Missing child evidence, stale test identity, an untraced output, or an unresolved impact edge SHALL cap the reported understanding depth.

#### Scenario: Parent narrative is complete but a leaf test is stale
- **WHEN** a parent summary describes all expected behavior but one contributing leaf binds stale test evidence
- **THEN** the parent remains usable as a bounded summary while the proven understanding depth stops before that leaf closes

### Requirement: Repository understanding uses seven provider-neutral static-readiness layers
When the target is WorldGuard itself, deepening SHALL measure the continuous path through evidence qualification, implementation inventory, traceability, independent semantics, model-code-test binding, resource-oracle binding, and static blueprint readiness. Complete inventory/disposition, one primary owner, FunctionBlock state transitions, topology and interfaces, intent and caller links, implementation and test design, required resources and oracles, and deterministic affected/reverse indexes SHALL be exact obligations within those layers. Each layer SHALL consume the current static evidence of the layer beneath it, identify its first unresolved item, and MUST NOT treat a narrative summary, file presence, model membership, self-authored confidence, execution receipt, installed copy, or release artifact as proof of deeper static understanding.

#### Scenario: Six layers close but canonical static projection does not
- **WHEN** evidence qualification, implementation inventory, traceability, independent semantics, model-code-test binding, and resource-oracle binding close but the normalized exact-current static projection or its affected/reverse closure is incomplete
- **THEN** the deepest proven understanding stops at layer six and static blueprint readiness remains the explicit layer-seven gap

#### Scenario: All static layers close before lifecycle work
- **WHEN** all seven static layers are proven but tests have not executed,
  external resources were not checked, and installation and release have not
  run
- **THEN** static understanding may report layer seven while every execution,
  availability, installation, and release gate remains independently `not_run`

#### Scenario: Affected-only review closes one branch
- **WHEN** an ordinary task proves the complete affected closure for one subtree while unrelated branches were not run
- **THEN** the result licenses that bounded static maintenance scope but does not advance the whole-repository deepest static layer
