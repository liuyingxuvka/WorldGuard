#!/usr/bin/env python3
"""Compose and validate one WorldGuard selected prompt bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from worldguard.contracts import (
    Claim,
    claim_predictive_intent,
    derive_guard_requirements,
)


BLUEPRINT_OPERATIONS = {
    "create",
    "update",
    "check",
    "impact",
    "trace",
}
BLUEPRINT_IDENTITY_OPERATIONS = {
    "update",
    "check",
    "impact",
    "trace",
}
CLAIM_REQUIRED_SHAPES = {"unit_contract", "model_mesh", "task_local_revision"}
RETIRED_PROMPT_FACT_FIELDS = {
    "task_shape_candidates",
    "task_shape_facts",
    "requested_semantics",
    "predictive_intent",
    "target_guards",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def compose_prompt_bundle(
    skill_root: Path,
    facts: dict[str, Any],
    *,
    topology_path: Path | None = None,
) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    topology_path = topology_path or skill_root / "references" / "internal-guard-routes.json"
    topology = _load_json(topology_path)
    findings: list[dict[str, Any]] = []

    retired_fields = sorted(RETIRED_PROMPT_FACT_FIELDS.intersection(facts))
    if retired_fields:
        findings.append(
            {"code": "prompt_fact_fields_retired", "fields": retired_fields}
        )

    shape_value = facts.get("task_shape")
    selected_shape = shape_value.strip() if isinstance(shape_value, str) else ""
    if not selected_shape:
        findings.append({"code": "task_shape_invalid", "field": "task_shape"})
    shape_rows = {
        row["shape_id"]: row
        for row in topology.get("task_shapes", [])
        if isinstance(row, dict) and isinstance(row.get("shape_id"), str)
    }
    if selected_shape and selected_shape not in shape_rows:
        findings.append(
            {"code": "task_shape_unsupported", "task_shape": selected_shape}
        )

    claim: Claim | None = None
    claim_value = facts.get("claim")
    if claim_value is not None:
        if not isinstance(claim_value, dict):
            findings.append({"code": "claim_invalid", "reason": "claim_not_object"})
        else:
            try:
                claim = Claim.from_dict(claim_value)
            except (TypeError, ValueError) as error:
                findings.append({"code": "claim_invalid", "reason": str(error)})
    elif selected_shape in CLAIM_REQUIRED_SHAPES:
        findings.append({"code": "claim_missing", "task_shape": selected_shape})

    guard_derivation = derive_guard_requirements(claim) if claim is not None else None
    semantics = (
        guard_derivation.requested_semantics if guard_derivation is not None else ()
    )
    derived_guards = guard_derivation.guard_ids if guard_derivation is not None else ()
    unmapped = (
        list(guard_derivation.unmapped_semantics)
        if guard_derivation is not None
        else []
    )

    routes = [row for row in topology.get("routes", []) if isinstance(row, dict)]
    if unmapped and selected_shape not in {"template_pack", "world_blueprint"}:
        findings.append({"code": "claim_semantics_unmapped", "semantics": unmapped})
    if selected_shape in {"unit_contract", "model_mesh", "task_local_revision"} and not derived_guards:
        findings.append({"code": "derived_guard_set_empty"})

    affected_guard_value = facts.get("affected_guard_ids", [])
    if isinstance(affected_guard_value, str):
        affected_guard_value = [affected_guard_value]
    if not isinstance(affected_guard_value, list) or any(
        not isinstance(item, str) for item in affected_guard_value
    ):
        affected_guard_value = []
        findings.append({"code": "affected_guard_ids_invalid"})
    affected_guards = tuple(
        dict.fromkeys(item.strip() for item in affected_guard_value if item.strip())
    )
    known_guard_ids = {str(row.get("guard_id", "")) for row in routes}
    unknown_affected = sorted(set(affected_guards).difference(known_guard_ids))
    if selected_shape == "world_blueprint":
        operation = str(facts.get("blueprint_operation", "")).strip()
        if operation not in BLUEPRINT_OPERATIONS:
            findings.append(
                {
                    "code": "blueprint_operation_not_exact",
                    "operation": operation,
                    "allowed": sorted(BLUEPRINT_OPERATIONS),
                }
            )
        spans = facts.get("request_source_spans")
        spans_valid = isinstance(spans, list) and bool(spans)
        if spans_valid:
            for span in spans:
                if not isinstance(span, dict):
                    spans_valid = False
                    break
                start = span.get("start")
                end = span.get("end")
                if (
                    not isinstance(span.get("source_id"), str)
                    or not span["source_id"].strip()
                    or not isinstance(span.get("text"), str)
                    or not span["text"].strip()
                    or not isinstance(start, int)
                    or isinstance(start, bool)
                    or not isinstance(end, int)
                    or isinstance(end, bool)
                    or start < 0
                    or end <= start
                ):
                    spans_valid = False
                    break
        if not spans_valid:
            findings.append(
                {
                    "code": "blueprint_required_input_missing",
                    "fields": ["request_source_spans"],
                }
            )
        target_identity_required = True
        common_missing = (
            [
                field_name
                for field_name in (
                    "target_id",
                    "target_revision",
                    "declared_boundary",
                )
                if not isinstance(facts.get(field_name), str)
                or not str(facts.get(field_name, "")).strip()
            ]
            if target_identity_required
            else []
        )
        if common_missing:
            findings.append(
                {
                    "code": "blueprint_required_input_missing",
                    "fields": common_missing,
                }
            )
        if "affected_guard_ids" not in facts:
            findings.append(
                {
                    "code": "blueprint_required_input_missing",
                    "fields": ["affected_guard_ids"],
                }
            )
        operation_missing: list[str] = []
        blueprint_identity = facts.get("world_blueprint_or_query_identity")
        if operation in BLUEPRINT_IDENTITY_OPERATIONS and (
            not isinstance(blueprint_identity, str) or not blueprint_identity.strip()
        ):
            operation_missing.append("world_blueprint_or_query_identity")
        if operation == "create":
            refs = facts.get("target_material_refs")
            if (
                not isinstance(refs, list)
                or not refs
                or any(not isinstance(item, str) or not item.strip() for item in refs)
            ):
                operation_missing.append("target_material_refs")
        elif operation == "update":
            if not isinstance(facts.get("change_intent"), str) or not str(
                facts.get("change_intent", "")
            ).strip():
                operation_missing.append("change_intent")
            changed_ids = facts.get("changed_ids")
            if (
                not isinstance(changed_ids, list)
                or not changed_ids
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in changed_ids
                )
            ):
                operation_missing.append("changed_ids")
        elif operation == "impact":
            changed_ids = facts.get("changed_ids")
            if (
                not isinstance(changed_ids, list)
                or not changed_ids
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in changed_ids
                )
            ):
                operation_missing.append("changed_ids")
        elif operation == "trace":
            if not isinstance(facts.get("trace_target_id"), str) or not str(
                facts.get("trace_target_id", "")
            ).strip():
                operation_missing.append("trace_target_id")
        if operation_missing:
            findings.append(
                {
                    "code": "blueprint_operation_input_missing",
                    "operation": operation,
                    "fields": sorted(set(operation_missing)),
                }
            )
        if unknown_affected:
            findings.append(
                {
                    "code": "blueprint_affected_guard_unknown",
                    "guard_ids": unknown_affected,
                }
            )
        selected_guards = affected_guards
    else:
        operation = ""
        if affected_guards:
            findings.append(
                {
                    "code": "blueprint_affected_guards_outside_blueprint_route",
                    "guard_ids": list(affected_guards),
                }
            )
        selected_guards = derived_guards

    caller_guards = set(claim.target_guards) if claim is not None else set()
    omitted = (
        sorted(set(derived_guards) - caller_guards)
        if caller_guards and selected_shape != "world_blueprint"
        else []
    )

    bundle_paths: list[str] = ["SKILL.md", "references/entry-routing.md"]
    if selected_shape in shape_rows:
        bundle_paths.append(str(shape_rows[selected_shape].get("reference_path", "")))
    rows_by_guard = {str(row.get("guard_id", "")): row for row in routes}
    for guard in selected_guards:
        row = rows_by_guard.get(guard, {})
        bundle_paths.append(str(row.get("reference_path", "")))

    predictive = claim_predictive_intent(claim) if claim is not None else False
    if selected_shape == "task_local_revision" or predictive:
        bundle_paths.append("references/task-local-model-deepening.md")
    if selected_shape == "model_mesh" and facts.get("handoff_present"):
        bundle_paths.append("references/handoff-contracts.md")
    if facts.get("fact_revision_requested"):
        bundle_paths.append("references/fact-revision.md")
    if facts.get("model_authority_requested"):
        bundle_paths.append("references/model-authority.md")
    if facts.get("final_reporting_requested"):
        bundle_paths.append("references/closure-report.md")
    bundle_paths = list(dict.fromkeys(path for path in bundle_paths if path))

    bundle_components: list[dict[str, Any]] = []
    for relative in bundle_paths:
        path = skill_root / relative
        if not path.is_file():
            findings.append({"code": "mandatory_prompt_reference_missing", "path": relative})
            continue
        bundle_components.append({"path": relative, "bytes": len(path.read_bytes())})
    route_capsules = [
        {
            "guard_id": guard,
            "bytes": len(
                json.dumps(
                    rows_by_guard[guard],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        }
        for guard in selected_guards
        if guard in rows_by_guard
    ]
    bundle_bytes = sum(item["bytes"] for item in bundle_components) + sum(
        item["bytes"] for item in route_capsules
    )
    budget = topology.get("prompt_budget", {})
    entry_max = budget.get("entry_shell_max_bytes")
    route_max = budget.get("single_route_capsule_max_bytes")
    blueprint_reference_max = budget.get("single_blueprint_reference_max_bytes")
    blueprint_reference_minimum_headroom = budget.get(
        "single_blueprint_reference_minimum_headroom_bytes"
    )
    selected_max = budget.get("selected_operation_bundle_max_bytes")
    headroom = budget.get("minimum_reasoning_headroom_bytes")
    entry_bytes = next(
        (item["bytes"] for item in bundle_components if item["path"] == "SKILL.md"),
        0,
    )
    if not isinstance(entry_max, int) or entry_bytes > entry_max:
        findings.append(
            {
                "code": "entry_prompt_budget_exceeded",
                "observed": entry_bytes,
                "maximum": entry_max,
            }
        )
    if not isinstance(route_max, int) or route_max <= 0:
        findings.append(
            {
                "code": "route_capsule_budget_invalid",
                "observed": route_max,
            }
        )
    else:
        for capsule in route_capsules:
            if capsule["bytes"] > route_max:
                findings.append(
                    {
                        "code": "route_capsule_budget_exceeded",
                        "guard_id": capsule["guard_id"],
                        "observed": capsule["bytes"],
                        "maximum": route_max,
                    }
                )
    blueprint_bytes = 0
    blueprint_reference_headroom: int | None = None
    if selected_shape == "world_blueprint":
        blueprint_bytes = next(
            (
                item["bytes"]
                for item in bundle_components
                if item["path"] == "references/world-blueprint.md"
            ),
            0,
        )
        if (
            not isinstance(blueprint_reference_max, int)
            or blueprint_bytes > blueprint_reference_max
        ):
            findings.append(
                {
                    "code": "blueprint_reference_budget_exceeded",
                    "observed": blueprint_bytes,
                    "maximum": blueprint_reference_max,
                }
            )
        if (
            not isinstance(blueprint_reference_minimum_headroom, int)
            or blueprint_reference_minimum_headroom < 0
        ):
            findings.append(
                {
                    "code": "blueprint_reference_headroom_budget_invalid",
                    "observed": blueprint_reference_minimum_headroom,
                }
            )
        elif isinstance(blueprint_reference_max, int):
            blueprint_reference_headroom = blueprint_reference_max - blueprint_bytes
            if blueprint_reference_headroom < blueprint_reference_minimum_headroom:
                findings.append(
                    {
                        "code": "blueprint_reference_headroom_too_small",
                        "observed": blueprint_reference_headroom,
                        "minimum": blueprint_reference_minimum_headroom,
                        "reference_bytes": blueprint_bytes,
                        "maximum": blueprint_reference_max,
                    }
                )
    if not isinstance(selected_max, int) or bundle_bytes > selected_max:
        findings.append(
            {
                "code": "selected_prompt_bundle_budget_exceeded",
                "observed": bundle_bytes,
                "maximum": selected_max,
            }
        )
    if not isinstance(headroom, int) or headroom < 12000:
        findings.append(
            {
                "code": "prompt_reasoning_headroom_too_small",
                "observed": headroom,
                "minimum": 12000,
            }
        )

    operation_claim_boundaries = {}
    return {
        "schema_version": "worldguard.prompt_bundle_check.v1",
        "status": "pass" if not findings else "blocked",
        "ok": not findings,
        "selected_task_shape": selected_shape,
        "blueprint_operation": operation,
        "blueprint_operation_claim_boundary": operation_claim_boundaries.get(
            operation,
            (
                "The selected blueprint operation remains bounded to its declared target, "
                "revision, evidence, and native result."
                if operation
                else ""
            ),
        ),
        "requested_semantics": list(semantics),
        "derived_guard_ids": list(derived_guards),
        "guard_derivation_fingerprint": (
            guard_derivation.fingerprint if guard_derivation is not None else ""
        ),
        "affected_guard_ids": list(affected_guards),
        "selected_guard_ids": list(selected_guards),
        "caller_target_guard_omissions": omitted,
        "bundle_paths": bundle_paths,
        "bundle_components": bundle_components,
        "route_capsules": route_capsules,
        "bundle_bytes": bundle_bytes,
        "blueprint_reference_bytes": blueprint_bytes,
        "blueprint_reference_headroom_bytes": blueprint_reference_headroom,
        "reasoning_headroom_bytes": headroom,
        "findings": findings,
        "claim_boundary": (
            "This check proves only deterministic task-shape, complete claim-derived Guard, "
            "reference-load, and prompt-budget projection. It does not execute Guard semantics "
            "or prove factual truth, installation, Git, tag, or release."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", default="skills/worldguard")
    parser.add_argument("--facts", required=True)
    parser.add_argument("--topology")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = compose_prompt_bundle(
        Path(args.skill_root),
        _load_json(Path(args.facts)),
        topology_path=Path(args.topology) if args.topology else None,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={report['status']} findings={len(report['findings'])}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
