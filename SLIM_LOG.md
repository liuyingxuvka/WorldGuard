# WorldGuard slim execution log

## Scope and authority

- Baseline: v0.7.15, `e99b9998ad1a3159f66029b11548cde0ec8445bd`.
- Branch: `slim/2026-10`; authority: WorldGuard WG-01–WG-60 actions and XR-01 dependency table in the 2026-10-21 handoff.
- User version override: final WorldGuard **0.7.16**, new FlowGuard **0.70.7**. Historical baseline references remain unchanged.
- Each action is implemented and verified in numeric order, then committed using its prescribed subject. Explicit approved removals supersede historical receipt/DNA preservation requirements.
- Canonical source is `worldguard/`; WG-01–WG-35 synchronize its portable mirror. WG-36 onward installation generates the portable runtime.
- No push, Git tag, GitHub Release publication or global skill installation by this worker; root coordinates cross-repository completion.

## Preparation and baseline

Environment: repository `.venv`, Python 3.12.14 (>=3.11); pytest 9.1.1; editable WorldGuard 0.7.15 and read-only tracked FlowGuard baseline 0.70.6 from `../guard-baseline/flowguard`. The environment had completed before the cached Python 3.11 location was supplied; the actual interpreter is recorded rather than reporting 3.11 results. Editable build metadata is ignored and does not modify baseline tracked source.

| Command | Actual result | Time |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 386 passed | 73.35 s |
| `.venv/bin/python -m flowguard map check` | 0 errors, 0 warnings, 0 info | 0.52 s |
| `.venv/bin/python -m flowguard release` | 7 declared / 7 executed; PASS | 4.31 s |
| `.venv/bin/python scripts/sync_worldguard_portable_runtime.py check` | mirror parity PASS, no write | 0.10 s |
| `.venv/bin/python skills/worldguard/scripts/run_worldguard.py check --example fuel_cell` | exit 0; 130766 output bytes | 0.29 s |

The baseline suite takes longer than the handoff machine's 30–35 seconds; no functional conclusion depends on matching elapsed time. Detailed raw outputs, exact paths and timings are retained in the external `WorldGuard` results directory.

Baseline tracked size: 638 files / 18566156 bytes; canonical Python 23403 lines; test Python 10777 lines.

## Actions

The coordinator opened WG-01–WG-08 under the user's parallel authorization: inspection found no runtime dependency on RG-01–RG-10 because both use isolated exact baselines. This changes cross-repository scheduling only; numeric action order and verification remain unchanged. A later independent XR dependency review opened WG-09–WG-44 on the same exact baseline dependencies too: this range reads no new RG source and first probes the new FlowGuard at WG-45. After WG-44, wait for the coordinator's complete new FlowGuard signal. WG-32/WG-36 continue reading the frozen LogicWriting baseline; an unavailable repository-only portable layout after WG-36 remains expected until XR-11, while installed portable execution must pass.

### WG-01: 删除 self-DNA、执行深度“证据桥”和运行时身份审计

Status: completed.

