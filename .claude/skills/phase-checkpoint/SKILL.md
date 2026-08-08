---
name: phase-checkpoint
description: Use when finishing a phase and preparing a checkpoint report for human review, or when starting a new phase's worktree. Covers what "done" means, how to report status, and how to hand off to the next phase.
---

# Phase checkpoint protocol

FinSight development proceeds in worktree-per-phase increments (see `docs/PHASE_DIRECTIVE.md`).
Full stop at the end of every phase — do not open the next phase's worktree until the human
explicitly approves.

## Before declaring a phase done

1. Run the `phase-boundary-auditor` subagent against the current diff. Do not self-report
   completion without this — it exists specifically to catch what the implementing agent is
   too close to the work to see.
2. Confirm every item in the phase's exit checklist in `docs/PHASE_DIRECTIVE.md` has direct
   evidence (a model, service, test, or endpoint), not just a claim.
3. Confirm `.claude/phase-ownership.json` doesn't need updating for the next phase (new apps
   created this phase should be added to the next phase's `owns` list if they didn't exist
   when the ownership file was drafted).

## Checkpoint report format

- What shipped, mapped directly to the phase's checklist items
- What didn't ship and why (be specific — "ran out of time" vs "blocked on decision X")
- Output of the phase-boundary-auditor subagent, included verbatim
- Any drift discovered between the current repo state and what `docs/SYSTEM_GAP_REPORT.md`
  (or its latest `_v2`, `_v3`, ... version) recorded
- Explicit ask: "ready to open the Phase N+1 worktree?" — do not proceed without a yes

## Starting the next phase

1. Update `.claude/phase-ownership.json`'s `active_phase` field
2. Re-read the new phase's section of `docs/PHASE_DIRECTIVE.md` in full
3. Confirm Step 0 (re-verification against stale docs) isn't needed again — only required
   once at the very start, not per-phase, unless significant time has passed since the last
   checkpoint
