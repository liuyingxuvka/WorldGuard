> Historical document (June 2026 audit); it does not describe current behavior. Current behavior: `README.md` and `skills/worldguard/`.

# WorldGuard Productization Contamination Audit

Audit date: 2026-06-14

This audit covers the visible repository materials for productizing WorldGuard as a generic public project. It is a disposition record only. It does not move, delete, archive, publish, or implement any file changes.

## Productization Boundary

Core WorldGuard material is the generic model-first guard system: `GuardContract`, `GuardResult`, ledger semantics, kernel aggregation, the seven guard backbones, validation gates, and acceptance criteria that keep claims tied to explicit model evidence.

Non-core material is any fuel-cell toy demo, route repair evidence, generated replay output, one-off checker, historical blocker closure artifact, or local orchestration/runtime state. Fuel-cell content may remain useful as an optional example, but it must not become a hidden core requirement for WorldGuard.

## Disposition Register

| Material | Classification | Evidence observed | Disposition | Productization handling |
|---|---|---|---|---|
| `WorldGuard_TECHNICAL_SPEC.md` generic overview, contracts, ledgers, guard specs, kernel rules, test design, prohibited approaches, acceptance matrix, and MVP route | Core product material | The spec defines model-first checks, four `GuardStatus` values, ledger requirements, seven guard responsibilities, kernel read-only handoff, validation commands, and final MVP acceptance standards. | KEEP | Keep as the source of truth for the generic project. Downstream cleanup may move it under `docs/`, but the core semantics should remain public and generic. |
| `WorldGuard_TECHNICAL_SPEC.md` fuel-cell toy demo section, including repair-v5 and repair-v4 demo blocks | Sample-only and mixed into core-facing spec | The demo is explicitly scoped as a toy fixture and says it does not validate real fuel-cell physics, law, safety, compliance, deployment, market, or strategy claims. It also contains repair-version history. | ARCHIVE | Split out of the core spec into optional example documentation or archived productization evidence. Do not leave it as a core requirement section. |
| `WorldGuard_TECHNICAL_SPEC.md` repository layout references to `examples/fuel_cell/` and `tests/test_fuel_cell_demo.py` | Optional example blueprint | The blueprint places fuel-cell assets under `examples/` and tests, not in guard core modules. | KEEP | Keep only as an optional example/test blueprint. Public copy must say the demo is a fixture, not a domain validation claim. |
| `.flowpilot/` | Run-local orchestration state | The directory is present at the repository root and is not part of the product API, docs, examples, tests, or source package. Its contents were not inspected for this audit. | DROP | Exclude from public repository content. If retained for internal provenance, keep outside the public project tree. |
| `evidence/` root | Non-core evidence dump | All visible child paths are WG-13 fuel-cell repair artifacts or repair checks, not generic WorldGuard source. | ARCHIVE | Do not publish as a root-level project directory. Downstream work should either relocate current sample fixtures into `examples/`/`tests/fixtures/` or preserve evidence under a private/internal archive. |
| `evidence/wg-13-fuel-cell-case-repair-v5-artifact/input_story_fragment.yaml` | Current sample-only fixture | Defines Company A/B/C fuel-cell toy story, target guards, and explicit no-real-world scope limits. | KEEP | Keep only if relocated to an optional fuel-cell example fixture path. It must not be required by generic guard contracts or core acceptance. |
| `evidence/wg-13-fuel-cell-case-repair-v5-artifact/world_model.yaml` | Current sample-only fixture | Defines toy agents, lab spaces, resources, causal variables, payoff table, norms, and event line for the fuel-cell example. | KEEP | Keep only as optional example/test fixture data. Generic WorldGuard behavior must be validated by broader per-guard fixtures, not by this domain alone. |
| `evidence/wg-13-fuel-cell-case-repair-v5-artifact/expected_guard_report.yaml` | Current sample-only expected output | Records expected outputs for all seven guards and maps the demo contradiction to canonical `FAIL`. | KEEP | Keep only as optional fuel-cell expected-output fixture. It should not define the universal acceptance shape by itself. |
| `evidence/wg-13-fuel-cell-case-repair-v5-artifact/ledger_outputs.yaml` | Current sample-only ledger fixture | Provides event, agent, space, resource, causal, conflict, norm, counterexample, and aggregate ledgers for the toy demo. | KEEP | Keep only as optional example ledger fixture. Core ledger requirements should stay in generic docs and tests. |
| `tools/check_wg13_repair_v5_deliverables.py` | Current sample/release-evidence checker | Checks the v5 fuel-cell artifact files, closure evidence, contradiction semantics, and toy boundaries. It is tied to WG-13 repair-v5 paths and blocker closure evidence. | ARCHIVE | Do not keep as a root-level generic tool. If its checks remain useful, convert the reusable parts into normal example tests; otherwise archive with the v5 repair evidence. |
| `evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/closure_evidence.json` | Current route closure evidence, non-core | Records v5 freshness, artifact locations, blocker linkage, deliverable checks, final matrix, gate ledger, and terminal replay. | ARCHIVE | Preserve only as internal route evidence. Do not make blocker closure JSON part of the public project surface. |
| `evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/replay_output.json` | Generated replay output | Generated by the v5 checker and includes machine replay projection for the fuel-cell route. | DROP | Exclude from public source. Regenerate from tests when needed instead of committing route-local output. |
| `tools/check_wg13_repair_v4.py` | Stale repair checker | Checks repair-v4 headings and `blocker-0003` closure evidence; superseded by repair-v5. | DROP | Remove from public product scope. It is stale and should not remain beside generic project tooling. |
| `evidence/wg-13-fuel-cell-case-repair-v4/repair_v4_evidence.json` | Stale historical repair evidence | Records repair-v4 evidence, `blocker-0003` closure, and an older integrated fuel-cell check that is superseded by repair-v5. | ARCHIVE | Keep only in a private or historical archive if provenance is required. Do not use for current public acceptance. |

