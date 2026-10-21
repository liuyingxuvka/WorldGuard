from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
SEMANTIC_GUARD_ROUTES: dict[str, tuple[str, ...]] = {'event': ('EventGuard',), 'events': ('EventGuard',), 'temporal': ('EventGuard',), 'timeline': ('EventGuard',), 'agent': ('AgentGuard',), 'bdi': ('AgentGuard',), 'space': ('SpaceGuard',), 'spatial': ('SpaceGuard',), 'rcc8': ('SpaceGuard',), 'resource': ('ResourceGuard',), 'conservation': ('ResourceGuard',), 'causal': ('CausalGuard',), 'causality': ('CausalGuard',), 'intervention': ('CausalGuard',), 'counterfactual': ('CausalGuard',), 'conflict': ('ConflictGuard',), 'game': ('ConflictGuard',), 'norm': ('NormGuard',), 'normative': ('NormGuard',), 'prediction': ('EventGuard', 'CausalGuard'), 'predictive': ('EventGuard', 'CausalGuard'), 'forecast': ('EventGuard', 'CausalGuard'), 'future_outcome': ('EventGuard', 'CausalGuard')}
PREDICTIVE_SEMANTICS = {'prediction', 'predictive', 'forecast', 'future_outcome'}
RETIRED_WORLD_MODEL_INPUT_FIELDS = {'event_line', 'agents', 'rcc8_relations', 'resources', 'causal_variables', 'causal_equations', 'causal_graph', 'conflict_players', 'conflict_actions', 'conflict_states', 'conflict_payoffs', 'conflict_transitions', 'norms', 'facts', 'variable_observations', 'signal_observations'}
RETIRED_TOP_LEVEL_INPUT_FIELDS = {'agents', 'norm_model', 'signal_observations', 'time_series_observations', 'scenarios', 'holdout_scenarios', 'interventions', 'counterfactuals'}

def _reject_retired_runtime_input_paths(world_model: dict[str, Any], inputs: dict[str, Any]) -> None:
    retired_world = sorted(RETIRED_WORLD_MODEL_INPUT_FIELDS.intersection(world_model))
    if retired_world:
        raise ValueError('world_model uses retired Guard input fields; migrate them to inputs: ' + ', '.join(retired_world))
    retired_inputs = sorted(RETIRED_TOP_LEVEL_INPUT_FIELDS.intersection(inputs))
    if retired_inputs:
        raise ValueError('inputs uses retired alternate Guard paths: ' + ', '.join(retired_inputs))
    event_model = inputs.get('event_model')
    if isinstance(event_model, dict) and 'events' in event_model:
        raise ValueError('inputs.event_model.events is retired; migrate events to inputs.events')
    if isinstance(event_model, dict) and 'exclusive_violation' in event_model:
        raise ValueError('inputs.event_model.exclusive_violation is retired; use contradictory_fluents')
    agent_model = inputs.get('agent_model')
    if isinstance(agent_model, dict) and 'agents' in agent_model:
        raise ValueError('inputs.agent_model.agents is retired; migrate agents to inputs.beliefs')
    for index, event in enumerate(inputs.get('events', [])):
        if not isinstance(event, dict):
            continue
        retired = sorted({'branch_ids', 'perturbation_ids'}.intersection(event))
        if retired:
            raise ValueError(f'inputs.events[{index}] uses retired fields: ' + ', '.join(retired))
    observations = inputs.get('variable_observations')
    if observations is not None:
        if not isinstance(observations, dict):
            raise ValueError('inputs.variable_observations must be a mapping of variable id to timepoint ids')
        if any((not isinstance(value, list) for value in observations.values())):
            raise ValueError('inputs.variable_observations values must be lists of timepoint ids')
    causal = inputs.get('causal_model')
    if isinstance(causal, dict):
        for field_name in ('scenarios', 'holdout_scenarios'):
            records = causal.get(field_name)
            if records is None:
                continue
            if not isinstance(records, dict):
                raise ValueError(f'inputs.causal_model.{field_name} must be a mapping')
            if any((isinstance(record, dict) and 'values' in record for record in records.values())):
                raise ValueError(f'inputs.causal_model.{field_name} records use retired nested values')
        for index, intervention in enumerate(causal.get('interventions', [])):
            if isinstance(intervention, dict):
                retired = sorted({'id', 'values'}.intersection(intervention))
                if retired:
                    raise ValueError(f'inputs.causal_model.interventions[{index}] uses retired fields: ' + ', '.join(retired))
        for index, counterfactual in enumerate(causal.get('counterfactuals', [])):
            if isinstance(counterfactual, dict):
                retired = sorted({'id', 'variable'}.intersection(counterfactual))
                if retired:
                    raise ValueError(f'inputs.causal_model.counterfactuals[{index}] uses retired fields: ' + ', '.join(retired))
    for index, fact in enumerate(inputs.get('facts', [])):
        if isinstance(fact, dict) and 'name' in fact:
            raise ValueError(f'inputs.facts[{index}].name is retired; use fact_id')
    for index, norm in enumerate(inputs.get('norms', [])):
        condition = norm.get('condition') if isinstance(norm, dict) else None
        if isinstance(condition, dict) and 'fact' in condition:
            raise ValueError(f'inputs.norms[{index}].condition.fact is retired; use fact_id')

