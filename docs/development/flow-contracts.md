# FlowGuard 2 developer contracts

WorldGuard keeps its native world/claim checker. FlowGuard supplies a generated software map and the shared exception queries; it does not replace the world model or add a second world checker. Ordinary functional changes stay in production tests. Ask `python -m flowguard show "what this decides"` before writing another copy; bind a rule only for a necessary copy or a useful regression boundary.

## The finite native migration

The prior v0.10.0 index contained nine aspects, 40 promises, 45 explicit abstract bad observations and 58 production-test links (46 unique). Its original bytes remain in Git at `v0.10.0:tests/flow_migration/coverage.json`. The old State/expected-operation interpreter and tests that only rejected its own fabricated bad State are retired. This is not a claim that 45 shipping-code mutations were detected.

`tests/native_contracts` keeps the actual finite native inputs and the extra witnesses from all nine prior replays. Expected result tables are frozen literals expanded from the unchanged v0.10.0 test oracle; they are checked against real production functions or the real CLI, never filled from current shipping output. The seven-Guard catalog already checks every native failure code and exact status/code once, so its duplicate replay is removed and an explicit registry-equality regression is retained.

The former shared-adapter chapter flow is now four ordinary native state/time cases plus a bad-to-good recovery case in one process. Real invalid input is also checked with later-stage spies, because the old coarse stage projection did not prove that later stages never ran. Observed-copy input immutability/deep-copy independence, raw input digests, exact witness codes, mesh tree lines and reversible timeline deltas remain actual assertions.

## Every prior promise has an actual owner

