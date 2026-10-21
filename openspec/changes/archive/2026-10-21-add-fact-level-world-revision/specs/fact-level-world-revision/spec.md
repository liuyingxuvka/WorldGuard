## ADDED Requirements

### Requirement: Fact truth and falsity support remain independent

WorldGuard SHALL evaluate each fact as `true`, `false`, `both`, or `neither` from signed support and strict-rule closure.

#### Scenario: Positive and negative support coexist

- **WHEN** current evidence supports both signs of one fact
- **THEN** the fact SHALL evaluate to `both` without deriving arbitrary unrelated facts

#### Scenario: No support exists

- **WHEN** neither sign is supported
- **THEN** the fact SHALL evaluate to `neither`, not `false`

### Requirement: Revision is previewed transactionally

WorldGuard SHALL compute fact-level revision against an immutable base snapshot and SHALL keep preview separate from activation.

#### Scenario: A transaction is proposed

- **WHEN** support additions and retractions are supplied
- **THEN** WorldGuard SHALL compute closure and deltas on a copy while the accepted base remains unchanged

### Requirement: Activation preserves declared facts and evidence

WorldGuard SHALL activate only a current preview whose closure, contradiction visibility, preserved facts, regression evidence, and holdout evidence all satisfy the transaction contract.

#### Scenario: A preserved fact changes unexpectedly

- **WHEN** preview changes any declared preserved fact state
- **THEN** activation SHALL block with the changed support and rule chain

#### Scenario: The base changed after preview

- **WHEN** the accepted base fingerprint differs from the transaction base
- **THEN** activation SHALL fail stale and require a new preview

#### Scenario: Closure and regressions pass

- **WHEN** closure terminates, contradictions are visible, preserved facts pass, and current regression/holdout evidence is bound
- **THEN** WorldGuard MAY activate once and SHALL emit an immutable receipt
