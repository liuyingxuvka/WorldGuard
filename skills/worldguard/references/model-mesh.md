# One tree of world models

Split a world when separate parts need their own contracts and checks. For a two-part
story, save this `mesh.yaml` beside `part1.yaml` and `part2.yaml`:

```yaml
mesh_id: two_parts
nodes:
  - model_id: whole
    contract:
      claim:
        claim_id: ending
        asserts: [{node: part2, holds: arrived, at: t2}]
  - {model_id: part1, contract: part1.yaml}
  - {model_id: part2, contract: part2.yaml}
edges:
  - {edge_id: whole_1, source_model_id: whole, target_model_id: part1, relation: parent_child}
  - {edge_id: whole_2, source_model_id: whole, target_model_id: part2, relation: parent_child}
  - {edge_id: next, source_model_id: part1, target_model_id: part2, relation: continues}
```

`part1.yaml`:

```yaml
contract_id: part1
claim: {claim_id: departed, asserts: [{holds: travelling, at: t1}]}
inputs:
  event_model: {initial_states: [at_home]}
  events:
    - {event_id: depart, at: t1, initiates: [travelling], terminates: [at_home]}
```

`part2.yaml`:

```yaml
contract_id: part2
claim: {claim_id: arrived, asserts: [{holds: arrived, at: t2}]}
inputs:
  event_model: {initial_states: [travelling]}
  events:
    - {event_id: arrive, at: t2, initiates: [arrived], terminates: [travelling]}
```

Run `python skills/worldguard/scripts/run_worldguard.py mesh-check --mesh mesh.yaml`;
add `--json` for node reports. For two trip segments, replace `t1`/`t2` with quoted
ISO date-times and name the departure/arrival events and fluents for the trip.

`continues` carries the source's final unscoped fluent state to the target start.
Every fluent the target mentions must have the same start value; source-only fluents
are outside that target's obligation. Event time formats must agree across the edge,
and the target cannot begin before the source ends. Shared unique token colors must
start where they ended. Optional `variables: [name]` compares native causal scenario
values: by matching scenario name, or one source scenario against every target
scenario, with absolute tolerance 1e-9. Missing values are GAP; mismatches FAIL.
`continues` rejects port mappings. Dependencies, including continues, cannot cycle.

`parent_child` defines containment from parent to child; ports are optional. A `node:`
assertion can read only a descendant of its holder and requires `mesh-check`.
A summary node may have only these rows and no inputs: true rows PASS, false rows
FAIL, unresolved rows GAP. Each child still runs independently; a passing parent
cannot hide a child's non-PASS. `checked.roots` counts nodes without a parent edge.

`consumes_output_of` checks port labels and requires exact nonempty `port_mappings`;
it does not carry state. To express “the next node continues from here”, use
`continues`. If parent-child ports are supplied, the same type/cardinality checks
apply. Other relations are `depends_on`, `refines`, `replaces`, `conflicts_with`,
`same_world_version` and `supersedes`; they do not transfer ports.

Optional authority, ports, allowed/forbidden use lists, read_only and snapshots keep
their defaults. Handoffs are read-only; forbidden transfers FAIL and transfers outside
an explicit allowed list exceed the boundary. Sources default to current; only
`current`, `stale`, `unknown` are valid freshness values. A handoff requiring current
source state gaps on stale/unknown sources. Missing endpoints or contracts GAP.
Contracts may be embedded mappings or YAML/JSON paths relative to the mesh file;
unreadable files are input errors naming the node. A mesh is PASS only when every
node and edge check is PASS. Child reports, source labels and scope limits remain
available in full JSON.


## Authority and reporting

When needed, declare `authority.owns`, `excludes` and `scope_limits` for each node.
Excluded requested semantics exceed the boundary; a needed semantic absent from an
explicit ownership list is a gap. Labels and plausible prose do not expand authority.
Report the aggregate status, affected node/edge ids and each native code with its
state/value/time difference, counterexample or missing input. Keep required-source
freshness and allowed/forbidden transfers visible. Full JSON retains all child
results; a parent assertion does not replace their native checks or clear their gaps.
