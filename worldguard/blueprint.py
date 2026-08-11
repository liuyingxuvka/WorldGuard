from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
import hashlib
import json
import math
import re
from typing import Any

from .contracts import GuardContract
from .blueprint_census import (
    ExternalObjectCensusError,
    validate_external_object_census_record,
    validate_external_object_census_source,
)
from .guard_model_contract import (
    GuardCandidatePurposeError,
    verify_guard_candidate_purpose_contract,
)
from .guards import GUARD_RUNNERS
from .io import load_mapping
from .semantic import EXECUTOR_REGISTRY, SemanticStatus, fingerprint_mesh
from .status import GuardStatus, aggregate_statuses


WORLD_BLUEPRINT_SCHEMA_VERSION = "worldguard.world_blueprint.v1"
WORLD_ELEMENT_KINDS = frozenset(
    {
        "entity",
        "property",
        "relation",
        "event",
        "state",
        "transition",
        "resource",
        "causal_link",
        "agent",
        "conflict",
        "norm",
    }
)
WORLD_DEPENDENCY_RELATIONS = frozenset(
    {
        "depends_on",
        "caused_by",
        "constrained_by",
        "consumes",
        "precedes",
        "governed_by",
        "conflicts_with",
    }
)
PORT_CARDINALITIES = frozenset({"one", "optional", "many"})
BINDING_ROLES = frozenset(
    {"target_material", "evidence", "test_check", "native_result"}
)
TARGET_SEMANTIC_SUPPORT_MODES = frozenset({"direct", "derived"})
FRESHNESS_STATES = frozenset({"current", "stale", "unknown"})
INTERFACE_DISPOSITIONS = frozenset(
    {"parent_input", "parent_output", "internal_terminal"}
)
CONTRIBUTION_KINDS = frozenset({"child_output", "owned_element_output"})
CHILD_INPUT_SOURCE_KINDS = frozenset(
    {"parent_input", "sibling_output", "parent_element_output"}
)
ELEMENT_INPUT_SOURCE_KINDS = frozenset({"node_input", "dependency_output"})
BINDING_OBSERVATION_MODES = frozenset(
    {"local_content", "provider_content", "external_identity"}
)
BEHAVIOR_COMMITMENT_INPUT_KINDS = frozenset(
    {
        "request_contract",
        "target_material",
        "target_object_census_source",
        "target_semantic_authority",
        "target_object_census_authority",
        "openspec",
        "spark",
        "changelog",
    }
)
BEHAVIOR_COMMITMENT_INPUT_MODES = frozenset(
    {"local_content", "external_identity"}
)
NATIVE_SEMANTIC_FIELDS: dict[str, frozenset[str]] = {
    "entity": frozenset({"identity"}),
    "property": frozenset({"subject_id", "property_name", "value"}),
    "relation": frozenset({"relation", "participant_ids"}),
    "event": frozenset({"at", "terminates", "initiates", "releases"}),
    "state": frozenset({"state_id", "initial", "terminal"}),
    "transition": frozenset(
        {
            "source_state",
            "target_state",
            "source_initial",
            "target_terminal",
            "guard",
            "guard_value",
            "effect",
        }
    ),
    "resource": frozenset({"resource_id", "quantity", "unit"}),
    "causal_link": frozenset(
        {"cause_ids", "effect_id", "mechanism", "mechanism_claim_scope"}
    ),
    "agent": frozenset(
        {
            "agent_id",
            "beliefs",
            "desires",
            "intentions",
            "conflicting_intentions",
        }
    ),
    "conflict": frozenset(
        {
            "participant_ids",
            "issue",
            "actions",
            "resolution_states",
            "transitions",
            "payoffs",
        }
    ),
    "norm": frozenset(
        {"modality", "subject_id", "action", "condition", "facts"}
    ),
}
CAUSAL_MECHANISM_CLAIM_SCOPES = frozenset({"graph_only", "mechanism_truth"})
NATIVE_SEMANTIC_FIELD_DISPOSITIONS: dict[str, dict[str, str]] = {
    "entity": {"identity": "not_applicable"},
    "property": {
        "subject_id": "not_applicable",
        "property_name": "not_applicable",
        "value": "not_applicable",
    },
    "relation": {
        "relation": "conditional_owner_input",
        "participant_ids": "conditional_owner_input",
    },
    "event": {
        "at": "owner_input",
        "terminates": "owner_input",
        "initiates": "owner_input",
        "releases": "owner_input",
    },
    "state": {
        "state_id": "owner_input",
        "initial": "owner_input_with_unverified_semantics",
        "terminal": "owner_input_with_unverified_semantics",
    },
    "transition": {
        "source_state": "owner_input",
        "target_state": "owner_input",
        "source_initial": "owner_input",
        "target_terminal": "owner_input",
        "guard": "owner_input_with_unverified_semantics",
        "guard_value": "owner_input",
        "effect": "owner_input_with_unverified_semantics",
    },
    "resource": {
        "resource_id": "owner_input",
        "quantity": "owner_input",
        "unit": "owner_input",
    },
    "causal_link": {
        "cause_ids": "owner_input",
        "effect_id": "owner_input",
        "mechanism": "unverified_boundary",
        "mechanism_claim_scope": "request_control",
    },
    "agent": {
        "agent_id": "owner_input",
        "beliefs": "owner_input_with_unverified_semantics",
        "desires": "owner_input_with_unverified_semantics",
        "intentions": "owner_input_with_unverified_semantics",
        "conflicting_intentions": "owner_input",
    },
    "conflict": {
        "participant_ids": "owner_input",
        "issue": "owner_input_with_unverified_semantics",
        "actions": "owner_input",
        "resolution_states": "owner_input",
        "transitions": "owner_input",
        "payoffs": "owner_input",
    },
    "norm": {
        "modality": "owner_input",
        "subject_id": "owner_input",
        "action": "owner_input",
        "condition": "owner_input_with_unverified_semantics",
        "facts": "owner_input_with_unverified_semantics",
    },
}

_NATIVE_SEMANTIC_OWNER_INPUT_PATHS: dict[str, dict[str, str]] = {
    "relation": {
        "relation": "inputs.spatial_relations[0].relation",
        "participant_ids": "inputs.spatial_relations[0].x/y",
    },
    "event": {
        "at": "inputs.events[0].at",
        "terminates": "inputs.events[0].terminates",
        "initiates": "inputs.events[0].initiates",
        "releases": "inputs.events[0].releases",
    },
    "state": {
        field_name: f"inputs.event_model.states[0].{field_name}"
        for field_name in ("state_id", "initial", "terminal")
    },
    "transition": {
        field_name: f"inputs.event_model.transitions[0].{field_name}"
        for field_name in ("source_state", "target_state", "guard", "effect")
    }
    | {
        "source_initial": "inputs.event_model.states[source_state].initial",
        "target_terminal": "inputs.event_model.states[target_state].terminal",
        "guard_value": "inputs.event_model.guard_values[guard]",
    },
    "resource": {
        field_name: f"inputs.resources.inventory[0].{field_name}"
        for field_name in ("resource_id", "quantity", "unit")
    },
    "causal_link": {
        "cause_ids": "inputs.causal_model.graph[*][0]",
        "effect_id": "inputs.causal_model.graph[*][1]",
    },
    "agent": {
        "agent_id": "inputs.beliefs.<agent_id>.agent_id",
        "beliefs": "inputs.beliefs.<agent_id>.beliefs",
        "desires": "inputs.beliefs.<agent_id>.desires",
        "intentions": "inputs.beliefs.<agent_id>.intentions",
        "conflicting_intentions": "inputs.agent_model.conflicting_intentions",
    },
    "conflict": {
        "participant_ids": "inputs.game_model.players",
        "issue": "inputs.game_model.issue",
        "actions": "inputs.game_model.actions",
        "resolution_states": "inputs.game_model.states",
        "transitions": "inputs.game_model.transitions",
        "payoffs": "inputs.game_model.payoffs",
    },
    "norm": {
        "modality": "inputs.norms[0].modality",
        "subject_id": "inputs.norms[0].subject_id",
        "action": "inputs.norms[0].action",
        "condition": "inputs.norms[0].condition",
        "facts": "inputs.facts",
    },
}

_NATIVE_SEMANTIC_EVALUATED_CLAIM_SCOPES = {
    "event": "declared_event_fluent_consistency",
    "state": "declared_state_flag_integrity",
    "transition": "declared_transition_identity_and_field_completeness",
    "resource": "declared_inventory_non_negative_validity",
    "causal_link": "graph_only",
    "agent": "declared_bdi_completeness_and_intention_conflict",
    "conflict": "declared_finite_game_completeness_and_probability",
    "norm": "declared_norm_modality_and_condition_fact_binding",
    "relation": "declared_rcc8_base_consistency",
}

_NATIVE_SEMANTIC_UNVERIFIED_FIELD_SCOPES: dict[str, dict[str, str]] = {
    "state": {
        "initial": "actual_initial_state_truth",
        "terminal": "terminal_state_reachability",
    },
    "transition": {
        "guard": "guard_expression_truth",
        "effect": "effect_execution_truth",
    },
    "agent": {
        "beliefs": "belief_truth",
        "desires": "desire_truth",
        "intentions": "intention_execution_truth",
    },
    "conflict": {"issue": "issue_factual_truth_or_resolution"},
    "norm": {
        "condition": "condition_truth",
        "facts": "external_fact_truth",
    },
}


def _assert_native_semantic_field_dispositions_complete() -> None:
    if set(NATIVE_SEMANTIC_FIELD_DISPOSITIONS) != set(NATIVE_SEMANTIC_FIELDS):
        raise RuntimeError("Native semantic kinds and field dispositions differ.")
    for kind, fields in NATIVE_SEMANTIC_FIELDS.items():
        dispositions = NATIVE_SEMANTIC_FIELD_DISPOSITIONS[kind]
        if set(dispositions) != set(fields):
            raise RuntimeError(
                f"Native semantic field dispositions are incomplete for {kind}."
            )


_assert_native_semantic_field_dispositions_complete()


def _native_semantic_field_errors(kind: str, fields: Mapping[str, Any]) -> list[str]:
    """Return exact typed-field violations for one native WorldGuard object."""

    errors: list[str] = []

    def require_text(name: str) -> None:
        value = fields.get(name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{name}:non_empty_string_required")

    def require_text_list(name: str, *, minimum: int = 1) -> None:
        value = fields.get(name)
        if (
            not isinstance(value, list)
            or len(value) < minimum
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            errors.append(f"{name}:non_empty_string_list_required")

    def require_mapping_list(name: str, *, minimum: int = 1) -> list[Mapping[str, Any]]:
        value = fields.get(name)
        if (
            not isinstance(value, list)
            or len(value) < minimum
            or any(not isinstance(item, Mapping) for item in value)
        ):
            errors.append(f"{name}:mapping_list_required")
            return []
        return list(value)

    if kind == "entity":
        require_text("identity")
    elif kind == "property":
        require_text("subject_id")
        require_text("property_name")
        value = fields.get("value")
        if value is None or isinstance(value, (dict, list)):
            errors.append("value:scalar_required")
    elif kind == "relation":
        require_text("relation")
        require_text_list("participant_ids", minimum=2)
        relation = fields.get("relation")
        participants = fields.get("participant_ids")
        if (
            isinstance(relation, str)
            and relation.upper() in _BLUEPRINT_RCC8
            and isinstance(participants, list)
            and len(participants) != 2
        ):
            errors.append("participant_ids:exactly_two_required_for_rcc8")
    elif kind == "event":
        require_text("at")
        require_text_list("terminates", minimum=0)
        require_text_list("initiates", minimum=0)
        require_text_list("releases", minimum=0)
        terminates = fields.get("terminates")
        initiates = fields.get("initiates")
        releases = fields.get("releases")
        if terminates == [] and initiates == [] and releases == []:
            errors.append("event_axiom:at_least_one_fluent_required")
    elif kind == "state":
        require_text("state_id")
        for field_name in ("initial", "terminal"):
            if not isinstance(fields.get(field_name), bool):
                errors.append(f"{field_name}:boolean_required")
    elif kind == "transition":
        for field_name in ("source_state", "target_state", "guard", "effect"):
            require_text(field_name)
        for field_name in ("source_initial", "target_terminal", "guard_value"):
            if not isinstance(fields.get(field_name), bool):
                errors.append(f"{field_name}:boolean_required")
    elif kind == "resource":
        require_text("resource_id")
        quantity = fields.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            errors.append("quantity:number_required")
        elif not math.isfinite(float(quantity)) or float(quantity) < 0:
            errors.append("quantity:finite_non_negative_required")
        require_text("unit")
    elif kind == "causal_link":
        require_text_list("cause_ids")
        require_text("effect_id")
        require_text("mechanism")
        require_text("mechanism_claim_scope")
        scope = fields.get("mechanism_claim_scope")
        if isinstance(scope, str) and scope not in CAUSAL_MECHANISM_CLAIM_SCOPES:
            errors.append("mechanism_claim_scope:unsupported_scope")
    elif kind == "agent":
        require_text("agent_id")
        for field_name in ("beliefs", "desires", "intentions"):
            require_text_list(field_name)
        require_text_list("conflicting_intentions", minimum=0)
    elif kind == "conflict":
        require_text_list("participant_ids", minimum=2)
        require_text("issue")
        require_text_list("actions")
        require_text_list("resolution_states")
        transitions = require_mapping_list("transitions")
        payoffs = require_mapping_list("payoffs")
        for index, transition in enumerate(transitions):
            unknown = sorted(
                set(transition).difference({"from", "to", "probabilities"})
            )
            if unknown:
                errors.append(
                    f"transitions[{index}]:unknown_fields:{','.join(unknown)}"
                )
            for field_name in ("from", "to"):
                value = transition.get(field_name)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"transitions[{index}].{field_name}:non_empty_string_required"
                    )
            probabilities = transition.get("probabilities")
            if (
                not isinstance(probabilities, list)
                or not probabilities
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or float(value) < 0
                    for value in probabilities
                )
            ):
                errors.append(
                    f"transitions[{index}].probabilities:finite_non_negative_number_list_required"
                )
        for index, payoff in enumerate(payoffs):
            unknown = sorted(set(payoff).difference({"player", "state", "value"}))
            if unknown:
                errors.append(f"payoffs[{index}]:unknown_fields:{','.join(unknown)}")
            for field_name in ("player", "state"):
                value = payoff.get(field_name)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"payoffs[{index}].{field_name}:non_empty_string_required"
                    )
            value = payoff.get("value")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                errors.append(f"payoffs[{index}].value:finite_number_required")
    elif kind == "norm":
        for field_name in ("modality", "subject_id", "action", "condition"):
            require_text(field_name)
        facts = require_mapping_list("facts")
        for index, fact in enumerate(facts):
            unknown = sorted(set(fact).difference({"fact_id", "value"}))
            if unknown:
                errors.append(f"facts[{index}]:unknown_fields:{','.join(unknown)}")
            fact_id = fact.get("fact_id")
            if not isinstance(fact_id, str) or not fact_id.strip():
                errors.append(f"facts[{index}].fact_id:non_empty_string_required")
            if not isinstance(fact.get("value"), bool):
                errors.append(f"facts[{index}].value:boolean_required")
    return sorted(errors)


class BlueprintLayerStatus(StrEnum):
    PROVEN = "proven"
    GAP = "gap"
    BOUNDARY = "boundary"
    NOT_RUN = "not_run"


class BlueprintError(ValueError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


BEHAVIOR_CASE_KINDS = frozenset(
    {"known_good", "known_bad", "admission_bad"}
)
STATE_EFFECT_DISPOSITIONS = frozenset({"applicable", "not_applicable", "unverified"})


@dataclass(frozen=True)
class BehaviorCaseContract:
    """One source-independent target behavior/oracle row.

    The row is intentionally language-neutral.  Purpose proof consumes the
    input/oracle fields; blueprint qualification also preserves the explicit
    state/effect expectation so a passing output cannot hide a state mismatch.
    """

    case_id: str
    case_kind: str
    text: str
    inputs: dict[str, Any]
    pre_state: dict[str, Any]
    expected_output: dict[str, Any]
    post_state: dict[str, Any]
    effects: dict[str, Any]
    state_effect_disposition: str
    state_effect_reason: str
    oracle_id: str
    claim_boundary: str
    coverage_context: dict[str, Any] = field(default_factory=dict)
    failure_id: str = ""
    blocked_claim: str = ""
    expected_guard_status: str = ""
    expected_semantic_status: str = ""
    expected_status: str = ""
    expected_code: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, owner: str) -> "BehaviorCaseContract":
        _unknown_fields(
            data,
            {
                "case_id",
                "case_kind",
                "text",
                "inputs",
                "coverage_context",
                "pre_state",
                "expected_output",
                "post_state",
                "effects",
                "state_effect_disposition",
                "state_effect_reason",
                "failure_id",
                "blocked_claim",
                "expected_guard_status",
                "expected_semantic_status",
                "expected_status",
                "expected_code",
                "oracle_id",
                "claim_boundary",
            },
            owner,
        )
        case_kind = _required_text(data.get("case_kind"), f"{owner}.case_kind")
        if case_kind not in BEHAVIOR_CASE_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BEHAVIOR_CASE_KIND_UNKNOWN",
                f"{owner} uses an unknown behavior-case kind.",
                details={"owner": owner, "case_kind": case_kind},
            )
        disposition = _required_text(
            data.get("state_effect_disposition"),
            f"{owner}.state_effect_disposition",
        )
        if disposition not in STATE_EFFECT_DISPOSITIONS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BEHAVIOR_STATE_EFFECT_DISPOSITION_UNKNOWN",
                f"{owner} uses an unknown state/effect disposition.",
                details={"owner": owner, "disposition": disposition},
            )
        mappings: dict[str, dict[str, Any]] = {}
        for field_id in (
            "inputs",
            "coverage_context",
            "pre_state",
            "expected_output",
            "post_state",
            "effects",
        ):
            value = data.get(field_id, {})
            if not isinstance(value, Mapping):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_CASE_FIELD_INVALID",
                    f"{owner}.{field_id} must be an object.",
                    details={"owner": owner, "field_id": field_id},
                )
            mappings[field_id] = dict(value)
        if disposition != "applicable" and not str(
            data.get("state_effect_reason", "")
        ).strip():
            raise BlueprintError(
                "WORLD_BLUEPRINT_BEHAVIOR_STATE_EFFECT_REASON_MISSING",
                f"{owner} must explain a non-applicable or unverified state/effect boundary.",
                details={"owner": owner, "disposition": disposition},
            )
        if case_kind == "known_good":
            if (
                data.get("expected_guard_status") != "PASS"
                or data.get("expected_semantic_status") != "PASS"
                or data.get("failure_id")
                or data.get("expected_status")
                or data.get("expected_code")
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_GOOD_ORACLE_INVALID",
                    f"{owner} known-good oracle must require structural and semantic PASS only.",
                    details={"owner": owner},
                )
        elif case_kind == "known_bad":
            for field_id in (
                "failure_id",
                "blocked_claim",
                "expected_status",
                "expected_code",
            ):
                _required_text(data.get(field_id), f"{owner}.{field_id}")
            if data.get("expected_guard_status") or data.get("expected_semantic_status"):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_BAD_ORACLE_INVALID",
                    f"{owner} known-bad oracle must use expected_status/expected_code.",
                    details={"owner": owner},
                )
        else:
            for field_id in (
                "failure_id",
                "blocked_claim",
                "expected_status",
                "expected_code",
            ):
                _required_text(data.get(field_id), f"{owner}.{field_id}")
            if data.get("expected_status") != "REJECTED":
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_ORACLE_INVALID",
                    f"{owner} admission-bad oracle must require REJECTED.",
                    details={"owner": owner},
                )
            if data.get("expected_guard_status") or data.get(
                "expected_semantic_status"
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_ORACLE_INVALID",
                    f"{owner} admission-bad oracle cannot claim Guard execution.",
                    details={"owner": owner},
                )
            candidate = mappings["inputs"].get("world_element")
            if (
                set(mappings["inputs"]) != {"world_element"}
                or not isinstance(candidate, Mapping)
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_INPUT_INVALID",
                    f"{owner} admission-bad case requires one exact world_element input.",
                    details={"owner": owner},
                )
            if not mappings["expected_output"]:
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_DETAILS_MISSING",
                    f"{owner} admission-bad oracle requires an error-detail subset.",
                    details={"owner": owner},
                )
            if not str(data.get("oracle_id", "")).startswith(
                "oracle:worldguard:WorldBlueprintAdmission:"
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_ORACLE_INVALID",
                    f"{owner} admission-bad case requires the parser-owned oracle.",
                    details={"owner": owner},
                )
            if not str(data.get("failure_id", "")).startswith(
                "failure:world-blueprint:admission:"
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_FAILURE_INVALID",
                    f"{owner} admission-bad case requires a parser-owned failure id.",
                    details={"owner": owner},
                )
            if (
                disposition != "not_applicable"
                or mappings["pre_state"]
                or mappings["post_state"]
                or mappings["effects"]
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_STATE_INVALID",
                    f"{owner} admission-bad case cannot claim state execution.",
                    details={"owner": owner},
                )
        return cls(
            case_id=_required_text(data.get("case_id"), f"{owner}.case_id"),
            case_kind=case_kind,
            text=_required_text(data.get("text"), f"{owner}.text"),
            inputs=mappings["inputs"],
            coverage_context=mappings["coverage_context"],
            pre_state=mappings["pre_state"],
            expected_output=mappings["expected_output"],
            post_state=mappings["post_state"],
            effects=mappings["effects"],
            state_effect_disposition=disposition,
            state_effect_reason=str(data.get("state_effect_reason", "")).strip(),
            failure_id=str(data.get("failure_id", "")).strip(),
            blocked_claim=str(data.get("blocked_claim", "")).strip(),
            expected_guard_status=str(data.get("expected_guard_status", "")).strip(),
            expected_semantic_status=str(data.get("expected_semantic_status", "")).strip(),
            expected_status=str(data.get("expected_status", "")).strip(),
            expected_code=str(data.get("expected_code", "")).strip(),
            oracle_id=_required_text(data.get("oracle_id"), f"{owner}.oracle_id"),
            claim_boundary=_required_text(
                data.get("claim_boundary"), f"{owner}.claim_boundary"
            ),
        )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_kind": self.case_kind,
            "text": self.text,
            "inputs": self.inputs,
            "coverage_context": self.coverage_context,
            "pre_state": self.pre_state,
            "expected_output": self.expected_output,
            "post_state": self.post_state,
            "effects": self.effects,
            "state_effect_disposition": self.state_effect_disposition,
            "state_effect_reason": self.state_effect_reason,
            "failure_id": self.failure_id,
            "blocked_claim": self.blocked_claim,
            "expected_guard_status": self.expected_guard_status,
            "expected_semantic_status": self.expected_semantic_status,
            "expected_status": self.expected_status,
            "expected_code": self.expected_code,
            "oracle_id": self.oracle_id,
            "claim_boundary": self.claim_boundary,
        }

    @property
    def input_fingerprint(self) -> str:
        return "sha256:" + fingerprint_mesh(
            {
                "inputs": self.inputs,
                "coverage_context": self.coverage_context,
                "pre_state": self.pre_state,
            }
        )

    @property
    def case_fingerprint(self) -> str:
        return "sha256:" + fingerprint_mesh(self.fingerprint_payload())

    def to_dict(self) -> dict[str, Any]:
        return self.fingerprint_payload()


@dataclass(frozen=True)
class BlueprintTaskPurpose:
    declaration_id: str
    purpose: str
    boundary: str
    selected_failure_ids: tuple[str, ...]
    behavior_cases: tuple[BehaviorCaseContract, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, owner: str) -> "BlueprintTaskPurpose":
        _unknown_fields(
            data,
            {
                "declaration_id",
                "purpose",
                "boundary",
                "selected_failure_ids",
                "behavior_cases",
            },
            owner,
        )
        selected = tuple(str(value) for value in data.get("selected_failure_ids", []))
        if not selected or len(selected) != len(set(selected)) or any(not value for value in selected):
            raise BlueprintError(
                "WORLD_BLUEPRINT_TASK_PURPOSE_FAILURES_INVALID",
                f"{owner} requires one or more unique protected failure ids.",
                details={"owner": owner, "selected_failure_ids": list(selected)},
            )
        cases = tuple(
            sorted(
                (
                    BehaviorCaseContract.from_dict(
                        row, owner=f"{owner} behavior case"
                    )
                    for row in data.get("behavior_cases", [])
                ),
                key=lambda row: row.case_id,
            )
        )
        if len({row.case_id for row in cases}) != len(cases):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BEHAVIOR_CASE_ID_DUPLICATE",
                f"{owner} contains duplicate behavior-case ids.",
                details={"owner": owner},
            )
        good = [row for row in cases if row.case_kind == "known_good"]
        bad_by_failure: dict[str, list[BehaviorCaseContract]] = {
            failure_id: [] for failure_id in selected
        }
        extras: list[str] = []
        for row in cases:
            if row.case_kind != "known_bad":
                continue
            if row.failure_id not in bad_by_failure:
                extras.append(row.failure_id)
            else:
                bad_by_failure[row.failure_id].append(row)
        if len(good) != 1 or extras or any(len(rows) != 1 for rows in bad_by_failure.values()):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BEHAVIOR_CASE_CARDINALITY_INVALID",
                f"{owner} requires one known-good and one known-bad per selected failure.",
                details={
                    "owner": owner,
                    "known_good_count": len(good),
                    "known_bad_counts": {
                        key: len(value) for key, value in bad_by_failure.items()
                    },
                    "extra_failure_ids": extras,
                },
            )
        return cls(
            declaration_id=_required_text(
                data.get("declaration_id"), f"{owner}.declaration_id"
            ),
            purpose=_required_text(data.get("purpose"), f"{owner}.purpose"),
            boundary=_required_text(data.get("boundary"), f"{owner}.boundary"),
            selected_failure_ids=selected,
            behavior_cases=cases,
        )

    @property
    def purpose_fingerprint(self) -> str:
        return "sha256:" + fingerprint_mesh(self.fingerprint_payload())

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "declaration_id": self.declaration_id,
            "purpose": self.purpose,
            "boundary": self.boundary,
            "selected_failure_ids": list(self.selected_failure_ids),
            "behavior_cases": [row.to_dict() for row in self.behavior_cases],
        }

    def to_dict(self) -> dict[str, Any]:
        return self.fingerprint_payload()

    def to_guard_declaration(
        self,
        *,
        guard: str,
        task_contract_id: str,
        run_id: str,
        model_instance_id: str,
    ) -> dict[str, Any]:
        good = next(row for row in self.behavior_cases if row.case_kind == "known_good")
        bad = [row for row in self.behavior_cases if row.case_kind == "known_bad"]
        return {
            "schema_version": "worldguard.task_guard_purpose.v1",
            "declaration_id": self.declaration_id,
            "task_contract_id": task_contract_id,
            "run_id": run_id,
            "model_instance_id": model_instance_id,
            "guard": guard,
            "purpose": self.purpose,
            "boundary": self.boundary,
            "selected_failure_ids": list(self.selected_failure_ids),
            "known_good": {
                "case_id": good.case_id,
                "text": good.text,
                "inputs": good.inputs,
                "coverage_context": good.coverage_context,
                "expected_guard_status": good.expected_guard_status,
                "expected_semantic_status": good.expected_semantic_status,
                "native_oracle_id": good.oracle_id,
            },
            "known_bad_cases": [
                {
                    "case_id": row.case_id,
                    "failure_id": row.failure_id,
                    "blocked_claim": row.blocked_claim,
                    "text": row.text,
                    "inputs": row.inputs,
                    "coverage_context": row.coverage_context,
                    "expected_status": row.expected_status,
                    "expected_code": row.expected_code,
                    "native_oracle_id": row.oracle_id,
                }
                for row in bad
            ],
            "declaration_sequence": 1,
        }


def _unknown_fields(data: Mapping[str, Any], allowed: set[str], owner: str) -> None:
    unknown = sorted(set(data).difference(allowed))
    if unknown:
        raise BlueprintError(
            "WORLD_BLUEPRINT_UNKNOWN_FIELD",
            f"{owner} contains unknown fields: " + ", ".join(unknown),
            details={"owner": owner, "unknown_fields": unknown},
        )


def _required_text(value: Any, field_id: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise BlueprintError(
            "WORLD_BLUEPRINT_REQUIRED_FIELD_MISSING",
            f"WorldBlueprint requires {field_id}.",
            details={"field_id": field_id},
        )
    return result


def _required_sha256(value: Any, field_id: str) -> str:
    result = _required_text(value, field_id)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", result) is None:
        raise BlueprintError(
            "WORLD_BLUEPRINT_FINGERPRINT_INVALID",
            f"{field_id} requires canonical sha256 lowercase hex.",
            details={"field_id": field_id, "observed": result},
        )
    return result


def _normalized_trust_fingerprints(
    values: Iterable[str], field_id: str
) -> tuple[str, ...]:
    """Normalize one explicit caller trust set and reject non-current identities."""

    return tuple(
        sorted(
            {
                _required_sha256(value, field_id)
                for value in values
                if str(value).strip()
            }
        )
    )


@dataclass(frozen=True)
class TypedPort:
    port_id: str
    value_type: str
    schema_id: str
    schema_version: str
    refines: tuple[str, ...] = ()
    cardinality: str = "one"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, owner: str) -> "TypedPort":
        _unknown_fields(
            data,
            {
                "port_id",
                "value_type",
                "schema_id",
                "schema_version",
                "refines",
                "cardinality",
            },
            owner,
        )
        cardinality = str(data.get("cardinality", "one")).strip()
        if cardinality not in PORT_CARDINALITIES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_PORT_CARDINALITY_UNKNOWN",
                f"{owner} uses unknown cardinality {cardinality}.",
                details={"owner": owner, "cardinality": cardinality},
            )
        return cls(
            port_id=_required_text(data.get("port_id"), f"{owner}.port_id"),
            value_type=_required_text(
                data.get("value_type"), f"{owner}.value_type"
            ),
            schema_id=_required_text(data.get("schema_id"), f"{owner}.schema_id"),
            schema_version=_required_text(
                data.get("schema_version"), f"{owner}.schema_version"
            ),
            refines=tuple(
                sorted(
                    _required_text(value, f"{owner}.refines")
                    for value in data.get("refines", [])
                )
            ),
            cardinality=cardinality,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "value_type": self.value_type,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "refines": list(self.refines),
            "cardinality": self.cardinality,
        }

    @property
    def schema_identity(self) -> str:
        return f"{self.schema_id}@{self.schema_version}"


def _port_compatibility(source: TypedPort, target: TypedPort) -> dict[str, Any]:
    """Return one deterministic schema/cardinality compatibility proof."""

    if source.cardinality != target.cardinality:
        relation = "incompatible"
        reason = "cardinality_mismatch"
    elif source.schema_identity == target.schema_identity:
        relation = "exact"
        reason = "exact_schema_identity"
    elif target.schema_identity in source.refines:
        relation = "refines"
        reason = "source_declares_target_refinement"
    else:
        relation = "incompatible"
        reason = "schema_identity_unrelated"
    payload = {
        "schema_version": "worldguard.port_compatibility.v1",
        "source_port_id": source.port_id,
        "source_schema_id": source.schema_id,
        "source_schema_version": source.schema_version,
        "source_refines": list(source.refines),
        "target_port_id": target.port_id,
        "target_schema_id": target.schema_id,
        "target_schema_version": target.schema_version,
        "source_cardinality": source.cardinality,
        "target_cardinality": target.cardinality,
        "compatibility_relation": relation,
        "reason": reason,
    }
    return {**payload, "proof_fingerprint": "sha256:" + fingerprint_mesh(payload)}


@dataclass(frozen=True)
class NativeSemanticRef:
    semantic_id: str
    element_kind: str
    native_object_id: str
    native_schema_id: str
    provider_id: str
    provider_version: str
    observation_binding_id: str
    semantic_fields: dict[str, Any]
    content_fingerprint: str
    claim_boundary: str
    task_purpose: BlueprintTaskPurpose | None = None

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        element_id: str,
        expected_kind: str,
    ) -> "NativeSemanticRef":
        _unknown_fields(
            data,
            {
                "semantic_id",
                "element_kind",
                "native_object_id",
                "native_schema_id",
                "provider_id",
                "provider_version",
                "observation_binding_id",
                "semantic_fields",
                "content_fingerprint",
                "claim_boundary",
                "task_purpose",
            },
            f"element {element_id} native semantic",
        )
        observed_kind = _required_text(
            data.get("element_kind"),
            f"element {element_id}.native_semantic.element_kind",
        )
        if observed_kind != expected_kind:
            raise BlueprintError(
                "WORLD_BLUEPRINT_NATIVE_SEMANTIC_KIND_MISMATCH",
                f"Element {element_id} native semantic kind does not match its element kind.",
                details={"expected": expected_kind, "observed": observed_kind},
            )
        fields_value = data.get("semantic_fields")
        if not isinstance(fields_value, Mapping):
            raise BlueprintError(
                "WORLD_BLUEPRINT_NATIVE_SEMANTIC_FIELDS_INVALID",
                f"Element {element_id} requires typed native semantic fields.",
                details={"element_id": element_id},
            )
        fields = dict(fields_value)
        expected_fields = NATIVE_SEMANTIC_FIELDS[expected_kind]
        missing = sorted(expected_fields.difference(fields))
        unknown = sorted(set(fields).difference(expected_fields))
        empty = sorted(
            key
            for key, value in fields.items()
            if value is None or (isinstance(value, str) and not value.strip())
        )
        type_errors = _native_semantic_field_errors(expected_kind, fields)
        if missing or unknown or empty or type_errors:
            raise BlueprintError(
                "WORLD_BLUEPRINT_NATIVE_SEMANTIC_FIELDS_INVALID",
                f"Element {element_id} native semantic fields do not match the {expected_kind} contract.",
                details={
                    "element_id": element_id,
                    "missing_fields": missing,
                    "unknown_fields": unknown,
                    "empty_fields": empty,
                    "type_errors": type_errors,
                },
            )
        semantic_id = _required_text(
            data.get("semantic_id"),
            f"element {element_id}.native_semantic.semantic_id",
        )
        expected_semantic_id = f"semantic:{element_id}"
        if semantic_id != expected_semantic_id:
            raise BlueprintError(
                "WORLD_BLUEPRINT_NATIVE_SEMANTIC_ID_MISMATCH",
                f"Element {element_id} must own its exact native semantic id.",
                details={"expected": expected_semantic_id, "observed": semantic_id},
            )
        native_schema_id = _required_text(
            data.get("native_schema_id"),
            f"element {element_id}.native_semantic.native_schema_id",
        )
        expected_schema_id = f"worldguard.native.{expected_kind}.v1"
        if native_schema_id != expected_schema_id:
            raise BlueprintError(
                "WORLD_BLUEPRINT_NATIVE_SCHEMA_MISMATCH",
                f"Element {element_id} uses a non-current native semantic schema.",
                details={"expected": expected_schema_id, "observed": native_schema_id},
            )
        task_purpose_value = data.get("task_purpose")
        task_purpose = (
            BlueprintTaskPurpose.from_dict(
                task_purpose_value,
                owner=f"element {element_id} native semantic task purpose",
            )
            if isinstance(task_purpose_value, Mapping)
            else None
        )
        identity = {
            "semantic_id": semantic_id,
            "element_kind": observed_kind,
            "native_object_id": _required_text(
                data.get("native_object_id"),
                f"element {element_id}.native_semantic.native_object_id",
            ),
            "native_schema_id": native_schema_id,
            "provider_id": _required_text(
                data.get("provider_id"),
                f"element {element_id}.native_semantic.provider_id",
            ),
            "provider_version": _required_text(
                data.get("provider_version"),
                f"element {element_id}.native_semantic.provider_version",
            ),
            "observation_binding_id": _required_text(
                data.get("observation_binding_id"),
                f"element {element_id}.native_semantic.observation_binding_id",
            ),
            "semantic_fields": fields,
            "claim_boundary": _required_text(
                data.get("claim_boundary"),
                f"element {element_id}.native_semantic.claim_boundary",
            ),
            "task_purpose": task_purpose,
        }
        fingerprint_identity = {
            key: value for key, value in identity.items() if key != "task_purpose"
        }
        expected_fingerprint = "sha256:" + fingerprint_mesh(fingerprint_identity)
        observed_fingerprint = _required_text(
            data.get("content_fingerprint"),
            f"element {element_id}.native_semantic.content_fingerprint",
        )
        if observed_fingerprint != expected_fingerprint:
            raise BlueprintError(
                "WORLD_BLUEPRINT_NATIVE_SEMANTIC_FINGERPRINT_INVALID",
                f"Element {element_id} native semantic fingerprint does not match its typed content.",
                details={
                    "element_id": element_id,
                    "expected": expected_fingerprint,
                    "observed": observed_fingerprint,
                },
            )
        return cls(content_fingerprint=observed_fingerprint, **identity)

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "semantic_id": self.semantic_id,
            "element_kind": self.element_kind,
            "native_object_id": self.native_object_id,
            "native_schema_id": self.native_schema_id,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "observation_binding_id": self.observation_binding_id,
            "semantic_fields": self.semantic_fields,
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = {
            **self.fingerprint_payload(),
            "content_fingerprint": self.content_fingerprint,
        }
        if self.task_purpose is not None:
            payload["task_purpose"] = self.task_purpose.to_dict()
        return payload


