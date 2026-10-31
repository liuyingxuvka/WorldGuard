# One tree of world models

A mesh contains one root and nodes joined by `parent_child` and `continues` edges.
Every node has `model_id`, `contract` and optional string `source`. Contracts may be
embedded mappings or YAML/JSON paths relative to the mesh file. Unreadable paths
are input errors naming the node. Other node fields and edge relations are rejected.

Save `mesh.yaml` beside `part1.yaml` and `part2.yaml`:

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
  - {edge_id: whole_1, from: whole, to: part1, relation: parent_child}
  - {edge_id: whole_2, from: whole, to: part2, relation: parent_child}
  - {edge_id: next, from: part1, to: part2, relation: continues}
variants:
  - id: lost_departure
    code: MESH_HANDOFF_STATE_MISMATCH
    remove: ["nodes[part1].contract.inputs.events[depart].initiates"]
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

Run `mesh-check --mesh mesh.yaml`.
The summary also carries `mesh_id` and `input_digests` (the mesh file and every node contract file, relative to the mesh file, sha256 of raw bytes), so a consumer can bind a tree like one contract.
`mesh-check --example story` loads the same portable three-node shape from the skill.
`--json` adds node reports; both forms include depth-first `tree` lines: each node's
own status, ` (tree <status>)` when its subtree differs, and each `continues` edge's
result and codes; the root's subtree status equals `status`, e.g. `whole PASS (tree FAIL)`,
`  part1 PASS -> continues part2 FAIL MESH_HANDOFF_TIME_BACKWARDS`, `  part2 PASS`.

## Containment and continuation

`parent_child` defines containment: one root, at most one parent per node, all
nodes connected. Otherwise GAP `MESH_NOT_ONE_TREE`: add a root with containment
edges to every top-level node.
A root may contain only claim rows. `node:` assertions read only descendants and
require `mesh-check`; false rows FAIL, unresolved rows GAP. Every child still runs
independently. A node without `contract` reads `GAP planned`; absent edge
endpoints GAP with `MESH_EDGE_NODE_MISSING`. Cycles FAIL.

`continues` checks earlier final unscoped fluents against next initial values for
each next-mentioned fluent; earlier-only names need not be copied. Clocks must
agree and time cannot run backwards. Shared unique colors retain location. Optional
`variables: [name]` compares native causal scenario values: matching scenario names,
or one earlier scenario against every next scenario, at absolute tolerance 1e-9.
Missing values GAP; state, time, token or value differences FAIL with the edge id.

A planned node is a node without `contract`: it reads `GAP planned`
(`MESH_EXPECTED_NODE_CONTRACT_MISSING`) and the tree cannot PASS until its contract is added.

## Known-bad edits and observations

Mesh `variants:` use contract `set`/`remove`/`add`, `expect` and `code` rules on
loaded nodes/edges. Each independent copy reruns the whole tree without recursion.
A variant that escapes its expected status/code produces `VARIANT_NOT_CAUGHT`.
Malformed paths or edits are input errors naming the variant.

`timeline --mesh mesh.yaml` prints the tree, then each node's timeline as `<node>: world …`;
`--full` repeats full states; otherwise each start is full and later rows show changes. `--json` gives the full structure. Use `compare --mesh mesh.yaml --observed log.yaml`
with a `nodes: {model_id: observations}` mapping; each result names its node. Adding
`--write-observed OUT` writes an independent embedded-contract tree changing only
observed event times. Run `mesh-check --mesh OUT` to see effects on later nodes.

`source:` is an unchecked original-text pointer copied into problems. Report
status, node/edge ids, codes, differences or missing inputs and scope limits.
Full JSON preserves every child result.
