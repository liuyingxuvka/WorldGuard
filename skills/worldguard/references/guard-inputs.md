# Guard inputs

A contract has `claim`, `world_model` and `inputs`. Ask for Guards through `claim.requested_semantics`
(`event`, `agent`, `spatial`, `resource`, `causal`, `conflict`, `norm`; `predictive` adds EventGuard and
CausalGuard). The claim `text` is a description only: WorldGuard never reads it, so every fact the claim
depends on must be in `inputs`. Each block below passes as written; copy it under `inputs:`.
Two complete, passing worlds: `assets/examples/scene_locked_door.yaml` (story) and
`assets/examples/trip_ferry.yaml` (trip).

Bind the claim to the model with `claim.asserts`, a list of rows checked against the model (each Guard below
shows its row; a row also selects its Guard). A false row is `FAIL` (`CLAIM_ASSERTION_FALSE`, with the observed
value); a row naming something the model does not declare is `GAP` (`CLAIM_ASSERTION_UNRESOLVED`); a claim
without `asserts` is `GAP` (`CLAIM_NOT_BOUND`: claim not bound to the world model).

To mark a part of the claim that a Guard does not own, add its id to `requested_semantics`; that Guard then
reports `BOUNDARY_EXCEEDED`. The ids are listed per Guard.

A boundary id listed below yields `BOUNDARY_EXCEEDED` only alongside a Guard already derived from
normal semantics or assertions. A boundary of an unselected Guard remains `QUALIFICATION_SEMANTIC_UNMAPPED`
`GAP`, with a hint naming that Guard and its normal semantic. Real failures and gaps retain priority:
`FAIL` > `GAP` > `BOUNDARY_EXCEEDED` > `PASS`.

## EventGuard

```yaml
event_model: {initial_states: [door_locked]}
events:
  - {event_id: e_unlock, at: t1, requires: [door_locked], initiates: door_open, terminates: door_locked}
  - {event_id: e_enter, at: t2, requires: [door_open], initiates: iris_inside}
```

Claim assertion: `{holds: iris_inside, at: t2}` (after every event at or before `at`; add `value: false` for
"does not hold") or `{event: e_unlock, before: e_enter}`.

`event_id` is unique within one `scenario_id` (or the default scenario); different scenarios may reuse ids.
Use one time kind throughout all events and `holds.at` assertions in a contract: a YAML number,
a label such as `t1`/`day2` with one shared prefix, an ISO date/date-time, or a quoted same-day
clock such as `"9:40"` or `"17:12:30"`. ISO times must consistently include or omit timezones.
For trips crossing midnight, use ISO dates. Quote clock times: YAML reads unquoted `9:40` as the
number 580, so mixing it with `"10:20"` is an input error. Unknown times such as `evening` or
`t4b`, mixed kinds/prefixes, and duplicate event ids within one scenario are input errors.
For `before`/`holds`, add `scenario: <id>` to select a declared scenario; ambiguous reused event ids
without it and unknown scenarios are gaps. Spatial relation `at` values remain uninterpreted labels.
A missing event time remains a native missing-axiom `GAP`; an explicitly supplied invalid time is an input error.
Events run in parsed time order;
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

Claim assertion: `{agent: Mara, intends: unlock_door}` (or `believes`, `desires`).

The map key must equal `agent_id`; `beliefs` and `desires` must be non-empty lists; `intentions` must be present but may be `[]` (for example a bystander with no plan). Optional:
`agent_model.conflicting_intentions`. Catches: identity mismatch, incomplete belief/desire/intention records,
declared conflicting intentions. Boundary ids: `payoff`, `equilibrium`, `causal_effect`, `permission`.

## SpaceGuard

```yaml
spatial_relations:
  - {at: t1, x: key, y: box, relation: NTPP}
  - {at: t1, x: box, y: room, relation: NTPP}
```

Claim assertion: `{relation: NTPP, x: key, y: box, at: t1}` (a declared relation or its converse).

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

Claim assertion: `{place: on_ferry, color: traveler, qty: 1}` (tokens after all transitions; add
`after: <transition id>` for an earlier point).

