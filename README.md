# WorldGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="WorldGuard concept hero showing contracts flowing through guard checks into model mesh closure" width="100%" />
</p>

<p align="center">
  <strong>A model-first guard framework for auditable world-claim checks.</strong>
</p>
<!-- README HERO END -->

**Package:** `worldguard`<br>
**Release type:** source-only Python package and Codex skill workflow

The source version does not by itself assert a tag, hosted GitHub Release, or
installed-consumer identity; those require separate current evidence.

WorldGuard checks whether a claim about a modeled world is supported, contradicted, missing required inputs, or outside the declared model boundary. It is built for workflows where an AI assistant, developer, or reviewer needs structured evidence instead of a narrative-only answer.

English comes first; a Chinese mirror follows below.

## Development and installation checks

WorldGuard uses ordinary native checks and pytest. No author-supervision tool or compiled author contract is needed. The living `.flowguard/map.json` binds source, tests, and the executable models; `python -m flowguard map models` runs them.

```bash
python -m pytest -q
python -m worldguard.guard_model_contract
```

Portable consumers run `python /path/to/worldguard/scripts/run_worldguard.py check --help`; no Python distribution metadata is required.

## What It Does

WorldGuard provides two core check shapes:

- `GuardContract`: checks one claim against one explicit world model.
- `ModelMeshContract`: checks multiple model nodes, authority boundaries, read-only handoffs, source freshness, dependency cycles, and child ledger preservation.

The runtime returns four statuses without collapsing them:

- `PASS`: the declared model supports the requested claim.
- `FAIL`: the declared model contradicts the claim.
- `GAP`: required model inputs are missing.
- `BOUNDARY_EXCEEDED`: the claim asks the model to support semantics it does not own.

## Guard Families

WorldGuard currently includes these guard families:

- `EventGuard`: event and trace support.
- `AgentGuard`: agent beliefs, capabilities, desires, and intentions.
- `SpaceGuard`: spatial relation checks.
- `ResourceGuard`: resource, place, token, transition, and capacity checks.
- `CausalGuard`: structural causal support.
- `ConflictGuard`: conflicting incentives or payoff-policy contradictions.
- `NormGuard`: permission, obligation, and prohibition checks.

## ModelMesh

`ModelMeshContract` is the generic connection layer above unit guard checks. It is designed to prevent a locally valid model from being used as proof for a larger system when the connection is not justified.

It checks:

- model authority: each node can only support the semantics it owns;
- handoffs: downstream nodes may read upstream evidence but cannot mutate it;
- `allowed_use` and `forbidden_use`: outputs must stay inside declared use boundaries;
- freshness: stale or unknown sources cannot support current downstream claims when current evidence is required;
- cycles: dependency loops are reported as mesh failures;
- evidence preservation: child reports, ledgers, gaps, and counterexamples survive aggregation.

## Task-local fact revision

WorldGuard can now preview and activate an explicit fact-support revision without
turning the result into a new global database or a new Guard. Positive and
negative support remain independent, so one fact can be `true`, `false`, `both`,
or `neither`. A contradiction stays visible and does not make unrelated facts
true.

The preview is immutable and recalculates strict-rule closure after additions or
retractions. Activation then requires the exact preview fingerprint, preserved
facts, explicit contradiction acknowledgement, and current regression plus
holdout evidence. A stale base, missing evidence, or repeated transaction id
blocks visibly.

Fact activation is deliberately not task closure. A successful activation
returns `task_local_revalidation_required` and hands the exact candidate back
to the same task-local prediction owner for current native depth, original
scenario, and independent real-holdout checks.

## Task-local predictive revision

Every prediction names one task and purpose, a coverage universe, explicit
assumptions and unknowns, and its predecessor; later iterations name the exact
prior gap ids. WorldGuard computes the coverage and gap fingerprints itself.
`task-model revision` runs the candidate mesh once and takes the state,
transition, branch, perturbation, intervention, counterfactual, and holdout gaps
from that run rather than from a caller-authored gap list.