@dataclass(frozen=True)
class ElementDependency:
    dependency_id: str
    relation: str
    depends_on_element_id: str

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "ElementDependency":
        _unknown_fields(
            data,
            {"dependency_id", "relation", "depends_on_element_id"},
            owner,
        )
        relation = str(data.get("relation", "")).strip()
        if relation not in WORLD_DEPENDENCY_RELATIONS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_RELATION_UNKNOWN",
                f"{owner} uses unknown dependency relation {relation or '<missing>'}.",
                details={"owner": owner, "relation": relation},
            )
        return cls(
            dependency_id=_required_text(
                data.get("dependency_id"), f"{owner}.dependency_id"
            ),
            relation=relation,
            depends_on_element_id=_required_text(
                data.get("depends_on_element_id"),
                f"{owner}.depends_on_element_id",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "relation": self.relation,
            "depends_on_element_id": self.depends_on_element_id,
        }


@dataclass(frozen=True)
class ElementOutputTerminal:
    output_port_id: str
    reason: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, owner: str) -> "ElementOutputTerminal":
        _unknown_fields(data, {"output_port_id", "reason"}, owner)
        return cls(
            output_port_id=_required_text(
                data.get("output_port_id"), f"{owner}.output_port_id"
            ),
            reason=_required_text(data.get("reason"), f"{owner}.reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_port_id": self.output_port_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class WorldElement:
    element_id: str
    kind: str
    owner_node_id: str
    dependencies: tuple[ElementDependency, ...] = ()
    input_ports: tuple[TypedPort, ...] = ()
    output_ports: tuple[TypedPort, ...] = ()
    internal_terminal_outputs: tuple[ElementOutputTerminal, ...] = ()
    native_semantic: NativeSemanticRef | None = None
    contributes_to_claim: bool = False
    required_binding_roles: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorldElement":
        _unknown_fields(
            data,
            {
                "element_id",
                "kind",
                "owner_node_id",
                "dependencies",
                "input_ports",
                "output_ports",
                "internal_terminal_outputs",
                "native_semantic",
                "contributes_to_claim",
                "required_binding_roles",
            },
            "world element",
        )
        element_id = _required_text(data.get("element_id"), "element.element_id")
        kind = str(data.get("kind", "")).strip()
        if kind not in WORLD_ELEMENT_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_ELEMENT_KIND_UNKNOWN",
                f"World element {element_id} uses unknown kind {kind or '<missing>'}.",
                details={"element_id": element_id, "kind": kind},
            )
        roles = tuple(sorted(str(value) for value in data.get("required_binding_roles", [])))
        unknown_roles = sorted(set(roles).difference(BINDING_ROLES))
        if unknown_roles:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BINDING_ROLE_UNKNOWN",
                f"World element {element_id} uses unknown binding roles.",
                details={"element_id": element_id, "roles": unknown_roles},
            )
        return cls(
            element_id=element_id,
            kind=kind,
            owner_node_id=_required_text(
                data.get("owner_node_id"), f"element {element_id}.owner_node_id"
            ),
            dependencies=tuple(
                sorted(
                    (
                        ElementDependency.from_dict(
                            row, owner=f"element {element_id} dependency"
                        )
                        for row in data.get("dependencies", [])
                    ),
                    key=lambda row: row.dependency_id,
                )
            ),
            input_ports=tuple(
                sorted(
                    (
                        TypedPort.from_dict(
                            row, owner=f"element {element_id} input port"
                        )
                        for row in data.get("input_ports", [])
                    ),
                    key=lambda row: row.port_id,
                )
            ),
            output_ports=tuple(
                sorted(
                    (
                        TypedPort.from_dict(
                            row, owner=f"element {element_id} output port"
                        )
                        for row in data.get("output_ports", [])
                    ),
                    key=lambda row: row.port_id,
                )
            ),
            internal_terminal_outputs=tuple(
                sorted(
                    (
                        ElementOutputTerminal.from_dict(
                            row,
                            owner=f"element {element_id} internal terminal output",
                        )
                        for row in data.get("internal_terminal_outputs", [])
                    ),
                    key=lambda row: row.output_port_id,
                )
            ),
            native_semantic=NativeSemanticRef.from_dict(
                data.get("native_semantic", {}),
                element_id=element_id,
                expected_kind=kind,
            ),
            contributes_to_claim=bool(data.get("contributes_to_claim", False)),
            required_binding_roles=roles,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "kind": self.kind,
            "owner_node_id": self.owner_node_id,
            "dependencies": [item.to_dict() for item in self.dependencies],
            "input_ports": [item.to_dict() for item in self.input_ports],
            "output_ports": [item.to_dict() for item in self.output_ports],
            "internal_terminal_outputs": [
                item.to_dict() for item in self.internal_terminal_outputs
            ],
            "native_semantic": (
                self.native_semantic.to_dict() if self.native_semantic is not None else None
            ),
            "contributes_to_claim": self.contributes_to_claim,
            "required_binding_roles": list(self.required_binding_roles),
        }


@dataclass(frozen=True)
class ChildOutputMapping:
    mapping_id: str
    child_node_id: str
    child_output_port_id: str
    disposition: str
    parent_port_id: str = ""
    reason: str = ""

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "ChildOutputMapping":
        _unknown_fields(
            data,
            {
                "mapping_id",
                "child_node_id",
                "child_output_port_id",
                "disposition",
                "parent_port_id",
                "reason",
            },
            owner,
        )
        disposition = str(data.get("disposition", "")).strip()
        if disposition not in INTERFACE_DISPOSITIONS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_INTERFACE_DISPOSITION_UNKNOWN",
                f"{owner} uses unknown disposition {disposition or '<missing>'}.",
                details={"owner": owner, "disposition": disposition},
            )
        return cls(
            mapping_id=_required_text(data.get("mapping_id"), f"{owner}.mapping_id"),
            child_node_id=_required_text(
                data.get("child_node_id"), f"{owner}.child_node_id"
            ),
            child_output_port_id=_required_text(
                data.get("child_output_port_id"),
                f"{owner}.child_output_port_id",
            ),
            disposition=disposition,
            parent_port_id=str(data.get("parent_port_id", "")).strip(),
            reason=str(data.get("reason", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "child_node_id": self.child_node_id,
            "child_output_port_id": self.child_output_port_id,
            "disposition": self.disposition,
            "parent_port_id": self.parent_port_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ChildInputMapping:
    mapping_id: str
    child_node_id: str
    child_input_port_id: str
    source_kind: str
    source_id: str
    source_port_id: str

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "ChildInputMapping":
        _unknown_fields(
            data,
            {
                "mapping_id",
                "child_node_id",
                "child_input_port_id",
                "source_kind",
                "source_id",
                "source_port_id",
            },
            owner,
        )
        source_kind = str(data.get("source_kind", "")).strip()
        if source_kind not in CHILD_INPUT_SOURCE_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_CHILD_INPUT_SOURCE_KIND_UNKNOWN",
                f"{owner} uses unknown child-input source kind {source_kind or '<missing>'}.",
                details={"owner": owner, "source_kind": source_kind},
            )
        return cls(
            mapping_id=_required_text(data.get("mapping_id"), f"{owner}.mapping_id"),
            child_node_id=_required_text(
                data.get("child_node_id"), f"{owner}.child_node_id"
            ),
            child_input_port_id=_required_text(
                data.get("child_input_port_id"),
                f"{owner}.child_input_port_id",
            ),
            source_kind=source_kind,
            source_id=_required_text(data.get("source_id"), f"{owner}.source_id"),
            source_port_id=_required_text(
                data.get("source_port_id"), f"{owner}.source_port_id"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "child_node_id": self.child_node_id,
            "child_input_port_id": self.child_input_port_id,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_port_id": self.source_port_id,
        }


@dataclass(frozen=True)
class ElementInputMapping:
    mapping_id: str
    element_id: str
    element_input_port_id: str
    source_kind: str
    source_id: str
    source_port_id: str

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "ElementInputMapping":
        _unknown_fields(
            data,
            {
                "mapping_id",
                "element_id",
                "element_input_port_id",
                "source_kind",
                "source_id",
                "source_port_id",
            },
            owner,
        )
        source_kind = str(data.get("source_kind", "")).strip()
        if source_kind not in ELEMENT_INPUT_SOURCE_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_ELEMENT_INPUT_SOURCE_KIND_UNKNOWN",
                f"{owner} uses unknown element-input source kind {source_kind or '<missing>'}.",
                details={"owner": owner, "source_kind": source_kind},
            )
        return cls(
            mapping_id=_required_text(data.get("mapping_id"), f"{owner}.mapping_id"),
            element_id=_required_text(
                data.get("element_id"), f"{owner}.element_id"
            ),
            element_input_port_id=_required_text(
                data.get("element_input_port_id"),
                f"{owner}.element_input_port_id",
            ),
            source_kind=source_kind,
            source_id=_required_text(data.get("source_id"), f"{owner}.source_id"),
            source_port_id=_required_text(
                data.get("source_port_id"), f"{owner}.source_port_id"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "element_id": self.element_id,
            "element_input_port_id": self.element_input_port_id,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_port_id": self.source_port_id,
        }


@dataclass(frozen=True)
class OutputContribution:
    source_kind: str
    source_id: str
    source_port_id: str

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "OutputContribution":
        _unknown_fields(data, {"source_kind", "source_id", "source_port_id"}, owner)
        source_kind = str(data.get("source_kind", "")).strip()
        if source_kind not in CONTRIBUTION_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_CONTRIBUTION_KIND_UNKNOWN",
                f"{owner} uses unknown contribution kind {source_kind or '<missing>'}.",
                details={"owner": owner, "source_kind": source_kind},
            )
        return cls(
            source_kind=source_kind,
            source_id=_required_text(data.get("source_id"), f"{owner}.source_id"),
            source_port_id=_required_text(
                data.get("source_port_id"), f"{owner}.source_port_id"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_port_id": self.source_port_id,
        }


@dataclass(frozen=True)
class ParentOutputDerivation:
    derivation_id: str
    parent_output_port_id: str
    sources: tuple[OutputContribution, ...]

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "ParentOutputDerivation":
        _unknown_fields(
            data, {"derivation_id", "parent_output_port_id", "sources"}, owner
        )
        sources = tuple(
            sorted(
                (
                    OutputContribution.from_dict(row, owner=f"{owner} source")
                    for row in data.get("sources", [])
                ),
                key=lambda row: (row.source_kind, row.source_id, row.source_port_id),
            )
        )
        return cls(
            derivation_id=_required_text(
                data.get("derivation_id"), f"{owner}.derivation_id"
            ),
            parent_output_port_id=_required_text(
                data.get("parent_output_port_id"),
                f"{owner}.parent_output_port_id",
            ),
            sources=sources,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "derivation_id": self.derivation_id,
            "parent_output_port_id": self.parent_output_port_id,
            "sources": [item.to_dict() for item in self.sources],
        }


@dataclass(frozen=True)
class WorldBlueprintNode:
    node_id: str
    title: str
    depth: int
    parent_node_id: str = ""
    child_node_ids: tuple[str, ...] = ()
    owned_element_ids: tuple[str, ...] = ()
    input_ports: tuple[TypedPort, ...] = ()
    output_ports: tuple[TypedPort, ...] = ()
    child_input_mappings: tuple[ChildInputMapping, ...] = ()
    element_input_mappings: tuple[ElementInputMapping, ...] = ()
    child_output_mappings: tuple[ChildOutputMapping, ...] = ()
    output_derivations: tuple[ParentOutputDerivation, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorldBlueprintNode":
        _unknown_fields(
            data,
            {
                "node_id",
                "title",
                "depth",
                "parent_node_id",
                "child_node_ids",
                "owned_element_ids",
                "input_ports",
                "output_ports",
                "child_input_mappings",
                "element_input_mappings",
                "child_output_mappings",
                "output_derivations",
            },
            "world blueprint node",
        )
        node_id = _required_text(data.get("node_id"), "node.node_id")
        depth_value = data.get("depth")
        if isinstance(depth_value, bool) or not isinstance(depth_value, int) or depth_value < 0:
            raise BlueprintError(
                "WORLD_BLUEPRINT_DEPTH_INVALID",
                f"Node {node_id} requires a non-negative integer depth.",
                details={"node_id": node_id, "depth": depth_value},
            )
        return cls(
            node_id=node_id,
            title=_required_text(data.get("title"), f"node {node_id}.title"),
            depth=depth_value,
            parent_node_id=str(data.get("parent_node_id", "")).strip(),
            child_node_ids=tuple(sorted(str(value) for value in data.get("child_node_ids", []))),
            owned_element_ids=tuple(sorted(str(value) for value in data.get("owned_element_ids", []))),
            input_ports=tuple(
                sorted(
                    (
                        TypedPort.from_dict(row, owner=f"node {node_id} input port")
                        for row in data.get("input_ports", [])
                    ),
                    key=lambda row: row.port_id,
                )
            ),
            output_ports=tuple(
                sorted(
                    (
                        TypedPort.from_dict(row, owner=f"node {node_id} output port")
                        for row in data.get("output_ports", [])
                    ),
                    key=lambda row: row.port_id,
                )
            ),
            child_input_mappings=tuple(
                sorted(
                    (
                        ChildInputMapping.from_dict(
                            row, owner=f"node {node_id} child input mapping"
                        )
                        for row in data.get("child_input_mappings", [])
                    ),
                    key=lambda row: row.mapping_id,
                )
            ),
            element_input_mappings=tuple(
                sorted(
                    (
                        ElementInputMapping.from_dict(
                            row, owner=f"node {node_id} element input mapping"
                        )
                        for row in data.get("element_input_mappings", [])
                    ),
                    key=lambda row: row.mapping_id,
                )
            ),
            child_output_mappings=tuple(
                sorted(
                    (
                        ChildOutputMapping.from_dict(
                            row, owner=f"node {node_id} child output mapping"
                        )
                        for row in data.get("child_output_mappings", [])
                    ),
                    key=lambda row: row.mapping_id,
                )
            ),
            output_derivations=tuple(
                sorted(
                    (
                        ParentOutputDerivation.from_dict(
                            row, owner=f"node {node_id} output derivation"
                        )
                        for row in data.get("output_derivations", [])
                    ),
                    key=lambda row: row.derivation_id,
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "depth": self.depth,
            "parent_node_id": self.parent_node_id,
            "child_node_ids": list(self.child_node_ids),
            "owned_element_ids": list(self.owned_element_ids),
            "input_ports": [item.to_dict() for item in self.input_ports],
            "output_ports": [item.to_dict() for item in self.output_ports],
            "child_input_mappings": [
                item.to_dict() for item in self.child_input_mappings
            ],
            "element_input_mappings": [
                item.to_dict() for item in self.element_input_mappings
            ],
            "child_output_mappings": [
                item.to_dict() for item in self.child_output_mappings
            ],
            "output_derivations": [item.to_dict() for item in self.output_derivations],
        }


@dataclass(frozen=True)
class BlueprintBinding:
    binding_id: str
    role: str
    subject_element_id: str
    resource_id: str
    owner: str
    locator: str
    provider_id: str
    provider_version: str
    provider_capability_id: str
    observation_mode: str
    target_id: str
    target_revision: str
    freshness_status: str
    content_fingerprint: str
    receipt_fingerprint: str
    claim_boundary: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlueprintBinding":
        _unknown_fields(
            data,
            {
                "binding_id",
                "role",
                "subject_element_id",
                "resource_id",
                "owner",
                "locator",
                "provider_id",
                "provider_version",
                "provider_capability_id",
                "observation_mode",
                "target_id",
                "target_revision",
                "freshness_status",
                "content_fingerprint",
                "receipt_fingerprint",
                "claim_boundary",
            },
            "world blueprint binding",
        )
        binding_id = _required_text(data.get("binding_id"), "binding.binding_id")
        role = str(data.get("role", "")).strip()
        if role not in BINDING_ROLES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BINDING_ROLE_UNKNOWN",
                f"Binding {binding_id} uses unknown role {role or '<missing>'}.",
                details={"binding_id": binding_id, "role": role},
            )
        freshness = str(data.get("freshness_status", "")).strip()
        if freshness not in FRESHNESS_STATES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_FRESHNESS_UNKNOWN",
                f"Binding {binding_id} uses unknown freshness {freshness or '<missing>'}.",
                details={"binding_id": binding_id, "freshness_status": freshness},
            )
        content_fingerprint = _required_text(
            data.get("content_fingerprint"),
            f"binding {binding_id}.content_fingerprint",
        )
        if re.fullmatch(r"sha256:[0-9a-f]{64}", content_fingerprint) is None:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BINDING_FINGERPRINT_INVALID",
                f"Binding {binding_id} requires canonical sha256:lowercase-hex identity.",
                details={
                    "binding_id": binding_id,
                    "content_fingerprint": content_fingerprint,
                },
            )
        receipt_fingerprint = _required_text(
            data.get("receipt_fingerprint"),
            f"binding {binding_id}.receipt_fingerprint",
        )
        if re.fullmatch(r"sha256:[0-9a-f]{64}", receipt_fingerprint) is None:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BINDING_RECEIPT_FINGERPRINT_INVALID",
                f"Binding {binding_id} requires a canonical observation receipt fingerprint.",
                details={
                    "binding_id": binding_id,
                    "receipt_fingerprint": receipt_fingerprint,
                },
            )
        observation_mode = str(data.get("observation_mode", "")).strip()
        if observation_mode not in BINDING_OBSERVATION_MODES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BINDING_OBSERVATION_MODE_UNKNOWN",
                f"Binding {binding_id} uses an unknown observation mode.",
                details={"binding_id": binding_id, "observation_mode": observation_mode},
            )
        return cls(
            binding_id=binding_id,
            role=role,
            subject_element_id=_required_text(
                data.get("subject_element_id"),
                f"binding {binding_id}.subject_element_id",
            ),
            resource_id=_required_text(
                data.get("resource_id"), f"binding {binding_id}.resource_id"
            ),
            owner=_required_text(data.get("owner"), f"binding {binding_id}.owner"),
            locator=_required_text(
                data.get("locator"), f"binding {binding_id}.locator"
            ),
            provider_id=_required_text(
                data.get("provider_id"), f"binding {binding_id}.provider_id"
            ),
            provider_version=_required_text(
                data.get("provider_version"),
                f"binding {binding_id}.provider_version",
            ),
            provider_capability_id=_required_text(
                data.get("provider_capability_id"),
                f"binding {binding_id}.provider_capability_id",
            ),
            observation_mode=observation_mode,
            target_id=_required_text(
                data.get("target_id"), f"binding {binding_id}.target_id"
            ),
            target_revision=_required_text(
                data.get("target_revision"),
                f"binding {binding_id}.target_revision",
            ),
            freshness_status=freshness,
            content_fingerprint=content_fingerprint,
            receipt_fingerprint=receipt_fingerprint,
            claim_boundary=_required_text(
                data.get("claim_boundary"),
                f"binding {binding_id}.claim_boundary",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "role": self.role,
            "subject_element_id": self.subject_element_id,
            "resource_id": self.resource_id,
            "owner": self.owner,
            "locator": self.locator,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "provider_capability_id": self.provider_capability_id,
            "observation_mode": self.observation_mode,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "freshness_status": self.freshness_status,
            "content_fingerprint": self.content_fingerprint,
            "receipt_fingerprint": self.receipt_fingerprint,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class DeclaredBlueprintGap:
    gap_id: str
    gap_kind: str
    code: str
    message: str
    disposition: str
    affected_claim_boundary: str
    node_id: str = ""
    element_id: str = ""
    port_id: str = ""
    required_role: str = ""
    expected_owner: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeclaredBlueprintGap":
        _unknown_fields(
            data,
            {
                "gap_id",
                "gap_kind",
                "code",
                "message",
                "disposition",
                "affected_claim_boundary",
                "node_id",
                "element_id",
                "port_id",
                "required_role",
                "expected_owner",
            },
            "declared blueprint gap",
        )
        disposition = str(data.get("disposition", "gap")).strip()
        if disposition not in {"gap", "boundary"}:
            raise BlueprintError(
                "WORLD_BLUEPRINT_GAP_DISPOSITION_UNKNOWN",
                "Declared blueprint gaps must use gap or boundary disposition.",
                details={"disposition": disposition},
            )
        required_role = str(data.get("required_role", "")).strip()
        if required_role and required_role not in BINDING_ROLES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BINDING_ROLE_UNKNOWN",
                f"Declared gap names unknown role {required_role}.",
                details={"required_role": required_role},
            )
        return cls(
            gap_id=_required_text(data.get("gap_id"), "declared_gap.gap_id"),
            gap_kind=_required_text(data.get("gap_kind"), "declared_gap.gap_kind"),
            code=_required_text(data.get("code"), "declared_gap.code"),
            message=_required_text(data.get("message"), "declared_gap.message"),
            disposition=disposition,
            affected_claim_boundary=_required_text(
                data.get("affected_claim_boundary"),
                "declared_gap.affected_claim_boundary",
            ),
            node_id=str(data.get("node_id", "")).strip(),
            element_id=str(data.get("element_id", "")).strip(),
            port_id=str(data.get("port_id", "")).strip(),
            required_role=required_role,
            expected_owner=str(data.get("expected_owner", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "gap_kind": self.gap_kind,
            "code": self.code,
            "message": self.message,
            "disposition": self.disposition,
            "affected_claim_boundary": self.affected_claim_boundary,
            "node_id": self.node_id,
            "element_id": self.element_id,
            "port_id": self.port_id,
            "required_role": self.required_role,
            "expected_owner": self.expected_owner,
        }


@dataclass(frozen=True)
class DeclaredBlueprintInput:
    input_id: str
    node_id: str
    port_id: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeclaredBlueprintInput":
        _unknown_fields(
            data,
            {"input_id", "node_id", "port_id"},
            "declared blueprint input",
        )
        return cls(
            input_id=_required_text(data.get("input_id"), "declared_input.input_id"),
            node_id=_required_text(data.get("node_id"), "declared_input.node_id"),
            port_id=_required_text(data.get("port_id"), "declared_input.port_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "node_id": self.node_id,
            "port_id": self.port_id,
        }


@dataclass(frozen=True)
class BlueprintOutputRef:
    output_id: str
    node_id: str
    port_id: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlueprintOutputRef":
        _unknown_fields(
            data,
            {"output_id", "node_id", "port_id"},
            "declared blueprint output",
        )
        return cls(
            output_id=_required_text(
                data.get("output_id"), "declared_output.output_id"
            ),
            node_id=_required_text(data.get("node_id"), "declared_output.node_id"),
            port_id=_required_text(data.get("port_id"), "declared_output.port_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_id": self.output_id,
            "node_id": self.node_id,
            "port_id": self.port_id,
        }


@dataclass(frozen=True)
class BehaviorCommitmentInputRef:
    input_id: str
    input_kind: str
    observation_mode: str
    locator: str
    target_id: str
    target_revision: str
    content_fingerprint: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BehaviorCommitmentInputRef":
        if not isinstance(data, Mapping):
            raise BlueprintError(
                "WORLD_BLUEPRINT_COMMITMENT_INPUT_INVALID",
                "Behavior commitment input refs must be exact typed objects.",
            )
        _unknown_fields(
            data,
            {
                "input_id",
                "input_kind",
                "observation_mode",
                "locator",
                "target_id",
                "target_revision",
                "content_fingerprint",
            },
            "behavior commitment adapter input",
        )
        input_kind = _required_text(
            data.get("input_kind"), "commitment_inventory.input_refs.input_kind"
        )
        if input_kind not in BEHAVIOR_COMMITMENT_INPUT_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_COMMITMENT_INPUT_KIND_UNKNOWN",
                "Behavior commitment adapter input uses an unknown source kind.",
                details={"input_kind": input_kind},
            )
        observation_mode = _required_text(
            data.get("observation_mode"),
            "commitment_inventory.input_refs.observation_mode",
        )
        if observation_mode not in BEHAVIOR_COMMITMENT_INPUT_MODES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_COMMITMENT_INPUT_MODE_UNKNOWN",
                "Behavior commitment adapter input uses an unknown observation mode.",
                details={"observation_mode": observation_mode},
            )
        return cls(
            input_id=_required_text(
                data.get("input_id"), "commitment_inventory.input_refs.input_id"
            ),
            input_kind=input_kind,
            observation_mode=observation_mode,
            locator=_required_text(
                data.get("locator"), "commitment_inventory.input_refs.locator"
            ),
            target_id=_required_text(
                data.get("target_id"), "commitment_inventory.input_refs.target_id"
            ),
            target_revision=_required_text(
                data.get("target_revision"),
                "commitment_inventory.input_refs.target_revision",
            ),
            content_fingerprint=_required_sha256(
                data.get("content_fingerprint"),
                "commitment_inventory.input_refs.content_fingerprint",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "input_kind": self.input_kind,
            "observation_mode": self.observation_mode,
            "locator": self.locator,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "content_fingerprint": self.content_fingerprint,
        }


@dataclass(frozen=True)
class BehaviorCommitmentInventoryRef:
    inventory_id: str
    authority_owner_id: str
    locator: str
    adapter_id: str
    adapter_version: str
    adapter_capability_id: str
    target_id: str
    target_revision: str
    input_refs: tuple[BehaviorCommitmentInputRef, ...]
    claim_boundary: str

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> "BehaviorCommitmentInventoryRef":
        _unknown_fields(
            data,
            {
                "inventory_id",
                "authority_owner_id",
                "locator",
                "adapter_id",
                "adapter_version",
                "adapter_capability_id",
                "target_id",
                "target_revision",
                "input_refs",
                "claim_boundary",
            },
            "behavior commitment inventory reference",
        )
        input_refs = tuple(
            sorted(
                (
                    BehaviorCommitmentInputRef.from_dict(value)
                    for value in data.get("input_refs", [])
                ),
                key=lambda row: row.input_id,
            )
        )
        if not input_refs:
            raise BlueprintError(
                "WORLD_BLUEPRINT_COMMITMENT_INPUTS_MISSING",
                "Behavior commitment inventory requires at least one independent request or target-material input.",
            )
        return cls(
            inventory_id=_required_text(
                data.get("inventory_id"), "commitment_inventory.inventory_id"
            ),
            authority_owner_id=_required_text(
                data.get("authority_owner_id"),
                "commitment_inventory.authority_owner_id",
            ),
            locator=_required_text(
                data.get("locator"), "commitment_inventory.locator"
            ),
            adapter_id=_required_text(
                data.get("adapter_id"), "commitment_inventory.adapter_id"
            ),
            adapter_version=_required_text(
                data.get("adapter_version"),
                "commitment_inventory.adapter_version",
            ),
            adapter_capability_id=_required_text(
                data.get("adapter_capability_id"),
                "commitment_inventory.adapter_capability_id",
            ),
            target_id=_required_text(
                data.get("target_id"), "commitment_inventory.target_id"
            ),
            target_revision=_required_text(
                data.get("target_revision"),
                "commitment_inventory.target_revision",
            ),
            input_refs=input_refs,
            claim_boundary=_required_text(
                data.get("claim_boundary"),
                "commitment_inventory.claim_boundary",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_id": self.inventory_id,
            "authority_owner_id": self.authority_owner_id,
            "locator": self.locator,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "adapter_capability_id": self.adapter_capability_id,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "input_refs": [row.to_dict() for row in self.input_refs],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class BehaviorOutputCommitment:
    commitment_id: str
    behavior_id: str
    output_id: str
    node_id: str
    port_id: str
    owner_id: str
    input_ids: tuple[str, ...]
    required_contributor_element_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BehaviorOutputCommitment":
        _unknown_fields(
            data,
            {
                "commitment_id",
                "behavior_id",
                "output_id",
                "node_id",
                "port_id",
                "owner_id",
                "input_ids",
                "required_contributor_element_ids",
            },
            "behavior output commitment",
        )
        input_ids = tuple(
            sorted(
                _required_text(value, "behavior_commitment.input_ids")
                for value in data.get("input_ids", [])
            )
        )
        if not input_ids:
            raise BlueprintError(
                "WORLD_BLUEPRINT_COMMITMENT_INPUTS_MISSING",
                "Every behavior output commitment requires at least one independent input id.",
            )
        required_contributors = tuple(
            sorted(
                _required_text(
                    value,
                    "behavior_commitment.required_contributor_element_ids",
                )
                for value in data.get("required_contributor_element_ids", [])
            )
        )
        if not required_contributors:
            raise BlueprintError(
                "WORLD_BLUEPRINT_COMMITMENT_CONTRIBUTORS_MISSING",
                "Every behavior output commitment requires an independent contributor denominator.",
            )
        return cls(
            commitment_id=_required_text(
                data.get("commitment_id"), "behavior_commitment.commitment_id"
            ),
            behavior_id=_required_text(
                data.get("behavior_id"), "behavior_commitment.behavior_id"
            ),
            output_id=_required_text(
                data.get("output_id"), "behavior_commitment.output_id"
            ),
            node_id=_required_text(
                data.get("node_id"), "behavior_commitment.node_id"
            ),
            port_id=_required_text(
                data.get("port_id"), "behavior_commitment.port_id"
            ),
            owner_id=_required_text(
                data.get("owner_id"), "behavior_commitment.owner_id"
            ),
            input_ids=input_ids,
            required_contributor_element_ids=required_contributors,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "behavior_id": self.behavior_id,
            "output_id": self.output_id,
            "node_id": self.node_id,
            "port_id": self.port_id,
            "owner_id": self.owner_id,
            "input_ids": list(self.input_ids),
            "required_contributor_element_ids": list(
                self.required_contributor_element_ids
            ),
        }


@dataclass(frozen=True)
class TargetSemanticBindingResponsibility:
    binding_id: str
    role: str
    owner_id: str
    resource_id: str
    locator: str
    provider_id: str
    provider_version: str
    provider_capability_id: str
    observation_mode: str

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        owner: str,
    ) -> "TargetSemanticBindingResponsibility":
        _unknown_fields(
            data,
            {
                "binding_id",
                "role",
                "owner_id",
                "resource_id",
                "locator",
                "provider_id",
                "provider_version",
                "provider_capability_id",
                "observation_mode",
            },
            owner,
        )
        role = _required_text(data.get("role"), f"{owner}.role")
        if role not in BINDING_ROLES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_BINDING_ROLE_UNKNOWN",
                "Target semantic authority names an unknown binding role.",
                details={"owner": owner, "role": role},
            )
        observation_mode = _required_text(
            data.get("observation_mode"), f"{owner}.observation_mode"
        )
        if observation_mode not in BINDING_OBSERVATION_MODES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_BINDING_MODE_UNKNOWN",
                "Target semantic authority names an unknown observation mode.",
                details={"owner": owner, "observation_mode": observation_mode},
            )
        return cls(
            binding_id=_required_text(data.get("binding_id"), f"{owner}.binding_id"),
            role=role,
            owner_id=_required_text(data.get("owner_id"), f"{owner}.owner_id"),
            resource_id=_required_text(data.get("resource_id"), f"{owner}.resource_id"),
            locator=_required_text(data.get("locator"), f"{owner}.locator"),
            provider_id=_required_text(data.get("provider_id"), f"{owner}.provider_id"),
            provider_version=_required_text(
                data.get("provider_version"), f"{owner}.provider_version"
            ),
            provider_capability_id=_required_text(
                data.get("provider_capability_id"),
                f"{owner}.provider_capability_id",
            ),
            observation_mode=observation_mode,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "role": self.role,
            "owner_id": self.owner_id,
            "resource_id": self.resource_id,
            "locator": self.locator,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "provider_capability_id": self.provider_capability_id,
            "observation_mode": self.observation_mode,
        }


@dataclass(frozen=True)
class TargetSemanticNotApplicableResponsibility:
    role: str
    reason: str

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "TargetSemanticNotApplicableResponsibility":
        _unknown_fields(data, {"role", "reason"}, owner)
        role = _required_text(data.get("role"), f"{owner}.role")
        if role not in BINDING_ROLES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_BINDING_ROLE_UNKNOWN",
                "Target semantic authority names an unknown not-applicable role.",
                details={"owner": owner, "role": role},
            )
        return cls(
            role=role,
            reason=_required_text(data.get("reason"), f"{owner}.reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "reason": self.reason}


@dataclass(frozen=True)
class TargetSemanticDerivationResponsibility:
    derivation_id: str
    target_element_id: str
    owner_node_id: str
    parent_output_port_id: str
    sources: tuple[OutputContribution, ...]

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, owner: str
    ) -> "TargetSemanticDerivationResponsibility":
        _unknown_fields(
            data,
            {
                "derivation_id",
                "target_element_id",
                "owner_node_id",
                "parent_output_port_id",
                "sources",
            },
            owner,
        )
        sources = tuple(
            sorted(
                (
                    OutputContribution.from_dict(
                        row, owner=f"{owner} source"
                    )
                    for row in data.get("sources", [])
                ),
                key=lambda row: (row.source_kind, row.source_id, row.source_port_id),
            )
        )
        if not sources:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_DERIVATION_SOURCES_MISSING",
                "A target semantic derivation responsibility requires exact sources.",
                details={"owner": owner},
            )
        return cls(
            derivation_id=_required_text(
                data.get("derivation_id"), f"{owner}.derivation_id"
            ),
            target_element_id=_required_text(
                data.get("target_element_id"), f"{owner}.target_element_id"
            ),
            owner_node_id=_required_text(
                data.get("owner_node_id"), f"{owner}.owner_node_id"
            ),
            parent_output_port_id=_required_text(
                data.get("parent_output_port_id"),
                f"{owner}.parent_output_port_id",
            ),
            sources=sources,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "derivation_id": self.derivation_id,
            "target_element_id": self.target_element_id,
            "owner_node_id": self.owner_node_id,
            "parent_output_port_id": self.parent_output_port_id,
            "sources": [row.to_dict() for row in self.sources],
        }


@dataclass(frozen=True)
class TargetMaterialSemanticAssertion:
    assertion_id: str
    source_input_kind: str
    source_path: tuple[str | int, ...]
    target_element_id: str
    semantic_path: tuple[str | int, ...]

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        owner: str,
    ) -> "TargetMaterialSemanticAssertion":
        _unknown_fields(
            data,
            {
                "assertion_id",
                "source_input_kind",
                "source_path",
                "target_element_id",
                "semantic_path",
            },
            owner,
        )
        source_kind = _required_text(
            data.get("source_input_kind"), f"{owner}.source_input_kind"
        )
        if source_kind != "target_material":
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_ASSERTION_SOURCE_INVALID",
                "Current target semantic assertions must bind observed target material.",
                details={"owner": owner, "source_input_kind": source_kind},
            )

        def parse_path(value: Any, field_id: str) -> tuple[str | int, ...]:
            if not isinstance(value, list) or not value:
                raise BlueprintError(
                    "WORLD_BLUEPRINT_TARGET_SEMANTIC_ASSERTION_PATH_INVALID",
                    "Target semantic assertion paths must be non-empty arrays.",
                    details={"field_id": field_id},
                )
            parsed: list[str | int] = []
            for part in value:
                if isinstance(part, bool) or not isinstance(part, (str, int)):
                    raise BlueprintError(
                        "WORLD_BLUEPRINT_TARGET_SEMANTIC_ASSERTION_PATH_INVALID",
                        "Target semantic assertion path members must be strings or indexes.",
                        details={"field_id": field_id, "path": value},
                    )
                if isinstance(part, str) and not part:
                    raise BlueprintError(
                        "WORLD_BLUEPRINT_TARGET_SEMANTIC_ASSERTION_PATH_INVALID",
                        "Target semantic assertion path strings cannot be empty.",
                        details={"field_id": field_id, "path": value},
                    )
                parsed.append(part)
            return tuple(parsed)

        return cls(
            assertion_id=_required_text(
                data.get("assertion_id"), f"{owner}.assertion_id"
            ),
            source_input_kind=source_kind,
            source_path=parse_path(data.get("source_path"), f"{owner}.source_path"),
            target_element_id=_required_text(
                data.get("target_element_id"), f"{owner}.target_element_id"
            ),
            semantic_path=parse_path(
                data.get("semantic_path"), f"{owner}.semantic_path"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "source_input_kind": self.source_input_kind,
            "source_path": list(self.source_path),
            "target_element_id": self.target_element_id,
            "semantic_path": list(self.semantic_path),
        }


@dataclass(frozen=True)
class TargetSemanticElementCommitment:
    element_id: str
    element_kind: str
    owner_node_id: str
    required_guard_owner_id: str
    required_executor_id: str
    required_executor_version: str
    native_semantic: NativeSemanticRef
    binding_responsibilities: tuple[TargetSemanticBindingResponsibility, ...]
    not_applicable_responsibilities: tuple[
        TargetSemanticNotApplicableResponsibility, ...
    ]
    support_mode: str
    derivation_responsibilities: tuple[
        TargetSemanticDerivationResponsibility, ...
    ]

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> "TargetSemanticElementCommitment":
        _unknown_fields(
            data,
            {
                "element_id",
                "element_kind",
                "owner_node_id",
                "required_guard_owner_id",
                "required_executor_id",
                "required_executor_version",
                "native_semantic",
                "binding_responsibilities",
                "not_applicable_responsibilities",
                "support_mode",
                "derivation_responsibilities",
            },
            "target semantic element commitment",
        )
        element_id = _required_text(data.get("element_id"), "target_semantic.element_id")
        element_kind = _required_text(
            data.get("element_kind"), f"target_semantic {element_id}.element_kind"
        )
        if element_kind not in WORLD_ELEMENT_KINDS:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_ELEMENT_KIND_UNKNOWN",
                "Target semantic authority names an unknown element kind.",
                details={"element_id": element_id, "element_kind": element_kind},
            )
        responsibilities = tuple(
            sorted(
                (
                    TargetSemanticBindingResponsibility.from_dict(
                        row,
                        owner=f"target semantic {element_id} binding responsibility",
                    )
                    for row in data.get("binding_responsibilities", [])
                ),
                key=lambda row: row.role,
            )
        )
        not_applicable_responsibilities = tuple(
            sorted(
                (
                    TargetSemanticNotApplicableResponsibility.from_dict(
                        row,
                        owner=(
                            f"target semantic {element_id} not-applicable responsibility"
                        ),
                    )
                    for row in data.get("not_applicable_responsibilities", [])
                ),
                key=lambda row: row.role,
            )
        )
        binding_roles = [row.role for row in responsibilities]
        not_applicable_roles = [
            row.role for row in not_applicable_responsibilities
        ]
        responsibility_roles = [*binding_roles, *not_applicable_roles]
        if (
            set(responsibility_roles) != set(BINDING_ROLES)
            or _duplicates(responsibility_roles)
        ):
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_ROLE_DENOMINATOR_INVALID",
                "Every target semantic element requires exactly one disposition for every support role.",
                details={
                    "element_id": element_id,
                    "missing_roles": sorted(
                        set(BINDING_ROLES).difference(responsibility_roles)
                    ),
                    "unknown_roles": sorted(
                        set(responsibility_roles).difference(BINDING_ROLES)
                    ),
                    "duplicate_roles": _duplicates(responsibility_roles),
                },
            )
        binding_ids = [row.binding_id for row in responsibilities]
        if _duplicates(binding_ids):
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_BINDING_ID_DUPLICATE",
                "Applicable target semantic responsibilities require unique binding ids.",
                details={
                    "element_id": element_id,
                    "duplicate_binding_ids": _duplicates(binding_ids),
                },
            )
        support_mode = _required_text(
            data.get("support_mode"),
            f"target_semantic {element_id}.support_mode",
        )
        if support_mode not in TARGET_SEMANTIC_SUPPORT_MODES:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_SUPPORT_MODE_UNKNOWN",
                "Target semantic element uses an unknown support mode.",
                details={"element_id": element_id, "support_mode": support_mode},
            )
        derivation_responsibilities = tuple(
            sorted(
                (
                    TargetSemanticDerivationResponsibility.from_dict(
                        row,
                        owner=(
                            f"target semantic {element_id} derivation responsibility"
                        ),
                    )
                    for row in data.get("derivation_responsibilities", [])
                ),
                key=lambda row: row.derivation_id,
            )
        )
        derivation_ids = [row.derivation_id for row in derivation_responsibilities]
        owner_node_id = _required_text(
            data.get("owner_node_id"), f"target_semantic {element_id}.owner_node_id"
        )
        derivation_identity_mismatches = [
            row.to_dict()
            for row in derivation_responsibilities
            if row.target_element_id != element_id or row.owner_node_id != owner_node_id
        ]
        if (
            (support_mode == "derived" and not derivation_responsibilities)
            or (support_mode == "direct" and derivation_responsibilities)
            or _duplicates(derivation_ids)
            or derivation_identity_mismatches
        ):
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_DERIVATION_DENOMINATOR_INVALID",
                "Derived support requires unique derivations and direct support forbids them.",
                details={
                    "element_id": element_id,
                    "support_mode": support_mode,
                    "derivation_ids": derivation_ids,
                    "duplicate_derivation_ids": _duplicates(derivation_ids),
                    "identity_mismatches": derivation_identity_mismatches,
                },
            )
        return cls(
            element_id=element_id,
            element_kind=element_kind,
            owner_node_id=owner_node_id,
            required_guard_owner_id=_required_text(
                data.get("required_guard_owner_id"),
                f"target_semantic {element_id}.required_guard_owner_id",
            ),
            required_executor_id=_required_text(
                data.get("required_executor_id"),
                f"target_semantic {element_id}.required_executor_id",
            ),
            required_executor_version=_required_text(
                data.get("required_executor_version"),
                f"target_semantic {element_id}.required_executor_version",
            ),
            native_semantic=NativeSemanticRef.from_dict(
                data.get("native_semantic", {}),
                element_id=element_id,
                expected_kind=element_kind,
            ),
            binding_responsibilities=responsibilities,
            not_applicable_responsibilities=not_applicable_responsibilities,
            support_mode=support_mode,
            derivation_responsibilities=derivation_responsibilities,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_kind": self.element_kind,
            "owner_node_id": self.owner_node_id,
            "required_guard_owner_id": self.required_guard_owner_id,
            "required_executor_id": self.required_executor_id,
            "required_executor_version": self.required_executor_version,
            "native_semantic": self.native_semantic.to_dict(),
            "binding_responsibilities": [
                row.to_dict() for row in self.binding_responsibilities
            ],
            "not_applicable_responsibilities": [
                row.to_dict()
                for row in self.not_applicable_responsibilities
            ],
            "support_mode": self.support_mode,
            "derivation_responsibilities": [
                row.to_dict() for row in self.derivation_responsibilities
            ],
        }

    def result_projection(self) -> dict[str, Any]:
        purpose = self.native_semantic.task_purpose
        return {
            "element_id": self.element_id,
            "element_kind": self.element_kind,
            "owner_node_id": self.owner_node_id,
            "required_guard_owner_id": self.required_guard_owner_id,
            "required_executor_id": self.required_executor_id,
            "required_executor_version": self.required_executor_version,
            "native_semantic_fingerprint": self.native_semantic.content_fingerprint,
            "task_purpose_fingerprint": (
                purpose.purpose_fingerprint if purpose is not None else ""
            ),
            "binding_responsibility_fingerprints": [
                "sha256:" + fingerprint_mesh(row.to_dict())
                for row in self.binding_responsibilities
            ],
            "not_applicable_responsibility_fingerprints": [
                "sha256:" + fingerprint_mesh(row.to_dict())
                for row in self.not_applicable_responsibilities
            ],
            "support_mode": self.support_mode,
            "derivation_responsibility_fingerprints": [
                "sha256:" + fingerprint_mesh(row.to_dict())
                for row in self.derivation_responsibilities
            ],
        }


