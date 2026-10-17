# claim-derived-semantic-coverage Specification

## Purpose
TBD - created by archiving change enforce-claim-derived-semantic-coverage. Update Purpose after archive.
## Requirements
### Requirement: Target-owned Guard-model prevention contract
WorldGuard SHALL declare, for every registered Guard, the invalid claim class the Guard prevents, the boundary it does not license, and exactly one native good case that passes both the Guard runner and its semantic executor.

#### Scenario: Guard is connected but purpose-free
- **WHEN** a registered Guard lacks a prevention purpose, blocked-claim class, unsupported boundary, or its one native good case
- **THEN** Guard-model adequacy SHALL fail even when the Guard is reachable from the kernel

### Requirement: Finite protected Guard-failure universe
WorldGuard SHALL source-discover every literal Guard-runner error code and per-Guard semantic finding code, SHALL declare exactly one native bad case for every discovered `(Guard, layer, code)`, and SHALL require an oracle that observes the exact expected status and single code.

#### Scenario: Failure class is missing, duplicated, or shallowly represented
- **WHEN** the declared inventory differs from the source-discovered inventory, a failure class has zero or multiple bad cases, or a bad case emits a different status/code set
- **THEN** the native Guard-model contract and its FlowGuard exhaustion child SHALL fail closed

#### Scenario: Mesh lifecycle failure is encountered
- **WHEN** executor registration or provider availability fails
- **THEN** the failure SHALL remain under mesh/provider lifecycle ownership and SHALL NOT be counted as an individual Guard failure merely to close that Guard's inventory

### Requirement: One enforced semantic closure
WorldGuard SHALL have one current target-native closure behavior in which required semantic execution always runs. The current contract and CLI MUST reject the retired `closure_profile` field and `--closure-profile` selector instead of preserving a structural-only, advisory, bypass, or fallback path.

#### Scenario: Caller requests structural-only closure
- **WHEN** a mesh payload supplies `closure_profile` or the CLI caller supplies `--closure-profile`
- **THEN** WorldGuard SHALL reject the request before evaluation and SHALL NOT issue a structural-only result

#### Scenario: Bounded claim is evaluated
- **WHEN** a claim is bounded rather than predictive
- **THEN** WorldGuard SHALL still execute all required Guard semantics and SHALL limit only the claim boundary, not the validation depth

### Requirement: Router-visible native ownership

#### Scenario: Router compiles the current contract
- **WHEN** the global router inspects WorldGuard's current contract source
- **THEN** it SHALL discover the complete native route and check sets and SHALL NOT block WorldGuard merely because those bindings exist only inside a nested profile

### Requirement: Claim-derived Guard routes
WorldGuard SHALL derive required Guards and semantic routes from structured claim atoms and SHALL compare them with every caller-declared target route.

#### Scenario: Caller omits required Guard
- **WHEN** a claim atom requires a semantic route whose owning Guard is absent from the target mesh
- **THEN** WorldGuard SHALL return a concrete coverage `GAP` and SHALL NOT license prediction

### Requirement: Expected semantic coverage universe
WorldGuard SHALL bind expected model nodes, semantic children, scenarios, holdout scenarios, time horizon, branches, perturbations, and claim atoms to the current mesh fingerprint and native depth receipt.

#### Scenario: Required node has no contract
- **WHEN** an expected semantic-rollout node has no `GuardContract`
- **THEN** the node SHALL be listed as skipped/missing, aggregate status SHALL not pass, and coverage SHALL be reduced

#### Scenario: Caller expected list omits a discovered node
- **WHEN** the current semantic or predictive mesh contains a node that is absent from `expected_model_node_ids`
- **THEN** WorldGuard SHALL retain the node in the effective denominator, report declaration reconciliation failure, and SHALL NOT license prediction

