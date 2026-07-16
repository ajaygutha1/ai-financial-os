# AI Financial OS — Master Architecture & Milestone Plan

## Context

The goal is to build a production-quality "AI Financial Operating System" — a unified financial
data platform with explainable, agentic AI on top — engineered to the bar of a senior fintech
team (Stripe/Ramp/Plaid-caliber), not a toy budgeting app. Given the enormous scope (12+
subsystems: multi-source ingestion, a financial analytics engine, 8 AI agents, RAG, a full audit/
explainability system, a real-time dashboard, security hardening), the right approach is to lock
the target architecture and a full milestone sequence *before* writing code, then build one
vertical slice at a time so nothing gets rebuilt later. This plan covers that full architecture,
the complete milestone roadmap, and a fully detailed spec for Milestone 1 (the only milestone we
build now — later milestones are re-planned in detail when we reach them, since requirements may
shift).

**Decisions already locked in with the user:**
1. New project at `~/Projects/ai-financial-os`, fresh git repo (currently does not exist).
2. AI provider: Claude API (Anthropic) directly, but every agent/tool/RAG component talks to a
   thin `AIProvider` adapter interface, never the Anthropic SDK directly — so swapping/adding
   providers later means writing one new adapter class. No heavyweight multi-provider framework
   (e.g. LiteLLM) now — premature for this stage.
3. Data connectors: build against stubbed/mocked connectors (Plaid/Coinbase/brokerage) first;
   CSV import is the one *real* ingestion path in Milestone 1 since it needs no external creds.
4. Milestone 1 = foundation: Docker Compose skeleton, FastAPI clean-architecture skeleton,
   Postgres schema + Alembic migration 0001, JWT + Google/GitHub OAuth, CSV import →
   normalization → stored transactions, Next.js dashboard shell (login, transactions table, net
   worth tile), CI for both services.