## Category Coverage

| Category | Covered materials | Disposition |
|---|---|---|
| Generic WorldGuard core | `WorldGuard_TECHNICAL_SPEC.md` non-demo sections covering contracts, status semantics, ledgers, guard specs, kernel behavior, validation, and acceptance | KEEP |
| Fuel-cell optional example | `WorldGuard_TECHNICAL_SPEC.md` fuel-cell demo section; `evidence/wg-13-fuel-cell-case-repair-v5-artifact/*.yaml` | KEEP only as optional example fixtures after relocation or clear labeling |
| Current route/productization evidence | `tools/check_wg13_repair_v5_deliverables.py`; `evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/closure_evidence.json` | ARCHIVE |
| Generated output | `evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/replay_output.json` | DROP |
| Stale repair-v4 material | `tools/check_wg13_repair_v4.py`; `evidence/wg-13-fuel-cell-case-repair-v4/repair_v4_evidence.json`; repair-v4 blocks embedded in the spec | DROP stale checker; ARCHIVE stale evidence and embedded history |
| Run-local orchestration state | `.flowpilot/` | DROP from public repository scope |

## Downstream Consumption Notes

- `archive_plan` can treat `ARCHIVE` rows as material that may be preserved outside the clean public core, with v5 current evidence separated from stale v4 evidence.
- `file_map` can map `KEEP` core material to public docs/source/tests, map `KEEP` sample fixtures to optional example paths, and exclude `DROP` rows from public source.
- `core_clean_check` should fail if `.flowpilot/`, root-level `evidence/`, root-level WG-13 repair checkers, or stale repair-v4 materials remain in the generic public project surface.
- `public_release_audit` should verify that fuel-cell content is described only as a toy fixture and that no public copy claims real fuel-cell physics, legal compliance, safety certification, deployment readiness, market truth, or strategy proof.

## Local Validation

- The audit names the visible non-core, stale, sample-only, generated, and run-local material categories.
- Each audited material has an explicit `KEEP`, `ARCHIVE`, or `DROP` disposition.
- This document does not perform archive or drop actions; it only records downstream disposition decisions.
- The audit does not copy private packet body text and does not make fuel-cell material part of core WorldGuard requirements.
