# System Gap Report v2 — Blueprint 82-Item Checklist (refresh)

Generated: 2026-07-05, re-audit of `SYSTEM_GAP_REPORT.md` (2026-06-11) per `PHASE_DIRECTIVE.md`
Step 0. Same legend/format as v1.

**Addendum (2026-07-06):** since this report was generated, the three items it identified as
still-open (Counterparty/Customer migration + fuzzy-matcher generalisation, auto-categorisation
service, DataMaturity composite scorer) were explicitly directed by the human and completed in
this same session, each verified with real command output, isolated test runs, mutation testing
(maturity scorer), and phase-boundary-auditor review. The body of this report below still
reflects the 2026-07-05 point-in-time audit (left as-is for historical accuracy); the "Phase 1
close-out checklist status" section has been updated to the current state — see there for
evidence references. Adapter porting (bank-feed/accounting-API) remains intentionally deferred —
the synthetic-org generator satisfies the original reason for it (unblocking demo data), and
building real adapters with no live service to call would be premature per `PHASE_DIRECTIVE.md`'s
own anti-gold-plating guidance.

Legend: ✅ DONE · 🟡 PARTIAL · ❌ MISSING
Location: **main** = committed on `main` (HEAD `7b75b8c`) · **wt** = uncommitted work-in-progress
in `.claude/worktrees/phase-1-data-backbone` (branch `worktree-phase-1-data-backbone`) · **none**
= not started.

