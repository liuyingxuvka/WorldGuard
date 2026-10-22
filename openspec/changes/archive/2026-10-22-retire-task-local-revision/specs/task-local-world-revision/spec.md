# task-local-world-revision Specification

## Purpose
Compare a frozen prediction with a later observation and decide, task-locally and reversibly, whether a separate candidate model closes the task.
## Requirements
### Requirement: Prediction snapshot is frozen before observation
The system SHALL bind each prediction snapshot to an exact base world-model id, version, file hash, and prediction sequence before accepting its observation.

#### Scenario: Current prediction is frozen
- **WHEN** the base world-model file is readable and the prediction is structurally complete
- **THEN** `freeze` records the file SHA-256 (or checks a declared one) and emits a stable prediction fingerprint

#### Scenario: Model changes after freeze
- **WHEN** the base world-model file changes after `freeze`
- **THEN** `compare` with the frozen prediction rejects the stale model identity

#### Scenario: Observation is not later than prediction
- **WHEN** an observation sequence is equal to or earlier than the prediction sequence
- **THEN** the system rejects the comparison as hindsight-invalid

### Requirement: Real observations preserve numeric values and relationships
The system SHALL retain finite observed numeric values, observed relationship records, and a non-empty source reference. It MUST NOT reduce empirical validation to timepoint presence alone.

#### Scenario: Numeric observation is compared
- **WHEN** an observation provides an actual value for a predicted target
- **THEN** the evaluator compares it with the expected value and absolute tolerance

#### Scenario: Relationship observation is compared
- **WHEN** an observation provides a typed left/relation/right record for a predicted relationship
- **THEN** the evaluator compares the full relationship content

### Requirement: World mismatches have bounded native categories
Every expected value or relationship SHALL declare one mismatch category from initial state, transition, causal relation, resource, agent, observation mapping, or other. Contradicted or missing expectations MUST retain that category in the receipt.

#### Scenario: Causal prediction is contradicted
- **WHEN** an actual value falls outside the tolerance of an expectation categorized as causal relation
- **THEN** the mismatch receipt reports `causal_relation`

#### Scenario: Expected observation is missing
- **WHEN** a predicted target is absent from the real observation
- **THEN** the receipt reports a typed missing mismatch instead of passing

### Requirement: Candidate world model remains separate from v1
The system SHALL require distinct current base and candidate world-model artifacts and MUST NOT overwrite the base during evaluation.

#### Scenario: Separate candidate is evaluated
- **WHEN** base and candidate paths and hashes are current and distinct
- **THEN** candidate revalidation proceeds while retaining the base identity

#### Scenario: Candidate aliases the base
- **WHEN** the candidate path or content hash equals the base
- **THEN** revision validation fails because no reversible candidate exists

### Requirement: Candidate revalidation includes original scenario and real holdout
Candidate acceptance SHALL require exactly one original-scenario revalidation and exactly one real-holdout-observation revalidation, each written as `{check_id, role, empirical_comparison}` for the candidate. Evaluation SHALL run the candidate mesh once and require current native semantic execution of both declared scenario scopes plus passing independent empirical comparisons.

#### Scenario: Both revalidation roles pass
- **WHEN** the original scenario and real holdout receipts are current and both statuses pass
- **THEN** the candidate may be accepted

#### Scenario: Holdout only proves execution
- **WHEN** a holdout has semantic rollout pass but lacks a passing real-observation comparison
- **THEN** the candidate cannot be accepted

### Requirement: Candidate disposition is reversible
The system SHALL derive an accepted, rejected, or rolled-back disposition from exact current identities and the complete required revalidation inventory.

#### Scenario: Candidate passes
- **WHEN** every required original-scenario and real-holdout receipt passes before activation
- **THEN** the candidate disposition is accepted and v1 remains recorded as the rollback base

#### Scenario: Unapplied candidate fails
- **WHEN** any required receipt fails before activation
- **THEN** the candidate is rejected and `base_model_preserved` is true

#### Scenario: Applied candidate fails
- **WHEN** any required receipt fails after activation and the rollback identity equals the still-current base
- **THEN** the candidate is rolled back to v1

### Requirement: Existing semantic rollout remains authoritative for model execution
The task-local evaluator SHALL consume WorldGuard semantic-rollout status and MUST NOT duplicate or weaken EventGuard, CausalGuard, or predictive-depth checks.

#### Scenario: Empirical match without semantic rollout
- **WHEN** observed values match but the required WorldGuard semantic rollout is not passing
- **THEN** candidate revalidation remains non-pass

### Requirement: Revision remains task-local
The system SHALL limit automatic revision to the current task-model candidate and MUST NOT alter WorldGuard source, core thresholds, installed skills, or reusable defaults.

#### Scenario: Task ends
- **WHEN** a revision is accepted, rejected, or rolled back
- **THEN** no WorldGuard algorithm or default model is modified