Additional judgment calls (my recommendation, not yet run by the user — flagged for the exit-plan
question round): Python tooling = `uv` + `ruff` + `mypy` (fast, modern, matches the "senior fintech
engineer" bar); frontend package manager = `pnpm`.

---

## Target Architecture (steady state — what M1 starts and later milestones grow into)

### Repo layout — monorepo
```
ai-financial-os/
├── api/            # FastAPI backend
├── web/             # Next.js frontend
├── docs/             # ADRs, ERD
├── docker-compose.yml
├── .github/workflows/{api-ci.yml, web-ci.yml}
└── .env.example
```
Monorepo because the DB schema, AI response contracts, and frontend types must evolve in lockstep
across ~10 milestones — one PR should be able to touch a migration, a service, and a dashboard
component atomically. Each app keeps its own dependency manifest and Dockerfile, so they remain
independently deployable containers despite living in one repo.

### Backend clean-architecture layering
`routers → services → repositories → models`, with `ai/`, `ingestion/`, `analytics/`, `jobs/`,
`notifications/` as peer top-level modules (not nested inside `services/`) since each grows its
own test suite and Celery tasks independently. Rule: `ai` may call `services`/`repositories`, never
the reverse; only `ai/provider/anthropic_provider.py` may `import anthropic`.

```
api/app/
├── main.py
├── core/            # config, security (JWT/OAuth), db, redis, logging, exceptions
├── models/           # SQLAlchemy ORM (one file per aggregate)
├── schemas/           # Pydantic DTOs
├── routers/v1/         # thin HTTP layer
├── services/          # business logic
├── repositories/        # DB access
├── ingestion/
│   ├── connectors/       # base.py Connector protocol; csv.py now, plaid/coinbase/ofx/robinhood later
│   └── normalization/     # parser, merchant_normalizer, deduplicator, pipeline
├── analytics/           # engine.py registry + modules/ (M3+)
├── ai/                # provider/, agents/, tools/, rag/, prompts/, audit.py (M4+, empty stubs in M1)
└── jobs/               # celery_app.py + tasks/ (M2+)
```

### AI adapter interface (designed now conceptually, built in M4)
```python
class AIProvider(ABC):
    async def generate_structured(self, *, system, messages, response_model, tools=None, metadata): ...
    async def stream(self, *, system, messages, metadata): ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```
Every AI call carries `AICallMetadata{user_id, agent_name, prompt_version, purpose}`; the adapter
wraps every underlying call with a persisted audit record (prompt, response, model, tokens,
latency, retrieved doc IDs, tool calls) *before* returning — so audit logging is structurally
impossible to bypass, not something each agent has to remember to do. This is the mechanism that
satisfies "never allow black-box recommendations."

### Database — now vs. later
Build now (M1): `users`, `oauth_accounts`, `accounts`, `transactions`, `audit_log`. All PKs are
UUIDs so every later FK target is stable. `transactions.category`/`merchant_normalized` are plain
string columns in M1 — deliberately, so promoting them to first-class `category`/`merchant` tables
in M2 is an additive migration, not a redesign. `accounts.account_type` and
`transactions.transaction_type`/`import_source` enums already include values reserved for later
milestones (investment, crypto, dividend, plaid, etc.) so M2+ never needs an enum migration.
Deferred tables (built when their milestone arrives): `category`/`merchant`, `investment_holding`/
`tax_lot`/`security`, `recurring_bill`, `goal`, `analytics_result`, `ai_audit_log`/
`ai_recommendation`/`agent_run`, `rag_document`/`rag_chunk` (pgvector), `connector_credential`/
`sync_job`.

### Frontend — Next.js App Router
```
web/app/(auth)/{login,callback/[provider]}/page.tsx
web/app/(dashboard)/layout.tsx            # sidebar+topbar, auth guard
web/app/(dashboard)/{dashboard,transactions}/page.tsx
web/components/{ui (shadcn), dashboard/, transactions/}
web/lib/{api-client.ts, query-keys.ts}
web/hooks/{use-auth.ts, use-transactions.ts, ...}
web/schemas/                                # Zod, single source of truth for RHF + response validation
web/middleware.ts                           # route protection
```

### Docker Compose (M1: postgres, redis, api, web; M2+ adds worker/beat)
Health checks on postgres/redis gate api startup so `alembic upgrade head` doesn't race a
not-ready DB. Source mounted as volumes in dev for hot reload.

---

## Full Milestone Roadmap (M1 → production-grade v1)

| # | Milestone | Goal | Unblocks |
|---|---|---|---|
| **M1** | Foundation, Auth, CSV | Login, CSV import, transactions + net worth visible | Everything — sets schema/layering/CI patterns |
| M2 | Ingestion breadth + normalization engine | OFX/QFX + stubbed Plaid/Coinbase/Robinhood connectors behind `Connector` protocol; real merchant/dedup/currency/transfer engine; Celery+Redis workers enter Compose | M3 (analytics needs multi-source data) |
| M3 | Financial analytics engine | Modular `analytics/modules/*`: cash flow, net worth, burn rate, savings rate, debt payoff, expense trends, subscriptions, emergency fund, ratios | M4 (agents need numbers to cite) |
| M4 | AI adapter + first agent + audit plumbing | `AIProvider`/Anthropic adapter, `ai_audit_log`/`ai_recommendation` tables, one agent (Financial Advisor) end-to-end with citations to real calculations | M5 (RAG plugs into proven pattern), M6 |
| M5 | RAG pipeline | pgvector, hybrid retrieval (vector+keyword), IRS/SEC/Investopedia corpus, citations wired into Financial Advisor | M6 |
| M6 | Remaining agents | Investment Analyst, Expense Analyst, Tax Advisor, Fraud Detection, Budget Coach, Retirement Planner, Portfolio Risk Analyst — same M4 pattern | M7 |
| M7 | Full dashboard | Every panel (allocation, debt, bills, budget, portfolio, insights, risk, forecasts, goals), near-real-time via SSE/polling | M8 |
| M8 | Security hardening | RBAC, rate limiting, JWT refresh hardening, secrets management, PII/credential encryption, OWASP pass | M9 (real creds shouldn't touch the system before this) |
| M9 | Real Plaid/Coinbase integration | Swap stub connectors for real ones (same protocol from M2 = additive, not a rewrite), Plaid Link, webhooks | M10 |
| M10 | Polish, observability, performance | OpenTelemetry, error tracking, load testing, AI cost tracking, Playwright E2E, prod Compose | Production-grade v1 |

Each milestone is a shippable, demoable vertical slice; none require reworking an earlier
milestone's schema or module boundaries because M1's schema and interfaces are designed with the
full roadmap in view (see "Database — now vs. later" above).

---

## Milestone 1 — Detailed Implementation Plan (build this now)

### `api/` structure
```
api/app/
├── main.py
├── core/{config,db,security,logging,exceptions}.py
├── models/{base,user,account,transaction,audit_log}.py
├── schemas/{auth,account,transaction,csv_import}.py
├── routers/v1/{auth,accounts,transactions,imports,analytics}.py
├── services/{auth_service,account_service,transaction_service,csv_import_service,net_worth_service}.py
├── repositories/{user,account,transaction,audit_log}_repository.py
├── ingestion/normalization/{parser,merchant_normalizer,deduplicator,pipeline}.py
└── ai/, analytics/, jobs/, notifications/   # __init__.py placeholders only, no logic yet
api/alembic/versions/0001_initial_schema.py
api/tests/{conftest,test_auth,test_csv_import,test_transactions,test_net_worth}.py
api/pyproject.toml, Dockerfile
```

### Migration `0001_initial_schema.py` — tables
All PKs `UUID` (`gen_random_uuid()` via `pgcrypto`), all tables get `created_at`/`updated_at`.

- **users**: `id`, `email` (unique), `hashed_password` (nullable — OAuth-only users), `full_name`,
  `is_active`, `is_verified`.
- **oauth_accounts**: `id`, `user_id` FK→users (cascade), `provider` (`google`|`github`),
  `provider_account_id`, `access_token_enc`/`refresh_token_enc` (nullable, real encryption in M8),
  unique(`provider`, `provider_account_id`).
- **accounts**: `id`, `user_id` FK, `name`, `institution_name`, `account_type` (enum incl.
  checking/savings/credit_card/investment/crypto/loan/mortgage/retirement/other — full set now to
  avoid enum migrations later), `account_subtype`, `currency`, `current_balance`,
  `available_balance`, `mask`, `source` (manual/csv_import/plaid/coinbase/ofx/robinhood),
  `external_account_id` (nullable), `is_active`; index(`user_id`).
- **transactions**: `id`, `user_id` FK, `account_id` FK (cascade), `posted_at`, `amount`
  numeric(18,4) (sign convention: negative=outflow), `currency`, `merchant_raw`,
  `merchant_normalized` (indexed), `description`, `category` (plain string in M1, promoted to FK
  table in M2), `transaction_type` (enum incl. purchase/payment/transfer/fee/interest/deposit/
  withdrawal/dividend/buy/sell/refund/other), `is_transfer`, `is_duplicate_of` (self-FK, nullable),
  `import_source`, `import_batch_id` (indexed), `external_transaction_id`, `raw_payload` jsonb;
  index(`user_id`,`posted_at desc`); partial unique(`account_id`,`external_transaction_id`) where
  not null.
- **audit_log** (generic system audit, separate from the AI-specific audit tables added in M4):
  `id`, `user_id` FK nullable, `event_type`, `resource_type`, `resource_id`, `metadata` jsonb,
  `ip_address`; index(`user_id`,`created_at desc`), index(`event_type`).

Migration enables `pgcrypto` only — **not** `pgvector` yet (added in M5 when actually used).

### Auth flow
- `POST /auth/register`, `POST /auth/login` → bcrypt via passlib; access JWT (15 min, in response
  body) + refresh JWT (14 days, `httpOnly`+`secure`+`SameSite=lax` cookie, never touched by JS).
- `POST /auth/refresh` validates the cookie, rotates it, issues a new access token. (Stateless for
  M1; Redis-backed revocation denylist is an M8 hardening addition, not needed yet.)
- OAuth (Google + GitHub via `authlib`): `GET /auth/oauth/{provider}` redirects with CSRF `state`;
  `GET /auth/oauth/{provider}/callback` validates state, exchanges code, fetches profile, then
  `auth_service.handle_oauth_login()` — link to existing `oauth_accounts` row, else link by
  verified email, else create new user — then issues tokens the same way as password login.

### CSV normalization pipeline (in order)
Upload+validate → parse (sniff delimiter/encoding, map common bank headers) → field normalization
(dates, `Decimal` amounts with a user-selected debit-sign convention) → merchant normalization
(regex/rule-based cleanup) → duplicate detection (hash on account+date+amount+merchant, plus a
±2-day fuzzy window for pending/posted dupes — flagged via `is_duplicate_of`, never silently
dropped) → bulk persist within one DB transaction, tagged with `import_batch_id` and `raw_payload`
→ return `CsvImportResult{imported_count, duplicate_count, error_count, errors}` + one `audit_log`
row. Synchronous in M1 (no Celery yet — files are small; async is a natural M2 upgrade).

### FastAPI endpoints
```
POST /api/v1/auth/{register,login,refresh,logout}
GET  /api/v1/auth/oauth/{provider}
GET  /api/v1/auth/oauth/{provider}/callback
GET  /api/v1/auth/me
GET  /api/v1/accounts            POST /api/v1/accounts          GET /api/v1/accounts/{id}
GET  /api/v1/transactions?account_id=&from=&to=&page=&page_size=
POST /api/v1/imports/csv
GET  /api/v1/analytics/net-worth
GET  /health
```

### Next.js pages/components
`(auth)/login`, `(auth)/callback/[provider]`, `(dashboard)/layout` (sidebar/topbar + auth guard),
`(dashboard)/dashboard` (`NetWorthTile`), `(dashboard)/transactions` (`TransactionsTable`,
`ImportCsvDialog`); `components/auth/{LoginForm,OAuthButtons}`; `hooks/use-{auth,accounts,
transactions,csv-import}.ts`; `schemas/{auth,transaction}.ts` (Zod); `lib/api-client.ts` (attaches
token, retries once through `/auth/refresh` on 401); `middleware.ts` (redirects unauthenticated
users to `/login`).

### CI
`.github/workflows/api-ci.yml` (path-filtered to `api/**`): postgres+redis service containers →
`ruff check`/`format --check` → `mypy` → `alembic upgrade head` → `pytest --cov`.
`.github/workflows/web-ci.yml` (path-filtered to `web/**`): `pnpm install` → `eslint` →
`tsc --noEmit` → `pnpm build`. Both are required status checks on `main`. Playwright E2E is
deliberately deferred to M10.

---

## Verification (Milestone 1)

1. `docker compose up` brings up postgres/redis/api/web all healthy; `alembic upgrade head` runs
   cleanly against a fresh DB.
2. `pytest` (api) and `ruff`/`mypy` pass; `pnpm build`/`tsc --noEmit`/`eslint` pass (web).
3. Manual E2E in browser: register → login → (optionally) OAuth login with Google/GitHub sandbox
   creds → upload a sample CSV → see imported transactions in the table with duplicates flagged →
   see net worth tile reflect account balances.
4. Re-upload the same CSV and confirm duplicate detection flags rows instead of double-inserting.
5. Push a test branch and confirm both GitHub Actions workflows go green.

---

## Milestone 2 — Detailed Implementation Plan (built and verified)

Goal: ingestion breadth (real OFX/QFX parsing + stubbed Plaid/Coinbase/Robinhood
connectors behind one shared protocol) and the real normalization engine M1
deliberately deferred (currency conversion, transfer detection, refund matching,
ACH/wire classification), plus five additive architecture enhancements approved
during M2 planning that harden the ingestion path without touching M1's existing
schema or module boundaries.

### Connector protocol

`ingestion/connectors/base.py` defines a `Connector` protocol every source
implements identically:
```python
class Connector(Protocol):
    def fetch_accounts(self) -> list[RawAccount]: ...
    def fetch_transactions(self, cursor: str | None) -> tuple[list[RawTransaction], str | None]: ...
```
The `cursor` parameter mirrors real Plaid's `/transactions/sync` API shape
deliberately — so M9's swap from stub to real Plaid is a new file implementing
this same protocol, not a redesign.

- `ingestion/connectors/ofx.py` — real parsing via `ofxparse`/`ofxtools`, feeding
  the same normalization pipeline CSV already uses.
- `ingestion/connectors/{plaid,coinbase,robinhood}_stub.py` — deterministic fake
  data shaped like each provider's real API/export format.

### Category & merchant promotion

Additive migration `0002`: new `category` and `merchant` tables, plus nullable
`category_id`/`merchant_id` FK columns on `transactions`. The normalization
pipeline now writes only the FK columns going forward; the old
`category`/`merchant_normalized` string columns are left in place, unpopulated,
for this milestone — no backfill and no drop yet. The contract phase (backfill
existing rows, then drop the string columns) is deferred to a later migration,
following the non-disruptive expand/contract path M1's schema was designed to
allow.

### Normalization engine additions

`ingestion/normalization/{currency_converter,transfer_detector}.py` plus
extensions to the existing merchant/dedup modules for refund matching and
ACH/wire classification — same rule-based style as M1's merchant normalizer, no
new abstraction layer.

### Celery + Redis become active infrastructure

`jobs/celery_app.py` + `jobs/tasks/sync_accounts.py`; `docker-compose.yml` gains
`worker` and `beat` services. Recurring/automated sync is the reason M2, not M1,
is when Celery actually starts doing work.

### New/extended tables (migration `0002`)

| Table | Columns added |
|---|---|
| `category` | `id`, `name`, `parent_id` (self-FK, hierarchical) |
| `merchant` | `id`, `canonical_name`, `category_id` (FK) |
| `connector_credential` | `id`, `user_id` FK, `provider`, encrypted-placeholder token fields (real encryption in M8) |
| `sync_job` | `id`, `account_id` FK, `status`, `started_at`, `finished_at`, `cursor_before`, `cursor_after`, `idempotency_key` (unique), `reconciliation_status`, `discrepancy_amount` |
| `domain_events` | `id`, `event_type`, `payload` jsonb, `aggregate_type`, `aggregate_id`, `occurred_at` |
| `transaction_provenance` | `id`, `transaction_id` FK, `sync_job_id` FK, `step`, `detail` jsonb, `created_at` |

### Enhancement 1 — Domain Events + Event Bus

Additive event emission alongside existing service writes — not full event
sourcing, so nothing about how state is read or written today changes.
`app/events/domain_event.py` (Pydantic event models: `TransactionImported`,
`SyncCompleted`, `DuplicateDetected`, `TransferDetected`), `app/events/event_bus.py`
(`record()` durably persists the event in the same DB transaction as the write
it accompanies; `dispatch()` does best-effort in-process + optional Redis
pub/sub fan-out after commit), called from `csv_import_service.py`,
`ofx_import_service.py`, and the new `sync_service.py`. Unblocks: M3 (invalidate
analytics cache on new-transaction events instead of polling), M4 (agents react to
events), M7 (SSE live dashboard), M9 (webhooks map directly onto this bus).

### Enhancement 2 — Immutable, Tamper-Evident Audit Log

Hardens M1's `audit_log` table: a migration adds `REVOKE UPDATE, DELETE` for the
app role (or a rejecting trigger), plus optional `prev_hash`/`row_hash` columns so
each row's hash depends on the previous row's — tampering with history breaks the
chain. Sets the pattern M4's `ai_audit_log` inherits from day one.

### Enhancement 3 — Data Lineage & Transaction Provenance

Formalizes M1's loose `raw_payload`/`import_source`/`import_batch_id` tracking:
the normalization pipeline now emits a step-by-step trace (what changed, at which
step) into `transaction_provenance`, linked to the `sync_job` that produced it.
Optional `GET /transactions/{id}/provenance` endpoint. This is the same data
shape M4's AI agents will need to cite "which transactions were analyzed" —
built here for free instead of retrofitted later.

### Enhancement 4 — Idempotent, Cursor-Based Incremental Sync

Every `sync_job` carries `cursor_before`/`cursor_after` and a unique
`idempotency_key`, so a crashed or retried sync can't double-insert. This is the
same cursor-based model real Plaid's `/transactions/sync` API uses, so M9's real
integration is a drop-in against an already-correct sync model.

### Enhancement 5 — Balance Reconciliation Engine

`app/analytics/reconciliation.py` (placed next to where M3's analytics engine
will live — reconciliation status is itself a small analytic) verifies
`starting_balance + sum(transactions since) == reported_current_balance` after
every sync, storing `reconciliation_status`/`discrepancy_amount` on `sync_job`.
Surfaces to M7's dashboard as a data-health indicator; M6's Fraud Detection agent
can later consume unresolved discrepancies as a signal.

None of the five enhancements require new infrastructure beyond Postgres + Redis +
Celery already in `docker-compose.yml` — all extend the `sync_job` table and
normalization pipeline M2 already plans, not parallel subsystems.

## Milestone 3 — Detailed Implementation Plan (built and verified)

Goal: the modular financial analytics engine M1/M2 deliberately deferred --
cash flow, net worth, burn rate, savings rate, debt payoff, expense trends,
subscription detection, emergency fund health, and financial ratios -- computed
from the real transaction/account data M1/M2 already ingest, with no new
tables. Unblocks M4 (agents need real numbers to cite).

### The sign-convention design decision

The one subtlety the whole milestone hinges on: `transaction.amount` is signed
relative to *its own account's* balance (`balance_before + amount ==
balance_after`, per M2's reconciliation engine), not the user's total wealth.
A positive amount is income on a checking/savings account but a new charge
(real spending) on a credit card; a negative amount is an expense on
checking/savings but a payment/credit on a credit card. `transaction_type`
turned out *not* to be a usable classifier for this -- the M1/M2 pipelines
default every non-transfer row to `PURCHASE` regardless of sign. So
`app/analytics/common.py` classifies income/expense per transaction by
`account_type` instead, documented in one place and reused by every module
that needs it (`cash_flow`, `burn_rate`, `savings_rate`, `expense_trends`,
`subscriptions`, `emergency_fund`, `debt_payoff`, `ratios`). Loans/mortgages
are excluded from the expense side entirely -- there's no "purchase" concept
there, only balance-reducing payments already reflected in the paying
account's own outflow.

### Structure

```
api/app/analytics/
├── common.py           # MonthlyFlow, month_start/add_months, classify_flow, monthly_income_and_expenses
├── engine.py            # AnalyticsEngine registry -- routers call modules directly for static typing;
│                         # the registry exists so M4's agents get one generic run(metric, user_id, **params)
├── modules/
│   ├── net_worth.py      # migrated from the M1 NetWorthService (deleted)
│   ├── cash_flow.py, burn_rate.py, savings_rate.py
│   ├── expense_trends.py  # category-level rising/falling/steady vs. trailing average
│   ├── subscriptions.py   # rule-based: >=2 charges, consistent cadence + amount within 10%
│   ├── emergency_fund.py  # liquid assets / trailing avg. expenses, tiered health label
│   ├── debt_payoff.py     # naive projection from trailing net paydown rate
│   └── ratios.py          # composes emergency_fund/net_worth rather than re-deriving them
└── reconciliation.py (M2, unchanged)
```

Every response schema (`app/schemas/analytics.py`) carries a `methodology`
string alongside the numbers -- cheap to add now, and it's exactly the
"why was this computed this way" text M4's explainability requirement needs
agents to cite. `TransactionRepository.list_for_analytics()` adds one
unpaginated, date-bounded fetch with `account`/`category_ref` eager-loaded,
reused by every module instead of each hand-rolling a query.

### Endpoints

`GET /api/v1/analytics/{net-worth,cash-flow,burn-rate,savings-rate,
expense-trends,subscriptions,emergency-fund,debt-payoff,ratios}`, each
accepting an optional `months` window. 104 backend tests (up from 84),
covering empty-state and realistic scenarios per module -- the trickiest
category was date construction: tests originally placed "this month" fixtures
at fixed day offsets, which silently broke depending on what day of the month
the suite happened to run (a transaction dated after "today" is correctly
excluded by the date-bounded query, so a fixture at day 6 fails if the suite
runs on day 3). Fixed by using `date.today()` directly for single-day
fixtures and fully-elapsed prior months for anything needing multiple
distinct dates.

### Frontend

Six new dashboard widgets (`CashFlowChart`, `FinancialRatiosTile`,
`EmergencyFundTile`, `ExpenseTrendsCard`, `SubscriptionsCard`,
`DebtPayoffCard`) share one `AnalyticsCard` wrapper for the
loading/error/content pattern `NetWorthTile` established in M1. Savings rate
and burn rate are folded into one `FinancialRatiosTile` rather than three
separate cards, since `ratios` already returns `savings_rate` and
`liquidity_ratio_months` directly -- one less round trip and one less card.

### Demo data

`docs/demo-data/generate.py` produces two date-relative CSVs (checking +
credit card, regenerated fresh before any demo) with merchant names chosen to
match `merchant_normalizer.py`'s known-merchant table (Whole Foods, Netflix,
Spotify, Uber, Starbucks), so expense trends and subscriptions have real
categories/cadences to show instead of "Uncategorized." See
`docs/demo-data/README.md` for the walkthrough.

### Bugs found during hands-on verification (fixed, not just noted)

Browser verification (Playwright driving the real app, not just curling the
API) caught two real issues the API-level checks alone missed: the cash-flow
chart's Y-axis labels were clipped to an unreadable "00.00" (a negative
`margin.left` combined with a too-narrow axis `width` pushed long
`formatCurrency` labels partly off the card -- fixed with a compact `$6k`-style
axis formatter and a non-negative margin); and the "Net saving" stat showed a
confusing negative sign (`average_monthly_burn` is negative when saving,
which read fine next to "Burn rate" but not next to "Net saving" -- fixed by
displaying the absolute value, since the label already encodes direction).

## Milestone 4 — Detailed Implementation Plan (built and verified)

Goal: the `AIProvider` adapter, audit plumbing, and the first real agent
(Financial Advisor) end-to-end -- calling the analytics engine as tools and
producing a structured, cited, confidence-scored recommendation. Unblocks M5
(RAG plugs into this same pattern) and M6 (remaining agents reuse it as-is).

### Model choice and sync-first design

Default model is `claude-opus-4-8` (configurable via `AI_MODEL`), not
downgraded for cost -- financial-advice quality is worth it, and it's the
user's call to change, not a default this system picks. `AIProvider` is a
**sync** interface, matching the rest of this codebase's sync
SQLAlchemy/FastAPI style, rather than introducing async for one subsystem (a
deliberate departure from this doc's original M1-era sketch, which predates
the actual sync-Session pattern M1 shipped with).

### Structured output: a terminal tool, not `output_config.format`

The originally-sketched design paired `tools` with `output_config.format` on
every turn so a final text answer would be schema-constrained. That combo is
under-documented for multi-turn tool loops, so the safer, well-established
pattern was used instead: `submit_recommendations` is declared as an
ordinary strict-schema tool (`ToolDefinition`, `strict: true`,
`additionalProperties: false`) alongside the analytics tools, with
`tool_choice` left at its default `auto`. The agent loop treats a tool call
to `submit_recommendations` as the terminal signal -- no reliance on
`stop_reason == "end_turn"` or any interaction between two features at once.

### Structure

```
api/app/ai/
├── provider/
│   ├── base.py             # AIProvider ABC -- generate() is concrete: persists an
│   │                         # AIAuditLog row before returning, so audit logging is
│   │                         # structurally impossible for an agent to bypass
│   ├── anthropic_provider.py  # the only module that may `import anthropic`
│   ├── fake_provider.py     # test double: scripted RawModelResults, real persistence
│   └── dependency.py        # FastAPI DI seam -- routers depend on this, not the class
├── tools/
│   └── analytics_tools.py   # one strict-schema tool per M3 metric, wrapping AnalyticsEngine.run()
└── agents/
    └── financial_advisor.py # system prompt, tool-calling loop, FinancialAdviceResult
```

`AIProvider.generate()` is concrete (not abstract) precisely so persistence
can't be an afterthought each agent has to remember -- only `_call_model()`
(the actual network/fake call) is provider-specific. Every call also records
token usage (input/output/cache-read/cache-creation) and latency for cost
observability, seeding what M10's cost tracking will read.

### Database (migration `0003`)

- **agent_run**: one row per agent invocation (may span several model
  calls). `status` (running/completed/failed), `user_message`,
  `error_message`. `user_id` is nullable + `ON DELETE SET NULL` -- the AI
  decision trail should survive account deletion, same reasoning as
  `audit_log.user_id`.
- **ai_audit_log**: one row per underlying model call. Hash-chained and
  immutable -- the *exact* pattern from M2's `audit_log` (Enhancement 2),
  applied here because a hash chain without an enforcement trigger only
  *detects* tampering on demand; it doesn't prevent it. `prev_hash`/`row_hash`
  are `NOT NULL` from creation (a new table, no M2-style nullable-then-
  backfill needed). Stores `system_prompt`, `messages`, `tool_calls`,
  `response` (full content blocks, including thinking-block summaries),
  `stop_reason`, and token/latency metrics.
- **ai_recommendation**: the user-facing deliverable -- `title`,
  `explanation`, `category`, `confidence`, `citations` (which metrics backed
  it), `status` (active/dismissed/completed). Deliberately separate from
  `ai_audit_log`: the dashboard queries this table directly for "your AI
  insights" without parsing raw audit JSON.

### Financial Advisor agent

System prompt requires citing which tool outputs back every recommendation
and forbids inventing numbers a tool could supply exactly. The loop: send
the user's message (or a default "general financial health check" prompt) +
all M3 analytics tools + `submit_recommendations`; execute whatever tools
Claude calls, feed results back; repeat up to `AI_MAX_TOOL_ITERATIONS` (default
6) until `submit_recommendations` is called. If the budget is exhausted
without a submission, the run is marked `failed` (`AgentIncompleteError`) --
never fabricates a recommendation. A `stop_reason == "refusal"` is audit-
logged like any other call, then raised as `AIRefusalError` rather than
silently retried.

### Endpoints

`POST /api/v1/ai/financial-advisor/advice` (optional `message`, defaults to
a general check-up) and `GET /api/v1/ai/recommendations`. Returns 503 with a
clear message if `ANTHROPIC_API_KEY` isn't configured, rather than a raw SDK
auth error.

### Testing without live API calls

`FakeAIProvider` pops pre-scripted `RawModelResult`s but runs every call
through the *same* concrete `generate()` persistence path as the real
provider -- tests exercise the actual audit/hash-chain logic, not a mocked-
away version of it. 9 new tests (113 total): the immutability trigger
(update/delete/truncate all rejected, mirroring M2's audit_log tests), the
full agent loop (tool call -> submit -> recommendation + 2-row verified hash
chain), the iteration-budget-exhausted failure path, the refusal path, and
the HTTP endpoints with the provider swapped via FastAPI's dependency
override. One consequence worth noting: `ai_audit_log`'s new immutability
trigger meant the test suite's per-test cleanup (which bulk-deletes every
table between tests) needed the same trigger-disable escape hatch
`conftest.py` already used for `audit_log`.

### Live verification (real Anthropic API, not the fake provider)

The fake-provider test suite alone couldn't catch a bug in the *actual*
request shape sent to Anthropic, and it didn't: the first live call 400'd
with `"tools.1.custom: For 'integer' type, properties maximum, minimum are
not supported"` -- `_months_schema()`'s `minimum`/`maximum` constraints on
the `months` tool parameter aren't valid in Anthropic tool input schemas.
Fixed by moving the valid range into the description text (the analytics
endpoints themselves still enforce 1-24) and re-verified live. The
subsequent real run against realistic demo data produced genuinely
well-reasoned, correctly-cited output (e.g. correctly flagging that idle
cash sits in checking rather than a high-yield account, and an honest caveat
that the then-current month was partial and not fully reliable), with
`agent_run`/`ai_audit_log`/`ai_recommendation` all persisting correctly and
real token counts recorded.

### Frontend

`AIInsightsCard`: a persistent list of past recommendations (`GET
/recommendations`, always loaded) plus a "Get advice" button (`POST
/financial-advisor/advice`, user-triggered -- not auto-fetched, since it costs
real tokens) that invalidates and refetches the list on success. Fills the
"AI insights" dashboard placeholder from M1/M3.

## Milestone 5 — Detailed Implementation Plan (built and verified)

Goal: give the Financial Advisor a second knowledge source alongside this
user's own numbers -- general personal-finance guidance (emergency-fund
sizing, debt payoff strategies, retirement accounts, tax brackets,
diversification, budgeting frameworks) retrieved via RAG and cited by title,
the same way `metrics_used` already cites analytics tools.

### Embeddings: local (fastembed), not an API

Chosen over calling out to an embeddings API so the RAG pipeline has no extra
per-query cost or external dependency once the corpus is ingested. Within
"local," `fastembed` (ONNX runtime, `BAAI/bge-small-en-v1.5`, 384 dimensions)
was chosen over `sentence-transformers` specifically to avoid pulling in
PyTorch for what is otherwise a small, focused embedding task -- `fastembed`'s
only heavy dependency is `onnxruntime`. Same adapter shape as `AIProvider`:
`EmbeddingProvider` ABC (`embed()`, `dimensions`) with `FastEmbedProvider`
(real) and `FakeEmbeddingProvider` (test double). The fake isn't a text hash
-- it's a deterministic hashing-trick bag-of-words, so texts sharing
vocabulary land closer together in cosine distance than unrelated texts,
which matters for retrieval-ranking tests to be meaningful rather than
vacuous.

### Corpus: small, hand-authored, explicitly not scraped

Six short markdown documents (`docs/rag-corpus/`) written for this project
rather than pulled from IRS/SEC/Investopedia, since scraping real regulatory
sources raises sourcing/licensing questions this milestone didn't need to
take on to prove the pipeline. `docs/rag-corpus/README.md` documents this
choice and how to swap in real sourced documents later via the existing
`source`/`source_url` fields. The tax-brackets document carries an explicit,
deliberate disclaimer that its figures are illustrative examples, not
current-year-authoritative -- a financial app asserting stale tax law as fact
is a real risk, not a hypothetical one.

### Database (migration `0004`)

- **pgvector extension** (`CREATE EXTENSION IF NOT EXISTS vector`), and the
  `postgres` Compose service image changed from `postgres:16-alpine` to
  `pgvector/pgvector:pg16` -- same Postgres 16 data format underneath, so the
  existing named volume survives the swap unmodified.
- **rag_document**: `title`, `source`, `category`, `source_url`,
  `content_hash` (unique -- backs idempotent re-ingestion).
- **rag_chunk**: `document_id` (FK, cascade delete), `chunk_index`, `content`,
  `embedding` (`vector(384)`), `token_count`. Two indexes carry the actual
  retrieval load: an HNSW index (`vector_cosine_ops`, m=16, ef_construction=64)
  for vector search, and a GIN index over `to_tsvector('english', content)`
  for full-text search.

### Chunking

`chunk_markdown()` splits by `##` heading first (each chunk prefixed with
`{title} — {heading}` so it stays meaningful once separated from the rest of
the document), then applies a 300-word sliding window with 50-word overlap to
any section still too long. Token counts are an approximate `len//4`
heuristic for observability only, never used for a billing or context-limit
decision.

### Ingestion: idempotent by content hash

`RAGIngestionService.ingest_directory()` hashes each file's content; an
unchanged document is skipped entirely, a changed document (same title,
different hash) has its old chunks deleted and replaced wholesale rather than
diffed chunk-by-chunk -- the corpus is small enough that re-embedding a whole
document is cheap and much simpler than a diff. Verified idempotent against
the real dev DB: first run ingested all 6 documents (29 chunks), a second run
against unchanged files skipped all 6.

### Hybrid retrieval: Reciprocal Rank Fusion, not score blending

`HybridRetriever` runs both pgvector cosine-distance search and Postgres
full-text search, then fuses results with Reciprocal Rank Fusion (`1 / (60 +
rank + 1)`, standard RRF-paper default) rather than trying to normalize and
blend cosine distance against `ts_rank` directly -- the two scores aren't on
comparable scales, but rank position always is. Category filtering is applied
after fusion. Manually verified against the real ingested corpus with several
queries before wiring it into the agent, to catch retrieval-quality issues
independent of any agent-loop bug.

### Agent integration

`search_knowledge_base` is a new strict-schema tool (`build_rag_tool`)
alongside the M4 analytics tools; the system prompt tells the model to use it
for general-principle questions (an emergency-fund target, avalanche vs.
snowball) rather than this user's own numbers, which the analytics tools
already cover. `RecommendationItem` gained a `sources_used: list[str]` field,
parallel to `metrics_used`, populated with the document titles the model
actually leaned on -- left empty when a recommendation is purely numbers-based.
`FinancialAdvisorAgent` now takes an `EmbeddingProvider` alongside the
`AIProvider`, threaded through the same FastAPI DI seam
(`get_embedding_provider`, overridden with `FakeEmbeddingProvider` in tests).

### Live verification (real Anthropic API) surfaced two real bugs

- **Same class of bug as M4, different tool.** The auto-generated
  `submit_recommendations` schema (`FinancialAdviceResult.model_json_schema()`)
  emits `minimum`/`maximum` for `confidence: float = Field(ge=0.0, le=1.0)` --
  valid JSON Schema, but Anthropic tool schemas reject it for `number` types
  the same way M4 found for `integer` types. Fixed by recursively stripping
  `minimum`/`maximum` from the generated schema before using it as
  `input_schema` (the 0-1 bound still applies at `model_validate()` time; the
  valid range is now stated in the tool description instead).
- **A genuine, reproducible model failure mode, not a schema bug.** With that
  fix in place, asking for multiple long recommendations in one turn (e.g.
  both an emergency-fund target and an avalanche-vs-snowball comparison)
  reliably produced a `submit_recommendations` call with `recommendations: []`
  while the real recommendation content was dumped as raw text inside
  `reasoning_summary`, wrapped in fake `<parameter name="...">` tags
  resembling a different tool-calling convention entirely. This passes schema
  validation (a string can contain anything; an empty array is a valid
  array), so it can only be caught by content inspection, not the schema.
  Reproduced twice with the same prompt; a simple single-recommendation
  prompt never triggered it, confirming it's specific to long, multi-item
  submissions. Fixed by detecting the `<parameter` marker in
  `reasoning_summary` post-validation and treating it as a failed submission
  -- the agent sends a corrective `tool_result` explaining exactly what was
  wrong and retries (consuming one iteration of the existing budget) rather
  than silently returning the malformed result to the user. Re-verified live
  with the same prompt that reproduced it: correct, well-cited, 3-recommendation
  output on the first attempt after the fix.

### Frontend

`AIInsightsCard` now reads both `citations.metrics_used` and
`citations.sources_used` off each `AIRecommendation` and renders them as
separate "Based on: ..." / "Sources: ..." lines when non-empty -- the
citation data existed in M4 but wasn't surfaced in the UI at all until now.

### Testing

17 new tests (140 total): chunker unit tests (heading split, no-heading
fallback, sliding-window overlap, token-count monotonicity), retrieval tests
against a real pgvector-backed test database with `FakeEmbeddingProvider`
(keyword+vector fusion surfaces the right document, category filtering,
top-k limiting), and agent-level tests with `FakeAIProvider` proving the
agent calls `search_knowledge_base` and records `sources_used` correctly, and
that a scripted malformed submission (the exact failure shape hit live) is
caught and retried rather than accepted.

## Milestone 6 — Detailed Implementation Plan (built and verified)

Goal: the remaining seven agents (Expense Analyst, Budget Coach, Retirement
Planner, Tax Advisor, Fraud Detection, Investment Analyst, Portfolio Risk
Analyst), reusing the M4/M5 tool-calling and RAG pattern rather than
reinventing it seven times.

### Architectural move: extract `BaseAgent` before writing agent #2

`FinancialAdvisorAgent`'s tool-calling loop (M4), malformed-submission
recovery (M5), and audit persistence had zero agent-specific logic in
them -- every future agent would need the exact same ~150 lines. Rather than
copy-paste that seven times, it was extracted first, as its own verified
step, into `app/ai/agents/base.py`:

- **`BaseRecommendationItem`** / **`BaseAdviceResult`**: the shared
  `title`/`explanation`/`category`/`confidence`/`metrics_used`/`sources_used`
  shape. Each concrete agent subclasses `BaseRecommendationItem` to narrow
  `category` to its own domain `Literal` (pydantic supports redeclaring a
  field with a narrower type in a subclass) -- mypy's list-invariance check
  doesn't see through that narrowing on `recommendations: list[...]`, so each
  subclass's override carries a documented `# type: ignore[assignment]`.
- **`BaseAgent`**: `run()`, `_run_loop()`, `_submit_tool()`, and the
  malformed-submission handling, all moved here unchanged. Concrete agents
  supply only `agent_name`, `prompt_version`, `system_prompt`, `result_model`,
  and `build_tools()`.
- `FinancialAdvisorAgent` became the first subclass, refactored with the
  explicit goal of zero behavior change -- verified by the full pre-existing
  test suite passing unchanged before any new agent was written.

### Scope decision: Investment Analyst and Portfolio Risk Analyst, without holdings data

Neither agent has per-security data to work with -- `accounts` stores only a
balance per account, with no holdings/positions table (tickers, shares, cost
basis), and that arrives with M9's real Plaid/Coinbase integration, not this
milestone. Rather than defer both agents or build a manual holdings table
ahead of schedule, the choice made (with the user) was to ship both today at
the account-type level: allocation and concentration reasoning over the
existing `net_worth.by_account_type` breakdown (cash vs. investment vs.
crypto vs. retirement), with both agents' system prompts explicitly stating
the limitation and refusing to guess at per-security answers. Both gain
richer analysis automatically once M9 lands real holdings, without any
rework -- they'd simply gain a new tool to call.

### New analytics modules (three, registered in the M3 engine)

- **`retirement_contributions`**: total retirement-account balance plus
  average net monthly contribution over a trailing window -- same
  sign-convention helpers as M3's `cash_flow`.
- **`taxable_events`**: dividend/interest/buy/sell transaction counts and
  totals over a trailing window. Explicitly gross activity, not a
  capital-gains calculation -- this schema doesn't track cost basis or tax
  lots, and the Tax Advisor's system prompt is written to never imply
  otherwise.
- **`anomaly_detection`**: three deterministic, rule-based checks --
  possible duplicate charges (same account/merchant/amount within 3 days),
  unusually large charges for their category, and large first-time charges
  from a new merchant. Each baseline (category average, overall average) is
  computed **leave-one-out** -- excluding the transaction being evaluated
  from its own baseline -- the same principle `expense_trends` (M3) already
  established by comparing the latest month against the *prior* months'
  average rather than a baseline that includes itself. Without that, one
  large charge dilutes the very average it's measured against and can hide
  from its own check in a small sample.

All three follow the existing "routers call modules directly, the AI layer
calls them through `AnalyticsEngine.run()`" split -- each also got a
`GET /analytics/...` REST endpoint for free, ahead of any dashboard panel
that will eventually use them (M7).

`build_analytics_tools()` gained an `include: set[str] | None` filter so each
specialist agent can request only its own metrics (e.g. Tax Advisor gets just
`taxable_events`, not all twelve) rather than every agent seeing every tool
-- unscoped, a Tax Advisor could technically call `subscriptions`, which is
just noise for its purpose. `FinancialAdvisorAgent`, the generalist, still
gets the full set via `include=None`.

### RAG corpus: one new document, one new category

`fraud-prevention-basics.md` (duplicate charges, what to do about a
suspicious one, freezing a card) -- same hand-authored, explicitly-scoped
style as the other six M5 documents. `"fraud"` added to `rag_tools.py`'s
category enum.

### Router: one generic endpoint replaces one hardcoded one

`POST /api/v1/ai/{agent_slug}/advice` with an `AGENT_REGISTRY: dict[str,
type[BaseAgent]]` replaces the M4/M5 hardcoded `/financial-advisor/advice`
route -- every agent shares the same request/response shape, so one endpoint
serves all eight rather than seven more hand-written ones. Unknown slugs
return 404. `GET /api/v1/ai/recommendations` needed no changes -- it was
already agent-agnostic (filters by user, not by agent), so it already
aggregates every agent's output into one feed.

### Live verification (real Anthropic API) found a robustness gap, not a new bug class

The M5 malformed-submission failure mode (the model dumping real
recommendation content as text inside `reasoning_summary`, wrapped in fake
`<parameter name="...">` tags, while leaving `recommendations: []`)
recurred live on Investment Analyst -- confirming it's a genuine,
non-deterministic model quirk, not something specific to the Financial
Advisor's prompt. What M5's fix (reject the malformed submission, nudge a
retry) didn't anticipate: the model repeated the **identical** malformed
shape five times in a row and exhausted the iteration budget, despite the
first attempt already containing a perfectly good recommendation -- a text
nudge doesn't reliably break the model out of this particular failure mode.

Since the malformed shape is consistent -- the real payload always appears
as a JSON array immediately after a `<parameter name="recommendations">`
tag, at the end of the string -- `BaseAgent` now attempts **direct recovery**
before falling back to reject-and-retry: extract the embedded JSON, validate
it against the agent's own result model, and use it if it parses cleanly.
An empty recovered list is treated as no recovery (a hollow "success" is no
better than the original failure) and still falls through to the existing
reject-and-retry safety net. Recovering beats retrying: it turns a
reproducible failure into a same-turn success instead of gambling on the
model correcting itself, and it was verified both as a unit test replaying
the exact malformed shape captured from the live failure, and by re-running
the live request that failed.

### Frontend

`AIInsightsCard` gained an agent picker (`Select`, one static config array of
slug/label pairs -- the agent list is deploy-time config, not worth a
`GET /agents` round trip) so "Get advice" can target any of the eight agents,
and each recommendation now shows a small agent-name label alongside its
category badge, since the feed mixes all eight agents' output chronologically
and needs to stay legible as more agents get used. Verified in a real browser
(Playwright-driven): switching the picker to "Fraud Detection" and clicking
"Get advice" posts to `/api/v1/ai/fraud-detection/advice`, and the new
recommendation appears at the top of the feed correctly labeled.

### Testing

32 new tests (172 total): the `BaseAgent` extraction verified as zero
behavior change against the full pre-existing suite; 3 new analytics module
test files (retirement contributions, taxable events, anomaly detection,
including the leave-one-out baseline behavior); 14 parametrized tests
(2 per new agent) proving each agent's distinct schema round-trips correctly
through the shared loop and that `build_tools()` is correctly scoped; a
recovery test replaying the exact malformed shape observed live; and router
tests for the registry (`GET /agents`, unknown-slug 404, dispatch-by-slug).

## Milestone 7 — Detailed Implementation Plan (built and verified)

Goal: the full dashboard -- every panel the roadmap named (allocation, debt,
bills, budget, portfolio, insights, risk, forecasts, goals), and genuine
near-real-time updates via SSE, not just polling.

### Scoping decisions made before writing any code

Research before this milestone found that "full dashboard" was a much bigger
bundle than it looked: two of the nine named panels (forecasts, goals) had
*zero* backing data anywhere (no model, no module), "budget" had only a
stateless AI agent with nothing persisted, and the entire live-delivery side
of "near-real-time" (an SSE endpoint, a Redis subscriber, a frontend client)
was greenfield -- only the durable outbox half (`domain_events` table,
`EventBus.record()`/`dispatch()`) existed, wired into CSV/OFX import and
connector sync but with zero consumers. Three decisions were made explicitly
with the user before building, rather than guessed:

1. **Real-time mechanism: full SSE**, not polling -- the bigger, riskier
   lift, chosen deliberately over the simpler `refetchInterval` alternative.
2. **Goals: build a real, persisted feature now**, not deferred.
3. **Budget: add a lightweight persisted `BudgetTarget` model**, upgrading
   M6's stateless Budget Coach agent rather than leaving it framework-only.

Two panels needed no new backend at all: **allocation** (`net_worth`'s
existing `by_account_type` breakdown, M3) just needed a dashboard tile, and
**bills** is the existing `subscriptions` module (M3) re-sorted by
`next_expected_date` into an `UpcomingBillsCard` that complements rather than
duplicates the merchant/cadence-focused `SubscriptionsCard`.

### Prerequisite: `domain_events` gained a `user_id`

`DomainEventLog` was deliberately polymorphic (`aggregate_type`/
`aggregate_id`, no `user_id`) -- fine when nothing consumed it live, but the
SSE stream needs to deliver only one user's own events without joining back
through aggregate-type-specific tables to figure out ownership. Added
`user_id` (nullable, indexed, no backfill needed) to the Pydantic
`DomainEvent` base and the SQLAlchemy row, threaded through both existing
emitters (`ingestion_common.py`, `sync_service.py`). The Redis publish
channel changed from `domain_events.{aggregate_type}` to
`domain_events.user.{user_id}`, so the SSE subscriber needs exactly one
channel per connected user instead of a firehose it would filter
client-side.

### Goals

`Goal` either tracks a linked account's live balance or a manually-updated
running total, never both -- `current_amount` and `progress_pct` are
computed properties, not stored columns. `progress_pct` is explicitly
quantized to `Decimal("0.0001")` to match every other money column's
precision, since pure Python `Decimal` division otherwise returns a
variable, input-dependent number of decimal places rather than a fixed
scale -- the same fix was needed again later for `budget_vs_actual`'s
`pct_used`. Full CRUD at `/api/v1/goals`, ownership-checked (a goal can't
link to another user's account).

### Budget

`BudgetTarget`: one monthly target per `(user, category)`, upsert semantics
(setting a category's target again overwrites it rather than creating a
duplicate). New `budget_vs_actual` analytics module compares this *calendar
month's* actual category spend against targets -- deliberately always the
current month, not a configurable trailing window like every other module,
since budgets are inherently monthly. This upgrades Budget Coach (M6) from
purely stateless: it now checks `budget_vs_actual` first and compares
against real targets when they exist, falling back to a generic
50/30/20-style suggestion only when none are set, and must say plainly
which case it's in. A small `GET /api/v1/categories` endpoint was added too
-- categories were previously only ever resolved by name during ingestion,
never listed, and the budget-target picker needed something to list.

### Forecast

Naive straight-line projection: trailing-window average monthly net cash
flow added to current net worth, once per month, for 6 months. Explicitly
documented as not a real forecast model (no one-off-event, seasonality, or
growth-rate modeling) -- same category of naive projection as `debt_payoff`'s
payoff estimate, and the frontend chart repeats the caveat in a caption
rather than only in an API `methodology` field a user never sees.

### SSE: ticket-based auth, not the access token in a URL

`EventSource` can't send a custom `Authorization` header, so the normal
15-minute bearer access token can't be used directly for the stream
connection -- and putting it in a URL (which browsers, proxies, and access
logs routinely record) is a worse tradeoff than a ticket that's dead within
seconds. `POST /api/v1/events/ticket` (normal bearer auth) issues a
Redis-backed, single-use, 30-second-TTL ticket; `GET /api/v1/events/stream`
consumes it (`GETDEL`, so reuse fails) and subscribes to
`domain_events.user.{user_id}` via a real async Redis client, streaming
SSE-formatted messages with a 15-second keepalive ping. The frontend
`useLiveUpdates` hook mints a ticket, opens the `EventSource`, and coarsely
invalidates every TanStack Query on any message -- a domain event can move
numbers on nearly every panel, so a fine-grained event-type -> query-key map
wasn't worth building yet. Reconnect-on-error is custom rather than
`EventSource`'s built-in reconnect, since the built-in version would replay
the same now-consumed ticket and fail every time.

**Two real bugs found while building this, both fixed:**

- The async Redis client was `@lru_cache`'d like its sync counterpart (used
  for `EventBus.dispatch()`), but an async client's connections are bound to
  the event loop that created them -- a cached singleton reused from a
  different loop (a new test, a worker restart) raises `RuntimeError: Event
  loop is closed`. Removed the cache; constructing a fresh client is cheap
  since `from_url` doesn't eagerly connect.
- Testing the stream endpoint through `TestClient` hung indefinitely: an
  open-ended `StreamingResponse` body never completes until the client
  disconnects, and `TestClient`'s in-process ASGI transport doesn't reliably
  propagate an early client-side close into server-side generator
  cancellation the way a real network disconnect would. Tests call the
  streaming coroutine and consume its `body_iterator` directly instead, with
  an explicit `asyncio.wait_for` timeout, sidestepping the transport
  entirely rather than fighting it.

Live-verified in a real browser rather than trusting the unit tests alone:
an import triggered from a completely separate session (a second login, no
shared browser state) caused the open dashboard to automatically refetch
every analytics query within ~400ms with no manual reload -- the actual
publish -> Redis -> stream -> `EventSource` -> `invalidateQueries` ->
refetch pipeline, working end to end.

### A note on environment reliability during this milestone

Several edits made mid-session were found to have silently reverted on disk
moments after being written (confirmed via `git diff` going empty right
after a successful edit) -- most likely Docker Desktop's bind-mount file
sync racing with host-side Alembic commands run while the `api` container
(which mounts the same directory) was live. Every file touched in this
milestone was re-verified immediately after writing with a direct `git diff`
before moving on, and small, fully-tested checkpoints were committed
throughout rather than one commit at the end, specifically to bound how much
work could ever be at risk from a repeat.

### Testing

27 new tests (199 total): Goals CRUD and ownership checks; Budget CRUD,
upsert semantics, and `budget_vs_actual`'s current-month comparison;
forecast's flat-projection and average-net-flow-driven projection cases; and
the SSE ticket/stream logic (issuance, single-use consumption, invalid/reused
rejection, and the connected-message handshake) exercised as direct coroutine
calls rather than through `TestClient` for the reasons above.

## After approval

M1 through M7 are all built and verified end-to-end (199 tests passing,
mypy --strict and ruff clean, full Docker Compose stack, and the dashboard
manually driven end-to-end in a real browser against realistic demo data,
including a genuine cross-session SSE live-update). A few specifics were
refined during hands-on M2 implementation versus the original spec:
`ofxparse` was used over `ofxtools` for OFX parsing; the shared `imports.py`
schema replaced the CSV-only `csv_import.py` once OFX needed the same
response shape; the audit-log immutability trigger also covers `TRUNCATE` (a
separate Postgres trigger event that a bare `DELETE` trigger doesn't catch);
and four DB-backed pipeline lookups (dedup, merchant resolution,
transfer/refund matching) were bundled into a single `PipelineDependencies`
object rather than four growing callback parameters. Milestone 8 (security
hardening -- RBAC, rate limiting, JWT refresh hardening, secrets management,
an OWASP pass) is next.
