"""The unchanged finite native world fixtures shared by independent model aspects."""
from dataclasses import dataclass, replace
from copy import deepcopy
from contextlib import redirect_stdout
from pathlib import Path
import tempfile,io,json,sys
from flowguard import InvariantResult
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'pyproject.toml').is_file())
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

@dataclass(frozen=True)
class CheckRequest:
    case_id: str
    time_form: str = "label"
    event_order_correct: bool = True
    duplicate_ids: bool = False
    scm_mode: str = "none"
    boundary: str = "none"
    rows: str = "order"
    tokens_cloned: bool = False
    forbidden_event: bool = False
    uncaught_variant: bool = False
    compare: bool = False
    compare_mismatch: bool = False
    retired_key: str = ""
    token_event_mismatch: bool = False
    transition_unlinked: bool = False
    observed_copy: bool = False
    timeline: bool = False
    space_token: str = "none"
    actor_state: str = "none"


EXTERNAL_INPUTS = (
    CheckRequest("actor_state_unchecked", actor_state="unchecked"),
    CheckRequest("actor_state_free", actor_state="free"),
    CheckRequest("compare_match", rows="comparison", compare=True),
    CheckRequest("compare_mismatch", rows="comparison", compare=True, compare_mismatch=True),
    CheckRequest("uncaught_variant", uncaught_variant=True, rows="variants"),
    CheckRequest("forbidden_event", forbidden_event=True, rows="norm"),
    CheckRequest("event_clock", scm_mode="event_clock", rows="variable"),
    CheckRequest("tokens_cloned", tokens_cloned=True, rows="tokens"),
    CheckRequest("number", time_form="number"),
    CheckRequest("label"),
    CheckRequest("iso", time_form="iso"),
    CheckRequest("clock_reversed", time_form="clock", event_order_correct=False),
    CheckRequest("clock_good", time_form="clock"),
    CheckRequest("word_time", time_form="word"),
    CheckRequest("mixed_time", time_form="mixed"),
    CheckRequest("duplicate_ids", duplicate_ids=True),
    CheckRequest("scenario_late", scm_mode="scenario", rows="variable"),
    CheckRequest("intervention_late", scm_mode="intervention", rows="variable"),
    CheckRequest("owned_boundary", boundary="owned"),
    CheckRequest("foreign_boundary", boundary="unselected"),
    CheckRequest("unbound", rows="none"),
    CheckRequest("false_row", rows="false"),
    CheckRequest("unknown_row", rows="unknown"),
    CheckRequest("missing_event_time", time_form="missing"),
    CheckRequest("partial_run_fail", scm_mode="partial_fail", rows="variable"),
    CheckRequest("partial_run_gap", scm_mode="partial_gap", rows="variable"),
    CheckRequest("boundary_with_fail", time_form="clock", event_order_correct=False, boundary="owned"),
    CheckRequest("boundary_with_gap", time_form="missing", boundary="owned"),
    *(CheckRequest("retired_" + key, retired_key=key) for key in (
        "schema_version", "run_id", "dependencies", "output_requirements", "target_guard", "target_guards", "atoms")),
    CheckRequest("token_event_mismatch", token_event_mismatch=True, rows="tokens"),
    CheckRequest("transition_unlinked", transition_unlinked=True, rows="tokens"),
    CheckRequest("observed_copy", compare=True, compare_mismatch=True, observed_copy=True, rows="comparison"),
    CheckRequest("timeline_late_ferry", scm_mode="event_clock", rows="variable", timeline=True),
    CheckRequest("space_token_agrees", rows="tokens", space_token="agrees"),
    CheckRequest("space_token_disjoint", rows="tokens", space_token="disjoint"),
    CheckRequest("space_token_unrelated", rows="tokens", space_token="unrelated"),
)