@dataclass(frozen=True)
class ClaimAtom:
    atom_id: str
    text: str = ''
    requested_semantics: list[str] = field(default_factory=list)
    predictive_intent: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ClaimAtom':
        retired = sorted({'id', 'semantics', 'predictive'}.intersection(data))
        if retired:
            raise ValueError('claim atom uses retired fields: ' + ', '.join(retired))
        requested = data.get('requested_semantics', [])
        if isinstance(requested, str):
            requested = [requested]
        return cls(atom_id=str(data.get('atom_id', '')), text=str(data.get('text', '')), requested_semantics=[str(item) for item in requested], predictive_intent=bool(data.get('predictive_intent', False)))

    def to_dict(self) -> dict[str, Any]:
        return {'atom_id': self.atom_id, 'text': self.text, 'requested_semantics': self.requested_semantics, 'predictive_intent': self.predictive_intent}

@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    target_guards: list[str] = field(default_factory=list)
    requested_semantics: list[str] = field(default_factory=list)
    atoms: list[ClaimAtom] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Claim':
        if 'target_guard' in data:
            raise ValueError('claim.target_guard is retired; migrate the input to claim.target_guards')
        target_guards = data.get('target_guards', [])
        if isinstance(target_guards, str):
            target_guards = [target_guards]
        requested_semantics = data.get('requested_semantics', [])
        if isinstance(requested_semantics, str):
            requested_semantics = [requested_semantics]
        atoms = [ClaimAtom.from_dict(item) for item in data.get('atoms', [])]
        if not requested_semantics and (not atoms):
            raise ValueError('claim requires current requested_semantics or structured atoms')
        return cls(claim_id=str(data.get('claim_id', '')), text=str(data.get('text', '')), target_guards=list(target_guards), requested_semantics=[str(item) for item in requested_semantics], atoms=atoms)

    def to_dict(self) -> dict[str, Any]:
        return {'claim_id': self.claim_id, 'text': self.text, 'target_guards': self.target_guards, 'requested_semantics': self.requested_semantics, 'atoms': [atom.to_dict() for atom in self.atoms]}

def claim_predictive_intent(claim: Claim) -> bool:
    semantics = {str(item).strip().lower() for item in claim.requested_semantics if str(item).strip()}
    semantics.update((str(item).strip().lower() for atom in claim.atoms for item in atom.requested_semantics if str(item).strip()))
    return bool(any((atom.predictive_intent for atom in claim.atoms)) or semantics.intersection(PREDICTIVE_SEMANTICS))

def claim_semantics(claim: Claim) -> tuple[str, ...]:
    values = [*claim.requested_semantics]
    values.extend((item for atom in claim.atoms for item in atom.requested_semantics))
    if claim_predictive_intent(claim):
        values.append('predictive')
    return tuple(dict.fromkeys((str(item).strip().lower() for item in values if str(item).strip())))

@dataclass(frozen=True)
class GuardRequirementDerivation:
    """Canonical claim-to-Guard denominator shared by every WorldGuard route."""
    claim_id: str
    requested_semantics: tuple[str, ...]
    guard_ids: tuple[str, ...]
    unmapped_semantics: tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {'schema_version': 'worldguard.guard_requirement_derivation.v1', 'claim_id': self.claim_id, 'requested_semantics': list(self.requested_semantics), 'guard_ids': list(self.guard_ids), 'unmapped_semantics': list(self.unmapped_semantics), 'fingerprint': self.fingerprint}

def derive_guard_requirements(claim: Claim) -> GuardRequirementDerivation:
    """Own the one current claim-semantics-to-Guard derivation path."""
    guards: list[str] = []
    semantics = claim_semantics(claim)
    for semantic in semantics:
        guards.extend(SEMANTIC_GUARD_ROUTES.get(semantic, ()))
    guard_ids = tuple(dict.fromkeys(guards))
    unmapped = tuple((semantic for semantic in semantics if semantic not in SEMANTIC_GUARD_ROUTES))
    identity = {'schema_version': 'worldguard.guard_requirement_derivation.v1', 'claim_id': claim.claim_id, 'requested_semantics': list(semantics), 'guard_ids': list(guard_ids), 'unmapped_semantics': list(unmapped)}
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return GuardRequirementDerivation(claim_id=claim.claim_id, requested_semantics=semantics, guard_ids=guard_ids, unmapped_semantics=unmapped, fingerprint='sha256:' + hashlib.sha256(canonical).hexdigest())

