## MODIFIED Requirements

### Requirement: Candidate selection has deterministic zero, one, and many outcomes
WorldGuard SHALL select template candidates only from normalized explicit applicability facts. Declaration order, filename order, priority scores, AI preference, and the presence of a shared base fragment MUST NOT select a winner.

#### Scenario: No candidate blocks even when a base fragment exists
- **WHEN** zero non-base candidates match and a current base fragment exists for the requested contract kind
- **THEN** selection returns `no_match`, identifies the base as a non-selectable construction fragment, and construction does not begin

#### Scenario: One candidate is selected
- **WHEN** exactly one non-base candidate matches the request facts
- **THEN** selection returns `selected` with that candidate id, the required base fragment id, and exact selection fingerprint

#### Scenario: Multiple candidates block
- **WHEN** more than one non-base candidate matches the same request facts
- **THEN** selection returns `ambiguous`, preserves every matching candidate id, and construction fails without choosing one

#### Scenario: No unique base fragment blocks construction
- **WHEN** exactly one candidate matches but no unique current base fragment exists for the requested contract kind
- **THEN** construction fails with a typed base-missing or base-ambiguous error

### Requirement: Template validation integrates without replacing final closure
Template-pack validation SHALL prove construction integrity only. It MUST NOT replace `run_worldguard`, `run_model_mesh`, target-native depth evaluation, provider readiness, or SkillGuard declared-check supervision required for a broader conclusion.

#### Scenario: Selected candidate and base produce a structurally valid instance
- **WHEN** exactly one candidate is selected, its required base fragment composes successfully, and semantic evidence for a PASS conclusion is incomplete
- **THEN** the template receipt remains construction-only and later WorldGuard evaluation preserves GAP or BOUNDARY status

#### Scenario: No-match request attempts construction
- **WHEN** template selection returned `no_match`
- **THEN** template validation does not construct from the shared base and preserves the no-match result
