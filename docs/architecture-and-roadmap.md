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

Additive migration `0002`: `category` and `merchant` tables, backfilled from
`transactions.category`/`merchant_normalized`; add `category_id`/`merchant_id` FK
columns, then drop the old string columns — exactly the non-disruptive migration
path M1's schema was designed to allow.

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
(`publish()`, in-process + optional Redis pub/sub for live fan-out), called from
`csv_import_service.py` and the new `sync_service.py`. Unblocks: M3 (invalidate
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

### Frontend

`AIInsightsCard`: a persistent list of past recommendations (`GET
/recommendations`, always loaded) plus a "Get advice" button (`POST
/financial-advisor/advice`, user-triggered -- not auto-fetched, since it costs
real tokens) that invalidates and refetches the list on success. Fills the
"AI insights" dashboard placeholder from M1/M3.

## After approval

M1 through M4 are all built and verified end-to-end (113 tests passing,
mypy --strict and ruff clean, full Docker Compose stack, and the dashboard
manually driven end-to-end in a real browser against realistic demo data). A
few specifics were refined during hands-on M2 implementation versus the
original spec: `ofxparse` was used over `ofxtools` for OFX parsing; the shared
`imports.py` schema replaced the CSV-only `csv_import.py` once OFX needed the
same response shape; the audit-log immutability trigger also covers
`TRUNCATE` (a separate Postgres trigger event that a bare `DELETE` trigger
doesn't catch); and four DB-backed pipeline lookups (dedup, merchant
resolution, transfer/refund matching) were bundled into a single
`PipelineDependencies` object rather than four growing callback parameters.
Milestone 5 (the RAG pipeline: pgvector, hybrid retrieval, IRS/SEC/
Investopedia corpus, citations wired into the Financial Advisor) is next.
