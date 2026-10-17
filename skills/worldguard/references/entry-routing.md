# WorldGuard Entry Routing

This reference owns conditional instruction loading. Runtime contracts and native semantic owners determine substantive results.

1. Preserve typed task facts and their source spans: one `task_shape`, current claim/atoms/requested semantics, predictive intent, concrete model/input identities, scope, providers, and missing evidence. Absent facts stay missing.
2. Select exactly one of `unit_contract`, `model_mesh`, `world_blueprint`, `task_local_revision`, or `template_pack` using `task_shapes` in `internal-guard-routes.json`. Zero matches is no-match; several matches is ambiguity. Do not rank by words or invent a discriminator.
3. For unit, mesh, and task-local claims, use `worldguard.contracts.derive_guard_requirements`. Its denominator, unmapped semantics, and fingerprint are shared by unit qualification, mesh, and the prompt audit. `claim.target_guards` asserts completeness; it cannot replace derivation. Prediction requires EventGuard and CausalGuard. Failures stay with their native owner.
4. Load the selected shape's `reference_path` and each selected Guard capsule's `reference_path`. Missing mandatory references block. Run the declared `first_native_action` directly; no extra purpose/proof gate is required.

| Trigger | Material to load |
|---|---|
| Unit | `worldguard-contracts.md` + derived Guard material |
| Mesh | `model-mesh.md` + derived Guard material; `handoff-contracts.md` only for handoffs |
| Blueprint | `world-blueprint.md` + only explicit `affected_guard_ids` material |
| Task-local or predictive intent | `task-local-model-deepening.md` |
| Fact-support revision | `fact-revision.md` |
| Template construction | `template-packs.md` |
| Authority audit / final reporting | `model-authority.md` / `closure-report.md`, respectively |

A shape's `required_input_fields` are admission fields. A Guard's `possible_consumed_input_fields` enumerate legal branches, not fields every run must provide. A result's `consumed_inputs` records what that execution used.

For a blueprint, preserve source spans, exact `blueprint_operation`, target/revision/boundary, and explicit current `affected_guard_ids`. `create` requires target-material refs; `update` also needs current blueprint identity, change intent, and changed ids; `check` needs current identity; `impact` needs current identity and changed ids; `trace` needs current identity and one trace target. Missing, unknown, or mixed operations block. Affected Guard ids condition loading; they do not certify that impact analysis ran. Detailed census, trust, test/evidence, and projection gates live only in the blueprint reference.

Prompt-audit bundle paths and UTF-8 byte counts are author diagnostics, not measured model tokens or evidence that a reader loaded them. Preserve exact native statuses and evidence boundaries after the selected action.
