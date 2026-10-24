# worldguard-model-mesh Specification

## Purpose
Check one tree of native contracts while preserving every child's evidence.

## Requirements
### Requirement: One tree and two edge relations
`ModelMeshContract` SHALL accept `mesh_id`, `nodes`, `edges` and optional `variants`.
Nodes SHALL contain `model_id`, a contract and optional string `source`; contracts
MAY be embedded or relative YAML/JSON paths. Edges SHALL contain `edge_id`, `from`,
`to`, `relation` and optional `variables` for continuation. Only `parent_child` and
`continues` SHALL be accepted. Retired fields or relations SHALL be input errors.
Unreadable contract paths SHALL name the node in an input error.

Exactly one root, at most one parent per node and connectivity through containment
SHALL be required; otherwise GAP `MESH_NOT_ONE_TREE` SHALL list roots or multiple
parents and explain how to add one summary root. Missing endpoints SHALL be GAP
`MESH_EDGE_NODE_MISSING`; cycles SHALL FAIL.

### Requirement: Stateful continuation and containment
Continuation SHALL compare earlier final unscoped fluents with next initial values
for every next-mentioned fluent, compatible event clocks and nondecreasing time,
shared unique token locations and optional scenario variables at absolute tolerance
1e-9. Missing values SHALL GAP; definite state/time/token/value differences SHALL
FAIL with the edge and values. Earlier-only fluents need not be copied.

A `node:` assertion SHALL read only a descendant's world inputs during mesh-check;
standalone or non-descendant references SHALL GAP. Such rows SHALL not derive Guards
for their holder. Summary-only contracts MAY have no local inputs. Every child
SHALL run once and contribute its native status regardless of parent assertions.
Missing node contracts SHALL produce `MESH_EXPECTED_NODE_CONTRACT_MISSING` GAP.

### Requirement: Whole-tree known-bad edits
Mesh variants SHALL apply independent in-memory set/remove/add edits, then rerun
the complete tree with recursive variants disabled. Every variant SHALL match its
expected non-pass status and optional code; otherwise `VARIANT_NOT_CAUGHT` SHALL
block PASS. Invalid edit paths SHALL produce an input error naming the variant.

### Requirement: Readable portable tree
Both summary and full mesh reports SHALL contain depth-first `tree` lines using
two spaces per depth, each node's own status, ` (tree <status>)` when its subtree
status (own, descendants and findings inside the subtree; a `continues` finding counts
at the nearest common ancestor of its ends) differs, and each outgoing
`-> continues <id> <status> [codes]`. A node without a contract SHALL read
`GAP planned`. The root line's subtree status SHALL equal the report status.
`mesh-check --example story` SHALL read the bundled three-node story. `timeline
--mesh` SHALL print this tree and the event-bearing node timelines; `--json` SHALL
retain their complete structures. Child problems and scope limits SHALL survive
aggregation. `source:` SHALL remain an unchecked original-text pointer.

### Requirement: Whole-tree observations
`compare --mesh --observed` SHALL accept observations under `nodes`, name each node
in comparison rows and use native single-world tolerance rules. `--write-observed`
SHALL write a new tree with resolved contracts embedded and only selected observed
event times changed, leaving original files and variable values unchanged. Running
mesh-check on that copy SHALL expose native continuation and later-node failures.
