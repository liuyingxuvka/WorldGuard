# worldguard-template-pack-builder Specification

## Purpose

Provide WorldGuard-owned construction scaffolds for current GuardContract and ModelMeshContract inputs. Semantic execution remains with native world owners.

## Requirements

### Requirement: Current native manifests and registry

WorldGuard SHALL validate current schema, contract kind, exact field ownership, native validator ids and content fingerprints. Stale or malformed manifests SHALL block before construction.

### Requirement: Exact zero, one and many selection

Only normalized explicit applicability facts SHALL determine candidates. Zero candidates SHALL return `no_match` and block construction; the shared base is never a selectable fallback. One candidate SHALL compose after the unique current base. More than one SHALL remain `ambiguous`, preserve all candidate ids and block without ranking.

### Requirement: Disjoint composition and exact slots

Each fragment's owned field ids SHALL equal its payload leaves. Equal or ancestor/descendant ownership overlap, undeclared writes and contract-kind mismatch SHALL block. Each discovered slot SHALL have exactly one binding; missing or unused bindings SHALL block. No implicit value SHALL invent task identity or world evidence.

### Requirement: Native construction validation

Every built instance SHALL run its registered WorldGuard-native shape and complete claim-derived route validators. Unknown or failed bindings SHALL block. Ordinary construction SHALL require no checker-purpose declaration, proof catalog, neutral transport or supervision framework. A valid scaffold SHALL still require actual `run_worldguard` or `run_model_mesh` execution for substantive claims.

### Requirement: Exact current instance identity

The instance receipt SHALL bind registry, selection, selected/base packs, slot bindings, output, validators and final instance fingerprints. Exact repeated builds SHALL be stable. Changed governed inputs SHALL change identity or be rejected as stale.

### Requirement: Existing semantic authority

Templates SHALL neither derive an alternative Guard denominator nor choose behavior evidence, factual truth, semantic PASS or predictive license. Guard-specific packs add only their explicit input slots; mesh profiles scaffold bounded/predictive coverage fields. Native world checks retain all domain behavior, evidence boundaries and typed terminal statuses.
