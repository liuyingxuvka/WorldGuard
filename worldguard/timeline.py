"""Read the same finite event, token and scalar state used by native checks."""
from __future__ import annotations

from collections.abc import Mapping

from .clock import event_time_values, time_kind
from .contracts import GuardContract
from .semantic import fluent_values, causal_scenario_values, event_replay, token_replay


def _tokens(marking):
    result = {}
    for (place, color), quantity in sorted(marking.items()):
        result.setdefault(place, {})[color] = quantity
    return result


def _event_ids(value):
    if isinstance(value, dict):
        own = {str(value["event_id"])} if value.get("event_id") else set()
        own.update(map(str, value.get("event_ids", [])))
        for key, child in value.items():
            if key != "trace":
                own.update(_event_ids(child))
        return own
    if isinstance(value, list):
        return set().union(*(_event_ids(child) for child in value)) if value else set()
    return set()


def _short(value):
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_short(child)}" for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return ",".join(_short(child) for child in value)
    return str(value)


def _limited(parts, limit=5):
    """At most five parts, then how many more."""
    shown = list(parts[:limit])
    if len(parts) > limit:
        shown.append(f"+{len(parts) - limit} more")
    return "; ".join(shown)


def _submodels(inputs):
    """One line of text per declared agent, space, conflict and norm sub-model."""
    result = {}
    beliefs = inputs.get("beliefs")
    if isinstance(beliefs, Mapping) and beliefs:
        parts = []
        for agent, record in beliefs.items():
            record = record if isinstance(record, Mapping) else {}
            intends = ",".join(map(str, record.get("intentions") or [])) or "-"
            believes = ",".join(map(str, record.get("beliefs") or [])) or "-"
            parts.append(f"{agent} intends {intends}; believes {believes}")
        result["agents"] = _limited(parts)
    relations = [row for row in inputs.get("spatial_relations") or [] if isinstance(row, Mapping)]
    if relations:
        parts = [f"{row.get('at')} {row.get('x')} {str(row.get('relation', '')).upper()} {row.get('y')}" for row in relations]
        result["space"] = _limited(parts)
    game = inputs.get("game_model")
    if isinstance(game, Mapping) and game:
        players = ",".join(map(str, game.get("players") or [])) or "-"
        actions = game.get("actions") if isinstance(game.get("actions"), Mapping) else {}
        moves = " ".join(f"{player}:{','.join(map(str, rows))}" for player, rows in actions.items())
        states = ",".join(map(str, game.get("states") or [])) or "-"
        result["conflict"] = f"players {players}; actions {moves or '-'}; states {states}"
    norms = [row for row in inputs.get("norms") or [] if isinstance(row, Mapping)]
    if norms:
        parts = [f"{row.get('actor')} {row.get('modality')} {row.get('action')}" for row in norms]
        result["norms"] = _limited(parts)
    return result


def _claims(contract, report, rows):
    """Each claim row with the result the native report gave it."""
    claim_id = contract.claim.claim_id or contract.contract_id
    binding = report.claim_binding if report is not None else {}
    assertions = binding.get("assertions", []) if isinstance(binding, Mapping) else []
    claims = []
    for row in assertions:
        status = str(row.get("status"))
        code = next((gap["code"] for gap in rows if gap.get("claim_row") == row.get("index")), None)
        if status != "PASS" and code is None:
            code = "CLAIM_ASSERTION_FALSE" if status == "FAIL" else "CLAIM_ASSERTION_UNRESOLVED"
        claims.append({"claim_id": claim_id, "row": row.get("index"), "assertion": _short(row.get("assertion", {})),
                       "status": status, **({"code": code} if status != "PASS" else {})})
    if report is not None and not assertions:
        claims.append({"claim_id": claim_id, "row": None, "status": "GAP", "code": "CLAIM_NOT_BOUND"})
    return claims


