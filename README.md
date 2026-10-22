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
Install FlowGuard only from the owner's GitHub (`git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>`); the PyPI package named `flowguard` is a different project.

```bash
python -m pytest -q
python -m worldguard.guard_model_contract
```

Portable consumers run `python /path/to/worldguard/scripts/run_worldguard.py check --help`; no Python distribution metadata is required.

## What It Does

The native CLI commands are `check` and `mesh-check`. Start a new contract by copying a world from `skills/worldguard/assets/examples/` and editing its model and assertions.

WorldGuard provides two core check shapes:

- `GuardContract`: checks one claim against one explicit world model. The claim says what it claims as `claim.asserts` rows, which are evaluated on the model; the claim text is never read.
- `ModelMeshContract`: checks multiple model nodes, authority boundaries, read-only handoffs, source freshness, dependency cycles, and child ledger preservation.

The runtime returns four statuses without collapsing them:

- `PASS`: the declared model supports the requested claim.
- `FAIL`: the declared model contradicts the claim.
- `GAP`: required model inputs are missing, or the claim is not bound to the model (no `claim.asserts`).
- `BOUNDARY_EXCEEDED`: the claim asks the model to support semantics it does not own.

Event times use one format per contract: YAML numbers, labels with a shared prefix (`t1`, `t2`),
ISO dates/times with a consistent timezone convention, or quoted same-day clocks (`"9:40"`, `"17:12:30"`).
Unknown or mixed times and duplicate event ids within one scenario are input errors (exit 2).
Use ISO dates across midnight. YAML's unquoted `9:40` is a number, so quote clock values.
Event assertions can select `scenario`; reused ids without a scenario and unknown scenarios are gaps.
A missing event time prevents ordering its applicable scenarios; independent scenarios still report known failures.

Causal scenario and holdout assignments replace the named variables' equations. A declared intervention
runs even on an empty scenario; constraints and unscoped variable assertions check every scenario,
holdout and intervention. Select a run with `scenario: <id>`. Interventions use a list of mappings with
unique ids, a declared scenario id and numeric assignments; malformed or colliding run identities are input errors.

A declared boundary of a Guard already derived from the claim yields `BOUNDARY_EXCEEDED`. A boundary
belonging only to an unselected Guard remains an unmapped `GAP` with a hint naming its normal semantic.
Real failures and gaps keep their priority: `FAIL` > `GAP` > `BOUNDARY_EXCEEDED` > `PASS`.

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

Every node runs its native contract once. Missing contracts are gaps. Prediction semantics select EventGuard and CausalGuard, with no separate prediction-license or timepoint-coverage gate.

It checks:

- model authority: each node can only support the semantics it owns;
- handoffs: downstream nodes may read upstream evidence but cannot mutate it;
- `allowed_use` and `forbidden_use`: outputs must stay inside declared use boundaries;
- freshness: stale or unknown sources cannot support current downstream claims when current evidence is required;
- cycles: dependency loops are reported as mesh failures;
- evidence preservation: child reports, ledgers, gaps, and counterexamples survive aggregation.

## Quick Start

```powershell
python -m pip install -e .
python -m pytest
python -m worldguard.examples.fuel_cell --check
python -m worldguard.cli check --example fuel_cell
python -m worldguard.cli mesh-check --mesh examples/model_mesh/basic_mesh.yaml
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

FlowGuard 只从主人的 GitHub 安装（`git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>`）；PyPI 上叫 `flowguard` 的是另一个项目。

## 它能做什么

原生 CLI 命令为 `check` 和 `mesh-check`。从 `skills/worldguard/assets/examples/` 复制一个世界，再修改模型和断言即可开始新合约。

WorldGuard 有两种核心检查形态：

- `GuardContract`：一个声明，对一个显式世界模型做单元检查。
- `ModelMeshContract`：多个模型节点之间的连接检查，包括权限边界、只读 handoff、证据新鲜度、依赖循环和子报告保留。

运行结果不会被压成模糊的“通过/不通过”，而是保留四种状态：

- `PASS`：模型支持这个声明。
- `FAIL`：模型反驳这个声明。
- `GAP`：缺少必要输入。
- `BOUNDARY_EXCEEDED`：声明要求模型支持它没有权限支持的语义。

每份合约的事件和 `holds.at` 只用一种时间写法：YAML 数字、同前缀标签（`t1`、`t2`）、
时区约定一致的 ISO 日期时间，或带引号的同日钟点（`"9:40"`、`"17:12:30"`）。
未知或混写时间、同场景重复事件 ID 是输入错误（退出 2）。跨午夜请用 ISO 日期。
YAML 把未加引号的 `9:40` 读成数字，所以钟点必须加引号。事件断言可用 `scenario`
指定场景；复用 ID 未指定场景而有歧义或指定未知场景时返回缺口。
事件缺少时间只阻止其适用场景的排序；独立场景中已经确定的失败仍会报告。

因果场景和留出场景的赋值会替换对应变量的方程；其余变量重新计算。干预即使基于空场景
也会执行。约束及未指定 `scenario` 的变量断言检查所有场景、留出和干预；可用
`scenario: <id>` 选择一次运行。干预必须是包含唯一 ID、已声明场景 ID 和数字赋值的映射列表；
错误形状和相互冲突的运行 ID 是输入错误。

已由声明派生的 Guard 遇到自己声明的边界时，结果为 `BOUNDARY_EXCEEDED`。只属于未选 Guard
的边界仍是未映射 `GAP`，并提示对应 Guard 的常规语义。真实失败和缺口的优先级保持为
`FAIL` > `GAP` > `BOUNDARY_EXCEEDED` > `PASS`。

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

每个节点的原生合约都会运行一次；缺少合约是缺口。预测语义选择 EventGuard 和 CausalGuard，不另设预测许可或时间点覆盖门槛。

`ModelMeshContract` 是单个 Guard 检查之上的通用连接层。它解决的问题是：一个局部模型通过了，不等于整个模型网格可以通过。

它会检查：

- 模型权限：每个节点只能支持自己拥有的语义；
- handoff：下游只能读上游证据，不能修改上游结果；
- `allowed_use` 和 `forbidden_use`：输出用途必须留在声明边界内；
- freshness：需要当前证据时，陈旧或未知来源不能支撑下游当前声明；
- 循环依赖：依赖环会导致 mesh 失败；
- 证据保留：子报告、ledger、gap 和反例不能在聚合时丢失。

## 快速开始

```powershell
python -m pip install -e .
python -m pytest
python -m worldguard.examples.fuel_cell --check
python -m worldguard.cli check --example fuel_cell
python -m worldguard.cli mesh-check --mesh examples/model_mesh/basic_mesh.yaml
```

## 这个项目不是什么

WorldGuard 不是物理求解器、法律判断器、安全认证器、市场模型或部署可行性判断器。fuel-cell 示例只是测试用的 toy fixture，不证明真实燃料电池物理、法律合规、安全认证、部署准备、市场真实性或商业策略。

这个核心包也不直接包含小说写作、学术论文修改或游戏设计工作流。那些应该作为上层技能来使用 WorldGuard 的通用 contract。
