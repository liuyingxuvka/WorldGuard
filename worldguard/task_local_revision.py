"""Strict task-local prediction and reversible world-model revision.

The current route has one owner.  It freezes an independently bounded task
prediction before observation, runs the separate candidate mesh once with
independent original/holdout observations, derives gap transitions, and refuses to
close while any current predictive obligation remains open.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping


TASK_LOCAL_REVISION_SCHEMA_VERSION = "worldguard.task_local_revision.v2"
TASK_LOCAL_REVISION_OWNER_ID = "worldguard.task_local_world_revision"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class WorldMismatchCategory(StrEnum):
    INITIAL_STATE = "initial_state"
    TRANSITION = "transition"
    CAUSAL_RELATION = "causal_relation"
    RESOURCE = "resource"
    AGENT = "agent"
    OBSERVATION_MAPPING = "observation_mapping"
    OTHER = "other"


class WorldRevisionKind(StrEnum):
    UPDATE_INITIAL_STATE = "update_initial_state"
    UPDATE_TRANSITION = "update_transition"
    UPDATE_CAUSAL_RELATION = "update_causal_relation"
    UPDATE_RESOURCE = "update_resource"
    UPDATE_AGENT = "update_agent"
    UPDATE_OBSERVATION_MAPPING = "update_observation_mapping"
    UPDATE_BOUNDARY = "update_boundary"


class RevalidationRole(StrEnum):
    ORIGINAL_SCENARIO = "original_scenario"
    REAL_HOLDOUT_OBSERVATION = "real_holdout_observation"


_CURRENT_TERMINALS = {
    "continue_iteration",
    "model_closed_for_task",
    "external_input_required",
    "progress_stalled",
    "iteration_limit",
    "candidate_rejected",
    "candidate_rolled_back",
    "blocked",
}
_PREDICTIVE_GAP_PREFIXES = (
    "state",
    "transition",
    "branch",
    "perturbation",
    "intervention",
    "counterfactual",
    "holdout",
)


def _strict_fields(data: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")


def _require_fields(data: Mapping[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"{label} is missing current fields: {', '.join(missing)}")


def _text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} must be non-empty")
    return result


def _sha256_text(value: Any, label: str) -> str:
    result = _text(value, label).lower()
    if not SHA256_RE.fullmatch(result):
        raise ValueError(f"{label} must contain exactly 64 hexadecimal characters")
    return result


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_path(base_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else base_dir / path


def _unique_texts(raw: Any, label: str, *, non_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{label} must be a list")
    values = tuple(_text(item, label) for item in raw)
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    if non_empty and not values:
        raise ValueError(f"{label} must be non-empty")
    return values


def _receipt_body(
    data: Mapping[str, Any],
    *,
    artifact_kind: str,
    label: str,
) -> dict[str, Any]:
    if str(data.get("artifact_kind", "")) != artifact_kind:
        raise ValueError(f"{label} artifact_kind is not current")
    return dict(data)


def coverage_universe_fingerprint(
    *,
    universe_id: str,
    owner_id: str,
    source_ref: str,
    coverage_ids: tuple[str, ...] | list[str],
) -> str:
    return _fingerprint(
        {
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "universe_id": _text(universe_id, "coverage_universe_id"),
            "owner_id": _text(owner_id, "coverage_universe_owner_id"),
            "source_ref": _text(source_ref, "coverage_universe_source_ref"),
            "coverage_ids": sorted(_text(item, "coverage id") for item in coverage_ids),
        }
    )


@dataclass(frozen=True)
class WorldModelIdentity:
    model_id: str
    model_version: str
    path: str
    sha256: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorldModelIdentity":
        _strict_fields(data, {"model_id", "model_version", "path", "sha256"}, "world model identity")
        return cls(
            model_id=_text(data.get("model_id"), "model_id"),
            model_version=_text(data.get("model_version"), "model_version"),
            path=_text(data.get("path"), "path"),
            sha256=_sha256_text(data.get("sha256"), "sha256"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ExpectedWorldValue:
    expectation_id: str
    target_id: str
    expected_value: float
    tolerance: float
    mismatch_category: WorldMismatchCategory
    weakening_condition: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExpectedWorldValue":
        _strict_fields(
            data,
            {"expectation_id", "target_id", "expected_value", "tolerance", "mismatch_category", "weakening_condition"},
            "expected world value",
        )
        tolerance = _finite(data.get("tolerance"), "tolerance")
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        try:
            category = WorldMismatchCategory(_text(data.get("mismatch_category"), "mismatch_category"))
        except ValueError as exc:
            raise ValueError("mismatch_category is not a WorldGuard-native category") from exc
        return cls(
            expectation_id=_text(data.get("expectation_id"), "expectation_id"),
            target_id=_text(data.get("target_id"), "target_id"),
            expected_value=_finite(data.get("expected_value"), "expected_value"),
            tolerance=tolerance,
            mismatch_category=category,
            weakening_condition=_text(data.get("weakening_condition"), "weakening_condition"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "expectation_id": self.expectation_id,
            "target_id": self.target_id,
            "expected_value": self.expected_value,
            "tolerance": self.tolerance,
            "mismatch_category": self.mismatch_category.value,
            "weakening_condition": self.weakening_condition,
        }


@dataclass(frozen=True)
class ExpectedWorldRelationship:
    expectation_id: str
    relationship_id: str
    left: str
    relation: str
    right: str
    mismatch_category: WorldMismatchCategory
    weakening_condition: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExpectedWorldRelationship":
        _strict_fields(
            data,
            {"expectation_id", "relationship_id", "left", "relation", "right", "mismatch_category", "weakening_condition"},
            "expected world relationship",
        )
        try:
            category = WorldMismatchCategory(_text(data.get("mismatch_category"), "mismatch_category"))
        except ValueError as exc:
            raise ValueError("mismatch_category is not a WorldGuard-native category") from exc
        return cls(
            expectation_id=_text(data.get("expectation_id"), "expectation_id"),
            relationship_id=_text(data.get("relationship_id"), "relationship_id"),
            left=_text(data.get("left"), "left"),
            relation=_text(data.get("relation"), "relation"),
            right=_text(data.get("right"), "right"),
            mismatch_category=category,
            weakening_condition=_text(data.get("weakening_condition"), "weakening_condition"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "expectation_id": self.expectation_id,
            "relationship_id": self.relationship_id,
            "left": self.left,
            "relation": self.relation,
            "right": self.right,
            "mismatch_category": self.mismatch_category.value,
            "weakening_condition": self.weakening_condition,
        }


@dataclass(frozen=True)
class ExternalInputRequirement:
    input_id: str
    owner_id: str
    reason: str
    blocked_gap_ids: tuple[str, ...]
    affected_claim_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExternalInputRequirement":
        allowed = {"input_id", "owner_id", "reason", "blocked_gap_ids", "affected_claim_ids"}
        _strict_fields(data, allowed, "external input requirement")
        _require_fields(data, allowed, "external input requirement")
        return cls(
            input_id=_text(data.get("input_id"), "external input id"),
            owner_id=_text(data.get("owner_id"), "external input owner id"),
            reason=_text(data.get("reason"), "external input reason"),
            blocked_gap_ids=_unique_texts(data.get("blocked_gap_ids"), "blocked_gap_ids", non_empty=True),
            affected_claim_ids=_unique_texts(data.get("affected_claim_ids"), "affected_claim_ids", non_empty=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "owner_id": self.owner_id,
            "reason": self.reason,
            "blocked_gap_ids": list(self.blocked_gap_ids),
            "affected_claim_ids": list(self.affected_claim_ids),
        }


@dataclass(frozen=True)
class PredictionSnapshot:
    prediction_id: str
    task_id: str
    purpose: str
    coverage_universe_id: str
    coverage_universe_owner_id: str
    coverage_universe_source_ref: str
    coverage_universe_fingerprint: str
    coverage_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    iteration: int
    max_iterations: int
    predecessor_iteration_fingerprint: str
    prior_gap_ids: tuple[str, ...]
    prior_gap_fingerprints: tuple[str, ...]
    model: WorldModelIdentity
    prediction_sequence: int
    initial_state: dict[str, Any]
    intervention: dict[str, Any]
    expected_values: tuple[ExpectedWorldValue, ...]
    expected_relationships: tuple[ExpectedWorldRelationship, ...]
    weakening_conditions: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictionSnapshot":
        allowed = {
            "schema_version", "prediction_id", "task_id", "purpose",
            "coverage_universe_id", "coverage_universe_owner_id", "coverage_universe_source_ref",
            "coverage_universe_fingerprint", "coverage_ids", "assumptions", "unknowns",
            "iteration", "max_iterations", "predecessor_iteration_fingerprint", "prior_gap_ids",
            "prior_gap_fingerprints",
            "model", "prediction_sequence", "initial_state", "intervention", "expected_values",
            "expected_relationships", "weakening_conditions",
        }
        _strict_fields(data, allowed, "prediction snapshot")
        _require_fields(data, allowed - {"coverage_universe_fingerprint", "prior_gap_fingerprints"}, "prediction snapshot")
        if data.get("schema_version") != TASK_LOCAL_REVISION_SCHEMA_VERSION:
            raise ValueError("prediction snapshot schema_version is not current")
        model = data.get("model")
        if not isinstance(model, Mapping):
            raise ValueError("prediction model must be a mapping")
        initial_state = data.get("initial_state")
        intervention = data.get("intervention")
        if not isinstance(initial_state, Mapping) or not isinstance(intervention, Mapping):
            raise ValueError("initial_state and intervention must be mappings")
        try:
            sequence = int(data.get("prediction_sequence"))
            iteration = int(data.get("iteration"))
            max_iterations = int(data.get("max_iterations"))
        except (TypeError, ValueError) as exc:
            raise ValueError("prediction sequence and iteration fields must be integers") from exc
        if (
            sequence < 0
            or isinstance(data.get("prediction_sequence"), bool)
            or isinstance(data.get("iteration"), bool)
            or isinstance(data.get("max_iterations"), bool)
        ):
            raise ValueError("prediction_sequence must be a non-negative integer")
        if iteration < 0 or max_iterations < 1 or iteration >= max_iterations:
            raise ValueError("iteration must be inside the finite max_iterations budget")
        value_rows = data.get("expected_values")
        relationship_rows = data.get("expected_relationships")
        if not isinstance(value_rows, list) or not isinstance(relationship_rows, list):
            raise ValueError("expected_values and expected_relationships must be lists")
        expected_values = tuple(ExpectedWorldValue.from_dict(row) for row in value_rows if isinstance(row, Mapping))
        expected_relationships = tuple(ExpectedWorldRelationship.from_dict(row) for row in relationship_rows if isinstance(row, Mapping))
        if len(expected_values) != len(value_rows) or len(expected_relationships) != len(relationship_rows):
            raise ValueError("prediction expectations must be mappings")
        if not expected_values and not expected_relationships:
            raise ValueError("prediction requires at least one expected value or relationship")
        expectation_ids = [*(row.expectation_id for row in expected_values), *(row.expectation_id for row in expected_relationships)]
        if len(expectation_ids) != len(set(expectation_ids)):
            raise ValueError("expectation ids must be unique")
        coverage_ids = _unique_texts(data.get("coverage_ids"), "coverage_ids", non_empty=True)
        if set(coverage_ids) != set(expectation_ids):
            raise ValueError("coverage_ids must exactly equal the independently bounded expectation ids")
        assumptions = _unique_texts(data.get("assumptions"), "assumptions", non_empty=True)
        unknowns = _unique_texts(data.get("unknowns"), "unknowns", non_empty=True)
        prior_gap_ids = _unique_texts(data.get("prior_gap_ids"), "prior_gap_ids")
        prior = tuple(_sha256_text(item, "prior gap fingerprint") for item in _unique_texts(data.get("prior_gap_fingerprints", []), "prior_gap_fingerprints"))
        predecessor = _text(data.get("predecessor_iteration_fingerprint"), "predecessor_iteration_fingerprint")
        if iteration == 0:
            if predecessor != "root" or prior or prior_gap_ids:
                raise ValueError("iteration zero requires predecessor 'root' and no prior gaps")
        else:
            predecessor = _sha256_text(predecessor, "predecessor_iteration_fingerprint")
            if not prior_gap_ids:
                raise ValueError("later iterations require exact prior gap ids")
            latest = _fingerprint(sorted(prior_gap_ids))
            if not prior or prior[-1] != latest:
                prior = (*prior, latest)
        universe_id = _text(data.get("coverage_universe_id"), "coverage_universe_id")
        universe_owner = _text(data.get("coverage_universe_owner_id"), "coverage_universe_owner_id")
        universe_source = _text(data.get("coverage_universe_source_ref"), "coverage_universe_source_ref")
        expected_universe_fingerprint = coverage_universe_fingerprint(
            universe_id=universe_id,
            owner_id=universe_owner,
            source_ref=universe_source,
            coverage_ids=coverage_ids,
        )
        if data.get("coverage_universe_fingerprint") not in (None, expected_universe_fingerprint):
            raise ValueError("coverage_universe_fingerprint does not match the independent inventory")
        weakening = _unique_texts(data.get("weakening_conditions"), "weakening_conditions", non_empty=True)
        return cls(
            prediction_id=_text(data.get("prediction_id"), "prediction_id"),
            task_id=_text(data.get("task_id"), "task_id"),
            purpose=_text(data.get("purpose"), "purpose"),
            coverage_universe_id=universe_id,
            coverage_universe_owner_id=universe_owner,
            coverage_universe_source_ref=universe_source,
            coverage_universe_fingerprint=expected_universe_fingerprint,
            coverage_ids=coverage_ids,
            assumptions=assumptions,
            unknowns=unknowns,
            iteration=iteration,
            max_iterations=max_iterations,
            predecessor_iteration_fingerprint=predecessor,
            prior_gap_ids=prior_gap_ids,
            prior_gap_fingerprints=prior,
            model=WorldModelIdentity.from_dict(model),
            prediction_sequence=sequence,
            initial_state=dict(initial_state),
            intervention=dict(intervention),
            expected_values=expected_values,
            expected_relationships=expected_relationships,
            weakening_conditions=weakening,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "prediction_id": self.prediction_id,
            "task_id": self.task_id,
            "purpose": self.purpose,
            "coverage_universe_id": self.coverage_universe_id,
            "coverage_universe_owner_id": self.coverage_universe_owner_id,
            "coverage_universe_source_ref": self.coverage_universe_source_ref,
            "coverage_universe_fingerprint": self.coverage_universe_fingerprint,
            "coverage_ids": list(self.coverage_ids),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "predecessor_iteration_fingerprint": self.predecessor_iteration_fingerprint,
            "prior_gap_ids": list(self.prior_gap_ids),
            "prior_gap_fingerprints": list(self.prior_gap_fingerprints),
            "model": self.model.to_dict(),
            "prediction_sequence": self.prediction_sequence,
            "initial_state": self.initial_state,
            "intervention": self.intervention,
            "expected_values": [item.to_dict() for item in self.expected_values],
            "expected_relationships": [item.to_dict() for item in self.expected_relationships],
            "weakening_conditions": list(self.weakening_conditions),
        }


@dataclass(frozen=True)
class ObservedWorldRelationship:
    relationship_id: str
    left: str
    relation: str
    right: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObservedWorldRelationship":
        _strict_fields(data, {"relationship_id", "left", "relation", "right"}, "observed world relationship")
        return cls(
            relationship_id=_text(data.get("relationship_id"), "relationship_id"),
            left=_text(data.get("left"), "left"),
            relation=_text(data.get("relation"), "relation"),
            right=_text(data.get("right"), "right"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"relationship_id": self.relationship_id, "left": self.left, "relation": self.relation, "right": self.right}


def observation_evidence_fingerprint(
    *,
    observation_id: str,
    prediction_id: str,
    observation_sequence: int,
    source_ref: str,
    values: Mapping[str, float],
    relationships: tuple[ObservedWorldRelationship, ...] | list[ObservedWorldRelationship],
    external_inputs: tuple[ExternalInputRequirement, ...] | list[ExternalInputRequirement],
) -> str:
    return _fingerprint(
        {
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "observation_id": observation_id,
            "prediction_id": prediction_id,
            "observation_sequence": observation_sequence,
            "source_ref": source_ref,
            "values": dict(values),
            "relationships": [item.to_dict() for item in relationships],
            "external_inputs": [item.to_dict() for item in external_inputs],
        }
    )


def observation_content_fingerprint(
    *,
    values: Mapping[str, float],
    relationships: tuple[ObservedWorldRelationship, ...] | list[ObservedWorldRelationship],
    external_inputs: tuple[ExternalInputRequirement, ...] | list[ExternalInputRequirement],
) -> str:
    """Fingerprint observation content independently of renameable ids and refs."""

    return _fingerprint(
        {
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "values": dict(values),
            "relationships": [item.to_dict() for item in relationships],
            "external_inputs": [item.to_dict() for item in external_inputs],
        }
    )


@dataclass(frozen=True)
class ObservedWorldSnapshot:
    observation_id: str
    prediction_id: str
    observation_sequence: int
    source_ref: str
    values: dict[str, float]
    relationships: tuple[ObservedWorldRelationship, ...]
    evidence_id: str
    evidence_fingerprint: str
    external_inputs: tuple[ExternalInputRequirement, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObservedWorldSnapshot":
        allowed = {
            "schema_version", "observation_id", "prediction_id", "observation_sequence", "source_ref",
            "values", "relationships", "evidence_id", "evidence_fingerprint", "external_inputs",
        }
        _strict_fields(data, allowed, "observed world snapshot")
        _require_fields(data, allowed - {"evidence_fingerprint"}, "observed world snapshot")
        if data.get("schema_version") != TASK_LOCAL_REVISION_SCHEMA_VERSION:
            raise ValueError("observed world snapshot schema_version is not current")
        try:
            sequence = int(data.get("observation_sequence"))
        except (TypeError, ValueError) as exc:
            raise ValueError("observation_sequence must be a non-negative integer") from exc
        if sequence < 0 or isinstance(data.get("observation_sequence"), bool):
            raise ValueError("observation_sequence must be a non-negative integer")
        raw_values = data.get("values")
        raw_relationships = data.get("relationships")
        raw_external = data.get("external_inputs")
        if not isinstance(raw_values, Mapping) or not isinstance(raw_relationships, list) or not isinstance(raw_external, list):
            raise ValueError("observation values must be a mapping and relationships/external_inputs lists")
        values = {_text(key, "observed value target"): _finite(value, f"observed value for {key}") for key, value in raw_values.items()}
        relationships = tuple(ObservedWorldRelationship.from_dict(row) for row in raw_relationships if isinstance(row, Mapping))
        external_inputs = tuple(ExternalInputRequirement.from_dict(row) for row in raw_external if isinstance(row, Mapping))
        if len(relationships) != len(raw_relationships) or len(external_inputs) != len(raw_external):
            raise ValueError("observed relationships and external inputs must be mappings")
        if len({item.relationship_id for item in relationships}) != len(relationships):
            raise ValueError("observed relationship ids must be unique")
        if len({item.input_id for item in external_inputs}) != len(external_inputs):
            raise ValueError("external input ids must be unique")
        if not values and not relationships and not external_inputs:
            raise ValueError("observation requires actual evidence or an exact external input requirement")
        observation_id = _text(data.get("observation_id"), "observation_id")
        prediction_id = _text(data.get("prediction_id"), "prediction_id")
        source_ref = _text(data.get("source_ref"), "source_ref")
        expected = observation_evidence_fingerprint(
            observation_id=observation_id,
            prediction_id=prediction_id,
            observation_sequence=sequence,
            source_ref=source_ref,
            values=values,
            relationships=relationships,
            external_inputs=external_inputs,
        )
        if data.get("evidence_fingerprint") not in (None, expected):
            raise ValueError("observation evidence_fingerprint is stale or tampered")
        return cls(
            observation_id=observation_id,
            prediction_id=prediction_id,
            observation_sequence=sequence,
            source_ref=source_ref,
            values=values,
            relationships=relationships,
            evidence_id=_text(data.get("evidence_id"), "evidence_id"),
            evidence_fingerprint=expected,
            external_inputs=external_inputs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "observation_id": self.observation_id,
            "prediction_id": self.prediction_id,
            "observation_sequence": self.observation_sequence,
            "source_ref": self.source_ref,
            "values": self.values,
            "relationships": [item.to_dict() for item in self.relationships],
            "evidence_id": self.evidence_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "external_inputs": [item.to_dict() for item in self.external_inputs],
        }


@dataclass(frozen=True)
class RevalidationCheck:
    check_id: str
    role: RevalidationRole
    empirical_comparison: dict[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RevalidationCheck":
        allowed = {"check_id", "role", "empirical_comparison"}
        _strict_fields(data, allowed, "revalidation check")
        _require_fields(data, allowed, "revalidation check")
        comparison = data.get("empirical_comparison")
        if not isinstance(comparison, Mapping):
            raise ValueError("revalidation empirical_comparison must be a mapping")
        try:
            role = RevalidationRole(_text(data.get("role"), "role"))
        except ValueError as exc:
            raise ValueError("revalidation role is not supported") from exc
        return cls(check_id=_text(data.get("check_id"), "check_id"), role=role, empirical_comparison=dict(comparison))

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "role": self.role.value, "empirical_comparison": self.empirical_comparison}


@dataclass(frozen=True)
class CandidateWorldModelRevision:
    revision_id: str
    prediction_id: str
    base_model: WorldModelIdentity
    candidate_model: WorldModelIdentity
    revision_kind: WorldRevisionKind
    prediction_receipt: dict[str, Any]
    comparison_receipt: dict[str, Any]
    candidate_build_evidence_fingerprints: tuple[str, ...]
    required_revalidation_ids: tuple[str, ...]
    revalidations: tuple[RevalidationCheck, ...]
    candidate_applied: bool
    rollback_model: WorldModelIdentity | None
    external_inputs: tuple[ExternalInputRequirement, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateWorldModelRevision":
        allowed = {
            "schema_version", "revision_id", "prediction_id", "base_model", "candidate_model", "revision_kind",
            "prediction_receipt", "comparison_receipt", "candidate_build_evidence_fingerprints",
            "required_revalidation_ids", "revalidations", "candidate_applied", "rollback_model", "external_inputs",
        }
        _strict_fields(data, allowed, "candidate world-model revision")
        _require_fields(data, allowed, "candidate world-model revision")
        if data.get("schema_version") != TASK_LOCAL_REVISION_SCHEMA_VERSION:
            raise ValueError("candidate revision schema_version is not current")
        base = data.get("base_model")
        candidate = data.get("candidate_model")
        prediction_receipt = data.get("prediction_receipt")
        comparison_receipt = data.get("comparison_receipt")
        if not all(isinstance(item, Mapping) for item in (base, candidate, prediction_receipt, comparison_receipt)):
            raise ValueError("candidate revision identities and receipts must be mappings")
        try:
            revision_kind = WorldRevisionKind(_text(data.get("revision_kind"), "revision_kind"))
        except ValueError as exc:
            raise ValueError("revision_kind is not a task-local WorldGuard operation") from exc
        required_ids = _unique_texts(data.get("required_revalidation_ids"), "required_revalidation_ids", non_empty=True)
        current_revalidation_ids = {
            RevalidationRole.ORIGINAL_SCENARIO.value,
            RevalidationRole.REAL_HOLDOUT_OBSERVATION.value,
        }
        if set(required_ids) != current_revalidation_ids or len(required_ids) != 2:
            raise ValueError("required_revalidation_ids must be the two current typed roles")
        rows = data.get("revalidations")
        if not isinstance(rows, list):
            raise ValueError("revalidations must be a list")
        revalidations = tuple(RevalidationCheck.from_dict(row) for row in rows if isinstance(row, Mapping))
        if len(revalidations) != len(rows):
            raise ValueError("revalidations must be mappings")
        check_ids = tuple(item.check_id for item in revalidations)
        if len(check_ids) != len(set(check_ids)) or set(check_ids) != set(required_ids):
            raise ValueError("revalidations must exactly equal required_revalidation_ids")
        roles = [item.role for item in revalidations]
        if roles.count(RevalidationRole.ORIGINAL_SCENARIO) != 1 or roles.count(RevalidationRole.REAL_HOLDOUT_OBSERVATION) != 1 or len(roles) != 2:
            raise ValueError("candidate revision requires exactly one original and one real holdout receipt")
        applied = data.get("candidate_applied")
        if not isinstance(applied, bool):
            raise ValueError("candidate_applied must be boolean")
        rollback = data.get("rollback_model")
        if applied and not isinstance(rollback, Mapping):
            raise ValueError("an applied candidate requires rollback_model")
        if not applied and rollback is not None:
            raise ValueError("rollback_model is only valid after candidate application")
        build_evidence = tuple(_sha256_text(item, "candidate build evidence fingerprint") for item in _unique_texts(data.get("candidate_build_evidence_fingerprints"), "candidate_build_evidence_fingerprints", non_empty=True))
        external_rows = data.get("external_inputs")
        if not isinstance(external_rows, list):
            raise ValueError("external_inputs must be a list")
        external = tuple(ExternalInputRequirement.from_dict(row) for row in external_rows if isinstance(row, Mapping))
        if len(external) != len(external_rows) or len({item.input_id for item in external}) != len(external):
            raise ValueError("external_inputs must be unique mappings")
        return cls(
            revision_id=_text(data.get("revision_id"), "revision_id"),
            prediction_id=_text(data.get("prediction_id"), "prediction_id"),
            base_model=WorldModelIdentity.from_dict(base),
            candidate_model=WorldModelIdentity.from_dict(candidate),
            revision_kind=revision_kind,
            prediction_receipt=dict(prediction_receipt),
            comparison_receipt=dict(comparison_receipt),
            candidate_build_evidence_fingerprints=build_evidence,
            required_revalidation_ids=required_ids,
            revalidations=revalidations,
            candidate_applied=applied,
            rollback_model=WorldModelIdentity.from_dict(rollback) if isinstance(rollback, Mapping) else None,
            external_inputs=external,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "revision_id": self.revision_id,
            "prediction_id": self.prediction_id,
            "base_model": self.base_model.to_dict(),
            "candidate_model": self.candidate_model.to_dict(),
            "revision_kind": self.revision_kind.value,
            "prediction_receipt": self.prediction_receipt,
            "comparison_receipt": self.comparison_receipt,
            "candidate_build_evidence_fingerprints": list(self.candidate_build_evidence_fingerprints),
            "required_revalidation_ids": list(self.required_revalidation_ids),
            "revalidations": [item.to_dict() for item in self.revalidations],
            "candidate_applied": self.candidate_applied,
            "rollback_model": self.rollback_model.to_dict() if self.rollback_model else None,
            "external_inputs": [item.to_dict() for item in self.external_inputs],
        }


def _identity_receipt(identity: WorldModelIdentity, base_dir: Path) -> dict[str, Any]:
    path = _resolve_path(base_dir, identity.path)
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    return {
        **identity.to_dict(),
        "resolved_path": str(path.resolve()) if path.exists() else str(path),
        "actual_sha256": actual,
        "status": "current" if actual == identity.sha256 else "stale",
    }


def _same_identity(left: WorldModelIdentity, right: WorldModelIdentity) -> bool:
    return left.to_dict() == right.to_dict()


def freeze_prediction_snapshot(prediction: PredictionSnapshot, *, base_dir: Path) -> dict[str, Any]:
    model = _identity_receipt(prediction.model, base_dir)
    return (
        {
            "artifact_kind": "worldguard_prediction_snapshot_receipt",
            "receipt_version": "2.0",
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "owner_id": TASK_LOCAL_REVISION_OWNER_ID,
            "status": "pass" if model["status"] == "current" else "blocked",
            "prediction_id": prediction.prediction_id,
            "task_id": prediction.task_id,
            "purpose": prediction.purpose,
            "coverage_universe_id": prediction.coverage_universe_id,
            "coverage_universe_owner_id": prediction.coverage_universe_owner_id,
            "coverage_universe_source_ref": prediction.coverage_universe_source_ref,
            "coverage_universe_fingerprint": prediction.coverage_universe_fingerprint,
            "coverage_ids": list(prediction.coverage_ids),
            "assumptions": list(prediction.assumptions),
            "unknowns": list(prediction.unknowns),
            "iteration": prediction.iteration,
            "max_iterations": prediction.max_iterations,
            "predecessor_iteration_fingerprint": prediction.predecessor_iteration_fingerprint,
            "prior_gap_fingerprints": list(prediction.prior_gap_fingerprints),
            "prior_gap_ids": list(prediction.prior_gap_ids),
            "prediction_sequence": prediction.prediction_sequence,
            "model_identity": model,
            "prediction_fingerprint": _fingerprint(prediction.to_dict()),
            "expected_value_count": len(prediction.expected_values),
            "expected_relationship_count": len(prediction.expected_relationships),
            "weakening_conditions": list(prediction.weakening_conditions),
            "claim_boundary": "This freezes one independently bounded task prediction before observation; it does not prove empirical accuracy or task closure.",
        }
    )


def _external_input_findings(
    external_inputs: tuple[ExternalInputRequirement, ...],
    open_gap_ids: set[str],
) -> tuple[list[str], set[str]]:
    declared: list[str] = [gap_id for item in external_inputs for gap_id in item.blocked_gap_ids]
    findings: list[str] = []
    if len(declared) != len(set(declared)):
        findings.append("external_gap_has_multiple_owners")
    unknown = sorted(set(declared) - open_gap_ids)
    if unknown:
        findings.append("external_input_names_non_open_gap")
    return findings, set(declared)


def compare_observed_world(
    prediction: PredictionSnapshot,
    observation: ObservedWorldSnapshot,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    if observation.prediction_id != prediction.prediction_id:
        raise ValueError("observation prediction_id does not match the prediction snapshot")
    if observation.observation_sequence <= prediction.prediction_sequence:
        raise ValueError("observation_sequence must be strictly later than prediction_sequence")
    frozen = freeze_prediction_snapshot(prediction, base_dir=base_dir)
    if frozen["status"] != "pass":
        raise ValueError("prediction snapshot model identity is not current")

    matches: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for expected in prediction.expected_values:
        actual = observation.values.get(expected.target_id)
        common = {
            "expectation_id": expected.expectation_id,
            "expectation_kind": "value",
            "target_id": expected.target_id,
            "mismatch_category": expected.mismatch_category.value,
            "expected_value": expected.expected_value,
            "tolerance": expected.tolerance,
            "weakening_condition": expected.weakening_condition,
        }
        if actual is None:
            mismatches.append({**common, "mismatch_id": f"{prediction.prediction_id}:{expected.expectation_id}:missing", "mismatch_code": "expected_value_missing", "actual_value": None})
        elif abs(actual - expected.expected_value) > expected.tolerance:
            mismatches.append({**common, "mismatch_id": f"{prediction.prediction_id}:{expected.expectation_id}:contradicted", "mismatch_code": "value_outside_tolerance", "actual_value": actual})
        else:
            matches.append({**common, "actual_value": actual})

    observed_relationships = {item.relationship_id: item for item in observation.relationships}
    for expected in prediction.expected_relationships:
        actual = observed_relationships.get(expected.relationship_id)
        common = {
            "expectation_id": expected.expectation_id,
            "expectation_kind": "relationship",
            "relationship_id": expected.relationship_id,
            "mismatch_category": expected.mismatch_category.value,
            "expected_relationship": {"left": expected.left, "relation": expected.relation, "right": expected.right},
            "weakening_condition": expected.weakening_condition,
        }
        if actual is None:
            mismatches.append({**common, "mismatch_id": f"{prediction.prediction_id}:{expected.expectation_id}:missing", "mismatch_code": "expected_relationship_missing", "actual_relationship": None})
        elif (actual.left, actual.relation, actual.right) != (expected.left, expected.relation, expected.right):
            mismatches.append({**common, "mismatch_id": f"{prediction.prediction_id}:{expected.expectation_id}:contradicted", "mismatch_code": "relationship_contradicted", "actual_relationship": actual.to_dict()})
        else:
            matches.append({**common, "actual_relationship": actual.to_dict()})

    mismatch_ids = sorted(item["mismatch_id"] for item in mismatches)
    observed_expectation_ids = {item["expectation_id"] for item in (*matches, *mismatches)}
    coverage_gaps = sorted(f"coverage:{coverage_id}" for coverage_id in prediction.coverage_ids if coverage_id not in observed_expectation_ids)
    open_gap_ids = sorted(set(mismatch_ids) | set(coverage_gaps))
    gap_fingerprint = _fingerprint(open_gap_ids)
    external_findings, externally_blocked = _external_input_findings(observation.external_inputs, set(open_gap_ids))
    if external_findings:
        terminal_reason = "blocked"
    elif open_gap_ids and externally_blocked == set(open_gap_ids):
        terminal_reason = "external_input_required"
    elif open_gap_ids and prediction.iteration + 1 >= prediction.max_iterations:
        terminal_reason = "iteration_limit"
    elif open_gap_ids and gap_fingerprint in set(prediction.prior_gap_fingerprints):
        terminal_reason = "progress_stalled"
    else:
        terminal_reason = "continue_iteration"
    next_actions = sorted(
        {
            *("revise_world_model" for item in mismatch_ids if item not in externally_blocked),
            *("acquire_declared_coverage" for item in coverage_gaps if item not in externally_blocked),
            *(f"obtain_external_input:{item.input_id}" for item in observation.external_inputs),
            *("evaluate_candidate_native_depth" for _ in [0] if not open_gap_ids),
        }
    )
    status = "blocked" if external_findings else ("pass" if not mismatches and not coverage_gaps else "fail")
    return (
        {
            "artifact_kind": "worldguard_observed_world_comparison_receipt",
            "receipt_version": "2.0",
            "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
            "owner_id": TASK_LOCAL_REVISION_OWNER_ID,
            "status": status,
            "prediction_id": prediction.prediction_id,
            "observation_id": observation.observation_id,
            "task_id": prediction.task_id,
            "purpose": prediction.purpose,
            "prediction_sequence": prediction.prediction_sequence,
            "observation_sequence": observation.observation_sequence,
            "source_ref": observation.source_ref,
            "evidence_id": observation.evidence_id,
            "observation_evidence_fingerprint": observation.evidence_fingerprint,
            "observation_content_fingerprint": observation_content_fingerprint(
                values=observation.values,
                relationships=observation.relationships,
                external_inputs=observation.external_inputs,
            ),
            "model_identity": frozen["model_identity"],
            "prediction_fingerprint": frozen["prediction_fingerprint"],
            "coverage_universe_fingerprint": prediction.coverage_universe_fingerprint,
            "matches": matches,
            "mismatches": mismatches,
            "mismatch_ids": mismatch_ids,
            "coverage_gap_ids": coverage_gaps,
            "input_gap_ids": open_gap_ids,
            "gap_fingerprint": gap_fingerprint,
            "external_inputs": [item.to_dict() for item in observation.external_inputs],
            "external_binding_findings": external_findings,
            "next_actions": next_actions,
            "terminal_reason": terminal_reason,
            "iteration": prediction.iteration,
            "claim_boundary": "This receipt compares only the independently declared task universe with one later content-addressed observation. It cannot close the task without current native depth and independent candidate revalidation.",
        }
    )


def _load_candidate_mesh(candidate_model: WorldModelIdentity, base_dir: Path):
    """Load the candidate as a native mesh; other model kinds cannot close a revision."""
    from .io import load_mapping
    from .mesh import ModelMeshContract

    identity = _identity_receipt(candidate_model, base_dir)
    if identity["status"] != "current":
        raise ValueError("candidate model identity is not current")
    payload = load_mapping(identity["resolved_path"])
    raw = payload.get("mesh", payload)
    if not isinstance(raw, Mapping) or not raw.get("mesh_id") or not isinstance(raw.get("nodes"), list) or not raw["nodes"]:
        raise ValueError("revision closure supports a current native mesh candidate only")
    return ModelMeshContract.from_dict(raw)


def _comparison_binds_model(comparison: Mapping[str, Any], model: WorldModelIdentity) -> bool:
    identity = comparison.get("model_identity")
    if not isinstance(identity, Mapping):
        return False
    return (
        str(identity.get("model_id", "")) == model.model_id
        and str(identity.get("model_version", "")) == model.model_version
        and str(identity.get("path", "")) == model.path
        and str(identity.get("sha256", "")).lower() == model.sha256
        and str(identity.get("actual_sha256", "")).lower() == model.sha256
        and str(identity.get("status", "")).lower() == "current"
    )


def _predictive_gap_categories(gaps: list[str]) -> dict[str, list[str]]:
    result = {category: [] for category in _PREDICTIVE_GAP_PREFIXES}
    for gap in gaps:
        # Native mesh gap identities include predictive_object/... prefixes;
        # keep the exact ids rather than requiring caller-invented categories.
        categories = [category for category in result if re.search(r"(?:^|[_:])" + category + r"(?:$|[_:])", gap)]
        for category in categories or ["other"]:
            result.setdefault(category, []).append(gap)
    return {key: sorted(value) for key, value in result.items()}


def evaluate_candidate_world_revision(revision: CandidateWorldModelRevision, *, base_dir: Path) -> dict[str, Any]:
    base = _identity_receipt(revision.base_model, base_dir)
    candidate = _identity_receipt(revision.candidate_model, base_dir)
    findings: list[str] = []
    if base["status"] != "current":
        findings.append("base_model_identity_stale")
    if candidate["status"] != "current":
        findings.append("candidate_model_identity_stale")
    if Path(base["resolved_path"]) == Path(candidate["resolved_path"]) or base["actual_sha256"] == candidate["actual_sha256"]:
        findings.append("candidate_not_distinct_from_base")

    try:
        prediction_body = _receipt_body(revision.prediction_receipt, artifact_kind="worldguard_prediction_snapshot_receipt", label="prediction")
        comparison_body = _receipt_body(revision.comparison_receipt, artifact_kind="worldguard_observed_world_comparison_receipt", label="comparison")
    except ValueError as exc:
        prediction_body = {}
        comparison_body = {}
        findings.append(str(exc))
    task_id = str(prediction_body.get("task_id", ""))
    coverage_fingerprint = str(prediction_body.get("coverage_universe_fingerprint", ""))
    iteration = int(prediction_body.get("iteration", 0) or 0)
    max_iterations = int(prediction_body.get("max_iterations", 1) or 1)
    prior_gap_fingerprints = set(prediction_body.get("prior_gap_fingerprints", [])) if isinstance(prediction_body.get("prior_gap_fingerprints", []), list) else set()
    if revision.prediction_id != prediction_body.get("prediction_id") or revision.prediction_id != comparison_body.get("prediction_id"):
        findings.append("prediction_receipt_identity_mismatch")
    if prediction_body.get("status") != "pass":
        findings.append("prediction_receipt_non_pass")
    if comparison_body.get("task_id") != task_id or comparison_body.get("coverage_universe_fingerprint") != coverage_fingerprint:
        findings.append("comparison_task_or_coverage_mismatch")
    if not _comparison_binds_model(comparison_body, revision.base_model):
        findings.append("comparison_base_model_identity_mismatch")
    candidate_mesh = None
    mesh_report = None
    try:
        from .mesh import run_model_mesh

        candidate_mesh = _load_candidate_mesh(revision.candidate_model, base_dir)
        mesh_report = run_model_mesh(candidate_mesh)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        findings.append(f"candidate_mesh_not_runnable:{exc}")

    check_results: list[dict[str, Any]] = []
    for check in revision.revalidations:
        issues: list[str] = []
        comparison = check.empirical_comparison
        try:
            comparison_receipt = _receipt_body(comparison, artifact_kind="worldguard_observed_world_comparison_receipt", label=f"revalidation {check.check_id}")
        except ValueError as exc:
            comparison_receipt = {}
            issues.append(str(exc))
        if mesh_report is None or candidate_mesh is None:
            issues.append("semantic_rollout_not_run")
        else:
            if mesh_report.semantic_status.value != "PASS":
                issues.append("semantic_rollout_non_pass")
            field = "scenario_ids" if check.role == RevalidationRole.ORIGINAL_SCENARIO else "holdout_scenario_ids"
            scopes_executed = bool(mesh_report.node_reports)
            for node_id in mesh_report.node_reports:
                scope = candidate_mesh.semantic_coverage.per_model_node.get(node_id, {})
                expected = set(scope.get(field, getattr(candidate_mesh.semantic_coverage, field)))
                observed = {
                    item
                    for receipt in mesh_report.semantic_receipts
                    if receipt.node_id == node_id
                    for item in receipt.outputs.get("executed_" + field, [])
                }
                if not expected or not expected <= observed:
                    scopes_executed = False
            if not scopes_executed:
                issues.append("semantic_role_scope_not_executed")
        if comparison_receipt.get("status") != "pass" or comparison_receipt.get("input_gap_ids"):
            issues.append("empirical_comparison_non_pass")
        if comparison_receipt.get("task_id") != task_id or comparison_receipt.get("coverage_universe_fingerprint") != coverage_fingerprint:
            issues.append("empirical_task_or_coverage_mismatch")
        if not _comparison_binds_model(comparison_receipt, revision.candidate_model):
            issues.append("empirical_comparison_candidate_identity_mismatch")
        check_results.append(
            {
                "check_id": check.check_id,
                "role": check.role.value,
                "semantic_status": mesh_report.semantic_status.value if mesh_report is not None else "NOT_RUN",
                "observation_id": comparison_receipt.get("observation_id", ""),
                "observation_source_ref": comparison_receipt.get("source_ref", ""),
                "observation_evidence_fingerprint": comparison_receipt.get("observation_evidence_fingerprint", ""),
                "observation_content_fingerprint": comparison_receipt.get("observation_content_fingerprint", ""),
                "effective_status": "pass" if not issues else "fail",
                "issues": issues,
            }
        )

    by_role = {item["role"]: item for item in check_results}
    original = by_role.get(RevalidationRole.ORIGINAL_SCENARIO.value, {})
    holdout = by_role.get(RevalidationRole.REAL_HOLDOUT_OBSERVATION.value, {})
    for key, code in (
        ("observation_id", "holdout_observation_identity_not_independent"),
        ("observation_source_ref", "holdout_source_not_independent"),
        ("observation_evidence_fingerprint", "holdout_evidence_not_independent"),
        ("observation_content_fingerprint", "holdout_content_alias_not_independent"),
    ):
        if original.get(key) and original.get(key) == holdout.get(key):
            holdout.setdefault("issues", []).append(code)
    if holdout.get("observation_evidence_fingerprint") in set(revision.candidate_build_evidence_fingerprints):
        holdout.setdefault("issues", []).append("holdout_used_for_candidate_construction")
    for item in check_results:
        item["issues"] = sorted(set(item["issues"]))
        item["effective_status"] = "pass" if not item["issues"] else "fail"
    failed = [item["check_id"] for item in check_results if item["effective_status"] != "pass"]

    depth = mesh_report.depth_receipt if mesh_report is not None else None
    raw_predictive_gaps = sorted(set(str(item) for item in (depth.predictive_gaps if depth is not None else [])))
    current_gap_ids = {f"native:{item}" for item in raw_predictive_gaps}
    predictive_licensed = bool(depth.predictive_claim_licensed) if depth is not None else False
    if not predictive_licensed and not raw_predictive_gaps:
        current_gap_ids.add("native:predictive_claim_not_licensed")
    prior_gap_ids = prediction_body.get("prior_gap_ids", [])
    input_gap_ids = (
        set(str(item) for item in prior_gap_ids if str(item))
        if iteration > 0 and isinstance(prior_gap_ids, list)
        else set(str(item) for item in comparison_body.get("input_gap_ids", []) if str(item))
    )
    resolved_gap_ids = sorted(input_gap_ids - current_gap_ids)
    persisted_gap_ids = sorted(input_gap_ids & current_gap_ids)
    introduced_gap_ids = sorted(current_gap_ids - input_gap_ids)
    current_gap_ids_sorted = sorted(current_gap_ids)
    current_gap_fingerprint = _fingerprint(current_gap_ids_sorted)
    progressed = bool(resolved_gap_ids or introduced_gap_ids) and current_gap_fingerprint not in prior_gap_fingerprints

    external_findings, externally_blocked = _external_input_findings(revision.external_inputs, current_gap_ids)
    findings.extend(external_findings)
    exact_external_stop = bool(current_gap_ids) and not external_findings and externally_blocked == current_gap_ids
    rollback = None
    if findings:
        disposition = "blocked"
        terminal_reason = "blocked"
    elif failed:
        if not revision.candidate_applied:
            disposition = "rejected"
            terminal_reason = "candidate_rejected"
        else:
            assert revision.rollback_model is not None
            rollback = _identity_receipt(revision.rollback_model, base_dir)
            if rollback["status"] == "current" and _same_identity(revision.rollback_model, revision.base_model):
                disposition = "rolled_back"
                terminal_reason = "candidate_rolled_back"
            else:
                disposition = "blocked"
                terminal_reason = "blocked"
                findings.append("rollback_identity_does_not_match_current_base")
    elif current_gap_ids:
        disposition = "continue_iteration"
        if exact_external_stop:
            terminal_reason = "external_input_required"
        elif iteration + 1 >= max_iterations:
            terminal_reason = "iteration_limit"
        elif not progressed:
            terminal_reason = "progress_stalled"
        else:
            terminal_reason = "continue_iteration"
    else:
        disposition = "accepted"
        terminal_reason = "model_closed_for_task"
    if terminal_reason not in _CURRENT_TERMINALS:
        raise AssertionError("computed terminal reason is not current")
    status = "pass" if disposition == "accepted" else ("fail" if disposition in {"rejected", "rolled_back"} else "blocked")
    next_actions = (
        [f"obtain_external_input:{item.input_id}" for item in revision.external_inputs]
        if terminal_reason == "external_input_required"
        else (["revise_candidate_from_current_gaps"] if terminal_reason == "continue_iteration" else [])
    )
    payload = {
        "artifact_kind": "worldguard_task_model_revision_receipt",
        "receipt_version": "2.0",
        "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
        "owner_id": TASK_LOCAL_REVISION_OWNER_ID,
        "status": status,
        "revision_id": revision.revision_id,
        "prediction_id": revision.prediction_id,
        "task_id": task_id,
        "purpose": prediction_body.get("purpose", ""),
        "coverage_universe_fingerprint": coverage_fingerprint,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "predecessor_iteration_fingerprint": prediction_body.get("predecessor_iteration_fingerprint", ""),
        "revision_kind": revision.revision_kind.value,
        "disposition": disposition,
        "terminal_reason": terminal_reason,
        "base_model": base,
        "candidate_model": candidate,
        "rollback_model": rollback,
        "candidate_mesh_status": mesh_report.status.value if mesh_report is not None else "NOT_RUN",
        "predictive_claim_licensed": predictive_licensed,
        "native_predictive_gap_ids": raw_predictive_gaps,
        "predictive_gap_categories": _predictive_gap_categories(raw_predictive_gaps),
        "input_gap_ids": sorted(input_gap_ids),
        "resolved_gap_ids": resolved_gap_ids,
        "persisted_gap_ids": persisted_gap_ids,
        "introduced_gap_ids": introduced_gap_ids,
        "current_gap_ids": current_gap_ids_sorted,
        "current_gap_fingerprint": current_gap_fingerprint,
        "progressed": progressed,
        "candidate_build_evidence_fingerprints": list(revision.candidate_build_evidence_fingerprints),
        "required_revalidation_ids": list(revision.required_revalidation_ids),
        "revalidation_results": check_results,
        "failed_revalidation_ids": failed,
        "external_inputs": [item.to_dict() for item in revision.external_inputs],
        "next_actions": next_actions,
        "identity_findings": sorted(set(findings)),
        "base_model_preserved": base["status"] == "current",
        "revision_fingerprint": _fingerprint(revision.to_dict()),
        "claim_boundary": "This decision applies only to the exact task, coverage universe, base/candidate models, one fresh run of the candidate mesh, and the independent original/holdout observations. Only this owner may emit model_closed_for_task.",
    }
    return payload


__all__ = [
    "TASK_LOCAL_REVISION_OWNER_ID",
    "TASK_LOCAL_REVISION_SCHEMA_VERSION",
    "CandidateWorldModelRevision",
    "ExpectedWorldRelationship",
    "ExpectedWorldValue",
    "ExternalInputRequirement",
    "ObservedWorldRelationship",
    "ObservedWorldSnapshot",
    "PredictionSnapshot",
    "RevalidationCheck",
    "RevalidationRole",
    "WorldMismatchCategory",
    "WorldModelIdentity",
    "WorldRevisionKind",
    "compare_observed_world",
    "coverage_universe_fingerprint",
    "evaluate_candidate_world_revision",
    "freeze_prediction_snapshot",
    "observation_evidence_fingerprint",
    "observation_content_fingerprint",
]
