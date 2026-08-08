# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Model Selection

Choose the model per task using this routing table. Default to **Sonnet** for
general development work.

| Model | Use for |
|-------|---------|
| **opusplan** (Opus for planning) | Counterparty/Customer migration, Monte Carlo design, idempotency/dedup logic |
| **fable** | Phase 4 (behavioural layer) and Phase 5 (stress tests) full-phase execution |
| **haiku** | Formatting, simple smoke tests, boilerplate scaffolding |
| **sonnet** (default) | All other development work |

For each task, pick the model based on the table above before starting.

## Phase discipline

This project builds in worktree-per-phase increments. The current phase and file ownership
are tracked in `.claude/phase-ownership.json` — **read it before editing anything**, and know
that edits outside the active phase's owned paths are hook-blocked, not just discouraged.

Full stop at the end of every phase. See the `phase-checkpoint` skill for what a checkpoint
report needs to contain before requesting to proceed.

## Testing bar (overrides any global default for this project)

Risk-based, not blanket coverage: mandatory tests for money/decimal handling, cross-source
dedup, reconciliation matching, FX conversion/overrides, idempotency, and counterparty
merge logic. Standard CRUD/serializer paths get light smoke tests only. See the
`money-handling` skill for the specific invariants these tests need to check.

## Reference docs (read on demand, not every session)

- `docs/PRODUCT_BLUEPRINT.md` — full product spec, why decisions were made
- `docs/PHASE_DIRECTIVE.md` — the build order, phase-by-phase, with exit checklists
- `docs/PHASE1_COORDINATION.md`, `docs/SYSTEM_GAP_REPORT.md` (or latest `_v2`+) — current
  state audits; check these are still fresh (recent date) before trusting them blindly
