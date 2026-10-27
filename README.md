# WorldGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="WorldGuard contracts and world-model checks" width="100%" />
</p>
<!-- README HERO END -->

WorldGuard checks a story, trip, plan or process against an explicit executable
world model. Write the model and `claim.asserts`; the claim sentence is never read.
A passing model supports the declared claim within its scope, without establishing
factual truth. English instructions come first; 中文说明 follows below.

## Start with a world or one model tree

```bash
python skills/worldguard/scripts/run_worldguard.py timeline --example trip
python skills/worldguard/scripts/run_worldguard.py check --example scene
python skills/worldguard/scripts/run_worldguard.py check --example trip
python skills/worldguard/scripts/run_worldguard.py mesh-check --example story
```

Start from the model: read an existing world or tree with `timeline` (and
`mesh-check`) first; for a new one write the claim rows, only the inputs they need,
one known-bad variant per claim, a tree for chapters or days, and contract-less
planned nodes for parts not written yet.

Copy a world from `skills/worldguard/assets/examples/` and edit its inputs and
assertions. The commands are `check`, `mesh-check`, `timeline` and `compare`.

- One contract contains `contract_id`, `claim`, `world_model`, `inputs` and optional
  `variants`. Claim semantics and assertion kinds derive the seven native Guards:
  Event, Agent, Space, Resource, Causal, Conflict and Norm. Prediction selects Event
  and Causal. Unknown semantics remain `QUALIFICATION_SEMANTIC_UNMAPPED` GAP.
- One mesh contains `mesh_id`, `nodes`, `edges` and optional `variants`. Each node
  has `model_id`, `contract` and optional `source`. Contracts may be embedded or
  paths relative to the mesh file. Edges use `from` / `to` and only `parent_child`
  or `continues`. There is exactly one root and at most one parent per node;
  otherwise `MESH_NOT_ONE_TREE` is GAP. A root may hold only descendant `node:`
  assertions. A passing parent never hides a non-passing child.
- `continues` checks final-to-initial fluent state, event time, shared unique token
  locations and optional scenario variables. Gaps retain missing values; known
  contradictions fail. Missing edge endpoints produce `MESH_EDGE_NODE_MISSING`.
- Contract and mesh `variants:` apply declared edits to independent in-memory
  copies. Each must reach its expected status and optional native code; otherwise
  `VARIANT_NOT_CAUGHT` blocks PASS. Tree variants rerun the whole tree.
- `source:` is an original-text pointer copied into related problems. Its contents
  are not checked, and it does not give a model any extra qualification.

Read [the contract guide](skills/worldguard/references/worldguard-contracts.md),
[Guard input examples](skills/worldguard/references/guard-inputs.md), or
[the small tree](skills/worldguard/references/model-mesh.md) for runnable formats.
Retired fields are input errors with a named field and a one-line migration fix.

## Events, resources and results

A world with unscoped events and token transfers must link every transition using
`event: <event_id>`. Some or all links missing give GAP
`RESOURCE_TRANSITION_UNLINKED`, naming the transition ids. A supplied link to an
absent or scoped event is an input error. Complete links replay by event time,
keeping list order for multiple transfers fired by one event. Resource-only worlds
keep list order. Same-named fluents and places must agree initially and after each
event: the fluent holds exactly when the place has at least one token. The first
mismatch per name gives FAIL `WORLD_EVENT_TOKEN_MISMATCH` with the step and trace.
A single token's place must also agree with the spatial relations declared at the
same time: a declared-disjoint region FAILs `WORLD_SPACE_TOKEN_MISMATCH`, an
unrelated region is GAP `WORLD_SPACE_TOKEN_UNRELATED`.
These checks apply regardless of which Guards the claim derives.

Use one clock kind per contract: YAML numbers, labels with one prefix (`t1`, `t2`),
ISO dates/times with consistent timezone convention, or quoted same-day clocks
(`"9:40"`). Use ISO times across midnight. Unknown or mixed time kinds and duplicate
event ids within one scenario are input errors, exit 2. Missing event times remain
native GAP; independent known failures survive. Assertions select a scenario with
`scenario`; ambiguous reused event ids and unknown scenarios are gaps.

