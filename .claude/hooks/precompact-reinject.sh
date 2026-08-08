#!/bin/bash
# SessionStart hook (matcher: "compact") — fires at the start of the new
# session immediately after Claude Code compacts (summarises) context,
# whether triggered manually (/compact) or automatically. Purpose: the
# active phase's directive and the standing engineering rules are exactly
# the things a summarisation pass is most likely to blur or drop. This
# re-surfaces them via additionalContext so the agent doesn't quietly drift
# after compaction on a long session.
#
# VERIFIED against https://code.claude.com/docs/en/hooks.md (fetched
# 2026-07-05): a PreCompact hook fires BEFORE compaction and only supports
# decision control (block/allow the compaction itself, via a top-level
# "decision" field) — its stdout is NOT injected as context afterward.
# The documented mechanism for re-injecting content after compaction is
# SessionStart with matcher "compact", returning
# hookSpecificOutput.additionalContext. This script is wired to
# SessionStart/"compact" in .claude/settings.local.json, not to PreCompact —
# despite the filename (kept for continuity with what it's named elsewhere).

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
OWNERSHIP_FILE="$PROJECT_DIR/.claude/phase-ownership.json"
ACTIVE_PHASE=$(jq -r '.active_phase' "$OWNERSHIP_FILE" 2>/dev/null || echo "unknown")

CONTEXT=$(cat << CONTEXT_EOF
=== RE-ANCHORING CONTEXT AFTER COMPACTION ===
--- CLAUDE.md ---
$(cat "$PROJECT_DIR/CLAUDE.md" 2>/dev/null || echo "(CLAUDE.md not found)")

--- Active phase: $ACTIVE_PHASE ---
Full detail in docs/PHASE_DIRECTIVE.md — re-read that phase's section now.

--- Standing rules (non-negotiable, every phase) ---
- decimal-only money handling, never float, currency-aware rounding
- every automated inference is user-correctable and audit-logged, never destructive
- migrations committed alongside the models they define
- risk-based tests only for: money handling, dedup, reconciliation, FX conversion, idempotency
- do not touch files outside .claude/phase-ownership.json's active phase without asking
CONTEXT_EOF
)

jq -n --arg ctx "$CONTEXT" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
exit 0
