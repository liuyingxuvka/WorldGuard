"""Shared finite replay, clock, norm and scalar-equation helpers."""
from __future__ import annotations

import ast
import math
from typing import Any, Mapping

from .clock import time_key


NORM_MODALITIES = frozenset({"permitted", "obligatory", "forbidden", "prohibited"})


def _event_time_key(value: Any) -> float:
    """Delegate all event time ordering to the canonical clock owner."""
    return time_key(value)


def missing_bdi_fields(record: Mapping[str, Any]) -> list[str]:
    """Beliefs and desires must be non-empty; intentions must be present but may be empty."""
    missing = [name for name in ("beliefs", "desires") if not record.get(name)]
    if record.get("intentions") is None:
        missing.append("intentions")
    return missing


def event_replay(events: list[Any], initial_fluents: Any = (), scenario_id: str = ""):
    """Yield (event, fluents holding before it, fluents holding after it) for one scenario, in time order."""
    holding = frozenset(_fluent_values(initial_fluents))
    applicable = [
        event for event in events
        if isinstance(event, dict) and (not event.get("scenario_id") or str(event["scenario_id"]) == scenario_id)
    ]
    for event in sorted(applicable, key=lambda item: _event_time_key(item.get("at", ""))):
        ended = set(_fluent_values(event.get("terminates"))) | set(_fluent_values(event.get("releases")))
        after = frozenset((holding - ended) | set(_fluent_values(event.get("initiates"))))
        yield event, holding, after
        holding = after


def event_precondition_failures(events: list[Any], initial_fluents: Any = ()) -> list[dict[str, Any]]:
    """Return every event whose `requires` fluents do not hold when it happens."""
    scenario_ids = sorted({str(event["scenario_id"]) for event in events if isinstance(event, dict) and event.get("scenario_id")})
    failures: list[dict[str, Any]] = []
    for scenario_id in scenario_ids or [""]:
        applicable = [
            event for event in events
            if isinstance(event, dict) and (not event.get("scenario_id") or str(event["scenario_id"]) == scenario_id)
        ]
        if any("at" not in event for event in applicable):
            # Missing axioms prevent ordering only this scenario, including its shared events.
            continue
        for event, before, _ in event_replay(applicable, initial_fluents, scenario_id):
            missing = sorted(set(_fluent_values(event.get("requires"))) - before)
            if missing:
                row = {"event_id": event.get("event_id"), "at": event.get("at"), "missing_fluents": missing, "holding_fluents": sorted(before)}
                failures.append({**row, "scenario_id": scenario_id} if scenario_id else row)
    return failures


def norm_activity(norms: list[Any], facts: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return (active norms, norms whose condition fact is not declared) for boolean condition facts."""
    fact_values = {str(item["fact_id"]): item["value"] for item in facts if isinstance(item, dict) and item.get("fact_id")}
    missing = []
    active = []
    for index, norm in enumerate(norms):
        condition = norm.get("condition") if isinstance(norm, dict) else None
        needed = ""
        expected: bool | None = None
        if isinstance(condition, str) and condition:
            needed = condition
            expected = True
        elif isinstance(condition, dict):
            needed = str(condition.get("fact_id", ""))
            expected_value = condition.get("equals", condition.get("value", True))
            if isinstance(expected_value, bool):
                expected = expected_value
        if not needed or expected is None or needed not in fact_values:
            missing.append({"norm": index, "condition": condition, "needed_fact": needed or "condition fact"})
        elif fact_values[needed] is expected:
            active.append(norm)
    return active, missing


def active_norm_conflicts(norms: list[Any]) -> list[dict[str, Any]]:
    """Return (actor, action) groups whose active norms both forbid and permit/require it."""
    groups: dict[tuple[str, str], list[Any]] = {}
    for norm in norms:
        if isinstance(norm, dict):
            key = (str(norm.get("actor", "")), str(norm.get("action", "")))
            groups.setdefault(key, []).append(norm)
    conflicts = []
    for (actor, action), group in sorted(groups.items()):
        modalities = {str(norm.get("modality", "")) for norm in group}
        if modalities & {"forbidden", "prohibited"} and modalities & {"permitted", "obligatory"}:
            conflicts.append({"actor": actor, "action": action, "norms": group})
    return conflicts


def _string_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(key) for key in value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _fluent_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key, active in value.items() if active]
    return _string_values(value)


def _resolve_event_guard(value: Any, declared_values: Mapping[str, Any]) -> bool | None:
    """Evaluate the deliberately small current EventGuard predicate surface."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.lower() == "true":
            return True
        if normalized.lower() == "false":
            return False
        declared = declared_values.get(normalized)
        if isinstance(declared, bool):
            return declared
    return None


_RCC8 = {"DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPI", "NTPPI"}


_RCC8_CONVERSE = {
    "DC": "DC",
    "EC": "EC",
    "PO": "PO",
    "EQ": "EQ",
    "TPP": "TPPI",
    "NTPP": "NTPPI",
    "TPPI": "TPP",
    "NTPPI": "NTPP",
}


_ALLOWED_AST = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
)