Closing a candidate needs one original scenario and one genuinely independent
holdout observation; a renamed copy of the same observation is caught by its
content. WorldGuard
computes resolved, persisted, and introduced gaps itself; unchanged evidence
stalls, a finite iteration limit blocks, and missing external evidence must name
the exact gaps, owner, reason, and affected claims.

## Quick Start

```powershell
python -m pip install -e .
python -m pytest
python -m worldguard.examples.fuel_cell --check
python -m worldguard.cli check --example fuel_cell
python -m worldguard.cli mesh-check --mesh examples/model_mesh/basic_mesh.yaml
python -m worldguard.cli task-model fact-revision-preview base.json transaction.json
python -m worldguard.cli task-model fact-revision-activate base.json transaction.json activation.json
```

If your Python scripts directory is on `PATH`, the console entry point is also available:

```powershell
worldguard check --example fuel_cell
```

## Python API

```python
from worldguard import GuardContract, ModelMeshContract, run_worldguard, run_model_mesh

contract = GuardContract.from_dict({...})
report = run_worldguard(contract)

mesh = ModelMeshContract.from_dict({...})
mesh_report = run_model_mesh(mesh)
```

## Codex Skill

The repository includes the WorldGuard skill under `skills/worldguard/`. It explains how to write a world model and run it with the portable launcher `skills/worldguard/scripts/run_worldguard.py`, and how to report non-pass results without turning them into a weak pass.

Install it into an agent's skills directory (Python 3.11 or newer; YAML world models also need PyYAML, JSON ones do not). The installer copies the `worldguard/` package into the installed skill's `runtime/`; inside this repository the launcher imports the repository package directly:

```bash
python -m pip install PyYAML
python scripts/install_skill.py --target "$CODEX_HOME/skills"          # or ~/.claude/skills
python scripts/install_skill.py --target "$CODEX_HOME/skills" --check  # exit 1 if the copy differs
```

## What This Is Not

WorldGuard is not a physics solver, legal authority, safety certifier, market model, or deployment-readiness checker. The fuel-cell example is a toy fixture for guard behavior and regression testing. It does not validate real fuel-cell physics, legal compliance, safety certification, deployment readiness, market truth, or business strategy.

WorldGuard also does not include a domain-specific novel, academic-paper, or game-design workflow in this core package. Those should be built as upper-layer skills that call the generic WorldGuard contracts.

## Repository Layout

```text
worldguard/                  Python runtime and CLI
worldguard/guards/           Guard implementations
worldguard/examples/fuel_cell/  Toy unit-check fixture (packaged with the runtime)
examples/model_mesh/         Generic mesh-check fixture
tests/                       Runtime and regression tests
skills/worldguard/           Codex skill copy
openspec/                    Current OpenSpec specs and archived change proposals
docs/                        Historical audit notes
assets/readme-hero/          README visual assets
```

## Release Notes

See [CHANGELOG.md](./CHANGELOG.md) for the current version and the release history.

## License

No license file is included yet. Treat this repository as source-visible but not yet licensed for unrestricted third-party reuse until a license is added.

---

# WorldGuard 中文说明

**包名：** `worldguard`<br>
**发布类型：** 源码版 Python 包 + Codex 技能工作流

WorldGuard 用来检查一个“世界声明”是否被显式模型支持、是否被模型反驳、是否缺少必要输入，或者是否超出了模型边界。它的目标不是给一个凭感觉的自然语言结论，而是保留结构化证据、缺口、反例和边界。

## 它能做什么

WorldGuard 有两种核心检查形态：

- `GuardContract`：一个声明，对一个显式世界模型做单元检查。
- `ModelMeshContract`：多个模型节点之间的连接检查，包括权限边界、只读 handoff、证据新鲜度、依赖循环和子报告保留。

运行结果不会被压成模糊的“通过/不通过”，而是保留四种状态：

