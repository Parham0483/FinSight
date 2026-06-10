# FinSight — Product Blueprint v2

> Refined 2026-06-10. Supersedes the v1 strategy (maturity tiers + document
> extraction + mascot UX), which it keeps, corrects, and extends.
> Two goals drive every decision here:
> 1. **Genuinely help any business that struggles with cash flow.**
> 2. **Be a defensible, demo-able flagship project for a fintech master's
>    application** — every feature should produce a measurable claim.

---

## 1. The problem, stated precisely

SMEs don't die from lack of profit; they die from **cash-flow timing**.
The three concrete failure modes:

1. **Late-paying customers** — invoices exist but cash arrives weeks after
   the due date (DSO problem). #1 cause of SME insolvency.
2. **Invisible obligations** — recurring bills, tax deadlines, payroll, and
   loan repayments that surprise an owner who manages by bank-balance.
3. **No forward view** — owners see today's balance, not the balance in
   45 days, so corrective action (chase an invoice, delay a purchase,
   arrange financing) happens too late or never.

A forecast alone fixes #3. The platform must also fix #1 (payment-behaviour
modelling) and #2 (obligation detection), and then close the loop with
**actions** (scenarios, alerts, reminders) — a forecast nobody acts on has
no value.

---

## 2. Logic corrections to the v1 design

### 2.1 Maturity = data **quality score**, not calendar span

v1 computes stage from the span between earliest and latest transaction.
Flaws: 3 transactions spanning 181 days would rate "expert"; a sparse,
uncategorised ledger rates equal to a clean reconciled one.

**v2: composite DataMaturity score (0–100), computed from:**

| Component | Weight | Measures |
|---|---|---|
| History span | 30% | days between first and last transaction (capped at 365) |
| Coverage density | 25% | days-with-data ÷ span (gaps reduce score) |
| Categorisation rate | 15% | % of transactions with a category |
| Source reliability | 15% | bank-connected > documents > manual |
| Reconciliation rate | 10% | % of invoices/documents matched to transactions |
| Recency | 5% | days since last data point (stale data decays) |

Stages map from the score (new <5, learning 5–25, developing 25–50,
established 50–75, expert 75+). Keeps the existing five-stage UX, mascot
moods, and capability gating untouched — only the input becomes honest.

**Explicit fast-forward rule:** importing two years of bank history on day
one *should* jump an org to established/expert immediately. This is a
feature — the onboarding wizard and mascot must say "import history to
fast-forward" — not an accident of the formula.

### 2.2 Gate **confidence**, not visibility

v1 hides longer horizons until a stage unlocks them. For a finance product
this is the wrong axiom: the honest statement is never "no 90-day forecast",
it is "a 90-day forecast with wide uncertainty".

