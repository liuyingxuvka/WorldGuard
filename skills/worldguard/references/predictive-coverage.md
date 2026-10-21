# Predictive coverage

Load this reference only when a mesh claim is predictive (`requested_semantics` contains `predictive`, or `semantic_coverage.profile` is `predictive`). A bounded mesh needs none of it.

## SemanticCoverageContract Fields

- `profile`: `bounded` by default or explicit `predictive`
- `expected_model_node_ids`
- `excluded_model_nodes`: explicit reason, closed disposition, and non-critical/non-contributing object only
- `expected_semantic_child_ids`
- `scenario_ids`
- `holdout_scenario_ids`
- `state_ids`
- `transition_ids`
- `event_ids`
- `fluent_ids`
- `branch_ids`
- `perturbation_ids`
- `intervention_ids`
- `counterfactual_ids`
- `horizon`: explicit `start`, `end`, and step count
- `timepoint_ids`: target-owned representative checkpoints; these are required observations, not a demand to enumerate every raw point
- `minimum_timepoint_count` and `minimum_timepoint_coverage`: optional stricter target floors; they cannot weaken the native square-root floor or maximum-gap gate
- `time_strata`: optional target-authored additional phase-to-timepoint mapping; WorldGuard always derives its native early/middle/late positions from numeric, prefixed-numeric, or ISO time values, and caller labels cannot replace those three gates
- `axis_dispositions`: for predictive coverage, exactly one current row for each `state`, `transition`, `event`, `fluent`, `branch`, `perturbation`, `intervention`, and `counterfactual` axis. Each row is either `required` with a non-empty expected-id inventory, one allowed native `observation_field`, and a claim boundary, or `not_applicable` with empty expected/observed identities, no observation field, a concrete reason, and a claim boundary.
- `per_model_node`: optional target-owned overrides when expected model nodes genuinely have different horizons or axes; without an override the shared policy applies independently to every expected node

The current mesh inventory defines the denominator. `expected_model_node_ids`
asserts that the caller accounted for that inventory and cannot remove a
discovered node. A valid exclusion remains in the discovered/declared/excluded
reconciliation report but contributes to neither execution nor covered claim
scope. WorldGuard reports which effective nodes were executed, skipped,
missing, or locally bounded. Predictive fields are not credited merely
because they exist. Every predictive identity axis must first close its
applicability disposition. A required axis compares exact expected ids to its
native output; an empty required inventory is a blocking contract defect. A
not-applicable axis passes only when its expected and native-observed ids are
both empty and its reason and claim boundary are present. Event ids bind only
to `executed_event_ids`. Fluent ids bind only to one declared fluent-specific
output: `reached_fluent_ids`, `active_fluent_ids`, or the normalized values of
`final_fluent_ids_by_scenario`. They never become state or transition
evidence. For a static EventGuard event-calculus exercise, state and transition
may therefore be reasoned `not_applicable`; WorldGuard records that disposition
instead of manufacturing `<missing>` items or treating empty arrays as a pass.
The remaining required EventGuard/CausalGuard outputs must demonstrate the
corresponding scenario, event/fluent or other applicable axes, branch,
perturbation, intervention, counterfactual, holdout, representative timepoint
count/ratio, native phase-stratified execution, and per-model-node depth. A
1,000-step horizon with only two observed points is a predictive gap; enough
points concentrated in one phase are also a gap; and a rich aggregate cannot
hide one shallow expected model node.

When a node exposes variables or signals, each `(node, variable-or-signal)` pair
is its own temporal child universe over the same horizon. Every child uses its
own observations and must satisfy the native square-root count floor plus
early/middle/late coverage. WorldGuard reports that effective floor
per object; a fixed external ratio must not
replace it. The native examples are 32 representative points for 1,000 steps
and 100 for 10,000 steps, unless a target declares a stricter floor. Meeting
the count and early/middle/late phases is still insufficient when one
normalized gap exceeds the native maximum-gap bound.

Bounded semantic `PASS` does not imply predictive readiness. Predictive closure needs `depth_receipt.predictive_claim_licensed: true` and an empty `depth_receipt.predictive_gaps` in the current mesh report.
