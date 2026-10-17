from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
from worldguard import GuardContract, ModelMeshContract, QualificationContext, SemanticStatus, run_worldguard
from worldguard.status import GuardStatus
from worldguard.guard_model_contract import PROTECTED_FAILURE_CLASSES
from worldguard.template_packs import GUARD_CONTRACT_KIND, MODEL_MESH_CONTRACT_KIND, TARGET_APPLICABILITY_RESULT_FIELDS, TARGET_TEMPLATE_INTERCHANGE_FIELDS, TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION, TARGET_TEMPLATE_CATALOG_FIELDS, TARGET_TEMPLATE_MANIFEST_FIELDS, VALIDATOR_GUARD_SHAPE, WORLDGUARD_TEMPLATE_ROUTE_ID, TemplateFragment, TemplatePackError, TemplatePackManifest, TemplatePackRegistry, build_template_instance, build_target_template_interchange, builtin_template_registry, compose_template_packs, template_slot, validate_target_template_interchange
ROOT = Path(__file__).resolve().parents[1]

def _event_bindings() -> dict[str, object]:
    task_contract_id = 'template:event-contract'
    run_id = 'template:event-run'
    model_id = 'template:event-model'
    return {'contract_id': task_contract_id, 'run_id': run_id, 'claim_id': 'claim:event-template', 'claim_text': 'a declared event initiates readiness', 'target_guards': ['EventGuard'], 'requested_semantics': ['event'], 'claim_atoms': [{'atom_id': 'atom:event', 'text': 'the event initiates readiness', 'requested_semantics': ['event'], 'predictive_intent': False}], 'model_id': model_id, 'model_version': 'v1', 'event_inputs': [{'event_id': 'event:ready', 'at': 't0', 'initiates': 'ready'}]}

def _base_guard_bindings() -> dict[str, object]:
    return {'contract_id': 'template:base-contract', 'run_id': 'template:base-run', 'claim_id': 'claim:base', 'claim_text': 'unrouted bounded input', 'target_guards': [], 'requested_semantics': [], 'claim_atoms': [], 'model_id': 'template:base-model', 'model_version': 'v1'}

def test_builtin_guard_pack_selects_validates_and_fingerprints_stably() -> None:
    registry = builtin_template_registry()
    first = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=_event_bindings())
    second = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=_event_bindings())
    assert first.receipt.selection.outcome == 'selected'
    assert first.receipt.selection.selected_pack_id == 'worldguard.guard-contract.event'
    assert first.data['inputs']['events'][0]['event_id'] == 'event:ready'
    assert GuardContract.from_dict(first.data).contract_id == 'template:event-contract'
    assert len(first.receipt.validator_receipts) == 2
    assert first.receipt.instance_fingerprint == second.receipt.instance_fingerprint
    assert len(first.receipt.instance_fingerprint) == 64

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
    second = replace(current, pack_id='worldguard.guard-contract.second-base', manifest_fingerprint='')
    second = replace(second, manifest_fingerprint=second.current_fingerprint())
    with pytest.raises(TemplatePackError) as caught:
        TemplatePackRegistry.build((current, second))
    assert caught.value.code == 'TEMPLATE_BASE_AMBIGUOUS'

def test_template_construction_never_substitutes_for_semantic_provider_or_depth() -> None:
    instance = build_template_instance(builtin_template_registry(), contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=_event_bindings())
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

def test_stale_manifest_and_stale_registry_are_rejected() -> None:
    current = builtin_template_registry()
    manifest_data = current.by_id('worldguard.guard-contract.event').to_dict()
    manifest_data['pack_version'] = '2'
    stale_manifest = TemplatePackManifest.from_dict(manifest_data)
    with pytest.raises(TemplatePackError) as caught:
        stale_manifest.validate()
    assert caught.value.code == 'TEMPLATE_MANIFEST_STALE'
    mutable_registry = builtin_template_registry()
    mutable_registry.manifests[0].fragments[0].payload['schema_version'] = 'changed'
    with pytest.raises(TemplatePackError) as caught:
        mutable_registry.validate()
    assert caught.value.code in {'TEMPLATE_MANIFEST_STALE', 'TEMPLATE_REGISTRY_STALE'}

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
    unknown = replace(current, native_validator_ids=('worldguard.unknown.v1',), manifest_fingerprint='')
    unknown = replace(unknown, manifest_fingerprint=unknown.current_fingerprint())
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

def test_binding_change_changes_instance_fingerprint() -> None:
    registry = builtin_template_registry()
    first_bindings = _event_bindings()
    second_bindings = _event_bindings()
    second_bindings['claim_text'] = 'a different task-local event claim'
    first = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=first_bindings)
    second = build_template_instance(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], slot_bindings=second_bindings)
    assert first.receipt.binding_fingerprint != second.receipt.binding_fingerprint
    assert first.receipt.output_fingerprint != second.receipt.output_fingerprint
    assert first.receipt.instance_fingerprint != second.receipt.instance_fingerprint

