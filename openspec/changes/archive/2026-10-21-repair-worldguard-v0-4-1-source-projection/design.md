## Context

The release identity is correct but its content is internally inconsistent. The fix is direct current replacement, not a compatibility alias.

## Goals / Non-Goals

**Goals**

- Restore source/bundled/package parity and current model authority.
- Keep the released defect repair separately auditable while validating and
  publishing it in the same frozen v0.5.0 candidate.

**Non-Goals**

- No fact-level revision or new route.

## Decisions

1. v0.4.1 remains historical; source currentness is corrected in v0.5.0
   because the user authorized one uninterrupted combined upgrade.
2. Bundled runtime is regenerated/copied from the exact source owner and parity-tested.
3. Unfinished maintenance items use exact current receipts or explicit successor disposition.
4. Snapshot bootstrap follows passing parity/model evidence.

## Risks / Trade-offs

Bundled parity edits invalidate maintenance receipts and require fresh validation.

## Migration Plan

Fix parity first, then add fact-level behavior, freeze both changes together,
bootstrap/audit authority, and publish one v0.5.0 release.