| Prior aspect and promise | Native regression owner | Existing production tests retained |
|---|---|---|
| `guard_semantics:event_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `guard_semantics:agent_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `guard_semantics:space_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `guard_semantics:resource_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `guard_semantics:causal_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `guard_semantics:conflict_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `guard_semantics:norm_guard_failures_keep_their_code` | `tests/test_guard_model_contract.py::test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure` | `tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure`; `tests/guards/test_status_matrix.py:test_guard_status_matrix` |
| `mesh_handoff:continues_requires_matching_state` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_continues_carries_state_and_time`; `tests/test_model_mesh.py:test_continues_compares_exactly_the_fluents_both_chapters_name` |
| `mesh_handoff:continues_moves_time_forward` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_continues_trip_cannot_depart_before_prior_arrival` |
| `mesh_handoff:node_rows_read_descendants_only` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_node_rows_read_descendants_only` |
| `mesh_handoff:child_non_pass_reaches_root` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_child_failure_reaches_root_even_when_parent_assertion_is_true` |
| `mesh_handoff:dependency_cycle_fails` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_continues_cycle_fails` |
| `mesh_handoff:one_root` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_a_mesh_with_two_roots_is_not_one_tree` |
| `mesh_handoff:mesh_variants_must_fail` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_mesh_variant_must_fail_with_its_code` |
| `mesh_handoff:tree_lines_match_status` | `tests/native_contracts/test_native_results.py::test_mesh_handoff_native_cases` | `tests/test_model_mesh.py:test_tree_lines_show_subtree_and_edge_status` |
| `skill_install:check_reports_every_difference` | `tests/native_contracts/test_native_results.py::test_skill_install_native_bytes_and_read_only_dry_run` | `tests/test_cli_module.py:test_install_skill_copies_the_skill_and_the_launcher_writes_no_bytecode` |
| `world_check:actor_state_checked` | `tests/native_contracts/test_native_results.py::test_world_check_native_cases` | `tests/test_qualification.py:test_actor_state_unchecked_is_a_gap`; `tests/test_qualification.py:test_actor_state_free_reason_is_printed` |
| `world_check:pass_needs_bound_true_rows` | `tests/native_contracts/test_native_results.py::test_world_check_native_cases` | `tests/test_world_model_language.py:test_a_claim_without_assertions_is_not_bound_to_the_world_model` |
| `world_check:variants_must_fail` | `tests/native_contracts/test_native_results.py::test_world_check_native_cases` | `tests/test_variants_timeline.py:test_examples_check_their_known_bad_variants_and_catch_a_missing_rule` |
| `world_check:one_row_per_problem` | `tests/native_contracts/test_native_results.py::test_world_check_native_cases` | `tests/test_qualification.py:test_one_row_per_problem_in_short_and_full_reports` |
| `world_check:child_status_decides_exit` | `tests/native_contracts/test_native_results.py::test_world_check_native_cases` | `tests/test_cli_module.py:test_cli_runs_the_single_bundled_world_example`; `tests/test_cli_module.py:test_missing_bundled_example_explains_skill_distribution` |
| `world_compare:compare_flags_values_outside_tolerance` | `tests/native_contracts/test_native_results.py::test_world_compare_native_cases` | `tests/test_compare.py:test_trip_arrival_uses_minutes_and_declared_tolerance` |
| `world_compare:observedcopy_only_selected_event` | `tests/native_contracts/test_native_results.py::test_world_compare_native_cases` | `tests/test_compare.py:test_written_observed_copy_shows_the_downstream_break` |
| `world_consistency:scenario_values_reach_constraints` | `tests/native_contracts/test_native_results.py::test_world_consistency_native_cases` | `tests/test_world_model_language.py:test_scenario_overrides_reach_constraints_and_claim_rows`; `tests/test_world_model_language.py:test_interventions_on_empty_scenarios_reach_constraints_and_claim_rows`; `tests/test_world_model_language.py:test_completed_causal_runs_survive_another_incomplete_run` |
| `world_consistency:declared_boundary_is_boundary_exceeded` | `tests/native_contracts/test_native_results.py::test_world_consistency_native_cases` | `tests/test_qualification.py:test_declared_boundary_trials_keep_their_native_status`; `tests/test_qualification.py:test_each_derived_guard_boundary_is_a_final_boundary[CausalGuard]` |
| `world_events:illegal_event_has_no_effect` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_world_model_language.py:test_illegal_event_has_no_effect` |
| `world_events:event_times_reach_constraints` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_world_model_language.py:test_event_times_drive_causal_constraints_without_another_timetable` |
| `world_events:clock_times_order_events` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[time_hhmm_yaml-1-FAIL-codes0]`; `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut2_out/hhmm_false_pass_yaml-1-FAIL-codes1]` |
| `world_events:forbidden_event_fails` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_world_model_language.py:test_storm_prohibition_applies_to_the_actual_boat_event` |
| `world_events:unique_tokens_stay_unique` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_world_model_language.py:test_unique_traveler_duplication_fails_and_a_foreign_actor_is_a_gap` |
| `world_events:tokens_match_events` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_world_model_language.py:test_tokens_that_disagree_with_events_fail_at_the_step` |
| `world_events:transitions_name_events` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_world_model_language.py:test_unlinked_transition_is_a_gap_naming_it` |
| `world_events:space_matches_tokens` | `tests/native_contracts/test_native_results.py::test_world_events_native_cases` | `tests/test_qualification.py:test_space_rows_agree_with_token_places` |
| `world_input:mesh_summary_names_its_inputs` | `tests/native_contracts/test_native_results.py::test_world_input_native_cases` | `tests/test_cli_module.py:test_mesh_check_reports_mesh_id_and_input_digests` |
| `world_input:summary_names_its_inputs` | `tests/native_contracts/test_native_results.py::test_world_input_native_cases` | `tests/test_cli_module.py:test_check_reports_input_digests` |
| `world_input:bad_time_is_input_error` | `tests/native_contracts/test_native_results.py::test_world_input_native_cases` | `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/bad_time_yaml-2-error-codes2]`; `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/mixed_time_yaml-2-error-codes3]`; `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut2_out/word_time_yaml-2-error-codes4]`; `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut_out/hhmm_yaml-2-error-codes5]`; `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut_out/hhmm_padded_yaml-2-error-codes6]` |
| `world_input:duplicate_event_id_is_input_error` | `tests/native_contracts/test_native_results.py::test_world_input_native_cases` | `tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/dup_event_id_yaml-2-error-codes7]` |
| `world_input:retired_keys_are_input_errors` | `tests/native_contracts/test_native_results.py::test_world_input_native_cases` | `tests/test_contracts.py:test_retired_contract_keys_are_input_errors` |
| `world_timeline:timeline_shows_changes_after_start` | `tests/native_contracts/test_native_results.py::test_world_timeline_native_cases` | `tests/test_variants_timeline.py:test_timeline_prints_changes_after_the_start_line` |
| `world_timeline:timeline_shows_every_problem` | `tests/native_contracts/test_native_results.py::test_world_timeline_native_cases` | `tests/test_variants_timeline.py:test_timeline_shows_claims_submodels_and_every_problem` |

## The old bad observations keep their meaning

Each old bad id below is covered by the native input/witness of its promise above. The removed abstract mutation constructor is not a production owner. A real output with the described bad status/code/copy/ordering would fail those native assertions. The new invalid-input spy additionally protects `stages_run_after_parse_error`.