`places` hold the starting tokens (`color`, `qty`). `transitions` fire in list order: the list is the story or
clock order, and each step can only consume tokens that earlier steps left. `capacities` (optional) cap tokens
per place. Catches: a step that needs a token that is not there (locked door, missed ferry, someone in two
places), capacity overflow. Boundary ids: `permission`, `authorization`, `obligation`.

## CausalGuard

```yaml
causal_model:
  variables: [train_arrival_h, ferry_out_h, slack_h]
  equations: {train_arrival_h: "10.08", ferry_out_h: "11.0", slack_h: "ferry_out_h - train_arrival_h"}
  scenarios: {timetable: {}, train_10min_late: {train_arrival_h: 10.25}}
  interventions:
    - {intervention_id: train_20min_late, scenario_id: timetable, set: {train_arrival_h: 10.4}}
  constraints: ["slack_h >= 0"]
```

Claim assertion: `{variable: slack_h, op: ">=", value: 0.5}` (in every scenario, holdout and intervention, or add `scenario: <scenario or intervention id>`).

Every variable needs a scalar equation over numbers and other variables; at least one of `scenarios`,
`holdout_scenarios`, `interventions` or `counterfactuals` is required. Optional `constraints`: comparisons of
variables and numbers that must hold in every scenario, holdout and intervention. Scenario and holdout
assignments replace the named variable's equation, independent of declaration order; other equations
recompute from those values. `exogenous` names inputs supplied only by scenarios (no equation).
`interventions` is a list of mappings: unique nonempty `intervention_id`, an existing `scenario_id`
(including an empty `{}` scenario or a holdout), and `set` mapping declared variables/exogenous inputs to
finite numbers. A do assignment takes precedence over the scenario; counterfactuals still query its result.
Run ids must be distinct across scenarios, holdouts and interventions. Malformed interventions are input
errors. Catches: a constraint that fails
(`CAUSAL_CONSTRAINT_VIOLATED`, for example a negative transfer time), missing or unsafe equations, cycles,
scenarios that fail to evaluate.
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

Claim assertion: `{player: a, state: s, reward: 1}`.

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

Claim assertion: `{actor: pilot, action: leave_harbor, modality: permitted}` (an active norm with that
modality and none of the opposite one).

`modality` is `permitted`, `obligatory`, `forbidden` or `prohibited`; every `condition` names a fact with a
boolean `value`. A norm whose condition is false is inactive. Write a claimed permission as a `permitted` norm.
Catches: the same actor and action both forbidden and permitted/required by active norms
(`NORM_ACTIVE_CONFLICT`), unknown modalities, missing or duplicate facts. Boundary ids: `token`, `capacity`,
`physical_enablement`.

## Shared event clock and entities

- In equations/constraints, `t_<event_id>` is the unscoped event time in hours; ISO times start at midnight on the first event day. Example: `equations: {slack: "t_ferry - t_train"}`. Scenario/intervention assignments can override these names. Do not declare a variable with the same name.
- Link every resource transition to an event, or leave all unlinked: `{id: board, event: e_board, consumes: [...], produces: [...]}`. Linked transitions run by event time; ties keep list order.
- `resources.unique: [traveler]` rejects a color whose total across places exceeds one after a step.
- An event can name `actor: traveler` and `with: [friend]`; every unique color moved by a linked transition must be among its participants.
- Optional `world_model.entities: {traveler: {kind: person}, port: {kind: place}}` registers ids used by beliefs, spatial pairs, event participants and unique colors. Missing ids produce `ENTITY_UNDECLARED`.
- Related events at one time produce `EVENT_SAME_TIME_ORDER_UNKNOWN`; give them distinct times.

## Actions and norms

An event with `actor: traveler, action: take_boat` is checked against active prohibitions. A norm can use `condition: {fluent: storm_warning, value: true}`; its fluent is read immediately before that event. A `modality` claim row for such a norm needs `at: <time>`. Static `fact_id` conditions keep their existing meaning. Only prohibitions are checked against actions; this does not establish fulfilment of obligations.

Once any event declares an actor, every BDI intention needs an event with that actor and matching action. To model knowledge over time, use an event such as `{event_id: read_log, at: t3, initiates: cora_knows_fraud}` and require `cora_knows_fraud` on later events. AgentGuard does not infer belief changes from prose.