Causal scenario/holdout assignments replace those variables' equations; other
variables recompute. Interventions use unique ids, an existing scenario id and
finite numeric assignments. Constraints and unscoped variable assertions check
all scenarios, holdouts and interventions, including empty declared scenarios.
Norms check actual event actions; RCC8 uses native relation composition.

Statuses remain distinct: `FAIL` > `GAP` > `BOUNDARY_EXCEEDED` > `PASS`.
A claim without assertions is GAP `CLAIM_NOT_BOUND`; false assertions FAIL with
`CLAIM_ASSERTION_FALSE`, and unresolved assertions GAP. Check and mesh exit 0 on
PASS, 1 on non-PASS, 2 on invalid input. Their defaults are short JSON summaries;
`--json` adds full child/Guard rows. Mesh reports include depth-first `tree` lines:
each node's own status, ` (tree <status>)` when its subtree differs, each
`continues` edge's result and codes, and `GAP planned` for a node without a contract;
the root line agrees with the overall status.
Failed event preconditions block fluent effects in assertions, timelines and handoffs.
Check summaries and full JSON include sorted relative input paths with raw-byte SHA-256
in `input_digests`. Each command has a help description.
Timeline starts with full state, then fluent `+`/`-` changes and changed token places;
`--full` repeats complete state lines. Its readable text shows: each claim row with its result, one line per
declared agent, space, conflict and norm sub-model, the steps with source and
problem codes, and a `problems:` section for every other problem of the check.
`--json` preserves the complete view. It reads a model rather than proving closure.

## Compare actual observations

```bash
python skills/worldguard/scripts/run_worldguard.py compare --contract world.yaml --observed log.yaml
python skills/worldguard/scripts/run_worldguard.py compare --mesh mesh.yaml --observed log.yaml --write-observed actual.json
python skills/worldguard/scripts/run_worldguard.py mesh-check --mesh actual.json
python skills/worldguard/scripts/run_worldguard.py timeline --mesh actual.json
```

Supply event times and/or scenario variable values; mesh observations are keyed by
`nodes: {model_id: observations}`. Comparison checks only supplied values and emits
matches/mismatches with signed actual-minus-expected differences. ISO/clock time
and tolerances use minutes; numeric/label clocks use their own scale. Unknown ids,
ambiguous scenarios and invalid tolerances are input errors. Exit 0 means all
matches; 1 means a mismatch. `--write-observed OUT` writes a new independent
contract/tree, changing only selected observed event occurrences' `at` fields.
Variables stay unchanged, original files are untouched and existing OUT is refused.
Rerun native checks on the copy to see downstream consequences.

## Install and develop

Python 3.11 or newer is required. YAML files need PyYAML; JSON files do not.
The portable skill installer copies `worldguard/` to the installed skill's
`runtime/`; the repository launcher uses the repository package directly.

```bash
python -m pip install PyYAML
python scripts/install_skill.py --target "$CODEX_HOME/skills"
python scripts/install_skill.py --target "$CODEX_HOME/skills" --check
```

The `worldguard` console entry point is also available with the package installed.
The Python API exports `GuardContract`, `ModelMeshContract`, `run_worldguard` and
`run_model_mesh`. Development uses ordinary pytest and the living FlowGuard map:

```bash
python -m pytest -q
python -m flowguard map models
```

Install FlowGuard from the owner's GitHub tag specified in `pyproject.toml`; the
PyPI project named `flowguard` is a different package. Source version alone does
not establish a hosted release or installed-consumer identity.

`worldguard/` holds the runtime; `tests/` the regression tests;
`skills/worldguard/` the skill, its three references and bundled examples;
`openspec/specs/` the current specifications. See [CHANGELOG.md](CHANGELOG.md).
WorldGuard is not a physics solver, legal judgment, safety certificate or market
prediction. Upper-layer writing and research workflows may call its world models.
No license file is included; source visibility alone grants no unrestricted reuse.