def _equation_error(expression: Any, known_names: set[str]) -> str:
    if isinstance(expression, (int, float, bool)):
        return ""
    if not isinstance(expression, str) or not expression.strip():
        return "equation is empty or not a supported scalar expression"
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return "equation is not valid expression syntax"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            return f"unsupported expression node: {type(node).__name__}"
        if isinstance(node, ast.Name) and node.id not in known_names:
            return f"unknown variable: {node.id}"
    return ""


def _safe_scalar_eval(expression: Any, environment: dict[str, float]) -> float:
    if isinstance(expression, bool):
        return float(expression)
    if isinstance(expression, (int, float)):
        return float(expression)
    tree = ast.parse(str(expression), mode="eval")
    return float(eval(compile(tree, "<worldguard-causal>", "eval"), {"__builtins__": {}}, environment))


def _scenario_records(value: Any) -> dict[str, dict[str, float]]:
    records: dict[str, dict[str, float]] = {}
    if isinstance(value, dict):
        for scenario_id, raw in value.items():
            if isinstance(raw, dict):
                records[str(scenario_id)] = {
                    str(key): float(item) for key, item in raw.items()
                }
    return records


def _evaluate_equations(
    variables: list[str],
    equations: dict[str, Any],
    seed: dict[str, float],
    overrides: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[str]]:
    # Scenario assignments replace endogenous equations, and explicit do assignments take precedence.
    environment = dict(seed)
    overrides = {**{key: value for key, value in seed.items() if key in variables}, **dict(overrides or {})}
    environment.update(overrides)
    remaining = [variable for variable in variables if variable not in overrides]
    errors: list[str] = []
    for _ in range(max(1, len(remaining) + 1)):
        progressed = False
        for variable in list(remaining):
            try:
                environment[variable] = _safe_scalar_eval(equations[variable], environment)
            except (KeyError, NameError):
                continue
            except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
                errors.append(f"{variable}:{type(exc).__name__}")
                remaining.remove(variable)
            else:
                remaining.remove(variable)
                progressed = True
        if not remaining or not progressed:
            break
    errors.extend(f"{variable}:unresolved_dependencies" for variable in remaining)
    return environment, errors