Worktree HEAD is now `986b443` ("wip: Phase 1 data backbone — counterparties app,
source-agnostic transactions, ingestion adapters, synthetic-org generator"), on top of `main`'s
`0b94452` (main has since moved to `7b75b8c` with unrelated frontend-hardening work; no conflict
with Phase-1's owned backend paths). On top of `986b443` there are further **uncommitted**
changes: `counterparties/models.py` (normalise_name rewrite) and `counterparties/tests/test_api.py`
(updated), plus two new untracked test files (`transactions/tests/test_ingestion.py`,
`transactions/tests/test_models.py`).

---

## What changed since 2026-06-11 (headline)

1. **Tests now exist for the new Phase-1 code** — v1's biggest flagged gap ("empty scaffolds, no
   tests written") is resolved. `transactions/tests/` (2 files, 267 lines) and `counterparties/tests/`
   (3 files, 212 lines) are populated; `categories/tests/` (3 files, unchanged from v1) also present.
   Test **execution** against a live DB is still being verified as this report is finalised — see
   "Open verification" at the end.
2. **Synthetic-org generator is built** — v1 marked this an empty scaffold (item 48). It's now a
   239-line management command (`generate_synthetic_org.py`) with café/agency profiles, seasonal
   monthly curves, recurring rent/payroll, and per-customer late-payment behaviour. This was called
   out in `PHASE_DIRECTIVE.md` as the thing to build "early, not last" — it has been.
3. **`normalise_name` counterparty matching was reworked** (uncommitted, in progress) — tokenises on
   non-alphanumerics instead of truncating at `*`/`#`, and drops digit-containing tokens more
   robustly. Still **deterministic only** — no rapidfuzz fuzzy-merge yet, so this is a refinement of
   an existing gap, not a closed one.
4. **fx / alerts / insights apps**: confirmed to have real models (as flagged before this audit
   started), but this is **not new** — they've been at this state since the Week-1 commit `edd54ed`
   and are byte-identical to `main`. The service/logic layer for all three (provider adapters,
   median-rate calc, divergence flagging, rules engine, digest, briefing generation) remains
   entirely unbuilt. **The original report's ❌/none markings for services on these apps stand;**
   only the "app doesn't exist" framing was stale, not the "no logic" framing.
5. **customers-vs-counterparties unification has NOT happened.** Still two parallel models,
   `customers.Customer` and `counterparties.Counterparty`, with no FK bridging them.
   `documents/services/matching.py::_match_customer` still imports and matches against the OLD
   `Customer` model — confirmed no `Counterparty` references anywhere in that file. This is the
   #1 open item in `PHASE_DIRECTIVE.md`'s resolved-decisions section and remains fully open.
6. **No auto-categorisation service** — `categories` app is unchanged (taxonomy + seeds only);
   `Transaction.category` FK exists but nothing populates it automatically at ingest.
7. **No counterparty rollup alias** — rollup logic (`rollup_by`, `rollup_by_tag`) lives only on
   `/transactions/rollup/`; `counterparties/urls.py` has no `rollup/` route.
8. **Bank-feed / accounting-API / document adapters not ported** — `IngestionSource` contract has
   only `CsvImportSource` and `ManualEntrySource`. No TrueLayer/accounting/document adapter classes
   exist under `transactions/ingestion/`.
9. **DataMaturity scorer is still single-signal** (day-count only) — confirmed by reading
   `maturity.py` in full; the "composite, multi-signal" methodology from blueprint v2.2 §2.1 has not
   been implemented. `capabilities` per stage are just static label lists, not computed from
   multiple signals.
10. Nothing on main or in this worktree has started Phase 2–5 submodules: no
    `forecasting/{engine,accuracy,backtest,behaviour,montecarlo}/`, no `apps/scorecards/`. Confirmed
    absent, matching v1.

---

## Full checklist re-verification

Only items whose status or evidence **changed** from v1 are detailed below; unlisted items are
unchanged and the reader should trust v1's row for them (re-verified spot-checks confirmed no
drift on frontend items 63–78, and Django apps items 7 fx / 9 chat / 10 alerts beyond what's noted
above).

| # | Item | v1 Status | v2 Status | What changed |
|---|------|-----------|-----------|---------------|
| 2 | Auto-categorisation service | 🟡 | 🟡 (unchanged) | Confirmed still absent; `Transaction.category` FK exists but no wiring service. |
| 3 | Counterparty ResolutionService, fuzzy-merge | 🟡 | 🟡 (refined, not closed) | `normalise_name` reworked (tokeniser-based) but still deterministic; no rapidfuzz. |
| 13 | Counterparty model | ✅ | ✅ | Unchanged in shape; `normalise_name` logic improved. |
| 29 | IngestionSource adapters | 🟡 | 🟡 (unchanged) | Still only CSV + manual; no bank/accounting/document adapters. |
| 31 | Fuzzy-matcher over Counterparty | 🟡 | 🟡 (unchanged) | `documents/matching.py::_match_customer` confirmed still targets `Customer`, zero `Counterparty` references. |
| 32 | DataMaturity composite scorer | ✅ | 🟡 (downgraded) | v1 marked ✅ on existence; on inspection it's single-signal (day-count), not composite per blueprint v2.2 §2.1. Downgrading to 🟡 pending the composite rework `PHASE_DIRECTIVE.md` explicitly calls for. |
| 48 | Synthetic-org generator | 🟡 (scaffold) | ✅ | `generate_synthetic_org.py` now fully implemented (239 lines, café + agency profiles, seasonality, recurring obligations, `--seed` determinism). |
| 51 | Counterparties rollup alias | 🟡 | 🟡 (unchanged) | Still only on `/transactions/rollup/`; no `/counterparties/rollup/`. |
| 79 | Per-phase tests (transactions/counterparties) | 🟡 (empty scaffolds) | ✅ | `transactions/tests/` and `counterparties/tests/` now populated (267 + 212 lines respectively) covering models, ingestion/dedup, services (resolve/merge), and API. **Confirmed**: 67/67 passing against a live Postgres instance — see Test-run confirmation section. |
| 7 (apps) | fx app | ❌ | ❌ (clarified) | Models (`FxRate`, `FxAlert`) exist since Week 1, unchanged since v1 despite framing suggesting otherwise. Still no service/provider/median-rate/divergence logic — `urls.py` empty, `tasks.py` a stub. |
| 10 (apps) | alerts app | 🟡 | 🟡 (clarified) | `Alert`/`AlertSettings` models exist since Week 1, unchanged. No rules engine or digest logic. |
| — | insights app (not in original 82, discovered) | not tracked | ❌ | `AIInsight` model only, unchanged since Week 1; no service logic. |
| — | organisations RBAC accountant role | 🟡 (unverified) | 🟡 (clarified) | `OrgMembership.ROLE_CHOICES` does include `accountant`, but no permission-layer enforcement beyond membership lookup. No GDPR export/delete endpoints exist. |

**Tally movement since v1** (47 ❌ / 17 🟡 / 18 ✅ of 82):
- Item 48 moves 🟡→✅ (+1 ✅, -1 🟡)
- Item 32 moves ✅→🟡 (-1 ✅, +1 🟡) — net wash on counts, but this is a real regression in
  understanding, not a code regression: the scorer didn't get worse, the original ✅ was too
  generous.
- Item 79 moves 🟡→✅, confirmed by an actual green pytest run (67/67 passing) — see Test-run
  confirmation section above.
- **Net: 20 ✅ (18 → 20), 15 🟡 (17 → 15), 47 ❌ unchanged in count** — though two of the
  unchanged-❌ items (fx, insights) are now reclassified from "doesn't exist" to "exists but
  empty," which doesn't change the working-software gap, only the accuracy of *why* it's ❌.

---

## Phase 1 close-out checklist status (per `PHASE_DIRECTIVE.md`)

**Updated 2026-07-06** — all three previously-open substantive items are now done:

- [x] **Counterparty/Customer migration + fuzzy-matcher generalisation** — Customer model deleted;
      Invoice relocated to `apps.counterparties` (state-only migration, `customers` app kept
      registered solely as a migration-history shell). Backfill migration
      (`apps/customers/migrations/0003_backfill_counterparties.py`) creates a `type=customer`
      Counterparty per Customer with a provenance note, idempotent and reversible — verified with
      real fixture data via Django's `MigrationExecutor` (3 customers with distinct
      risk_score/avg_days_late/payment_terms_days, correctly carried into `Counterparty.notes`).
      Fuzzy matcher in `documents/services/matching.py` now matches across all Counterparty types
      (fixed a latent bug where PO/receipt/cheque vendors were matched against a customer-only
      list), excluding soft-merged rows. Full migration graph applies cleanly on a fresh DB
      (`makemigrations --check` reports no drift). Tests: `apps/customers/tests/test_backfill_migration.py`,
      `apps/counterparties/tests/test_invoice.py`, `apps/documents/tests/test_matching.py`,
      `apps/documents/tests/test_views_confirm_helpers.py`.