@dataclass(frozen=True)
class TargetSemanticAuthority:
    authority_id: str
    authority_owner_id: str
    target_id: str
    target_revision: str
    claim_boundary: str
    required_node_ids: tuple[str, ...]
    elements: tuple[TargetSemanticElementCommitment, ...]
    material_assertions: tuple[TargetMaterialSemanticAssertion, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TargetSemanticAuthority":
        _unknown_fields(
            data,
            {
                "schema_version",
                "authority_id",
                "authority_owner_id",
                "target_id",
                "target_revision",
                "claim_boundary",
                "required_node_ids",
                "elements",
                "material_assertions",
            },
            "target semantic authority",
        )
        if data.get("schema_version") != "worldguard.target_semantic_authority.v2":
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_AUTHORITY_SCHEMA_INVALID",
                "Target semantic authority schema is not current.",
                details={"observed": data.get("schema_version")},
            )
        required_node_ids = tuple(
            sorted(
                _required_text(value, "target_semantic_authority.required_node_ids")
                for value in data.get("required_node_ids", [])
            )
        )
        elements = tuple(
            sorted(
                (
                    TargetSemanticElementCommitment.from_dict(row)
                    for row in data.get("elements", [])
                ),
                key=lambda row: row.element_id,
            )
        )
        assertions = tuple(
            sorted(
                (
                    TargetMaterialSemanticAssertion.from_dict(
                        row, owner="target semantic material assertion"
                    )
                    for row in data.get("material_assertions", [])
                ),
                key=lambda row: row.assertion_id,
            )
        )
        duplicates = {
            "required_node_ids": _duplicates(required_node_ids),
            "element_ids": _duplicates([row.element_id for row in elements]),
            "assertion_ids": _duplicates([row.assertion_id for row in assertions]),
            "derivation_ids": _duplicates(
                [
                    derivation.derivation_id
                    for row in elements
                    for derivation in row.derivation_responsibilities
                ]
            ),
        }
        duplicates = {key: value for key, value in duplicates.items() if value}
        if duplicates or not required_node_ids or not elements or not assertions:
            raise BlueprintError(
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_AUTHORITY_DENOMINATOR_INVALID",
                "Target semantic authority requires non-empty unique nodes, elements, and material assertions.",
                details={"duplicates": duplicates},
            )
        return cls(
            authority_id=_required_text(
                data.get("authority_id"), "target_semantic_authority.authority_id"
            ),
            authority_owner_id=_required_text(
                data.get("authority_owner_id"),
                "target_semantic_authority.authority_owner_id",
            ),
            target_id=_required_text(
                data.get("target_id"), "target_semantic_authority.target_id"
            ),
            target_revision=_required_text(
                data.get("target_revision"),
                "target_semantic_authority.target_revision",
            ),
            claim_boundary=_required_text(
                data.get("claim_boundary"),
                "target_semantic_authority.claim_boundary",
            ),
            required_node_ids=required_node_ids,
            elements=elements,
            material_assertions=assertions,
        )

    @property
    def required_guard_owner_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    row.required_guard_owner_id
                    for row in self.elements
                    if row.required_guard_owner_id != "not_applicable"
                }
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "worldguard.target_semantic_authority.v2",
            "authority_id": self.authority_id,
            "authority_owner_id": self.authority_owner_id,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "claim_boundary": self.claim_boundary,
            "required_node_ids": list(self.required_node_ids),
            "elements": [row.to_dict() for row in self.elements],
            "material_assertions": [row.to_dict() for row in self.material_assertions],
        }


@dataclass(frozen=True)
class BehaviorCommitmentAdapterRegistration:
    adapter_id: str
    adapter_version: str
    capability_id: str
    execution_owner_id: str
    execution_owner_version: str
    executor_id: str
    executor_version: str
    required_input_kinds: tuple[str, ...]
    supported_input_kinds: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "worldguard.behavior_commitment_adapter_registration.v1",
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "capability_id": self.capability_id,
            "execution_owner_id": self.execution_owner_id,
            "execution_owner_version": self.execution_owner_version,
            "executor_id": self.executor_id,
            "executor_version": self.executor_version,
            "required_input_kinds": list(self.required_input_kinds),
            "supported_input_kinds": list(self.supported_input_kinds),
        }

    @property
    def registration_fingerprint(self) -> str:
        return "sha256:" + fingerprint_mesh(self.to_dict())


@dataclass(frozen=True)
class BehaviorCommitmentAdapterRegistry:
    registrations: tuple[BehaviorCommitmentAdapterRegistration, ...]

    def __post_init__(self) -> None:
        identities = [
            (row.adapter_id, row.adapter_version, row.capability_id)
            for row in self.registrations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("BehaviorCommitmentAdapterRegistry has duplicate owners")

    def resolve(
        self,
        adapter_id: str,
        adapter_version: str,
        capability_id: str,
    ) -> BehaviorCommitmentAdapterRegistration | None:
        return next(
            (
                row
                for row in self.registrations
                if (
                    row.adapter_id,
                    row.adapter_version,
                    row.capability_id,
                )
                == (adapter_id, adapter_version, capability_id)
            ),
            None,
        )


BEHAVIOR_COMMITMENT_ADAPTER_REGISTRY = BehaviorCommitmentAdapterRegistry(
    registrations=(
        BehaviorCommitmentAdapterRegistration(
            adapter_id="worldguard.request-contract.commitment-adapter",
            adapter_version="v2",
            capability_id="worldguard.behavior-commitment.replay.v2",
            execution_owner_id="worldguard.behavior-commitment.adapter-owner",
            execution_owner_version="v2",
            executor_id="worldguard.behavior-commitment.request-contract.v2",
            executor_version="v2",
            required_input_kinds=(
                "request_contract",
                "target_material",
                "target_object_census_source",
                "target_semantic_authority",
                "target_object_census_authority",
            ),
            supported_input_kinds=(
                "request_contract",
                "target_material",
                "target_object_census_source",
                "target_semantic_authority",
                "target_object_census_authority",
            ),
        ),
    )
)


@dataclass(frozen=True)
class WorldBlueprintContract:
    blueprint_id: str
    target_id: str
    target_revision: str
    declared_boundary: str
    root_node_id: str
    nodes: tuple[WorldBlueprintNode, ...]
    elements: tuple[WorldElement, ...]
    bindings: tuple[BlueprintBinding, ...]
    declared_inputs: tuple[DeclaredBlueprintInput, ...]
    declared_outputs: tuple[BlueprintOutputRef, ...]
    commitment_inventory: BehaviorCommitmentInventoryRef
    declared_gaps: tuple[DeclaredBlueprintGap, ...] = ()
    blueprint_fingerprint: str = ""
    schema_version: str = WORLD_BLUEPRINT_SCHEMA_VERSION
    source_root: str = field(default="", compare=False, repr=False)
    source_path: str = field(default="", compare=False, repr=False)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        source_root: str | Path = "",
    ) -> "WorldBlueprintContract":
        _unknown_fields(
            data,
            {
                "schema_version",
                "blueprint_id",
                "target_id",
                "target_revision",
                "declared_boundary",
                "root_node_id",
                "nodes",
                "elements",
                "bindings",
                "declared_inputs",
                "declared_outputs",
                "commitment_inventory",
                "declared_gaps",
                "blueprint_fingerprint",
            },
            "world blueprint",
        )
        schema_version = str(data.get("schema_version", "")).strip()
        if schema_version != WORLD_BLUEPRINT_SCHEMA_VERSION:
            raise BlueprintError(
                "WORLD_BLUEPRINT_SCHEMA_INVALID",
                "WorldBlueprint schema_version is not current.",
                details={
                    "expected": WORLD_BLUEPRINT_SCHEMA_VERSION,
                    "observed": schema_version,
                },
            )
        candidate = cls(
            blueprint_id=_required_text(data.get("blueprint_id"), "blueprint_id"),
            target_id=_required_text(data.get("target_id"), "target_id"),
            target_revision=_required_text(
                data.get("target_revision"), "target_revision"
            ),
            declared_boundary=_required_text(
                data.get("declared_boundary"), "declared_boundary"
            ),
            root_node_id=_required_text(data.get("root_node_id"), "root_node_id"),
            nodes=tuple(
                sorted(
                    (WorldBlueprintNode.from_dict(row) for row in data.get("nodes", [])),
                    key=lambda row: row.node_id,
                )
            ),
            elements=tuple(
                sorted(
                    (WorldElement.from_dict(row) for row in data.get("elements", [])),
                    key=lambda row: row.element_id,
                )
            ),
            bindings=tuple(
                sorted(
                    (BlueprintBinding.from_dict(row) for row in data.get("bindings", [])),
                    key=lambda row: row.binding_id,
                )
            ),
            declared_inputs=tuple(
                sorted(
                    (
                        DeclaredBlueprintInput.from_dict(row)
                        for row in data.get("declared_inputs", [])
                    ),
                    key=lambda row: row.input_id,
                )
            ),
            declared_outputs=tuple(
                sorted(
                    (
                        BlueprintOutputRef.from_dict(row)
                        for row in data.get("declared_outputs", [])
                    ),
                    key=lambda row: row.output_id,
                )
            ),
            commitment_inventory=BehaviorCommitmentInventoryRef.from_dict(
                data.get("commitment_inventory", {})
            ),
            declared_gaps=tuple(
                sorted(
                    (
                        DeclaredBlueprintGap.from_dict(row)
                        for row in data.get("declared_gaps", [])
                    ),
                    key=lambda row: row.gap_id,
                )
            ),
            schema_version=schema_version,
            source_root=str(source_root),
        )
        current = candidate.current_fingerprint()
        declared = str(data.get("blueprint_fingerprint", "")).strip()
        if declared and declared != current:
            raise BlueprintError(
                "WORLD_BLUEPRINT_FINGERPRINT_STALE",
                "Declared WorldBlueprint fingerprint does not match current content.",
                details={"declared": declared, "current": current},
            )
        return replace(candidate, blueprint_fingerprint=current)

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "blueprint_id": self.blueprint_id,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "declared_boundary": self.declared_boundary,
            "root_node_id": self.root_node_id,
            "nodes": [item.to_dict() for item in self.nodes],
            "elements": [item.to_dict() for item in self.elements],
            "bindings": [item.to_dict() for item in self.bindings],
            "declared_inputs": [item.to_dict() for item in self.declared_inputs],
            "declared_outputs": [item.to_dict() for item in self.declared_outputs],
            "commitment_inventory": self.commitment_inventory.to_dict(),
            "declared_gaps": [item.to_dict() for item in self.declared_gaps],
        }

    def current_fingerprint(self) -> str:
        return fingerprint_mesh(self.fingerprint_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.fingerprint_payload(), "blueprint_fingerprint": self.blueprint_fingerprint}


def load_world_blueprint(path: str | Path) -> WorldBlueprintContract:
    resolved = Path(path).resolve()
    return replace(
        WorldBlueprintContract.from_dict(
            load_mapping(resolved),
            source_root=resolved.parent,
        ),
        source_path=str(resolved),
    )


@dataclass(frozen=True)
class CrossArtifactProjectionResult:
    """One independently owned projection result consumed by native qualification.

    The result is evidence about a separate artifact, not part of the native
    blueprint itself.  Its source/report identities and complete source-id
    denominator therefore remain explicit and receipt-bound.
    """

    projection_id: str
    provider_id: str
    provider_version: str
    provider_capability_id: str
    execution_owner_id: str
    execution_owner_version: str
    target_id: str
    target_revision: str
    claim_boundary: str
    source_blueprint_fingerprint: str
    source_report_fingerprint: str
    required_source_ids: tuple[str, ...]
    projected_source_ids: tuple[str, ...]
    unresolved_source_ids: tuple[str, ...]
    normalized_payload: dict[str, Any]
    normalized_payload_fingerprint: str
    status: str
    producer_identity_fingerprint: str
    terminal_receipt_payload: dict[str, Any]
    terminal_receipt_fingerprint: str
    schema_version: str = "worldguard.cross_artifact_projection.v2"

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> "CrossArtifactProjectionResult":
        _unknown_fields(
            data,
            {
                "schema_version",
                "projection_id",
                "provider_id",
                "provider_version",
                "provider_capability_id",
                "execution_owner_id",
                "execution_owner_version",
                "target_id",
                "target_revision",
                "claim_boundary",
                "source_blueprint_fingerprint",
                "source_report_fingerprint",
                "required_source_ids",
                "projected_source_ids",
                "unresolved_source_ids",
                "normalized_payload",
                "normalized_payload_fingerprint",
                "status",
                "producer_identity_fingerprint",
                "terminal_receipt_payload",
                "terminal_receipt_fingerprint",
            },
            "cross-artifact projection result",
        )
        schema_version = _required_text(
            data.get("schema_version"), "cross_artifact_projection.schema_version"
        )
        if schema_version != "worldguard.cross_artifact_projection.v2":
            raise BlueprintError(
                "WORLD_BLUEPRINT_CROSS_ARTIFACT_SCHEMA_INVALID",
                "Cross-artifact projection result schema is not current.",
                details={"schema_version": schema_version},
            )
        status = _required_text(
            data.get("status"), "cross_artifact_projection.status"
        )
        if status not in {"proven", "gap", "boundary"}:
            raise BlueprintError(
                "WORLD_BLUEPRINT_CROSS_ARTIFACT_STATUS_INVALID",
                "Cross-artifact projection status must be proven, gap, or boundary.",
                details={"status": status},
            )
        identifier_sets: dict[str, tuple[str, ...]] = {}
        for field_id in (
            "required_source_ids",
            "projected_source_ids",
            "unresolved_source_ids",
        ):
            value = data.get(field_id)
            if (
                not isinstance(value, list)
                or any(not isinstance(item, str) or not item for item in value)
                or len(value) != len(set(value))
            ):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_CROSS_ARTIFACT_SET_INVALID",
                    f"Cross-artifact projection {field_id} must be a unique string list.",
                    details={"field_id": field_id},
                )
            identifier_sets[field_id] = tuple(sorted(value))
        normalized_payload = data.get("normalized_payload")
        if not isinstance(normalized_payload, Mapping):
            raise BlueprintError(
                "WORLD_BLUEPRINT_CROSS_ARTIFACT_PAYLOAD_INVALID",
                "Cross-artifact normalized payload must be an object.",
            )
        terminal_receipt_payload = data.get("terminal_receipt_payload")
        if not isinstance(terminal_receipt_payload, Mapping):
            raise BlueprintError(
                "WORLD_BLUEPRINT_CROSS_ARTIFACT_RECEIPT_INVALID",
                "Cross-artifact terminal receipt must remain an in-memory object.",
            )
        return cls(
            schema_version=schema_version,
            projection_id=_required_text(
                data.get("projection_id"), "cross_artifact_projection.projection_id"
            ),
            provider_id=_required_text(
                data.get("provider_id"), "cross_artifact_projection.provider_id"
            ),
            provider_version=_required_text(
                data.get("provider_version"),
                "cross_artifact_projection.provider_version",
            ),
            provider_capability_id=_required_text(
                data.get("provider_capability_id"),
                "cross_artifact_projection.provider_capability_id",
            ),
            execution_owner_id=_required_text(
                data.get("execution_owner_id"),
                "cross_artifact_projection.execution_owner_id",
            ),
            execution_owner_version=_required_text(
                data.get("execution_owner_version"),
                "cross_artifact_projection.execution_owner_version",
            ),
            target_id=_required_text(
                data.get("target_id"), "cross_artifact_projection.target_id"
            ),
            target_revision=_required_text(
                data.get("target_revision"),
                "cross_artifact_projection.target_revision",
            ),
            claim_boundary=_required_text(
                data.get("claim_boundary"),
                "cross_artifact_projection.claim_boundary",
            ),
            source_blueprint_fingerprint=_required_sha256(
                data.get("source_blueprint_fingerprint"),
                "cross_artifact_projection.source_blueprint_fingerprint",
            ),
            source_report_fingerprint=_required_sha256(
                data.get("source_report_fingerprint"),
                "cross_artifact_projection.source_report_fingerprint",
            ),
            required_source_ids=identifier_sets["required_source_ids"],
            projected_source_ids=identifier_sets["projected_source_ids"],
            unresolved_source_ids=identifier_sets["unresolved_source_ids"],
            normalized_payload=dict(normalized_payload),
            normalized_payload_fingerprint=_required_sha256(
                data.get("normalized_payload_fingerprint"),
                "cross_artifact_projection.normalized_payload_fingerprint",
            ),
            status=status,
            producer_identity_fingerprint=_required_sha256(
                data.get("producer_identity_fingerprint"),
                "cross_artifact_projection.producer_identity_fingerprint",
            ),
            terminal_receipt_payload=dict(terminal_receipt_payload),
            terminal_receipt_fingerprint=_required_sha256(
                data.get("terminal_receipt_fingerprint"),
                "cross_artifact_projection.terminal_receipt_fingerprint",
            ),
        )

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_id": self.projection_id,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "provider_capability_id": self.provider_capability_id,
            "execution_owner_id": self.execution_owner_id,
            "execution_owner_version": self.execution_owner_version,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "claim_boundary": self.claim_boundary,
            "source_blueprint_fingerprint": self.source_blueprint_fingerprint,
            "source_report_fingerprint": self.source_report_fingerprint,
            "required_source_ids": list(self.required_source_ids),
            "projected_source_ids": list(self.projected_source_ids),
            "unresolved_source_ids": list(self.unresolved_source_ids),
            "normalized_payload": self.normalized_payload,
            "normalized_payload_fingerprint": self.normalized_payload_fingerprint,
            "status": self.status,
        }

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            **self.evidence_payload(),
            "producer_identity_fingerprint": self.producer_identity_fingerprint,
            "terminal_receipt_payload": self.terminal_receipt_payload,
            "terminal_receipt_fingerprint": self.terminal_receipt_fingerprint,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.fingerprint_payload(),
            "terminal_receipt_fingerprint": self.terminal_receipt_fingerprint,
        }


@dataclass(frozen=True)
class BlueprintGap:
    gap_id: str
    code: str
    message: str
    severity: GuardStatus
    layer_id: str
    depth: int
    claim_boundary: str
    node_id: str = ""
    element_id: str = ""
    port_id: str = ""
    binding_id: str = ""
    required_role: str = ""
    expected_owner: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "layer_id": self.layer_id,
            "depth": self.depth,
            "claim_boundary": self.claim_boundary,
            "node_id": self.node_id,
            "element_id": self.element_id,
            "port_id": self.port_id,
            "binding_id": self.binding_id,
            "required_role": self.required_role,
            "expected_owner": self.expected_owner,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class BlueprintLayerResult:
    layer_id: str
    status: BlueprintLayerStatus
    gap_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "status": self.status.value,
            "gap_ids": list(self.gap_ids),
        }


@dataclass(frozen=True)
class WorldBlueprintReport:
    status: GuardStatus
    blueprint_id: str
    target_id: str
    target_revision: str
    blueprint_fingerprint: str
    report_fingerprint: str
    qualification_layers: tuple[BlueprintLayerResult, ...]
    depth_layers: tuple[BlueprintLayerResult, ...]
    deepest_continuously_proven_layer: int | None
    first_unresolved_layer: int | None
    native_domain_qualified: bool
    full_domain_qualified: bool
    object_dna_qualified: bool
    object_census: dict[str, Any]
    partial_model_usable: bool
    native_execution_receipts: tuple[dict[str, Any], ...]
    gaps: tuple[BlueprintGap, ...]
    claim_boundary: str
    cross_artifact_projection: CrossArtifactProjectionResult | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status.value,
            "blueprint_id": self.blueprint_id,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "report_fingerprint": self.report_fingerprint,
            "qualification_layers": [item.to_dict() for item in self.qualification_layers],
            "depth_layers": [item.to_dict() for item in self.depth_layers],
            "deepest_continuously_proven_layer": self.deepest_continuously_proven_layer,
            "first_unresolved_layer": self.first_unresolved_layer,
            "native_domain_qualified": self.native_domain_qualified,
            "full_domain_qualified": self.full_domain_qualified,
            "object_dna_qualified": self.object_dna_qualified,
            "object_census": self.object_census,
            "partial_model_usable": self.partial_model_usable,
            "native_execution_receipts": list(self.native_execution_receipts),
            "gaps": [item.to_dict() for item in self.gaps],
            "claim_boundary": self.claim_boundary,
        }
        if self.cross_artifact_projection is not None:
            payload["cross_artifact_projection"] = (
                self.cross_artifact_projection.to_dict()
            )
        return payload


def _gap(
    blueprint: WorldBlueprintContract,
    *,
    code: str,
    message: str,
    severity: GuardStatus,
    layer_id: str,
    depth: int = 0,
    node_id: str = "",
    element_id: str = "",
    port_id: str = "",
    binding_id: str = "",
    required_role: str = "",
    expected_owner: str = "",
    evidence: dict[str, Any] | None = None,
    gap_id: str = "",
) -> BlueprintGap:
    subject = binding_id or port_id or element_id or node_id or str(len(message))
    return BlueprintGap(
        gap_id=gap_id or f"{blueprint.blueprint_id}:{code}:{subject}",
        code=code,
        message=message,
        severity=severity,
        layer_id=layer_id,
        depth=max(0, depth),
        claim_boundary=blueprint.declared_boundary,
        node_id=node_id,
        element_id=element_id,
        port_id=port_id,
        binding_id=binding_id,
        required_role=required_role,
        expected_owner=expected_owner,
        evidence=evidence or {},
    )


