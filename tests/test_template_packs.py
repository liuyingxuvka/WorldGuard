from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
from worldguard import (GuardContract, ModelMeshContract, QualificationContext, SemanticStatus, run_worldguard)
from worldguard.status import GuardStatus
from worldguard.guard_model_contract import PROTECTED_FAILURE_CLASSES
from worldguard.template_packs import (GUARD_CONTRACT_KIND, MODEL_MESH_CONTRACT_KIND, VALIDATOR_GUARD_SHAPE, TemplateFragment, TemplatePackError, TemplatePackManifest, TemplatePackRegistry, build_template_instance, builtin_template_registry, compose_template_packs, template_slot)
ROOT = Path(__file__).resolve().parents[1]

def _event_bindings() -> dict[str, object]:
    task_contract_id = 'template:event-contract'
    run_id = 'template:event-run'
    model_id = 'template:event-model'
    return {'contract_id': task_contract_id, 'run_id': run_id, 'claim_id': 'claim:event-template', 'claim_text': 'a declared event initiates readiness', 'target_guards': ['EventGuard'], 'requested_semantics': ['event'], 'claim_atoms': [{'atom_id': 'atom:event', 'text': 'the event initiates readiness', 'requested_semantics': ['event'], 'predictive_intent': False}], 'claim_asserts': [{'holds': 'ready', 'at': 't0'}], 'model_id': model_id, 'model_version': 'v1', 'event_inputs': [{'event_id': 'event:ready', 'at': 't0', 'initiates': 'ready'}]}

def _base_guard_bindings() -> dict[str, object]:
    return {'contract_id': 'template:base-contract', 'run_id': 'template:base-run', 'claim_id': 'claim:base', 'claim_text': 'unrouted bounded input', 'target_guards': [], 'requested_semantics': [], 'claim_atoms': [], 'claim_asserts': [], 'model_id': 'template:base-model', 'model_version': 'v1'}

def test_builtin_guard_pack_selects_and_validates_deterministically() -> None:
    registry = builtin_template_registry()
    first = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=_event_bindings())
    second = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=_event_bindings())
    assert first.receipt.selection.outcome == 'selected'
    assert first.receipt.selection.selected_pack_id == 'worldguard.guard-contract.event'
    assert first.data['inputs']['events'][0]['event_id'] == 'event:ready'
    assert GuardContract.from_dict(first.data).contract_id == 'template:event-contract'
    assert len(first.receipt.validator_receipts) == 2
    assert first.receipt.pack_ids == ('worldguard.guard-contract.base', 'worldguard.guard-contract.event')
    assert first.to_dict() == second.to_dict()

def test_no_candidate_blocks_instead_of_activating_the_shared_scaffold() -> None:
    registry = builtin_template_registry()
    selection = registry.select(GUARD_CONTRACT_KIND, ['unmatched:fact'])
    assert selection.outcome == 'no_match'
    assert selection.candidate_pack_ids == ()
    with pytest.raises(TemplatePackError) as caught:
        build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['unmatched:fact'], slot_bindings=_base_guard_bindings())
    assert caught.value.code == 'TEMPLATE_SELECTION_NO_MATCH'

def test_many_matching_candidates_are_visible_and_never_ranked() -> None:
    registry = builtin_template_registry()
    selection = registry.select(GUARD_CONTRACT_KIND, ['guard:EventGuard', 'guard:CausalGuard'])
    assert selection.outcome == 'ambiguous'
    assert selection.candidate_pack_ids == ('worldguard.guard-contract.causal', 'worldguard.guard-contract.event')
    with pytest.raises(TemplatePackError) as caught:
        build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard', 'guard:CausalGuard'], slot_bindings=_event_bindings())
    assert caught.value.code == 'TEMPLATE_SELECTION_AMBIGUOUS'
    assert caught.value.details['candidate_pack_ids'] == list(selection.candidate_pack_ids)

def test_no_match_without_base_is_a_typed_blocker() -> None:
    candidate = TemplatePackManifest.build(pack_id='test.guard.candidate', pack_version='1', contract_kind=GUARD_CONTRACT_KIND, is_base=False, required_fact_ids=('candidate:yes',), fragments=(TemplateFragment.build('fragment:candidate', {'inputs': {'events': []}}),), native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary='test-only construction boundary')
    registry = TemplatePackRegistry.build((candidate,))
    assert registry.select(GUARD_CONTRACT_KIND, ()).outcome == 'no_match'
    with pytest.raises(TemplatePackError) as caught:
        build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, slot_bindings={})
    assert caught.value.code == 'TEMPLATE_SELECTION_NO_MATCH'

def test_one_matching_candidate_without_base_is_a_typed_blocker() -> None:
    candidate = TemplatePackManifest.build(pack_id='test.guard.candidate', pack_version='1', contract_kind=GUARD_CONTRACT_KIND, is_base=False, required_fact_ids=('candidate:yes',), fragments=(TemplateFragment.build('fragment:candidate', {'inputs': {'events': []}}),), native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary='test-only construction boundary')
    registry = TemplatePackRegistry.build((candidate,))
    assert registry.select(GUARD_CONTRACT_KIND, ('candidate:yes',)).outcome == 'selected'
    with pytest.raises(TemplatePackError) as caught:
        build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=('candidate:yes',), slot_bindings={})
    assert caught.value.code == 'TEMPLATE_SELECTED_BASE_MISSING'