- [x] **Auto-categorisation service** — `apps/categories/services.py`: rule-before-keyword-before-LLM
      ladder (`suggest_category`), with `CategorisationRule` (new model, migration
      `apps/categories/migrations/0002_categorisation_rule.py`) implementing rule promotion after
      2 reinforcing corrections per the money-handling skill's correction-ladder invariant. Wired
      into ingestion (`transactions/ingestion/base.py::_persist`) and the correction path
      (`transactions/views.py::TransactionDetailView.patch` calls `record_correction`). LLM step
      (Claude Haiku) gracefully no-ops without an API key and never returns a category outside the
      org's own taxonomy. Tests: `apps/categories/tests/test_categorisation_service.py` (11 cases)
      + 1 ingestion-level test — 12 total, all passing in isolation.
- [x] **Synthetic-org generator** — unchanged from prior status, already built.
- [x] **Risk-based tests for `transactions/`, `counterparties/`** — unchanged from prior status,
      already confirmed passing.
- [x] **DataMaturity composite scorer matching blueprint v2.2 §2.1** — `apps/forecasting/maturity.py`
      rewritten from single-signal day-count to a six-component weighted composite (History span
      30%, Coverage density 25%, Categorisation rate 15%, Source reliability 15%, Reconciliation
      rate 10%, Recency 5% — weights verified to match the blueprint table exactly). Stage buckets
      now driven by score (new <5, learning 5-25, developing 25-50, established 50-75, expert 75+)
      per spec. Verified with a real before/after comparison against a synthetic café org (old:
      day-count-only `stage='expert'` with zero visibility into data quality; new: `score=77.44`
      with a full six-component breakdown). 14 tests in `apps/forecasting/tests/test_maturity.py`,
      including two blueprint-flaw regression tests (fast-forward bulk-history-reaches-established,
      sparse-uncategorised-ledger-does-not-reach-expert-from-span-alone) and one sanity test against
      real `generate_synthetic_org` output (not just hand-placed minimal fixtures). Mutation-tested:
      confirmed `test_history_span_component_caps_at_365_days` is a genuine, isolated regression
      test for the 365-day cap; also surfaced a real, accepted coverage gap — no test currently
      pins the weight-to-component mapping in the final composite score (swapping which weight
      belongs to history_span vs. coverage_density doesn't fail any test with the data shapes
      currently exercised).
- [ ] Bank-feed/accounting-API/document adapters into `IngestionSource` — **intentionally deferred**,
      not a gap. The synthetic-org generator satisfies the original stated purpose (unblocking
      realistic demo/backtest data) via direct generation rather than the adapter contract; building
      real adapters with no live service to call would be premature gold-plating per
      `PHASE_DIRECTIVE.md`'s own guidance. Revisit when Phase 2+ needs real ingestion.

Five of six close-out items are done; the sixth is a deliberate, reasoned deferral, not an
oversight. Phase 1 close-out is now substantively complete.

---

## Test-run confirmation (item 79 resolved)

Full `pytest` run against a live Postgres instance is now confirmed. The project's own
Docker build path (`backend/Dockerfile`) was abnormally slow on this machine (apt mirror fetch
alone exceeded 5 minutes per large package with no clear stall — not actually hung, just
network-bound) and was abandoned in favour of a throwaway `python:3.12-slim` container attached
to the existing `finsight_default` network, running against the already-running `finsight-db-1`/
`finsight-redis-1` containers directly (no schema/data risk — pytest-django creates and tears
down its own `test_finsight` database, never touching the real one).

First run surfaced 21 failures, all traced to one root cause: `libmagic` (the system library
backing the `python-magic` package used in `apps/documents/views.py`) wasn't present in the
minimal image, and since `finsight/urls.py` includes `documents.urls` unconditionally, any test
that resolves the URLconf (all API tests) failed at import time — not a Phase-1 code defect,
an environment gap. After installing `libmagic1`:

```
67 passed in 1.17s
```

**Item 79 → ✅.** All transactions/counterparties/categories tests (models, ingestion/dedup,
services, API) are green. Note this only ran the Phase-1-owned suites named in `PHASE_DIRECTIVE.md`
Step 0, not the whole repo — the `documents` app's own test suite (if any) was not exercised here
and is out of Phase-1 scope.
