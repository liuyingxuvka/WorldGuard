# worldguard-template-pack-builder Specification

## Purpose

Provide WorldGuard-owned construction scaffolds for current GuardContract and ModelMeshContract inputs. Semantic execution remains with native world owners.

## Requirements

### Requirement: Current native manifests and registry

WorldGuard SHALL validate the schema, contract kind, exact field ownership and native validator ids of every built-in manifest. Malformed manifests SHALL block before construction.

#### Scenario: Manifest names an unknown validator
- **WHEN** a manifest binds a validator id that WorldGuard does not register
- **THEN** registry construction SHALL fail with `TEMPLATE_NATIVE_VALIDATOR_UNKNOWN`

### Requirement: Exact zero, one and many selection

Only normalized explicit applicability facts SHALL determine candidates. Zero candidates SHALL return `no_match` and block construction; the shared base is never a selectable fallback. One candidate SHALL compose after the unique current base. More than one SHALL remain `ambiguous`, preserve all candidate ids and block without ranking.

#### Scenario: Two candidates match
- **WHEN** the facts match two candidate packs
- **THEN** selection SHALL be `ambiguous`, list both ids and build nothing

### Requirement: Disjoint composition and exact slots

Each fragment's owned field ids SHALL equal its payload leaves. Equal or ancestor/descendant ownership overlap, undeclared writes and contract-kind mismatch SHALL block. Each discovered slot SHALL have exactly one binding; missing or unused bindings SHALL block. No implicit value SHALL invent task identity or world evidence.

#### Scenario: Binding is missing
- **WHEN** a declared slot has no binding
- **THEN** construction SHALL fail with `TEMPLATE_SLOT_MISSING`

### Requirement: Native construction validation

Every built instance SHALL run its registered WorldGuard-native shape and claim-derived route validators. Unknown or failed validators SHALL block. The instance receipt SHALL list only the selection, the composed pack ids and each validator's result; it SHALL carry no construction fingerprints. A valid scaffold SHALL still require actual `run_worldguard` or `run_model_mesh` execution for substantive claims.

#### Scenario: Built contract is incomplete
- **WHEN** the built GuardContract lacks a run id
- **THEN** construction SHALL fail with `TEMPLATE_NATIVE_VALIDATION_FAILED`

#### Scenario: Pack misses a claim-derived Guard route
- **WHEN** the claim of a built GuardContract derives a Guard that its `target_guards` do not list
- **THEN** construction SHALL fail with `TEMPLATE_NATIVE_VALIDATION_FAILED` and name the missing Guard ids

### Requirement: Existing semantic authority

Templates SHALL neither derive an alternative Guard denominator nor choose behavior evidence, factual truth, semantic PASS or predictive license. Guard-specific packs add only their explicit input slots; mesh profiles scaffold bounded/predictive coverage fields. Native world checks retain all domain behavior, evidence boundaries and typed terminal statuses.

#### Scenario: Scaffold is built
- **WHEN** a Guard contract is built from a template
- **THEN** its verdict SHALL come only from running it through `run_worldguard`