#### Scenario: Node is explicitly excluded
- **WHEN** a target excludes a discovered node from semantic or predictive coverage
- **THEN** the exclusion SHALL include a reason and closed disposition, SHALL remain visible in the receipt, and the excluded node SHALL NOT contribute semantic receipts, aggregate coverage, or covered claim scope

#### Scenario: Exclusion is unresolved
- **WHEN** an excluded node lacks a reason, uses an unresolved disposition, or still contributes execution evidence
- **THEN** reconciliation SHALL fail and prediction SHALL remain unlicensed

### Requirement: Predictive adequacy
A predictive WorldGuard route MUST execute native rollout semantics over a non-degenerate horizon with states, transitions, interventions, counterfactuals, holdout evidence, branches, and perturbations.

#### Scenario: Single event
- **WHEN** a predictive claim supplies only one event at one timepoint
- **THEN** the local event check MAY be bounded but `predictive_claim_licensed` SHALL be false and aggregate predictive closure SHALL remain a gap

#### Scenario: Single equation
- **WHEN** a predictive or causal-outcome claim supplies one parseable equation without interventions, counterfactuals, horizon, and holdout rollout evidence
- **THEN** equation evaluability MAY be bounded but predictive closure SHALL remain a gap

#### Scenario: Structural equation map is partial
- **WHEN** an SCM declares multiple endogenous variables but supplies structural equations for only a non-empty subset
- **THEN** CausalGuard SHALL return `GAP` with `CAUSAL_MISSING_STRUCTURAL_EQUATION` and SHALL identify every missing variable

#### Scenario: Complete bounded predictive fixture
- **WHEN** all claim-derived Guards run current supported semantics over declared scenarios, horizon, branches, perturbations, interventions, counterfactuals, and holdout cases
- **THEN** the native receipt MAY set `predictive_claim_licensed` true only for that declared coverage universe

#### Scenario: Two points from a thousand-step horizon
- **WHEN** a predictive model declares 1,000 horizon steps but executes only one or two representative timepoints
- **THEN** the native count/ratio floor SHALL fail, early/middle/late gaps SHALL remain visible, and prediction SHALL remain unlicensed

#### Scenario: Many points in one phase
- **WHEN** the total representative count meets the numeric floor but all points are concentrated in one temporal phase
- **THEN** missing native early/middle/late strata SHALL block predictive licensing even if caller-declared strata rename those points

### Requirement: Per-model-node predictive depth
WorldGuard SHALL evaluate time, scenario, holdout, state, transition, branch, perturbation, intervention, and counterfactual adequacy for each expected predictive model node, not only for their aggregate union. Normal and holdout scenarios SHALL also remain separate for each claim-derived required Guard so one rich route cannot hide another route's missing rollout.

#### Scenario: Aggregate is rich but one child is shallow
- **WHEN** one model node supplies complete rollout evidence while another expected node supplies only two timepoints and a partial transition set
- **THEN** the shallow node SHALL remain a per-object gap and aggregate predictive licensing SHALL remain false

#### Scenario: One required Guard skips holdout rollout
- **WHEN** the aggregate contains normal and holdout evidence but one claim-derived required Guard does not execute the holdout scenario
- **THEN** that Guard's scenario object SHALL remain shallow and predictive licensing SHALL remain false

### Requirement: Per-variable or signal temporal depth
When an expected predictive model node exposes variables or signals, WorldGuard SHALL derive a separate temporal child universe for each variable or signal and SHALL apply the native count, ratio, and early/middle/late gates to each child.

#### Scenario: Node is deep but one variable is shallow
- **WHEN** node-level observations meet the temporal floor but one declared variable or signal has only one or two observed timepoints, or observations only in one phase
- **THEN** that child universe SHALL remain a per-object gap and predictive licensing SHALL remain false

#### Scenario: No variables or signals exist
- **WHEN** a model node genuinely exposes no variables or signals
- **THEN** WorldGuard SHALL NOT invent a fake variable-timepoint obligation and SHALL preserve the node-level temporal policy

