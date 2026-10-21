## Why

WorldGuard v0.4.1 tag and release point to the intended commit, but `pyproject.toml` and bundled runtime identify 0.4.1 while source `worldguard/__init__.py` still identifies 0.4.0. Existing parity tests make this a released-content defect, and observed FlowGuard model authority is also absent.

## What Changes

- Align source and bundled runtime version/content to the sole v0.4.1 contract.
- Complete or explicitly supersede remaining current maintenance checks.
- Establish and audit one observed FlowGuard model-system snapshot.
- Carry the repair into the same frozen v0.5.0 candidate as fact-level revision,
  while retaining this change as the explicit defect and currentness boundary.

## Capabilities

### New Capabilities

- `worldguard-source-projection-currentness`: Defines source/bundled/package version parity, maintenance disposition, and observed model authority.

## Impact

Affected surfaces: source/bundled runtime version and parity tests, FlowGuard authority/adoption, remaining maintenance tasks, and the v0.5.0 version/changelog/release evidence.
