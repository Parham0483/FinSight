# FinSight — Phase Directive (Post Phase-1 Audit)

Author: Parham Golmohammadi, drafted with Claude
Supersedes: nothing — this extends `PRODUCT_BLUEPRINT.md`, `PHASE1_COORDINATION.md`,
`SYSTEM_GAP_REPORT.md` (all dated 2026-06-11) with resolved decisions and a build order.
Read all four before starting. This doc is the answer key to the open questions in
`PHASE1_COORDINATION.md` §4 and the sequencing plan for `SYSTEM_GAP_REPORT.md`'s 47 missing items.

**Working model:** worktree-per-phase (matches the existing Phase-1 agent pattern). One phase,
one worktree, one branch. Full stop at the end of every phase for human review — do not start
the next phase's worktree until explicitly told to proceed.

**Timeline:** target is a strong, demoable Phase 1–4 core in 8–10 weeks (before MSc starts
~mid-September 2026), with Phase 5 attempted opportunistically if time allows. If any phase
overruns its budget by more than ~1 week, stop and flag it at the next checkpoint instead of
silently descoping — the cut decision is Parham's to make, not the agent's.

---

## Step 0 — Mandatory, before any new work

The audit docs are three weeks old. Do not trust them blindly.

1. Check current `git log`, `git worktree list`, and diff against what
   `PHASE1_COORDINATION.md` describes as the worktree HEAD (`0b94452` + uncommitted changes).
2. Re-run the 82-item checklist logic from `SYSTEM_GAP_REPORT.md` against the **current** repo
   state — not the recorded one. Produce `SYSTEM_GAP_REPORT_v2.md` with the same format
   (✅/🟡/❌, main/wt/none, evidence) so drift since 2026-06-11 is visible.
3. Report back before proceeding: did anything change since the audit? Is the Phase-1
   worktree still uncommitted? Are there any files/apps not covered by the original audit?

Do not begin Phase 1 close-out (below) until this comes back clean.

---

## Resolved decisions (previously open questions)

These answer `PHASE1_COORDINATION.md` §4 directly:

1. **Counterparty absorbs Customer.** Customer does not stay as a parallel directory.
   - Migration: create a `Counterparty` (type=`customer`) row for every existing `Customer`;
     repoint `Invoice.customer` FK to `Invoice.counterparty` (constrained to type=`customer`);
     carry `Customer.risk_score` over as a field or note on Counterparty for now — it will be
     superseded properly by the Phase 5 CustomerScorecard, don't over-engineer it today.
   - Retire the `customers` app once the migration is verified against real/synthetic data —
     don't leave it in place "just in case."
   - **This migration is also where the fuzzy-matcher gap closes.** Generalise the existing
     rapidfuzz logic in `documents/services/matching.py` (currently `_match_customer` against
     the old Customer model) to match against Counterparty instead. Two open gaps, one piece
     of work — do them together, not sequentially.
2. **Rollup endpoints:** keep the primary implementation at `/transactions/rollup/`. Add a thin
   `/counterparties/rollup/` alias that calls the same underlying logic, filtered to counterparty
   dimensions — satisfies blueprint item 51 without duplicating rollup logic.
3. **CounterpartyTag/Group:** no separate model. The existing ArrayField tags are adequate.
   Revisit only if a real need for tag hierarchies/groups emerges — don't build it speculatively.
4. **Testing bar:** risk-based, not blanket 80% coverage. Mandatory tests for: money/decimal
   handling, cross-source dedup, reconciliation matching, FX conversion and rate overrides,
   idempotency (retried transactions, webhook replays), and the counterparty merge/soft-merge
   logic. Standard CRUD/serializer paths get light smoke tests, not exhaustive coverage. Do not
   chase a coverage percentage — chase "the expensive-to-get-wrong logic is tested."
5. **Scope target:** Phases 1–4 are the committed core and must be finished properly. Phase 5 is
   attempted after, in this priority order (see Phase 5 section for why):
   1. Stress tests + Cash Resilience Score
   2. Customer scorecards
   3. Alerts + collections assistant (cut first if time is short)

---

## Phase 1 close-out (before Phase 2 starts)

Per `SYSTEM_GAP_REPORT.md`, still open within Phase 1 scope:

- [ ] Execute the Counterparty/Customer migration + fuzzy-matcher generalisation above
- [ ] Auto-categorisation service: rule-check-before-LLM, wiring categories onto transactions
      at ingest (categories app already has taxonomy + seeds — this is the missing service layer)
- [ ] Synthetic-org generator (management command) — **do this early, not last.** Every
      following phase needs realistic demo/backtest data (café, agency, e-commerce seasonal
      patterns per the blueprint). Building it late means demoing nothing convincingly for weeks.
- [ ] Risk-based tests per decision #4 above, for `transactions/` and `counterparties/`
- [ ] Confirm `DataMaturity` composite scorer matches blueprint v2.2 methodology (§2.1),
      not just data-days
- [ ] Bank-feed/accounting-API/document adapters into the `IngestionSource` contract — CSV +
      manual already exist; port the rest only as far as needed to unblock realistic synthetic
      data generation. Full TrueLayer-live polish is explicitly Phase 7 — don't gold-plate this now.

