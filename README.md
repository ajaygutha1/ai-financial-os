# AI Financial OS

An AI-powered financial intelligence platform — not a budgeting app. Aggregates a
user's entire financial life into a unified data model, runs a modular
analytics engine over it, and layers explainable, agentic AI on top with
full audit trails.

This repo is being built milestone by milestone. See `docs/` for the
architecture and roadmap. **Milestone 1 (this state)** covers: auth (JWT +
Google/GitHub OAuth), the core data model, CSV import with a normalization/
dedup pipeline, and a dashboard shell with a live net worth tile.

## Stack

- **Frontend**: Next.js (App Router), TypeScript, Tailwind, shadcn/ui,
  TanStack Query, React Hook Form, Zod, Recharts, Framer Motion.
- **Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis.
- **Infra**: Docker Compose, GitHub Actions.

## Running locally

Requires Docker (or a Docker-compatible runtime like Colima).

```bash
cp .env.example .env   # then edit secrets as needed
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`, health check at `/health`)
- Web: http://localhost:3000

The `api` container runs `alembic upgrade head` automatically on startup.

## Running the backend test suite

Tests run against a real Postgres database (not mocks), so a Postgres
instance must be reachable. With the compose stack's `postgres` service
running:

```bash
docker exec ai-financial-os-postgres-1 psql -U finos -d finos -c "CREATE DATABASE finos_test;"
cd api
uv sync
uv run pytest -q
```

## Project layout

```
api/    FastAPI backend (routers -> services -> repositories -> models)
web/    Next.js frontend (App Router)
docs/   Architecture decisions, ERD, roadmap
```