Removed self-DNA, unused execution-depth evidence bridge, runtime identity author checks and their dedicated files; preserved deep.json and the release workflow version consistency check. Synchronized canonical changes to the portable mirror. The expected unused scripts -> worldguard.mesh dependency was removed after map check exposed it.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-01/mirror.log`) |
| `map-before` | 1 | check: 1 error(s), 4 warning(s), 0 info (`WG-01/map-before.log`) |
| `map` | 0 | check: 0 error(s), 4 warning(s), 0 info (`WG-01/map.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-01/models.log`) |
| `pytest` | 0 | 375 passed in 32.41s (`WG-01/pytest.log`) |
| `residue` | 0 | (no output) (`WG-01/residue.log`) |
| `portable-help` | 0 |   --example {fuel_cell} (`WG-01/portable-help.log`) |

Adaptations: Only scheduling changed: root explicitly opened WG-01–WG-08 in parallel with RG-01–RG-10 after verifying there is no actual dependency; all action-local ordering and checks remain intact.

### WG-02: 修复燃料电池示例：改成当前输入格式，自检逐条比对期望状态

Status: completed.

Updated the packaged fuel-cell world to current agent, causal and boolean-fact inputs. Each story claim declares an expected status and run_check compares every claim instead of accepting any FAIL; the portable invocation now yields True / PASS,PASS,FAIL / no mismatches. Preserved BOUNDARY_STRINGS and expected_guard_report for WG-03.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-02/mirror.log`) |
| `fuel-cell` | 0 | True ['PASS', 'PASS', 'FAIL'] [] (`WG-02/fuel-cell.log`) |
| `pytest` | 0 | 375 passed in 34.45s (`WG-02/pytest.log`) |
| `map` | 0 | check: 0 error(s), 4 warning(s), 0 info (`WG-02/map.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-02/models.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-03: NormGuard 增加真正的规范冲突检查；删除只为示例写死的字符串

Status: completed.

Replaced toy recipe substring special cases with native active-norm conflict detection grouped by actor/action, shared by structural and semantic owners. False condition facts make a norm inactive; missing/malformed/duplicate fact checks remain. Added real active/inactive conflict cases and updated the fuel-cell asserted permission and independent native failure catalog (79 known-bad cases).

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-03/mirror.log`) |
| `focused` | 0 | 34 passed in 0.41s (`WG-03/focused.log`) |
| `catalog` | 0 | status=pass purposes=7 goods=7 failures=79 known_bads=79 (`WG-03/catalog.log`) |
| `fuel-cell` | 0 | True ['PASS', 'PASS', 'FAIL'] [] ['NORM_ACTIVE_CONFLICT'] (`WG-03/fuel-cell.log`) |
| `pytest` | 0 | 376 passed in 33.33s (`WG-03/pytest.log`) |
| `map` | 0 | check: 0 error(s), 6 warning(s), 0 info (`WG-03/map.log`) |
| `residue` | 0 | (no output) (`WG-03/residue.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-04: 判定不再看主张句子里的词：边界只由 requested_semantics 里的语义 id 决定

Status: completed.

Guard boundaries and predictive intent now use explicit requested semantic ids only, including atom semantics; natural-language prose cannot change the verdict or inferred route set. Preserved all model checks after each boundary check and ResourceGuard ordered token replay. Migrated the independent boundary catalog/blueprint replay and status cases to semantic ids, and added the real locked-door scene and prose/order regressions.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-04/mirror.log`) |
| `catalog` | 0 | status=pass purposes=7 goods=7 failures=78 known_bads=78 (`WG-04/catalog.log`) |
| `focused` | 0 | 17 passed in 1.44s (`WG-04/focused.log`) |
| `pytest` | 0 | 378 passed in 37.52s (`WG-04/pytest.log`) |
| `map` | 0 | check: 0 error(s), 7 warning(s), 0 info (`WG-04/map.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-04/models.log`) |
| `residue` | 0 | (no output) (`WG-04/residue.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-05: claim.target_guards 改为可选：引擎总是运行自己推导出的 Guard 集合

Status: completed.

The qualification owner always executes the native derived Guard set. Caller target_guards remain readable, omitted/unexpected sets remain visible, and neither echo mismatch blocks execution. Mesh coverage uses the derived set too; unknown semantics still create a visible GAP. Actual portable scene probes with missing target_guards and an extra SpaceGuard both pass while executing EventGuard/ResourceGuard/AgentGuard exactly.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-05/mirror.log`) |
| `focused` | 0 | 79 passed in 0.64s (`WG-05/focused.log`) |
| `target-guards` | 0 | extra PASS ['EventGuard', 'ResourceGuard', 'AgentGuard'] ['SpaceGuard'] (`WG-05/target-guards.log`) |
| `pytest` | 0 | 378 passed in 53.14s (`WG-05/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-05/map.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-05/models.log`) |
| `residue` | 0 | (no output) (`WG-05/residue.log`) |

Adaptations: Root independently certified WG-09–WG-44 can continue against frozen baselines; WG-45 is the first actual new-FlowGuard probe. This further scheduling adaptation changes no action purpose or within-repository order.

