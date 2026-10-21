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