| Prior abstract bad observation | Preserved promise |
|---|---|
| `guard_semantics:event_guard_bad_case_passes` | `event_guard_failures_keep_their_code` |
| `guard_semantics:agent_guard_bad_case_passes` | `agent_guard_failures_keep_their_code` |
| `guard_semantics:space_guard_bad_case_passes` | `space_guard_failures_keep_their_code` |
| `guard_semantics:resource_guard_bad_case_passes` | `resource_guard_failures_keep_their_code` |
| `guard_semantics:causal_guard_bad_case_passes` | `causal_guard_failures_keep_their_code` |
| `guard_semantics:conflict_guard_bad_case_passes` | `conflict_guard_failures_keep_their_code` |
| `guard_semantics:norm_guard_bad_case_passes` | `norm_guard_failures_keep_their_code` |
| `guard_semantics:event_guard_reports_another_code` | `event_guard_failures_keep_their_code` |
| `guard_semantics:resource_guard_reports_another_code` | `resource_guard_failures_keep_their_code` |
| `mesh_handoff:label_only_handoff` | `continues_requires_matching_state` |
| `mesh_handoff:continues_closed_world` | `continues_requires_matching_state` |
| `mesh_handoff:time_not_checked` | `continues_moves_time_forward` |
| `mesh_handoff:node_rows_read_any_node` | `node_rows_read_descendants_only` |
| `mesh_handoff:root_hides_child` | `child_non_pass_reaches_root` |
| `mesh_handoff:cycles_ignored` | `dependency_cycle_fails` |
| `mesh_handoff:multiple_roots_allowed` | `one_root` |
| `mesh_handoff:variants_not_run` | `mesh_variants_must_fail` |
| `mesh_handoff:root_line_hides_edge_failure` | `tree_lines_match_status` |
| `skill_install:check_misses_an_edited_copy` | `check_reports_every_difference` |
| `world_check:unbound_claim_passes` | `pass_needs_bound_true_rows` |
| `world_check:variants_ignored` | `variants_must_fail` |
| `world_check:layered_duplicates` | `one_row_per_problem` |
| `world_check:stages_run_after_parse_error` | `child_status_decides_exit` |
| `world_check:ignores_gap` | `child_status_decides_exit` |
| `world_check:actor_state_ignored` | `actor_state_checked` |
| `world_compare:tolerance_ignored` | `compare_flags_values_outside_tolerance` |
| `world_compare:observed_copy_shifts_downstream` | `observedcopy_only_selected_event` |
| `world_consistency:endogenous_seed_dropped` | `scenario_values_reach_constraints` |
| `world_consistency:interventions_ignored` | `scenario_values_reach_constraints` |
| `world_consistency:boundary_ranked_as_gap` | `declared_boundary_is_boundary_exceeded` |
| `world_events:illegal_event_applies_effects` | `illegal_event_has_no_effect` |
| `world_events:causal_copy_drifts` | `event_times_reach_constraints` |
| `world_events:string_sorted_times` | `clock_times_order_events` |
| `world_events:norms_ignore_events` | `forbidden_event_fails` |
| `world_events:tokens_cloned` | `unique_tokens_stay_unique` |
| `world_events:token_event_drift_ignored` | `tokens_match_events` |
| `world_events:transition_event_link_ignored` | `transitions_name_events` |
| `world_events:space_token_drift_ignored` | `space_matches_tokens` |
| `world_input:digest_omits_the_contract` | `summary_names_its_inputs` |
| `world_input:word_times_accepted` | `bad_time_is_input_error` |
| `world_input:duplicate_ids_accepted` | `duplicate_event_id_is_input_error` |
| `world_input:retired_keys_accepted` | `retired_keys_are_input_errors` |
| `world_input:mesh_digest_omits_a_node` | `mesh_summary_names_its_inputs` |
| `world_timeline:timeline_repeats_full_state` | `timeline_shows_changes_after_start` |
| `world_timeline:timeline_drops_non_event_problems` | `timeline_shows_every_problem` |

## Source boundaries

The one exception policy is `tests/error_policy.py`: nine permitted caught-type/function keys, 16 actual handlers, their reasons and the written rule each serves. The shared fixed queries replace the handwritten control-flow scanner; the original handler/silencer examples remain tests of the shared facts. Exact counts matter: a second quiet handler in an allowed function is not automatically allowed.

WorldGuard permits no skipped, xfailed/xpassed or early-exit test. This is stricter than FlowGuard platform exceptions, so it selects `skip_policy = "forbid"`; the original subprocess probes remain the acceptance boundary. The suite also retains its own small `no_record_in_the_repository` fixture because native `.worldguard` contradictions must be created in copied temporary inputs.

The previous five route records only checked that callable definitions existed. Generated map queries now locate those owners; real CLI/native tests keep actual behavior and sequencing. No shadow executable workflow or manually maintained function graph is introduced.

Historical owner request files stay byte-for-byte unchanged. The skill launcher lines consumed by LogicWriting remain unchanged. Runtime/tooling migration does not itself change the installable WorldGuard skill or require a release. Formal dependency validation waits for the published FlowGuard v2.0.0 tag; a development source installation is not that evidence.

Run `python -m pytest -q` for the full native suite. CI uses `python -m flowguard check --all`, which runs ordinary pytest with the intent sentinel and fixed-query policy. Publication still waits for complete CI on its own exact source commit.