### WG-06: 最小合同不再崩溃：缺 contract_id / model_version 用默认值，输入错误返回 JSON

Status: completed.

Minimal contracts now default contract_id to claim_id and missing model_version to unversioned. check and mesh-check report OSError/UnicodeError/ValueError/YAML input failures as WORLDGUARD_INPUT_INVALID JSON with exit 2. Preserved retired-field migration errors and existing blueprint input errors. Real portable probes confirm malformed and missing check/mesh inputs are typed errors without tracebacks.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-06/mirror.log`) |
| `focused` | 0 | 7 passed in 4.38s (`WG-06/focused.log`) |
| `input-errors` | 0 | mesh-check 2 WORLDGUARD_INPUT_INVALID [Errno 2] No such file or directory: '/workspace/guard-repair-20261021/results/WorldGuard/WG-06/missing-mesh.yaml' (`WG-06/input-errors.log`) |
| `pytest` | 0 | 378 passed in 30.83s (`WG-06/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-06/map.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-07: EventGuard 按真实时间顺序推演事件（t9 在 t10 之前）

Status: completed.

Semantic EventGuard orders numeric/prefixed-numeric times and ISO date-times chronologically, including observed_timepoints. The real t9 lock / t10 unlock regression now ends unlocked and reports t9 before t10. Structural EventGuard and mesh time parsing remain unchanged; bound the new ordinary test to the existing semantic core owner.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-07/mirror.log`) |
| `focused` | 0 | 95 passed in 0.65s (`WG-07/focused.log`) |
| `pytest` | 0 | 379 passed in 39.93s (`WG-07/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-07/map.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-07/models.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-08: 统一退出码：0 = PASS，1 = 非通过，2 = 输入错误

Status: completed.