---

# WorldGuard 中文说明

WorldGuard 把故事、行程、计划或过程写成可执行世界模型，用 `claim.asserts`
逐行检查说法；不会读取说法句子来猜结论。PASS 只适用于已声明模型和边界，不证明现实真伪。

先从模型开始：用 `timeline --example trip` 读回一个世界，再用 `check --example scene|trip` 检查；没写完的章节先放没有 `contract` 的节点（`GAP planned`）。`mesh-check --example story` 是技能自带的一棵树。
节点只写 `model_id`、`contract` 和可选 `source`；合约可内嵌，也可用相对文件路径。
边只用 `from` / `to`，关系只有 `parent_child` 和 `continues`。必须恰有一个根，
每节点至多一个父节点，否则 GAP `MESH_NOT_ONE_TREE`。父节点可用 `node:` 读取后代；
父节点通过不能掩盖子节点的问题。`continues` 检查结束到开始的状态、时间、唯一令牌和指定变量。

有事件又有资源转移时，每个转移用 `event:` 点名触发事件；全部或部分没连，都是
GAP `RESOURCE_TRANSITION_UNLINKED`，会列出转移 ID。显式指错事件仍是输入错误。
同名状态和地点在初始及每个事件后都要一致：状态成立当且仅当地点至少有一个令牌；
否则 FAIL `WORLD_EVENT_TOKEN_MISMATCH` 给出第一次冲突的步骤。
单个令牌的位置还要和同一时刻声明的空间关系相容：推出不相交是 FAIL `WORLD_SPACE_TOKEN_MISMATCH`，
没有关系是 GAP `WORLD_SPACE_TOKEN_UNRELATED`。只有资源的模型仍按列表重放。
缺时间仍是原生缺口；独立、已确定的失败不会被其他缺口遮住。

合约和树都可写 `variants:`：在独立副本上制造已知坏，必须达到声明状态和问题码；
树的变体会重跑整棵树。`source:` 只是未经检查的原文位置，不校验来源内容，也不赋予结论资格。
退役字段一经出现就是输入错误，按报错提示移除并改用当前格式。

`timeline --contract world.yaml`、`timeline --mesh mesh.yaml` 默认输出可读文字；
文字先列每条说法行和结果、每个声明的子模型（`agents:`、`space:`、`conflict:`、`norms:`），
再列事件步骤（起始完整状态，之后只列 fluent 的 `+`/`-` 和变化的令牌位置，`--full` 保留完整行），最后 `problems:` 列出其余全部问题；`--json` 保留完整结构。树摘要有逐行的 `tree`：
节点自己的状态、子树不同时的 `(tree …)`、每条 `continues` 边的结果和问题码，没有合约的节点写 `GAP planned`。`compare --contract|--mesh --observed`
只比较提供的观测，树的观测按 `nodes` 分组。ISO/钟点容差用分钟，数值/标签钟用自己的尺度。
加 `--write-observed OUT` 只把选中的事件发生时间写入新副本，不改变量或原文件，已有文件拒绝覆盖。
对副本再跑 `check` 或 `mesh-check`，查看实际时间是否破坏后续计划。

四种状态按 `FAIL`、`GAP`、`BOUNDARY_EXCEEDED`、`PASS` 保留优先级。检查通过退出 0，
非 PASS 退出 1，输入错误退出 2；比对全部匹配退出 0，超差退出 1。不满足前置条件的事件不产生 fluent 效果。检查的摘要和完整 JSON 都有 `input_digests`（相对路径和原字节 SHA-256）。四个命令都有帮助说明。普通检查摘要仍为短 JSON，
只在需要完整 Guard/子节点信息时加 `--json`。报告状态、问题码、反例或缺失输入和模型范围。

技能安装命令和完整可运行格式见上方英文说明及三个参考页。技能名字、启动器路径和安装器入口保持稳定。
