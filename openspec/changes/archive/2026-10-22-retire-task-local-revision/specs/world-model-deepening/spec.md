# world-model-deepening Specification

## Purpose
Define task-local predictive model deepening through independent coverage,
native depth and holdout evidence, explicit gap lineage, and bounded terminal
decisions.
## Requirements
### Requirement: Predictions carry task and coverage identity

Every current `PredictionSnapshot` SHALL bind a task id and purpose, an independently owned coverage universe whose ids equal the prediction expectations, non-empty assumptions and unknowns, a finite iteration budget, and its predecessor; later iterations SHALL also carry the exact prior gap ids. WorldGuard computes the coverage and prior-gap fingerprints. Older shapes SHALL be rejected.

#### Scenario: Shallow prediction
- **GIVEN** a prediction has one expected value but no task coverage or unknown boundary
- **WHEN** task-local depth is evaluated
- **THEN** it is blocked as shallow and cannot license broad world claims

#### Scenario: Legacy prediction shape
- **GIVEN** a prediction omits any current task, coverage, assumption, unknown, or predecessor field
- **WHEN** the prediction is parsed or frozen
- **THEN** it is rejected rather than upgraded, defaulted, or accepted through a compatibility path

### Requirement: Observations are typed evidence and the candidate runs once

Every observation SHALL carry an evidence identity computed from its actual values, relationships, source, and sequence, plus a content fingerprint independent of renameable ids and source labels. Candidate evaluation SHALL run the candidate mesh once and SHALL derive every state, transition, branch, perturbation, intervention, counterfactual, and holdout gap from that run.

#### Scenario: Caller reports no predictive gaps
- **GIVEN** the candidate run contains a predictive gap
- **AND** the caller supplies no separate remaining-gap list
- **WHEN** candidate closure is evaluated
- **THEN** the native gap remains open and the caller cannot suppress it

#### Scenario: Candidate is not a runnable mesh
- **GIVEN** the candidate model file is not a current native mesh
- **WHEN** candidate closure is evaluated
- **THEN** closure is blocked with the exact finding

### Requirement: Predictive gaps force candidate continuation

Candidate evaluation SHALL continue when the candidate run's `predictive_gaps` contain addressable state, transition, branch, perturbation, intervention, counterfactual, or holdout gaps. A candidate run that does not license the predictive claim SHALL contribute an open gap even when its raw gap list is empty.

#### Scenario: Fact revision without predictive revalidation
- **GIVEN** a fact transaction activates successfully
- **AND** the candidate has not passed the current predictive/depth/holdout checks
- **WHEN** revision closure is evaluated
- **THEN** the candidate is non-terminal and requires another iteration

### Requirement: Iterations preserve candidate identity and gap transitions

Every iteration SHALL record base/candidate identities, the exact predecessor, input/resolved/persisted/introduced gap ids, and terminal reason. Those transitions and progress SHALL be computed from the current comparison, the candidate run, and the two revalidations; caller-authored transition maps or boolean progress claims have no authority.

#### Scenario: New gap after candidate
- **GIVEN** a candidate resolves one mismatch but exposes a new branch gap
- **WHEN** the candidate is evaluated
- **THEN** the new gap remains open and the next iteration is required

#### Scenario: Renamed or unchanged gap
- **GIVEN** a candidate resolves no input gap or repeats an already observed gap fingerprint
- **WHEN** progress is evaluated
- **THEN** the task ends visibly as `progress_stalled` rather than counting a caller-authored transition as progress

### Requirement: Original and holdout revalidation are typed and independent

Candidate acceptance SHALL require exactly one original-scenario revalidation and exactly one real-holdout revalidation, each written as `{check_id, role, empirical_comparison}` for the candidate. The candidate run SHALL execute both the declared original and holdout scenarios. The two observations SHALL have different identities, sources, and content fingerprints, and the holdout fingerprint SHALL NOT occur in candidate-construction evidence.

#### Scenario: Semantic pass string instead of a comparison
- **GIVEN** a revalidation contains only `semantic_rollout_status: PASS`
- **WHEN** the current revision schema is parsed
- **THEN** the legacy shape is rejected

#### Scenario: Holdout aliases construction evidence
- **GIVEN** the holdout observation fingerprint is also used to construct the candidate
- **WHEN** candidate closure is evaluated
- **THEN** the candidate is rejected and cannot close the task

### Requirement: External blockers are exact and visible

If a required observation or world fact is unavailable outside the current tools, the result SHALL name the exact external input, the exact open gap ids it blocks, why it is required, the responsible external owner, and which claim ids are limited. An external terminal is valid only when every still-open gap is covered by those exact declarations.

#### Scenario: Missing external observation
- **GIVEN** a requested observation cannot be obtained locally
- **WHEN** WorldGuard evaluates the task model
- **THEN** it returns `external_input_required` with the input identity and affected claim boundary

### Requirement: Fact activation re-enters the same task-local owner

A successful fact activation SHALL preserve its four-valued candidate and SHALL emit a typed handoff bound to the same task, the sole `worldguard.task_local_world_revision` owner, and the activated candidate fingerprint. Fact activation SHALL always require a current prediction, a candidate run, and original and holdout revalidation and SHALL never emit `model_closed_for_task`.

#### Scenario: Fact-only activation is green
- **GIVEN** a fact transaction and its fact regression/holdout checks pass
- **WHEN** activation succeeds
- **THEN** the activation receipt ends at `task_local_revalidation_required`
- **AND** only the same task-local owner may later decide task closure
