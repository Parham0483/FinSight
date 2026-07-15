#!/bin/bash
# PreToolUse hook — blocks Edit/Write calls that touch a path owned by a phase
# other than the currently active one, per .claude/phase-ownership.json.
#
# This exists because PHASE1_COORDINATION.md's "DO NOT TOUCH" list is prose —
# prose can be missed in a long session or after context compaction. This
# makes the same rule impossible to violate instead of merely discouraged.
#
# VERIFIED against https://code.claude.com/docs/en/hooks.md (PreToolUse section,
# fetched 2026-07-05): .tool_input.file_path is the correct field for Edit/Write.
# permissionDecision values "allow"/"deny"/"ask"/"defer" are current and correct.

set -euo pipefail

OWNERSHIP_FILE="$CLAUDE_PROJECT_DIR/.claude/phase-ownership.json"
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0   # not a file-editing tool call, allow

# Make path relative to project root for matching against ownership.json
REL_PATH="${FILE_PATH#"$CLAUDE_PROJECT_DIR"/}"

ACTIVE_PHASE=$(jq -r '.active_phase' "$OWNERSHIP_FILE")

# Does this path fall under a phase OTHER than the active one?
OWNING_PHASE=$(jq -r --arg p "$REL_PATH" '
  .phases | to_entries[] |
  select(.value.owns | any(. as $prefix | $p | startswith($prefix))) |
  .key
' "$OWNERSHIP_FILE" | head -1)

if [ -n "$OWNING_PHASE" ] && [ "$OWNING_PHASE" != "$ACTIVE_PHASE" ]; then
  jq -n --arg reason "Blocked: '$REL_PATH' is owned by '$OWNING_PHASE', but active phase is '$ACTIVE_PHASE'. Per PHASE1_COORDINATION.md collision-avoidance map, do not edit another phase's files without an explicit human instruction to change .claude/phase-ownership.json first." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 0
fi

# Shared/coordinate-first paths: warn but don't hard-block (these need judgment,
# not a flat rule) — surfaced as feedback so Claude sees it before proceeding.
COORDINATE=$(jq -r --arg p "$REL_PATH" '
  .shared_coordinate_before_edit // [] | any(. as $prefix | $p | startswith($prefix))
' "$OWNERSHIP_FILE")

if [ "$COORDINATE" = "true" ]; then
  jq -n --arg reason "'$REL_PATH' is flagged shared_coordinate_before_edit (e.g. customers-vs-counterparties unification is unresolved territory). Proceed only if this edit is part of the explicitly planned migration, not incidentally." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $reason}}'
  exit 0
fi

exit 0