**v2: every forecast is probabilistic** (P10/P50/P90 quantile bands).
Maturity controls:
- which horizons are shown **with confidence** (narrow bands, "certified"),
- which are shown **greyed with wide bands** ("I can guess, but give me
  more data and watch this band narrow").

The engagement loop gets *stronger*: users watch the uncertainty band
visibly narrow as data accumulates — the mascot's "I'm learning" becomes a
measurable, visual fact. Feature-level gates (scenarios, FX exposure,
seasonal intelligence) remain stage-gated as in v1.

### 2.3 Accuracy must be a **system**, not a slogan

v1 says "forecast accuracy is a core requirement" with no mechanism.

**v2: forecast accountability loop:**
- Every forecast run is persisted (ForecastRun model already exists).
- A nightly job scores past runs against actuals once the horizon elapses:
  MAPE for point forecasts, **pinball loss** for quantiles, plus calibration
  (did 80% of actuals fall inside the P10–P90 band?).
- Accuracy per horizon is **shown to the user** ("my 30-day forecasts for
  you have been within ±8%") — trust through verification, and the single
  best interview/demo artefact the project can produce.
- Backtesting harness: replay any org's history, forecasting from each
  historical point — model changes ship only if backtests improve.

---

## 3. The forecasting engine (new — v1 never specified it)

Hybrid three-layer architecture, industry standard for cash-flow (cf.
Agicap, Float) and far more defensible than a single ML model:

### Layer 1 — Known flows (deterministic ledger)
Future-dated certain/near-certain cash events, projected directly:
- AR: open invoices with due dates (from documents pipeline or manual)
- AP: bills payable, detected recurring obligations
- Payroll, rent, loan schedules, tax deadlines (region-aware later)
- **Recurring-transaction detection engine** feeds this layer: interval
  clustering per counterparty (weekly/monthly/quarterly + amount tolerance)
  promotes detected patterns into projected obligations the user confirms.

### Layer 2 — Behavioural adjustment (the differentiator)
Known flows are wrong in *timing*: customers pay late. Per-customer
**payment-behaviour profiles** learn the distribution of (paid_date −
due_date) from history. An invoice due June 1 from a customer with median
+12 days lateness lands in the forecast where it will actually arrive — and
the engine ships a per-customer reliability score (a soft credit-risk
signal: "Acme pays 12±4 days late, deteriorating").

### Layer 3 — Unknown flows (statistical) + Monte Carlo assembly
Variable inflows/outflows that aren't invoice-backed, forecast with
maturity-appropriate models:
- learning: weekly-pattern naive + trailing average
- developing: ETS / seasonal decomposition (statsmodels)
- established+: gradient boosting with calendar features, or Prophet-class
  models, selected by backtest score per org

**Assembly:** Monte Carlo simulation (~1,000 paths) samples Layer-2 payment
timings and Layer-3 residuals → daily balance distribution → P10/P50/P90
bands, **probability-of-cash-out date**, and safety-buffer breach risk.

### Outputs the engine must expose
- Daily projected balance with quantile bands per horizon (7/30/90/365)
- **Runway**: most-likely and worst-case cash-out dates
- Per-driver attribution ("the dip on July 3 is payroll + Acme's likely-late
  invoice") — drives the insights app and the mascot's concerned mood.

---

## 4. Closing the loop: from forecast to action

### Scenario planning (stage: established)
Forked forecast with what-if levers, diffed against baseline:
delay/accelerate an invoice, add a hire (recurring outflow), one-off
purchase, financing injection, price/volume change. UI: side-by-side bands.
This is the feature that *helps*; the forecast only informs.

### Alerts (the existing shell, now specified)
- Projected breach of safety buffer within N days (P10 path)
- Invoice overdue / customer behaviour deteriorating
- Detected new recurring obligation awaiting confirmation
- Forecast-vs-actual drift beyond threshold (model health)
Delivery: in-app via mascot (concerned mood) + email digest.

### Collections assistant (stage: developing+)
AR aging view, one-click polite reminder emails generated by Claude with
invoice context, escalating tone sequences. Directly attacks failure mode
#1 and demos beautifully.

---

## 5. Data architecture completions

- **Unified ingestion**: bank feed (TrueLayer), documents (existing 4-tier
  extraction), CSV import, manual entry — all normalise into Transaction
  with `source` + `confidence`; the existing fuzzy-matcher reconciles
  documents↔transactions, and reconciliation feeds the maturity score.
- **Transaction enrichment**: hierarchical category taxonomy; auto-
  categorisation via embeddings/Claude with the same tiered cost discipline
  as extraction; counterparty resolution (normalise "AMZN*MKTP" → Amazon).
- **Multi-currency**: store original amount+currency and base-currency
  equivalent at transaction-date rate; forecast in base currency; FX
  exposure report (established+) shows sensitivity to rate moves.
- **CSV import** ships before bank integration polish — fastest path to
  real data and the demo backbone.
- **Synthetic-org generator** (management command): realistic seasonal SME
  patterns (café, agency, e-commerce) for demo mode, screenshots, and
  backtest fixtures.

## 6. Trust infrastructure (cheap now, expensive later)

Fintech-grade posture, mostly already started (Fernet, httpOnly JWT,
rotation, throttling). Add: append-only audit log of mutations; org-scoped
RBAC honouring the new accountant role (read+annotate, no money-moving
config); GDPR export/delete per org; idempotent webhook ingestion;
`decimal`-only money handling (never float) with currency-aware rounding.

## 7. Differentiation map — what no competitor does

Every incumbent (Agicap, Float, Fathom, Causal, Finmark, QuickBooks/Xero
planners) shares five assumptions. Each one is an opening:

### 7.1 They assume accounting software → **document-first onboarding**
Competitors onboard via Xero/QuickBooks integration. The majority of SMEs
globally — and almost all in emerging markets — run on invoices, bank SMS,
and spreadsheets. FinSight's 4-tier extraction already means a business can
**photograph a stack of invoices and have a working forecast** with no
finance stack at all. Make this the positioning headline: *"forecasting
for the spreadsheet-and-shoebox majority."* Later extension: a
WhatsApp/Telegram bot — snap a receipt in chat, the bot confirms the
extraction. No incumbent can onboard these businesses at all.

### 7.2 They output dashboards → **ask-your-forecast (conversational explainability)**
Forecasts elsewhere are black-box lines. FinSight's driver attribution
(§3) becomes an interface: the mascot answers *"why is July risky?"* with
an answer **grounded in the org's own ledger and forecast decomposition**
("payroll on the 1st + Acme's invoice will likely arrive 12 days late").
Strict grounding rule: the LLM narrates retrieved attribution data, never
computes numbers. This turns the mascot from delight into the product's
primary interface — and no competitor has an interrogable forecast.

### 7.3 They forecast the expected → **SME stress tests (Cash Resilience Score)**
Banks stress-test; SMEs never get to. On top of the Monte Carlo engine,
one-click standardised shocks: top customer churns, all receivables slip
30 days, 15% FX devaluation, 20% demand dip. Output: survival horizon per
shock + a single **Cash Resilience Score (0–100)** that trends over time.
Bank-grade risk methodology brought to a café owner — new to the segment,
and a master's-thesis topic in itself.

### 7.4 They are West-centric → **regional financial calendar intelligence**
Seasonality models elsewhere know Christmas. A *global* SME platform must
know Ramadan and Eid cash patterns, Nowruz, Chinese New Year, Diwali,
per-country tax deadlines and payday conventions. Implementation is cheap
(calendar feature library feeding Layer 1 obligations and Layer 3
features); the differentiation for non-Western markets is enormous.

### 7.5 They keep accuracy private → **the lender-ready pack**
The accountability loop (§2.3) produces something novel: a *verified
forecast track record*. Export a financing dossier — cash history, forecast
bands, and "this platform's 30-day forecasts for this business have been
within ±X% for N months" — turning forecast credibility into a **portable
credit signal** for loan applications. Research-adjacent (open-banking
credit signalling) and a genuine new artefact in the space.

### Designed-for-later (needs user scale, schema designed now)
Anonymised peer benchmarking: "your DSO is 12 days worse than similar
agencies." Network-effect moat; ship only with enough orgs and a
differential-privacy review.

---

## 8. Build order

| Phase | Scope | Proves |
|---|---|---|
| **1. Data backbone** | Transactions API, CSV import, categories, synthetic-org generator, tests | end-to-end data flow; source-agnostic ingestion wedge (§7.1) |
| **2. Engine v1** | Layer 1+3 (known flows + naive/ETS), quantile bands, runway, dashboard chart, regional calendar feature library (§7.4) | probabilistic forecasting |
| **3. Accountability** | ForecastRun scoring job, accuracy display, backtest harness | "verifiably accurate" |
| **4. Behaviour layer** | recurring detection, payment-behaviour profiles, Monte Carlo assembly | the core differentiator |
| **5. Action + risk layer** | alerts, scenario planning, collections assistant, **stress tests + Cash Resilience Score** (§7.3) | forecast → decision |
| **6. Intelligence layer** | **ask-your-forecast grounded chat** (§7.2), AI briefings, maturity v2 composite scoring | explainability |
| **7. Reach** | TrueLayer live, multi-currency/FX exposure, **lender-ready pack** (§7.5), WhatsApp/Telegram ingestion bot (§7.1), benchmarking schema | platform completeness |

Tests are written with each phase (TDD, 80% target), not retrofitted.
Phases 1–4 are the dissertation-grade core; 5–7 are each independently
demo-able capstones — ship in order, stop anywhere and still have a
coherent product.

## 9. Resume / master's-application framing

Every phase yields a concrete claim:
- "Probabilistic cash-flow engine (Monte Carlo over learned payment-
  behaviour distributions); 30-day P50 within X% MAPE on backtests."
- "Cost-optimised LLM document pipeline: 4-tier escalation, ~$0.003/doc
  average, confidence-routed."
- "Forecast accountability: automated pinball-loss scoring + calibration
  monitoring of every shipped forecast."
- "Bank-style stress testing for SMEs: standardised shock library over a
  Monte Carlo engine, summarised as a Cash Resilience Score."
- "Grounded conversational explainability: LLM narrates forecast
  attribution, computes nothing — zero-hallucination by construction."
- "Multi-tenant Django/DRF with encrypted bank tokens, rotating httpOnly
  JWT, audit logging."
- Thesis-adjacent topics: SME credit-risk signals from payment behaviour;
  verified forecast track records as portable credit signals; uncertainty
  communication in consumer fintech UX (the maturity/mascot system is
  literally a study in this); financial inclusion via document-first
  onboarding in low-formalisation economies.