**Checkpoint 1:** stop here. Report status against the checklist above, plus `SYSTEM_GAP_REPORT_v2.md`
diffed against v1. Wait for sign-off before opening the Phase 2 worktree.

---

## Phase 2 — Engine v1 (per blueprint §3, §8)

- [ ] Layer 1: deterministic ledger of known flows (AR/AP with due dates, payroll/rent/loan
      schedules, recurring obligations promoted from detection)
- [ ] Layer 3: maturity-appropriate statistical forecasting — start with weekly-pattern naive +
      trailing average (learning stage) and ETS/seasonal decomposition (developing stage) via
      statsmodels. Gradient boosting / Prophet-class models are explicitly a later refinement,
      not a Phase 2 requirement — don't over-build this before Phase 3 tells you if it's accurate.
- [ ] Quantile bands (P10/P50/P90) on daily projected balance, runway (most-likely + worst-case
      cash-out dates), driver attribution feeding the dashboard chart
- [ ] Regional calendar feature library (§7.4) — footprint-derived from org's actual country
      code + counterparty countries + currencies, not user-toggled
- [ ] FX service v1: two provider sources, published rate = median, basic divergence flagging.
      Full dual-rate/adaptive-refresh sophistication (§5.1) is Phase 7 — v1 just needs to be
      *correct and honest*, not exhaustive

**Checkpoint 2:** stop here. Demo the dashboard chart with quantile bands on synthetic-org data
before continuing.

---

## Phase 3 — Accountability (per blueprint §2.3, §8)

- [ ] ForecastRun scoring job: WAPE (primary) + MASE against a seasonal-naive baseline
- [ ] Pinball loss + coverage of the P10–P90 band (target 80%), scored per horizon
- [ ] Accuracy display surfaced to the user — this is explicitly the single best demo/interview
      artefact per the blueprint; do not deprioritise it in favour of more forecasting
      sophistication
- [ ] Backtesting harness: rolling-origin cross-validation over synthetic-org history, strict
      temporal splits, no leakage

**Checkpoint 3:** stop here. The number "our 30-day forecasts are within ±X%" must be real and
reproducible before moving on.

---

## Phase 4 — Behaviour layer (per blueprint §3 Layer 2, §8) — the core differentiator

- [ ] Recurring-transaction detection: interval clustering per counterparty (weekly/monthly/
      quarterly + amount tolerance), promoted to projected obligations pending user confirmation
- [ ] Payment-behaviour profiles: per-customer distribution of (paid_date − due_date), reliability
      score, feeding Layer 1 timing
- [ ] Monte Carlo assembly (~1,000 paths) sampling Layer 2 timing + Layer 3 residuals →
      daily balance distribution, probability-of-cash-out date, safety-buffer breach risk

**Checkpoint 4:** stop here. This is the phase that makes FinSight more than a dashboard —
confirm the behavioural adjustment is visibly changing forecast timing on synthetic data with
known injected lateness patterns before calling it done.

---

## Phase 5 — Action + risk layer (attempt in this order; cut from the bottom if time is short)

1. **Stress tests + Cash Resilience Score (§7.3).** Reuses the Phase 4 Monte Carlo engine
   directly — apply a shock (customer churn, 30-day receivables slip, FX devaluation calibrated
   from realised volatility, demand dip) and rerun the simulation. Cheapest Phase 5 item given
   Phase 4 is done, and the highest demo/interview payoff.
2. **Customer scorecards (Value/Reliability/Risk, §4).** Reuses Counterparty + the payment-
   behaviour profiles from Phase 4. Medium effort — RFM/DSO/CLV-lite are citable, not invented.
3. **Alerts + collections assistant.** Lowest priority of the three — genuinely separate build
   (rules engine, email digest, Claude-generated reminder sequences). Cut this first if the
   8–10 week window is tight; it's valuable but the least differentiated of the three.

**Checkpoint 5:** stop here regardless of how far through the list you got. Report what shipped
and what didn't — a partial, honest Phase 5 is fine; the blueprint itself calls Phases 5–7
independently demo-able capstones, not a single unit that must complete together.

---

## Explicitly out of scope for now — do not start these without a direct instruction

Xero/QuickBooks/Sage/Zoho connectors · WhatsApp/Telegram ingestion bot · lender-ready pack export ·
peer benchmarking · full dual-rate/adaptive-refresh FX (§5.1 in full) · CI eval suite for chat
(there is no chat yet — Phase 6) · anonymised global rule promotion across orgs.

These are real, in the blueprint, and worth building eventually — they are Phase 6–7 or later.
An agent picking up spare capacity should ask before touching them, not assume they're helpful
extras.

---

## Standing engineering rules (carry through every phase)

- `decimal`-only money handling, never float, currency-aware rounding — no exceptions
- Every mutation from an automated inference (categorisation, counterparty merge, FX rate,
  recurring-obligation detection) is user-correctable and audit-logged, never destructive
- Migrations committed alongside the models they define — no uncommitted schema drift between
  worktree and main (this was flagged as a real risk in the Phase-1 coordination doc; don't repeat it)
- Tests per decision #4 above, written with the phase, not retrofitted after checkpoint sign-off
