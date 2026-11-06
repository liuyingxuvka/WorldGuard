"""Finite expected native results retained from the prior test-only oracle (WG4d5aa15)."""
from dataclasses import dataclass
from .world_cases import CheckRequest, EXTERNAL_INPUTS

REQUESTS = {row.case_id: row for row in EXTERNAL_INPUTS}
REQUESTS["illegal_event_effect"] = CheckRequest("illegal_event_effect", rows="illegal_effect")

INPUT_RESULTS = {'number': 'PASS',
 'label': 'PASS',
 'iso': 'PASS',
 'word_time': 'error',
 'mixed_time': 'error',
 'duplicate_ids': 'error',
 'missing_event_time': 'PASS',
 'retired_schema_version': 'error',
 'retired_run_id': 'error',
 'retired_dependencies': 'error',
 'retired_output_requirements': 'error',
 'retired_target_guard': 'error',
 'retired_target_guards': 'error',
 'retired_atoms': 'error'}

EVENTS_RESULTS = {'illegal_event_effect': 'FAIL',
 'forbidden_event': 'FAIL',
 'event_clock': 'FAIL',
 'tokens_cloned': 'FAIL',
 'clock_reversed': 'FAIL',
 'clock_good': 'PASS',
 'missing_event_time': 'GAP',
 'token_event_mismatch': 'FAIL',
 'transition_unlinked': 'GAP',
 'space_token_agrees': 'PASS',
 'space_token_disjoint': 'FAIL',
 'space_token_unrelated': 'GAP'}

CONSISTENCY_RESULTS = {'label': 'PASS',
 'scenario_late': 'FAIL',
 'intervention_late': 'FAIL',
 'owned_boundary': 'BOUNDARY_EXCEEDED',
 'partial_run_fail': 'FAIL',
 'partial_run_gap': 'GAP'}

COMPARE_RESULTS = {'compare_match': 'PASS', 'compare_mismatch': 'FAIL', 'observed_copy': 'FAIL'}

CHECK_RESULTS = {'unbound': (1, 'GAP', ('PASS', 'PASS', 'PASS', 'PASS')),
 'false_row': (1, 'FAIL', ('PASS', 'PASS', 'PASS', 'PASS')),
 'unknown_row': (1, 'GAP', ('PASS', 'PASS', 'PASS', 'PASS')),
 'uncaught_variant': (1, 'GAP', ('PASS', 'PASS', 'PASS', 'PASS')),
 'foreign_boundary': (1, 'GAP', ('PASS', 'PASS', 'PASS', 'GAP')),
 'boundary_with_fail': (1, 'FAIL', ('PASS', 'FAIL', 'BOUNDARY_EXCEEDED', 'FAIL')),
 'boundary_with_gap': (1, 'GAP', ('PASS', 'GAP', 'BOUNDARY_EXCEEDED', 'GAP')),
 'actor_state_unchecked': (1, 'GAP', ('PASS', 'PASS', 'PASS', 'GAP')),
 'actor_state_free': (0, 'PASS', ('PASS', 'PASS', 'PASS', 'PASS')),
 'label': (0, 'PASS', ('PASS', 'PASS', 'PASS', 'PASS')),
 'word_time': (2, 'error', ('error', '', '', '')),
 'duplicate_ids': (2, 'error', ('error', '', '', '')),
 'tokens_cloned': (1, 'FAIL', ('PASS', 'FAIL', 'PASS', 'FAIL')),
 'transition_unlinked': (1, 'GAP', ('PASS', 'GAP', 'PASS', 'PASS')),
 'scenario_late': (1, 'FAIL', ('PASS', 'PASS', 'FAIL', 'FAIL')),
 'owned_boundary': (1, 'BOUNDARY_EXCEEDED', ('PASS', 'PASS', 'BOUNDARY_EXCEEDED', 'BOUNDARY_EXCEEDED')),
 'missing_event_time': (1, 'GAP', ('PASS', 'GAP', 'PASS', 'GAP')),
 'partial_run_gap': (1, 'GAP', ('PASS', 'PASS', 'GAP', 'GAP'))}

@dataclass(frozen=True)
class MeshCase:
    case: str
    state_matches: bool = True
    time_forward: bool = True
    descendant: bool = True
    child_status: str = 'PASS'
    cycle: bool = False
    one_root: bool = True
    has_variant: bool = False
    variant_caught: bool = True
    planned_node: bool = False
    named_before: bool = True

MESH_CASES = (
    MeshCase('chapters_ok_rooted.yaml'),
    MeshCase('end_state_contradiction.yaml', state_matches=False, one_root=False),
    MeshCase('ch2_resurrects.yaml', state_matches=False, one_root=False),
    MeshCase('time_backwards.yaml', time_forward=False, one_root=False),
    MeshCase('unrelated', descendant=False, one_root=False),
    MeshCase('child_fail', child_status='FAIL'),
    MeshCase('child_gap', child_status='GAP'),
    MeshCase('child_boundary', child_status='BOUNDARY_EXCEEDED'),
    MeshCase('cycle', cycle=True),
    MeshCase('chapters_ok.yaml', one_root=False),
    MeshCase('caught_variant', has_variant=True),
    MeshCase('uncaught_variant', has_variant=True, variant_caught=False),
    MeshCase('planned', planned_node=True),
    MeshCase('edge_time_backwards', time_forward=False),
    MeshCase('unnamed_fluent', state_matches=False, named_before=False),
)

MESH_RESULTS = {'chapters_ok_rooted.yaml': (0, 'PASS', (), ()),
 'end_state_contradiction.yaml': (1, 'FAIL', ('MESH_HANDOFF_STATE_MISMATCH', 'MESH_NOT_ONE_TREE'), ('FAIL',)),
 'ch2_resurrects.yaml': (1, 'FAIL', ('MESH_HANDOFF_STATE_MISMATCH', 'MESH_NOT_ONE_TREE'), ('FAIL',)),
 'time_backwards.yaml': (1, 'FAIL', ('MESH_HANDOFF_TIME_BACKWARDS', 'MESH_NOT_ONE_TREE'), ('FAIL',)),
 'unrelated': (1, 'GAP', ('CLAIM_ASSERTION_UNRESOLVED', 'MESH_NOT_ONE_TREE'), ()),
 'child_fail': (1, 'FAIL', ('CLAIM_ASSERTION_FALSE',), ()),
 'child_gap': (1, 'GAP', ('CLAIM_ASSERTION_UNRESOLVED',), ()),
 'child_boundary': (1, 'BOUNDARY_EXCEEDED', ('EVENT_BOUNDARY_NUMERIC_DYNAMICS',), ()),
 'cycle': (1, 'FAIL', ('MESH_DEPENDENCY_CYCLE',), ()),
 'chapters_ok.yaml': (1, 'GAP', ('MESH_NOT_ONE_TREE',), ()),
 'caught_variant': (0, 'PASS', (), ()),
 'uncaught_variant': (1, 'GAP', ('VARIANT_NOT_CAUGHT',), ()),
 'planned': (1, 'GAP', ('MESH_EXPECTED_NODE_CONTRACT_MISSING',), ()),
 'edge_time_backwards': (1, 'FAIL', ('MESH_HANDOFF_TIME_BACKWARDS',), ('FAIL',)),
 'unnamed_fluent': (0, 'PASS', (), ())}

