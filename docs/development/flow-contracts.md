# FlowGuard developer contracts

The U tooling migration preserves WorldGuard production behavior and its original native tests.
`tests/flow_migration/coverage.json` maps all nine prior model aspects, 40 independent rules,
45 explicit original abstract bad observations and 58 original test links. None is retired.
The bad controls reject the same abstract bad facts as before; they do not claim 45 mutations
of shipping WorldGuard code. Each aspect separately calls actual production functions or CLI
fixtures and asserts the expected native result. The five map-generated system routes retain
static callable/ownership checks; their old text does not establish additional runtime order.

`.flowguard/flow/mesh_handoff.py` is one meaningful bounded flow: every combination of
matching/mismatching shared state and forwards/backwards numeric time, plus reconfiguration
and recovery, is checked by the shared FlowGuard adapter against the actual continuation
owner. Resources, missing time, tree aggregation, input errors, guard status/code coverage,
observed-copy selection and reversible timeline rendering retain their direct native tests.
There is no replacement Explorer, old workflow interpreter or compatibility engine.

The old map recorded unmodeled launcher and release owners. Deleting its metric does not
repair either production owner. The retained installer/launcher tests and unchanged release
workflow keep their original boundaries; the finite handoff model makes no claim to model
them. Keep the launcher lines used by LogicWriting preflight unchanged.

For a stateful feature change, update the affected flow first and run `python -m flowguard check`;
for a functional contract, change its direct tests. Run the full native test suite and
`python -m flowguard release` on the final source. Conflict ids can change when a conflict's
kind changes during upgrade: compare its subject, sources and path rather than treating the
new id as a different business obligation. Historical request words remain byte unchanged.

This developer migration keeps WorldGuard at 0.9.0. It is applied to main only after the
FlowGuard v1.0.0 candidate passes U, is published and the actual public tag installation is
verified. A private 0.74.0 preview is development evidence, not that final acceptance.