def test_two_base_templates_are_rejected_before_selection() -> None:
    current = builtin_template_registry().by_id('worldguard.guard-contract.base')
    second = replace(current, pack_id='worldguard.guard-contract.second-base')
    with pytest.raises(TemplatePackError) as caught:
        TemplatePackRegistry.build((current, second))
    assert caught.value.code == 'TEMPLATE_BASE_AMBIGUOUS'

def test_template_construction_never_substitutes_for_semantic_provider_or_depth() -> None:
    instance = build_template_instance(builtin_template_registry(), contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=_event_bindings())
    assert instance.data['claim']['asserts'] == [{'holds': 'ready', 'at': 't0'}]
    assert run_worldguard(instance.data).status == GuardStatus.PASS
    provider_missing = run_worldguard(instance.data, context=QualificationContext(provider_availability={'EventGuard': False}))
    assert provider_missing.structural_status == GuardStatus.PASS
    assert provider_missing.semantic_status == SemanticStatus.NOT_RUN
    assert provider_missing.status == GuardStatus.GAP
    depth_not_run = run_worldguard(instance.data, context=QualificationContext(rollout_inputs={'status': 'NOT_RUN'}))
    assert depth_not_run.structural_status == GuardStatus.PASS
    assert depth_not_run.semantic_status == SemanticStatus.PASS
    assert depth_not_run.rollout_status == SemanticStatus.NOT_RUN
    assert depth_not_run.status == GuardStatus.GAP

def test_composition_rejects_overlapping_field_owners() -> None:
    base = TemplatePackManifest.build(pack_id='test.guard.base', pack_version='1', contract_kind=GUARD_CONTRACT_KIND, is_base=True, fragments=(TemplateFragment.build('fragment:base', {'contract_id': template_slot('contract_id')}),), native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary='test base')
    candidate = TemplatePackManifest.build(pack_id='test.guard.overlap', pack_version='1', contract_kind=GUARD_CONTRACT_KIND, is_base=False, required_fact_ids=('overlap',), fragments=(TemplateFragment.build('fragment:overlap', {'contract_id': 'wrong'}),), native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary='test candidate')
    with pytest.raises(TemplatePackError) as caught:
        compose_template_packs((base, candidate))
    assert caught.value.code == 'TEMPLATE_FIELD_OWNERSHIP_CONFLICT'
    assert caught.value.details['field_id'] == 'contract_id'

def test_fragment_rejects_undeclared_or_phantom_owned_fields() -> None:
    fragment = TemplateFragment.from_dict({'fragment_id': 'fragment:mismatch', 'owned_field_ids': ['claim.text'], 'payload': {'claim': {'claim_id': 'claim:one'}}})
    with pytest.raises(TemplatePackError) as caught:
        fragment.validate()
    assert caught.value.code == 'TEMPLATE_FRAGMENT_FIELD_OWNERSHIP_MISMATCH'

def test_missing_and_unused_slot_bindings_fail_closed() -> None:
    missing = _event_bindings()
    missing.pop('model_id')
    with pytest.raises(TemplatePackError) as caught:
        build_template_instance(builtin_template_registry(), contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=missing)
    assert caught.value.code == 'TEMPLATE_SLOT_MISSING'
    assert caught.value.details['slot_id'] == 'model_id'
    extra = _event_bindings()
    extra['undeclared_extra'] = True
    with pytest.raises(TemplatePackError) as caught:
        build_template_instance(builtin_template_registry(), contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=extra)
    assert caught.value.code == 'TEMPLATE_BINDING_UNUSED'
    assert caught.value.details['unused_slot_ids'] == ['undeclared_extra']

def test_unknown_native_validator_blocks_registry_admission() -> None:
    current = builtin_template_registry().by_id('worldguard.guard-contract.base')
    unknown = replace(current, native_validator_ids=('worldguard.unknown.v1',))
    with pytest.raises(TemplatePackError) as caught:
        TemplatePackRegistry.build((unknown,))
    assert caught.value.code == 'TEMPLATE_NATIVE_VALIDATOR_UNKNOWN'

def test_model_mesh_pack_builds_canonical_bounded_scaffold() -> None:
    instance = build_template_instance(builtin_template_registry(), contract_kind=MODEL_MESH_CONTRACT_KIND, fact_ids=['coverage:bounded'], slot_bindings={'mesh_id': 'mesh:template', 'run_id': 'mesh:template-run', 'nodes': [], 'expected_model_node_ids': []})
    mesh = ModelMeshContract.from_dict(instance.data)
    assert mesh.mesh_id == 'mesh:template'
    assert mesh.semantic_coverage.profile == 'bounded'
    assert instance.receipt.selection.selected_pack_id == 'worldguard.model-mesh.bounded'
    assert len(instance.receipt.validator_receipts) == 2

def test_binding_change_changes_the_built_contract() -> None:
    registry = builtin_template_registry()
    first_bindings = _event_bindings()
    second_bindings = _event_bindings()
    second_bindings['claim_text'] = 'a different task-local event claim'
    first = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=first_bindings)
    second = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=second_bindings)
    assert first.data['claim']['text'] == 'a declared event initiates readiness'
    assert second.data['claim']['text'] == 'a different task-local event claim'
    assert first.receipt.to_dict() == second.receipt.to_dict()