def _duplicates(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _layer_status(gaps: Sequence[BlueprintGap]) -> BlueprintLayerStatus:
    if not gaps:
        return BlueprintLayerStatus.PROVEN
    if any(gap.severity == GuardStatus.BOUNDARY_EXCEEDED for gap in gaps) and not any(
        gap.severity in {GuardStatus.FAIL, GuardStatus.GAP} for gap in gaps
    ):
        return BlueprintLayerStatus.BOUNDARY
    return BlueprintLayerStatus.GAP


def _node_depth(nodes: Mapping[str, WorldBlueprintNode], node_id: str) -> int:
    node = nodes.get(node_id)
    return node.depth if node else 0


def _binding_receipt_fingerprint(binding: BlueprintBinding) -> str:
    return "sha256:" + fingerprint_mesh(
        {
            "schema_version": "worldguard.blueprint_resource_observation.v1",
            "binding_id": binding.binding_id,
            "role": binding.role,
            "subject_element_id": binding.subject_element_id,
            "resource_id": binding.resource_id,
            "owner": binding.owner,
            "locator": binding.locator,
            "provider_id": binding.provider_id,
            "provider_version": binding.provider_version,
            "provider_capability_id": binding.provider_capability_id,
            "observation_mode": binding.observation_mode,
            "target_id": binding.target_id,
            "target_revision": binding.target_revision,
            "freshness_status": binding.freshness_status,
            "content_fingerprint": binding.content_fingerprint,
            "claim_boundary": binding.claim_boundary,
        }
    )


def _local_binding_content_fingerprint(
    binding: BlueprintBinding,
    *,
    source_root: str,
) -> tuple[str, str]:
    if not source_root:
        return "", "source_root_missing"
    path_text, separator, selector = binding.locator.partition("#")
    relative = Path(path_text)
    if relative.is_absolute():
        return "", "absolute_locator_forbidden"
    root = Path(source_root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return "", "locator_escapes_source_root"
    if not candidate.is_file():
        return "", "resource_missing"
    content = candidate.read_bytes()
    if separator:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "", "selector_requires_json_object"
        if not isinstance(payload, Mapping) or selector not in payload:
            return "", "resource_selector_missing"
        content = json.dumps(
            payload[selector],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    return "sha256:" + hashlib.sha256(content).hexdigest(), ""


def _local_binding_json_payload(
    binding: BlueprintBinding,
    *,
    source_root: str,
) -> tuple[dict[str, Any] | None, str]:
    """Load the exact selected JSON object behind one local binding."""

    if not source_root:
        return None, "source_root_missing"
    path_text, separator, selector = binding.locator.partition("#")
    relative = Path(path_text)
    if relative.is_absolute():
        return None, "absolute_locator_forbidden"
    root = Path(source_root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return None, "locator_escapes_source_root"
    if not candidate.is_file():
        return None, "resource_missing"
    try:
        payload: Any = json.loads(candidate.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "resource_invalid_json"
    if separator:
        if not isinstance(payload, Mapping) or selector not in payload:
            return None, "resource_selector_missing"
        payload = payload[selector]
    if not isinstance(payload, Mapping):
        return None, "resource_not_object"
    return dict(payload), ""


def _validate_external_evidence_observation(
    blueprint: WorldBlueprintContract,
    element: WorldElement,
    binding: BlueprintBinding,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Validate that evidence semantics, not just bytes, support this subject."""

    fields = {
        "schema_version",
        "evidence_id",
        "target_id",
        "target_revision",
        "claim_boundary",
        "subject_element_id",
        "owner_id",
        "source_id",
        "producer_id",
        "producer_version",
        "freshness_status",
        "observed",
        "supports",
        "observation",
    }
    missing = sorted(fields.difference(payload))
    unknown = sorted(set(payload).difference(fields))
    if missing or unknown:
        return None, "external_evidence_shape_mismatch", {
            "missing_fields": missing,
            "unknown_fields": unknown,
        }
    expected = {
        "schema_version": "worldguard.external_evidence_observation.v1",
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "claim_boundary": blueprint.declared_boundary,
        "subject_element_id": element.element_id,
        "owner_id": binding.owner,
        "source_id": binding.resource_id,
        "producer_id": binding.provider_id,
        "producer_version": binding.provider_version,
        "freshness_status": "current",
        "observed": True,
        "supports": element.element_id,
    }
    mismatches = {
        field_name: {"expected": expected_value, "observed": payload.get(field_name)}
        for field_name, expected_value in expected.items()
        if payload.get(field_name) != expected_value
    }
    if not str(payload.get("evidence_id", "")).strip():
        mismatches["evidence_id"] = {
            "expected": "non-empty",
            "observed": payload.get("evidence_id"),
        }
    if not str(payload.get("observation", "")).strip():
        mismatches["observation"] = {
            "expected": "non-empty",
            "observed": payload.get("observation"),
        }
    else:
        expected_observation = (
            f"Observed support for {element.element_id} within "
            f"{blueprint.declared_boundary}."
        )
        if payload.get("observation") != expected_observation:
            mismatches["observation"] = {
                "expected": expected_observation,
                "observed": payload.get("observation"),
            }
    if mismatches:
        return None, "external_evidence_semantic_mismatch", {
            "mismatches": mismatches
        }
    result_payload = {
        "schema_version": "worldguard.external_evidence_alignment_result.v1",
        "evidence_id": payload["evidence_id"],
        "binding_id": binding.binding_id,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "element_id": element.element_id,
        "owner_id": binding.owner,
        "source_id": binding.resource_id,
        "producer_id": binding.provider_id,
        "producer_version": binding.provider_version,
        "freshness_status": "current",
        "observed": True,
        "supports": element.element_id,
        "content_fingerprint": binding.content_fingerprint,
        "claim_boundary": blueprint.declared_boundary,
        "terminal_status": "PASS",
    }
    receipt_payload = {
        **result_payload,
        "schema_version": "worldguard.external_evidence_alignment_receipt.v1",
        "result_fingerprint": "sha256:" + fingerprint_mesh(result_payload),
    }
    return (
        {
            **receipt_payload,
            "receipt_fingerprint": "sha256:" + fingerprint_mesh(receipt_payload),
        },
        "",
        {},
    )


def _execute_external_test_check(
    blueprint: WorldBlueprintContract,
    element: WorldElement,
    binding: BlueprintBinding,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Execute one external test design through the current domain owner."""

    fields = {
        "schema_version",
        "check_id",
        "target_id",
        "target_revision",
        "claim_boundary",
        "subject_element_id",
        "owner_id",
        "source_id",
        "producer_id",
        "producer_version",
        "freshness_status",
        "execution_mode",
        "behavior_case_id",
        "behavior_case_fingerprint",
        "inputs",
        "oracle",
    }
    missing = sorted(fields.difference(payload))
    unknown = sorted(set(payload).difference(fields))
    if missing or unknown:
        return None, "external_test_shape_mismatch", {
            "missing_fields": missing,
            "unknown_fields": unknown,
        }
    semantic = element.native_semantic
    task_purpose = semantic.task_purpose if semantic is not None else None
    owner_guard, requested_semantic = (
        _blueprint_native_owner(semantic) if semantic is not None else ("", "")
    )
    if task_purpose is None or not owner_guard or owner_guard not in EXECUTOR_REGISTRY:
        return None, "external_test_owner_unavailable", {
            "element_id": element.element_id,
            "owner_guard": owner_guard,
        }
    matching_cases = [
        row
        for row in task_purpose.behavior_cases
        if row.case_id == payload.get("behavior_case_id")
        and row.case_kind == "known_good"
    ]
    if len(matching_cases) != 1:
        return None, "external_test_known_good_case_unresolved", {
            "behavior_case_id": payload.get("behavior_case_id"),
            "matching_case_ids": [row.case_id for row in matching_cases],
        }
    behavior_case = matching_cases[0]
    executor_id = EXECUTOR_REGISTRY[owner_guard].binding.executor_id
    executor_version = executor_id.rsplit(".", 1)[-1]
    expected_oracle = {
        "oracle_id": behavior_case.oracle_id,
        "expected_output": behavior_case.expected_output,
        "expected_post_state": behavior_case.post_state,
        "expected_effects": behavior_case.effects,
        "expected_terminal_status": "PASS",
    }
    expected_identity = {
        "schema_version": "worldguard.external_test_check.v1",
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "claim_boundary": blueprint.declared_boundary,
        "subject_element_id": element.element_id,
        "owner_id": binding.owner,
        "source_id": binding.resource_id,
        "producer_id": binding.provider_id,
        "producer_version": binding.provider_version,
        "freshness_status": "current",
        "execution_mode": "current_domain_owner",
        "behavior_case_id": behavior_case.case_id,
        "behavior_case_fingerprint": behavior_case.case_fingerprint,
        "inputs": behavior_case.inputs,
        "oracle": expected_oracle,
    }
    identity_mismatches = {
        field_name: {"expected": expected_value, "observed": payload.get(field_name)}
        for field_name, expected_value in expected_identity.items()
        if payload.get(field_name) != expected_value
    }
    if not str(payload.get("check_id", "")).strip():
        identity_mismatches["check_id"] = {
            "expected": "non-empty",
            "observed": payload.get("check_id"),
        }
    if identity_mismatches:
        return None, "external_test_contract_mismatch", {
            "mismatches": identity_mismatches
        }

    contract_id = (
        f"world-blueprint-external-test:{blueprint.blueprint_id}:"
        f"{element.element_id}:{payload['check_id']}"
    )
    run_id = f"world-blueprint-external-test:{blueprint.target_revision}"
    declaration = task_purpose.to_guard_declaration(
        guard=owner_guard,
        task_contract_id=contract_id,
        run_id=run_id,
        model_instance_id=blueprint.target_id,
    )
    parent_contract = GuardContract.from_dict(
        {
            "contract_id": contract_id,
            "schema_version": "worldguard.contract.v1",
            "run_id": run_id,
            "claim": {
                "claim_id": f"external-test:{element.element_id}",
                "text": f"Execute external check for one {requested_semantic} element.",
                "target_guards": [owner_guard],
                "requested_semantics": [requested_semantic],
            },
            "world_model": {
                "model_id": blueprint.target_id,
                "model_version": blueprint.target_revision,
                "entities": {},
                "relations": {},
                "assumptions": [],
                "scope_limits": [blueprint.declared_boundary],
            },
            "inputs": dict(payload["inputs"]),
            "guard_purpose_declarations": [declaration],
        }
    )
    execution_error = ""
    try:
        contract = parent_contract.for_guard(owner_guard)
        verify_guard_candidate_purpose_contract(contract, owner_guard)
        structural = GUARD_RUNNERS[owner_guard](contract)
        semantic_status, semantic_findings, _, outputs = (
            EXECUTOR_REGISTRY[owner_guard].execute(contract)
        )
    except (GuardCandidatePurposeError, KeyError, TypeError, ValueError) as exc:
        structural_status = GuardStatus.FAIL
        semantic_status = SemanticStatus.FAIL
        semantic_findings = [
            {
                "code": getattr(exc, "code", "WORLD_BLUEPRINT_EXTERNAL_TEST_EXECUTION_ERROR"),
                "message": str(exc),
            }
        ]
        outputs = {}
        execution_error = type(exc).__name__
    else:
        structural_status = structural.status
    mismatches = _behavior_expected_subset(
        behavior_case.expected_output,
        outputs,
        path="output",
    )
    if behavior_case.state_effect_disposition == "applicable":
        mismatches.extend(
            _behavior_expected_subset(
                behavior_case.post_state, outputs, path="post_state"
            )
        )
        mismatches.extend(
            _behavior_expected_subset(
                behavior_case.effects, outputs, path="effects"
            )
        )
    terminal_status = (
        "PASS"
        if structural_status == GuardStatus.PASS
        and semantic_status == SemanticStatus.PASS
        and not semantic_findings
        and not mismatches
        else "FAIL"
    )
    result_payload = {
        "structural_status": structural_status.value,
        "semantic_status": semantic_status.value,
        "semantic_findings": semantic_findings,
        "outputs": outputs,
        "oracle_mismatches": mismatches,
        "execution_error": execution_error,
        "terminal_status": terminal_status,
    }
    receipt_payload = {
        "schema_version": "worldguard.external_test_execution_receipt.v1",
        "execution_id": (
            f"external-test:{blueprint.blueprint_id}:{element.element_id}:"
            f"{payload['check_id']}"
        ),
        "check_id": payload["check_id"],
        "binding_id": binding.binding_id,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "element_id": element.element_id,
        "test_owner_id": binding.owner,
        "source_id": binding.resource_id,
        "producer_id": binding.provider_id,
        "producer_version": binding.provider_version,
        "domain_owner_guard": owner_guard,
        "executor_id": executor_id,
        "executor_version": executor_version,
        "freshness_status": "current",
        "inputs_fingerprint": "sha256:" + fingerprint_mesh(payload["inputs"]),
        "oracle_fingerprint": "sha256:" + fingerprint_mesh(payload["oracle"]),
        "result_fingerprint": "sha256:" + fingerprint_mesh(result_payload),
        "terminal_status": terminal_status,
        "claim_boundary": blueprint.declared_boundary,
    }
    receipt = {
        **receipt_payload,
        "receipt_fingerprint": "sha256:" + fingerprint_mesh(receipt_payload),
    }
    return receipt, ("" if terminal_status == "PASS" else "external_test_failed"), {
        "result": result_payload
    }


_PROVIDER_CAPABILITY_REGISTRY: dict[tuple[str, str, str], dict[str, str]] = {
    (
        "external.workflow.provider",
        "v7",
        "workflow.content-observation.v1",
    ): {
        "schema_version": "worldguard.provider_capability_registration.v1",
        "registry_id": "worldguard.provider-capabilities.current",
        "provider_id": "external.workflow.provider",
        "provider_version": "v7",
        "provider_capability_id": "workflow.content-observation.v1",
        "execution_owner_id": "external.workflow.provider.current-observation-owner",
        "execution_owner_version": "v7",
        "claim_boundary": "exact current binding-content observation only",
    }
}


def _provider_capability_registration(
    binding: BlueprintBinding,
) -> dict[str, str] | None:
    row = _PROVIDER_CAPABILITY_REGISTRY.get(
        (
            binding.provider_id,
            binding.provider_version,
            binding.provider_capability_id,
        )
    )
    if row is None:
        return None
    payload = dict(row)
    return {
        **payload,
        "registry_entry_fingerprint": "sha256:" + fingerprint_mesh(payload),
    }


def _provider_observation_expected(
    binding: BlueprintBinding,
    registration: Mapping[str, str],
) -> dict[str, Any]:
    request_payload = {
        "schema_version": "worldguard.blueprint_provider_request.v1",
        "binding_id": binding.binding_id,
        "role": binding.role,
        "subject_element_id": binding.subject_element_id,
        "target_id": binding.target_id,
        "target_revision": binding.target_revision,
        "resource_id": binding.resource_id,
        "claim_boundary": binding.claim_boundary,
        "provider_id": binding.provider_id,
        "provider_version": binding.provider_version,
        "provider_capability_id": binding.provider_capability_id,
    }
    request_fingerprint = "sha256:" + fingerprint_mesh(request_payload)
    input_payload = {
        "target_id": binding.target_id,
        "target_revision": binding.target_revision,
        "resource_id": binding.resource_id,
        "locator": binding.locator,
        "claim_boundary": binding.claim_boundary,
    }
    input_fingerprint = "sha256:" + fingerprint_mesh(input_payload)
    result_payload = {
        "binding_id": binding.binding_id,
        "resource_id": binding.resource_id,
        "content_fingerprint": binding.content_fingerprint,
        "terminal_status": "current",
    }
    result_fingerprint = "sha256:" + fingerprint_mesh(result_payload)
    attestation_payload = {
        "schema_version": "worldguard.provider_execution_attestation.v1",
        "execution_owner_id": registration["execution_owner_id"],
        "execution_owner_version": registration["execution_owner_version"],
        "registry_entry_fingerprint": registration[
            "registry_entry_fingerprint"
        ],
        "request_fingerprint": request_fingerprint,
        "input_fingerprint": input_fingerprint,
        "result_fingerprint": result_fingerprint,
        "terminal_status": "current",
    }
    return {
        "request_fingerprint": request_fingerprint,
        "input_fingerprint": input_fingerprint,
        "result_fingerprint": result_fingerprint,
        "execution_attestation_fingerprint": "sha256:"
        + fingerprint_mesh(attestation_payload),
    }


def _provider_binding_observation(
    binding: BlueprintBinding,
    *,
    source_root: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Validate one independent provider-content result without trusting binding defaults."""

    registration = _provider_capability_registration(binding)
    if registration is None:
        return False, "provider_capability_unregistered", {
            "provider_id": binding.provider_id,
            "provider_version": binding.provider_version,
            "provider_capability_id": binding.provider_capability_id,
        }
    if not source_root:
        return False, "source_root_missing", {}
    path_text, separator, selector = binding.locator.partition("#")
    relative = Path(path_text)
    if relative.is_absolute():
        return False, "absolute_locator_forbidden", {}
    root = Path(source_root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return False, "locator_escapes_source_root", {}
    if not candidate.is_file():
        return False, "provider_result_missing", {}
    try:
        payload: Any = json.loads(candidate.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "provider_result_invalid_json", {}
    if separator:
        if not isinstance(payload, Mapping) or selector not in payload:
            return False, "provider_result_selector_missing", {}
        payload = payload[selector]
    if not isinstance(payload, Mapping):
        return False, "provider_result_not_object", {}
    result = dict(payload)
    required = {
        "schema_version",
        "observation_id",
        "binding_id",
        "role",
        "subject_element_id",
        "owner",
        "observation_mode",
        "provider_id",
        "provider_version",
        "provider_capability_id",
        "target_id",
        "target_revision",
        "resource_id",
        "content_fingerprint",
        "claim_boundary",
        "status",
        "execution_owner_id",
        "execution_owner_version",
        "registry_entry_fingerprint",
        "request_fingerprint",
        "input_fingerprint",
        "result_fingerprint",
        "terminal_status",
        "execution_attestation_fingerprint",
        "receipt_fingerprint",
    }
    missing = sorted(required.difference(result))
    unknown = sorted(set(result).difference(required))
    if missing or unknown:
        return False, "provider_result_shape_mismatch", {
            "missing_fields": missing,
            "unknown_fields": unknown,
        }
    receipt = str(result.pop("receipt_fingerprint", ""))
    expected_receipt = "sha256:" + fingerprint_mesh(result)
    if receipt != expected_receipt:
        return False, "provider_result_receipt_mismatch", {
            "expected": expected_receipt,
            "observed": receipt,
        }
    execution_expected = _provider_observation_expected(binding, registration)
    expected = {
        "schema_version": "worldguard.blueprint_provider_observation.v2",
        "observation_id": f"observation:{binding.binding_id}",
        "binding_id": binding.binding_id,
        "role": binding.role,
        "subject_element_id": binding.subject_element_id,
        "owner": binding.owner,
        "observation_mode": binding.observation_mode,
        "provider_id": binding.provider_id,
        "provider_version": binding.provider_version,
        "provider_capability_id": binding.provider_capability_id,
        "target_id": binding.target_id,
        "target_revision": binding.target_revision,
        "resource_id": binding.resource_id,
        "content_fingerprint": binding.content_fingerprint,
        "claim_boundary": binding.claim_boundary,
        "status": "current",
        "execution_owner_id": registration["execution_owner_id"],
        "execution_owner_version": registration["execution_owner_version"],
        "registry_entry_fingerprint": registration[
            "registry_entry_fingerprint"
        ],
        "terminal_status": "current",
        **execution_expected,
    }
    mismatches = {
        field_name: {"expected": expected_value, "observed": result.get(field_name)}
        for field_name, expected_value in expected.items()
        if result.get(field_name) != expected_value
    }
    if mismatches:
        reason = (
            "provider_result_stale"
            if set(mismatches).issubset({"target_revision", "status"})
            else "provider_result_identity_mismatch"
        )
        return False, reason, {"mismatches": mismatches}
    if binding.receipt_fingerprint != receipt:
        return False, "provider_result_binding_receipt_mismatch", {
            "expected": receipt,
            "observed": binding.receipt_fingerprint,
        }
    return True, "", {
        "observation_id": result["observation_id"],
        "provider_id": result["provider_id"],
        "provider_version": result["provider_version"],
        "provider_capability_id": result["provider_capability_id"],
        "execution_owner_id": result["execution_owner_id"],
        "registry_entry_fingerprint": result["registry_entry_fingerprint"],
        "execution_attestation_fingerprint": result[
            "execution_attestation_fingerprint"
        ],
        "receipt_fingerprint": receipt,
    }


def _local_binding_json_object(
    binding: BlueprintBinding,
    *,
    source_root: str,
) -> tuple[dict[str, Any] | None, str]:
    """Load one exact local JSON object selected by a binding locator."""

    if not source_root:
        return None, "source_root_missing"
    path_text, separator, selector = binding.locator.partition("#")
    relative = Path(path_text)
    if relative.is_absolute():
        return None, "absolute_locator_forbidden"
    root = Path(source_root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return None, "locator_escapes_source_root"
    if not candidate.is_file():
        return None, "resource_missing"
    try:
        payload: Any = json.loads(candidate.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "resource_invalid_json"
    if separator:
        if not isinstance(payload, Mapping) or selector not in payload:
            return None, "resource_selector_missing"
        payload = payload[selector]
    if not isinstance(payload, Mapping):
        return None, "resource_not_object"
    return dict(payload), ""


def _load_behavior_commitment_adapter_input(
    input_ref: BehaviorCommitmentInputRef,
    *,
    blueprint: WorldBlueprintContract,
) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
    """Observe one exact adapter input; external identity never becomes replay."""

    if input_ref.target_id != blueprint.target_id:
        return None, {}, "commitment_adapter_input_target_mismatch"
    if input_ref.target_revision != blueprint.target_revision:
        return None, {}, "commitment_adapter_input_revision_mismatch"
    if input_ref.observation_mode != "local_content":
        return None, {
            "input_id": input_ref.input_id,
            "input_kind": input_ref.input_kind,
            "observation_mode": input_ref.observation_mode,
        }, "commitment_adapter_input_not_replayable"
    if not blueprint.source_root:
        return None, {}, "source_root_missing"
    path_text, separator, selector = input_ref.locator.partition("#")
    relative = Path(path_text)
    if relative.is_absolute():
        return None, {}, "absolute_locator_forbidden"
    root = Path(blueprint.source_root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return None, {}, "locator_escapes_source_root"
    if not candidate.is_file():
        return None, {}, "commitment_adapter_input_missing"
    content = candidate.read_bytes()
    try:
        payload: Any = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, {}, "commitment_adapter_input_invalid_json"
    if separator:
        if not isinstance(payload, Mapping) or selector not in payload:
            return None, {}, "commitment_adapter_input_selector_missing"
        payload = payload[selector]
        content = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    if not isinstance(payload, Mapping):
        return None, {}, "commitment_adapter_input_not_object"
    observed_fingerprint = "sha256:" + hashlib.sha256(content).hexdigest()
    observation = {
        **input_ref.to_dict(),
        "observed_content_fingerprint": observed_fingerprint,
    }
    if observed_fingerprint != input_ref.content_fingerprint:
        return None, observation, "commitment_adapter_input_content_mismatch"
    return dict(payload), observation, ""


def _resolve_json_value(
    payload: Any,
    path: Sequence[str | int],
) -> tuple[Any, str]:
    current = payload
    for index, part in enumerate(path):
        if isinstance(part, int):
            if not isinstance(current, list) or part < 0 or part >= len(current):
                return None, f"index_unresolved:{index}:{part}"
            current = current[part]
        else:
            if not isinstance(current, Mapping) or part not in current:
                return None, f"field_unresolved:{index}:{part}"
            current = current[part]
    return current, ""


def _json_leaf_paths(
    payload: Any,
    *,
    prefix: tuple[str | int, ...] = (),
) -> tuple[tuple[str | int, ...], ...]:
    if isinstance(payload, Mapping):
        rows: list[tuple[str | int, ...]] = []
        for key in sorted(payload):
            rows.extend(_json_leaf_paths(payload[key], prefix=(*prefix, str(key))))
        return tuple(rows)
    if isinstance(payload, list):
        rows = []
        for index, value in enumerate(payload):
            rows.extend(_json_leaf_paths(value, prefix=(*prefix, index)))
        return tuple(rows)
    return (prefix,)


def _target_semantic_census_members(
    authority: TargetSemanticAuthority,
) -> list[dict[str, Any]]:
    """Project the exact semantic denominator carried by a signed census."""

    return [
        {
            "element_id": row.element_id,
            "element_kind": row.element_kind,
            "owner_node_id": row.owner_node_id,
            "required_guard_owner_id": row.required_guard_owner_id,
            "support_mode": row.support_mode,
            "binding_roles": sorted(
                responsibility.role
                for responsibility in row.binding_responsibilities
            ),
            "not_applicable_roles": sorted(
                responsibility.role
                for responsibility in row.not_applicable_responsibilities
            ),
            "derivation_ids": sorted(
                responsibility.derivation_id
                for responsibility in row.derivation_responsibilities
            ),
        }
        for row in authority.elements
    ]


def _execute_request_contract_commitment_adapter(
    blueprint: WorldBlueprintContract,
    registration: BehaviorCommitmentAdapterRegistration,
    payloads_by_kind: Mapping[str, tuple[dict[str, Any], ...]],
    input_observations: tuple[dict[str, Any], ...],
) -> tuple[
    tuple[BehaviorOutputCommitment, ...],
    tuple[TargetSemanticElementCommitment, ...],
    dict[str, Any],
    dict[str, Any],
    str,
    dict[str, Any],
]:
    """Replay the one current request-contract adapter from observed inputs."""

    observed_kinds = set(payloads_by_kind)
    unsupported = sorted(observed_kinds.difference(registration.supported_input_kinds))
    missing_kinds = sorted(
        set(registration.required_input_kinds).difference(observed_kinds)
    )
    duplicate_kinds = sorted(
        kind for kind, rows in payloads_by_kind.items() if len(rows) != 1
    )
    if unsupported or missing_kinds or duplicate_kinds:
        return (), (), {}, {}, "commitment_adapter_input_set_invalid", {
            "unsupported_input_kinds": unsupported,
            "missing_input_kinds": missing_kinds,
            "non_singleton_input_kinds": duplicate_kinds,
        }
    request_contract = payloads_by_kind["request_contract"][0]
    target_material = payloads_by_kind["target_material"][0]
    target_census_source_payload = payloads_by_kind[
        "target_object_census_source"
    ][0]
    target_semantic_payload = payloads_by_kind["target_semantic_authority"][0]
    target_census_payload = payloads_by_kind[
        "target_object_census_authority"
    ][0]
    required_request_fields = {
        "schema_version",
        "request_id",
        "authority_owner_id",
        "adapter_id",
        "adapter_version",
        "adapter_capability_id",
        "target_id",
        "target_revision",
        "claim_boundary",
        "behaviors",
        "semantic_authority",
        "object_census",
    }
    missing_fields = sorted(required_request_fields.difference(request_contract))
    unknown_fields = sorted(set(request_contract).difference(required_request_fields))
    if missing_fields or unknown_fields:
        return (), (), {}, {}, "commitment_adapter_request_shape_mismatch", {
            "missing_fields": missing_fields,
            "unknown_fields": unknown_fields,
        }
    expected_request_identity = {
        "schema_version": "worldguard.behavior_request_contract.v2",
        "authority_owner_id": blueprint.commitment_inventory.authority_owner_id,
        "adapter_id": registration.adapter_id,
        "adapter_version": registration.adapter_version,
        "adapter_capability_id": registration.capability_id,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "claim_boundary": blueprint.declared_boundary,
    }
    identity_mismatches = {
        field_name: {
            "expected": expected_value,
            "observed": request_contract.get(field_name),
        }
        for field_name, expected_value in expected_request_identity.items()
        if request_contract.get(field_name) != expected_value
    }
    if identity_mismatches:
        return (), (), {}, {}, "commitment_adapter_request_identity_mismatch", {
            "mismatches": identity_mismatches
        }
    behavior_rows = request_contract.get("behaviors")
    if not isinstance(behavior_rows, list) or not behavior_rows:
        return (), (), {}, {}, "commitment_adapter_request_behaviors_missing", {}
    commitments: list[BehaviorOutputCommitment] = []
    material_bindings: list[dict[str, Any]] = []
    all_required_material_ids: set[str] = set()
    allowed_behavior_fields = {
        "commitment_id",
        "behavior_id",
        "output_id",
        "node_id",
        "port_id",
        "owner_id",
        "input_ids",
        "required_contributor_element_ids",
        "required_material_ids",
    }
    try:
        for index, row in enumerate(behavior_rows):
            if not isinstance(row, Mapping):
                raise BlueprintError(
                    "WORLD_BLUEPRINT_COMMITMENT_ADAPTER_BEHAVIOR_INVALID",
                    "Request-contract behavior row must be an object.",
                    details={"index": index},
                )
            missing_behavior_fields = sorted(allowed_behavior_fields.difference(row))
            unknown_behavior_fields = sorted(set(row).difference(allowed_behavior_fields))
            if missing_behavior_fields or unknown_behavior_fields:
                raise BlueprintError(
                    "WORLD_BLUEPRINT_COMMITMENT_ADAPTER_BEHAVIOR_INVALID",
                    "Request-contract behavior row has a non-current shape.",
                    details={
                        "index": index,
                        "missing_fields": missing_behavior_fields,
                        "unknown_fields": unknown_behavior_fields,
                    },
                )
            required_material_ids = tuple(
                sorted(
                    _required_text(
                        value,
                        f"request_contract.behaviors[{index}].required_material_ids",
                    )
                    for value in row.get("required_material_ids", [])
                )
            )
            if not required_material_ids:
                raise BlueprintError(
                    "WORLD_BLUEPRINT_COMMITMENT_ADAPTER_MATERIALS_MISSING",
                    "Every request behavior requires target-material identities.",
                    details={"index": index},
                )
            missing_material_ids = sorted(
                set(required_material_ids).difference(target_material)
            )
            if missing_material_ids:
                raise BlueprintError(
                    "WORLD_BLUEPRINT_COMMITMENT_ADAPTER_MATERIAL_UNKNOWN",
                    "Request behavior names target material absent from the observed material input.",
                    details={
                        "index": index,
                        "missing_material_ids": missing_material_ids,
                    },
                )
            commitment_payload = {
                key: value for key, value in row.items() if key != "required_material_ids"
            }
            commitment = BehaviorOutputCommitment.from_dict(commitment_payload)
            commitments.append(commitment)
            all_required_material_ids.update(required_material_ids)
            material_bindings.append(
                {
                    "commitment_id": commitment.commitment_id,
                    "required_material_ids": list(required_material_ids),
                }
            )
    except (BlueprintError, TypeError) as exc:
        return (), (), {}, {}, "commitment_adapter_request_behavior_invalid", {
            "error": str(exc),
            "code": getattr(exc, "code", ""),
            "details": getattr(exc, "details", {}),
        }
    commitments_tuple = tuple(sorted(commitments, key=lambda row: row.commitment_id))
    commitment_ids = [row.commitment_id for row in commitments_tuple]
    output_ids = [row.output_id for row in commitments_tuple]
    if _duplicates(commitment_ids) or _duplicates(output_ids):
        return (), (), {}, {}, "commitment_adapter_result_identity_duplicate", {
            "duplicate_commitment_ids": _duplicates(commitment_ids),
            "duplicate_output_ids": _duplicates(output_ids),
        }

    semantic_authority_request = request_contract.get("semantic_authority")
    if not isinstance(semantic_authority_request, Mapping):
        return (), (), {}, {}, "target_semantic_request_invalid", {
            "reason": "semantic_authority_not_object"
        }
    allowed_semantic_request_fields = {
        "authority_id",
        "authority_owner_id",
        "required_node_ids",
        "required_element_ids",
        "required_guard_owner_ids",
    }
    semantic_request_missing = sorted(
        allowed_semantic_request_fields.difference(semantic_authority_request)
    )
    semantic_request_unknown = sorted(
        set(semantic_authority_request).difference(allowed_semantic_request_fields)
    )
    if semantic_request_missing or semantic_request_unknown:
        return (), (), {}, {}, "target_semantic_request_invalid", {
            "missing_fields": semantic_request_missing,
            "unknown_fields": semantic_request_unknown,
        }
    try:
        target_semantic_authority = TargetSemanticAuthority.from_dict(
            target_semantic_payload
        )
    except (BlueprintError, TypeError) as exc:
        return (), (), {}, {}, "target_semantic_authority_invalid", {
            "error": str(exc),
            "code": getattr(exc, "code", ""),
            "details": getattr(exc, "details", {}),
        }
    try:
        validated_census = validate_external_object_census_record(
            target_census_payload
        )
    except (ExternalObjectCensusError, TypeError, ValueError) as exc:
        return (), (), {}, {}, "target_object_census_authority_invalid", {
            "error": str(exc)
        }
    try:
        validated_census_source = validate_external_object_census_source(
            target_census_source_payload
        )
    except (ExternalObjectCensusError, TypeError, ValueError) as exc:
        return (), (), {}, {}, "target_object_census_authority_invalid", {
            "error": str(exc),
            "source_kind": "target_object_census_source",
        }
    request_census_source = request_contract.get("object_census")
    if request_census_source != target_census_source_payload:
        return (), (), {}, {}, "target_object_census_denominator_mismatch", {
            "request_source_mismatch": {
                "expected_fingerprint": "sha256:"
                + fingerprint_mesh(target_census_source_payload),
                "observed_fingerprint": "sha256:"
                + fingerprint_mesh(request_census_source),
            }
        }
    census_authority = validated_census["authority"]
    if not isinstance(census_authority, Mapping):
        return (), (), {}, {}, "target_object_census_authority_invalid", {
            "error": "validated object census authority is not an object"
        }
    observed_input_fingerprints = {
        str(row["input_kind"]): str(row["observed_content_fingerprint"])
        for row in input_observations
        if row.get("input_kind")
        in {
            "request_contract",
            "target_material",
            "target_object_census_source",
            "target_semantic_authority",
        }
    }
    census_identity_mismatches = {
        field_name: {"expected": expected, "observed": observed}
        for field_name, expected, observed in (
            ("target_id", blueprint.target_id, census_authority.get("target_id")),
            (
                "target_revision",
                blueprint.target_revision,
                census_authority.get("target_revision"),
            ),
            (
                "claim_boundary",
                blueprint.declared_boundary,
                census_authority.get("claim_boundary"),
            ),
        )
        if expected != observed
    }
    census_input_mismatches = {
        input_kind: {
            "expected": census_authority["input_fingerprints"].get(input_kind),
            "observed": observed_input_fingerprints.get(input_kind),
        }
        for input_kind in (
            "request_contract",
            "target_material",
            "target_object_census_source",
            "target_semantic_authority",
        )
        if census_authority["input_fingerprints"].get(input_kind)
        != observed_input_fingerprints.get(input_kind)
    }
    semantic_census_members = _target_semantic_census_members(
        target_semantic_authority
    )
    source_projection = validated_census_source["source"]
    source_required_element_ids = [
        row["element_id"] for row in source_projection["members"]
    ]
    source_identity_mismatches = {
        field_name: {"expected": expected, "observed": observed}
        for field_name, expected, observed in (
            (
                "authority_id",
                census_authority.get("authority_id"),
                source_projection.get("authority_id"),
            ),
            (
                "authority_revision",
                census_authority.get("authority_revision"),
                source_projection.get("authority_revision"),
            ),
            (
                "authority_owner_id",
                census_authority.get("authority_owner_id"),
                source_projection.get("authority_owner_id"),
            ),
            ("target_id", blueprint.target_id, source_projection.get("target_id")),
            (
                "target_revision",
                blueprint.target_revision,
                source_projection.get("target_revision"),
            ),
            (
                "claim_boundary",
                blueprint.declared_boundary,
                source_projection.get("claim_boundary"),
            ),
            (
                "object_claim_kind",
                census_authority.get("object_claim_kind"),
                source_projection.get("object_claim_kind"),
            ),
            (
                "discovery_mode",
                validated_census.get("discovery_mode"),
                source_projection.get("discovery_mode"),
            ),
            (
                "discovery_source_id",
                source_projection.get("source_id"),
                validated_census["discovery_receipt"].get("source_id"),
            ),
            (
                "discovery_source_owner_id",
                source_projection.get("source_owner_id"),
                validated_census["discovery_receipt"].get("source_owner_id"),
            ),
        )
        if expected != observed
    }
    source_denominator_mismatches = {
        field_name: {"expected": expected, "observed": observed}
        for field_name, expected, observed in (
            (
                "required_node_ids",
                census_authority.get("required_node_ids"),
                source_projection.get("required_node_ids"),
            ),
            (
                "required_guard_owner_ids",
                census_authority.get("required_guard_owner_ids"),
                source_projection.get("required_guard_owner_ids"),
            ),
            (
                "members",
                census_authority.get("members"),
                source_projection.get("members"),
            ),
        )
        if expected != observed
    }
    census_denominator_mismatches = {
        field_name: {"expected": expected, "observed": observed}
        for field_name, expected, observed in (
            (
                "required_node_ids",
                list(target_semantic_authority.required_node_ids),
                census_authority.get("required_node_ids"),
            ),
            (
                "required_guard_owner_ids",
                list(target_semantic_authority.required_guard_owner_ids),
                census_authority.get("required_guard_owner_ids"),
            ),
            (
                "members",
                semantic_census_members,
                census_authority.get("members"),
            ),
        )
        if expected != observed
    }
    if (
        census_identity_mismatches
        or census_input_mismatches
        or census_denominator_mismatches
        or source_identity_mismatches
        or source_denominator_mismatches
    ):
        return (), (), {}, {}, "target_object_census_denominator_mismatch", {
            "identity_mismatches": census_identity_mismatches,
            "input_fingerprint_mismatches": census_input_mismatches,
            "denominator_mismatches": census_denominator_mismatches,
            "source_identity_mismatches": source_identity_mismatches,
            "source_denominator_mismatches": source_denominator_mismatches,
            "authority_fingerprint": validated_census["authority_fingerprint"],
            "producer_descriptor_fingerprint": validated_census[
                "producer_descriptor_fingerprint"
            ],
        }
    semantic_identity_mismatches = {
        field_name: {"expected": expected, "observed": observed}
        for field_name, expected, observed in (
            (
                "authority_id",
                semantic_authority_request.get("authority_id"),
                target_semantic_authority.authority_id,
            ),
            (
                "authority_owner_id",
                semantic_authority_request.get("authority_owner_id"),
                target_semantic_authority.authority_owner_id,
            ),
            ("target_id", blueprint.target_id, target_semantic_authority.target_id),
            (
                "target_revision",
                blueprint.target_revision,
                target_semantic_authority.target_revision,
            ),
            (
                "claim_boundary",
                blueprint.declared_boundary,
                target_semantic_authority.claim_boundary,
            ),
        )
        if expected != observed
    }
    expected_node_ids = tuple(
        sorted(
            _required_text(value, "request.semantic_authority.required_node_ids")
            for value in semantic_authority_request.get("required_node_ids", [])
        )
    )
    expected_element_ids = tuple(
        sorted(
            _required_text(value, "request.semantic_authority.required_element_ids")
            for value in semantic_authority_request.get("required_element_ids", [])
        )
    )
    expected_guard_owner_ids = tuple(
        sorted(
            _required_text(
                value, "request.semantic_authority.required_guard_owner_ids"
            )
            for value in semantic_authority_request.get(
                "required_guard_owner_ids", []
            )
        )
    )
    authority_element_ids = tuple(
        sorted(row.element_id for row in target_semantic_authority.elements)
    )
    independent_source_request_mismatches = {
        field_name: {"expected": list(expected), "observed": list(observed)}
        for field_name, expected, observed in (
            (
                "required_node_ids",
                expected_node_ids,
                tuple(source_projection["required_node_ids"]),
            ),
            (
                "required_element_ids",
                expected_element_ids,
                tuple(source_required_element_ids),
            ),
            (
                "required_guard_owner_ids",
                expected_guard_owner_ids,
                tuple(source_projection["required_guard_owner_ids"]),
            ),
        )
        if expected != observed
    }
    semantic_denominator_mismatches = {
        field_name: {"expected": list(expected), "observed": list(observed)}
        for field_name, expected, observed in (
            (
                "required_node_ids",
                expected_node_ids,
                target_semantic_authority.required_node_ids,
            ),
            ("required_element_ids", expected_element_ids, authority_element_ids),
            (
                "required_guard_owner_ids",
                expected_guard_owner_ids,
                target_semantic_authority.required_guard_owner_ids,
            ),
        )
        if expected != observed
    }
    duplicate_semantic_request_ids = {
        "required_node_ids": _duplicates(expected_node_ids),
        "required_element_ids": _duplicates(expected_element_ids),
        "required_guard_owner_ids": _duplicates(expected_guard_owner_ids),
    }
    duplicate_semantic_request_ids = {
        key: value
        for key, value in duplicate_semantic_request_ids.items()
        if value
    }
    if (
        semantic_identity_mismatches
        or semantic_denominator_mismatches
        or independent_source_request_mismatches
        or duplicate_semantic_request_ids
        or not expected_node_ids
        or not expected_element_ids
    ):
        return (), (), {}, {}, "target_semantic_denominator_mismatch", {
            "identity_mismatches": semantic_identity_mismatches,
            "denominator_mismatches": semantic_denominator_mismatches,
            "independent_source_request_mismatches": (
                independent_source_request_mismatches
            ),
            "duplicate_ids": duplicate_semantic_request_ids,
        }

    semantic_owner_mismatches: list[dict[str, Any]] = []
    for row in target_semantic_authority.elements:
        owner_guard, _ = _blueprint_native_owner(row.native_semantic)
        actual_owner = owner_guard or "not_applicable"
        actual_executor_id = (
            EXECUTOR_REGISTRY[owner_guard].binding.executor_id
            if owner_guard in EXECUTOR_REGISTRY
            else "worldguard.world-element.applicability.v1"
        )
        actual_executor_version = actual_executor_id.rsplit(".", 1)[-1]
        mismatches = {
            field_name: {"expected": expected, "observed": observed}
            for field_name, expected, observed in (
                (
                    "required_guard_owner_id",
                    actual_owner,
                    row.required_guard_owner_id,
                ),
                (
                    "required_executor_id",
                    actual_executor_id,
                    row.required_executor_id,
                ),
                (
                    "required_executor_version",
                    actual_executor_version,
                    row.required_executor_version,
                ),
            )
            if expected != observed
        }
        native_responsibilities = [
            binding
            for binding in row.binding_responsibilities
            if binding.role == "native_result"
        ]
        expected_binding_owner = owner_guard or "worldguard"
        if len(native_responsibilities) != 1:
            mismatches["native_result_responsibility_count"] = {
                "expected": 1,
                "observed": len(native_responsibilities),
            }
        else:
            native_responsibility = native_responsibilities[0]
            for field_name, expected, observed in (
                (
                    "native_binding_id",
                    row.native_semantic.observation_binding_id,
                    native_responsibility.binding_id,
                ),
                (
                    "native_binding_owner",
                    expected_binding_owner,
                    native_responsibility.owner_id,
                ),
                (
                    "native_binding_provider_id",
                    row.native_semantic.provider_id,
                    native_responsibility.provider_id,
                ),
                (
                    "native_binding_provider_version",
                    row.native_semantic.provider_version,
                    native_responsibility.provider_version,
                ),
            ):
                if expected != observed:
                    mismatches[field_name] = {
                        "expected": expected,
                        "observed": observed,
                    }
        if mismatches:
            semantic_owner_mismatches.append(
                {"element_id": row.element_id, "mismatches": mismatches}
            )
    if semantic_owner_mismatches:
        return (), (), {}, {}, "target_semantic_owner_registry_mismatch", {
            "mismatches": semantic_owner_mismatches
        }

    authority_elements = {
        row.element_id: row for row in target_semantic_authority.elements
    }
    assertion_results: list[dict[str, Any]] = []
    asserted_source_paths: list[tuple[str | int, ...]] = []
    assertion_failures: list[dict[str, Any]] = []
    for assertion in target_semantic_authority.material_assertions:
        asserted_source_paths.append(assertion.source_path)
        target_row = authority_elements.get(assertion.target_element_id)
        source_value, source_error = _resolve_json_value(
            target_material, assertion.source_path
        )
        semantic_value: Any = None
        semantic_error = "target_element_unknown"
        if target_row is not None:
            semantic_value, semantic_error = _resolve_json_value(
                target_row.native_semantic.to_dict(), assertion.semantic_path
            )
        result = {
            **assertion.to_dict(),
            "source_value": source_value,
            "semantic_value": semantic_value,
            "source_error": source_error,
            "semantic_error": semantic_error,
            "matched": (
                not source_error
                and not semantic_error
                and source_value == semantic_value
            ),
        }
        assertion_results.append(result)
        if not result["matched"]:
            assertion_failures.append(result)

    required_material_leaf_paths: list[tuple[str | int, ...]] = []
    for material_id in sorted(all_required_material_ids):
        required_material_leaf_paths.extend(
            _json_leaf_paths(target_material[material_id], prefix=(material_id,))
        )
    duplicate_asserted_paths = _duplicates(asserted_source_paths)
    missing_asserted_paths = sorted(
        set(required_material_leaf_paths).difference(asserted_source_paths),
        key=lambda path: json.dumps(path, ensure_ascii=False),
    )
    unexpected_asserted_paths = sorted(
        set(asserted_source_paths).difference(required_material_leaf_paths),
        key=lambda path: json.dumps(path, ensure_ascii=False),
    )
    if (
        assertion_failures
        or duplicate_asserted_paths
        or missing_asserted_paths
        or unexpected_asserted_paths
    ):
        return (), (), {}, {}, "target_semantic_material_mismatch", {
            "assertion_failures": assertion_failures,
            "duplicate_source_paths": [list(path) for path in duplicate_asserted_paths],
            "missing_source_paths": [list(path) for path in missing_asserted_paths],
            "unexpected_source_paths": [
                list(path) for path in unexpected_asserted_paths
            ],
        }

    adapter_result = {
        "schema_version": "worldguard.behavior_commitment_adapter_result.v2",
        "inventory_id": blueprint.commitment_inventory.inventory_id,
        "authority_owner_id": blueprint.commitment_inventory.authority_owner_id,
        "adapter_id": registration.adapter_id,
        "adapter_version": registration.adapter_version,
        "adapter_capability_id": registration.capability_id,
        "registration_fingerprint": registration.registration_fingerprint,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "claim_boundary": blueprint.declared_boundary,
        "request_id": str(request_contract.get("request_id", "")),
        "input_observations": list(input_observations),
        "commitments": [row.to_dict() for row in commitments_tuple],
        "material_bindings": sorted(
            material_bindings, key=lambda row: row["commitment_id"]
        ),
        "target_semantic_authority": {
            "authority_id": target_semantic_authority.authority_id,
            "authority_owner_id": target_semantic_authority.authority_owner_id,
            "required_node_ids": list(target_semantic_authority.required_node_ids),
            "required_element_ids": list(authority_element_ids),
            "required_guard_owner_ids": list(
                target_semantic_authority.required_guard_owner_ids
            ),
            "element_commitments": [
                row.result_projection() for row in target_semantic_authority.elements
            ],
            "material_assertions": assertion_results,
            "authority_fingerprint": "sha256:"
            + fingerprint_mesh(target_semantic_authority.to_dict()),
        },
        "target_object_census_authority": {
            "authority_id": census_authority["authority_id"],
            "authority_revision": census_authority["authority_revision"],
            "authority_owner_id": census_authority["authority_owner_id"],
            "object_claim_kind": census_authority["object_claim_kind"],
            "required_node_ids": list(census_authority["required_node_ids"]),
            "required_element_ids": [
                row["element_id"] for row in census_authority["members"]
            ],
            "required_guard_owner_ids": list(
                census_authority["required_guard_owner_ids"]
            ),
            "members": list(census_authority["members"]),
            "member_count": len(census_authority["members"]),
            "authority_fingerprint": validated_census["authority_fingerprint"],
            "producer_descriptor_fingerprint": validated_census[
                "producer_descriptor_fingerprint"
            ],
            "signature_valid": True,
            "coverage_complete": True,
            "discovery_mode": validated_census["discovery_mode"],
            "discovery_receipt": validated_census["discovery_receipt"],
            "independent_discovery_current": bool(
                validated_census["independent_discovery_declared"]
                and source_projection["discovery_mode"]
                == "independent_raw_target_request"
            ),
            "census_source_id": source_projection["source_id"],
            "census_source_owner_id": source_projection["source_owner_id"],
            "census_source_fingerprint": observed_input_fingerprints[
                "target_object_census_source"
            ],
        },
        "terminal_status": "PASS",
    }
    result_fingerprint = "sha256:" + fingerprint_mesh(adapter_result)
    request_payload = {
        "schema_version": "worldguard.behavior_commitment_adapter_request.v2",
        "inventory_reference": blueprint.commitment_inventory.to_dict(),
        "registration_fingerprint": registration.registration_fingerprint,
    }
    receipt_payload = {
        "schema_version": "worldguard.behavior_commitment_adapter_execution.v2",
        "execution_id": f"commitment-adapter:{blueprint.commitment_inventory.inventory_id}",
        "execution_owner_id": registration.execution_owner_id,
        "execution_owner_version": registration.execution_owner_version,
        "executor_id": registration.executor_id,
        "executor_version": registration.executor_version,
        "adapter_id": registration.adapter_id,
        "adapter_version": registration.adapter_version,
        "adapter_capability_id": registration.capability_id,
        "registration_fingerprint": registration.registration_fingerprint,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "request_fingerprint": "sha256:" + fingerprint_mesh(request_payload),
        "input_fingerprint": "sha256:" + fingerprint_mesh(list(input_observations)),
        "result_fingerprint": result_fingerprint,
        "terminal_status": "PASS",
        "claim_boundary": blueprint.declared_boundary,
    }
    terminal_receipt = {
        **receipt_payload,
        "receipt_fingerprint": "sha256:" + fingerprint_mesh(receipt_payload),
    }
    return (
        commitments_tuple,
        target_semantic_authority.elements,
        adapter_result,
        terminal_receipt,
        "",
        {},
    )


def _load_behavior_commitment_inventory(
    blueprint: WorldBlueprintContract,
    *,
    expected_cache_only: bool = False,
) -> tuple[
    tuple[BehaviorOutputCommitment, ...],
    tuple[TargetSemanticElementCommitment, ...],
    str,
    dict[str, Any],
]:
    """Replay current adapter inputs and compare the cache to owner output."""

    reference = blueprint.commitment_inventory
    reference_mismatches = {
        field_name: {"expected": expected, "observed": observed}
        for field_name, expected, observed in (
            ("target_id", blueprint.target_id, reference.target_id),
            ("target_revision", blueprint.target_revision, reference.target_revision),
            ("claim_boundary", blueprint.declared_boundary, reference.claim_boundary),
        )
        if expected != observed
    }
    if reference_mismatches:
        return (), (), "commitment_inventory_identity_mismatch", {
            "mismatches": reference_mismatches
        }
    registration = BEHAVIOR_COMMITMENT_ADAPTER_REGISTRY.resolve(
        reference.adapter_id,
        reference.adapter_version,
        reference.adapter_capability_id,
    )
    if registration is None:
        return (), (), "commitment_adapter_unregistered", {
            "adapter_id": reference.adapter_id,
            "adapter_version": reference.adapter_version,
            "adapter_capability_id": reference.adapter_capability_id,
        }
    duplicate_input_ids = _duplicates([row.input_id for row in reference.input_refs])
    if duplicate_input_ids:
        return (), (), "commitment_adapter_input_id_duplicate", {
            "duplicate_input_ids": duplicate_input_ids
        }
    payload_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    input_observations: list[dict[str, Any]] = []
    for input_ref in reference.input_refs:
        payload, observation, error = _load_behavior_commitment_adapter_input(
            input_ref,
            blueprint=blueprint,
        )
        if error:
            return (), (), error, {
                "input_id": input_ref.input_id,
                "input_kind": input_ref.input_kind,
                **observation,
            }
        assert payload is not None
        payload_rows[input_ref.input_kind].append(payload)
        input_observations.append(observation)
    (
        commitments,
        target_semantic_commitments,
        adapter_result,
        terminal_receipt,
        replay_error,
        replay_evidence,
    ) = (
        _execute_request_contract_commitment_adapter(
            blueprint,
            registration,
            {
                kind: tuple(rows)
                for kind, rows in sorted(payload_rows.items())
            },
            tuple(sorted(input_observations, key=lambda row: row["input_id"])),
        )
    )
    if replay_error:
        return (), (), replay_error, replay_evidence

    expected_cache = {
        "schema_version": "worldguard.behavior_commitment_inventory.v3",
        "inventory_id": reference.inventory_id,
        "authority_owner_id": reference.authority_owner_id,
        "adapter_id": reference.adapter_id,
        "adapter_version": reference.adapter_version,
        "adapter_capability_id": reference.adapter_capability_id,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "input_refs": [row.to_dict() for row in reference.input_refs],
        "claim_boundary": blueprint.declared_boundary,
        "adapter_result": adapter_result,
        "terminal_receipt": terminal_receipt,
    }
    if expected_cache_only:
        return commitments, target_semantic_commitments, "", {
            "expected_cache": expected_cache
        }
    if not blueprint.source_root:
        return commitments, target_semantic_commitments, "source_root_missing", {
            "registration_fingerprint": registration.registration_fingerprint,
            "terminal_receipt_fingerprint": terminal_receipt[
                "receipt_fingerprint"
            ],
        }
    relative = Path(reference.locator)
    if relative.is_absolute():
        return commitments, target_semantic_commitments, "absolute_locator_forbidden", {}
    root = Path(blueprint.source_root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return commitments, target_semantic_commitments, "locator_escapes_source_root", {}
    if not candidate.is_file():
        return commitments, target_semantic_commitments, "commitment_inventory_missing", {}
    try:
        raw: Any = json.loads(candidate.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return commitments, target_semantic_commitments, "commitment_inventory_invalid_json", {}
    if not isinstance(raw, Mapping):
        return commitments, target_semantic_commitments, "commitment_inventory_not_object", {}
    observed_cache = dict(raw)
    if observed_cache != expected_cache:
        return commitments, target_semantic_commitments, "commitment_adapter_result_mismatch", {
            "expected_cache_fingerprint": "sha256:"
            + fingerprint_mesh(expected_cache),
            "observed_cache_fingerprint": "sha256:"
            + fingerprint_mesh(observed_cache),
            "registration_fingerprint": registration.registration_fingerprint,
            "terminal_receipt_fingerprint": terminal_receipt[
                "receipt_fingerprint"
            ],
        }
    return commitments, target_semantic_commitments, "", {
        "inventory_id": reference.inventory_id,
        "authority_owner_id": reference.authority_owner_id,
        "adapter_id": reference.adapter_id,
        "adapter_version": reference.adapter_version,
        "adapter_capability_id": reference.adapter_capability_id,
        "registration_fingerprint": registration.registration_fingerprint,
        "input_refs": [row.to_dict() for row in reference.input_refs],
        "adapter_result_fingerprint": terminal_receipt["result_fingerprint"],
        "terminal_receipt_fingerprint": terminal_receipt["receipt_fingerprint"],
        "target_semantic_authority_fingerprint": adapter_result[
            "target_semantic_authority"
        ]["authority_fingerprint"],
        "required_node_ids": adapter_result["target_semantic_authority"][
            "required_node_ids"
        ],
        "required_element_ids": adapter_result["target_semantic_authority"][
            "required_element_ids"
        ],
        "required_guard_owner_ids": adapter_result["target_semantic_authority"][
            "required_guard_owner_ids"
        ],
        "target_object_census_authority": adapter_result[
            "target_object_census_authority"
        ],
    }


def compile_behavior_commitment_inventory_cache(
    blueprint: WorldBlueprintContract | Mapping[str, Any],
) -> dict[str, Any]:
    """Compile the sole current adapter replay cache without reading that cache."""

    if not isinstance(blueprint, WorldBlueprintContract):
        blueprint = WorldBlueprintContract.from_dict(blueprint)
    _, _, error, evidence = _load_behavior_commitment_inventory(
        blueprint,
        expected_cache_only=True,
    )
    if error:
        raise BlueprintError(
            "WORLD_BLUEPRINT_COMMITMENT_CACHE_COMPILE_BLOCKED",
            "The current registered commitment adapter could not compile its replay cache.",
            details={"reason": error, **evidence},
        )
    return dict(evidence["expected_cache"])


_BLUEPRINT_RCC8 = {"DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPI", "NTPPI"}


def _blueprint_native_owner(
    semantic: NativeSemanticRef,
) -> tuple[str, str]:
    """Return the current Guard owner and semantic route, or an explicit N/A."""

    if semantic.element_kind in {"event", "state", "transition"}:
        return "EventGuard", "event"
    if semantic.element_kind == "agent":
        return "AgentGuard", "agent"
    if semantic.element_kind == "resource":
        return "ResourceGuard", "resource"
    if semantic.element_kind == "causal_link":
        return "CausalGuard", "causal"
    if semantic.element_kind == "conflict":
        return "ConflictGuard", "conflict"
    if semantic.element_kind == "norm":
        return "NormGuard", "norm"
    if (
        semantic.element_kind == "relation"
        and str(semantic.semantic_fields.get("relation", "")).upper()
        in _BLUEPRINT_RCC8
    ):
        return "SpaceGuard", "spatial"
    return "", ""


def _blueprint_native_field_dispositions(
    semantic: NativeSemanticRef,
) -> list[dict[str, Any]]:
    """Account for every declared native field exactly once."""

    owner_guard, _ = _blueprint_native_owner(semantic)
    rows: list[dict[str, Any]] = []
    for field_id in sorted(NATIVE_SEMANTIC_FIELDS[semantic.element_kind]):
        disposition = NATIVE_SEMANTIC_FIELD_DISPOSITIONS[semantic.element_kind][
            field_id
        ]
        if disposition == "conditional_owner_input":
            disposition = "owner_input" if owner_guard else "not_applicable"
        row: dict[str, Any] = {
            "field_id": field_id,
            "disposition": disposition,
            "declared_value": semantic.semantic_fields[field_id],
            "owner_guard": owner_guard,
        }
        owner_path = _NATIVE_SEMANTIC_OWNER_INPUT_PATHS.get(
            semantic.element_kind, {}
        ).get(field_id)
        if disposition in {
            "owner_input",
            "owner_input_with_unverified_semantics",
        } and owner_path:
            row["owner_input_path"] = owner_path
        if disposition == "owner_input_with_unverified_semantics":
            row["evaluated_claim_scope"] = (
                _NATIVE_SEMANTIC_EVALUATED_CLAIM_SCOPES[semantic.element_kind]
            )
            row["unverified_claim_scope"] = (
                _NATIVE_SEMANTIC_UNVERIFIED_FIELD_SCOPES[semantic.element_kind][
                    field_id
                ]
            )
        elif disposition == "unverified_boundary":
            row["reason"] = (
                "The current owner evaluates the declared cause/effect graph, "
                "not the truth of the mechanism description."
            )
        elif disposition == "request_control":
            row["receipt_path"] = "requested_claim_scope"
        elif disposition == "not_applicable":
            row["reason"] = (
                "No current domain Guard owns this generic/container field."
            )
        rows.append(row)
    return rows


def _blueprint_native_inputs(semantic: NativeSemanticRef) -> dict[str, Any]:
    """Adapt one typed World element into the current pure owner input contract."""

    fields = semantic.semantic_fields
    kind = semantic.element_kind
    if kind == "event":
        return {
            "events": [
                {
                    "event_id": semantic.native_object_id,
                    "at": fields["at"],
                    "terminates": list(fields["terminates"]),
                    "initiates": list(fields["initiates"]),
                    "releases": list(fields["releases"]),
                }
            ],
            "event_model": {},
        }
    if kind == "state":
        return {
            "event_model": {
                "states": [
                    {
                        "state_id": fields["state_id"],
                        "initial": fields["initial"],
                        "terminal": fields["terminal"],
                    }
                ]
            },
            "events": [],
        }
    if kind == "transition":
        source_state = str(fields["source_state"])
        target_state = str(fields["target_state"])
        states = [
            {
                "state_id": source_state,
                "initial": fields["source_initial"],
                "terminal": fields["target_terminal"] if source_state == target_state else False,
            }
        ]
        if target_state != source_state:
            states.append(
                {
                    "state_id": target_state,
                    "initial": False,
                    "terminal": fields["target_terminal"],
                }
            )
        return {
            "event_model": {
                "states": states,
                "transitions": [
                    {
                        "transition_id": semantic.native_object_id,
                        "source_state": fields["source_state"],
                        "target_state": fields["target_state"],
                        "guard": fields["guard"],
                        "effect": fields["effect"],
                    }
                ],
                "guard_values": {str(fields["guard"]): fields["guard_value"]},
            },
            "events": [],
        }
    if kind == "agent":
        agent_id = str(fields["agent_id"])
        return {
            "beliefs": {
                agent_id: {
                    "agent_id": agent_id,
                    "beliefs": list(fields["beliefs"]),
                    "desires": list(fields["desires"]),
                    "intentions": list(fields["intentions"]),
                }
            },
            "agent_model": {
                "conflicting_intentions": list(fields["conflicting_intentions"]),
            },
        }
    if kind == "resource":
        return {
            "resources": {
                "inventory": [
                    {
                        "resource_id": fields["resource_id"],
                        "quantity": fields["quantity"],
                        "unit": fields["unit"],
                    }
                ]
            }
        }
    if kind == "causal_link":
        cause_ids = [str(value) for value in fields["cause_ids"]]
        effect_id = str(fields["effect_id"])
        variables = list(dict.fromkeys([*cause_ids, effect_id]))
        graph = [[cause_id, effect_id] for cause_id in cause_ids]
        return {
            "causal_model": {
                "variables": variables,
                "graph": graph,
                "claim_scope": "graph_only",
            }
        }
    if kind == "conflict":
        return {
            "game_model": {
                "players": list(fields["participant_ids"]),
                "issue": fields["issue"],
                "actions": list(fields["actions"]),
                "states": list(fields["resolution_states"]),
                "transitions": [dict(value) for value in fields["transitions"]],
                "payoffs": [dict(value) for value in fields["payoffs"]],
            }
        }
    if kind == "norm":
        condition = str(fields["condition"])
        return {
            "norms": [
                {
                    "norm_id": semantic.native_object_id,
                    "modality": str(fields["modality"]),
                    "subject_id": str(fields["subject_id"]),
                    "action": str(fields["action"]),
                    "condition": condition,
                }
            ],
            "facts": [dict(value) for value in fields["facts"]],
        }
    if kind == "relation":
        participants = [str(value) for value in fields["participant_ids"]]
        return {
            "spatial_relations": [
                {
                    "relation": str(fields["relation"]).upper(),
                    "x": participants[0],
                    "y": participants[1],
                }
            ]
        }
    return {}


def _blueprint_native_unverified_boundaries(
    semantic: NativeSemanticRef,
) -> list[dict[str, Any]]:
    """Retain declared fields that the current native owner does not execute."""

    rows = [
        {
            "boundary_id": f"boundary:{semantic.semantic_id}:{row['field_id']}",
            "field_id": row["field_id"],
            "status": "unverified",
            "declared_value": row["declared_value"],
            "evaluated_claim_scope": row["evaluated_claim_scope"],
            "unverified_claim_scope": row["unverified_claim_scope"],
            "owner_guard": row["owner_guard"],
            "reason": (
                "The owner preserves and checks the declared field only within "
                "the evaluated static scope; the broader semantic truth remains unverified."
            ),
        }
        for row in _blueprint_native_field_dispositions(semantic)
        if row["disposition"] == "owner_input_with_unverified_semantics"
    ]
    if semantic.element_kind == "causal_link":
        rows.append(
            {
            "boundary_id": f"boundary:{semantic.semantic_id}:mechanism",
            "field_id": "mechanism",
            "status": "unverified",
            "declared_value": str(semantic.semantic_fields["mechanism"]),
            "requested_claim_scope": str(
                semantic.semantic_fields["mechanism_claim_scope"]
            ),
            "owner_guard": "CausalGuard",
            "reason": (
                "Current CausalGuard executes the stable cause/effect graph but "
                "does not execute or verify the declared mechanism description."
            ),
            }
        )
    return rows


def _blueprint_owner_terminal_status(
    structural_status: GuardStatus,
    semantic_status: SemanticStatus,
) -> str:
    if structural_status == GuardStatus.FAIL or semantic_status == SemanticStatus.FAIL:
        return "FAIL"
    if (
        structural_status == GuardStatus.GAP
        or semantic_status in {SemanticStatus.GAP, SemanticStatus.NOT_RUN}
    ):
        return "GAP"
    if (
        structural_status == GuardStatus.BOUNDARY_EXCEEDED
        or semantic_status == SemanticStatus.BOUNDARY_ONLY
    ):
        return "BOUNDARY_EXCEEDED"
    if structural_status == GuardStatus.PASS and semantic_status == SemanticStatus.PASS:
        return "PASS"
    return "GAP"


def _behavior_expected_subset(
    expected: Any,
    observed: Any,
    *,
    path: str,
) -> list[dict[str, Any]]:
    """Return deterministic source-independent behavior-oracle mismatches."""

    if isinstance(expected, Mapping):
        if not isinstance(observed, Mapping):
            return [{"path": path, "expected": dict(expected), "observed": observed}]
        mismatches: list[dict[str, Any]] = []
        for key in sorted(expected):
            child_path = f"{path}.{key}" if path else str(key)
            if key not in observed:
                mismatches.append(
                    {"path": child_path, "expected": expected[key], "observed": "<missing>"}
                )
            else:
                mismatches.extend(
                    _behavior_expected_subset(
                        expected[key], observed[key], path=child_path
                    )
                )
        return mismatches
    if isinstance(expected, list):
        if not isinstance(observed, list) or expected != observed:
            return [{"path": path, "expected": expected, "observed": observed}]
        return []
    if expected != observed:
        return [{"path": path, "expected": expected, "observed": observed}]
    return []


def _prove_blueprint_admission_cases(
    task_purpose: BlueprintTaskPurpose,
) -> dict[str, Any]:
    """Replay exact parser-level counterexamples owned by WorldBlueprint.

    Guard-native known-bad cases remain under the selected Guard's purpose
    proof.  Admission-bad cases instead prove that an invalid typed world
    element cannot cross the sole current WorldBlueprint parser boundary.
    """

    observations: list[dict[str, Any]] = []
    for case in task_purpose.behavior_cases:
        if case.case_kind != "admission_bad":
            continue
        candidate = case.inputs["world_element"]
        observed_status = "ACCEPTED"
        observed_code = ""
        observed_details: dict[str, Any] = {}
        try:
            WorldElement.from_dict(candidate)
        except BlueprintError as exc:
            observed_status = "REJECTED"
            observed_code = exc.code
            observed_details = dict(exc.details)
        detail_mismatches = _behavior_expected_subset(
            case.expected_output,
            observed_details,
            path="details",
        )
        passed = bool(
            observed_status == case.expected_status
            and observed_code == case.expected_code
            and not detail_mismatches
        )
        observations.append(
            {
                "case_id": case.case_id,
                "case_kind": case.case_kind,
                "failure_id": case.failure_id,
                "native_oracle_id": case.oracle_id,
                "expected_status": case.expected_status,
                "observed_status": observed_status,
                "expected_code": case.expected_code,
                "observed_code": observed_code,
                "expected_details": case.expected_output,
                "observed_details": observed_details,
                "detail_mismatches": detail_mismatches,
                "passed": passed,
            }
        )
    payload = {
        "schema_version": "worldguard.blueprint_admission_case_proof.v1",
        "status": (
            "pass"
            if observations and all(row["passed"] for row in observations)
            else "fail"
        ),
        "declaration_id": task_purpose.declaration_id,
        "case_count": len(observations),
        "observations": observations,
    }
    return {
        **payload,
        "proof_fingerprint": "sha256:" + fingerprint_mesh(payload),
    }


def _execute_blueprint_native_semantic(
    blueprint: WorldBlueprintContract,
    element: WorldElement,
    binding: BlueprintBinding | None,
    observed_payload: Mapping[str, Any] | None,
    *,
    observation_error: str = "",
    admission_findings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Ask the current domain owner to issue one exact terminal receipt."""

    semantic = element.native_semantic
    findings: list[dict[str, Any]] = [dict(row) for row in admission_findings]
    if semantic is None:
        findings.append(
            {
                "code": "WORLD_BLUEPRINT_NATIVE_SEMANTIC_MISSING",
                "message": "The native semantic object is unavailable for owner execution.",
            }
        )
    if binding is None:
        findings.append(
            {
                "code": "WORLD_BLUEPRINT_NATIVE_OBSERVATION_BINDING_MISSING",
                "message": "The owner execution has no observation binding.",
            }
        )
    elif binding.observation_mode != "local_content":
        findings.append(
            {
                "code": "WORLD_BLUEPRINT_NATIVE_EXECUTION_INPUT_NOT_LOCAL",
                "message": "Native owner execution requires exact local content.",
                "evidence": {"observation_mode": binding.observation_mode},
            }
        )
    if observation_error:
        findings.append(
            {
                "code": "WORLD_BLUEPRINT_NATIVE_EXECUTION_INPUT_UNAVAILABLE",
                "message": "The native owner input could not be loaded exactly.",
                "evidence": {"reason": observation_error},
            }
        )
    if semantic is not None and observed_payload is not None:
        expected_payload = semantic.fingerprint_payload()
        if dict(observed_payload) != expected_payload:
            findings.append(
                {
                    "code": "WORLD_BLUEPRINT_NATIVE_EXECUTION_INPUT_MISMATCH",
                    "message": "Observed native content differs from the modeled owner input.",
                    "evidence": {
                        "expected_fingerprint": semantic.content_fingerprint,
                        "observed_fingerprint": "sha256:"
                        + fingerprint_mesh(dict(observed_payload)),
                    },
                }
            )

    owner_guard, requested_semantic = (
        _blueprint_native_owner(semantic) if semantic is not None else ("", "")
    )
    owner_inputs = (
        _blueprint_native_inputs(semantic)
        if semantic is not None and owner_guard
        else {}
    )
    task_purpose = semantic.task_purpose if semantic is not None else None
    if owner_guard and task_purpose is None:
        findings.append(
            {
                "code": "WORLD_BLUEPRINT_TASK_PURPOSE_MISSING",
                "message": (
                    "An applicable native element requires one target-local purpose "
                    "and behavior-case contract before owner execution."
                ),
                "evidence": {"owner_guard": owner_guard, "element_id": element.element_id},
            }
        )
    elif owner_guard and task_purpose is not None:
        boundary_mismatches = sorted(
            row.case_id
            for row in task_purpose.behavior_cases
            if row.claim_boundary != blueprint.declared_boundary
        )
        if task_purpose.boundary != blueprint.declared_boundary or boundary_mismatches:
            findings.append(
                {
                    "code": "WORLD_BLUEPRINT_TASK_PURPOSE_BOUNDARY_MISMATCH",
                    "message": "Task purpose and behavior cases must share the exact target boundary.",
                    "evidence": {
                        "purpose_boundary": task_purpose.boundary,
                        "blueprint_boundary": blueprint.declared_boundary,
                        "case_ids": boundary_mismatches,
                    },
                }
            )
    field_dispositions = (
        _blueprint_native_field_dispositions(semantic)
        if semantic is not None
        else []
    )
    unverified_boundaries = (
        _blueprint_native_unverified_boundaries(semantic)
        if semantic is not None and owner_guard
        else []
    )
    executor_id = (
        EXECUTOR_REGISTRY[owner_guard].binding.executor_id
        if owner_guard in EXECUTOR_REGISTRY
        else "worldguard.world-element.applicability.v1"
    )
    executor_version = executor_id.rsplit(".", 1)[-1]
    request_payload = {
        "schema_version": "worldguard.blueprint_native_owner_request.v1",
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "blueprint_id": blueprint.blueprint_id,
        "element_id": element.element_id,
        "semantic_id": semantic.semantic_id if semantic is not None else "",
        "native_object_id": semantic.native_object_id if semantic is not None else "",
        "native_schema_id": semantic.native_schema_id if semantic is not None else "",
        "semantic_fingerprint": semantic.content_fingerprint if semantic is not None else "",
        "owner_guard": owner_guard,
        "executor_id": executor_id,
        "executor_version": executor_version,
        "native_provider_id": semantic.provider_id if semantic is not None else "",
        "native_provider_version": (
            semantic.provider_version if semantic is not None else ""
        ),
        "observation_binding_id": binding.binding_id if binding is not None else "",
        "observation_content_fingerprint": (
            binding.content_fingerprint if binding is not None else ""
        ),
        "field_dispositions": field_dispositions,
        "task_purpose_fingerprint": (
            task_purpose.purpose_fingerprint if task_purpose is not None else ""
        ),
        "behavior_case_fingerprints": (
            [row.case_fingerprint for row in task_purpose.behavior_cases]
            if task_purpose is not None
            else []
        ),
        "claim_boundary": blueprint.declared_boundary,
    }
    request_fingerprint = "sha256:" + fingerprint_mesh(request_payload)
    input_payload = {
        "observed_native_object": dict(observed_payload or {}),
        "owner_inputs": owner_inputs,
    }
    input_fingerprint = "sha256:" + fingerprint_mesh(input_payload)
    structural_result: dict[str, Any] = {}
    semantic_result: dict[str, Any] = {}
    execution_disposition = "not_run"
    terminal_status = "GAP"
    requested_claim_scope = (
        str(semantic.semantic_fields["mechanism_claim_scope"])
        if semantic is not None and semantic.element_kind == "causal_link"
        else ""
    )
    evaluated_claim_scope = ""
    licensed_claim_scope = ""
    qualified_subscope = ""
    evaluated_claim_scopes: list[str] = []
    purpose_contract_result: dict[str, Any] = {}
    admission_case_proof_result: dict[str, Any] = {}
    behavior_case_result: dict[str, Any] = {}

    if not findings and task_purpose is not None:
        admission_cases = [
            row
            for row in task_purpose.behavior_cases
            if row.case_kind == "admission_bad"
        ]
        if admission_cases:
            admission_case_proof_result = _prove_blueprint_admission_cases(
                task_purpose
            )
            if admission_case_proof_result["status"] != "pass":
                findings.append(
                    {
                        "code": "WORLD_BLUEPRINT_ADMISSION_CASE_PROOF_FAILED",
                        "message": (
                            "A task-local parser admission counterexample did not "
                            "match the WorldBlueprint-owned oracle."
                        ),
                        "evidence": admission_case_proof_result,
                    }
                )

    if not findings and semantic is not None and not owner_guard:
        execution_disposition = "not_applicable"
        terminal_status = "NOT_APPLICABLE"
        semantic_result = {
            "status": "NOT_APPLICABLE",
            "reason": "No current domain Guard owns this container/generic element kind.",
            "element_kind": semantic.element_kind,
        }
    elif not findings and semantic is not None:
        contract_id = f"world-blueprint:{blueprint.blueprint_id}:{element.element_id}"
        run_id = f"world-blueprint:{blueprint.target_revision}"
        assert task_purpose is not None
        declaration = task_purpose.to_guard_declaration(
            guard=owner_guard,
            task_contract_id=contract_id,
            run_id=run_id,
            model_instance_id=blueprint.target_id,
        )
        parent_contract = GuardContract.from_dict(
            {
                "contract_id": contract_id,
                "schema_version": "worldguard.contract.v1",
                "run_id": run_id,
                "claim": {
                    "claim_id": f"native-owner:{element.element_id}",
                    "text": f"Evaluate one {requested_semantic} world element.",
                    "target_guards": [owner_guard],
                    "requested_semantics": [requested_semantic],
                },
                "world_model": {
                    "model_id": blueprint.target_id,
                    "model_version": blueprint.target_revision,
                    "entities": {},
                    "relations": {},
                    "assumptions": [],
                    "scope_limits": [blueprint.declared_boundary],
                },
                "inputs": owner_inputs,
                "guard_purpose_declarations": [declaration],
            }
        )
        try:
            contract = parent_contract.for_guard(owner_guard)
            purpose_binding = verify_guard_candidate_purpose_contract(
                contract, owner_guard
            )
            purpose_contract_result = purpose_binding.to_dict()
            structural = GUARD_RUNNERS[owner_guard](contract)
            semantic_status, semantic_findings, consumed_inputs, outputs = (
                EXECUTOR_REGISTRY[owner_guard].execute(contract)
            )
        except GuardCandidatePurposeError as exc:
            findings.append(
                {
                    "code": exc.code,
                    "message": str(exc),
                    "evidence": {
                        "owner_guard": owner_guard,
                        "executor_id": executor_id,
                        **exc.details,
                    },
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            findings.append(
                {
                    "code": "WORLD_BLUEPRINT_NATIVE_OWNER_EXECUTION_ERROR",
                    "message": "The current domain owner could not evaluate the adapted native input.",
                    "evidence": {
                        "owner_guard": owner_guard,
                        "executor_id": executor_id,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                }
            )
        else:
            execution_disposition = "executed"
            evaluated_claim_scopes = [
                _NATIVE_SEMANTIC_EVALUATED_CLAIM_SCOPES[semantic.element_kind]
            ]
            structural_result = structural.to_dict()
            semantic_result = {
                "status": semantic_status.value,
                "findings": semantic_findings,
                "consumed_inputs": consumed_inputs,
                "outputs": outputs,
            }
            terminal_status = _blueprint_owner_terminal_status(
                structural.status,
                semantic_status,
            )
            findings.extend(structural.errors)
            findings.extend(semantic_findings)
            target_cases = [
                row for row in task_purpose.behavior_cases if row.inputs == owner_inputs
            ]
            target_case = target_cases[0] if len(target_cases) == 1 else None
            case_mismatches: list[dict[str, Any]] = []
            if target_case is None:
                terminal_status = "GAP"
                findings.append(
                    {
                        "code": "WORLD_BLUEPRINT_TARGET_BEHAVIOR_CASE_UNBOUND",
                        "message": (
                            "The current target input must match exactly one declared "
                            "known-good or counterexample behavior case."
                        ),
                        "evidence": {
                            "matching_case_ids": [row.case_id for row in target_cases],
                            "target_input_fingerprint": "sha256:"
                            + fingerprint_mesh(owner_inputs),
                        },
                    }
                )
                behavior_case_result = {
                    "status": "GAP",
                    "matching_case_ids": [row.case_id for row in target_cases],
                }
            elif target_case.case_kind == "known_good":
                case_mismatches.extend(
                    _behavior_expected_subset(
                        target_case.expected_output,
                        outputs,
                        path="output",
                    )
                )
            else:
                observed_codes = sorted(
                    {
                        str(row.get("code", ""))
                        for row in [*structural.errors, *semantic_findings]
                        if str(row.get("code", ""))
                    }
                )
                if (
                    terminal_status != target_case.expected_status
                    or target_case.expected_code not in observed_codes
                ):
                    case_mismatches.append(
                        {
                            "path": "failure_oracle",
                            "expected": {
                                "status": target_case.expected_status,
                                "code": target_case.expected_code,
                            },
                            "observed": {
                                "status": terminal_status,
                                "codes": observed_codes,
                            },
                        }
                    )
            if (
                target_case is not None
                and target_case.state_effect_disposition == "applicable"
            ):
                case_mismatches.extend(
                    _behavior_expected_subset(
                        target_case.pre_state,
                        owner_inputs,
                        path="pre_state",
                    )
                )
                case_mismatches.extend(
                    _behavior_expected_subset(
                        target_case.post_state,
                        outputs,
                        path="post_state",
                    )
                )
                case_mismatches.extend(
                    _behavior_expected_subset(
                        target_case.effects,
                        outputs,
                        path="effects",
                    )
                )
            if target_case is not None:
                behavior_case_result = {
                    "case_id": target_case.case_id,
                    "case_kind": target_case.case_kind,
                    "case_fingerprint": target_case.case_fingerprint,
                    "oracle_id": target_case.oracle_id,
                    "state_effect_disposition": target_case.state_effect_disposition,
                    "state_effect_reason": target_case.state_effect_reason,
                    "mismatches": case_mismatches,
                    "status": "PASS" if not case_mismatches else "FAIL",
                }
                if case_mismatches:
                    terminal_status = "FAIL"
                    findings.append(
                        {
                            "code": "WORLD_BLUEPRINT_TARGET_BEHAVIOR_ORACLE_MISMATCH",
                            "message": (
                                "Target owner output/state/effect/failure does not match "
                                "the source-independent behavior-case oracle."
                            ),
                            "evidence": behavior_case_result,
                        }
                    )
            if semantic.element_kind == "causal_link":
                evaluated_claim_scope = "graph_only"
                if (
                    structural.status == GuardStatus.PASS
                    and semantic_status == SemanticStatus.PASS
                ):
                    if requested_claim_scope == "graph_only":
                        licensed_claim_scope = "graph_only"
                    else:
                        qualified_subscope = "graph_only"
            if (
                semantic.element_kind == "causal_link"
                and semantic.semantic_fields["mechanism_claim_scope"]
                == "mechanism_truth"
                and terminal_status == "PASS"
            ):
                terminal_status = "GAP"
                findings.append(
                    {
                        "code": "WORLD_BLUEPRINT_CAUSAL_MECHANISM_UNVERIFIED",
                        "message": (
                            "The current CausalGuard qualified the stable graph, "
                            "but did not verify the declared mechanism as causal truth."
                        ),
                        "evidence": {
                            "semantic_id": semantic.semantic_id,
                            "requested_claim_scope": "mechanism_truth",
                            "evaluated_claim_scope": evaluated_claim_scope,
                            "qualified_subscope": qualified_subscope,
                        },
                    }
                )

    if unverified_boundaries:
        unverified_boundaries = [
            {
                **row,
                **(
                    {"evaluated_claim_scope": evaluated_claim_scope}
                    if evaluated_claim_scope
                    else {}
                ),
                **(
                    {"licensed_claim_scope": licensed_claim_scope}
                    if licensed_claim_scope
                    else {}
                ),
                **(
                    {"qualified_subscope": qualified_subscope}
                    if qualified_subscope
                    else {}
                ),
            }
            for row in unverified_boundaries
        ]

    result_payload = {
        "structural_result": structural_result,
        "semantic_result": semantic_result,
        "terminal_status": terminal_status,
        "findings": findings,
        "field_dispositions": field_dispositions,
        "evaluated_claim_scopes": evaluated_claim_scopes,
        "purpose_contract_result": purpose_contract_result,
        "behavior_case_result": behavior_case_result,
    }
    if admission_case_proof_result:
        result_payload["admission_case_proof_result"] = (
            admission_case_proof_result
        )
    if requested_claim_scope:
        result_payload["requested_claim_scope"] = requested_claim_scope
    if evaluated_claim_scope:
        result_payload["evaluated_claim_scope"] = evaluated_claim_scope
    if licensed_claim_scope:
        result_payload["licensed_claim_scope"] = licensed_claim_scope
    if qualified_subscope:
        result_payload["qualified_subscope"] = qualified_subscope
    if unverified_boundaries:
        result_payload["unverified_boundaries"] = unverified_boundaries
    result_fingerprint = "sha256:" + fingerprint_mesh(result_payload)
    payload = {
        "schema_version": "worldguard.blueprint_native_execution.v2",
        "execution_id": f"native-execution:{blueprint.blueprint_id}:{element.element_id}",
        "execution_disposition": execution_disposition,
        "owner_guard": owner_guard,
        "executor_id": executor_id,
        "executor_version": executor_version,
        "native_provider_id": semantic.provider_id if semantic is not None else "",
        "native_provider_version": (
            semantic.provider_version if semantic is not None else ""
        ),
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "element_id": element.element_id,
        "semantic_id": semantic.semantic_id if semantic is not None else "",
        "native_object_id": semantic.native_object_id if semantic is not None else "",
        "native_schema_id": semantic.native_schema_id if semantic is not None else "",
        "semantic_fingerprint": semantic.content_fingerprint if semantic is not None else "",
        "observation_binding_id": binding.binding_id if binding is not None else "",
        "observation_content_fingerprint": binding.content_fingerprint if binding is not None else "",
        "request_fingerprint": request_fingerprint,
        "input_fingerprint": input_fingerprint,
        "result_fingerprint": result_fingerprint,
        "claim_boundary": blueprint.declared_boundary,
        "status": terminal_status,
        "terminal_status": terminal_status,
        "structural_result": structural_result,
        "semantic_result": semantic_result,
        "findings": findings,
        "field_dispositions": field_dispositions,
        "evaluated_claim_scopes": evaluated_claim_scopes,
        "purpose_contract_result": purpose_contract_result,
        "behavior_case_result": behavior_case_result,
    }
    if admission_case_proof_result:
        payload["admission_case_proof_result"] = admission_case_proof_result
    if requested_claim_scope:
        payload["requested_claim_scope"] = requested_claim_scope
    if evaluated_claim_scope:
        payload["evaluated_claim_scope"] = evaluated_claim_scope
    if licensed_claim_scope:
        payload["licensed_claim_scope"] = licensed_claim_scope
    if qualified_subscope:
        payload["qualified_subscope"] = qualified_subscope
    if unverified_boundaries:
        payload["unverified_boundaries"] = unverified_boundaries
    return {**payload, "receipt_fingerprint": "sha256:" + fingerprint_mesh(payload)}


_CROSS_ARTIFACT_PROJECTION_CAPABILITIES: dict[
    tuple[str, str, str], dict[str, str]
] = {
    (
        "worldguard.flowguard.blueprint-projection",
        "v1",
        "worldguard.flowguard.target-blueprint.v1",
    ): {
        "execution_owner_id": "worldguard.flowguard.blueprint-projection-owner",
        "execution_owner_version": "v1",
        "producer_identity_fingerprint": "sha256:"
        + fingerprint_mesh(
            {
                "provider_id": "worldguard.flowguard.blueprint-projection",
                "provider_version": "v1",
                "provider_capability_id": "worldguard.flowguard.target-blueprint.v1",
                "execution_owner_id": "worldguard.flowguard.blueprint-projection-owner",
                "execution_owner_version": "v1",
            }
        ),
    }
}


def _cross_artifact_required_source_ids(
    blueprint: WorldBlueprintContract,
) -> tuple[str, ...]:
    source_ids: set[str] = {
        f"blueprint:{blueprint.blueprint_id}",
        f"commitment-inventory:{blueprint.commitment_inventory.inventory_id}",
    }
    for node in blueprint.nodes:
        source_ids.add(f"node:{node.node_id}")
        source_ids.update(
            f"port:{node.node_id}:input:{port.port_id}" for port in node.input_ports
        )
        source_ids.update(
            f"port:{node.node_id}:output:{port.port_id}" for port in node.output_ports
        )
        source_ids.update(
            f"mapping:{node.node_id}:child-input:{row.mapping_id}"
            for row in node.child_input_mappings
        )
        source_ids.update(
            f"mapping:{node.node_id}:element-input:{row.mapping_id}"
            for row in node.element_input_mappings
        )
        source_ids.update(
            f"mapping:{node.node_id}:child-output:{row.mapping_id}"
            for row in node.child_output_mappings
        )
        source_ids.update(
            f"derivation:{node.node_id}:{row.derivation_id}"
            for row in node.output_derivations
        )
    for element in blueprint.elements:
        source_ids.add(f"element:{element.element_id}")
        source_ids.update(
            f"dependency:{element.element_id}:{row.dependency_id}"
            for row in element.dependencies
        )
        semantic = element.native_semantic
        if semantic is None or semantic.task_purpose is None:
            continue
        purpose = semantic.task_purpose
        source_ids.add(f"purpose:{element.element_id}:{purpose.declaration_id}")
        for case in purpose.behavior_cases:
            source_ids.add(f"case:{element.element_id}:{case.case_id}")
            source_ids.add(
                f"oracle:{element.element_id}:{case.case_id}:{case.oracle_id}"
            )
    source_ids.update(f"binding:{row.binding_id}" for row in blueprint.bindings)
    source_ids.update(f"input:{row.input_id}" for row in blueprint.declared_inputs)
    source_ids.update(f"output:{row.output_id}" for row in blueprint.declared_outputs)
    source_ids.update(f"declared-gap:{row.gap_id}" for row in blueprint.declared_gaps)
    return tuple(sorted(source_ids))


def _cross_artifact_projection_gap(
    blueprint: WorldBlueprintContract,
    *,
    code: str,
    message: str,
    severity: GuardStatus,
    evidence: dict[str, Any],
) -> BlueprintGap:
    return _gap(
        blueprint,
        code=code,
        message=message,
        severity=severity,
        layer_id="cross_artifact_projection",
        evidence=evidence,
    )


def _validate_cross_artifact_projection(
    blueprint: WorldBlueprintContract,
    projection: CrossArtifactProjectionResult,
    *,
    native_report_fingerprint: str,
    native_domain_qualified: bool,
) -> tuple[BlueprintGap, ...]:
    expected_required = _cross_artifact_required_source_ids(blueprint)
    expected_registration = _CROSS_ARTIFACT_PROJECTION_CAPABILITIES.get(
        (
            projection.provider_id,
            projection.provider_version,
            projection.provider_capability_id,
        )
    )
    errors: list[dict[str, Any]] = []
    boundary_error = False
    if expected_registration is None:
        boundary_error = True
        errors.append(
            {
                "reason": "provider_capability_unregistered",
                "provider_id": projection.provider_id,
                "provider_version": projection.provider_version,
                "provider_capability_id": projection.provider_capability_id,
            }
        )
    elif (
        projection.execution_owner_id
        != expected_registration["execution_owner_id"]
        or projection.execution_owner_version
        != expected_registration["execution_owner_version"]
        or projection.producer_identity_fingerprint
        != expected_registration["producer_identity_fingerprint"]
    ):
        boundary_error = True
        errors.append(
            {
                "reason": "execution_owner_mismatch",
                "expected": expected_registration,
                "observed": {
                    "execution_owner_id": projection.execution_owner_id,
                    "execution_owner_version": projection.execution_owner_version,
                    "producer_identity_fingerprint": (
                        projection.producer_identity_fingerprint
                    ),
                },
            }
        )
    identity_expected = {
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "claim_boundary": blueprint.declared_boundary,
        "source_blueprint_fingerprint": "sha256:"
        + blueprint.blueprint_fingerprint,
        "source_report_fingerprint": "sha256:" + native_report_fingerprint,
    }
    identity_observed = {
        key: getattr(projection, key) for key in identity_expected
    }
    if identity_observed != identity_expected:
        errors.append(
            {
                "reason": "source_identity_mismatch",
                "expected": identity_expected,
                "observed": identity_observed,
            }
        )
    if projection.required_source_ids != expected_required:
        errors.append(
            {
                "reason": "required_source_denominator_mismatch",
                "missing_source_ids": sorted(
                    set(expected_required).difference(projection.required_source_ids)
                ),
                "extra_source_ids": sorted(
                    set(projection.required_source_ids).difference(expected_required)
                ),
            }
        )
    projected = set(projection.projected_source_ids)
    unresolved = set(projection.unresolved_source_ids)
    required = set(projection.required_source_ids)
    if projected.intersection(unresolved) or projected.union(unresolved) != required:
        errors.append(
            {
                "reason": "projection_set_closure_invalid",
                "overlap_source_ids": sorted(projected.intersection(unresolved)),
                "unaccounted_source_ids": sorted(
                    required.difference(projected.union(unresolved))
                ),
                "foreign_source_ids": sorted(
                    projected.union(unresolved).difference(required)
                ),
            }
        )
    # The target-object projection is an in-memory audit composition, not a
    # transport envelope.  Keep the complete current blueprint payload and a
    # closed disposition for every source id; a source-id-only projection can
    # be re-signed after silently dropping target semantics.
    expected_dispositions = [
        {
            "source_id": source_id,
            "status": "projected" if source_id in projected else "unresolved",
        }
        for source_id in expected_required
    ]
    expected_normalized_payload = {
        "schema_version": "worldguard.flowguard.blueprint_projection_payload.v2",
        "blueprint": blueprint.fingerprint_payload(),
        "source_dispositions": expected_dispositions,
    }
    payload_shape_valid = (
        set(projection.normalized_payload)
        == set(expected_normalized_payload)
        and projection.normalized_payload.get("schema_version")
        == expected_normalized_payload["schema_version"]
        and projection.normalized_payload.get("blueprint")
        == expected_normalized_payload["blueprint"]
    )
    observed_dispositions = projection.normalized_payload.get("source_dispositions")
    if not isinstance(observed_dispositions, list):
        payload_shape_valid = False
        observed_dispositions = []
    if observed_dispositions != expected_dispositions:
        payload_shape_valid = False
    if not payload_shape_valid:
        errors.append(
            {
                "reason": "normalized_payload_lossless_blueprint_mismatch",
                "expected_blueprint_fingerprint": "sha256:"
                + blueprint.current_fingerprint(),
                "observed_blueprint_fingerprint": (
                    "sha256:"
                    + fingerprint_mesh(projection.normalized_payload.get("blueprint"))
                    if isinstance(projection.normalized_payload.get("blueprint"), Mapping)
                    else ""
                ),
                "expected_source_dispositions": expected_dispositions,
                "observed_source_dispositions": observed_dispositions,
            }
        )
    expected_payload_fingerprint = "sha256:" + fingerprint_mesh(
        projection.normalized_payload
    )
    if projection.normalized_payload_fingerprint != expected_payload_fingerprint:
        errors.append(
            {
                "reason": "normalized_payload_fingerprint_mismatch",
                "expected": expected_payload_fingerprint,
                "observed": projection.normalized_payload_fingerprint,
            }
        )
    expected_receipt_payload = {
        "schema_version": "worldguard.cross_artifact_projection_receipt.v2",
        "projection_id": projection.projection_id,
        "provider_id": projection.provider_id,
        "provider_version": projection.provider_version,
        "provider_capability_id": projection.provider_capability_id,
        "execution_owner_id": projection.execution_owner_id,
        "execution_owner_version": projection.execution_owner_version,
        "producer_identity_fingerprint": (
            projection.producer_identity_fingerprint
        ),
        "projection_result_fingerprint": "sha256:"
        + fingerprint_mesh(projection.evidence_payload()),
        "terminal_status": projection.status,
    }
    expected_receipt_fingerprint = "sha256:" + fingerprint_mesh(
        expected_receipt_payload
    )
    if projection.terminal_receipt_payload != expected_receipt_payload:
        errors.append(
            {
                "reason": "terminal_receipt_payload_mismatch",
                "expected": expected_receipt_payload,
                "observed": projection.terminal_receipt_payload,
            }
        )
    if projection.terminal_receipt_fingerprint != expected_receipt_fingerprint:
        errors.append(
            {
                "reason": "terminal_receipt_fingerprint_mismatch",
                "expected": expected_receipt_fingerprint,
                "observed": projection.terminal_receipt_fingerprint,
            }
        )
    status_matches_sets = (
        projection.status == "proven" and not unresolved and projected == required
    ) or (
        projection.status in {"gap", "boundary"} and bool(unresolved)
    )
    if not status_matches_sets:
        errors.append(
            {
                "reason": "terminal_status_set_mismatch",
                "status": projection.status,
                "unresolved_source_ids": sorted(unresolved),
            }
        )
    if projection.status == "proven" and not native_domain_qualified:
        errors.append({"reason": "native_domain_not_qualified"})

    if errors:
        return (
            _cross_artifact_projection_gap(
                blueprint,
                code="WORLD_BLUEPRINT_CROSS_ARTIFACT_RESULT_INVALID",
                message=(
                    "The supplied cross-artifact projection result is not current, "
                    "complete, or receipt-valid."
                ),
                severity=(
                    GuardStatus.BOUNDARY_EXCEEDED
                    if boundary_error
                    else GuardStatus.GAP
                ),
                evidence={
                    "projection_id": projection.projection_id,
                    "errors": errors,
                },
            ),
        )
    if projection.status != "proven":
        return (
            _cross_artifact_projection_gap(
                blueprint,
                code="WORLD_BLUEPRINT_CROSS_ARTIFACT_UNRESOLVED",
                message="The independent projection owner reported unresolved source ids.",
                severity=(
                    GuardStatus.BOUNDARY_EXCEEDED
                    if projection.status == "boundary"
                    else GuardStatus.GAP
                ),
                evidence={
                    "projection_id": projection.projection_id,
                    "unresolved_source_ids": list(
                        projection.unresolved_source_ids
                    ),
                },
            ),
        )
    return ()


def check_world_blueprint(
    blueprint: WorldBlueprintContract | Mapping[str, Any],
    *,
    cross_artifact_projection: CrossArtifactProjectionResult
    | Mapping[str, Any]
    | None = None,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> WorldBlueprintReport:
    if not isinstance(blueprint, WorldBlueprintContract):
        blueprint = WorldBlueprintContract.from_dict(blueprint)

    gaps: list[BlueprintGap] = []
    node_ids = [node.node_id for node in blueprint.nodes]
    element_ids = [element.element_id for element in blueprint.elements]
    binding_ids = [binding.binding_id for binding in blueprint.bindings]
    semantic_ids = [
        element.native_semantic.semantic_id
        for element in blueprint.elements
        if element.native_semantic is not None
    ]
    native_object_ids = [
        element.native_semantic.native_object_id
        for element in blueprint.elements
        if element.native_semantic is not None
    ]
    nodes = {node.node_id: node for node in blueprint.nodes}
    elements = {element.element_id: element for element in blueprint.elements}
    bindings = {binding.binding_id: binding for binding in blueprint.bindings}
    (
        behavior_commitments,
        target_semantic_commitments,
        commitment_inventory_error,
        commitment_inventory_evidence,
    ) = _load_behavior_commitment_inventory(blueprint)
    if commitment_inventory_error:
        commitment_gap_code = {
            "commitment_adapter_result_mismatch": (
                "WORLD_BLUEPRINT_COMMITMENT_ADAPTER_RESULT_MISMATCH"
            ),
            "target_semantic_material_mismatch": (
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_MATERIAL_MISMATCH"
            ),
            "target_semantic_denominator_mismatch": (
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_DENOMINATOR_MISMATCH"
            ),
            "target_semantic_owner_registry_mismatch": (
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_OWNER_REGISTRY_MISMATCH"
            ),
            "target_semantic_authority_invalid": (
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_AUTHORITY_INVALID"
            ),
            "target_semantic_request_invalid": (
                "WORLD_BLUEPRINT_TARGET_SEMANTIC_REQUEST_INVALID"
            ),
            "target_object_census_authority_invalid": (
                "WORLD_BLUEPRINT_OBJECT_CENSUS_AUTHORITY_INVALID"
            ),
            "target_object_census_denominator_mismatch": (
                "WORLD_BLUEPRINT_OBJECT_CENSUS_DENOMINATOR_MISMATCH"
            ),
        }.get(
            commitment_inventory_error,
            "WORLD_BLUEPRINT_COMMITMENT_INVENTORY_NOT_CURRENT",
        )
        gaps.append(
            _gap(
                blueprint,
                code=commitment_gap_code,
                message="The behavior/output denominator did not match a current closed-adapter replay.",
                severity=(
                    GuardStatus.FAIL
                    if commitment_inventory_error
                    in {
                        "absolute_locator_forbidden",
                        "locator_escapes_source_root",
                        "commitment_inventory_identity_mismatch",
                        "commitment_adapter_result_mismatch",
                        "commitment_adapter_input_content_mismatch",
                        "commitment_adapter_request_identity_mismatch",
                        "target_semantic_material_mismatch",
                        "target_semantic_denominator_mismatch",
                        "target_semantic_owner_registry_mismatch",
                        "target_semantic_authority_invalid",
                        "target_semantic_request_invalid",
                        "target_object_census_authority_invalid",
                        "target_object_census_denominator_mismatch",
                    }
                    else GuardStatus.GAP
                ),
                layer_id="identity_inventory",
                evidence={
                    "reason": commitment_inventory_error,
                    **commitment_inventory_evidence,
                },
            )
        )

    object_census_source = commitment_inventory_evidence.get(
        "target_object_census_authority", {}
    )
    object_census_authority_fingerprint = str(
        object_census_source.get("authority_fingerprint", "")
    )
    object_census_producer_fingerprint = str(
        object_census_source.get("producer_descriptor_fingerprint", "")
    )
    trusted_census_authorities = set(
        _normalized_trust_fingerprints(
            trusted_object_census_authority_fingerprints,
            "trusted_object_census_authority_fingerprints",
        )
    )
    trusted_census_producers = set(
        _normalized_trust_fingerprints(
            trusted_object_census_producer_descriptor_fingerprints,
            "trusted_object_census_producer_descriptor_fingerprints",
        )
    )
    object_census_authority_valid = bool(
        object_census_source.get("signature_valid")
    )
    object_census_independent_discovery_current = bool(
        object_census_source.get("independent_discovery_current")
    )
    object_census_exact_authority_trusted = bool(
        object_census_authority_fingerprint in trusted_census_authorities
    )
    object_census_producer_trusted = bool(
        object_census_producer_fingerprint in trusted_census_producers
    )
    object_census_producer_revision_licensed = bool(
        object_census_authority_valid
        and object_census_independent_discovery_current
        and object_census_producer_trusted
    )
    object_census_authority_licensed = bool(
        object_census_authority_valid
        and (
            object_census_exact_authority_trusted
            or object_census_producer_revision_licensed
        )
    )
    object_claim_kind = str(object_census_source.get("object_claim_kind", ""))
    integrated_object_claim = object_claim_kind == "integrated_target"
    census_required_nodes = set(object_census_source.get("required_node_ids", []))
    census_required_elements = set(
        object_census_source.get("required_element_ids", [])
    )
    census_missing_node_ids = sorted(census_required_nodes.difference(node_ids))
    census_unexpected_node_ids = sorted(set(node_ids).difference(census_required_nodes))
    census_missing_element_ids = sorted(
        census_required_elements.difference(element_ids)
    )
    census_unexpected_element_ids = sorted(
        set(element_ids).difference(census_required_elements)
    )
    object_census_coverage_complete = bool(
        object_census_source.get("coverage_complete")
        and not census_missing_node_ids
        and not census_unexpected_node_ids
        and not census_missing_element_ids
        and not census_unexpected_element_ids
    )
    commitment_ids = [row.commitment_id for row in behavior_commitments]
    commitment_output_ids = [row.output_id for row in behavior_commitments]
    for duplicate in _duplicates(commitment_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_COMMITMENT_ID_DUPLICATE",
                message="Independent behavior commitment ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                evidence={"commitment_id": duplicate},
            )
        )
    for duplicate in _duplicates(commitment_output_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_COMMITMENT_OUTPUT_DUPLICATE",
                message="One externally visible output must have one primary behavior commitment owner.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                evidence={"output_id": duplicate},
            )
        )

    target_semantics_by_element_id = {
        row.element_id: row for row in target_semantic_commitments
    }
    required_target_node_ids = set(
        commitment_inventory_evidence.get("required_node_ids", [])
    )
    required_target_element_ids = set(
        commitment_inventory_evidence.get("required_element_ids", [])
    )
    if target_semantic_commitments:
        if set(node_ids) != required_target_node_ids:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_TARGET_NODE_DENOMINATOR_MISMATCH",
                    message="Blueprint nodes do not exactly match the independently replayed target-node denominator.",
                    severity=GuardStatus.FAIL,
                    layer_id="identity_inventory",
                    evidence={
                        "missing_node_ids": sorted(
                            required_target_node_ids.difference(node_ids)
                        ),
                        "unexpected_node_ids": sorted(
                            set(node_ids).difference(required_target_node_ids)
                        ),
                        **commitment_inventory_evidence,
                    },
                )
            )
        if set(element_ids) != required_target_element_ids:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_TARGET_ELEMENT_DENOMINATOR_MISMATCH",
                    message="Blueprint elements do not exactly match the independently replayed target-element denominator.",
                    severity=GuardStatus.FAIL,
                    layer_id="identity_inventory",
                    evidence={
                        "missing_element_ids": sorted(
                            required_target_element_ids.difference(element_ids)
                        ),
                        "unexpected_element_ids": sorted(
                            set(element_ids).difference(required_target_element_ids)
                        ),
                        **commitment_inventory_evidence,
                    },
                )
            )

        for element_id, target_commitment in sorted(
            target_semantics_by_element_id.items()
        ):
            element = elements.get(element_id)
            if element is None:
                continue
            semantic_mismatches: dict[str, Any] = {}
            if element.kind != target_commitment.element_kind:
                semantic_mismatches["element_kind"] = {
                    "expected": target_commitment.element_kind,
                    "observed": element.kind,
                }
            if element.owner_node_id != target_commitment.owner_node_id:
                semantic_mismatches["owner_node_id"] = {
                    "expected": target_commitment.owner_node_id,
                    "observed": element.owner_node_id,
                }
            if element.native_semantic is None:
                semantic_mismatches["native_semantic"] = {
                    "expected": target_commitment.native_semantic.to_dict(),
                    "observed": None,
                }
            elif (
                element.native_semantic.to_dict()
                != target_commitment.native_semantic.to_dict()
            ):
                semantic_mismatches["native_semantic"] = {
                    "expected_fingerprint": "sha256:"
                    + fingerprint_mesh(target_commitment.native_semantic.to_dict()),
                    "observed_fingerprint": "sha256:"
                    + fingerprint_mesh(element.native_semantic.to_dict()),
                }
            if semantic_mismatches:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_TARGET_SEMANTIC_MISMATCH",
                        message="Blueprint semantic content does not match the independently replayed target commitment.",
                        severity=GuardStatus.FAIL,
                        layer_id="domain_semantics",
                        depth=_node_depth(nodes, target_commitment.owner_node_id),
                        node_id=target_commitment.owner_node_id,
                        element_id=element_id,
                        evidence=semantic_mismatches,
                    )
                )

            expected_binding_responsibilities = sorted(
                (
                    row.to_dict()
                    for row in target_commitment.binding_responsibilities
                ),
                key=lambda row: row["binding_id"],
            )
            observed_binding_responsibilities = sorted(
                (
                    {
                        "binding_id": binding.binding_id,
                        "role": binding.role,
                        "owner_id": binding.owner,
                        "resource_id": binding.resource_id,
                        "locator": binding.locator,
                        "provider_id": binding.provider_id,
                        "provider_version": binding.provider_version,
                        "provider_capability_id": binding.provider_capability_id,
                        "observation_mode": binding.observation_mode,
                    }
                    for binding in blueprint.bindings
                    if binding.subject_element_id == element_id
                ),
                key=lambda row: row["binding_id"],
            )
            if observed_binding_responsibilities != expected_binding_responsibilities:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_TARGET_BINDING_RESPONSIBILITY_MISMATCH",
                        message="Blueprint binding owners/providers/resources do not match the target-semantic responsibility denominator.",
                        severity=GuardStatus.FAIL,
                        layer_id="bindings",
                        depth=_node_depth(nodes, target_commitment.owner_node_id),
                        node_id=target_commitment.owner_node_id,
                        element_id=element_id,
                        evidence={
                            "expected": expected_binding_responsibilities,
                            "observed": observed_binding_responsibilities,
                        },
                    )
                )

            expected_derivation_responsibilities = [
                row.to_dict()
                for row in target_commitment.derivation_responsibilities
            ]
            expected_derivation_ids = {
                row.derivation_id
                for row in target_commitment.derivation_responsibilities
            }
            observed_derivation_responsibilities = sorted(
                (
                    {
                        "derivation_id": derivation.derivation_id,
                        "target_element_id": element_id,
                        "owner_node_id": node.node_id,
                        "parent_output_port_id": derivation.parent_output_port_id,
                        "sources": [row.to_dict() for row in derivation.sources],
                    }
                    for node in blueprint.nodes
                    for derivation in node.output_derivations
                    if derivation.derivation_id in expected_derivation_ids
                ),
                key=lambda row: row["derivation_id"],
            )
            if (
                observed_derivation_responsibilities
                != expected_derivation_responsibilities
            ):
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_TARGET_DERIVATION_RESPONSIBILITY_MISMATCH",
                        message="Blueprint output derivations do not match the independently declared semantic support lineage.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=_node_depth(nodes, target_commitment.owner_node_id),
                        node_id=target_commitment.owner_node_id,
                        element_id=element_id,
                        evidence={
                            "support_mode": target_commitment.support_mode,
                            "expected": expected_derivation_responsibilities,
                            "observed": observed_derivation_responsibilities,
                        },
                    )
                )

    for duplicate in _duplicates(node_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_NODE_ID_DUPLICATE",
                message="Blueprint node ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                node_id=duplicate,
            )
        )
    for duplicate in _duplicates(element_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_ELEMENT_ID_DUPLICATE",
                message="World element ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                element_id=duplicate,
            )
        )
    for duplicate in _duplicates(binding_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_BINDING_ID_DUPLICATE",
                message="Blueprint binding ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                binding_id=duplicate,
            )
        )
    for duplicate in _duplicates(semantic_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_NATIVE_SEMANTIC_ID_DUPLICATE",
                message="Native semantic ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                evidence={"semantic_id": duplicate},
            )
        )
    for duplicate in _duplicates(native_object_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_NATIVE_OBJECT_ID_DUPLICATE",
                message="Observed native object ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                evidence={"native_object_id": duplicate},
            )
        )
    if not blueprint.nodes:
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_NODE_INVENTORY_EMPTY",
                message="WorldBlueprint requires a non-empty node inventory.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
            )
        )
    if not blueprint.elements:
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_ELEMENT_INVENTORY_EMPTY",
                message="WorldBlueprint requires a non-empty element denominator.",
                severity=GuardStatus.GAP,
                layer_id="identity_inventory",
            )
        )

    roots = sorted(node.node_id for node in blueprint.nodes if not node.parent_node_id)
    if roots != [blueprint.root_node_id] or blueprint.root_node_id not in nodes:
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_ROOT_INVALID",
                message="Blueprint hierarchy requires exactly the declared root.",
                severity=GuardStatus.FAIL,
                layer_id="hierarchy",
                node_id=blueprint.root_node_id,
                evidence={"observed_root_ids": roots},
            )
        )

    actual_children: dict[str, list[str]] = defaultdict(list)
    for node in blueprint.nodes:
        if node.parent_node_id:
            if node.parent_node_id not in nodes:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_PARENT_UNKNOWN",
                        message="A non-root node names an unknown parent.",
                        severity=GuardStatus.FAIL,
                        layer_id="hierarchy",
                        depth=node.depth,
                        node_id=node.node_id,
                        evidence={"parent_node_id": node.parent_node_id},
                    )
                )
            else:
                actual_children[node.parent_node_id].append(node.node_id)
                parent = nodes[node.parent_node_id]
                if node.depth != parent.depth + 1:
                    gaps.append(
                        _gap(
                            blueprint,
                            code="WORLD_BLUEPRINT_DEPTH_MISMATCH",
                            message="Node depth does not match its parent chain.",
                            severity=GuardStatus.FAIL,
                            layer_id="hierarchy",
                            depth=node.depth,
                            node_id=node.node_id,
                            evidence={
                                "declared_depth": node.depth,
                                "expected_depth": parent.depth + 1,
                            },
                        )
                    )
    for node in blueprint.nodes:
        if node.depth == 0 and node.node_id != blueprint.root_node_id:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_EXTRA_DEPTH_ZERO_NODE",
                    message="Only the declared root may have depth zero.",
                    severity=GuardStatus.FAIL,
                    layer_id="hierarchy",
                    node_id=node.node_id,
                )
            )
        declared_children = list(node.child_node_ids)
        if _duplicates(declared_children):
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_CHILD_ID_DUPLICATE",
                    message="A parent lists the same child more than once.",
                    severity=GuardStatus.FAIL,
                    layer_id="hierarchy",
                    depth=node.depth,
                    node_id=node.node_id,
                    evidence={"duplicate_child_ids": _duplicates(declared_children)},
                )
            )
        if sorted(declared_children) != sorted(actual_children.get(node.node_id, [])):
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_CHILD_PARENT_MISMATCH",
                    message="Declared child inventory does not match parent ownership.",
                    severity=GuardStatus.FAIL,
                    layer_id="hierarchy",
                    depth=node.depth,
                    node_id=node.node_id,
                    evidence={
                        "declared_child_ids": sorted(declared_children),
                        "actual_child_ids": sorted(actual_children.get(node.node_id, [])),
                    },
                )
            )

    reachable: set[str] = set()
    active: list[str] = []
    cycles: list[list[str]] = []

    def visit(node_id: str) -> None:
        if node_id in active:
            cycles.append([*active[active.index(node_id) :], node_id])
            return
        if node_id in reachable or node_id not in nodes:
            return
        active.append(node_id)
        reachable.add(node_id)
        for child_id in sorted(actual_children.get(node_id, [])):
            visit(child_id)
        active.pop()

    visit(blueprint.root_node_id)
    root_reachable = set(reachable)
    for node_id in sorted(nodes):
        if node_id not in reachable:
            visit(node_id)
    for cycle in cycles:
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_HIERARCHY_CYCLE",
                message="Blueprint hierarchy contains a cycle.",
                severity=GuardStatus.FAIL,
                layer_id="hierarchy",
                node_id=cycle[0],
                evidence={"cycle": cycle},
            )
        )
    for orphan in sorted(set(node_ids).difference(root_reachable)):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_NODE_ORPHAN",
                message="Blueprint node is not reachable from the declared root.",
                severity=GuardStatus.FAIL,
                layer_id="hierarchy",
                depth=_node_depth(nodes, orphan),
                node_id=orphan,
            )
        )

    port_owners: dict[str, tuple[str, str, TypedPort]] = {}
    duplicate_ports: set[str] = set()
    for node in blueprint.nodes:
        local_ids = [port.port_id for port in [*node.input_ports, *node.output_ports]]
        duplicate_ports.update(_duplicates(local_ids))
        for direction, ports in (("input", node.input_ports), ("output", node.output_ports)):
            for port in ports:
                if port.port_id in port_owners:
                    duplicate_ports.add(port.port_id)
                port_owners[port.port_id] = (node.node_id, direction, port)
    for element in blueprint.elements:
        local_ids = [port.port_id for port in [*element.input_ports, *element.output_ports]]
        duplicate_ports.update(_duplicates(local_ids))
        for direction, ports in (("input", element.input_ports), ("output", element.output_ports)):
            for port in ports:
                if port.port_id in port_owners:
                    duplicate_ports.add(port.port_id)
                port_owners[port.port_id] = (element.element_id, direction, port)
    for port_id in sorted(duplicate_ports):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_PORT_ID_DUPLICATE",
                message="Typed port ids must be globally unique inside one blueprint.",
                severity=GuardStatus.FAIL,
                layer_id="identity_inventory",
                port_id=port_id,
            )
        )

    ownership_by_element: dict[str, list[str]] = defaultdict(list)
    for node in blueprint.nodes:
        for element_id in node.owned_element_ids:
            ownership_by_element[element_id].append(node.node_id)
            if element_id not in elements:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_OWNED_ELEMENT_UNKNOWN",
                        message="A node owns an element outside the declared denominator.",
                        severity=GuardStatus.FAIL,
                        layer_id="domain_semantics",
                        depth=node.depth,
                        node_id=node.node_id,
                        element_id=element_id,
                    )
                )
    for element in blueprint.elements:
        observed = ownership_by_element.get(element.element_id, [])
        if observed != [element.owner_node_id]:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_ELEMENT_OWNERSHIP_INVALID",
                    message="Every world element requires exactly one matching node owner.",
                    severity=GuardStatus.FAIL,
                    layer_id="domain_semantics",
                    depth=_node_depth(nodes, element.owner_node_id),
                    node_id=element.owner_node_id,
                    element_id=element.element_id,
                    evidence={"observed_owner_ids": observed},
                )
            )
        if element.owner_node_id not in nodes:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_ELEMENT_OWNER_UNKNOWN",
                    message="World element owner is outside the node inventory.",
                    severity=GuardStatus.FAIL,
                    layer_id="domain_semantics",
                    element_id=element.element_id,
                    evidence={"owner_node_id": element.owner_node_id},
                )
            )
        dependency_ids = [item.dependency_id for item in element.dependencies]
        for duplicate in _duplicates(dependency_ids):
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_DEPENDENCY_ID_DUPLICATE",
                    message="Element dependency ids must be unique.",
                    severity=GuardStatus.FAIL,
                    layer_id="domain_semantics",
                    depth=_node_depth(nodes, element.owner_node_id),
                    element_id=element.element_id,
                    evidence={"dependency_id": duplicate},
                )
            )
        for dependency in element.dependencies:
            if dependency.depends_on_element_id not in elements:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_DEPENDENCY_ENDPOINT_UNKNOWN",
                        message="Element dependency names an unknown upstream element.",
                        severity=GuardStatus.FAIL,
                        layer_id="domain_semantics",
                        depth=_node_depth(nodes, element.owner_node_id),
                        element_id=element.element_id,
                        evidence=dependency.to_dict(),
                    )
                )

    mapping_ids: list[str] = []
    derivation_ids: list[str] = []
    declared_input_ids = [item.input_id for item in blueprint.declared_inputs]
    declared_output_ids = [item.output_id for item in blueprint.declared_outputs]
    mapped_node_inputs: dict[tuple[str, str], list[str]] = defaultdict(list)
    node_input_consumers: dict[tuple[str, str], list[str]] = defaultdict(list)
    mapped_element_inputs: dict[tuple[str, str], list[str]] = defaultdict(list)
    element_output_consumers: dict[tuple[str, str], list[str]] = defaultdict(list)
    element_output_derivations: dict[tuple[str, str], list[str]] = defaultdict(list)
    mapped_child_outputs: dict[tuple[str, str], list[ChildOutputMapping]] = defaultdict(list)
    mapped_parent_output_sources: dict[
        tuple[str, str, str, str], list[str]
    ] = defaultdict(list)
    derived_child_output_sources: dict[
        tuple[str, str, str, str], list[str]
    ] = defaultdict(list)

    for duplicate in _duplicates(declared_input_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_DECLARED_INPUT_ID_DUPLICATE",
                message="Declared blueprint input ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="interfaces",
                evidence={"input_id": duplicate},
            )
        )
    for commitment in behavior_commitments:
        unknown_input_ids = sorted(
            set(commitment.input_ids).difference(declared_input_ids)
        )
        if unknown_input_ids:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_COMMITMENT_INPUT_UNKNOWN",
                    message="An independent behavior commitment names input ids outside the declared external-input denominator.",
                    severity=GuardStatus.FAIL,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, commitment.node_id),
                    node_id=commitment.node_id,
                    port_id=commitment.port_id,
                    expected_owner=commitment.owner_id,
                    evidence={
                        "commitment_id": commitment.commitment_id,
                        "unknown_input_ids": unknown_input_ids,
                        "declared_input_ids": sorted(declared_input_ids),
                        **commitment_inventory_evidence,
                    },
                )
            )
    for declared in blueprint.declared_inputs:
        node = nodes.get(declared.node_id)
        port = (
            next(
                (item for item in node.input_ports if item.port_id == declared.port_id),
                None,
            )
            if node is not None
            else None
        )
        if port is None:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_DECLARED_INPUT_UNKNOWN",
                    message="Declared external input is not a current node input port.",
                    severity=GuardStatus.FAIL,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, declared.node_id),
                    node_id=declared.node_id,
                    port_id=declared.port_id,
                    evidence=declared.to_dict(),
                )
            )
            continue
        mapped_node_inputs[(declared.node_id, declared.port_id)].append(
            declared.input_id
        )

    for parent in blueprint.nodes:
        parent_inputs = {port.port_id: port for port in parent.input_ports}
        parent_outputs = {port.port_id: port for port in parent.output_ports}
        for mapping in parent.child_input_mappings:
            mapping_ids.append(mapping.mapping_id)
            child = nodes.get(mapping.child_node_id)
            if child is None or mapping.child_node_id not in parent.child_node_ids:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_INPUT_MAPPING_CHILD_UNKNOWN",
                        message="Child-input mapping names a node that is not this parent's child.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        evidence=mapping.to_dict(),
                    )
                )
                continue
            child_port = next(
                (
                    port
                    for port in child.input_ports
                    if port.port_id == mapping.child_input_port_id
                ),
                None,
            )
            if child_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_CHILD_INPUT_UNKNOWN",
                        message="Child-input mapping names an undeclared child input.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=child.depth,
                        node_id=child.node_id,
                        port_id=mapping.child_input_port_id,
                        evidence=mapping.to_dict(),
                    )
                )
                continue
            mapped_node_inputs[(child.node_id, child_port.port_id)].append(
                mapping.mapping_id
            )
            source_port: TypedPort | None = None
            if mapping.source_kind == "parent_input":
                if mapping.source_id == parent.node_id:
                    source_port = parent_inputs.get(mapping.source_port_id)
                    if source_port is not None:
                        node_input_consumers[
                            (parent.node_id, source_port.port_id)
                        ].append(mapping.mapping_id)
            elif mapping.source_kind == "sibling_output":
                sibling = nodes.get(mapping.source_id)
                if (
                    sibling is not None
                    and sibling.node_id != child.node_id
                    and sibling.node_id in parent.child_node_ids
                ):
                    source_port = next(
                        (
                            port
                            for port in sibling.output_ports
                            if port.port_id == mapping.source_port_id
                        ),
                        None,
                    )
            else:
                source_element = elements.get(mapping.source_id)
                if (
                    source_element is not None
                    and source_element.owner_node_id == parent.node_id
                ):
                    source_port = next(
                        (
                            port
                            for port in source_element.output_ports
                            if port.port_id == mapping.source_port_id
                        ),
                        None,
                    )
            if source_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_CHILD_INPUT_SOURCE_UNKNOWN",
                        message="Child input source is not a declared parent input, sibling output, or parent-owned element output.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=child.depth,
                        node_id=child.node_id,
                        port_id=child_port.port_id,
                        evidence=mapping.to_dict(),
                    )
                )
            else:
                compatibility = _port_compatibility(source_port, child_port)
            if source_port is not None and compatibility["compatibility_relation"] == "incompatible":
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_CHILD_INPUT_PORT_INCOMPATIBLE",
                        message="Child input and its declared source have incompatible type or cardinality.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=child.depth,
                        node_id=child.node_id,
                        port_id=child_port.port_id,
                        evidence={
                            "mapping": mapping.to_dict(),
                            "source_port": source_port.to_dict(),
                            "child_port": child_port.to_dict(),
                            **compatibility,
                        },
                    )
                )

        for mapping in parent.element_input_mappings:
            mapping_ids.append(mapping.mapping_id)
            element = elements.get(mapping.element_id)
            if element is None or element.owner_node_id != parent.node_id:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_INPUT_MAPPING_ELEMENT_UNKNOWN",
                        message="Element-input mapping names an element not owned by this node.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        element_id=mapping.element_id,
                        evidence=mapping.to_dict(),
                    )
                )
                continue
            element_port = next(
                (
                    port
                    for port in element.input_ports
                    if port.port_id == mapping.element_input_port_id
                ),
                None,
            )
            if element_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_INPUT_UNKNOWN",
                        message="Element-input mapping names an undeclared element input.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        element_id=element.element_id,
                        port_id=mapping.element_input_port_id,
                        evidence=mapping.to_dict(),
                    )
                )
                continue
            mapped_element_inputs[(element.element_id, element_port.port_id)].append(
                mapping.mapping_id
            )
            source_port = None
            if mapping.source_kind == "node_input":
                if mapping.source_id == parent.node_id:
                    source_port = parent_inputs.get(mapping.source_port_id)
                    if source_port is not None:
                        node_input_consumers[
                            (parent.node_id, source_port.port_id)
                        ].append(mapping.mapping_id)
            else:
                dependency_ids = {
                    dependency.depends_on_element_id
                    for dependency in element.dependencies
                }
                source_element = elements.get(mapping.source_id)
                if source_element is not None and source_element.element_id in dependency_ids:
                    source_port = next(
                        (
                            port
                            for port in source_element.output_ports
                            if port.port_id == mapping.source_port_id
                        ),
                        None,
                    )
                    if source_port is not None:
                        element_output_consumers[
                            (source_element.element_id, source_port.port_id)
                        ].append(mapping.mapping_id)
            if source_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_INPUT_SOURCE_UNKNOWN",
                        message="Element input source is not its owner node input or a declared dependency output.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        element_id=element.element_id,
                        port_id=element_port.port_id,
                        evidence=mapping.to_dict(),
                    )
                )
            else:
                compatibility = _port_compatibility(source_port, element_port)
            if source_port is not None and compatibility["compatibility_relation"] == "incompatible":
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_INPUT_PORT_INCOMPATIBLE",
                        message="Element input and its declared source have incompatible type or cardinality.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        element_id=element.element_id,
                        port_id=element_port.port_id,
                        evidence={
                            "mapping": mapping.to_dict(),
                            "source_port": source_port.to_dict(),
                            "element_port": element_port.to_dict(),
                            **compatibility,
                        },
                    )
                )

        for mapping in parent.child_output_mappings:
            mapping_ids.append(mapping.mapping_id)
            child = nodes.get(mapping.child_node_id)
            if child is None or mapping.child_node_id not in parent.child_node_ids:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_INTERFACE_CHILD_UNKNOWN",
                        message="Interface mapping names a node that is not this parent's child.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        evidence=mapping.to_dict(),
                    )
                )
                continue
            child_outputs = {port.port_id: port for port in child.output_ports}
            child_port = child_outputs.get(mapping.child_output_port_id)
            if child_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_CHILD_OUTPUT_UNKNOWN",
                        message="Interface mapping names an undeclared child output.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=child.depth,
                        node_id=child.node_id,
                        port_id=mapping.child_output_port_id,
                        evidence=mapping.to_dict(),
                    )
                )
                continue
            mapped_child_outputs[(child.node_id, child_port.port_id)].append(mapping)
            if mapping.disposition == "internal_terminal":
                if mapping.parent_port_id or not mapping.reason:
                    gaps.append(
                        _gap(
                            blueprint,
                            code="WORLD_BLUEPRINT_INTERNAL_TERMINAL_INVALID",
                            message="Internal terminal mappings require a reason and no parent port.",
                            severity=GuardStatus.FAIL,
                            layer_id="interfaces",
                            depth=child.depth,
                            node_id=child.node_id,
                            port_id=child_port.port_id,
                            evidence=mapping.to_dict(),
                        )
                    )
                continue
            parent_ports = (
                parent_inputs
                if mapping.disposition == "parent_input"
                else parent_outputs
            )
            parent_port = parent_ports.get(mapping.parent_port_id)
            if parent_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_PARENT_PORT_UNKNOWN",
                        message="Interface mapping names an undeclared parent port.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        port_id=mapping.parent_port_id,
                        evidence=mapping.to_dict(),
                    )
                )
            else:
                compatibility = _port_compatibility(child_port, parent_port)
            if parent_port is not None and compatibility["compatibility_relation"] == "incompatible":
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_PORT_INCOMPATIBLE",
                        message="Child and parent ports have incompatible type or cardinality.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=child.depth,
                        node_id=child.node_id,
                        port_id=child_port.port_id,
                        evidence={
                            "mapping": mapping.to_dict(),
                            "child_port": child_port.to_dict(),
                            "parent_port": parent_port.to_dict(),
                            **compatibility,
                        },
                    )
                )
            elif mapping.disposition == "parent_input":
                mapped_node_inputs[(parent.node_id, parent_port.port_id)].append(
                    mapping.mapping_id
                )
            elif mapping.disposition == "parent_output":
                mapped_parent_output_sources[
                    (
                        parent.node_id,
                        parent_port.port_id,
                        child.node_id,
                        child_port.port_id,
                    )
                ].append(mapping.mapping_id)
        derivations_by_port: dict[str, list[ParentOutputDerivation]] = defaultdict(list)
        for derivation in parent.output_derivations:
            derivation_ids.append(derivation.derivation_id)
            derivations_by_port[derivation.parent_output_port_id].append(derivation)
            parent_port = parent_outputs.get(derivation.parent_output_port_id)
            if parent_port is None:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_DERIVATION_OUTPUT_UNKNOWN",
                        message="Output derivation names an undeclared node output.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        port_id=derivation.parent_output_port_id,
                    )
                )
                continue
            if not derivation.sources:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_OUTPUT_SOURCE_MISSING",
                        message="Every node output requires at least one declared source.",
                        severity=GuardStatus.GAP,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        port_id=parent_port.port_id,
                    )
                )
            for source in derivation.sources:
                source_port: TypedPort | None = None
                if source.source_kind == "child_output":
                    child = nodes.get(source.source_id)
                    if child and child.node_id in parent.child_node_ids:
                        source_port = next(
                            (
                                port
                                for port in child.output_ports
                                if port.port_id == source.source_port_id
                            ),
                            None,
                        )
                        if source_port is not None:
                            derived_child_output_sources[
                                (
                                    parent.node_id,
                                    parent_port.port_id,
                                    child.node_id,
                                    source_port.port_id,
                                )
                            ].append(derivation.derivation_id)
                else:
                    element = elements.get(source.source_id)
                    if element and element.owner_node_id == parent.node_id:
                        source_port = next(
                            (
                                port
                                for port in element.output_ports
                                if port.port_id == source.source_port_id
                            ),
                            None,
                        )
                        if source_port is not None:
                            element_output_derivations[
                                (element.element_id, source_port.port_id)
                            ].append(derivation.derivation_id)
                if source_port is None:
                    gaps.append(
                        _gap(
                            blueprint,
                            code="WORLD_BLUEPRINT_OUTPUT_SOURCE_UNKNOWN",
                            message="Output derivation source is not a declared child or owned element output.",
                            severity=GuardStatus.FAIL,
                            layer_id="interfaces",
                            depth=parent.depth,
                            node_id=parent.node_id,
                            port_id=parent_port.port_id,
                            evidence=source.to_dict(),
                        )
                    )
                else:
                    compatibility = _port_compatibility(source_port, parent_port)
                if source_port is not None and compatibility["compatibility_relation"] == "incompatible":
                    gaps.append(
                        _gap(
                            blueprint,
                            code="WORLD_BLUEPRINT_DERIVATION_PORT_INCOMPATIBLE",
                            message="Output source and derived output have incompatible type or cardinality.",
                            severity=GuardStatus.FAIL,
                            layer_id="interfaces",
                            depth=parent.depth,
                            node_id=parent.node_id,
                            port_id=parent_port.port_id,
                            evidence={
                                "source": source.to_dict(),
                                "source_port": source_port.to_dict(),
                                "parent_port": parent_port.to_dict(),
                                **compatibility,
                            },
                        )
                    )
        for output_port in parent.output_ports:
            count = len(derivations_by_port.get(output_port.port_id, []))
            if count != 1:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_OUTPUT_DERIVATION_CARDINALITY",
                        message="Every node output requires exactly one derivation owner.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=parent.depth,
                        node_id=parent.node_id,
                        port_id=output_port.port_id,
                        evidence={"derivation_count": count},
                    )
                )

    for element in blueprint.elements:
        terminal_rows: dict[str, list[ElementOutputTerminal]] = defaultdict(list)
        for terminal in element.internal_terminal_outputs:
            terminal_rows[terminal.output_port_id].append(terminal)
            if terminal.output_port_id not in {
                port.port_id for port in element.output_ports
            }:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_OUTPUT_TERMINAL_UNKNOWN",
                        message="Element output terminal names an undeclared output port.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=_node_depth(nodes, element.owner_node_id),
                        node_id=element.owner_node_id,
                        element_id=element.element_id,
                        port_id=terminal.output_port_id,
                    )
                )
        for output_port in element.output_ports:
            consumers = element_output_consumers.get(
                (element.element_id, output_port.port_id), []
            )
            derivations = element_output_derivations.get(
                (element.element_id, output_port.port_id), []
            )
            terminals = terminal_rows.get(output_port.port_id, [])
            if not consumers and not derivations and not terminals:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_OUTPUT_UNDISPOSITIONED",
                        message="Every element output must feed an element input, participate in its owner-node derivation, or declare an internal terminal reason.",
                        severity=GuardStatus.GAP,
                        layer_id="interfaces",
                        depth=_node_depth(nodes, element.owner_node_id),
                        node_id=element.owner_node_id,
                        element_id=element.element_id,
                        port_id=output_port.port_id,
                        evidence={
                            "consumer_mapping_ids": [],
                            "derivation_ids": [],
                            "internal_terminal_count": 0,
                        },
                    )
                )
            if len(terminals) > 1 or (terminals and (consumers or derivations)):
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_OUTPUT_DISPOSITION_CONFLICT",
                        message="An internal-terminal element output cannot also be consumed or derived and may have only one terminal owner.",
                        severity=GuardStatus.FAIL,
                        layer_id="interfaces",
                        depth=_node_depth(nodes, element.owner_node_id),
                        node_id=element.owner_node_id,
                        element_id=element.element_id,
                        port_id=output_port.port_id,
                        evidence={
                            "consumer_mapping_ids": sorted(consumers),
                            "derivation_ids": sorted(derivations),
                            "internal_terminal_count": len(terminals),
                        },
                    )
                )

    for duplicate in _duplicates(mapping_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_MAPPING_ID_DUPLICATE",
                message="Input and output mapping ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="interfaces",
                evidence={"mapping_id": duplicate},
            )
        )
    for node in blueprint.nodes:
        for input_port in node.input_ports:
            owners = mapped_node_inputs.get((node.node_id, input_port.port_id), [])
            if len(owners) != 1:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_NODE_INPUT_SOURCE_CARDINALITY",
                        message="Every node input requires exactly one declared external or parent-owned source.",
                        severity=GuardStatus.FAIL if len(owners) > 1 else GuardStatus.GAP,
                        layer_id="interfaces",
                        depth=node.depth,
                        node_id=node.node_id,
                        port_id=input_port.port_id,
                        evidence={"source_owner_ids": sorted(owners)},
                    )
                )
            consumers = node_input_consumers.get(
                (node.node_id, input_port.port_id), []
            )
            if not consumers:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_NODE_INPUT_DECORATIVE",
                        message="Every node input must feed at least one child or owned element input.",
                        severity=GuardStatus.GAP,
                        layer_id="interfaces",
                        depth=node.depth,
                        node_id=node.node_id,
                        port_id=input_port.port_id,
                        evidence={"consumer_mapping_ids": []},
                    )
                )
    for element in blueprint.elements:
        for input_port in element.input_ports:
            owners = mapped_element_inputs.get(
                (element.element_id, input_port.port_id), []
            )
            if len(owners) != 1:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_ELEMENT_INPUT_SOURCE_CARDINALITY",
                        message="Every element input requires exactly one owner-node or dependency source.",
                        severity=GuardStatus.FAIL if len(owners) > 1 else GuardStatus.GAP,
                        layer_id="interfaces",
                        depth=_node_depth(nodes, element.owner_node_id),
                        node_id=element.owner_node_id,
                        element_id=element.element_id,
                        port_id=input_port.port_id,
                        evidence={"source_owner_ids": sorted(owners)},
                    )
                )
    for duplicate in _duplicates(derivation_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_DERIVATION_ID_DUPLICATE",
                message="Output derivation ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="interfaces",
                evidence={"derivation_id": duplicate},
            )
        )
    for child in blueprint.nodes:
        if not child.parent_node_id:
            continue
        for output_port in child.output_ports:
            count = len(mapped_child_outputs.get((child.node_id, output_port.port_id), []))
            if count != 1:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_CHILD_OUTPUT_MAPPING_CARDINALITY",
                        message="Every child output requires exactly one parent-bound disposition.",
                        severity=GuardStatus.FAIL if count > 1 else GuardStatus.GAP,
                        layer_id="interfaces",
                        depth=child.depth,
                        node_id=child.node_id,
                        port_id=output_port.port_id,
                        evidence={"mapping_count": count},
                    )
                )

    for key in sorted(set(mapped_parent_output_sources) | set(derived_child_output_sources)):
        mapping_ids_for_source = mapped_parent_output_sources.get(key, [])
        derivation_ids_for_source = derived_child_output_sources.get(key, [])
        parent_node_id, parent_port_id, child_node_id, child_port_id = key
        if mapping_ids_for_source and len(derivation_ids_for_source) != 1:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_PARENT_OUTPUT_MAPPING_NOT_DERIVED",
                    message="A parent-output disposition must be consumed by exactly one derivation of that same parent output.",
                    severity=GuardStatus.FAIL,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, parent_node_id),
                    node_id=child_node_id,
                    port_id=child_port_id,
                    evidence={
                        "parent_node_id": parent_node_id,
                        "parent_output_port_id": parent_port_id,
                        "mapping_ids": sorted(mapping_ids_for_source),
                        "derivation_ids": sorted(derivation_ids_for_source),
                    },
                )
            )
        if derivation_ids_for_source and len(mapping_ids_for_source) != 1:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_DERIVATION_CHILD_OUTPUT_NOT_MAPPED",
                    message="A child-output derivation source must have exactly one matching parent-output disposition.",
                    severity=GuardStatus.FAIL,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, parent_node_id),
                    node_id=child_node_id,
                    port_id=child_port_id,
                    evidence={
                        "parent_node_id": parent_node_id,
                        "parent_output_port_id": parent_port_id,
                        "mapping_ids": sorted(mapping_ids_for_source),
                        "derivation_ids": sorted(derivation_ids_for_source),
                    },
                )
            )

    for duplicate in _duplicates(declared_output_ids):
        gaps.append(
            _gap(
                blueprint,
                code="WORLD_BLUEPRINT_DECLARED_OUTPUT_ID_DUPLICATE",
                message="Declared blueprint output ids must be unique.",
                severity=GuardStatus.FAIL,
                layer_id="interfaces",
                evidence={"output_id": duplicate},
            )
        )
    declared_outputs_by_id = {
        row.output_id: row for row in blueprint.declared_outputs
    }
    commitments_by_output_id = {
        row.output_id: row for row in behavior_commitments
    }
    for commitment in behavior_commitments:
        declared = declared_outputs_by_id.get(commitment.output_id)
        if declared is None:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_REQUIRED_COMMITMENT_OUTPUT_MISSING",
                    message="An independently required behavior output is absent from the blueprint output graph.",
                    severity=GuardStatus.GAP,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, commitment.node_id),
                    node_id=commitment.node_id,
                    port_id=commitment.port_id,
                    expected_owner=commitment.owner_id,
                    evidence={
                        **commitment.to_dict(),
                        **commitment_inventory_evidence,
                        "reason": "declared_output_missing",
                    },
                )
            )
        elif (declared.node_id, declared.port_id) != (
            commitment.node_id,
            commitment.port_id,
        ):
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_COMMITMENT_OUTPUT_MISMATCH",
                    message="A declared output id points somewhere other than its independent behavior commitment.",
                    severity=GuardStatus.FAIL,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, commitment.node_id),
                    node_id=commitment.node_id,
                    port_id=commitment.port_id,
                    expected_owner=commitment.owner_id,
                    evidence={
                        "commitment": commitment.to_dict(),
                        "declared_output": declared.to_dict(),
                    },
                )
            )
    for declared in blueprint.declared_outputs:
        if declared.output_id not in commitments_by_output_id:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_UNCOMMITTED_OUTPUT_DECLARED",
                    message="A caller-declared output has no independent behavior commitment authority.",
                    severity=GuardStatus.GAP,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, declared.node_id),
                    node_id=declared.node_id,
                    port_id=declared.port_id,
                    evidence={
                        "declared_output": declared.to_dict(),
                        **commitment_inventory_evidence,
                    },
                )
            )
    for output_ref in blueprint.declared_outputs:
        node = nodes.get(output_ref.node_id)
        if node is None or output_ref.port_id not in {
            port.port_id for port in node.output_ports
        }:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_DECLARED_OUTPUT_UNKNOWN",
                    message="Declared blueprint output is not a current node output.",
                    severity=GuardStatus.FAIL,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, output_ref.node_id),
                    node_id=output_ref.node_id,
                    port_id=output_ref.port_id,
                )
            )

    binding_by_element_role: dict[tuple[str, str], list[BlueprintBinding]] = defaultdict(list)
    binding_current: dict[str, bool] = {}
    external_test_execution_receipts: list[dict[str, Any]] = []
    external_evidence_alignment_receipts: list[dict[str, Any]] = []
    for binding in blueprint.bindings:
        binding_current[binding.binding_id] = True
        element = elements.get(binding.subject_element_id)
        if element is None:
            binding_current[binding.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_SUBJECT_UNKNOWN",
                    message="Binding subject is outside the world-element denominator.",
                    severity=GuardStatus.FAIL,
                    layer_id="bindings",
                    binding_id=binding.binding_id,
                    element_id=binding.subject_element_id,
                )
            )
            continue
        binding_by_element_role[(element.element_id, binding.role)].append(binding)
        depth = _node_depth(nodes, element.owner_node_id)
        if binding.target_id != blueprint.target_id:
            binding_current[binding.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_TARGET_MISMATCH",
                    message="Binding target identity does not match the current blueprint target.",
                    severity=GuardStatus.FAIL,
                    layer_id="bindings",
                    depth=depth,
                    binding_id=binding.binding_id,
                    element_id=element.element_id,
                    evidence={
                        "expected_target_id": blueprint.target_id,
                        "observed_target_id": binding.target_id,
                    },
                )
            )
        if binding.target_revision != blueprint.target_revision:
            binding_current[binding.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_REVISION_STALE",
                    message="Binding target revision does not match the current blueprint target.",
                    severity=GuardStatus.GAP,
                    layer_id="bindings",
                    depth=depth,
                    binding_id=binding.binding_id,
                    element_id=element.element_id,
                    evidence={
                        "expected_revision": blueprint.target_revision,
                        "observed_revision": binding.target_revision,
                    },
                )
            )
        if binding.freshness_status != "current":
            binding_current[binding.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_NOT_CURRENT",
                    message="Binding evidence is stale or has unknown freshness.",
                    severity=GuardStatus.GAP,
                    layer_id="bindings",
                    depth=depth,
                    binding_id=binding.binding_id,
                    element_id=element.element_id,
                    evidence={"freshness_status": binding.freshness_status},
                )
            )
        if binding.claim_boundary != blueprint.declared_boundary:
            binding_current[binding.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_CLAIM_BOUNDARY_MISMATCH",
                    message="Binding claim boundary does not match the blueprint boundary.",
                    severity=GuardStatus.FAIL,
                    layer_id="bindings",
                    depth=depth,
                    binding_id=binding.binding_id,
                    element_id=element.element_id,
                    evidence={
                        "expected": blueprint.declared_boundary,
                        "observed": binding.claim_boundary,
                    },
                )
            )
        if (
            binding.role != "native_result"
            and binding.observation_mode in {"local_content", "external_identity"}
        ):
            expected_receipt = _binding_receipt_fingerprint(binding)
            if binding.receipt_fingerprint != expected_receipt:
                binding_current[binding.binding_id] = False
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_BINDING_RECEIPT_MISMATCH",
                        message="Binding observation receipt does not match its exact identity.",
                        severity=GuardStatus.FAIL,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        evidence={
                            "expected": expected_receipt,
                            "observed": binding.receipt_fingerprint,
                        },
                    )
                )
        if binding.observation_mode == "external_identity":
            binding_current[binding.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_CONTENT_NOT_VERIFIED",
                    message="External identity is retained, but its resource content was not observed locally.",
                    severity=GuardStatus.BOUNDARY_EXCEEDED,
                    layer_id="bindings",
                    depth=depth,
                    binding_id=binding.binding_id,
                    element_id=element.element_id,
                    evidence={
                        "content_not_verified": True,
                        "provider_id": binding.provider_id,
                        "provider_version": binding.provider_version,
                        "locator": binding.locator,
                    },
                )
            )
        elif binding.observation_mode == "provider_content":
            observed, observation_error, observation_evidence = (
                _provider_binding_observation(
                    binding,
                    source_root=blueprint.source_root,
                )
            )
            if not observed:
                binding_current[binding.binding_id] = False
                unsafe = observation_error in {
                    "absolute_locator_forbidden",
                    "locator_escapes_source_root",
                    "provider_result_receipt_mismatch",
                    "provider_result_binding_receipt_mismatch",
                    "provider_result_identity_mismatch",
                }
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_PROVIDER_CONTENT_NOT_CURRENT",
                        message="Provider content result is missing, partial, foreign, stale, or invalid.",
                        severity=GuardStatus.FAIL if unsafe else GuardStatus.GAP,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        evidence={
                            "reason": observation_error,
                            "locator": binding.locator,
                            **observation_evidence,
                        },
                    )
                )
        else:
            observed_fingerprint, observation_error = _local_binding_content_fingerprint(
                binding,
                source_root=blueprint.source_root,
            )
            if observation_error:
                binding_current[binding.binding_id] = False
                unsafe = observation_error in {
                    "absolute_locator_forbidden",
                    "locator_escapes_source_root",
                }
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_BINDING_RESOURCE_UNAVAILABLE",
                        message="Local binding resource could not be observed safely and exactly.",
                        severity=GuardStatus.FAIL if unsafe else GuardStatus.GAP,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        evidence={
                            "reason": observation_error,
                            "locator": binding.locator,
                        },
                    )
                )
            elif observed_fingerprint != binding.content_fingerprint:
                binding_current[binding.binding_id] = False
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_BINDING_CONTENT_MISMATCH",
                        message="Declared binding fingerprint does not match observed resource content.",
                        severity=GuardStatus.FAIL,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        evidence={
                            "expected": binding.content_fingerprint,
                            "observed": observed_fingerprint,
                        },
                    )
                )
        if (
            integrated_object_claim
            and binding_current[binding.binding_id]
            and binding.role in {"evidence", "test_check"}
        ):
            if binding.observation_mode == "provider_content":
                # `_provider_binding_observation` above has already verified the
                # registered provider, exact request/input/result/terminal
                # attestation, and binding receipt.  A provider-owned observation
                # is therefore valid external support; it must not be downgraded
                # merely because its bytes are not local.  It still remains a
                # provider receipt, not a WorldGuard-authored semantic PASS.
                continue
            if binding.observation_mode != "local_content":
                binding_current[binding.binding_id] = False
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_EXTERNAL_SUPPORT_EXECUTION_NOT_LOCAL",
                        message=(
                            "Integrated-object evidence and tests require one current "
                            "executable local support record in this v1 route."
                        ),
                        severity=GuardStatus.GAP,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        required_role=binding.role,
                        evidence={"observation_mode": binding.observation_mode},
                    )
                )
                continue
            support_payload, support_load_error = _local_binding_json_payload(
                binding, source_root=blueprint.source_root
            )
            if support_load_error or support_payload is None:
                binding_current[binding.binding_id] = False
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_EXTERNAL_SUPPORT_RECORD_INVALID",
                        message=(
                            "The integrated-object support record could not be loaded "
                            "as one exact JSON object."
                        ),
                        severity=GuardStatus.FAIL,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        required_role=binding.role,
                        evidence={"reason": support_load_error},
                    )
                )
                continue
            if binding.role == "evidence":
                receipt, support_error, support_evidence = (
                    _validate_external_evidence_observation(
                        blueprint, element, binding, support_payload
                    )
                )
                gap_code = "WORLD_BLUEPRINT_EXTERNAL_EVIDENCE_SEMANTIC_MISMATCH"
                gap_message = (
                    "Evidence bytes are current but do not semantically support the "
                    "current target, revision, subject, owner, and source."
                )
            else:
                receipt, support_error, support_evidence = (
                    _execute_external_test_check(
                        blueprint, element, binding, support_payload
                    )
                )
                gap_code = "WORLD_BLUEPRINT_EXTERNAL_TEST_EXECUTION_FAILED"
                gap_message = (
                    "The external test design did not execute to a current terminal "
                    "PASS against its bound inputs and oracle."
                )
            if support_error or receipt is None:
                binding_current[binding.binding_id] = False
                gaps.append(
                    _gap(
                        blueprint,
                        code=gap_code,
                        message=gap_message,
                        severity=GuardStatus.FAIL,
                        layer_id="bindings",
                        depth=depth,
                        binding_id=binding.binding_id,
                        element_id=element.element_id,
                        required_role=binding.role,
                        evidence={
                            "reason": support_error,
                            **support_evidence,
                        },
                    )
                )
            elif binding.role == "evidence":
                external_evidence_alignment_receipts.append(receipt)
            else:
                external_test_execution_receipts.append(receipt)
    for (element_id, role), rows in sorted(binding_by_element_role.items()):
        if len(rows) > 1:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_ROLE_DUPLICATE",
                    message="One element binding role has more than one current owner.",
                    severity=GuardStatus.FAIL,
                    layer_id="bindings",
                    depth=_node_depth(nodes, elements[element_id].owner_node_id),
                    element_id=element_id,
                    required_role=role,
                    evidence={"binding_ids": [row.binding_id for row in rows]},
                )
            )

    purpose_declaration_ids = [
        element.native_semantic.task_purpose.declaration_id
        for element in blueprint.elements
        if element.native_semantic is not None
        and element.native_semantic.task_purpose is not None
    ]
    duplicate_purpose_declaration_ids = set(
        _duplicates(purpose_declaration_ids)
    )
    native_execution_receipts: list[dict[str, Any]] = []
    for element in blueprint.elements:
        semantic = element.native_semantic
        if semantic is None:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_SEMANTIC_MISSING",
                    message="Every World element requires one typed native semantic object.",
                    severity=GuardStatus.GAP,
                    layer_id="domain_semantics",
                    depth=_node_depth(nodes, element.owner_node_id),
                    element_id=element.element_id,
                )
            )
            continue
        depth = _node_depth(nodes, element.owner_node_id)
        purpose_admission_findings: tuple[dict[str, Any], ...] = ()
        if (
            semantic.task_purpose is not None
            and semantic.task_purpose.declaration_id
            in duplicate_purpose_declaration_ids
        ):
            purpose_admission_findings = (
                {
                    "code": "WORLD_BLUEPRINT_TASK_PURPOSE_DECLARATION_DUPLICATE",
                    "message": (
                        "Task-purpose declaration ids must identify exactly one "
                        "applicable target element."
                    ),
                    "evidence": {
                        "declaration_id": (
                            semantic.task_purpose.declaration_id
                        ),
                        "element_id": element.element_id,
                    },
                },
            )
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_TASK_PURPOSE_DECLARATION_DUPLICATE",
                    message=(
                        "A task-purpose declaration id is shared by more than one "
                        "target element."
                    ),
                    severity=GuardStatus.FAIL,
                    layer_id="native_checks",
                    depth=depth,
                    element_id=element.element_id,
                    evidence={
                        "declaration_id": semantic.task_purpose.declaration_id
                    },
                )
            )
        if semantic.claim_boundary != blueprint.declared_boundary:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_SEMANTIC_BOUNDARY_MISMATCH",
                    message="Native semantic claim boundary does not match the blueprint boundary.",
                    severity=GuardStatus.FAIL,
                    layer_id="domain_semantics",
                    depth=depth,
                    element_id=element.element_id,
                )
            )
        observation = bindings.get(semantic.observation_binding_id)
        if observation is None:
            receipt = _execute_blueprint_native_semantic(
                blueprint,
                element,
                None,
                None,
                observation_error="observation_binding_missing",
                admission_findings=purpose_admission_findings,
            )
            native_execution_receipts.append(receipt)
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_SEMANTIC_OBSERVATION_MISSING",
                    message="Native semantic content requires one exact observed native-result binding.",
                    severity=GuardStatus.GAP,
                    layer_id="native_checks",
                    depth=depth,
                    element_id=element.element_id,
                    binding_id=semantic.observation_binding_id,
                )
            )
            continue
        mismatches: dict[str, Any] = {}
        expected_observation = {
            "role": "native_result",
            "subject_element_id": element.element_id,
            "resource_id": semantic.native_object_id,
            "owner": _blueprint_native_owner(semantic)[0] or "worldguard",
            "provider_id": semantic.provider_id,
            "provider_version": semantic.provider_version,
            "content_fingerprint": semantic.content_fingerprint,
        }
        for field_name, expected_value in expected_observation.items():
            observed_value = getattr(observation, field_name)
            if observed_value != expected_value:
                mismatches[field_name] = {
                    "expected": expected_value,
                    "observed": observed_value,
                }
        if mismatches:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_SEMANTIC_OBSERVATION_MISMATCH",
                    message="Native semantic object and its observed provider result disagree.",
                    severity=GuardStatus.FAIL,
                    layer_id="native_checks",
                    depth=depth,
                    element_id=element.element_id,
                    binding_id=observation.binding_id,
                    evidence=mismatches,
                )
            )
        observed_payload: dict[str, Any] | None = None
        observation_error = ""
        if observation.observation_mode == "local_content":
            observed_payload, observation_error = _local_binding_json_object(
                observation,
                source_root=blueprint.source_root,
            )
        else:
            observation_error = "native_execution_requires_local_content"
        execution_receipt = _execute_blueprint_native_semantic(
            blueprint,
            element,
            observation,
            observed_payload,
            observation_error=observation_error,
            admission_findings=purpose_admission_findings,
        )
        native_execution_receipts.append(execution_receipt)
        target_commitment = target_semantics_by_element_id.get(element.element_id)
        if target_commitment is not None:
            actual_owner = execution_receipt["owner_guard"] or "not_applicable"
            actual_receipt_mismatches = {
                field_name: {"expected": expected, "observed": observed}
                for field_name, expected, observed in (
                    (
                        "owner_guard",
                        target_commitment.required_guard_owner_id,
                        actual_owner,
                    ),
                    (
                        "executor_id",
                        target_commitment.required_executor_id,
                        execution_receipt["executor_id"],
                    ),
                    (
                        "executor_version",
                        target_commitment.required_executor_version,
                        execution_receipt["executor_version"],
                    ),
                    (
                        "native_provider_id",
                        target_commitment.native_semantic.provider_id,
                        execution_receipt["native_provider_id"],
                    ),
                    (
                        "native_provider_version",
                        target_commitment.native_semantic.provider_version,
                        execution_receipt["native_provider_version"],
                    ),
                )
                if expected != observed
            }
            if actual_receipt_mismatches:
                binding_current[observation.binding_id] = False
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_TARGET_NATIVE_OWNER_MISMATCH",
                        message="Actual registered native execution owner/provider does not match the target-semantic commitment.",
                        severity=GuardStatus.FAIL,
                        layer_id="native_checks",
                        depth=depth,
                        element_id=element.element_id,
                        binding_id=observation.binding_id,
                        evidence=actual_receipt_mismatches,
                    )
                )
        if observation.receipt_fingerprint != execution_receipt["receipt_fingerprint"]:
            binding_current[observation.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_EXECUTION_RECEIPT_MISMATCH",
                    message="Native-result binding does not identify the current replay terminal.",
                    severity=GuardStatus.FAIL,
                    layer_id="native_checks",
                    depth=depth,
                    element_id=element.element_id,
                    binding_id=observation.binding_id,
                    evidence={
                        "expected": execution_receipt["receipt_fingerprint"],
                        "observed": observation.receipt_fingerprint,
                    },
                )
            )
        if execution_receipt["terminal_status"] not in {"PASS", "NOT_APPLICABLE"}:
            binding_current[observation.binding_id] = False
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_EXECUTION_FAILED",
                    message="The current native domain owner did not reach a qualified terminal.",
                    severity=(
                        GuardStatus.FAIL
                        if execution_receipt["terminal_status"] == "FAIL"
                        else GuardStatus.BOUNDARY_EXCEEDED
                        if execution_receipt["terminal_status"]
                        == "BOUNDARY_EXCEEDED"
                        else GuardStatus.GAP
                    ),
                    layer_id="native_checks",
                    depth=depth,
                    element_id=element.element_id,
                    binding_id=observation.binding_id,
                    evidence={
                        "execution_status": execution_receipt["terminal_status"],
                        "execution_disposition": execution_receipt[
                            "execution_disposition"
                        ],
                        "owner_guard": execution_receipt["owner_guard"],
                        "executor_id": execution_receipt["executor_id"],
                        "execution_id": execution_receipt["execution_id"],
                        "findings": execution_receipt["findings"],
                    },
                )
            )
        if not binding_current.get(observation.binding_id, False):
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_NATIVE_SEMANTIC_OBSERVATION_NOT_CURRENT",
                    message="Native semantic content is declared but lacks a current verified observation.",
                    severity=GuardStatus.GAP,
                    layer_id="native_checks",
                    depth=depth,
                    element_id=element.element_id,
                    binding_id=observation.binding_id,
                )
            )

    output_derivations = {
        (node.node_id, derivation.parent_output_port_id): derivation
        for node in blueprint.nodes
        for derivation in node.output_derivations
    }
    derived_claim_contributors: set[str] = set()

    def collect_output_contributors(
        node_id: str,
        port_id: str,
        *,
        contributors: set[str],
        visited: set[tuple[str, str]],
    ) -> None:
        key = (node_id, port_id)
        if key in visited:
            return
        visited.add(key)
        derivation = output_derivations.get(key)
        if derivation is None:
            return
        for source in derivation.sources:
            if source.source_kind == "owned_element_output":
                if source.source_id in elements:
                    contributors.add(source.source_id)
            elif source.source_kind == "child_output":
                collect_output_contributors(
                    source.source_id,
                    source.source_port_id,
                    contributors=contributors,
                    visited=visited,
                )

    for commitment in behavior_commitments:
        commitment_contributors: set[str] = set()
        collect_output_contributors(
            commitment.node_id,
            commitment.port_id,
            contributors=commitment_contributors,
            visited=set(),
        )
        derived_claim_contributors.update(commitment_contributors)
        missing_contributors = sorted(
            set(commitment.required_contributor_element_ids).difference(
                commitment_contributors
            )
        )
        unknown_contributors = sorted(
            set(commitment.required_contributor_element_ids).difference(elements)
        )
        if missing_contributors or unknown_contributors:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_REQUIRED_COMMITMENT_OUTPUT_MISSING",
                    message="An independently required behavior branch is absent from the committed output lineage.",
                    severity=GuardStatus.GAP,
                    layer_id="interfaces",
                    depth=_node_depth(nodes, commitment.node_id),
                    node_id=commitment.node_id,
                    port_id=commitment.port_id,
                    expected_owner=commitment.owner_id,
                    evidence={
                        **commitment.to_dict(),
                        "missing_contributor_element_ids": missing_contributors,
                        "unknown_contributor_element_ids": unknown_contributors,
                        "observed_contributor_element_ids": sorted(
                            commitment_contributors
                        ),
                        **commitment_inventory_evidence,
                    },
                )
            )

    for element in blueprint.elements:
        derived_contributor = element.element_id in derived_claim_contributors
        if element.contributes_to_claim != derived_contributor:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_CLAIM_CONTRIBUTOR_ASSERTION_MISMATCH",
                    message="Claim contribution is derived from declared output lineage; the element flag is only an assertion.",
                    severity=GuardStatus.FAIL,
                    layer_id="bindings",
                    depth=_node_depth(nodes, element.owner_node_id),
                    element_id=element.element_id,
                    evidence={
                        "derived_contributes_to_claim": derived_contributor,
                        "declared_contributes_to_claim": element.contributes_to_claim,
                    },
                )
            )
        target_commitment = target_semantics_by_element_id.get(element.element_id)
        expected_roles = (
            {
                row.role
                for row in target_commitment.binding_responsibilities
            }
            if target_commitment is not None
            else set()
        )
        declared_roles = set(element.required_binding_roles)
        if declared_roles != expected_roles:
            gaps.append(
                _gap(
                    blueprint,
                    code="WORLD_BLUEPRINT_BINDING_ROLE_ASSERTION_MISMATCH",
                    message="Required binding roles must exact-match the independent target-semantic role dispositions.",
                    severity=GuardStatus.FAIL,
                    layer_id="bindings",
                    depth=_node_depth(nodes, element.owner_node_id),
                    element_id=element.element_id,
                    evidence={
                        "expected_roles": sorted(expected_roles),
                        "declared_roles": sorted(declared_roles),
                    },
                )
            )

    for element in blueprint.elements:
        owner = nodes.get(element.owner_node_id)
        target_commitment = target_semantics_by_element_id.get(element.element_id)
        if target_commitment is None or owner is None:
            continue
        binding_responsibilities_by_role = {
            row.role: row for row in target_commitment.binding_responsibilities
        }
        not_applicable_by_role = {
            row.role: row
            for row in target_commitment.not_applicable_responsibilities
        }
        for role in sorted(BINDING_ROLES):
            rows = binding_by_element_role.get((element.element_id, role), [])
            current_rows = [
                row
                for row in rows
                if row.freshness_status == "current"
                and row.target_id == blueprint.target_id
                and row.target_revision == blueprint.target_revision
                and binding_current.get(row.binding_id, False)
            ]
            if role in not_applicable_by_role:
                responsibility = not_applicable_by_role[role]
                if rows:
                    gaps.append(
                        _gap(
                            blueprint,
                            code="WORLD_BLUEPRINT_NOT_APPLICABLE_ROLE_BOUND",
                            message="A target-semantic not-applicable role cannot carry a blueprint binding.",
                            severity=GuardStatus.FAIL,
                            layer_id=(
                                "native_checks"
                                if role == "native_result"
                                else "bindings"
                            ),
                            depth=owner.depth,
                            element_id=element.element_id,
                            required_role=role,
                            expected_owner=element.owner_node_id,
                            evidence={
                                "not_applicable_reason": responsibility.reason,
                                "binding_ids": sorted(row.binding_id for row in rows),
                            },
                        )
                    )
                continue
            responsibility = binding_responsibilities_by_role[role]
            if len(current_rows) != 1:
                gaps.append(
                    _gap(
                        blueprint,
                        code="WORLD_BLUEPRINT_REQUIRED_BINDING_MISSING",
                        message="A target-required element lacks its one authority-applicable binding role.",
                        severity=GuardStatus.GAP,
                        layer_id="native_checks" if role == "native_result" else "bindings",
                        depth=owner.depth,
                        element_id=element.element_id,
                        required_role=role,
                        expected_owner=element.owner_node_id,
                        evidence={"current_binding_count": len(current_rows)},
                    )
                )

    for declared in blueprint.declared_gaps:
        depth = _node_depth(nodes, declared.node_id)
        if declared.element_id in elements:
            depth = _node_depth(nodes, elements[declared.element_id].owner_node_id)
        gaps.append(
            _gap(
                blueprint,
                gap_id=declared.gap_id,
                code=declared.code,
                message=declared.message,
                severity=(
                    GuardStatus.BOUNDARY_EXCEEDED
                    if declared.disposition == "boundary"
                    else GuardStatus.GAP
                ),
                layer_id=declared.gap_kind,
                depth=depth,
                node_id=declared.node_id,
                element_id=declared.element_id,
                port_id=declared.port_id,
                required_role=declared.required_role,
                expected_owner=declared.expected_owner,
            )
        )

    conceptual_order = (
        "identity_inventory",
        "hierarchy",
        "interfaces",
        "domain_semantics",
        "bindings",
        "native_checks",
        "cross_artifact_projection",
    )
    native_gaps = tuple(
        gap for gap in gaps if gap.layer_id != "cross_artifact_projection"
    )

    def qualification_results(
        *, projection_was_supplied: bool
    ) -> list[BlueprintLayerResult]:
        results: list[BlueprintLayerResult] = []
        for layer_id in conceptual_order:
            layer_gaps = [gap for gap in gaps if gap.layer_id == layer_id]
            if layer_id == "cross_artifact_projection" and not projection_was_supplied:
                layer_status = BlueprintLayerStatus.NOT_RUN
            else:
                layer_status = _layer_status(layer_gaps)
            results.append(
                BlueprintLayerResult(
                    layer_id=layer_id,
                    status=layer_status,
                    gap_ids=tuple(sorted(gap.gap_id for gap in layer_gaps)),
                )
            )
        return results

    native_qualification_layers = qualification_results(
        projection_was_supplied=False
    )

    declared_depths = sorted(set(node.depth for node in blueprint.nodes))
    depth_layers: list[BlueprintLayerResult] = []
    continuous = True
    deepest: int | None = None
    first_unresolved: int | None = None
    for depth in declared_depths:
        depth_gaps = [gap for gap in native_gaps if gap.depth == depth]
        if not continuous:
            status = BlueprintLayerStatus.NOT_RUN
        else:
            status = _layer_status(depth_gaps)
            if status == BlueprintLayerStatus.PROVEN:
                deepest = depth
            else:
                continuous = False
                first_unresolved = depth
        depth_layers.append(
            BlueprintLayerResult(
                layer_id=f"depth:{depth}",
                status=status,
                gap_ids=tuple(sorted(gap.gap_id for gap in depth_gaps)),
            )
        )

    native_domain_qualified = bool(
        blueprint.nodes
        and blueprint.elements
        and blueprint.declared_outputs
        and not native_gaps
        and declared_depths == list(range(max(declared_depths) + 1))
    )
    census_members = [
        row
        for row in object_census_source.get("members", [])
        if isinstance(row, Mapping)
    ]
    census_test_element_ids = {
        str(row.get("element_id", ""))
        for row in census_members
        if "test_check" in row.get("binding_roles", [])
    }
    census_evidence_element_ids = {
        str(row.get("element_id", ""))
        for row in census_members
        if "evidence" in row.get("binding_roles", [])
    }
    test_design_element_ids = {
        element_id
        for element_id in census_test_element_ids
        if len(binding_by_element_role.get((element_id, "test_check"), [])) == 1
    }
    evidence_design_element_ids = {
        element_id
        for element_id in census_evidence_element_ids
        if len(binding_by_element_role.get((element_id, "evidence"), [])) == 1
    }
    executed_test_element_ids = {
        str(row.get("element_id", ""))
        for row in external_test_execution_receipts
        if row.get("terminal_status") == "PASS"
    }
    aligned_evidence_element_ids = {
        str(row.get("element_id", ""))
        for row in external_evidence_alignment_receipts
        if row.get("terminal_status") == "PASS"
    }
    external_test_design_present = bool(
        census_test_element_ids == test_design_element_ids
    )
    external_evidence_design_present = bool(
        census_evidence_element_ids == evidence_design_element_ids
    )
    external_test_execution_current = bool(
        census_test_element_ids == executed_test_element_ids
    )
    external_evidence_semantically_aligned = bool(
        external_evidence_design_present
        and census_evidence_element_ids == aligned_evidence_element_ids
    )
    applicable_external_binding_ids = {
        row.binding_id
        for (element_id, role), rows in binding_by_element_role.items()
        if (
            (role == "test_check" and element_id in census_test_element_ids)
            or (role == "evidence" and element_id in census_evidence_element_ids)
        )
        for row in rows
    }
    external_support_bytes_current = bool(
        all(binding_current.get(binding_id, False) for binding_id in applicable_external_binding_ids)
    )
    object_dna_qualified = bool(
        native_domain_qualified
        and object_census_authority_valid
        and object_census_authority_licensed
        and object_census_independent_discovery_current
        and object_census_coverage_complete
        and integrated_object_claim
        and external_support_bytes_current
        and external_test_design_present
        and external_evidence_design_present
        and external_test_execution_current
        and external_evidence_semantically_aligned
    )
    object_census_first_gap: dict[str, Any] | None = None
    if not object_census_authority_valid:
        object_census_first_gap = {
            "code": "object-census-authority-invalid",
            "detail": commitment_inventory_error
            or "no valid independently signed census was replayed",
        }
    elif not integrated_object_claim:
        object_census_first_gap = {
            "code": "object-claim-kind-not-integrated-target",
            "detail": (
                "the signed target is an oracle-carrying capability fixture, not an "
                "integrated external object"
            ),
        }
    elif not object_census_independent_discovery_current:
        object_census_first_gap = {
            "code": "object-census-independent-discovery-not-current",
            "detail": (
                "the denominator was not discovered from the frozen raw request, "
                "raw target material, and independent census source"
            ),
        }
    elif not object_census_coverage_complete:
        object_census_first_gap = {
            "code": "object-census-coverage-incomplete",
            "detail": "candidate nodes/elements do not exactly match the signed census",
        }
    elif not object_census_authority_licensed:
        object_census_first_gap = {
            "code": "object-census-trust-not-licensed",
            "detail": (
                "the signed census is portable and internally valid, but the caller "
                "did not trust its exact authority or producer descriptor fingerprint"
            ),
        }
    elif not external_test_design_present:
        object_census_first_gap = {
            "code": "object-test-design-incomplete",
            "detail": "one census-required test/check has no exact current design binding",
        }
    elif not external_evidence_design_present:
        object_census_first_gap = {
            "code": "object-evidence-design-incomplete",
            "detail": "one census-required evidence obligation has no exact current binding",
        }
    elif not external_support_bytes_current:
        object_census_first_gap = {
            "code": "object-support-bytes-not-current",
            "detail": "one required external evidence or test resource is missing or stale",
        }
    elif not external_test_execution_current:
        object_census_first_gap = {
            "code": "object-test-execution-not-current",
            "detail": "one required external test did not execute to terminal PASS",
        }
    elif not external_evidence_semantically_aligned:
        object_census_first_gap = {
            "code": "object-evidence-not-semantically-aligned",
            "detail": "one required evidence record does not support its bound subject",
        }
    elif not native_domain_qualified:
        object_census_first_gap = {
            "code": "candidate-native-consistency-not-qualified",
            "detail": "the census is licensed but the candidate model has native gaps",
        }
    object_census = {
        "authority_status": (
            "valid" if object_census_authority_valid else "invalid"
        ),
        "authority_licensed": object_census_authority_licensed,
        "exact_authority_trusted": object_census_exact_authority_trusted,
        "producer_trusted": object_census_producer_trusted,
        "producer_revision_licensed": object_census_producer_revision_licensed,
        "independent_discovery_current": object_census_independent_discovery_current,
        "independent_discovery_status": (
            "current"
            if object_census_independent_discovery_current
            else (
                "candidate_consistency"
                if object_census_source.get("discovery_mode")
                == "candidate_consistency"
                else "invalid_or_not_run"
            )
        ),
        "discovery_mode": str(object_census_source.get("discovery_mode", "")),
        "discovery_receipt_fingerprint": str(
            object_census_source.get("discovery_receipt", {}).get(
                "receipt_fingerprint", ""
            )
            if isinstance(object_census_source.get("discovery_receipt"), Mapping)
            else ""
        ),
        "coverage_complete": object_census_coverage_complete,
        "byte_currentness_status": (
            ("current" if external_support_bytes_current else "gap")
            if integrated_object_claim
            else "not_applicable_for_capability_fixture"
        ),
        "test_design_status": (
            ("present" if external_test_design_present else "gap")
            if integrated_object_claim
            else "not_applicable_for_capability_fixture"
        ),
        "test_execution_status": (
            ("passed" if external_test_execution_current else "failed_or_not_run")
            if integrated_object_claim
            else "not_applicable_for_capability_fixture"
        ),
        "evidence_design_status": (
            ("present" if external_evidence_design_present else "gap")
            if integrated_object_claim
            else "not_applicable_for_capability_fixture"
        ),
        "evidence_alignment_status": (
            (
                "aligned"
                if external_evidence_semantically_aligned
                else "misaligned_or_not_run"
            )
            if integrated_object_claim
            else "not_applicable_for_capability_fixture"
        ),
        "external_test_execution_receipts": sorted(
            external_test_execution_receipts,
            key=lambda row: (str(row.get("element_id", "")), str(row.get("check_id", ""))),
        ),
        "external_evidence_alignment_receipts": sorted(
            external_evidence_alignment_receipts,
            key=lambda row: (str(row.get("element_id", "")), str(row.get("evidence_id", ""))),
        ),
        "object_claim_kind": object_claim_kind,
        "object_dna_qualified": object_dna_qualified,
        "authority_id": str(object_census_source.get("authority_id", "")),
        "authority_revision": str(
            object_census_source.get("authority_revision", "")
        ),
        "authority_owner_id": str(
            object_census_source.get("authority_owner_id", "")
        ),
        "authority_fingerprint": object_census_authority_fingerprint,
        "producer_descriptor_fingerprint": object_census_producer_fingerprint,
        "required_node_ids": sorted(census_required_nodes),
        "required_element_ids": sorted(census_required_elements),
        "required_guard_owner_ids": list(
            object_census_source.get("required_guard_owner_ids", [])
        ),
        "missing_node_ids": census_missing_node_ids,
        "unexpected_node_ids": census_unexpected_node_ids,
        "missing_element_ids": census_missing_element_ids,
        "unexpected_element_ids": census_unexpected_element_ids,
        "unmapped_member_ids": sorted(
            {
                *census_missing_node_ids,
                *census_unexpected_node_ids,
                *census_missing_element_ids,
                *census_unexpected_element_ids,
            }
        ),
        "first_gap": object_census_first_gap,
    }
    native_status = (
        GuardStatus.PASS
        if native_domain_qualified
        else aggregate_statuses(gap.severity for gap in native_gaps)
    )
    native_partial_model_usable = bool(
        native_domain_qualified
        or any(row.status == BlueprintLayerStatus.PROVEN for row in depth_layers)
    )
    native_report_payload = {
        "status": native_status.value,
        "blueprint_id": blueprint.blueprint_id,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "blueprint_fingerprint": blueprint.blueprint_fingerprint,
        "qualification_layers": [
            row.to_dict() for row in native_qualification_layers
        ],
        "depth_layers": [row.to_dict() for row in depth_layers],
        "deepest_continuously_proven_layer": deepest,
        "first_unresolved_layer": first_unresolved,
        "native_domain_qualified": native_domain_qualified,
        "full_domain_qualified": False,
        "object_dna_qualified": object_dna_qualified,
        "object_census": object_census,
        "partial_model_usable": native_partial_model_usable,
        "native_execution_receipts": sorted(
            native_execution_receipts,
            key=lambda row: (row["element_id"], row["execution_id"]),
        ),
        "gaps": [gap.to_dict() for gap in native_gaps],
        "claim_boundary": blueprint.declared_boundary,
    }
    native_report_fingerprint = fingerprint_mesh(native_report_payload)

    projection_was_supplied = cross_artifact_projection is not None
    projection_result: CrossArtifactProjectionResult | None = None
    if cross_artifact_projection is not None:
        try:
            projection_result = (
                cross_artifact_projection
                if isinstance(
                    cross_artifact_projection, CrossArtifactProjectionResult
                )
                else CrossArtifactProjectionResult.from_dict(
                    cross_artifact_projection
                )
            )
        except BlueprintError as exc:
            gaps.append(
                _cross_artifact_projection_gap(
                    blueprint,
                    code=exc.code,
                    message=str(exc),
                    severity=GuardStatus.GAP,
                    evidence=exc.details,
                )
            )
        else:
            gaps.extend(
                _validate_cross_artifact_projection(
                    blueprint,
                    projection_result,
                    native_report_fingerprint=native_report_fingerprint,
                    native_domain_qualified=native_domain_qualified,
                )
            )

    qualification_layers = qualification_results(
        projection_was_supplied=projection_was_supplied
    )
    projection_proven = any(
        row.layer_id == "cross_artifact_projection"
        and row.status == BlueprintLayerStatus.PROVEN
        for row in qualification_layers
    )
    full_domain_qualified = native_domain_qualified and projection_proven
    partial_model_usable = bool(
        not full_domain_qualified
        and (
            native_domain_qualified
            or any(row.status == BlueprintLayerStatus.PROVEN for row in depth_layers)
        )
    )
    projection_gaps = [
        gap for gap in gaps if gap.layer_id == "cross_artifact_projection"
    ]
    status = (
        native_status
        if not native_domain_qualified or not projection_gaps
        else aggregate_statuses(gap.severity for gap in projection_gaps)
    )

    report_payload = {
        "status": status.value,
        "blueprint_id": blueprint.blueprint_id,
        "target_id": blueprint.target_id,
        "target_revision": blueprint.target_revision,
        "blueprint_fingerprint": blueprint.blueprint_fingerprint,
        "qualification_layers": [row.to_dict() for row in qualification_layers],
        "depth_layers": [row.to_dict() for row in depth_layers],
        "deepest_continuously_proven_layer": deepest,
        "first_unresolved_layer": first_unresolved,
        "native_domain_qualified": native_domain_qualified,
        "full_domain_qualified": full_domain_qualified,
        "object_dna_qualified": object_dna_qualified,
        "object_census": object_census,
        "partial_model_usable": partial_model_usable,
        "native_execution_receipts": sorted(
            native_execution_receipts,
            key=lambda row: (row["element_id"], row["execution_id"]),
        ),
        "gaps": [gap.to_dict() for gap in gaps],
        "claim_boundary": blueprint.declared_boundary,
    }
    if projection_result is not None:
        report_payload["cross_artifact_projection"] = projection_result.to_dict()
    return WorldBlueprintReport(
        status=status,
        blueprint_id=blueprint.blueprint_id,
        target_id=blueprint.target_id,
        target_revision=blueprint.target_revision,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        report_fingerprint=fingerprint_mesh(report_payload),
        qualification_layers=tuple(qualification_layers),
        depth_layers=tuple(depth_layers),
        deepest_continuously_proven_layer=deepest,
        first_unresolved_layer=first_unresolved,
        native_domain_qualified=native_domain_qualified,
        full_domain_qualified=full_domain_qualified,
        object_dna_qualified=object_dna_qualified,
        object_census=object_census,
        partial_model_usable=partial_model_usable,
        native_execution_receipts=tuple(
            sorted(
                native_execution_receipts,
                key=lambda row: (row["element_id"], row["execution_id"]),
            )
        ),
        gaps=tuple(gaps),
        claim_boundary=blueprint.declared_boundary,
        cross_artifact_projection=projection_result,
    )


