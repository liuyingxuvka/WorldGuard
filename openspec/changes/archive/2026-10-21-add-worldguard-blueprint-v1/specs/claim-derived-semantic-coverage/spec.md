## ADDED Requirements

### Requirement: Qualification denominator is identical across public shapes
For a given structured claim and target revision, WorldGuard SHALL derive one required Guard and semantic obligation denominator before unit, mesh, blueprint, or task-local aggregation. Caller declarations MUST reconcile exactly with that denominator before execution. An omitted derived Guard remains a visible gap; an unexpected declaration blocks all Guard execution rather than widening the denominator or selecting another owner.

#### Scenario: Unit caller omits a derived Guard
- **WHEN** a unit contract declares only EventGuard but its structured claim also requires CausalGuard
- **THEN** the qualification report retains both derived Guards, records the omitted CausalGuard declaration, and keeps final qualification non-pass

#### Scenario: Mesh declares the complete set for the same claim
- **WHEN** the same claim is evaluated in a mesh whose node declares EventGuard and CausalGuard
- **THEN** its required semantic denominator equals the unit route denominator rather than a mesh-specific superset or subset

#### Scenario: Caller declares an unrelated Guard
- **WHEN** the derived denominator contains EventGuard but the caller additionally declares AgentGuard
- **THEN** qualification records the unexpected AgentGuard, executes neither structural nor semantic owners, and returns a non-pass result

### Requirement: Unmapped structured semantics block qualification visibly
Every structured claim atom SHALL map to one or more current semantic owners or to an explicit unsupported boundary. An unmapped atom SHALL remain in the expected denominator with its identity and affected claim ids and MUST NOT be ignored, converted to a general Guard, or removed by a caller declaration.

#### Scenario: Claim atom has no current Guard mapping
- **WHEN** a structured claim contains a semantic atom with no registered WorldGuard owner
- **THEN** qualification reports the unmapped atom and affected claims and does not execute a guessed fallback Guard
