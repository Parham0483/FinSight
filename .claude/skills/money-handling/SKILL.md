---
name: money-handling
description: Use whenever writing or reviewing code that touches money amounts, currency conversion, transaction processing, or any automated inference (categorisation, counterparty merge, FX rates, recurring-obligation detection). Non-negotiable rules from PRODUCT_BLUEPRINT.md sections 5.2 and 6.
---

# Money handling and human-in-the-loop rules

These are correctness requirements, not style preferences. Violating them is the kind of bug
the risk-based testing bar in `docs/PHASE_DIRECTIVE.md` exists specifically to catch.

## Money representation

- `decimal` only, never `float`, anywhere money is stored, computed, or compared
- Currency-aware rounding — rounding rules differ by currency (not all currencies have 2
  decimal places), don't hardcode `.2f`-style assumptions
- Store original amount + currency AND base-currency equivalent at transaction-date rate —
  never discard the original

## Idempotency

- Retried transactions (webhook replays, sync retries) must not double-process. Use
  `dedup_hash` (amount + date + counterparty, per the existing pattern in
  `transactions/ingestion/base.py`) before persisting, not after
- Webhook ingestion in particular must be idempotent by design, not by accident

## Human-in-the-loop (every automated inference is correctable)

Every machine inference — categorisation, counterparty merge, FX rate, recurring-obligation
detection — follows three invariants:

1. **Corrections are audit-logged, never destructive.** The machine's original answer is
   preserved alongside the human's correction, always.
2. **Corrections propagate.** Dependent forecasts and reports recompute when a correction
   changes an upstream value.
3. **Corrections teach**, in this strict order of preference (don't skip to a fancier
   mechanism when a simpler one applies):
   - Rule promotion (a correction repeated N=2 times becomes a deterministic rule, checked
     before any LLM call)
   - Correction memory (few-shot retrieval for non-rule-shaped corrections)
   - Statistical tuning (provider weights, match thresholds, confidence cutoffs)
   - Eval + regression test (every correction becomes a permanent regression test)

If you're implementing a feature that involves any kind of automated guess, and it doesn't
have a correction path that satisfies these three invariants, it isn't done — flag it in the
checkpoint report rather than shipping it silently incomplete.