@dataclass(frozen=True)
class BlueprintImpactReport:
    blueprint_id: str
    blueprint_fingerprint: str
    changed_ids: tuple[str, ...]
    affected_members: tuple[dict[str, Any], ...]
    traversed_edges: tuple[dict[str, Any], ...]
    materialized_ids: tuple[str, ...]
    terminal_binding_ids: tuple[str, ...]
    gaps: tuple[dict[str, Any], ...]
    claim_boundary: str
    result_fingerprint: str
    operation: str = "impact"

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "blueprint_id": self.blueprint_id,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "changed_ids": list(self.changed_ids),
            "affected_members": list(self.affected_members),
            "traversed_edges": list(self.traversed_edges),
            "materialized_ids": list(self.materialized_ids),
            "terminal_binding_ids": list(self.terminal_binding_ids),
            "gaps": list(self.gaps),
            "claim_boundary": self.claim_boundary,
            "result_fingerprint": self.result_fingerprint,
        }


@dataclass(frozen=True)
class BlueprintTraceReport:
    status: GuardStatus
    blueprint_id: str
    blueprint_fingerprint: str
    target_id: str
    traced_members: tuple[dict[str, Any], ...]
    traversed_edges: tuple[dict[str, Any], ...]
    terminal_input_ids: tuple[str, ...]
    terminal_binding_ids: tuple[str, ...]
    cycle_witnesses: tuple[dict[str, Any], ...]
    gaps: tuple[dict[str, Any], ...]
    claim_boundary: str
    result_fingerprint: str
    operation: str = "trace"

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "status": self.status.value,
            "blueprint_id": self.blueprint_id,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "target_id": self.target_id,
            "traced_members": list(self.traced_members),
            "traversed_edges": list(self.traversed_edges),
            "terminal_input_ids": list(self.terminal_input_ids),
            "terminal_binding_ids": list(self.terminal_binding_ids),
            "cycle_witnesses": list(self.cycle_witnesses),
            "gaps": list(self.gaps),
            "claim_boundary": self.claim_boundary,
            "result_fingerprint": self.result_fingerprint,
        }