### Requirement: Bounded target-owned temporal policy
WorldGuard SHALL combine a native `ceil(sqrt(horizon_steps))` count floor with any stricter target-declared count or ratio and SHALL require native early/middle/late coverage plus a bounded maximum normalized gap without requiring project-grade validation of every horizon point.

#### Scenario: Caller lowers the floor
- **WHEN** a caller declares zero or weaker sampling floors
- **THEN** the WorldGuard-owned count/ratio/phase floor SHALL remain effective and SHALL NOT be weakened

#### Scenario: Count and phases pass but observations remain clustered
- **WHEN** the observed set meets the square-root count floor and touches early, middle, and late phases but leaves a normalized temporal hole larger than the native maximum-gap bound
- **THEN** predictive licensing SHALL remain blocked for that model node or variable/signal child


### Requirement: Explicit skipped coverage
WorldGuard SHALL preserve every expected but unexecuted semantic child with a typed skip reason and coverage impact.

#### Scenario: Provider unavailable
- **WHEN** an expected semantic child cannot run because its provider is unavailable
- **THEN** the receipt SHALL name the child, provider state, skip reason, missing coverage, and bounded claim statement

### Requirement: Target-run native receipt
WorldGuard SHALL emit a per-run receipt containing the expected and executed coverage universe, claim-derived routes, predictive adequacy, quantitative coverage, gaps, a boolean predictive license bound to the current mesh fingerprint, and exact content-addressed native observations for every executed semantic child and governed depth obligation.

#### Scenario: Static regression is green
- **WHEN** repository engine-health regressions pass but the current target mesh receipt is absent or stale

- **WHEN** a non-trivial or predictive WorldGuard conclusion is requested
- **THEN** the exact current target input SHALL produce target-owned dynamic inventories for every horizon step, required Guard scenario/holdout object, predictive axis class, model-node policy, and claim atom
- **AND** the depth receipt SHALL use the target-owned `scheduled_production` evidence domain bound to the current verified installation identity carried inside exactly one current target-owned mesh input; identity-shaped fields present only in the generic supervisor request SHALL NOT be consumed, and repository fixtures SHALL NOT substitute for target execution
- **AND** an `AGENTS.md` maintenance declaration, repository link, local semantic PASS, or regression suite SHALL NOT substitute for that supervised receipt
- **AND** the runtime evidence SHALL reconcile discovered, declared, and excluded mesh nodes and SHALL prove that excluded nodes contributed to neither object results nor covered claim scope

#### Scenario: Summary-only predictive receipt
- **WHEN** a receipt reports passing counts or exact object names but omits the native content, evidence ref, or content hash for an executed semantic child, temporal child, scenario/holdout portfolio, predictive axis, native floor, or claim route
- **THEN** that obligation SHALL remain unverifiable and predictive closure SHALL be blocked

### Requirement: Native evidence projection integrity
WorldGuard SHALL preserve its exact target-owned selected, evaluated, and validated sets and SHALL bind contribution evidence to exact native observations rather than transport placeholders, catalogs, or mechanically generated ordinal spans.

#### Scenario: Shallow predictive universe has no validated observation
- **WHEN** a native predictive universe has an empty validated set because its floor, phase, object, or scenario requirement failed
- **THEN** the projection SHALL keep the result empty and blocked and SHALL NOT insert `bridge-health` or any other synthetic success witness


#### Scenario: Narrow completion receipt misses old runtime files
- **THEN** the receipt SHALL be invalid and WorldGuard closure SHALL remain blocked

### Requirement: Receipt-only OpenSpec verification
OpenSpec SHALL consume the exact current WorldGuard parent receipt and MUST NOT rerun, resume, or reconstruct any native declared-check, installation, or full-suite owner.

#### Scenario: Parent receipt is missing or stale
- **WHEN** the portable parent receipt is missing, partial, stale, tampered, or identity-mismatched
- **THEN** verification SHALL fail closed without executing a missing owner