Unified check and mesh-check exits to 0 for PASS and 1 for non-pass, with existing typed input errors at 2. Example exits according to its expected-case self-check; blueprint impact exits 1 for gaps. Existing blueprint/task-model error and exit shapes are retained. Real valid/broken resource-scene tests and portable success/help probes pass.

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | mirror-ok (`WG-08/mirror.log`) |
| `focused` | 0 | 38 passed in 4.87s (`WG-08/focused.log`) |
| `portable-pass` | 0 | unit-and-example-ok (`WG-08/portable-pass.log`) |
| `portable-help` | 0 |   --example {fuel_cell} (`WG-08/portable-help.log`) |
| `pytest` | 0 | 380 passed in 46.56s (`WG-08/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-08/map.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-09: 删除仓库顶层已经漂移的燃料电池示例副本

Status: completed.

Deleted only the unused, drifted top-level examples/fuel_cell YAML copy and pointed the repository layout to the packaged canonical example. examples/model_mesh, packaged data and package-data configuration are unchanged. Running the installed fuel-cell module from an unrelated /tmp working directory succeeds.

| Check | Exit | Actual result / log |
|---|---:|---|
| `inventory` | 0 | ['model_mesh'] (`WG-09/inventory.log`) |
| `foreign-cwd` | 0 | foreign-cwd-ok (`WG-09/foreign-cwd.log`) |
| `pytest` | 0 | 380 passed in 42.02s (`WG-09/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-09/map.log`) |

Adaptations: None; reference purpose and implementation retained.

### WG-10: 删除路由 capsule、入口协议和两个作者用的提示词检查器

Status: completed.

Deleted unused route-capsule/entry-routing files, two author-only prompt checker scripts and their 24 dedicated tests. Removed their prompt references, retained the five shape rows and name: worldguard, and replaced openai.yaml with the 300-byte portable native-use prompt. Removed exactly the three script dependencies exposed as unused by map check; native launcher code is unchanged.

| Check | Exit | Actual result / log |
|---|---:|---|
| `map-before` | 1 | check: 1 error(s), 8 warning(s), 0 info (`WG-10/map-before.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-10/map.log`) |
| `residue` | 0 | (no output) (`WG-10/residue.log`) |
| `prompt-and-scripts` | 1 | ['__pycache__', 'run_worldguard.py', 'run_worldguard_check.py'] (`WG-10/prompt-and-scripts.log`) |
| `pytest` | 0 | 356 passed in 40.32s (`WG-10/pytest.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-10/models.log`) |
| `prompt-and-scripts-tracked` | 0 | ['skills/worldguard/scripts/run_worldguard.py', 'skills/worldguard/scripts/run_worldguard_check.py'] (`WG-10/prompt-and-scripts-tracked.log`) |

Adaptations: The literal directory listing also contained an ignored generated __pycache__; the initial strict two-entry probe failed and is preserved. A read-only git-tracked script inventory proves only run_worldguard.py and run_worldguard_check.py remain, without deleting unrelated generated cache artifacts.

### WG-06 supplemental correction: malformed mapping/container inputs

Independent review of exact `2be566d` found a real acceptance gap: `claim: null`, `inputs: null`, `nodes: null` and `nodes: [42]` returned legacy exit 1 / ok:false instead of WORLDGUARD_INPUT_INVALID / exit 2. The original failed observations remain in external CrossReview/WG-malformed-input-probe.json and WG-malformed-mesh-probe.json. Prior passes are the cases actually run, not complete input-shape coverage.

Root authorized this bounded correction after WG-10 and before WG-11, with a separate `fix:` commit and no historical rewrite or duplicate WG action prefix. GuardContract validates its required mapping sections at construction; mesh construction validates its container/row shapes and node contract mapping. A deliberately contractless node remains a native GAP/exit 1. No execution-stage TypeError catch was added; an internal-native TypeError control still propagates past CLI input handling.

| Check | Exit | Result |
|---|---:|---|
| Mirror sync/check | 0 | mirror-ok |
| Existing CLI/mesh/claim-coverage owners | 0 | 69 passed |
| Full suite | 0 | 359 passed in 41.43 s |
| Map check | 0 | 0 errors, 8 expected stale warnings (WG-35) |
| Models | 0 | 6 passed, 0 failed |

Finite controls include null and list values for claim/world_model/inputs; malformed nodes, edges and snapshots; a bad node-contract mapping; preserved explicit contract:null GAP; and a native TypeError that must not become an input error. Detailed logs: WG-06-followup/.

Independent exact-snapshot retest of supplemental commit `a17463d` passed the original four malformed cases, valid minimal PASS/0, contractless GAP/1 and the internal TypeError control. Root closed the bounded input-shapes finding; evidence: external CrossReview/WG-input-shape-retest-a17463d.json. This does not claim exhaustive malformed-input coverage.

### WG-11: FlowGuard 维护依赖只在 pyproject.toml 声明一次；删除测试和 README 里的版本号钉子

Status: completed.

Declared FlowGuard maintenance/test dependency once in pyproject.toml using the owner GitHub baseline tag, not PyPI. AGENTS references that declaration without another version number. Removed README and portable-version test pins; added one ordinary test comparing VERSION, project metadata and canonical __version__ without pinning a release number. No remote dependency download was run.

| Check | Exit | Actual result / log |
|---|---:|---|
| `dependency` | 0 | {'test': ['pytest', 'flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v0.70.6']} (`WG-11/dependency.log`) |
| `version-references` | 0 | worldguard/__init__.py:5:__version__ = "0.7.15" (`WG-11/version-references.log`) |
| `pytest` | 0 | 360 passed in 54.40s (`WG-11/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-11/map.log`) |

Adaptations: The reference grep shows its five intended source/dependency lines plus three historical baseline/override lines in SLIM_LOG; those history records are intentionally preserved. Full-suite count is 360 rather than 357 because the independently requested WG06 supplemental correction added three meaningful regressions.

### WG-12: 一份真正写明输入格式的 Guard 参考，附两个可直接复制的示例世界（并有测试守住）

Status: completed.

Added the 4759-byte Guard input reference with all seven executable input examples and two complete portable scene/trip worlds. Tests execute both portable worlds and every documented Guard block. The swapped train-arrival/ferry-out transition probe produces real FAIL/exit 1. Removed obsolete guard-boundaries/catalog-only references and bound new reference/test files to the existing guard owner.

| Check | Exit | Actual result / log |
|---|---:|---|
| `reference-size` | 0 | 4759 (`WG-12/reference-size.log`) |
| `focused` | 0 | 3 passed in 0.71s (`WG-12/focused.log`) |
| `trip-order-negative` | 0 | 1 FAIL (`WG-12/trip-order-negative.log`) |
| `residue` | 0 | (no output) (`WG-12/residue.log`) |
| `pytest` | 0 | 363 passed in 61.39s (0:01:01) (`WG-12/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-12/map.log`) |

Adaptations: Full-suite count includes the three retained WG06 supplemental regressions (363 versus reference 360); all action conclusions match.

### WG-13: 改写 SKILL.md：一张带命令的形状表 + 输入参考入口 + 结果规则（约 3 KB）

Status: completed.

Replaced the entry skill with the exact 2959-byte native-use guide: five stable shapes, copyable portable commands, input reference, optional supporting references, four preserved statuses and exit meanings. name: worldguard and the real launcher are unchanged. All referenced files exist; only the explicit instruction not to copy fingerprints/receipts remains. Reconciled cumulative changes against the audited baseline with flowguard change, full tests and all six currently retained models.

| Check | Exit | Actual result / log |
|---|---:|---|
| `prompt-and-links` | 0 | ['Report the status, the gap codes, and for each non-PASS Guard its errors and counterexample. Do not copy fingerprints or receipts.'] (`WG-13/prompt-and-links.log`) |
| `change-cumulative` | 0 | ARCH INFO duplicate_code worldguard.templates: 2 identical bodies (513 AST nodes) in ['worldguard.templates']: skills/worldguard/runtime/worldguard/template_packs.py:run_template_pack_contract, worldguard/template_packs. (`WG-13/change-cumulative.log`) |
| `pytest` | 0 | 363 passed in 39.80s (`WG-13/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-13/map.log`) |
| `models-cumulative` | 0 | models: 6 passed, 0 failed (`WG-13/models-cumulative.log`) |

Adaptations: The cumulative change check also records pre-existing dynamic-import/duplicate portable mirror observations; no map errors were hidden and stale confirmations remain deferred to WG35 as explicitly required.

### WG-14: 参考文档去掉签名普查、对象 DNA、投影和“收据”要求（蓝图、模型权威、收尾清单三篇）

Status: completed.

移除 blueprint/authority/closure 文档中的签名、DNA 与额外信任仪式，保留层级、端口、角色绑定、行为与影响追踪；363 项测试通过。

| Check | Exit | Actual result / log |
|---|---:|---|
| `residue` | 0 | (no output) (`WG-14/residue.log`) |
| `sizes` | 0 | 16644 total (`WG-14/sizes.log`) |
| `change` | 0 | REVIEW skills.worldguard.scripts: its files changed; update its description if behavior changed, then confirm skills.worldguard.scripts (`WG-14/change.log`) |
| `pytest` | 0 | 363 passed in 33.97s (`WG-14/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-14/map.log`) |

Adaptations: 按统一规则保留 SLIM_LOG.md 中历史术语；本项扫描只针对三个现行引用文件。

### WG-15: 精简合同和网格参考：预测覆盖规则单独成篇，交接规则并入 model-mesh.md

Status: completed.

预测覆盖规则迁至按需引用；网格交接规则合并为单一参考，合同说明反映可选 target_guards 的真实行为。363 项测试通过。

| Check | Exit | Actual result / log |
|---|---:|---|
| `references` | 0 | 12288 total (`WG-15/references.log`) |
| `change` | 0 | REVIEW skills.worldguard.scripts: its files changed; update its description if behavior changed, then confirm skills.worldguard.scripts (`WG-15/change.log`) |
| `pytest` | 0 | 363 passed in 36.25s (`WG-15/pytest.log`) |
| `map` | 0 | check: 0 error(s), 8 warning(s), 0 info (`WG-15/map.log`) |

Adaptations: predictive-coverage.md 实际 4532 字节（文档约 4533）；逐段语义保持，预测实现和网格交接执行未改。

### WG-16: 任务内参考改用便携命令；事实修订参考写出命令；模板包标成可选；加提示词大小测试

Status: completed.

任务内命令改为跨平台启动器路径，补事实修订命令，模板明确为单 Guard 可选脚手架；新增提示词大小上界测试并绑定原地图 owner，364 项测试通过。

| Check | Exit | Actual result / log |
|---|---:|---|
| `references` | 0 | (no output) (`WG-16/references.log`) |
| `change` | 0 | ARCH INFO duplicate_code worldguard.revision: 2 identical bodies (1858 AST nodes) in ['worldguard.revision']: skills/worldguard/runtime/worldguard/task_local_revision.py:evaluate_candidate_world_revision, worldguard/task (`WG-16/change.log`) |
| `pytest` | 0 | 364 passed in 49.76s (`WG-16/pytest.log`) |
| `map` | 0 | check: 0 error(s), 9 warning(s), 0 info (`WG-16/map.log`) |

Adaptations: 实际总数比文档多 3，来自已独立复核的 WG06 输入形状边界补测。

### WG-17: 删除已经失效的 FlowGuard 投影模块

Status: completed.

删除仅产生永久 gap 的旧 FlowGuard 投影适配器及 9 个导出、对应测试，保留原生蓝图。140 个剩余导出可加载，361 项测试和 6 个选中模型通过。

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | {"action":"check","authority":{"author_source":"worldguard","derived_projection":"skills/worldguard/runtime/worldguard","direction":"author_source_to_derived_projection_only"},"claim_boundary":"This audit proves raw-byte (`WG-17/mirror.log`) |
| `exports` | 0 | 140 ok (`WG-17/exports.log`) |
| `change` | 0 | ARCH INFO duplicate_code worldguard.templates: 2 identical bodies (513 AST nodes) in ['worldguard.templates']: skills/worldguard/runtime/worldguard/template_packs.py:run_template_pack_contract, worldguard/template_packs. (`WG-17/change.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-17/models.log`) |
| `pytest` | 0 | 361 passed in 72.27s (0:01:12) (`WG-17/pytest.log`) |
| `map` | 0 | check: 0 error(s), 9 warning(s), 0 info (`WG-17/map.log`) |

Adaptations: 完整测试实际 72.27 秒，未用文档预计时长替代实测。

### WG-18: 删除没人用的旧启动器；给 LogicWriting 真正依赖的便携启动器加测试

Status: completed.

删除未被技能引用的旧启动器；对真实启动器新增复制技能目录后执行 check 的行为测试，验证导入来自复制后的 runtime，357 项测试通过。

| Check | Exit | Actual result / log |
|---|---:|---|
| `launcher` | 0 | 7 passed in 3.73s (`WG-18/launcher.log`) |
| `inventory` | 0 | ['skills/worldguard/scripts/run_worldguard.py'] (`WG-18/inventory.log`) |
| `change` | 0 | REVIEW skills.worldguard.scripts: its files changed; update its description if behavior changed, then confirm skills.worldguard.scripts (`WG-18/change.log`) |
| `pytest` | 0 | 357 passed in 39.85s (`WG-18/pytest.log`) |
| `map` | 0 | check: 0 error(s), 9 warning(s), 0 info (`WG-18/map.log`) |

Adaptations: 脚本目录库存按 Git 跟踪文件核对，保留未跟踪的解释器缓存；真实启动器任何字节未改。

### WG-19: 单元检查总是直接执行：删除“调用方提供的 provider 收据回放”和“执行者身份”检查

Status: completed.

单元路径直接执行结构及语义 Guard；删除调用方 provider 收据回放和执行者身份记账，保留 provider_availability。7 项 qualification、348 项完整测试及 6 个模型通过，fuel_cell 输出 122688 字节。

| Check | Exit | Actual result / log |
|---|---:|---|
| `qualification` | 0 | 7 passed in 0.13s (`WG-19/qualification.log`) |
| `residue` | 0 | (no output) (`WG-19/residue.log`) |
| `mirror` | 0 | {"action":"check","authority":{"author_source":"worldguard","derived_projection":"skills/worldguard/runtime/worldguard","direction":"author_source_to_derived_projection_only"},"claim_boundary":"This audit proves raw-byte (`WG-19/mirror.log`) |
| `map-initial` | 1 | check: 1 error(s), 9 warning(s), 0 info (`WG-19/map-initial.log`) |
| `map` | 0 | check: 0 error(s), 9 warning(s), 0 info (`WG-19/map.log`) |
| `change` | 0 | ARCH INFO duplicate_code worldguard.core: 2 identical bodies (115 AST nodes) in ['worldguard.core']: skills/worldguard/runtime/worldguard/status.py:aggregate_statuses, worldguard/status.py:aggregate_statuses (`WG-19/change.log`) |
| `example` | 0 | 122688 (`WG-19/example.log`) |
| `pytest` | 0 | 348 passed in 48.66s (`WG-19/pytest.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-19/models.log`) |

Adaptations: 首次 map 发现文档预告的 worldguard.qualification→worldguard 无用依赖，删除该唯一已失效依赖后 map 0 errors；失败原日志保留。

### WG-20: 任务内修订闭环：自己运行候选网格，删除封签收据、depth-bind 和 revalidation-bind

Status: completed.

任务修订自行加载并执行候选网格一次；去除 depth/revalidation 封签绑定入口，工具计算省略的观测与覆盖指纹，保留缺口集合、停滞、预算、外部输入、回滚与独立留出规则。32 项任务测试、341 项完整测试和 6 个模型通过。

| Check | Exit | Actual result / log |
|---|---:|---|
| `mirror` | 0 | {"action":"check","authority":{"author_source":"worldguard","derived_projection":"skills/worldguard/runtime/worldguard","direction":"author_source_to_derived_projection_only"},"claim_boundary":"This audit proves raw-byte (`WG-20/mirror.log`) |
| `task-revision-initial` | 2 | 1 error in 0.32s (`WG-20/task-revision-initial.log`) |
| `task-revision` | 0 | 30 passed in 0.38s (`WG-20/task-revision.log`) |
| `map-initial` | 0 | check: 0 error(s), 9 warning(s), 0 info (`WG-20/map-initial.log`) |
| `scoped-revalidation` | 0 | 32 passed in 0.53s (`WG-20/scoped-revalidation.log`) |
| `cli-exports` | 0 | 135 ok (`WG-20/cli-exports.log`) |
| `residue` | 0 | (no output) (`WG-20/residue.log`) |
| `mirror-final` | 0 | {"action":"check","authority":{"author_source":"worldguard","derived_projection":"skills/worldguard/runtime/worldguard","direction":"author_source_to_derived_projection_only"},"claim_boundary":"This audit proves raw-byte (`WG-20/mirror-final.log`) |
| `change` | 0 | ARCH INFO duplicate_code worldguard.templates: 2 identical bodies (513 AST nodes) in ['worldguard.templates']: skills/worldguard/runtime/worldguard/template_packs.py:run_template_pack_contract, worldguard/template_packs. (`WG-20/change.log`) |
| `pytest` | 0 | 341 passed in 38.96s (`WG-20/pytest.log`) |
| `map` | 0 | check: 0 error(s), 9 warning(s), 0 info (`WG-20/map.log`) |
| `models` | 0 | models: 6 passed, 0 failed (`WG-20/models.log`) |

Adaptations: 参考片段跨节点合并 scope 会丢失现有 per_model_node 边界；沿用现有按节点 scope 覆盖并匹配 fresh receipt.node_id，两个有限正反例均断言只执行一次。负例保留原生 PASS/license 与全局并集，仅本节点缺 holdout 输出，确由 semantic_role_scope_not_executed 拒绝。首次作者脚本在测试迁移前断言停止造成 collection failure，保留原记录；完成迁移后通过。实际测试总数比文档多 5（WG06 3＋本项 2）。