@dataclass(frozen=True)
class _BlueprintIndexes:
    kinds: dict[str, str]
    forward: dict[str, tuple[dict[str, Any], ...]]
    reverse: dict[str, tuple[dict[str, Any], ...]]
    binding_ids: frozenset[str]
    input_port_ids: frozenset[str]
    output_port_ids: frozenset[str]
    declared_input_ids: frozenset[str]


def _edge_record(
    edge_id: str,
    relation: str,
    source_id: str,
    target_id: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "relation": relation,
        "source_id": source_id,
        "target_id": target_id,
        **details,
    }


def _build_blueprint_indexes(blueprint: WorldBlueprintContract) -> _BlueprintIndexes:
    kinds: dict[str, str] = {}
    forward_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reverse_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    binding_ids: set[str] = set()
    input_ports: set[str] = set()
    output_ports: set[str] = set()
    declared_input_ids: set[str] = set()

    def register(member_id: str, kind: str) -> None:
        if member_id in kinds and kinds[member_id] != kind:
            raise BlueprintError(
                "WORLD_BLUEPRINT_QUERY_ID_AMBIGUOUS",
                f"Blueprint member id {member_id} has more than one kind.",
                details={"member_id": member_id, "kinds": [kinds[member_id], kind]},
            )
        kinds[member_id] = kind

    def connect(edge: dict[str, Any]) -> None:
        forward_rows[edge["source_id"]].append(edge)
        reverse_rows[edge["target_id"]].append(edge)

    register(blueprint.blueprint_id, "blueprint")
    register(blueprint.target_id, "target")
    connect(
        _edge_record(
            f"blueprint-target:{blueprint.blueprint_id}:{blueprint.target_id}",
            "blueprint_target",
            blueprint.blueprint_id,
            blueprint.target_id,
        )
    )
    for node in blueprint.nodes:
        register(node.node_id, "node")
        if node.parent_node_id:
            connect(
                _edge_record(
                    f"hierarchy:{node.node_id}:{node.parent_node_id}",
                    "hierarchy_parent",
                    node.node_id,
                    node.parent_node_id,
                )
            )
        for port in node.input_ports:
            register(port.port_id, "node_input_port")
            input_ports.add(port.port_id)
            connect(
                _edge_record(
                    f"owner:{node.node_id}:{port.port_id}",
                    "owned_input_port",
                    port.port_id,
                    node.node_id,
                )
            )
        for port in node.output_ports:
            register(port.port_id, "node_output_port")
            output_ports.add(port.port_id)
            connect(
                _edge_record(
                    f"owner:{node.node_id}:{port.port_id}",
                    "owned_output_port",
                    node.node_id,
                    port.port_id,
                )
            )
        for mapping in node.child_input_mappings:
            register(mapping.mapping_id, "child_input_mapping")
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:source",
                    mapping.source_kind,
                    mapping.source_port_id,
                    mapping.mapping_id,
                )
            )
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:target",
                    "maps_child_input",
                    mapping.mapping_id,
                    mapping.child_input_port_id,
                )
            )
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:affected-source",
                    "affected_source_endpoint",
                    mapping.mapping_id,
                    mapping.source_port_id,
                )
            )
        for mapping in node.element_input_mappings:
            register(mapping.mapping_id, "element_input_mapping")
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:source",
                    mapping.source_kind,
                    mapping.source_port_id,
                    mapping.mapping_id,
                )
            )
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:target",
                    "maps_element_input",
                    mapping.mapping_id,
                    mapping.element_input_port_id,
                )
            )
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:affected-source",
                    "affected_source_endpoint",
                    mapping.mapping_id,
                    mapping.source_port_id,
                )
            )
        for mapping in node.child_output_mappings:
            register(mapping.mapping_id, "interface_mapping")
            connect(
                _edge_record(
                    mapping.mapping_id,
                    "interface_mapping",
                    mapping.child_output_port_id,
                    mapping.mapping_id,
                )
            )
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:owner",
                    "interface_owner",
                    mapping.child_node_id,
                    mapping.mapping_id,
                )
            )
            connect(
                _edge_record(
                    f"{mapping.mapping_id}:affected-source",
                    "affected_source_endpoint",
                    mapping.mapping_id,
                    mapping.child_output_port_id,
                )
            )
            if mapping.parent_port_id:
                connect(
                    _edge_record(
                        f"{mapping.mapping_id}:target",
                        mapping.disposition,
                        mapping.mapping_id,
                        mapping.parent_port_id,
                    )
                )
                connect(
                    _edge_record(
                        f"{mapping.mapping_id}:parent",
                        "affected_parent",
                        mapping.mapping_id,
                        node.node_id,
                    )
                )
        for derivation in node.output_derivations:
            register(derivation.derivation_id, "output_derivation")
            for index, source in enumerate(derivation.sources):
                connect(
                    _edge_record(
                        f"{derivation.derivation_id}:source:{index}",
                        source.source_kind,
                        source.source_port_id,
                        derivation.derivation_id,
                    )
                )
                connect(
                    _edge_record(
                        f"{derivation.derivation_id}:affected-source:{index}",
                        "affected_source_endpoint",
                        derivation.derivation_id,
                        source.source_port_id,
                    )
                )
            connect(
                _edge_record(
                    f"{derivation.derivation_id}:output",
                    "derives_output",
                    derivation.derivation_id,
                    derivation.parent_output_port_id,
                )
            )

    for element in blueprint.elements:
        register(element.element_id, "element")
        connect(
            _edge_record(
                f"element-owner:{element.element_id}",
                "element_owner",
                element.element_id,
                element.owner_node_id,
            )
        )
        semantic = element.native_semantic
        if semantic is not None:
            register(semantic.semantic_id, "native_semantic")
            connect(
                _edge_record(
                    f"native-semantic:{element.element_id}:affected-element",
                    "native_semantic_affects",
                    semantic.semantic_id,
                    element.element_id,
                )
            )
            connect(
                _edge_record(
                    f"native-semantic:{element.element_id}:execution-receipt",
                    "native_execution_receipt",
                    semantic.observation_binding_id,
                    semantic.semantic_id,
                )
            )
        for port in element.input_ports:
            register(port.port_id, "element_input_port")
            input_ports.add(port.port_id)
            connect(
                _edge_record(
                    f"element-input:{element.element_id}:{port.port_id}",
                    "element_input",
                    port.port_id,
                    element.element_id,
                )
            )
        for port in element.output_ports:
            register(port.port_id, "element_output_port")
            output_ports.add(port.port_id)
            connect(
                _edge_record(
                    f"element-output:{element.element_id}:{port.port_id}",
                    "element_output",
                    element.element_id,
                    port.port_id,
                )
            )
        for dependency in element.dependencies:
            register(dependency.dependency_id, "element_dependency")
            connect(
                _edge_record(
                    f"{dependency.dependency_id}:source",
                    "dependency_source",
                    dependency.depends_on_element_id,
                    dependency.dependency_id,
                    declared_relation=dependency.relation,
                )
            )
            connect(
                _edge_record(
                    f"{dependency.dependency_id}:target",
                    dependency.relation,
                    dependency.dependency_id,
                    element.element_id,
                )
            )
            connect(
                _edge_record(
                    f"{dependency.dependency_id}:affected-source",
                    "affected_dependency_endpoint",
                    dependency.dependency_id,
                    dependency.depends_on_element_id,
                )
            )

    for binding in blueprint.bindings:
        register(binding.binding_id, f"binding:{binding.role}")
        register(binding.resource_id, "resource")
        binding_ids.add(binding.binding_id)
        connect(
            _edge_record(
                f"binding-subject:{binding.binding_id}",
                f"{binding.role}_binding",
                binding.subject_element_id,
                binding.binding_id,
            )
        )
        connect(
            _edge_record(
                f"binding-resource:{binding.binding_id}",
                "binding_resource",
                binding.resource_id,
                binding.binding_id,
            )
        )
        connect(
            _edge_record(
                f"binding-affects:{binding.binding_id}",
                "binding_affects_subject",
                binding.binding_id,
                binding.subject_element_id,
            )
        )
        connect(
            _edge_record(
                f"binding-materializes:{binding.binding_id}",
                "binding_materializes_resource",
                binding.binding_id,
                binding.resource_id,
            )
        )

    for declared in blueprint.declared_inputs:
        register(declared.input_id, "declared_input")
        declared_input_ids.add(declared.input_id)
        connect(
            _edge_record(
                f"declared-input:{declared.input_id}:target",
                "external_input",
                declared.input_id,
                declared.port_id,
            )
        )
        connect(
            _edge_record(
                f"declared-input:{declared.input_id}:affected-port",
                "declares_input",
                declared.port_id,
                declared.input_id,
            )
        )

    for declared in blueprint.declared_outputs:
        register(declared.output_id, "declared_output")
        connect(
            _edge_record(
                f"declared-output:{declared.output_id}:source",
                "declares_output",
                declared.port_id,
                declared.output_id,
            )
        )
        connect(
            _edge_record(
                f"declared-output:{declared.output_id}:target",
                "blueprint_output",
                declared.output_id,
                blueprint.target_id,
            )
        )
        connect(
            _edge_record(
                f"declared-output:{declared.output_id}:affected-port",
                "affected_output_endpoint",
                declared.output_id,
                declared.port_id,
            )
        )
        connect(
            _edge_record(
                f"declared-output:{declared.output_id}:affected-node",
                "affected_output_endpoint",
                declared.output_id,
                declared.node_id,
            )
        )

    commitments, _, commitment_error, commitment_evidence = (
        _load_behavior_commitment_inventory(blueprint)
    )
    if commitment_error:
        raise BlueprintError(
            "WORLD_BLUEPRINT_COMMITMENT_INVENTORY_NOT_CURRENT",
            "Blueprint queries require the same current independent behavior commitment authority as qualification.",
            details={
                "reason": commitment_error,
                **commitment_evidence,
            },
        )
    inventory_id = blueprint.commitment_inventory.inventory_id
    register(inventory_id, "commitment_inventory")
    connect(
        _edge_record(
            f"commitment-inventory:{inventory_id}:blueprint",
            "commitment_inventory_affects",
            inventory_id,
            blueprint.blueprint_id,
        )
    )
    for commitment in commitments:
        register(commitment.commitment_id, "behavior_commitment")
        register(commitment.behavior_id, "behavior")
        connect(
            _edge_record(
                f"commitment-inventory:{inventory_id}:{commitment.commitment_id}",
                "inventory_owns_commitment",
                inventory_id,
                commitment.commitment_id,
            )
        )
        connect(
            _edge_record(
                f"behavior:{commitment.behavior_id}:{commitment.commitment_id}",
                "behavior_owns_commitment",
                commitment.behavior_id,
                commitment.commitment_id,
            )
        )
        connect(
            _edge_record(
                f"commitment:{commitment.commitment_id}:output",
                "commitment_requires_output",
                commitment.commitment_id,
                commitment.output_id,
            )
        )
        connect(
            _edge_record(
                f"commitment:{commitment.commitment_id}:port",
                "commitment_requires_port",
                commitment.commitment_id,
                commitment.port_id,
            )
        )
        connect(
            _edge_record(
                f"commitment:{commitment.commitment_id}:node",
                "commitment_owned_by",
                commitment.commitment_id,
                commitment.node_id,
                owner_id=commitment.owner_id,
            )
        )
        for input_id in commitment.input_ids:
            connect(
                _edge_record(
                    f"commitment:{commitment.commitment_id}:input:{input_id}",
                    "commitment_input",
                    input_id,
                    commitment.commitment_id,
                )
            )

    for gap in blueprint.declared_gaps:
        register(gap.gap_id, "declared_gap")
        subjects = tuple(
            value
            for value in (
                gap.node_id,
                gap.element_id,
                gap.port_id,
            )
            if value
        )
        for index, subject_id in enumerate(subjects):
            connect(
                _edge_record(
                    f"declared-gap:{gap.gap_id}:subject:{index}",
                    "declared_gap",
                    subject_id,
                    gap.gap_id,
                )
            )
            connect(
                _edge_record(
                    f"declared-gap:{gap.gap_id}:affected:{index}",
                    "gap_affects",
                    gap.gap_id,
                    subject_id,
                )
            )

    contained_ids = tuple(sorted(set(kinds).difference({blueprint.blueprint_id})))
    for member_id in contained_ids:
        connect(
            _edge_record(
                f"blueprint-contains:{blueprint.blueprint_id}:{member_id}",
                "blueprint_contains",
                blueprint.blueprint_id,
                member_id,
            )
        )

    def freeze(rows: dict[str, list[dict[str, Any]]]) -> dict[str, tuple[dict[str, Any], ...]]:
        return {
            member_id: tuple(
                sorted(
                    values,
                    key=lambda row: (
                        row["edge_id"],
                        row["relation"],
                        row["source_id"],
                        row["target_id"],
                    ),
                )
            )
            for member_id, values in rows.items()
        }

    return _BlueprintIndexes(
        kinds=kinds,
        forward=freeze(forward_rows),
        reverse=freeze(reverse_rows),
        binding_ids=frozenset(binding_ids),
        input_port_ids=frozenset(input_ports),
        output_port_ids=frozenset(output_ports),
        declared_input_ids=frozenset(declared_input_ids),
    )


