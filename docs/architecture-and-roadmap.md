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

## After approval

Scaffold only Milestone 1 per this plan. Stop and report before starting Milestone 2 — its detailed
design will be revisited once M1 is verified, since real experience building M1 may change M2's
specifics (e.g., exact OFX library, exact stub-connector shape).
