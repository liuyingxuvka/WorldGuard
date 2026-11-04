"""Finite chapter-input stimuli; check calls the real production continuation owner."""
from worldguard.mesh import ModelMeshContract, _continues_findings


class HandoffWorld:
    def __init__(self):
        self.state_matches = True
        self.time_forward = True
        self.checked = False
        self.state_failed = False
        self.time_failed = False

    def configure(self, state_matches, time_forward):
        self.state_matches = state_matches
        self.time_forward = time_forward
        self.checked = False
        self.state_failed = False
        self.time_failed = False

    def check(self):
        before = {'claim': {'requested_semantics': ['event']},
                  'inputs': {'event_model': {'initial_states': ['lit']},
                             'events': [{'event_id': 'a', 'at': 1, 'requires': 'lit', 'initiates': 'lit'}]}}
        after = {'claim': {'requested_semantics': ['event']},
                 'inputs': {'event_model': {'initial_states': ['lit'] if self.state_matches else []},
                            'events': [{'event_id': 'b', 'at': 2 if self.time_forward else 0, 'requires': 'lit'}]}}
        mesh = ModelMeshContract.from_dict({'mesh_id': 'finite-handoff',
            'nodes': [{'model_id': 'a', 'contract': before}, {'model_id': 'b', 'contract': after}],
            'edges': [{'edge_id': 'a-b', 'from': 'a', 'to': 'b', 'relation': 'continues'}]})
        codes = {finding.code for finding in _continues_findings(
            mesh, mesh.edges[0], mesh.nodes[0].contract, mesh.nodes[1].contract)}
        self.state_failed = 'MESH_HANDOFF_STATE_MISMATCH' in codes
        self.time_failed = 'MESH_HANDOFF_TIME_BACKWARDS' in codes
        self.checked = True