def _require_query_fingerprint(
    blueprint: WorldBlueprintContract,
    supplied_fingerprint: str,
) -> None:
    if supplied_fingerprint != blueprint.blueprint_fingerprint:
        raise BlueprintError(
            "WORLD_BLUEPRINT_QUERY_STALE",
            "Blueprint query fingerprint does not match the current blueprint.",
            details={
                "expected": blueprint.blueprint_fingerprint,
                "observed": supplied_fingerprint,
            },
        )


def _require_qualified_query_source(
    blueprint: WorldBlueprintContract,
    *,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> WorldBlueprintReport:
    """Qualify one query source before any derived index is materialized."""

    report = check_world_blueprint(
        blueprint,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    if report.status != GuardStatus.PASS or not report.native_domain_qualified:
        raise BlueprintError(
            "WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED",
            "Blueprint queries require one current native-qualified source report.",
            details={
                "blueprint_id": blueprint.blueprint_id,
                "blueprint_fingerprint": blueprint.blueprint_fingerprint,
                "qualification_report_fingerprint": report.report_fingerprint,
                "qualification_status": report.status.value,
                "native_domain_qualified": report.native_domain_qualified,
                "source_gap_ids": sorted(gap.gap_id for gap in report.gaps),
            },
        )
    return report


def blueprint_query_request_fingerprint(
    operation: str,
    *,
    blueprint_fingerprint: str,
    changed_ids: Sequence[str] = (),
    target_id: str = "",
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> str:
    operation = str(operation).strip()
    if operation not in {"impact", "trace"}:
        raise BlueprintError(
            "WORLD_BLUEPRINT_OPERATION_UNKNOWN",
            f"Unknown blueprint query operation: {operation or '<missing>'}.",
            details={"operation": operation},
        )
    payload: dict[str, Any] = {
        "operation": operation,
        "blueprint_fingerprint": _required_text(
            blueprint_fingerprint, "query.blueprint_fingerprint"
        ),
        "object_census_trust": {
            "authority_fingerprints": list(
                _normalized_trust_fingerprints(
                    trusted_object_census_authority_fingerprints,
                    "trusted_object_census_authority_fingerprints",
                )
            ),
            "producer_descriptor_fingerprints": list(
                _normalized_trust_fingerprints(
                    trusted_object_census_producer_descriptor_fingerprints,
                    "trusted_object_census_producer_descriptor_fingerprints",
                )
            ),
        },
    }
    if operation == "impact":
        normalized = sorted(set(str(value) for value in changed_ids if str(value)))
        if not normalized:
            raise BlueprintError(
                "WORLD_BLUEPRINT_IMPACT_REQUEST_EMPTY",
                "Impact request fingerprint requires changed ids.",
            )
        payload["changed_ids"] = normalized
    else:
        payload["target_id"] = _required_text(target_id, "query.target_id")
    return fingerprint_mesh(payload)


def blueprint_impact(
    blueprint: WorldBlueprintContract | Mapping[str, Any],
    *,
    blueprint_fingerprint: str,
    changed_ids: Sequence[str],
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> BlueprintImpactReport:
    if not isinstance(blueprint, WorldBlueprintContract):
        blueprint = WorldBlueprintContract.from_dict(blueprint)
    _require_query_fingerprint(blueprint, blueprint_fingerprint)
    _require_qualified_query_source(
        blueprint,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    indexes = _build_blueprint_indexes(blueprint)
    normalized = tuple(sorted(set(str(value) for value in changed_ids if str(value))))
    if not normalized:
        raise BlueprintError(
            "WORLD_BLUEPRINT_IMPACT_REQUEST_EMPTY",
            "Impact analysis requires at least one changed member id.",
        )
    unknown = sorted(set(normalized).difference(indexes.kinds))
    if unknown:
        raise BlueprintError(
            "WORLD_BLUEPRINT_QUERY_ID_UNKNOWN",
            "Impact analysis names ids outside the current blueprint.",
            details={"unknown_ids": unknown},
        )

    queue: deque[str] = deque(normalized)
    paths: dict[str, list[dict[str, Any]]] = {member_id: [] for member_id in normalized}
    traversed: dict[str, dict[str, Any]] = {}
    while queue:
        member_id = queue.popleft()
        for edge in indexes.forward.get(member_id, ()): 
            traversed[edge["edge_id"]] = edge
            target_id = edge["target_id"]
            if target_id not in paths:
                paths[target_id] = [*paths[member_id], edge]
                queue.append(target_id)

    affected_members = tuple(
        {
            "member_id": member_id,
            "member_kind": indexes.kinds.get(member_id, "edge_member"),
            "path_reason": paths[member_id][-1] if paths[member_id] else {
                "relation": "changed_input",
                "source_id": member_id,
                "target_id": member_id,
            },
            "path": paths[member_id],
        }
        for member_id in sorted(paths)
    )
    terminal_bindings = tuple(sorted(set(paths).intersection(indexes.binding_ids)))
    payload = {
        "operation": "impact",
        "blueprint_id": blueprint.blueprint_id,
        "blueprint_fingerprint": blueprint.blueprint_fingerprint,
        "changed_ids": list(normalized),
        "affected_members": list(affected_members),
        "traversed_edges": [traversed[key] for key in sorted(traversed)],
        "materialized_ids": sorted(paths),
        "terminal_binding_ids": list(terminal_bindings),
        "gaps": [],
        "claim_boundary": blueprint.declared_boundary,
    }
    return BlueprintImpactReport(
        blueprint_id=blueprint.blueprint_id,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        changed_ids=normalized,
        affected_members=affected_members,
        traversed_edges=tuple(traversed[key] for key in sorted(traversed)),
        materialized_ids=tuple(sorted(paths)),
        terminal_binding_ids=terminal_bindings,
        gaps=(),
        claim_boundary=blueprint.declared_boundary,
        result_fingerprint=fingerprint_mesh(payload),
    )


def blueprint_reverse_trace(
    blueprint: WorldBlueprintContract | Mapping[str, Any],
    *,
    blueprint_fingerprint: str,
    target_id: str,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> BlueprintTraceReport:
    if not isinstance(blueprint, WorldBlueprintContract):
        blueprint = WorldBlueprintContract.from_dict(blueprint)
    _require_query_fingerprint(blueprint, blueprint_fingerprint)
    blueprint_report = _require_qualified_query_source(
        blueprint,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    indexes = _build_blueprint_indexes(blueprint)
    target_id = str(target_id).strip()
    if target_id not in indexes.kinds:
        raise BlueprintError(
            "WORLD_BLUEPRINT_QUERY_ID_UNKNOWN",
            "Reverse trace target is outside the current blueprint.",
            details={"unknown_ids": [target_id]},
        )
    allowed_target_kinds = {
        "node",
        "node_input_port",
        "node_output_port",
        "element",
        "element_input_port",
        "element_output_port",
        "declared_output",
        "binding:target_material",
        "binding:evidence",
        "binding:test_check",
        "binding:native_result",
        "resource",
    }
    target_kind = indexes.kinds[target_id]
    if target_kind not in allowed_target_kinds:
        raise BlueprintError(
            "WORLD_BLUEPRINT_TRACE_TARGET_KIND_INVALID",
            "Reverse trace requires an output, node, element, port, binding, or material target.",
            details={
                "target_id": target_id,
                "target_kind": target_kind,
                "allowed_target_kinds": sorted(allowed_target_kinds),
            },
        )

    queue: deque[tuple[str, tuple[str, ...], tuple[dict[str, Any], ...]]] = deque(
        [(target_id, (target_id,), ())]
    )
    paths: dict[str, tuple[dict[str, Any], ...]] = {target_id: ()}
    traversed: dict[str, dict[str, Any]] = {}
    cycle_witnesses: dict[str, dict[str, Any]] = {}
    terminal_inputs: set[str] = set()
    terminal_bindings: set[str] = set()
    query_gaps: list[dict[str, Any]] = []

    while queue:
        member_id, path_ids, path_edges = queue.popleft()
        incoming = tuple(
            edge
            for edge in indexes.reverse.get(member_id, ())
            if edge["relation"]
            not in {
                "owned_output_port",
                "interface_owner",
                "binding_materializes_resource",
                "affected_source_endpoint",
                "affected_dependency_endpoint",
                "affected_output_endpoint",
                "gap_affects",
                "declares_input",
                "blueprint_contains",
                "commitment_requires_output",
                "commitment_requires_port",
                "commitment_owned_by",
            }
            and not edge["relation"].endswith("_binding")
        )
        if not incoming:
            member_kind = indexes.kinds.get(member_id, "")
            if member_id in indexes.declared_input_ids or member_kind == "resource":
                terminal_inputs.add(member_id)
            elif member_id in indexes.binding_ids:
                terminal_bindings.add(member_id)
            elif member_id in indexes.output_port_ids:
                query_gaps.append(
                    {
                        "gap_id": f"trace:broken-output:{member_id}",
                        "code": "WORLD_BLUEPRINT_TRACE_BROKEN_OUTPUT",
                        "message": "Output has no declared producer lineage.",
                        "member_id": member_id,
                        "claim_boundary": blueprint.declared_boundary,
                    }
                )
            elif member_id in indexes.input_port_ids:
                query_gaps.append(
                    {
                        "gap_id": f"trace:broken-input:{member_id}",
                        "code": "WORLD_BLUEPRINT_TRACE_BROKEN_INPUT",
                        "message": "Input has no declared external or mapped producer lineage.",
                        "member_id": member_id,
                        "claim_boundary": blueprint.declared_boundary,
                    }
                )
            else:
                query_gaps.append(
                    {
                        "gap_id": f"trace:non-terminal-dead-end:{member_id}",
                        "code": "WORLD_BLUEPRINT_TRACE_NON_TERMINAL_DEAD_END",
                        "message": "A non-terminal trace member has no declared producer lineage.",
                        "member_id": member_id,
                        "member_kind": member_kind,
                        "claim_boundary": blueprint.declared_boundary,
                    }
                )
            continue
        for edge in incoming:
            traversed[edge["edge_id"]] = edge
            source_id = edge["source_id"]
            reverse_edge = {
                **edge,
                "trace_direction": "target_to_source",
            }
            if source_id in path_ids:
                witness_ids = [*path_ids[path_ids.index(source_id) :], source_id]
                witness_id = f"cycle:{edge['edge_id']}:{source_id}"
                cycle_witnesses[witness_id] = {
                    "witness_id": witness_id,
                    "edge_id": edge["edge_id"],
                    "member_ids": witness_ids,
                }
                continue
            if source_id not in paths:
                new_edges = (*path_edges, reverse_edge)
                paths[source_id] = new_edges
                queue.append((source_id, (*path_ids, source_id), new_edges))
            if source_id in indexes.binding_ids:
                terminal_bindings.add(source_id)

    visited = set(paths)
    dependency_graph = {
        element.element_id: tuple(
            (dependency.depends_on_element_id, dependency.dependency_id)
            for dependency in element.dependencies
            if dependency.depends_on_element_id in visited
        )
        for element in blueprint.elements
        if element.element_id in visited
    }
    dependency_done: set[str] = set()
    dependency_active: list[str] = []

    def visit_dependencies(element_id: str) -> None:
        if element_id in dependency_active:
            cycle = [
                *dependency_active[dependency_active.index(element_id) :],
                element_id,
            ]
            witness_id = "cycle:dependency:" + ":".join(cycle)
            cycle_witnesses[witness_id] = {
                "witness_id": witness_id,
                "edge_id": "dependency-cycle",
                "member_ids": cycle,
            }
            return
        if element_id in dependency_done:
            return
        dependency_active.append(element_id)
        for upstream_id, _dependency_id in sorted(dependency_graph.get(element_id, ())):
            visit_dependencies(upstream_id)
        dependency_active.pop()
        dependency_done.add(element_id)

    for element_id in sorted(dependency_graph):
        visit_dependencies(element_id)
    for gap in blueprint_report.gaps:
        subjects = {gap.node_id, gap.element_id, gap.port_id, gap.binding_id}
        if visited.intersection(subject for subject in subjects if subject):
            query_gaps.append(
                {
                    "gap_id": gap.gap_id,
                    "code": "WORLD_BLUEPRINT_TRACE_BROKEN_HOP",
                    "source_code": gap.code,
                    "message": gap.message,
                    "member_ids": sorted(
                        visited.intersection(subject for subject in subjects if subject)
                    ),
                    "claim_boundary": gap.claim_boundary,
                }
            )

    traced_members = tuple(
        {
            "member_id": member_id,
            "member_kind": indexes.kinds.get(member_id, "edge_member"),
            "path": list(paths[member_id]),
        }
        for member_id in sorted(paths)
    )
    sorted_edges = tuple(traversed[key] for key in sorted(traversed))
    sorted_cycles = tuple(cycle_witnesses[key] for key in sorted(cycle_witnesses))
    sorted_gaps = tuple(
        sorted(query_gaps, key=lambda row: (str(row.get("gap_id", "")), str(row.get("code", ""))))
    )
    status = GuardStatus.GAP if sorted_gaps else GuardStatus.PASS
    payload = {
        "operation": "trace",
        "status": status.value,
        "blueprint_id": blueprint.blueprint_id,
        "blueprint_fingerprint": blueprint.blueprint_fingerprint,
        "target_id": target_id,
        "traced_members": list(traced_members),
        "traversed_edges": list(sorted_edges),
        "terminal_input_ids": sorted(terminal_inputs),
        "terminal_binding_ids": sorted(terminal_bindings),
        "cycle_witnesses": list(sorted_cycles),
        "gaps": list(sorted_gaps),
        "claim_boundary": blueprint.declared_boundary,
    }
    return BlueprintTraceReport(
        status=status,
        blueprint_id=blueprint.blueprint_id,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        target_id=target_id,
        traced_members=traced_members,
        traversed_edges=sorted_edges,
        terminal_input_ids=tuple(sorted(terminal_inputs)),
        terminal_binding_ids=tuple(sorted(terminal_bindings)),
        cycle_witnesses=sorted_cycles,
        gaps=sorted_gaps,
        claim_boundary=blueprint.declared_boundary,
        result_fingerprint=fingerprint_mesh(payload),
    )


__all__ = [
    "BINDING_ROLES",
    "BEHAVIOR_COMMITMENT_ADAPTER_REGISTRY",
    "BEHAVIOR_COMMITMENT_INPUT_KINDS",
    "BEHAVIOR_COMMITMENT_INPUT_MODES",
    "WORLD_BLUEPRINT_SCHEMA_VERSION",
    "WORLD_DEPENDENCY_RELATIONS",
    "WORLD_ELEMENT_KINDS",
    "BlueprintBinding",
    "BlueprintError",
    "BlueprintGap",
    "BlueprintImpactReport",
    "BlueprintLayerResult",
    "BlueprintLayerStatus",
    "BlueprintTraceReport",
    "BehaviorCommitmentAdapterRegistration",
    "BehaviorCommitmentAdapterRegistry",
    "BehaviorCommitmentInputRef",
    "BehaviorCommitmentInventoryRef",
    "BehaviorOutputCommitment",
    "ChildInputMapping",
    "ChildOutputMapping",
    "DeclaredBlueprintInput",
    "DeclaredBlueprintGap",
    "ElementInputMapping",
    "ElementDependency",
    "ElementOutputTerminal",
    "NativeSemanticRef",
    "OutputContribution",
    "ParentOutputDerivation",
    "TypedPort",
    "WorldBlueprintContract",
    "WorldBlueprintNode",
    "WorldBlueprintReport",
    "WorldElement",
    "blueprint_impact",
    "blueprint_query_request_fingerprint",
    "blueprint_reverse_trace",
    "check_world_blueprint",
    "load_world_blueprint",
]