def test_source_and_bundled_template_pack_runtime_are_exactly_equal() -> None:
    source = ROOT / 'worldguard' / 'template_packs.py'
    bundled = ROOT / 'skills' / 'worldguard' / 'runtime' / 'worldguard' / 'template_packs.py'
    assert bundled.read_bytes() == source.read_bytes()

def test_target_interchange_good_shape_is_exact_unsealed_and_content_bound() -> None:
    registry = builtin_template_registry()
    projection = build_target_template_interchange(registry, contract_kind=GUARD_CONTRACT_KIND, fact_ids=['guard:EventGuard'], native_registry_fingerprint=registry.registry_fingerprint)
    assert projection['schema_version'] == TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION
    assert set(projection) == set(TARGET_TEMPLATE_INTERCHANGE_FIELDS)
    assert set(projection['catalog']) == set(TARGET_TEMPLATE_CATALOG_FIELDS)
    assert 'catalog_digest' not in projection['catalog']
    assert projection['route_id'] == WORLDGUARD_TEMPLATE_ROUTE_ID
    assert projection['request_fingerprint'].startswith('sha256:')
    assert len(projection['request_fingerprint']) == 71
    native_by_id = {item.pack_id: item for item in registry.manifests if item.contract_kind == GUARD_CONTRACT_KIND}
    for template in projection['catalog']['templates']:
        assert set(template) == set(TARGET_TEMPLATE_MANIFEST_FIELDS)
        assert 'manifest_digest' not in template
        assert template['parameter_schema']['type'] == 'object'
        assert template['parameter_schema']['additionalProperties'] is False
        assert template['artifacts'][0]['content_template_hash'] == f"sha256:{native_by_id[template['template_id']].manifest_fingerprint}"
        assert template['builder']['content_hash'].startswith('sha256:')
        assert all((item['content_hash'].startswith('sha256:') for item in template['validators']))
    assert all((set(item) == set(TARGET_APPLICABILITY_RESULT_FIELDS) for item in projection['applicability_results']))
    eligibility = {item['template_id']: item['eligible'] for item in projection['applicability_results']}
    assert eligibility['worldguard.guard-contract.event'] is True
    assert eligibility['worldguard.guard-contract.base'] is False

def test_target_interchange_unknown_root_field_is_rejected() -> None:
    registry = builtin_template_registry()
    projection = build_target_template_interchange(registry, contract_kind=GUARD_CONTRACT_KIND, native_registry_fingerprint=registry.registry_fingerprint)
    unknown = deepcopy(projection)
    unknown['family_guess'] = 'forbidden'
    with pytest.raises(TemplatePackError) as caught:
        validate_target_template_interchange(unknown)
    assert caught.value.code == 'TEMPLATE_PROJECTION_ROOT_UNKNOWN_FIELD'
    assert caught.value.details['unknown_field_ids'] == ['family_guess']

@pytest.mark.parametrize(('contract_kind', 'fact_ids'), [(GUARD_CONTRACT_KIND, ['guard:EventGuard', 'guard:CausalGuard']), (MODEL_MESH_CONTRACT_KIND, ['coverage:bounded'])])
def test_target_interchange_candidate_inventory_equals_native_registry_once(contract_kind: str, fact_ids: list[str]) -> None:
    registry = builtin_template_registry()
    native_selection = registry.select(contract_kind, fact_ids)
    projection = build_target_template_interchange(registry, contract_kind=contract_kind, fact_ids=fact_ids, native_registry_fingerprint=registry.registry_fingerprint)
    native_ids = sorted((item.pack_id for item in registry.manifests if item.contract_kind == contract_kind))
    catalog_ids = [item['template_id'] for item in projection['catalog']['templates']]
    result_ids = [item['template_id'] for item in projection['applicability_results']]
    assert catalog_ids == native_ids
    assert result_ids == native_ids
    assert len(result_ids) == len(set(result_ids))
    eligible_candidates = {item['template_id'] for item in projection['applicability_results'] if item['eligible'] and item['template_id'] != projection['catalog']['base_template_id']}
    assert eligible_candidates == set(native_selection.candidate_pack_ids)

def test_target_interchange_wrong_route_is_rejected_by_worldguard() -> None:
    registry = builtin_template_registry()
    with pytest.raises(TemplatePackError) as caught:
        build_target_template_interchange(registry, contract_kind=GUARD_CONTRACT_KIND, native_registry_fingerprint=registry.registry_fingerprint, route_id='worldguard.not-the-template-route')
    assert caught.value.code == 'TEMPLATE_PROJECTION_ROUTE_INVALID'

def test_target_interchange_stale_native_identity_is_rejected() -> None:
    registry = builtin_template_registry()
    with pytest.raises(TemplatePackError) as caught:
        build_target_template_interchange(registry, contract_kind=GUARD_CONTRACT_KIND, native_registry_fingerprint='0' * 64)
    assert caught.value.code == 'TEMPLATE_PROJECTION_NATIVE_IDENTITY_STALE'
    assert caught.value.details['current_registry_fingerprint'] == registry.registry_fingerprint
