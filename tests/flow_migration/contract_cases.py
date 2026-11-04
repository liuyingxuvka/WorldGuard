"""Finite expected facts and the original bad observations, without a model runner."""
from importlib import import_module

TOPICS = ('guard_semantics', 'mesh_handoff', 'skill_install', 'world_check', 'world_compare',
          'world_consistency', 'world_events', 'world_input', 'world_timeline')
GUARD_BAD = {
    'event_guard_bad_case_passes': ('EventGuard', 'passes', 'event_guard_failures_keep_their_code'),
    'agent_guard_bad_case_passes': ('AgentGuard', 'passes', 'agent_guard_failures_keep_their_code'),
    'space_guard_bad_case_passes': ('SpaceGuard', 'passes', 'space_guard_failures_keep_their_code'),
    'resource_guard_bad_case_passes': ('ResourceGuard', 'passes', 'resource_guard_failures_keep_their_code'),
    'causal_guard_bad_case_passes': ('CausalGuard', 'passes', 'causal_guard_failures_keep_their_code'),
    'conflict_guard_bad_case_passes': ('ConflictGuard', 'passes', 'conflict_guard_failures_keep_their_code'),
    'norm_guard_bad_case_passes': ('NormGuard', 'passes', 'norm_guard_failures_keep_their_code'),
    'event_guard_reports_another_code': ('EventGuard', 'other_code', 'event_guard_failures_keep_their_code'),
    'resource_guard_reports_another_code': ('ResourceGuard', 'other_code', 'resource_guard_failures_keep_their_code'),
}
MESH_BAD = {
    'label_only_handoff': 'continues_requires_matching_state',
    'continues_closed_world': 'continues_requires_matching_state',
    'time_not_checked': 'continues_moves_time_forward',
    'node_rows_read_any_node': 'node_rows_read_descendants_only',
    'root_hides_child': 'child_non_pass_reaches_root',
    'cycles_ignored': 'dependency_cycle_fails',
    'multiple_roots_allowed': 'one_root',
    'variants_not_run': 'mesh_variants_must_fail',
    'root_line_hides_edge_failure': 'tree_lines_match_status',
}


def module(topic):
    return import_module('tests.flow_migration.' + topic)


def cases(topic):
    return ('install',) if topic == 'skill_install' else module(topic).CASES


def expected(topic, case, mutation=''):
    contract = module(topic)
    if topic == 'world_check':
        return contract.outcome(case, mutation)
    operation = {'guard_semantics': 'RunGuard', 'mesh_handoff': 'RunMesh',
                 'skill_install': 'InstallAndCheck'}.get(topic, 'Evaluate')
    if topic == 'guard_semantics' and mutation:
        guard, mutation, _rule = GUARD_BAD[mutation]
    else:
        guard = ''
    if topic == 'skill_install':
        mutation = bool(mutation)
    return getattr(contract, 'expected_' + operation)(case, contract.State(), mutation, guard)


def mutations(topic):
    if topic == 'guard_semantics':
        return {name: row[2] for name, row in GUARD_BAD.items()}
    if topic == 'mesh_handoff':
        return MESH_BAD
    if topic == 'skill_install':
        return {'check_misses_an_edited_copy': 'check_reports_every_difference'}
    return module(topic).MUTATIONS