def _real_contract(request):
    if request.actor_state != "none":
        event = {"event_id": "unlock", "at": "t1", "actor": "Lena", "source": "actor fixture",
                 "requires": "door_locked", "initiates": "door_unlocked", "terminates": "door_locked"}
        if request.actor_state == "free":
            event["actor_state_free"] = "the door opens from either side"
        return {"claim": {"asserts": [{"holds": "door_unlocked", "at": "t2"}]},
                "inputs": {"event_model": {"initial_states": ["lena_on_mainland", "lena_has_key", "door_locked"]},
                           "events": [event]}}
    if request.retired_key:
        contract = _real_contract(replace(request, retired_key=""))
        destination = contract["claim"] if request.retired_key in {"target_guard", "target_guards", "atoms"} else contract
        destination[request.retired_key] = None
        return contract
    if request.space_token != "none":
        contract = _real_contract(replace(request, space_token="none", rows="tokens_world"))
        region = {"agrees": "out", "disjoint": "home", "unrelated": "home"}[request.space_token]
        rows = [{"at": "t2", "x": "traveler", "y": region, "relation": "NTPP"}]
        if request.space_token == "disjoint":
            rows.append({"at": "t2", "x": "home", "y": "out", "relation": "DC"})
        contract["inputs"]["spatial_relations"] = rows
        contract["inputs"]["events"][0]["actor"] = "traveler"
        return contract
    if request.token_event_mismatch or request.transition_unlinked or request.rows == "tokens_world":
        transition = {"id": "move", "event": "move", "consumes": [{"place": "start", "color": "traveler", "qty": 1}],
                      "produces": [{"place": "other" if request.token_event_mismatch else "out", "color": "traveler", "qty": 1}]}
        if request.transition_unlinked:
            del transition["event"]
        return {"claim": {"requested_semantics": ["event", "resource"], "asserts": [{"holds": "out", "at": "t2"}]},
                "inputs": {"event_model": {"initial_states": ["start"]},
                    "events": [{"event_id": "move", "at": "t1", "requires": "start", "initiates": "out", "terminates": "start"}],
                    "resources": {"unique": ["traveler"], "places": {"start": [{"color": "traveler", "qty": 1}], "out": [], "other": []},
                                  "transitions": [transition]}}}
    if request.observed_copy:
        contract = _real_contract(replace(request, observed_copy=False))
        contract["inputs"]["causal_model"] = {"variables": ["distance"], "equations": {"distance": "3"}, "scenarios": {"plan": {}}, "constraints": ["distance >= 0"]}
        return contract
    if request.uncaught_variant:
        return {"claim": {"asserts": [{"holds": "done", "at": "t3"}]},
            "inputs": {"events": [{"event_id": "ready", "at": "t1", "initiates": "ready"},
                {"event_id": "use", "at": "t2", "initiates": "done"}]},
            "variants": [{"id": "requires_rule", "code": "EVENT_PRECONDITION_UNMET", "set": {"inputs.events[use].at": "t0"}}]}
    if request.forbidden_event:
        return {"claim": {"asserts": [{"actor": "traveler", "action": "take_boat", "modality": "forbidden"}]},
            "inputs": {"events": [{"event_id": "board", "at": 2, "actor": "traveler", "action": "take_boat", "initiates": "aboard"}],
                "norms": [{"actor": "traveler", "action": "take_boat", "modality": "forbidden", "condition": "storm"}],
                "facts": [{"fact_id": "storm", "value": True}]}}
    if request.tokens_cloned:
        return {"claim": {"asserts": [{"place": "out", "color": "traveler", "qty": 2}]},
            "inputs": {"event_model": {"initial_states": ["start"]},
                "events": [{"event_id": "clone", "at": "t1", "requires": "start", "initiates": "out", "terminates": "start"}],
                "resources": {"unique": ["traveler"], "places": {"start": [{"color": "traveler", "qty": 1}], "out": []},
                "transitions": [{"id": "clone", "event": "clone", "consumes": [{"place": "start", "color": "traveler", "qty": 1}],
                    "produces": [{"place": "out", "color": "traveler", "qty": 2}]}]}}}
    if request.scm_mode == "event_clock":
        return {"claim": {"asserts": [{"variable": "slack", "op": ">=", "value": 0}]},
            "inputs": {"events": [{"event_id": "train", "at": "10:05", "initiates": "at_port"},
                {"event_id": "ferry", "at": "10:00", "initiates": "aboard"}],
                "causal_model": {"variables": ["slack"], "equations": {"slack": "t_ferry - t_train"},
                    "scenarios": {"plan": {}}, "constraints": ["slack >= 0"]}}}
    if request.scm_mode != "none":
        if request.scm_mode.startswith("partial_"):
            value = -2 if request.scm_mode == "partial_fail" else 2
            causal = {"variables": ["x", "y"], "exogenous": ["u"], "equations": {"x": "u", "y": "x + 1"},
                      "scenarios": {"bad_missing": {}, "actual": {"u": value}}, "constraints": ["x >= 0"]}
            rows = [{"variable": "x", "op": ">=", "value": 0, "scenario": "actual"}]
        else:
            causal = {"variables": ["x", "y"], "equations": {"x": "1", "y": "x + 1"}, "scenarios": {"base": {}}, "constraints": ["y >= 0"]}
            if request.scm_mode == "scenario":
                causal["scenarios"]["late"] = {"x": -2}
            else:
                causal["interventions"] = [{"intervention_id": "late", "scenario_id": "base", "set": {"x": -2}}]
            rows = [{"variable": "y", "op": ">=", "value": 0}]
        return {"claim": {"claim_id": request.case_id, "asserts": rows}, "inputs": {"causal_model": causal}}
    first, second = {
        "number": (0, 2.5), "label": ("t9", "t10"), "iso": ("2026-11-02T09:40", "2026-11-02T10:20"),
        "clock": (("9:40", "10:20") if request.event_order_correct else ("10:20", "9:40")),
        "word": ("evening", "t10"), "mixed": ("t9", "2026-11-02T10:20"), "missing": (None, "t10"),
    }[request.time_form]
    events = [{"event_id": "first", "at": first, "initiates": "ready"},
              {"event_id": "first" if request.duplicate_ids else "second", "at": second, "requires": "ready", "initiates": "done"}]
    if request.time_form == "missing":
        del events[0]["at"]
    rows = [{"event": "first", "before": "second"}]
    if request.rows == "none":
        rows = []
    elif request.rows == "false":
        rows = [{"event": "second", "before": "first"}]
    elif request.rows == "unknown":
        rows = [{"holds": "not_in_the_world", "at": second}]
    semantics = ["event"]
    if request.boundary != "none":
        semantics.append("numeric_dynamics" if request.boundary == "owned" else "geometry")
    return {"claim": {"claim_id": request.case_id, "requested_semantics": semantics, "asserts": rows}, "inputs": {"events": events}}


