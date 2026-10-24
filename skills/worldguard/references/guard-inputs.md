# Guard inputs

Use `claim`, `world_model`, `inputs`. `requested_semantics` names event, agent,
spatial, resource, causal, conflict or norm; predictive derives Event and Causal.
Each input block below passes with its matching `claim.asserts` row. Claim prose is
never read. False rows FAIL `CLAIM_ASSERTION_FALSE`; unknown model items GAP
`CLAIM_ASSERTION_UNRESOLVED`; absent rows GAP `CLAIM_NOT_BOUND`. Complete worlds:
`assets/examples/scene_locked_door.yaml` and `trip_ferry.yaml`.

Boundary ids are listed per Guard; request one with its normal semantic for
`BOUNDARY_EXCEEDED`.

An unselected Guard's boundary remains `QUALIFICATION_SEMANTIC_UNMAPPED` GAP with
an owner/semantic hint. Priority: FAIL > GAP > BOUNDARY_EXCEEDED > PASS.

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

`places` hold starting tokens (`color`, `qty`). Without events, transitions fire in list order;
with events, every transition names its event and complete links run by event time. Each step
can consume only tokens that earlier steps left. `capacities` (optional) cap tokens
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
- Every transition names its event when the world has events: `{id: board, event: e_board, consumes: [...], produces: [...]}`. Missing links (some or all) give GAP `RESOURCE_TRANSITION_UNLINKED`, naming the transfer ids. Explicit links to absent or scoped events are input errors. Complete links run by event time; transfers at one event keep list order.
- A place and fluent with the same name must agree initially and after each event: the fluent holds exactly when the place has at least one token. Otherwise FAIL `WORLD_EVENT_TOKEN_MISMATCH` names the first inconsistent step. These world checks run regardless of requested Guards.
- A single token (declared `unique` or alone at that time) must sit where same-`at` spatial rows put it: a declared-disjoint region FAILs `WORLD_SPACE_TOKEN_MISMATCH`, an unrelated one is GAP `WORLD_SPACE_TOKEN_UNRELATED`; use one place name or declare the nesting.
- `resources.unique: [traveler]` rejects a color whose total across places exceeds one after a step.
- An event can name `actor: traveler` and `with: [friend]`; every unique color moved by a linked transition must be among its participants.
- Optional `world_model.entities: {traveler: {kind: person}, port: {kind: place}}` registers ids used by beliefs, spatial pairs, event participants and unique colors. Missing ids produce `ENTITY_UNDECLARED`.
- Related events at one time produce `EVENT_SAME_TIME_ORDER_UNKNOWN`; give them distinct times.

## Actions and norms

An event with `actor: traveler, action: take_boat` is checked against active prohibitions. A norm can use `condition: {fluent: storm_warning, value: true}`; its fluent is read immediately before that event. A `modality` claim row for such a norm needs `at: <time>`. Static `fact_id` conditions keep their existing meaning. Only prohibitions are checked against actions; this does not establish fulfilment of obligations.

Once any event declares an actor, every BDI intention needs an event with that actor and matching action. To model knowledge over time, use an event such as `{event_id: read_log, at: t3, initiates: cora_knows_fraud}` and require `cora_knows_fraud` on later events. AgentGuard does not infer belief changes from prose.
