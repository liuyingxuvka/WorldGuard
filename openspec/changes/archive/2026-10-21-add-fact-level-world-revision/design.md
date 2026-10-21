## Context

Task-local revision already owns the outer state machine. Fact-level revision is a subordinate transaction that evaluates inconsistent/incomplete support without mutating the accepted world until closure and preservation checks pass.

## Goals / Non-Goals

**Goals**

- Preserve positive and negative support independently.
- Apply strict rules to a four-valued closure.
- Preview, validate, and activate one transaction with a receipt.

**Non-Goals**

- No new Guard or global belief database.
- No explosion from contradiction and no closed-world negation.
- No hidden mutation before activation.

## Decisions

1. Each `WorldFact` has a stable id; `FactSupport` independently supports truth or falsity and records source/evidence.
2. Strict rules derive signed facts only when all antecedent signs are present.
3. A fact evaluates to `true`, `false`, `both`, or `neither`.
4. A `FactRevisionTransaction` contains additions, retractions by support id, declared preserved facts, and expected terminal deltas.
5. Preview computes closure on a copy. Activation requires current base fingerprint, completed closure, visible contradictions, preservation pass, regressions, and holdout evidence.
6. Runtime and bundled skill runtime share the same implementation bytes.

## Risks / Trade-offs

- Closure can loop; finite signed fact/rule ids and fixpoint detection bound execution.
- Retraction can have non-local effects; receipt includes changed closure and preserved-fact outcomes.

## Migration Plan

Migrate the behavior ledger, add fact revision beneath the current owner, update model/tests/contracts, activate a current model revision, then release v0.5.0.