def timeline(contract, *, scenario=None, problems=(), report=None):
    """The world step by step, its claim rows, declared sub-models and every problem of the native report."""
    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(contract)
    if report is not None:
        problems = report.gaps
    problems = list(problems)
    placed = set()
    inputs = contract.inputs
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    declared = {str(event.get("scenario_id")) for event in events if event.get("scenario_id")}
    if scenario is not None and scenario not in declared:
        raise ValueError(f"timeline scenario {scenario!r} is not declared")
    scenario = scenario or ""
    applicable = [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]
    if any("at" not in event for event in applicable):
        raise ValueError("timeline needs an at time for each applicable event")
    initial = fluent_values(inputs.get("event_model", {}).get("initial_states", []))
    resources = inputs.get("resources", {})
    transitions = [row for row in resources.get("transitions", []) if isinstance(row, Mapping)]
    marking, _ = token_replay({**resources, "transitions": []}, validate=False)
    starting = [index for index, row in enumerate(problems)
                if row.get("counterexample", {}).get("event_id", "not-initial") is None]
    placed.update(starting)
    steps = [{"at": None, "event_id": None, "fluents": sorted(initial), "tokens": _tokens(marking)}]
    if starting:
        steps[0]["problems"] = sorted({problems[index]["code"] for index in starting})
    linked = any("event" in row for row in transitions)
    for event, _, after in event_replay(applicable, initial, scenario, skip_illegal=True):
        matches = [row for row in transitions if row.get("event") == event["event_id"]]
        if linked and matches:
            marking, _ = token_replay(resources, str(matches[-1]["id"]), validate=False, events=events)
        here = [index for index, row in enumerate(problems) if event["event_id"] in _event_ids(row)]
        placed.update(here)
        step = {"at": event["at"], "event_id": event["event_id"], "fluents": sorted(after),
                "tokens": _tokens(marking), "problems": sorted({problems[index]["code"] for index in here})}
        if event.get("source"):
            step["source"] = event["source"]
        steps.append(step)
    if not linked and transitions:
        marking, _ = token_replay(resources, validate=False, events=events)
        if not applicable:
            steps.append({"at": None, "event_id": None, "fluents": sorted(initial), "problems": []})
        steps[-1]["tokens"] = _tokens(marking)
    variables = causal_scenario_values(inputs.get("causal_model", {}), event_time_values(events))
    claims = _claims(contract, report, problems)
    placed.update(index for index, row in enumerate(problems) if row.get("claim_row") is not None)
    if any(row.get("code") == "CLAIM_NOT_BOUND" for row in claims):
        placed.update(index for index, row in enumerate(problems) if row.get("code") == "CLAIM_NOT_BOUND")
    rest = []
    for index, row in enumerate(problems):
        if index in placed:
            continue
        item = {"code": row.get("code"), "guard": row.get("guard") or "-",
                "evidence": row.get("message") or _short(row.get("counterexample", {}))}
        on_scenario = row.get("counterexample", {}).get("scenario_id")
        if on_scenario is not None and str(on_scenario) in variables:
            item["scenario"] = str(on_scenario)
        rest.append(item)
    return {"contract_id": contract.contract_id, "clock": time_kind(applicable[0]["at"]) if applicable else "none",
            "steps": steps, "variables": variables, "claims": claims, "submodels": _submodels(inputs), "problems": rest}


def render_timeline_text(view, *, label=None, full=False):
    """Render the native timeline without changing or recomputing its checks."""
    head = f"world {view['contract_id']} (clock: {view['clock']})"
    lines = [f"{label}: {head}" if label else head]
    for claim in view.get("claims", []):
        result = claim["status"] + (f" {claim['code']}" if claim.get("code") else "")
        if claim.get("row") is None:
            lines.append(f"claim {claim['claim_id']}: {result}")
        else:
            lines.append(
                f"claim {claim['claim_id']} row {claim['row']}: {claim['assertion']} {result}"
            )
    for name in ("agents", "space", "conflict", "norms"):
        if name in view.get("submodels", {}):
            lines.append(f"{name}: {view['submodels'][name]}")
    previous_fluents = set()
    previous_tokens = {}
    for index, step in enumerate(view["steps"]):
        current_fluents = set(step["fluents"])
        current_tokens = step.get("tokens", {})
        if full or index == 0:
            fluents = ", ".join(step["fluents"]) or "-"
            places = current_tokens
        else:
            fluents = (
                " ".join(
                    [f"+{name}" for name in sorted(current_fluents - previous_fluents)]
                    + [f"-{name}" for name in sorted(previous_fluents - current_fluents)]
                )
                or "="
            )
            current_nonzero = {
                place: {color: quantity for color, quantity in colors.items() if quantity != 0}
                for place, colors in current_tokens.items()
            }
            previous_nonzero = {
                place: {color: quantity for color, quantity in colors.items() if quantity != 0}
                for place, colors in previous_tokens.items()
            }
            places = {
                place: current_nonzero.get(place, {})
                for place in sorted(set(current_nonzero) | set(previous_nonzero))
                if current_nonzero.get(place, {}) != previous_nonzero.get(place, {})
            }
        tokens = ", ".join(
            f"{place}="
            + ("+".join(f"{color}×{quantity:g}" for color, quantity in colors.items()) or "-")
            for place, colors in places.items()
            if any(colors.values()) or (not full and index > 0)
        )
        tokens = tokens or ("-" if full or index == 0 else "=")
        line = (
            f"{step['at'] if step['at'] is not None else 'start'}  {step.get('event_id') or '-'}  "
            f"fluents: {fluents} | tokens: {tokens}"
        )
        previous_fluents = current_fluents
        previous_tokens = current_tokens
        if step.get("source"):
            line += f" (source: {step['source']})"
        if step.get("problems"):
            line += "  !! " + ", ".join(step["problems"])
        lines.append(line)
    problems = view.get("problems", [])
    for scenario, values in view.get("variables", {}).items():
        rendered = ", ".join(
            f"{name}={value:.3g}" if isinstance(value, (int, float)) else f"{name}={value}"
            for name, value in values.items()
        )
        line = f"variables [{scenario}]: {rendered}"
        codes = sorted({row["code"] for row in problems if row.get("scenario") == scenario})
        if codes:
            line += "  !! " + ", ".join(codes)
        lines.append(line)
    loose = [row for row in problems if "scenario" not in row]
    if loose:
        lines.append("problems:")
        lines.extend(f"  {row['code']} ({row['guard']}): {row['evidence']}" for row in loose)
    return "\n".join(lines)
