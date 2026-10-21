## Why

WorldGuard already performs task-local prediction, observation, revision, replay, and holdout checks, but revision remains coarse at the world-state level. Contradictory and incomplete fact support therefore cannot be revised transactionally without risking silent loss of independent facts or accidental classical collapse.

## What Changes

- Add fact-level support records and strict rules with four-valued `true`, `false`, `both`, and `neither` evaluation.
- Compute a candidate revision transaction without mutating the accepted world state.
- Require closure, contradiction visibility, named preserved facts, and regression/holdout evidence before activation.
- Keep this as an extension of the existing task-local world revision owner, not a new Guard or alternate runtime.
- Keep source and bundled skill runtime byte-aligned, and extend prompt/reference, CLI, FlowGuard model, tests, installation, and release evidence.

## Capabilities

### New Capabilities

- `fact-level-world-revision`: Defines four-valued fact support, strict-rule closure, transaction preview, preservation, and activation receipts.

## Impact

Affected surfaces: WorldGuard runtime and bundled runtime, task-local revision/CLI/report contracts, prompts/references, FlowGuard model and behavior ledger, tests, SkillGuard maintenance inputs, README, version, and release metadata.
