"""WorldGuard's bounded behavior-commitment authority through v0.5."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from flowguard import (
    BehaviorCommitmentLedger,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    ProofArtifactRef,
    behavior_path_binding_from_primary_path_report,
    load_behavior_commitment_ledger,
    review_primary_path_authority,
)


ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = Path(__file__).resolve().with_name("ledger.json")
VALIDATION_PATHS = {
    "input": Path(__file__).resolve().with_name("validation-input.json"),
    "template": Path(__file__).resolve().with_name("validation-template.json"),
    "fact": Path(__file__).resolve().with_name("validation-fact.json"),
}

INPUT_COMMITMENT_ID = "commitment:worldguard-current-input-authority"
INPUT_INTENT_ID = "intent:worldguard-current-input-authority"
INPUT_PATH_ID = "path:worldguard-current-input-authority"
TEMPLATE_COMMITMENT_ID = "commitment:worldguard-template-selection-authority"
TEMPLATE_INTENT_ID = "intent:worldguard-template-selection-authority"
TEMPLATE_PATH_ID = "path:worldguard-template-selection-authority"
FACT_COMMITMENT_ID = "commitment:worldguard-fact-revision-authority"
FACT_INTENT_ID = "intent:worldguard-fact-revision-authority"
FACT_PATH_ID = "path:worldguard-fact-revision-authority"

INPUT_SURFACES = (
    "surface:worldguard-current-contract-code",
    "surface:worldguard-current-contract-tests",
    "surface:worldguard-current-contract-model",
    "surface:worldguard-current-contract-openspec",
)
TEMPLATE_SURFACES = (
    "surface:worldguard-template-code",
    "surface:worldguard-template-tests",
    "surface:worldguard-template-model",
    "surface:worldguard-template-docs",
)
FACT_SURFACES = (
    "surface:worldguard-fact-revision-code",
    "surface:worldguard-fact-revision-tests",
    "surface:worldguard-fact-revision-model",
    "surface:worldguard-fact-revision-docs",
)

INPUT_EVIDENCE_FILES = (
    "worldguard/contracts.py",
    "worldguard/semantic.py",
    "worldguard/guard_model_contract.py",
    "tests/test_contracts.py",
    "tests/test_guard_model_contract.py",
    ".flowguard/semantic_rollout_model.py",
)
TEMPLATE_EVIDENCE_FILES = (
    "worldguard/template_packs.py",
    "tests/test_template_packs.py",
    ".flowguard/worldguard_template_pack_builder.py",
    ".flowguard/worldguard_template_pack_field_lifecycle.md",
    "skills/worldguard/SKILL.md",
)
FACT_EVIDENCE_FILES = (
    "worldguard/fact_revision.py",
    "skills/worldguard/runtime/worldguard/fact_revision.py",
    "tests/test_fact_revision.py",
    ".flowguard/fact_revision/model.py",
    ".flowguard/fact_revision/run_checks.py",
    "skills/worldguard/.skillguard/checks/check_fact_revision.py",
    "skills/worldguard/references/fact-revision.md",
    "skills/worldguard/SKILL.md",
)
SHARED_EVIDENCE_FILES = (
    ".flowguard/behavior_commitment_ledger/ledger.json",
    ".flowguard/behavior_commitment_ledger/model.py",
    ".flowguard/behavior_commitment_ledger/run_checks.py",
)
EVIDENCE_FILES_BY_SHARD = {
    "input": SHARED_EVIDENCE_FILES + INPUT_EVIDENCE_FILES,
    "template": SHARED_EVIDENCE_FILES + TEMPLATE_EVIDENCE_FILES,
    "fact": SHARED_EVIDENCE_FILES + FACT_EVIDENCE_FILES,
}


def current_fingerprints(shard_id: str) -> dict[str, str]:
    """Return exact content identities for one independently owned shard."""

    evidence_files = EVIDENCE_FILES_BY_SHARD.get(shard_id)
    if evidence_files is None:
        raise ValueError(f"unknown_behavior_validation_shard:{shard_id}")
    identities: dict[str, str] = {}
    for relative in evidence_files:
        content = ROOT.joinpath(relative).read_bytes().replace(b"\r\n", b"\n")
        identities[relative] = f"sha256:{sha256(content).hexdigest()}"
    return identities


def validation_receipt_hash(validation: dict[str, object]) -> str:
    """Hash semantic evidence only; timestamps and captured output are attempt data."""

    identity = {
        "artifact_type": validation.get("artifact_type"),
        "schema_version": validation.get("schema_version"),
        "shard_id": validation.get("shard_id"),
        "command": validation.get("command"),
        "status": validation.get("status"),
        "exit_code": validation.get("exit_code"),
        "artifact_fingerprints": validation.get("artifact_fingerprints"),
        "toolchain_identity": validation.get("toolchain_identity"),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"sha256:{sha256(payload).hexdigest()}"


def _load_validation(shard_id: str) -> dict[str, object]:
    path = VALIDATION_PATHS[shard_id]
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _proof(
    *,
    artifact_id: str,
    obligation_id: str,
    shard_id: str,
    validation: dict[str, object],
) -> ProofArtifactRef:
    recorded = validation.get("artifact_fingerprints")
    current = current_fingerprints(shard_id)
    fingerprints_match = isinstance(recorded, dict) and recorded == current
    receipt_current = (
        validation.get("shard_id") == shard_id
        and validation.get("receipt_hash") == validation_receipt_hash(validation)
    )
    passed = (
        validation.get("status") == "passed"
        and validation.get("exit_code") == 0
        and receipt_current
    )
    is_current = bool(passed and fingerprints_match)
    stale_reasons = () if is_current else ("validation_missing_failed_or_inputs_changed",)
    return ProofArtifactRef(
        artifact_id=artifact_id,
        producer_route=f"worldguard-behavior-commitment-ledger:{shard_id}",
        command=str(validation.get("command", "")),
        result_path=str(VALIDATION_PATHS[shard_id].relative_to(ROOT)).replace(
            "\\", "/"
        ),
        result_status="passed" if passed else "not_run",
        exit_code=validation.get("exit_code") if isinstance(validation.get("exit_code"), int) else None,
        started_at=str(validation.get("started_at", "")),
        finished_at=str(validation.get("finished_at", "")),
        artifact_fingerprints=current,
        covered_obligation_ids=(obligation_id,),
        assertion_scope="external_contract",
        current=is_current,
        route_evidence_current=is_current,
        stale_reasons=stale_reasons,
    )


def build_primary_path_reports() -> tuple[object, object]:
    """Build both singular no-fallback path reports from current test evidence."""

    input_validation = _load_validation("input")
    template_validation = _load_validation("template")
    fact_validation = _load_validation("fact")
    input_obligation = "obligation:worldguard-current-input-only"
    template_obligation = "obligation:worldguard-template-selection-one-path"
    fact_obligation = "obligation:worldguard-fact-revision-one-path"
    input_plan = PrimaryPathAuthorityPlan(
        plan_id="ppa:worldguard-current-input-authority",
        primary_paths=(
            PrimaryPathContract(
                business_path_id=INPUT_PATH_ID,
                business_intent="accept only the current WorldGuard input contract",
                business_intent_id=INPUT_INTENT_ID,
                behavior_commitment_id=INPUT_COMMITMENT_ID,
                primary_entrypoint_id="worldguard.contracts.load_contract",
                owner_model_id=".flowguard/current_input_authority/model.py",
                owner_code_contract_id="contract:worldguard-v0.4-input-authority",
                expected_terminal="verified current input or visible typed contract failure",
                failure_policy="fail_closed",
                allowed_error_state_ids=("CONTRACT_INVALID",),
                evidence_ids=("tests/test_contracts.py", "tests/test_guard_model_contract.py"),
                runtime_evidence_state="current_pass",
                runtime_observation_ids=("observation:worldguard-current-input-targeted-tests",),
                required_obligation_ids=(input_obligation,),
                proof_artifact=_proof(
                    artifact_id="proof:worldguard-current-input-authority",
                    obligation_id=input_obligation,
                    shard_id="input",
                    validation=input_validation,
                ),
                source_surface_ids=INPUT_SURFACES,
            ),
        ),
        fallback_candidates=(),
        claim_scope="routine",
        coverage_case_ids=("case:current-input-accepted", "case:retired-input-rejected"),
        coverage_shard_ids=("shard:worldguard-current-input-authority",),
        coverage_receipt_ids=("receipt:worldguard-current-input-authority",),
        risk_gate_ids=("risk_gate:worldguard-current-input-authority",),
        expected_business_intents=("accept only the current WorldGuard input contract",),
        expected_business_intent_ids=(INPUT_INTENT_ID,),
        expected_candidate_ids=(),
        expected_surface_ids=INPUT_SURFACES,
        inventory_revision="worldguard-v0.4.0-current-only-contract",
        inventory_evidence_ids=("ledger:worldguard-v0.4-current-authority",),
        preflight_id="worldguard-v0.4-existing-model-preflight",
        behavior_commitment_ledger_id="worldguard-v0.4-current-authority",
        existing_current_path_ids=(INPUT_PATH_ID,),
        require_complete_candidate_inventory=True,
        require_material_runtime_evidence=True,
    )
    template_plan = PrimaryPathAuthorityPlan(
        plan_id="ppa:worldguard-template-selection-authority",
        primary_paths=(
            PrimaryPathContract(
                business_path_id=TEMPLATE_PATH_ID,
                business_intent="select exactly one applicable WorldGuard template or block",
                business_intent_id=TEMPLATE_INTENT_ID,
                behavior_commitment_id=TEMPLATE_COMMITMENT_ID,
                primary_entrypoint_id="worldguard.template_packs.select_template_pack",
                owner_model_id=".flowguard/template_selection/model.py",
                owner_code_contract_id="contract:worldguard-template-selection",
                expected_terminal="one selected template or visible typed no-match/ambiguity failure",
                failure_policy="fail_closed",
                allowed_error_state_ids=(
                    "TEMPLATE_SELECTION_NO_MATCH",
                    "TEMPLATE_SELECTION_AMBIGUOUS",
                ),
                evidence_ids=("tests/test_template_packs.py",),
                runtime_evidence_state="current_pass",
                runtime_observation_ids=("observation:worldguard-template-targeted-tests",),
                required_obligation_ids=(template_obligation,),
                proof_artifact=_proof(
                    artifact_id="proof:worldguard-template-selection-authority",
                    obligation_id=template_obligation,
                    shard_id="template",
                    validation=template_validation,
                ),
                source_surface_ids=TEMPLATE_SURFACES,
            ),
        ),
        fallback_candidates=(),
        claim_scope="routine",
        coverage_case_ids=(
            "case:template-zero-blocks",
            "case:template-one-selects",
            "case:template-many-blocks",
        ),
        coverage_shard_ids=("shard:worldguard-template-selection-authority",),
        coverage_receipt_ids=("receipt:worldguard-template-selection-authority",),
        risk_gate_ids=("risk_gate:worldguard-template-selection-authority",),
        expected_business_intents=("select exactly one applicable WorldGuard template or block",),
        expected_business_intent_ids=(TEMPLATE_INTENT_ID,),
        expected_candidate_ids=(),
        expected_surface_ids=TEMPLATE_SURFACES,
        inventory_revision="worldguard-v0.4.0-template-current-only",
        inventory_evidence_ids=("ledger:worldguard-v0.4-current-authority",),
        preflight_id="worldguard-v0.4-existing-model-preflight",
        behavior_commitment_ledger_id="worldguard-v0.4-current-authority",
        existing_current_path_ids=(TEMPLATE_PATH_ID,),
        require_complete_candidate_inventory=True,
        require_material_runtime_evidence=True,
    )
    fact_plan = PrimaryPathAuthorityPlan(
        plan_id="ppa:worldguard-fact-revision-authority",
        primary_paths=(
            PrimaryPathContract(
                business_path_id=FACT_PATH_ID,
                business_intent="preview and activate one task-local fact revision transaction",
                business_intent_id=FACT_INTENT_ID,
                behavior_commitment_id=FACT_COMMITMENT_ID,
                primary_entrypoint_id="worldguard.fact_revision.preview_fact_revision",
                owner_model_id=".flowguard/fact_revision/model.py",
                owner_code_contract_id="contract:worldguard-fact-revision",
                expected_terminal="one immutable preview followed by evidence-bound activation or one visible typed block",
                failure_policy="fail_closed",
                allowed_error_state_ids=(
                    "stale_base",
                    "preservation_changed",
                    "unacknowledged_contradiction",
                    "evidence_not_current",
                ),
                evidence_ids=("tests/test_fact_revision.py",),
                runtime_evidence_state="current_pass",
                runtime_observation_ids=(
                    "observation:worldguard-fact-revision-targeted-tests",
                ),
                required_obligation_ids=(fact_obligation,),
                proof_artifact=_proof(
                    artifact_id="proof:worldguard-fact-revision-authority",
                    obligation_id=fact_obligation,
                    shard_id="fact",
                    validation=fact_validation,
                ),
                source_surface_ids=FACT_SURFACES,
            ),
        ),
        fallback_candidates=(),
        claim_scope="routine",
        coverage_case_ids=(
            "case:fact-revision-current-activates",
            "case:fact-revision-contradiction-visible",
            "case:fact-revision-stale-blocks",
            "case:fact-revision-evidence-blocks",
        ),
        coverage_shard_ids=("shard:worldguard-fact-revision-authority",),
        coverage_receipt_ids=("receipt:worldguard-fact-revision-authority",),
        risk_gate_ids=("risk_gate:worldguard-fact-revision-authority",),
        expected_business_intents=(
            "preview and activate one task-local fact revision transaction",
        ),
        expected_business_intent_ids=(FACT_INTENT_ID,),
        expected_candidate_ids=(),
        expected_surface_ids=FACT_SURFACES,
        inventory_revision="worldguard-v0.5.0-fact-revision-current-only",
        inventory_evidence_ids=("ledger:worldguard-v0.5-current-authority",),
        preflight_id="worldguard-v0.5-existing-model-preflight",
        behavior_commitment_ledger_id="worldguard-v0.5-current-authority",
        existing_current_path_ids=(FACT_PATH_ID,),
        require_complete_candidate_inventory=True,
        require_material_runtime_evidence=True,
    )
    return (
        review_primary_path_authority(input_plan),
        review_primary_path_authority(template_plan),
        review_primary_path_authority(fact_plan),
    )


def build_worldguard_behavior_commitment_ledger() -> BehaviorCommitmentLedger:
    """Load the canonical inventory and attach only current PPA evidence."""

    ledger = load_behavior_commitment_ledger(LEDGER_PATH)
    input_report, template_report, fact_report = build_primary_path_reports()
    reports = {
        INPUT_COMMITMENT_ID: input_report,
        TEMPLATE_COMMITMENT_ID: template_report,
        FACT_COMMITMENT_ID: fact_report,
    }
    commitments = tuple(
        replace(
            commitment,
            path_authority=behavior_path_binding_from_primary_path_report(
                reports[commitment.commitment_id],
                business_intent_id=commitment.business_intent_id,
                behavior_commitment_id=commitment.commitment_id,
                ppa_report_id=f"report:{reports[commitment.commitment_id].plan_id}",
                evidence_refs=(
                    str(
                        VALIDATION_PATHS[
                            "input"
                            if commitment.commitment_id == INPUT_COMMITMENT_ID
                            else (
                                "template"
                                if commitment.commitment_id == TEMPLATE_COMMITMENT_ID
                                else "fact"
                            )
                        ]
                    ),
                ),
            ),
        )
        for commitment in ledger.commitments
    )
    return replace(ledger, commitments=commitments)


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


__all__ = [
    "LEDGER_PATH",
    "EVIDENCE_FILES_BY_SHARD",
    "FACT_EVIDENCE_FILES",
    "INPUT_EVIDENCE_FILES",
    "SHARED_EVIDENCE_FILES",
    "TEMPLATE_EVIDENCE_FILES",
    "VALIDATION_PATHS",
    "build_primary_path_reports",
    "build_worldguard_behavior_commitment_ledger",
    "current_fingerprints",
    "validation_receipt_hash",
]