def _replay_observed_copy(contract, observed):
    from worldguard.contracts import GuardContract
    from worldguard.compare import compare_with_observed_copy

    world = GuardContract.from_dict(contract)
    original = deepcopy(world.to_dict())
    observation = deepcopy(observed)
    result, copied = compare_with_observed_copy(world, observed)
    expected = deepcopy(original)
    expected["inputs"]["events"][0]["at"] = observed["events"]["first"]
    assert copied == expected, "observedcopy_only_selected_event: another event/scenario/variable changed"
    assert world.to_dict() == original and observed == observation, "observed-copy inputs were mutated"
    assert all("id" in row for row in result["matches"] + result["mismatches"])
    copied["inputs"]["events"][0]["initiates"] = "independent-copy-proof"
    assert world.to_dict() == original, "observed copy shares nested input objects"


class ReplayReport:
    def __init__(self, checked, mismatches):
        self.checked = checked
        self.mismatches = tuple(mismatches)
        self.ok = not self.mismatches

    def format_text(self, max_examples=None):
        return "\n".join([f"conformance: {self.checked - len(self.mismatches)}/{self.checked} model inputs match the real code",
                          *["  mismatch: " + mismatch for mismatch in self.mismatches[:max_examples]]])


def worst(values):
    return next((s for s in ('FAIL','GAP','BOUNDARY_EXCEEDED','PASS') if s in values), 'PASS')


