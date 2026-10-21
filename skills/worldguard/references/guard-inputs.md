# Guard inputs

A contract has `claim`, `world_model` and `inputs`. Ask for Guards through `claim.requested_semantics`
(`event`, `agent`, `spatial`, `resource`, `causal`, `conflict`, `norm`; `predictive` adds EventGuard and
CausalGuard). The claim `text` is a description only: WorldGuard never reads it, so every fact the claim
depends on must be in `inputs`. Each block below passes as written; copy it under `inputs:`.
Two complete, passing worlds: `assets/examples/scene_locked_door.yaml` (story) and
`assets/examples/trip_ferry.yaml` (trip).

To mark a part of the claim that a Guard does not own, add its id to `requested_semantics`; that Guard then
reports `BOUNDARY_EXCEEDED`. The ids are listed per Guard.

## EventGuard

```yaml
event_model: {initial_states: [door_locked]}
events:
  - {event_id: e_unlock, at: t1, requires: [door_locked], initiates: door_open, terminates: door_locked}
  - {event_id: e_enter, at: t2, requires: [door_open], initiates: iris_inside}
```

`event_id` is unique; `at` is a number, `t<number>` or an ISO date-time, and events run in that order;
`initiates`, `terminates`, `releases` name fluents (one id or a list). Optional: `requires` (fluents that must
hold when the event happens), `event_model.initial_states` (fluents that hold before the first event),
`event_model.contradictory_fluents`. Catches: an event whose required fluent does not hold at its time
(`EVENT_PRECONDITION_UNMET`, for example a door opened with a key handed over later), one event that starts and
ends the same fluent, declared contradictory fluents.
Boundary ids: `numeric_dynamics`, `thermodynamics`, `continuous_dynamics`.

## AgentGuard

```yaml
beliefs:
  Mara: {agent_id: Mara, beliefs: [door_locked], desires: [read_map], intentions: [unlock_door]}
```

The map key must equal `agent_id`; `beliefs` and `desires` must be non-empty lists; `intentions` must be present but may be `[]` (for example a bystander with no plan). Optional:
`agent_model.conflicting_intentions`. Catches: identity mismatch, incomplete belief/desire/intention records,
declared conflicting intentions. Boundary ids: `payoff`, `equilibrium`, `causal_effect`, `permission`.

## SpaceGuard

```yaml
spatial_relations:
  - {at: t1, x: key, y: box, relation: NTPP}
  - {at: t1, x: box, y: room, relation: NTPP}
```

`relation` is an RCC8 name: `DC`, `EC`, `PO`, `EQ`, `TPP`, `NTPP`, `TPPI`, `NTPPI`. Catches: two different
relations for one pair at one time, wrong converses, a non-`EQ` relation of an object to itself, and
compositions that contradict a declared relation (key inside box inside room, but key `DC` room).
Boundary ids: `metric_distance`, `geometry`.

## ResourceGuard

```yaml
resources:
  places: {at_port: [{color: traveler, qty: 1}], on_ferry: []}
  capacities: {on_ferry: 1}
  transitions:
    - {id: board, consumes: [{place: at_port, color: traveler, qty: 1}], produces: [{place: on_ferry, color: traveler, qty: 1}]}
```

`places` hold the starting tokens (`color`, `qty`). `transitions` fire in list order: the list is the story or
clock order, and each step can only consume tokens that earlier steps left. `capacities` (optional) cap tokens
per place. Catches: a step that needs a token that is not there (locked door, missed ferry, someone in two
places), capacity overflow. Boundary ids: `permission`, `authorization`, `obligation`.

## CausalGuard

```yaml
causal_model:
  variables: [train_arrival_h, ferry_out_h, slack_h]
  equations: {train_arrival_h: "10.08", ferry_out_h: "11.0", slack_h: "ferry_out_h - train_arrival_h"}
  scenarios: {timetable: {}}
```

Every variable needs a scalar equation over numbers and other variables; at least one of `scenarios`,
`holdout_scenarios`, `interventions` or `counterfactuals` is required. Catches: missing or unsafe equations,
cycles, scenarios that fail to evaluate. Does not check limits such as `slack_h >= 0`.
Boundary ids: `temporal_story`.

## ConflictGuard

```yaml
game_model:
  players: [a, b]
  actions: {a: [hold], b: [hold]}
  states: [s]
  transitions: [{from: s, to: s, probabilities: [1.0]}]
  payoffs: [{state: s, reward: {a: 1, b: 1}}]
```

All five parts are required. Catches: probabilities that do not sum to 1, duplicate players, references to
undeclared states or players. Boundary ids: `obligation`, `permission`, `deontic`.

## NormGuard

```yaml
norms:
  - {modality: permitted, actor: pilot, action: leave_harbor, condition: {fact_id: storm_cleared, value: true}}
  - {modality: forbidden, actor: pilot, action: leave_harbor, condition: {fact_id: storm_uncleared, value: true}}
facts:
  - {fact_id: storm_cleared, value: true}
  - {fact_id: storm_uncleared, value: false}
```

`modality` is `permitted`, `obligatory`, `forbidden` or `prohibited`; every `condition` names a fact with a
boolean `value`. A norm whose condition is false is inactive. Write a claimed permission as a `permitted` norm.
Catches: the same actor and action both forbidden and permitted/required by active norms
(`NORM_ACTIVE_CONFLICT`), unknown modalities, missing or duplicate facts. Boundary ids: `token`, `capacity`,
`physical_enablement`.