_CONSTRAINT_AST = (*_ALLOWED_AST, ast.Compare, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


def _causal_runs(causal: Mapping[str, Any], variables: list[str], equations: dict[str, Any], event_times=None):
    """One finite execution owner shared by checks, constraints and claim rows."""
    seeds = {name: {key: {**(event_times or {}), **values} for key, values in _scenario_records(causal.get(name, {})).items()}
             for name in ("scenarios", "holdout_scenarios")}
    results: dict[str, dict[str, dict[str, float]]] = {"scenarios": {}, "holdout_scenarios": {}, "interventions": {}}
    errors: list[dict[str, Any]] = []
    for family in ("scenarios", "holdout_scenarios"):
        for scenario_id, seed in sorted(seeds[family].items()):
            values, row_errors = _evaluate_equations(variables, equations, seed)
            if row_errors:
                errors.append({"scenario_id": scenario_id, "errors": row_errors})
            else:
                results[family][scenario_id] = values
    all_seeds = {**seeds["scenarios"], **seeds["holdout_scenarios"]}
    for intervention in causal.get("interventions", []):
        intervention_id = str(intervention["intervention_id"])
        scenario_id = str(intervention["scenario_id"])
        if scenario_id not in all_seeds:
            errors.append({"intervention_id": intervention_id, "errors": ["scenario is unavailable"]})
            continue
        values, row_errors = _evaluate_equations(variables, equations, all_seeds[scenario_id],
            {str(key): float(value) for key, value in intervention["set"].items()})
        if row_errors:
            errors.append({"intervention_id": intervention_id, "errors": row_errors})
        else:
            results["interventions"][intervention_id] = values
    return results, errors


def causal_scenario_values(causal: Mapping[str, Any], event_times=None) -> dict[str, dict[str, float]]:
    """Return completed scenario, holdout and intervention runs; native checks retain errors."""
    variables = [str(item) for item in causal.get("variables", [])]
    equations = causal.get("equations", {}) if isinstance(causal.get("equations"), dict) else {}
    known = set(variables) | {str(item) for item in causal.get("exogenous", [])} | set(event_times or {})
    if not variables or any(variable not in equations or _equation_error(equations[variable], known) for variable in variables):
        return {}
    results, _errors = _causal_runs(causal, variables, equations, event_times)
    return {**results["scenarios"], **results["holdout_scenarios"], **results["interventions"]}


def causal_constraint_findings(causal: Mapping[str, Any], event_times=None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Check each `constraints` comparison in every evaluated scenario; return (violations, unevaluable)."""
    constraints = [str(item) for item in causal.get("constraints", []) or []]
    if not constraints:
        return [], []
    runs = causal_scenario_values(causal, event_times)
    if not runs:
        return [], [{"constraint": text, "error": "constraints need scalar equations and at least one scenario"} for text in constraints]
    known = {str(item) for item in causal.get("variables", [])} | {str(item) for item in causal.get("exogenous", [])} | set(event_times or {})
    violations: list[dict[str, Any]] = []
    unevaluable: list[dict[str, Any]] = []
    for text in constraints:
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            tree = None
        names = sorted({node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}) if tree else []
        if tree is None or not isinstance(tree.body, ast.Compare) or set(names) - known or any(
            not isinstance(node, _CONSTRAINT_AST)
            or (isinstance(node, ast.Constant) and (
                isinstance(node.value, bool)
                or not isinstance(node.value, (int, float))
                or (isinstance(node.value, float) and not math.isfinite(node.value))
            ))
            for node in ast.walk(tree)
        ):
            unevaluable.append({"constraint": text, "error": "a constraint compares declared variables and numbers, for example 'slack_h >= 0'"})
            continue
        check = compile(tree, "<worldguard-constraint>", "eval")
        for scenario_id, values in sorted(runs.items()):
            try:
                holds = eval(check, {"__builtins__": {}}, dict(values))
            except (NameError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
                unevaluable.append({"constraint": text, "scenario_id": scenario_id,
                                    "error": f"{type(exc).__name__}: {exc}"})
                continue
            if not holds:
                violations.append({"constraint": text, "scenario_id": scenario_id, "values": {name: values.get(name) for name in names}})
    return violations, unevaluable


def token_replay(resources: Mapping[str, Any], stop_after: str | None = None, *, validate: bool = True, events=()):
    """Replay one trace; Guards check enablement, assertions read its declared marking."""
    places = resources.get("places", {})
    marking: dict[tuple[str, str], float] = {}
    for place, tokens in places.items():
        if not isinstance(tokens, list):
            return marking, {"kind": "bad_token", "place": place, "tokens": tokens}
        for token in tokens:
            if not isinstance(token, dict) or not token.get("color") or not _quantity(token.get("qty")):
                return marking, {"kind": "bad_token", "place": place, "token": token}
            key = str(place), str(token["color"])
            marking[key] = marking.get(key, 0.0) + float(token["qty"])
    transitions = list(resources.get("transitions", []))
    event_map = {str(event.get("event_id")): event for event in events if not event.get("scenario_id")}
    if transitions and any("event" in transition for transition in transitions):
        if any("at" not in event_map[str(transition["event"])] for transition in transitions):
            return marking, {"kind": "bad_transition", "needed": "time for each linked event"}
        transitions.sort(key=lambda transition: time_key(event_map[str(transition["event"])]["at"]))
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict) or not transition.get("id"):
            return marking, {"kind": "bad_transition", "transition": transition}
        for arc in transition.get("consumes", []):
            if not isinstance(arc, dict) or arc.get("place") not in places or not arc.get("color") or not _quantity(arc.get("qty")):
                return marking, {"kind": "bad_transition", "transition": transition["id"], "arc": arc}
            key = str(arc["place"]), str(arc["color"])
            available = marking.get(key, 0.0)
            if validate and available < float(arc["qty"]):
                return marking, {"kind": "missing_initial" if index == 0 else "overspend",
                    "transition": transition["id"], "place": key[0], "color": key[1],
                    "required_qty": arc["qty"], "available_qty": available,
                    "marking": {str(key): value for key, value in marking.items()}}
            marking[key] = available - float(arc["qty"])
        for arc in transition.get("produces", []):
            if not isinstance(arc, dict) or not arc.get("place") or not arc.get("color") or not _quantity(arc.get("qty")):
                return marking, {"kind": "bad_transition", "transition": transition["id"], "arc": arc}
            key = str(arc["place"]), str(arc["color"])
            marking[key] = marking.get(key, 0.0) + float(arc["qty"])
            if validate and key[1] in resources.get("unique", []) and sum(qty for (_, color), qty in marking.items() if color == key[1]) > 1:
                return marking, {"kind": "duplicated", "transition": transition["id"],
                    "tokens": {key[1]: {place: qty for (place, color), qty in marking.items() if color == key[1]}}}
            capacity = resources.get("capacities", {}).get(arc["place"])
            total = sum(value for (place, _), value in marking.items() if place == str(arc["place"]))
            if validate and capacity is not None and total > float(capacity):
                return marking, {"kind": "capacity", "transition": transition["id"], "place_total": total, "capacity": capacity}
        if validate:
            duplicated = {color: {place: qty for (place, token), qty in marking.items() if token == color}
                          for color in resources.get("unique", [])
                          if sum(qty for (_, token), qty in marking.items() if token == color) > 1}
            if duplicated:
                return marking, {"kind": "duplicated", "transition": transition["id"], "tokens": duplicated}
            if "event" in transition:
                event = event_map[str(transition["event"])]
                participants = {event.get("actor"), *event.get("with", [])}
                moved = {arc.get("color") for key in ("consumes", "produces") for arc in transition.get(key, [])}
                unnamed = sorted((moved & set(resources.get("unique", []))) - participants)
                if unnamed:
                    return marking, {"kind": "participant", "transition": transition["id"], "event_id": event["event_id"], "colors": unnamed}
        if stop_after is not None and str(transition["id"]) == str(stop_after):
            break
    return marking, None


def _quantity(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
