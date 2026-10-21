> Historical document (0.1 MVP specification); it does not describe current behavior. Current behavior: `README.md` and `skills/worldguard/`.

# WorldGuard 技术规格

版本：0.1 MVP 规格草案  
语言：中文  
范围：模型优先的世界状态、行为、空间、资源、因果、冲突与规范一致性守卫系统  
重要边界：本规格定义的是可审计的模型检查框架，不是法律意见、真实燃料电池物理验证、安全认证、合规认证或市场预测系统。

## 目录

1. [装配覆盖清单](#装配覆盖清单)
2. [WorldGuard 概览与模型优先哲学](#worldguard-概览与模型优先哲学)
3. [总体架构与 Kernel 职责](#总体架构与-kernel-职责)
4. [统一 GuardContract 与 GuardResult 协议](#统一-guardcontract-与-guardresult-协议)
5. [统一 Ledger 模型](#统一-ledger-模型)
6. [七个 Guard 规格](#七个-guard-规格)
7. [跨 Guard Kernel 集成规则](#跨-guard-kernel-集成规则)
8. [ModelMesh 通用模型网格](#modelmesh-通用模型网格)
9. [燃料电池 toy demo 端到端示例](#燃料电池-toy-demo-端到端示例)
10. [测试设计](#测试设计)
11. [GitHub 仓库蓝图与 MVP 实施路线](#github-仓库蓝图与-mvp-实施路线)
12. [禁止做法、常见错误与最终接受标准](#禁止做法常见错误与最终接受标准)

## 装配覆盖清单

| 已接受路线材料 | 最终文件位置 | 覆盖状态 |
|---|---|---|
| wg-01 overview | [WorldGuard 概览与模型优先哲学](#worldguard-概览与模型优先哲学) | 已整合 |
| wg-02 architecture | [总体架构与 Kernel 职责](#总体架构与-kernel-职责) | 已整合 |
| wg-03 contracts | [统一 GuardContract 与 GuardResult 协议](#统一-guardcontract-与-guardresult-协议) | 已整合，保留唯一 canonical 定义 |
| wg-04 ledgers | [统一 Ledger 模型](#统一-ledger-模型) | 已整合，保留 ledger channel 与语义 |
| wg-05 EventGuard | [EventGuard](#eventguard--event-calculus) | 已整合 |
| wg-06 AgentGuard repaired lineage | [AgentGuard](#agentguard--bdi) | 使用已修复路径，不并列旧阻塞版本 |
| wg-07 SpaceGuard | [SpaceGuard](#spaceguard--rcc8-定性空间推理) | 已整合 |
| wg-08 ResourceGuard | [ResourceGuard](#resourceguard--colored-petri-nets) | 已整合 |
| wg-09 CausalGuard | [CausalGuard](#causalguard--structural-causal-models) | 已整合 |
| wg-10 ConflictGuard | [ConflictGuard](#conflictguard--stochasticmarkov-games) | 已整合 |
| wg-11 NormGuard | [NormGuard](#normguard--deontic-logic) | 已整合 |
| wg-12 kernel integration | [跨 Guard Kernel 集成规则](#跨-guard-kernel-集成规则) | 已整合 |
| wg-13 fuel-cell demo repair-v3 | [燃料电池 toy demo 端到端示例](#燃料电池-toy-demo-端到端示例) | 使用 repair-v3 toy-scope 版本 |
| wg-14 test design | [测试设计](#测试设计) | 已整合，保留 required test fields 与 resource_missing_key_001 |
| wg-15 repository MVP | [GitHub 仓库蓝图与 MVP 实施路线](#github-仓库蓝图与-mvp-实施路线) | 已整合 |
| wg-16 prohibitions acceptance | [禁止做法、常见错误与最终接受标准](#禁止做法常见错误与最终接受标准) | 已整合，保留 20 行接受矩阵 |

装配约束：

- 本文件只保留一个 canonical `GuardContract`、`GuardResult`、状态集合、ledger 语义和 Kernel 聚合规则。
- `PASS`、`FAIL`、`GAP`、`BOUNDARY_EXCEEDED` 不得在后文被重命名、弱化或折叠。
- 所有 toy demo 只验证 WorldGuard fixture 和 handoff 语义，不验证真实世界物理、法律、合规、安全或市场结论。

## WorldGuard 概览与模型优先哲学

WorldGuard 是一组模型优先的守卫器，用来判断某个世界声明是否被显式模型支持、被模型反驳、缺少必要输入，或越出了当前 Guard 的语义边界。

核心目标不是让语言模型“觉得合理”，而是让每个 claim 经过结构化模型检查：

```text
claim + world_model + guard_contract
  -> GuardResult(status, errors, counterexamples, ledgers)
  -> Kernel aggregation
  -> audit-ready report
```

WorldGuard 的基本哲学：

1. 模型先于叙事。所有重要结论都必须回到显式状态、事件、资源、因果图、博弈、规范或空间关系。
2. Guard 只判定自己拥有的形式系统。越界不是失败，而是 `BOUNDARY_EXCEEDED`。
3. 缺失信息不是通过语言补齐。缺失输入必须输出 `GAP`，并记录 missing slots。
4. 失败必须可复现。`FAIL` 必须带有最小反例或可重放 trace。
5. Kernel 只调度、隔离、聚合、保留证据，不做静默修复。
6. ledgers 是一等公民。没有 ledger 的 PASS 或 FAIL 不可接受。

WorldGuard 不替代领域专家系统。它给出的是“在这个模型内，该 claim 是否被支撑”的可审计结论。

## 总体架构与 Kernel 职责

WorldGuard 由一个 Kernel 和七个专用 Guard 构成：

```text
                    +----------------------+
                    |      User Claim      |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |    GuardContract     |
                    +----------+-----------+
                               |
                               v
+-----------+  +-----------+  +-----------+  +--------------+
|EventGuard |  |AgentGuard |  |SpaceGuard |  |ResourceGuard |
+-----+-----+  +-----+-----+  +-----+-----+  +------+-------+
      |              |              |               |
      +--------------+--------------+---------------+
                     |
                     v
+-----------+  +-----------+  +-----------+
|CausalGuard|  |ConflictG. |  | NormGuard |
+-----+-----+  +-----+-----+  +-----+-----+
      |              |              |
      +--------------+--------------+
                     |
                     v
              +--------------+
              |    Kernel    |
              +------+-------+
                     |
                     v
              +--------------+
              |GuardedReport |
              +--------------+
```

Kernel 的职责：

- 接收 `GuardContract`。
- 按 claim scope 和 dependency graph 调度对应 Guard。
- 维护 Guard 间只读 handoff。
- 收集 `GuardResult`。
- 合并 ledger，但不覆盖、删除、修复子 Guard 结果。
- 生成聚合状态与可审计报告。
- 在最终报告中保留所有 `FAIL`、`GAP`、`BOUNDARY_EXCEEDED` 的源头、反例和 ledger channel。

Kernel 明确不负责：

- 补齐缺失模型字段。
- 将一个 Guard 的 PASS 转换成另一个 Guard 的 PASS。
- 根据叙事合理性覆盖形式系统结果。
- 将 toy demo 结论扩展成现实工程或法律判断。

Kernel 聚合优先级：

```text
if any hard FAIL:
    aggregate_status = FAIL
elif any unresolved GAP:
    aggregate_status = GAP
elif any BOUNDARY_EXCEEDED:
    aggregate_status = BOUNDARY_EXCEEDED
elif all required Guards PASS:
    aggregate_status = PASS
else:
    aggregate_status = GAP
```

该优先级不代表隐藏其他状态。即使最终为 `FAIL`，所有同时存在的 `GAP` 和 `BOUNDARY_EXCEEDED` 仍必须出现在 aggregate ledger。

## 统一 GuardContract 与 GuardResult 协议

### GuardStatus

```yaml
GuardStatus:
  PASS:
    meaning: "claim 在当前 Guard 拥有的模型边界内被支持"
  FAIL:
    meaning: "claim 在当前 Guard 拥有的模型边界内被反驳"
  GAP:
    meaning: "claim 可能可判定，但当前模型缺少必要输入、规则或证据"
  BOUNDARY_EXCEEDED:
    meaning: "claim 要求的语义不属于该 Guard 的形式系统"
```

禁止把 `GAP` 当作低置信度 `PASS`，禁止把 `BOUNDARY_EXCEEDED` 当作普通 `FAIL`。

### GuardContract canonical schema

```yaml
GuardContract:
  contract_id: string
  schema_version: string
  run_id: string
  claim:
    claim_id: string
    text: string
    target_guard: string | list[string]
    requested_semantics: list[string]
  world_model:
    model_id: string
    model_version: string
    entities: map
    relations: map
    assumptions: list[string]
    scope_limits: list[string]
  inputs:
    events: list
    beliefs: list
    spatial_relations: list
    resources: map
    causal_model: map
    game_model: map
    norms: list
  dependencies:
    upstream_results: list[GuardResultRef]
    read_only: true
  output_requirements:
    require_ledgers: true
    require_counterexample_for_non_pass: true
    allowed_status: [PASS, FAIL, GAP, BOUNDARY_EXCEEDED]
```

### GuardResult canonical schema

```yaml
GuardResult:
  result_id: string
  contract_id: string
  guard: string
  status: PASS | FAIL | GAP | BOUNDARY_EXCEEDED
  supported_claims: list[string]
  rejected_claims: list[string]
  missing_slots: list[MissingSlot]
  boundary_exceeded:
    owner: string
    unsupported_claim_parts: list[string]
  errors:
    - code: string
      severity: info | warning | blocking
      message: string
      source_ref: string
  counterexamples:
    - counterexample_id: string
      kind: trace | missing_slot | boundary_trace | model_conflict
      steps: list
      minimal: true
  ledgers:
    event_ledger: list[LedgerEntry]
    agent_ledger: list[LedgerEntry]
    space_ledger: list[LedgerEntry]
    resource_ledger: list[LedgerEntry]
    causal_ledger: list[LedgerEntry]
    conflict_ledger: list[LedgerEntry]
    norm_ledger: list[LedgerEntry]
    error_ledger: list[LedgerEntry]
    gap_ledger: list[LedgerEntry]
    boundary_ledger: list[LedgerEntry]
    counterexample_ledger: list[LedgerEntry]
  assumptions_used: list[string]
  scope_limits: list[string]
```

最小状态转换关系：

```text
Input x State -> Set(Output x State)
GuardContract x GuardLocalState -> Set(GuardResult x GuardLocalState')
```

这条关系要求 Guard 输出是集合，因为同一输入可能暴露多个反例、缺口或边界问题。实现可以选择 deterministic canonical ordering，但不能丢弃元素。

## 统一 Ledger 模型

Ledger 负责保留可追溯事实，而不是美化报告。每个 ledger entry 必须能回答四个问题：

1. 这个条目来自哪个 claim 或 Guard？
2. 它记录了什么状态、事件、缺口、反例或边界？
3. 它支持、反驳或阻塞了哪个输出？
4. 下游是否允许读取，是否允许修改？

### LedgerEntry schema

```yaml
LedgerEntry:
  ledger_entry_id: string
  run_id: string
  claim_id: string
  guard: string
  channel: event | agent | space | resource | causal | conflict | norm | error | gap | boundary | counterexample | aggregate
  status_impact: supports_pass | supports_fail | creates_gap | marks_boundary | informational
  payload: map
  source_refs: list[string]
  read_only_for_downstream: true
  created_at_step: string
```

### Ledger channel 语义

| channel | 记录对象 | 不允许做的事 |
|---|---|---|
| event | 事件、fluent、initiation、termination、clipping | 用事件叙事替代因果方程 |
| agent | belief、desire、intention、capability | 自动补齐未声明信念 |
| space | RCC8 区域关系与一致性 | 从拓扑关系推导未声明 metric distance |
| resource | colored token、place、transition、capacity | 用权限或愿望替代 token |
| causal | SCM 变量、结构方程、do 查询、反事实 | 用时间先后替代因果 |
| conflict | players、actions、states、payoffs、policies | 用偏好叙事替代收益与策略 |
| norm | obligation、permission、forbidden、violation | 用资源可行性替代规范许可 |
| error | 稳定错误码 | 隐藏 blocking error |
| gap | missing slot | 静默补齐 |
| boundary | owner boundary | 当作普通 FAIL 或 warning |
| counterexample | 最小反例或 trace | 改写为模糊说明 |
| aggregate | Kernel 聚合状态与引用 | 覆盖子 ledger |

## 七个 Guard 规格

### EventGuard — Event Calculus

目标：检查事件、时间点、fluent 持续性、初始化、终止和冲突。

核心公式：

```text
HoldsAt(f, t2) if
  Happens(e, t1)
  and Initiates(e, f, t1)
  and t1 < t2
  and not Clipped(t1, f, t2)

Clipped(t1, f, t2) if
  Happens(e, tc)
  and Terminates(e, f, tc)
  and t1 < tc < t2
```

EventGuard 输入：

```yaml
event_model:
  timepoints: [t0, t1, t2]
  events:
    - id: e_start
      at: t0
      type: start_cell
  fluents:
    - cell_running
  axioms:
    initiates:
      - [e_start, cell_running, t0]
    terminates: []
  exclusivity:
    - [stack_hot, stack_cold]
```

EventGuard 检查：

- PASS：claim 的 fluent 被事件公理支持，且没有 clipping 或互斥冲突。
- FAIL：事件模型推出与 claim 矛盾的 fluent 或互斥 fluent 同时成立。
- GAP：缺少 `Happens`、`Initiates`、`Terminates` 或时间关系。
- BOUNDARY_EXCEEDED：claim 要求连续动力学、物理方程、因果干预、规范许可等非 Event Calculus 语义。

伪代码：

```python
def event_guard(contract, state):
    model = contract.inputs.events
    if asks_for_numeric_dynamics(contract.claim):
        return boundary("EVENT_BOUNDARY_NUMERIC_DYNAMICS")
    missing = find_missing_event_axioms(contract.claim, model)
    if missing:
        return gap("EVENT_MISSING_INITIATION_AXIOM", missing)
    contradiction = find_exclusive_fluent_violation(model)
    if contradiction:
        return fail("EVENT_CONTRADICTORY_FLUENTS", contradiction)
    if supports_fluent_claim(contract.claim, model):
        return pass_result()
    return gap("EVENT_UNSUPPORTED_FLUENT", required_slots(contract.claim))
```

### AgentGuard — BDI

修复线说明：本节采用已接受的 AgentGuard repair 路径。AgentGuard 不是“角色动机描述器”，而是 BDI 状态检查器。

BDI 元素：

```text
B_a(phi): agent a believes phi
D_a(goal): agent a desires goal
I_a(plan): agent a intends plan
Cap_a(action): agent a can execute action
```

选择意图的最低条件：

```text
Selects(a, intention) only if
  all required beliefs hold
  and target desire is declared
  and required capability exists
  and intention does not conflict with another active intention
```

输入：

```yaml
agent_model:
  agents:
    controller:
      beliefs: [pressure_low, stack_ready]
      desires: [restore_pressure]
      capabilities: [open_valve]
      intentions:
        - id: i_open_valve
          preconditions: [pressure_low, stack_ready]
          action: open_valve
          target_desire: restore_pressure
```

输出语义：

- PASS：belief、desire、intention、capability 均声明并一致。
- FAIL：意图互斥、能力与行动矛盾、同一 agent 同时承诺不可共存意图。
- GAP：缺少必要 belief、desire、intention 或 capability。
- BOUNDARY_EXCEEDED：要求博弈均衡、规范许可、因果效果或资源 token。

### SpaceGuard — RCC8 定性空间推理

SpaceGuard 使用 RCC8 base relations：

```text
DC   disconnected
EC   externally connected
PO   partially overlapping
EQ   equal
TPP  tangential proper part
NTPP non-tangential proper part
TPPi inverse TPP
NTPPi inverse NTPP
```

输入：

```yaml
space_model:
  regions: [robot_body, safe_zone, wall]
  relations:
    - at: t0
      x: robot_body
      y: safe_zone
      relation: DC
  transition_neighborhood:
    DC: [EC]
    EC: [DC, PO]
```

检查：

- PASS：RCC8 关系一致，转换在 declared neighborhood 内。
- FAIL：同一 pair 同一时间存在不相容 base relations。
- GAP：缺少 pair relation 或 composition table 条目。
- BOUNDARY_EXCEEDED：claim 要求 metric distance、连续几何、传感器融合或动力学。

### ResourceGuard — Colored Petri Nets

ResourceGuard 用 Colored Petri Nets 检查资源、容量、并发和可执行性。

CPN 定义：

```text
CPN = (P, T, C, I, O, M)
P: places
T: transitions
C: token colors
I: input arcs
O: output arcs
M: marking

Enabled(t, M) iff
  for every input arc (p, t, color, qty):
    M(p, color) >= qty
  and every output capacity constraint is satisfied
```

输入：

```yaml
resource_model:
  places:
    hydrogen_tank:
      - color: h2
        qty: 2
    stack_available:
      - color: stack
        qty: 1
  capacities:
    buffer: 1
  transitions:
    - id: run_cell
      consumes:
        - place: hydrogen_tank
          color: h2
          qty: 1
      produces:
        - place: electricity_bus
          color: kwh
          qty: 1
```

输出：

- PASS：transition enabled 且容量约束满足。
- FAIL：容量溢出、互斥资源重复消费、dead transition 被声明可执行。
- GAP：缺少 token、place、color、arc 或 capacity 定义。
- BOUNDARY_EXCEEDED：claim 要求规范授权、真实热力学、市场价格或因果证明。

### CausalGuard — Structural Causal Models

CausalGuard 用 SCM 检查因果结构与反事实查询。

SCM：

```text
M = (U, V, F, P(U))
V = endogenous variables
U = exogenous variables
F = structural equations

do(X = x) replaces structural equation for X with constant x.
```

输入：

```yaml
causal_model:
  variables: [load, temperature, degradation]
  graph:
    - [load, temperature]
    - [temperature, degradation]
  equations:
    temperature: "f(load, ambient)"
    degradation: "g(temperature)"
  query:
    do:
      load: high
    effect: degradation
```

输出：

- PASS：变量、图、结构方程和 do 查询一致。
- FAIL：有向环、反事实与模型方程矛盾、claim 与 SCM 推出结果冲突。
- GAP：缺少变量、结构方程、外生假设或查询定义。
- BOUNDARY_EXCEEDED：只有时间先后、叙事“因为”、规范义务或博弈偏好。

### ConflictGuard — Stochastic/Markov Games

ConflictGuard 检查多 agent 冲突、策略、收益和状态转移。

Markov game：

```text
G = (S, N, {A_i}, T, {R_i}, gamma)
S: states
N: players
A_i: actions for player i
T(s' | s, a_1, ..., a_n): transition probability
R_i(s, a_1, ..., a_n): reward for player i
```

输入：

```yaml
game_model:
  players: [controller, operator]
  states: [normal, alarm]
  actions:
    controller: [continue, stop]
    operator: [approve, deny]
  transitions:
    - from: normal
      joint_action: [continue, approve]
      to: normal
      p: 1.0
  payoffs:
    - state: normal
      joint_action: [continue, approve]
      reward:
        controller: 3
        operator: 3
```

输出：

- PASS：players、actions、states、transition probabilities、payoffs、policies 声明完整且 claim 被支持。
- FAIL：概率和不为 1、策略不在 action set、收益矛盾、声称 best response 但 payoff 反驳。
- GAP：缺少 payoff、policy、player、action 或 transition。
- BOUNDARY_EXCEEDED：claim 要求 deontic obligation、物理 enablement 或 SCM 反事实。

### NormGuard — Deontic Logic

NormGuard 检查义务、许可、禁止、违反和规范冲突。

基本符号：

```text
O_a(phi): agent a is obligated to make phi true
P_a(phi): agent a is permitted to make phi true
F_a(phi): agent a is forbidden to make phi true
F_a(phi) = O_a(not phi)
Violation(a, phi) if O_a(phi) and not phi when deadline/condition is active
```

输入：

```yaml
norm_model:
  norms:
    - id: n_precheck
      modality: obligatory
      actor: operator
      action: complete_precheck
      condition: before_start
    - id: n_start
      modality: permitted
      actor: operator
      action: start_cell
      condition: precheck_complete
  facts:
    - before_start
    - precheck_complete
```

输出：

- PASS：permission 或 obligation 被规范和事实支持。
- FAIL：claim 要求允许被禁止 action，或规范集合推出 violation。
- GAP：缺少 permission、obligation、condition fact 或 priority rule。
- BOUNDARY_EXCEEDED：claim 要求资源 token、物理可执行性、收益最大化或因果效果。

## 跨 Guard Kernel 集成规则

### Read-only handoff

Guard 之间只允许读取上游 `GuardResult`：

```yaml
handoff:
  upstream_result_ref:
    result_id: result-event-001
    guard: EventGuard
    status: GAP
    read_only: true
  downstream_guard: NormGuard
  allowed_operation: read
  forbidden_operations:
    - mutate_status
    - fill_missing_slots
    - delete_counterexample
    - convert_gap_to_pass
```

### Kernel loop pseudocode

```python
def run_worldguard(contract):
    plan = build_dispatch_plan(contract)
    all_results = []
    aggregate_ledger = []

    for node in topological_order(plan):
        guard_contract = materialize_guard_contract(contract, node, all_results)
        assert upstream_results_are_read_only(guard_contract)
        result = run_guard(node.guard, guard_contract)
        validate_guard_result_shape(result)
        validate_non_pass_has_evidence(result)
        all_results.append(result)
        aggregate_ledger.extend(copy_ledger_entries(result, read_only=True))

    aggregate_status = aggregate_statuses([r.status for r in all_results])
    return GuardedReport(
        status=aggregate_status,
        child_results=all_results,
        aggregate_ledger=aggregate_ledger,
    )
```

### Dependency rules

- EventGuard 输出可作为 NormGuard 的条件事实候选，但若 EventGuard 为 `GAP`，NormGuard 不得假定条件成立。
- NormGuard 输出可阻止 ResourceGuard 的 action 被最终接受，但不能改变 ResourceGuard 的 token enablement 判断。
- SpaceGuard 输出可阻止空间安全 claim，但不能生成 metric geometry。
- CausalGuard 输出可解释因果 claim，但不能从 EventGuard 的时间顺序自动获得结构方程。
- ConflictGuard 输出可描述策略/收益冲突，但不能生成 Deontic Logic 权限。

## ModelMesh 通用模型网格

ModelMesh 是 WorldGuard core 的多模型检查层。它不引入小说、论文、游戏等领域结构字段，而是用通用模型节点和边描述多个世界模型之间的连接。

```text
GuardContract      -> 单个声明、单个模型、七个 Guard 检查
ModelMeshContract  -> 多个模型节点、模型边、权威范围、交接、版本/新鲜度、闭环报告
```

ModelMesh 的核心目标：

- 保留 `GuardContract` 作为 unit-level check，不把单声明合同变重。
- 检查 parent/child、depends_on、refines、replaces、conflicts_with、consumes_output_of、same_world_version、supersedes 等模型关系。
- 记录每个 `ModelNode` 的 `ModelAuthority`：它能判断什么、不能判断什么、作用边界是什么。
- 记录每条 `ModelEdge` 的 handoff contract：谁把什么输出交给谁、允许怎么用、禁止怎么用、是否要求当前证据。
- 检查 stale source、forbidden downstream use、mutable handoff、missing node、dependency cycle 和 authority overreach。
- 生成 `MeshReport`，保留 child `GuardedReport`、child ledgers 和 mesh-level findings。

ModelMesh 不允许的做法：

- 用一个 child model 的 `PASS` 代替 whole-mesh `PASS`。
- 让下游模型补上游模型的 `GAP`。
- 用 stale model 支持 current downstream claim。
- 让一个模型越过自己的 authority 解释别的语义。
- 把 chapter、scene、paragraph、quest 等领域 adapter 字段写入 WorldGuard core schema。

## 燃料电池 toy demo 端到端示例

本 demo 是 toy fixture，用来测试 WorldGuard 的 contract、handoff、ledger、non-PASS preservation 和 route-deliverable closure。它不验证真实燃料电池物理、安全、法规、工程控制、合规、部署或市场效益。

repair-v5 当前 artifact 位置：

- 规格表面：`WorldGuard_TECHNICAL_SPEC.md`
- named block surface：`WorldGuard_TECHNICAL_SPEC.md#repair-v5-named-artifact-blocks`
- `input_story_fragment` file：`evidence/wg-13-fuel-cell-case-repair-v5-artifact/input_story_fragment.yaml`
- `world_model` file：`evidence/wg-13-fuel-cell-case-repair-v5-artifact/world_model.yaml`
- `expected_guard_report` file：`evidence/wg-13-fuel-cell-case-repair-v5-artifact/expected_guard_report.yaml`
- `ledger_outputs` file：`evidence/wg-13-fuel-cell-case-repair-v5-artifact/ledger_outputs.yaml`
- scope note：this artifact child provides inspectable named blocks/files only; executable deliverable checks, final matrix replay, and route-wide blocker closure are owned by the sibling deliverable-check node.

### repair-v5 named artifact blocks

The four named blocks below are the current repair-v5 artifact contract. The stable files named in each block contain the complete YAML payloads and are referenced here so downstream checks can locate them deterministically.

```yaml
input_story_fragment:
  file: evidence/wg-13-fuel-cell-case-repair-v5-artifact/input_story_fragment.yaml
  artifact_version: repair-v5-artifact
  story_id: fuel_cell_company_abc_toy_001
  companies:
    company_a:
      display_name: Company A
      role: prototype_stack_owner
      responsibility: owns prototype hydrogen fuel-cell stack and membrane recipe
    company_b:
      display_name: Company B
      role: validation_bench_operator
      responsibility: operates shared validation bench and requests demo log
    company_c:
      display_name: Company C
      role: independent_safety_compliance_lab
      responsibility: controls precheck and restricted recipe release
  claims:
    - {claim_id: c_run_demo, target_guards: [EventGuard, AgentGuard, SpaceGuard, ResourceGuard, NormGuard]}
    - {claim_id: c_output_voltage, target_guards: [EventGuard, ResourceGuard, CausalGuard]}
    - {claim_id: c_share_full_recipe, target_guards: [AgentGuard, ConflictGuard, NormGuard]}
  scope_limits:
    - toy fixture only
    - no real fuel-cell thermodynamics
    - no legal compliance finding
    - no safety certification
    - no deployment readiness claim
    - no market truth or strategy proof
```

```yaml
world_model:
  file: evidence/wg-13-fuel-cell-case-repair-v5-artifact/world_model.yaml
  artifact_version: repair-v5-artifact
  initial_world_state:
    agents: [CompanyA.lead_engineer, CompanyB.test_operator, CompanyC.safety_auditor]
    lab_spaces: [lab_A_stack_room, lab_B_test_bench, lab_C_review_room, vent_zone]
    resources: [hydrogen_cartridge, prototype_stack, bench_slot, restricted_recipe_file]
    causal_variables: [precheck_complete, cell_running, voltage_output, recipe_disclosed]
    conflict_payoffs:
      - {joint_action: [A_share_full_log, B_accept_full_log, C_block_recipe_release], reward: {CompanyA: -4, CompanyB: 3, CompanyC: -5}}
      - {joint_action: [A_share_redacted_log, B_accept_redacted_log, C_allow_demo], reward: {CompanyA: 2, CompanyB: 2, CompanyC: 3}}
    norms: [n_demo_allowed_after_precheck, n_recipe_forbidden_under_nda, n_company_c_must_block_recipe_release]
  event_line:
    - e_c_precheck
    - e_a_install_stack
    - e_a_start_demo
    - e_voltage_trace
    - e_a_share_full_log
```

```yaml
expected_guard_report:
  file: evidence/wg-13-fuel-cell-case-repair-v5-artifact/expected_guard_report.yaml
  artifact_version: repair-v5-artifact
  aggregate_status: FAIL
  demo_outcome_label: CONTRADICTION
  status_mapping: "CONTRADICTION is represented as canonical FAIL with explicit ConflictGuard and NormGuard contradiction counterexamples."
  guard_results:
    - {guard: EventGuard, input_slice: [event_line, Happens, Initiates, HoldsAt], expected_status: PASS, model_repair_suggestion: none}
    - {guard: AgentGuard, input_slice: [CompanyA_BDI, CompanyB_BDI, CompanyC_BDI], expected_status: PASS, model_repair_suggestion: "do not treat intention as permission"}
    - {guard: SpaceGuard, input_slice: [lab_spaces, rcc8_relations], expected_status: PASS, model_repair_suggestion: "metric safety distance remains outside this demo"}
    - {guard: ResourceGuard, input_slice: [hydrogen_cartridge, prototype_stack, bench_slot, run_demo], expected_status: PASS, model_repair_suggestion: "use resource_missing_key_001 if h2 is removed"}
    - {guard: CausalGuard, input_slice: [causal_variables, causal_equations], expected_status: PASS, model_repair_suggestion: "do not infer physical efficiency or durability"}
    - {guard: ConflictGuard, input_slice: [players_A_B_C, demo_ready, conflict_payoffs], expected_status: FAIL, expected_errors: [CONFLICT_POLICY_CONTRADICTION], model_repair_suggestion: "replace i_share_full_log with share_redacted_log or model a Company C waiver"}
    - {guard: NormGuard, input_slice: [norms, c_precheck_complete, nda_active], expected_status: FAIL, expected_errors: [NORM_FORBIDDEN_ACTION_CONTRADICTION], model_repair_suggestion: "change claim to redacted log or add explicit overriding permission"}
```

```yaml
ledger_outputs:
  file: evidence/wg-13-fuel-cell-case-repair-v5-artifact/ledger_outputs.yaml
  artifact_version: repair-v5-artifact
  ledgers:
    event_ledger: [e_c_precheck, e_a_start_demo, e_voltage_trace]
    agent_ledger: [i_start_demo, i_share_full_log]
    space_ledger: [NTPP_prototype_stack_lab_B_test_bench, DC_lab_B_test_bench_lab_C_review_room]
    resource_ledger: [run_demo_consumes_h2_stack_slot_produces_demo_voltage]
    causal_ledger: [do_run_demo_reaches_cell_running_and_voltage_output]
    conflict_ledger: [CONFLICT_POLICY_CONTRADICTION]
    norm_ledger: [NORM_FORBIDDEN_ACTION_CONTRADICTION]
    counterexample_ledger: [ConflictGuard_payoff_trace, NormGuard_deontic_trace]
    aggregate_ledger: [CONTRADICTION_AS_FAIL]
  artifact_scope_note:
    sibling_deliverable_checks_required: true
    artifact_child_alone_closes_blocker_0004: false
```

### repair-v5 executable deliverable checks

```yaml
deliverable_checks:
  file: evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/closure_evidence.json
  replay_output: evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/replay_output.json
  command: "python tools/check_wg13_repair_v5_deliverables.py --root . --write-output evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/replay_output.json"
  current_scope: repair-v5
  blocker_id: blocker-0004
  closure_status: closed_by_current_repair_v5_deliverable_checks
  packet_independent: true
  active_phase_independent: true
  verifies:
    - input_story_fragment
    - world_model
    - expected_guard_report
    - ledger_outputs
    - all_seven_guard_expected_outputs
    - contradiction_as_fail_status_mapping
    - ledger_outputs_and_counterexamples
    - model_repair_suggestions
    - toy_scope_no_overclaim_boundaries
final_requirement_evidence_matrix:
  file: evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/closure_evidence.json
  rows: [rv5-deliverable-001, rv5-deliverable-002, rv5-deliverable-003, rv5-deliverable-004, rv5-deliverable-005, rv5-deliverable-006]
final_route_wide_gate_ledger:
  file: evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/closure_evidence.json
  gate_ledger_id: frwgl-wg13-rv5-001
  blocker_id: blocker-0004
  closure_status: closed_by_current_repair_v5_deliverable_checks
terminal_backward_replay:
  file: evidence/wg-13-fuel-cell-case-repair-v5-deliverable-checks/closure_evidence.json
  replay_id: terminal_backward_replay_wg13_repair_v5_001
  result: pass
```

### repair-v4 scenario evidence

该场景包含三家公司、实验室空间、资源、因果变量、冲突收益和规范：

```yaml
input_story_fragment:
  story_id: fuel_cell_company_abc_toy_001
  companies:
    Company A: "prototype hydrogen fuel-cell stack owner; owns the membrane recipe"
    Company B: "shared validation bench operator; wants a customer-facing demo log"
    Company C: "independent safety/compliance lab; controls restricted recipe release"
  claims:
    - claim_id: c_run_demo
      text: "Company A can run the prototype fuel-cell demo on Company B's bench after Company C's precheck."
      target_guards: [EventGuard, AgentGuard, SpaceGuard, ResourceGuard, NormGuard]
    - claim_id: c_output_voltage
      text: "If the demo run starts in the toy model, the observed voltage output becomes available."
      target_guards: [EventGuard, ResourceGuard, CausalGuard]
    - claim_id: c_share_full_recipe
      text: "Company A may share the full membrane recipe with Company B as part of the demo log."
      target_guards: [AgentGuard, ConflictGuard, NormGuard]
  scope_limits:
    - "toy fixture only"
    - "no real fuel-cell thermodynamics"
    - "no legal, safety, compliance, deployment, or market validation"
```

Initial WorldState:

```yaml
initial_world_state:
  time: t0
  agents:
    CompanyA.lead_engineer:
      beliefs: [c_precheck_complete, stack_ready, nda_active]
      desires: [show_voltage_output, protect_membrane_recipe]
      capabilities: [install_stack, start_demo, share_redacted_log]
      intentions: [i_install_stack, i_start_demo, i_share_full_log]
    CompanyB.test_operator:
      beliefs: [bench_available, expects_demo_log]
      desires: [receive_complete_demo_log]
      capabilities: [operate_bench]
    CompanyC.safety_auditor:
      beliefs: [nda_active, precheck_required]
      desires: [prevent_recipe_leak, allow_safe_demo]
      capabilities: [approve_precheck, block_recipe_release]
  lab_spaces:
    lab_A_stack_room: "Company A assembly room"
    lab_B_test_bench: "Company B shared validation bench"
    lab_C_review_room: "Company C review room"
    vent_zone: "Shared vented test zone"
  rcc8_relations:
    - {at: t0, x: prototype_stack, y: lab_A_stack_room, relation: NTPP}
    - {at: t1, x: prototype_stack, y: lab_B_test_bench, relation: NTPP}
    - {at: t1, x: lab_B_test_bench, y: vent_zone, relation: EC}
    - {at: t1, x: lab_B_test_bench, y: lab_C_review_room, relation: DC}
  resources:
    places:
      hydrogen_cartridge: [{color: h2, qty: 1}]
      prototype_stack: [{color: stack, qty: 1}]
      bench_slot: [{color: slot, qty: 1}]
      restricted_recipe_file: [{color: secret_recipe, qty: 1}]
    transitions:
      - id: run_demo
        consumes:
          - {place: hydrogen_cartridge, color: h2, qty: 1}
          - {place: prototype_stack, color: stack, qty: 1}
          - {place: bench_slot, color: slot, qty: 1}
        produces:
          - {place: voltage_trace, color: demo_voltage, qty: 1}
  causal_variables: [precheck_complete, cell_running, voltage_output, recipe_disclosed]
  causal_equations:
    cell_running: "f(precheck_complete, run_demo)"
    voltage_output: "g(cell_running)"
    recipe_disclosed: "h(share_full_log)"
  conflict_payoffs:
    - state: demo_ready
      joint_action: [A_share_full_log, B_accept_full_log, C_block_recipe_release]
      reward: {CompanyA: -4, CompanyB: 3, CompanyC: -5}
    - state: demo_ready
      joint_action: [A_share_redacted_log, B_accept_redacted_log, C_allow_demo]
      reward: {CompanyA: 2, CompanyB: 2, CompanyC: 3}
  norms:
    - id: n_demo_allowed_after_precheck
      modality: permitted
      actor: CompanyA.lead_engineer
      action: start_demo
      condition: c_precheck_complete
    - id: n_recipe_forbidden_under_nda
      modality: forbidden
      actor: CompanyA.lead_engineer
      action: share_membrane_recipe
      condition: nda_active
    - id: n_company_c_must_block_recipe_release
      modality: obligatory
      actor: CompanyC.safety_auditor
      action: block_recipe_release
      condition: nda_active
```

Event line:

```yaml
event_line:
  - {event_id: e_c_precheck, at: t0, actor: CompanyC.safety_auditor, initiates: c_precheck_complete}
  - {event_id: e_a_install_stack, at: t1, actor: CompanyA.lead_engineer, initiates: stack_installed_on_bench}
  - {event_id: e_a_start_demo, at: t2, actor: CompanyA.lead_engineer, initiates: cell_running}
  - {event_id: e_voltage_trace, at: t3, actor: bench_sensor, initiates: voltage_output_available}
  - {event_id: e_a_share_full_log, at: t4, actor: CompanyA.lead_engineer, initiates: membrane_recipe_disclosed_to_B}
```

### repair-v4 integrated WorldGuard check

`CONTRADICTION` is preserved as a demo outcome label and mapped into the canonical `GuardStatus.FAIL` enum with explicit contradiction counterexamples. `BOUNDARY_EXCEEDED` remains reserved for formal ownership boundaries.

| Guard | input slice | status | counterexample or ledger reference | model repair suggestion |
|---|---|---|---|---|
| EventGuard | event line `e_c_precheck` through `e_a_share_full_log`; `Happens`, `Initiates`, `HoldsAt` | PASS | `event_ledger`: precheck, start demo, voltage trace, and recipe disclosure events are supported | none for event support; keep event facts read-only |
| AgentGuard | Company A/B/C BDI states, capabilities, intentions | PASS | `agent_ledger`: referenced intentions have declared BDI slots | none for BDI completeness; do not treat intention as permission |
| SpaceGuard | `lab_A_stack_room`, `lab_B_test_bench`, `lab_C_review_room`, `vent_zone`, RCC8 relations | PASS | `space_ledger`: RCC8 relations are jointly satisfiable | none for RCC8; metric safety distance remains outside demo |
| ResourceGuard | `hydrogen_cartridge`, `prototype_stack`, `bench_slot`, `run_demo` transition | PASS | `resource_ledger`: `run_demo` consumes h2, stack, slot and produces demo voltage | none for `run_demo`; use `resource_missing_key_001` if h2 is removed |
| CausalGuard | SCM variables `precheck_complete`, `cell_running`, `voltage_output`, `recipe_disclosed` | PASS | `causal_ledger`: `do(run_demo=true)` reaches `cell_running` and `voltage_output` | do not infer physical efficiency or durability |
| ConflictGuard | players A/B/C, demo_ready state, full-log vs redacted-log actions, payoff table | FAIL with CONTRADICTION semantics | minimal trace: full-log joint action gives Company C reward -5 while redacted-log action gives 3 | replace `i_share_full_log` with `share_redacted_log` or add a modeled C waiver |
| NormGuard | permission to start demo, NDA prohibition on recipe sharing, C obligation to block release | FAIL with CONTRADICTION semantics | minimal trace: `nda_active` plus `n_recipe_forbidden_under_nda` derives `F_A(share_membrane_recipe)` while claim asserts permission | change claim to redacted log or add explicit overriding permission with priority |

Integrated output:

```yaml
integrated_worldguard_check:
  check_id: wg13_repair_v4_integrated_check_001
  aggregate_status: FAIL
  demo_outcome_label: CONTRADICTION
  status_mapping: "CONTRADICTION is represented as aggregate FAIL with explicit ConflictGuard and NormGuard contradiction counterexamples."
  per_guard_status:
    EventGuard: PASS
    AgentGuard: PASS
    SpaceGuard: PASS
    ResourceGuard: PASS
    CausalGuard: PASS
    ConflictGuard: FAIL
    NormGuard: FAIL
  minimal_counterexamples:
    - "ConflictGuard payoff trace: Company C blocks full recipe release because full-log sharing conflicts with its payoff-preserving policy."
    - "NormGuard deontic trace: NDA forbids sharing the membrane recipe while the claim asserts permission."
  model_repair_suggestions:
    - "Replace c_share_full_recipe with c_share_redacted_log."
    - "Or add explicit Company C waiver and priority rule before asserting recipe sharing permission."
    - "Keep start_demo and voltage_output claims separate from recipe-sharing contradiction."
```

Ledger outputs:

```yaml
ledger_outputs:
  event_ledger:
    - {claim_id: c_run_demo, event: e_a_start_demo, fluent: cell_running, status_impact: supports_pass}
  agent_ledger:
    - {claim_id: c_share_full_recipe, intention: i_share_full_log, status_impact: informational}
  space_ledger:
    - {claim_id: c_run_demo, relation: "NTPP(prototype_stack,lab_B_test_bench,t1)", status_impact: supports_pass}
  resource_ledger:
    - {claim_id: c_output_voltage, transition: run_demo, status_impact: supports_pass}
  causal_ledger:
    - {claim_id: c_output_voltage, query: "do(run_demo=true)", status_impact: supports_pass}
  conflict_ledger:
    - {claim_id: c_share_full_recipe, error: CONFLICT_POLICY_CONTRADICTION, status_impact: supports_fail}
  norm_ledger:
    - {claim_id: c_share_full_recipe, norm: n_recipe_forbidden_under_nda, status_impact: supports_fail}
  counterexample_ledger:
    - {guard: ConflictGuard, trace: [full_log_reward_for_C=-5, redacted_log_reward_for_C=3]}
    - {guard: NormGuard, trace: [nda_active, "F_A(share_membrane_recipe)", "claim P_A(share_membrane_recipe)"]}
  aggregate_ledger:
    - {check_id: wg13_repair_v4_integrated_check_001, aggregate_status: FAIL, demo_outcome_label: CONTRADICTION}
```

### repair-v4 route deliverable evidence

The route-deliverable evidence is current repair-v4 evidence and is replayable without FlowPilot packet identity, active packet state, one-time runtime phase, or manually remembered runtime context.

```yaml
route_deliverable_checks:
  evidence_id: wg13_repair_v4_evidence_20260613
  replay_command: "python tools/check_wg13_repair_v4.py --evidence evidence/wg-13-fuel-cell-case-repair-v4/repair_v4_evidence.json --spec WorldGuard_TECHNICAL_SPEC.md"
  checks:
    - {check_id: rdc-001, criterion: "A/B/C WorldState, event line, lab spaces, resources, causal variables, conflict payoffs, norms", status: pass}
    - {check_id: rdc-002, criterion: "all seven Guards have concrete input slices and outputs", status: pass}
    - {check_id: rdc-003, criterion: "integrated check preserves PASS/FAIL/GAP/CONTRADICTION semantics", status: pass}
    - {check_id: rdc-004, criterion: "replay does not depend on FlowPilot packet identity or active runtime phase", status: pass}
    - {check_id: rdc-005, criterion: "final_requirement_evidence_matrix exists", status: pass}
    - {check_id: rdc-006, criterion: "final_route_wide_gate_ledger exists and references blocker-0003 closure", status: pass}
    - {check_id: rdc-007, criterion: "terminal backward replay exists and composes to final closure", status: pass}
    - {check_id: rdc-008, criterion: "toy-fixture boundaries reject real-world overclaiming", status: pass}
```

```yaml
final_requirement_evidence_matrix:
  - requirement_id: fuel-cell-rv4-001
    requirement: "Concrete A/B/C scenario WorldState and event line"
    evidence: [initial_world_state, event_line, "WorldGuard_TECHNICAL_SPEC.md#repair-v4-scenario-evidence"]
    status: pass
  - requirement_id: fuel-cell-rv4-002
    requirement: "All seven Guard instantiations"
    evidence: [guard_instantiation_matrix, "WorldGuard_TECHNICAL_SPEC.md#repair-v4-integrated-worldguard-check"]
    status: pass
  - requirement_id: fuel-cell-rv4-003
    requirement: "Integrated status, counterexamples, and repair suggestions"
    evidence: [integrated_worldguard_check]
    status: pass
  - requirement_id: fuel-cell-rv4-004
    requirement: "Replayable route-deliverable checks without packet dependency"
    evidence: [route_deliverable_checks, "tools/check_wg13_repair_v4.py"]
    status: pass
  - requirement_id: fuel-cell-rv4-005
    requirement: "Final route gate evidence and terminal backward replay"
    evidence: [final_route_wide_gate_ledger, terminal_backward_replay]
    status: pass
  - requirement_id: fuel-cell-rv4-006
    requirement: "Toy-scope boundaries"
    evidence: [input_story_fragment.scope_limits, rdc-008]
    status: pass
```

```yaml
final_route_wide_gate_ledger:
  - gate_ledger_id: frwgl-wg13-rv4-001
    blocker_id: blocker-0003
    gate: route_deliverable_checks_missing
    current_repair_evidence: wg13_repair_v4_evidence_20260613
    closure_status: unblocked_by_current_repair_v4_evidence
    required_artifacts_present:
      - route_deliverable_checks
      - final_requirement_evidence_matrix
      - final_route_wide_gate_ledger
      - terminal_backward_replay
    no_stale_packet_dependency: true
```

```yaml
terminal_backward_replay:
  replay_id: terminal_backward_replay_wg13_repair_v4_001
  result: pass
  steps:
    - {step: "final acceptance requires fuel-cell demo deliverable checks", status: pass}
    - {step: "route-wide gate ledger marks blocker-0003 unblocked by current evidence", status: pass}
    - {step: "requirement matrix links all repair requirements to evidence ids and file locations", status: pass}
    - {step: "scenario and seven-Guard matrix provide concrete current evidence", status: pass}
    - {step: "final artifact surface contains repair-v4 headings", status: pass}
    - {step: "scope limits reject real-world physics/legal/safety/compliance claims", status: pass}
```

### Handoff behavior

If the `hydrogen_cartridge` `h2` token is removed, ResourceGuard must output `GAP`, even though EventGuard still supports `cell_running` in the event line:

```yaml
expected_non_pass:
  guard: ResourceGuard
  status: GAP
  errors: [RESOURCE_MISSING_TOKEN]
  counterexample:
    missing_slots:
      - transition: run_demo
        place: hydrogen_cartridge
        color: h2
        required_qty: 1
        available_qty: 0
```

Kernel must not let EventGuard's `cell_running` PASS repair ResourceGuard's missing token, and must not let AgentGuard's `i_share_full_log` intention override NormGuard's forbidden recipe-sharing result.

## 测试设计

所有测试 fixture 使用同一 schema：

```yaml
test_case:
  test_id: string
  guard: string
  input_model: map
  expected_status: PASS | FAIL | GAP | BOUNDARY_EXCEEDED
  expected_errors: list[string]
  expected_counterexample: map
  notes: string
```

### Per-Guard coverage matrix

| Guard | PASS | FAIL | GAP | BOUNDARY_EXCEEDED |
|---|---|---|---|---|
| EventGuard | event_pass_persistence_001 | event_exclusive_fluent_fail_001 | event_missing_initiation_gap_001 | event_boundary_exceeded_numeric_dynamics_001 |
| AgentGuard | agent_pass_bdi_intention_001 | agent_conflicting_intentions_fail_001 | agent_missing_belief_gap_001 | agent_boundary_exceeded_causal_payoff_001 |
| SpaceGuard | space_pass_rcc8_transition_001 | space_rcc8_contradiction_fail_001 | space_missing_relation_gap_001 | space_boundary_exceeded_metric_distance_001 |
| ResourceGuard | resource_pass_token_flow_001 | resource_capacity_overflow_fail_001 | resource_missing_key_001 | resource_boundary_exceeded_norm_authorization_001 |
| CausalGuard | causal_pass_do_query_001 | causal_cycle_fail_001 | causal_missing_equation_001 | causal_boundary_exceeded_temporal_story_001 |
| ConflictGuard | conflict_pass_policy_equilibrium_001 | conflict_invalid_probability_fail_001 | conflict_payoff_mismatch_001 | conflict_boundary_exceeded_deontic_obligation_001 |
| NormGuard | norm_pass_permission_001 | norm_forbidden_action_fail_001 | norm_missing_permission_001 | norm_boundary_exceeded_physical_enablement_001 |

### Required ResourceGuard missing-key example

```yaml
test_id: resource_missing_key_001
guard: ResourceGuard
input_model:
  places:
    hydrogen_tank:
      - color: h2
        qty: 0
  transition:
    id: run_cell
    consumes:
      - place: hydrogen_tank
        color: h2
        qty: 1
    produces:
      - place: electricity_bus
        color: kwh
        qty: 1
  claim:
    enabled: run_cell
expected_status: GAP
expected_errors: [RESOURCE_MISSING_TOKEN]
expected_counterexample:
  missing_slots:
    - transition: run_cell
      place: hydrogen_tank
      color: h2
      required_qty: 1
      available_qty: 0
notes: "gap_ledger records the missing colored token/key; no model component may infer fuel from desired output."
```

### Comparable non-PASS examples

```yaml
non_pass_examples:
  - test_id: event_missing_initiation_gap_001
    guard: EventGuard
    expected_status: GAP
    expected_errors: [EVENT_MISSING_INITIATION_AXIOM]
    expected_counterexample: {missing_slots: [{fluent: purge_complete, needed: "initiates(event,purge_complete,t)"}]}
    notes: "Observation alone is not Event Calculus support."
  - test_id: agent_missing_belief_gap_001
    guard: AgentGuard
    expected_status: GAP
    expected_errors: [AGENT_MISSING_BELIEF]
    expected_counterexample: {missing_slots: [{belief: b_purge_authorized}]}
    notes: "BDI runner cannot synthesize authorization belief."
  - test_id: space_boundary_exceeded_metric_distance_001
    guard: SpaceGuard
    expected_status: BOUNDARY_EXCEEDED
    expected_errors: [SPACE_BOUNDARY_METRIC_GEOMETRY]
    expected_counterexample: {boundary_trace: [{claim_part: distance_meters, owner: metric_geometry}]}
    notes: "RCC8 topology does not validate metric distance."
  - test_id: causal_missing_equation_001
    guard: CausalGuard
    expected_status: GAP
    expected_errors: [CAUSAL_MISSING_STRUCTURAL_EQUATION]
    expected_counterexample: {missing_slots: [{variable: degradation, needed: structural_equation}]}
    notes: "Graph edge alone is insufficient."
  - test_id: conflict_payoff_mismatch_001
    guard: ConflictGuard
    expected_status: GAP
    expected_errors: [CONFLICT_MISSING_PAYOFF]
    expected_counterexample: {missing_slots: [{state: s0, joint_action: [shield, attack], needed: payoff_vector}]}
    notes: "Best response requires payoff evidence."
  - test_id: norm_missing_permission_001
    guard: NormGuard
    expected_status: GAP
    expected_errors: [NORM_MISSING_PERMISSION]
    expected_counterexample: {missing_slots: [{actor: operator, action: vent_hydrogen, needed: permission_or_obligation}]}
    notes: "Silence is not permission unless explicitly modeled."
```

### Cross-Guard tests

```yaml
cross_guard_tests:
  - test_id: cross_event_to_norm_readonly_gap_001
    guard: CrossGuardKernel
    input_model:
      upstream:
        guard: EventGuard
        status: GAP
        error: EVENT_MISSING_INITIATION_AXIOM
      downstream:
        guard: NormGuard
        reads: [purge_complete]
    expected_status: GAP
    expected_errors: [KERNEL_PROPAGATES_UPSTREAM_GAP, EVENT_MISSING_INITIATION_AXIOM]
    expected_counterexample:
      trace:
        - EventGuard: "missing initiates(event,purge_complete,t)"
        - Kernel: "no silent repair"
    notes: "NormGuard cannot fill EventGuard missing axiom."
  - test_id: cross_norm_to_resource_forbidden_fail_001
    guard: CrossGuardKernel
    input_model:
      upstream:
        guard: NormGuard
        status: FAIL
        error: NORM_FORBIDDEN_ACTION
      downstream:
        guard: ResourceGuard
        token_enabled: true
    expected_status: FAIL
    expected_errors: [KERNEL_PRESERVES_FORBIDDEN_ACTION, NORM_FORBIDDEN_ACTION]
    expected_counterexample:
      trace:
        - NormGuard: "F(operator, vent_hydrogen)"
        - ResourceGuard: "transition token-enabled"
        - Kernel: "aggregate remains FAIL"
    notes: "Resource enablement cannot override forbidden norm."
  - test_id: cross_all_guard_mixed_aggregate_001
    guard: CrossGuardKernel
    input_model:
      outputs:
        - {guard: EventGuard, status: PASS}
        - {guard: AgentGuard, status: PASS}
        - {guard: SpaceGuard, status: BOUNDARY_EXCEEDED, error: SPACE_BOUNDARY_METRIC_GEOMETRY}
        - {guard: ResourceGuard, status: GAP, error: RESOURCE_MISSING_TOKEN}
        - {guard: CausalGuard, status: PASS}
        - {guard: ConflictGuard, status: FAIL, error: CONFLICT_INVALID_TRANSITION_PROBABILITY}
        - {guard: NormGuard, status: PASS}
    expected_status: FAIL
    expected_errors:
      - CONFLICT_INVALID_TRANSITION_PROBABILITY
      - RESOURCE_MISSING_TOKEN
      - SPACE_BOUNDARY_METRIC_GEOMETRY
    expected_counterexample:
      trace:
        - "ConflictGuard FAIL dominates final acceptance"
        - "ResourceGuard GAP and SpaceGuard boundary remain visible"
    notes: "Aggregate ledger must not collapse side conditions."
```

## GitHub 仓库蓝图与 MVP 实施路线

### Repository layout

```text
worldguard/
  pyproject.toml
  README.md
  docs/
    WorldGuard_TECHNICAL_SPEC.md
    examples/
      fuel_cell_toy.md
  worldguard/
    __init__.py
    contracts.py
    ledgers.py
    kernel.py
    guards/
      event_guard.py
      agent_guard.py
      space_guard.py
      resource_guard.py
      causal_guard.py
      conflict_guard.py
      norm_guard.py
  examples/
    fuel_cell/
      input_story_fragment.yaml
      world_model.yaml
      expected_guard_report.yaml
      ledger_outputs.yaml
  tests/
    guards/
      test_event_guard.py
      test_agent_guard.py
      test_space_guard.py
      test_resource_guard.py
      test_causal_guard.py
      test_conflict_guard.py
      test_norm_guard.py
    test_kernel_handoff.py
    test_fuel_cell_demo.py
    fixtures/
      per_guard/
      cross_guard/
```

### MVP route

1. Contract and ledger spine
   - Implement typed schemas for `GuardContract`, `GuardResult`, `Counterexample`, `LedgerEntry`.
   - Validate serialization, stable ids, required fields, non-PASS evidence.

2. Seven minimal Guard runners
   - Implement one local runner per Guard.
   - Each runner must produce all four statuses under tests.
   - Mathematical backbone must be explicit in code and docs.

3. Kernel orchestration
   - Implement dispatch plan, dependency ordering, read-only handoff, result aggregation.
   - Preserve child ledgers and counterexamples in aggregate report.

4. Fixtures and demo
   - Add per-Guard fixtures, cross-Guard fixtures, fuel-cell toy demo files.
   - Add expected report comparison.

5. Validation and release gate
   - Run schema tests, unit tests, cross-Guard tests, demo replay, acceptance matrix review.

### Minimum validation commands

```bash
python -m pytest tests/guards
python -m pytest tests/test_kernel_handoff.py
python -m pytest tests/test_fuel_cell_demo.py
python -m worldguard.examples.fuel_cell --check
```

The exact CLI may change during implementation, but MVP acceptance must retain equivalent validation gates.

## 禁止做法、常见错误与最终接受标准

### prohibited_approaches

以下做法是硬性不接受条件：

1. 用 story、自然语言总结或 chain-of-thought 替代模型、ledger、反例。
2. 用通用 prompt checklist 替代七个 Guard 的形式系统。
3. 从 toy demo 声称真实法律、合规、安全、燃料电池物理、市场或工程可靠性成立。
4. 静默修复缺失事件、信念、空间关系、token、结构方程、payoff 或 permission。
5. 用单一 Guard 的 PASS 替代其他 Guard 的判断。
6. 删除、合并或隐藏 ledgers。
7. 混用 Guard 语义，例如把 deontic obligation 当作 payoff。
8. 缺失证据时输出 unsupported PASS。
9. 非 PASS 没有 counterexample、missing slot 或 boundary trace。
10. 用文档润色替代接受证据。

### common_errors

| error_id | symptom | affected boundary | likely cause | required correction |
|---|---|---|---|---|
| common-001 narrative_pass | 只有“合理”说明，没有 GuardResult | all Guards | 模型优先退化成写作评审 | 补 GuardContract、GuardResult、ledger、counterexample |
| common-002 gap_as_fail | 缺输入被写成 FAIL | status semantics | 混淆缺证据与反例 | 改为 GAP 并列 missing_slots |
| common-003 boundary_as_fail | 越界被写成 FAIL | Guard ownership | 未标注 owner | 改为 BOUNDARY_EXCEEDED |
| common-004 hidden_repair | 输入缺失但结果 PASS | per-Guard contracts | runner 默认补全 | 禁止补槽，新增 missing-slot fixture |
| common-005 ledger_flattening | aggregate 只有最终结论 | Kernel aggregation | 为简洁丢证据 | 保留 source ledger ids |
| common-006 cross_guard_write | 下游修改上游输出 | handoff | 缺 read-only enforcement | 上游结果设为只读 |
| common-007 toy_overclaim | demo 被当现实验证 | demo scope | 混淆 fixture 与现实 | 加 toy scope limitation |
| common-008 missing_negative_tests | 只有 PASS 样例 | test design | happy path 偏差 | 每个 Guard 加 FAIL/GAP/BOUNDARY |
| common-009 unstable_ids | 没有稳定 claim/test/ledger id | fixtures | 仅写 prose | 使用稳定 id |
| common-010 semantics_optional | 数学 backbone 变成建议 | Guard specs | 把 Guard 当标签 | acceptance 要求形式系统 |

### final_mvp_checklist

- Contracts: `GuardContract`、`GuardResult`、`GuardStatus`、`GuardError`、`Counterexample`、`LedgerEntry`。
- Guard modules: 七个 Guard 均有 runner、边界检查和四状态输出。
- Mathematical backbones: EC、BDI、RCC8、CPN、SCM、stochastic/Markov games、Deontic Logic。
- Ledgers: per-Guard ledger、error、gap、boundary、counterexample、aggregate。
- Kernel loop: dispatch、read-only handoff、aggregation、non-PASS preservation。
- Fixtures: 每个 Guard 的 PASS/FAIL/GAP/BOUNDARY_EXCEEDED。
- Cross-Guard tests: upstream-to-downstream gap/fail/boundary/counterexample propagation。
- Demo assets: fuel-cell toy YAML files with expected report and ledgers。
- Validation gates: schema validation、unit tests、fixture replay、ledger completeness。
- Documentation: scope limits、prohibitions、common errors、MVP route、acceptance matrix。

### top_three_development_tasks

1. Build contracts and ledger spine  
   Deliverables: typed schemas, stable ids, validation errors, serialization tests.

2. Implement seven minimal Guard runners  
   Deliverables: runner per Guard, four-status fixtures, stable error codes, counterexamples.

3. Implement Kernel orchestration and demo replay  
   Deliverables: read-only handoff, aggregate report, fuel-cell replay, cross-Guard tests.

### five_easiest_failure_points

1. Boundary flattening: detect with boundary_ledger and owner checks.
2. Hidden input completion: detect by comparing consumed model to original input_model.
3. Ledger loss during aggregation: detect by child ledger to aggregate ledger parity checks.
4. Toy demo overclaim: detect by scope-limit search and review.
5. Generic prompt drift: detect by requiring mathematical backbone and structured fixture per Guard.

### acceptance_standard_coverage_matrix

| id | requirement text | evidence location | pass condition | reviewer check |
|---|---|---|---|---|
| acceptance-001 | WorldGuard must be model-first, not prose-first. | overview, contracts, prohibited approaches | Every accepted claim links to model input, GuardResult, ledger, or fixture. | Trace PASS and non-PASS claims to structured evidence. |
| acceptance-002 | Seven Guard backbones must remain explicit. | guard specs, MVP checklist | EC, BDI, RCC8, CPN, SCM, game model, Deontic Logic are named and used. | Verify no Guard is a generic prompt checklist. |
| acceptance-003 | Unified GuardContract must be stable. | contracts | Required fields and versioning serve all Guards. | Validate sample contracts for all seven Guards. |
| acceptance-004 | GuardResult must distinguish PASS, FAIL, GAP, BOUNDARY_EXCEEDED. | contracts, tests | Non-PASS statuses are not collapsed. | Inspect per-Guard fixtures and aggregation output. |
| acceptance-005 | Ledgers must be complete and inspectable. | ledger model | Source ids and channels preserve evidence. | Confirm each non-PASS fixture writes ledger entries. |
| acceptance-006 | Counterexamples must be concrete or explicitly absent with reason. | test design | FAIL/GAP/BOUNDARY include trace, missing_slots, or boundary_trace. | Reject vague narrative counterexamples. |
| acceptance-007 | EventGuard must test event/fluent support only. | EventGuard section | Event persistence, contradiction, missing initiation, boundary cases behave as specified. | Review EventGuard fixture group. |
| acceptance-008 | AgentGuard must preserve BDI semantics. | AgentGuard section | Belief/desire/intention/capability gaps and conflicts are visible. | Check missing belief and boundary tests. |
| acceptance-009 | SpaceGuard must preserve RCC8 qualitative scope. | SpaceGuard section | RCC8 consistency and missing relation are tested; metric claims remain boundary. | Inspect RCC8 and metric-boundary fixtures. |
| acceptance-010 | ResourceGuard must preserve Colored Petri Net token semantics. | ResourceGuard section | resource_missing_key_001 is present and concrete. | Verify missing token stays GAP. |
| acceptance-011 | CausalGuard must preserve SCM requirements. | CausalGuard section | Missing equations, cycles, invalid temporal causation are caught. | Inspect SCM equation and cycle counterexamples. |
| acceptance-012 | ConflictGuard must preserve stochastic/Markov game requirements. | ConflictGuard section | Payoff, policy, player, action, probability obligations are tested. | Verify payoff gap and probability failure. |
| acceptance-013 | NormGuard must preserve Deontic Logic requirements. | NormGuard section | Permission, obligation, forbidden action, and norm/resource boundary are tested. | Verify missing permission and forbidden action. |
| acceptance-014 | Kernel handoff must be read-only. | kernel integration, cross-Guard tests | Downstream Guards cannot repair or relabel upstream outputs. | Inspect Event-to-Norm and Norm-to-Resource cases. |
| acceptance-015 | Kernel aggregation must preserve blockers, gaps, boundaries, counterexamples. | kernel integration | Aggregate report includes all unresolved side conditions. | Compare child ledgers to aggregate ledger. |
| acceptance-016 | Fuel-cell demo must remain a toy fixture replay. | demo section | Demo validates schema/handoff/replay only. | Search for unbounded real-world claims. |
| acceptance-017 | Repository MVP must include schemas, runners, fixtures, demo assets, validation gates. | repository blueprint | Checklist items are present and actionable. | Map checklist to module/test areas. |
| acceptance-018 | Development route must be ordered and evidence-tied. | top three tasks | Contracts -> Guard runners -> Kernel/demo replay. | Ensure later tasks depend on prior contracts. |
| acceptance-019 | Prohibited approaches are hard rejection criteria. | prohibited_approaches | Narrative substitution, prompt substitution, hidden repair, overclaiming, ledger loss, unsupported PASS are rejected. | Treat occurrence as non-acceptance. |
| acceptance-020 | Final acceptance cannot be satisfied by polish alone. | this matrix and gates | Every row has concrete evidence location and pass condition. | Reject rows backed only by prose summary. |

## Final closure statement

WorldGuard 的最终接受条件是：模型、契约、Guard 运行、ledger、反例、测试和接受矩阵均能互相追踪；七个 Guard 的数学边界不被削弱；Kernel 只调度与聚合，不修复；toy demo 不越界声称真实世界有效性。任何 narrative-only、prompt-only、ledger-less、counterexample-less 或 unsupported PASS 的版本都不属于可接受的 WorldGuard MVP。