- `PASS`：模型支持这个声明。
- `FAIL`：模型反驳这个声明。
- `GAP`：缺少必要输入。
- `BOUNDARY_EXCEEDED`：声明要求模型支持它没有权限支持的语义。

## Guard 类型

当前包含：

- `EventGuard`：事件和轨迹。
- `AgentGuard`：主体的信念、能力、愿望和意图。
- `SpaceGuard`：空间关系。
- `ResourceGuard`：资源、place、token、transition 和 capacity。
- `CausalGuard`：结构因果支持。
- `ConflictGuard`：激励冲突或收益策略矛盾。
- `NormGuard`：许可、义务和禁止。

## ModelMesh

`ModelMeshContract` 是单个 Guard 检查之上的通用连接层。它解决的问题是：一个局部模型通过了，不等于整个模型网格可以通过。

它会检查：

- 模型权限：每个节点只能支持自己拥有的语义；
- handoff：下游只能读上游证据，不能修改上游结果；
- `allowed_use` 和 `forbidden_use`：输出用途必须留在声明边界内；
- freshness：需要当前证据时，陈旧或未知来源不能支撑下游当前声明；
- 循环依赖：依赖环会导致 mesh 失败；
- 证据保留：子报告、ledger、gap 和反例不能在聚合时丢失。

## 任务内事实修订

WorldGuard 现在可以预览并激活一次显式的事实支持修订，但这不会创建新的
全局数据库，也不会增加一个新的 Guard。正向支持和反向支持彼此独立，所以
同一个事实可以是“真”“假”“同时真且假”或“尚无支持”。矛盾会被明确展示，
但不会把无关事实也推成真。

预览不会修改原始快照；增加或撤回支持后，严格规则的推导闭包会重新计算。
真正激活时，还必须绑定同一个预览指纹、保护声明为不可变的事实、明确确认
矛盾，并提供当前的回归与留出验证证据。基础快照过期、证据不完整或重复使用
事务编号时都会明确阻断。

事实激活不是任务关闭。成功激活只会返回
`task_local_revalidation_required`，把这个精确候选重新交回同一个任务本地
预测 owner，重新运行当前原生深度、原场景和独立真实留出验证。

## 任务本地预测修订

每个预测都要写明一个任务和目的、覆盖全集、显式假设和未知边界，以及前序
迭代；后续迭代还要写明上一轮精确的 gap 编号。覆盖全集和 gap 集合的指纹由
WorldGuard 自己计算。`task-model revision` 会把候选网格实际运行一次，状态、
转移、分支、扰动、干预、反事实和留出 gap 都取自这次运行，调用方不能自己
填写“没有 gap”。

候选关闭需要一份原场景和一份真正独立的留出观测；改名后重复使用的同一份
观测会按内容被识别出来。
WorldGuard 自己计算已解决、仍存在和新引入的 gap；证据没有变化就停在
`progress_stalled`，迭代上限会阻断，外部缺失输入必须精确说明 gap、owner、
原因和受影响声明。

## 快速开始

```powershell
python -m pip install -e .
python -m pytest
python -m worldguard.examples.fuel_cell --check
python -m worldguard.cli check --example fuel_cell
python -m worldguard.cli mesh-check --mesh examples/model_mesh/basic_mesh.yaml
python -m worldguard.cli task-model fact-revision-preview base.json transaction.json
python -m worldguard.cli task-model fact-revision-activate base.json transaction.json activation.json
```

## 这个项目不是什么

WorldGuard 不是物理求解器、法律判断器、安全认证器、市场模型或部署可行性判断器。fuel-cell 示例只是测试用的 toy fixture，不证明真实燃料电池物理、法律合规、安全认证、部署准备、市场真实性或商业策略。

这个核心包也不直接包含小说写作、学术论文修改或游戏设计工作流。那些应该作为上层技能来使用 WorldGuard 的通用 contract。