def replay(request, *, write_observed=False):
    """Call the native CLI afresh, retaining the original fixture witness assertions."""
    from worldguard.cli import main
    with tempfile.TemporaryDirectory(prefix='world-aspect-') as directory:
        root=Path(directory); path=root/'world.json'; contract=_real_contract(request)
        path.write_text(json.dumps(contract), encoding='utf-8'); output=io.StringIO()
        with redirect_stdout(output):
            if request.compare:
                observed={'events': {'first': 't10' if request.compare_mismatch else 't9.1'}, 'time_tolerance': .2}
                if request.observed_copy:
                    observed.update(events={'first':'t9.1'},variables={'distance':99})
                    _replay_observed_copy(contract, observed)
                observation=root/'observed.json';observation.write_text(json.dumps(observed))
                args=['compare','--contract',str(path),'--observed',str(observation)]
                if write_observed: args+=['--write-observed',str(root/'copy.json')]
            else: args=['check','--contract',str(path),'--json']
            code=main(args)
        report=json.loads(output.getvalue())
        return code, report


def witness_assertions(request, gaps):
    if request.token_event_mismatch:
        assert any(row['code']=='WORLD_EVENT_TOKEN_MISMATCH' for row in gaps), 'missing token/event contradiction witness'
    if request.space_token in {'disjoint','unrelated'}:
        code='WORLD_SPACE_TOKEN_MISMATCH' if request.space_token=='disjoint' else 'WORLD_SPACE_TOKEN_UNRELATED'
        assert any(row['code']==code for row in gaps), f'missing {code} witness'
    if request.transition_unlinked:
        gap=next(row for row in gaps if row['code']=='RESOURCE_TRANSITION_UNLINKED')
        assert gap['missing_slots']==['move'], 'unlinked transition identity was not preserved'
    if request.tokens_cloned:
        assert any(row['code']=='RESOURCE_UNIQUE_TOKEN_DUPLICATED' for row in gaps), 'the original clone contradiction disappeared'


def stage_values(request, code, report):
    """Classify actual native contributions, not numerical or temporal world details."""
    if code==2: return ('error','','','')
    codes={row['code'] for row in report.get('gaps',[])}
    event_fail={'EVENT_PRECONDITION_UNMET','NORM_VIOLATED_BY_EVENT','RESOURCE_UNIQUE_TOKEN_DUPLICATED','WORLD_EVENT_TOKEN_MISMATCH','WORLD_SPACE_TOKEN_MISMATCH'}
    event_gap={'EVENT_MISSING_INITIATION_AXIOM','RESOURCE_TRANSITION_UNLINKED','WORLD_SPACE_TOKEN_UNRELATED'}
    events=('FAIL' if codes & event_fail or request.scm_mode=='event_clock' and 'CAUSAL_CONSTRAINT_VIOLATED' in codes
            else 'GAP' if codes & event_gap else 'PASS')
    consistency=('FAIL' if request.scm_mode!='event_clock' and 'CAUSAL_CONSTRAINT_VIOLATED' in codes
                 else 'GAP' if 'CAUSAL_SCENARIO_UNEVALUABLE' in codes
                 else 'BOUNDARY_EXCEEDED' if 'EVENT_BOUNDARY_NUMERIC_DYNAMICS' in codes else 'PASS')
    statuses=[row['status'] for row in report.get('guard_results',[])]
    if codes & {'QUALIFICATION_SEMANTIC_UNMAPPED', 'EVENT_ACTOR_STATE_UNCHECKED'}: statuses.append('GAP')
    return ('PASS',events,consistency,worst(statuses))


def _terminal_check(state, applies, expected, message):
    if state.request is not None and state.status and applies(state.request) and state.status!=expected[1]:
        return InvariantResult.fail(message)
    return InvariantResult.pass_()


def replay_timeline(request):
    from worldguard.cli import main
    with tempfile.TemporaryDirectory(prefix='timeline-aspect-') as directory:
        path=Path(directory)/'world.json';contract=_real_contract(request);path.write_text(json.dumps(contract))
        stream=io.StringIO()
        with redirect_stdout(stream):main(['timeline','--contract',str(path),'--json'])
        view=json.loads(stream.getvalue())
        code,report=replay(request)
        shown={c for step in view['steps'] for c in step.get('problems',[])}
        shown|={row['code'] for row in view.get('claims',[]) if row.get('code')}
        shown|={row['code'] for row in view.get('problems',[])}
        expected={row['code'] for row in report['gaps']}
        assert shown==expected and len(view.get('claims',[]))==len(contract['claim']['asserts']), f'timeline_shows_every_problem: timeline shows {sorted(shown)}, check reports {sorted(expected)}'