def derive_required_guards(claim: Claim) -> tuple[str, ...]:
    """Return the Guard IDs from the canonical requirement derivation."""
    return derive_guard_requirements(claim).guard_ids

def unmapped_claim_semantics(claim: Claim) -> tuple[str, ...]:
    return derive_guard_requirements(claim).unmapped_semantics

@dataclass(frozen=True)
class WorldModel:
    model_id: str
    model_version: str
    entities: dict[str, Any] = field(default_factory=dict)
    relations: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    scope_limits: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'WorldModel':
        if 'artifact_version' in data:
            raise ValueError('world_model.artifact_version is retired; migrate the input to world_model.model_version')
        return cls(model_id=str(data.get('model_id', '')), model_version=str(data.get('model_version', '')), entities=dict(data.get('entities', {})), relations=dict(data.get('relations', {})), assumptions=list(data.get('assumptions', [])), scope_limits=list(data.get('scope_limits', [])), data=dict(data))

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.data)
        result.update({'model_id': self.model_id, 'model_version': self.model_version, 'entities': self.entities, 'relations': self.relations, 'assumptions': self.assumptions, 'scope_limits': self.scope_limits})
        return result

@dataclass(frozen=True)
class GuardDependencies:
    upstream_results: list[Any] = field(default_factory=list)
    read_only: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> 'GuardDependencies':
        data = data or {}
        return cls(upstream_results=list(data.get('upstream_results', [])), read_only=bool(data.get('read_only', True)))

    def to_dict(self) -> dict[str, Any]:
        return {'upstream_results': self.upstream_results, 'read_only': self.read_only}

@dataclass(frozen=True)
class OutputRequirements:
    require_ledgers: bool = True
    require_counterexample_for_non_pass: bool = True
    allowed_status: list[str] = field(default_factory=lambda: ['PASS', 'FAIL', 'GAP', 'BOUNDARY_EXCEEDED'])

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> 'OutputRequirements':
        data = data or {}
        return cls(require_ledgers=bool(data.get('require_ledgers', True)), require_counterexample_for_non_pass=bool(data.get('require_counterexample_for_non_pass', True)), allowed_status=list(data.get('allowed_status', ['PASS', 'FAIL', 'GAP', 'BOUNDARY_EXCEEDED'])))

    def to_dict(self) -> dict[str, Any]:
        return {'require_ledgers': self.require_ledgers, 'require_counterexample_for_non_pass': self.require_counterexample_for_non_pass, 'allowed_status': self.allowed_status}

@dataclass(frozen=True)
class GuardContract:
    contract_id: str
    schema_version: str
    run_id: str
    claim: Claim
    world_model: WorldModel
    inputs: dict[str, Any] = field(default_factory=dict)
    dependencies: GuardDependencies = field(default_factory=GuardDependencies)
    output_requirements: OutputRequirements = field(default_factory=OutputRequirements)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'GuardContract':
        world_model = dict(data.get('world_model', {}))
        inputs = dict(data.get('inputs', {}))
        _reject_retired_runtime_input_paths(world_model, inputs)
        return cls(contract_id=str(data.get('contract_id', '')), schema_version=str(data.get('schema_version', 'worldguard.contract.v1')), run_id=str(data.get('run_id', 'worldguard-run')), claim=Claim.from_dict(data.get('claim', {})), world_model=WorldModel.from_dict(world_model), inputs=inputs, dependencies=GuardDependencies.from_dict(data.get('dependencies')), output_requirements=OutputRequirements.from_dict(data.get('output_requirements')))

    def for_guard(self, guard: str, upstream_results: list[Any] | None=None) -> 'GuardContract':
        """Bind one child to the same current model and read-only upstream inputs."""
        dependencies = GuardDependencies(upstream_results=upstream_results or [], read_only=True)
        return GuardContract(contract_id=f'{self.contract_id}:{guard}', schema_version=self.schema_version, run_id=self.run_id, claim=Claim(claim_id=self.claim.claim_id, text=self.claim.text, target_guards=[guard], requested_semantics=self.claim.requested_semantics, atoms=self.claim.atoms), world_model=self.world_model, inputs=self.inputs, dependencies=dependencies, output_requirements=self.output_requirements)

    def to_dict(self) -> dict[str, Any]:
        result = {'contract_id': self.contract_id, 'schema_version': self.schema_version, 'run_id': self.run_id, 'claim': self.claim.to_dict(), 'world_model': self.world_model.to_dict(), 'inputs': self.inputs, 'dependencies': self.dependencies.to_dict(), 'output_requirements': self.output_requirements.to_dict()}
        return result
