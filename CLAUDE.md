# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
docker compose up db        # start postgres (postgis/postgis:18-3.6)
uv run fastapi dev          # run dev server
uv run pytest tests         # run all tests
uv run pytest tests/test_health.py::test_health  # run single test
uv run alembic upgrade head                      # run migrations
uv run alembic revision --autogenerate -m "msg"  # generate migration
uv run ruff check .         # lint
uv run ruff format .        # format
uv run mypy .               # type check (only run when asked)
```

## Architecture

FastAPI backend with async PostgreSQL via SQLAlchemy 2.0 + asyncpg. Geography stored in PostGIS using GeoAlchemy2.

### Config (`app/core/config.py`)

`get_settings()` returns a cached `Settings` instance (pydantic-settings). Reads from environment variables, falls back to `.env` file. Use `get_settings()` — never instantiate `Settings()` directly.

Required env vars: `DB_USER`, `DB_PASSWORD`. Optional with defaults: `APP_NAME`, `DEBUG`, `ALLOWED_ORIGINS`, `DB_HOST`, `DB_PORT`, `DB_NAME`.

### DB layer (`app/core/db.py`)

`DBSession` wraps `AsyncSession` and exposes `fetch_all`, `fetch_one`, `fetch_one_or_none`, and `execute`. All writes use SQLAlchemy Core statements via `db.execute(sa.insert(...).values({Model.field: ...}).returning(Model))` — never the ORM unit-of-work (`session.add` / `flush` / `commit`).

`Database.session()` is an async context manager; `get_db_session()` is the FastAPI dependency, always declared with `Annotated`:

```python
DbSession = Annotated[DBSession, Depends(get_db_session)]
```

### Testing

Tests run against a real local PostgreSQL database. Each test gets a transaction that is rolled back after completion — no test data persists.

`conftest.py` provides:
- `db` — `DBSession` bound to a connection with a rolled-back transaction
- `client` — `AsyncClient` with `get_db_session` overridden to use the test session

Factory functions go in per-domain `tests/<domain>/factories.py` files, inserting rows via `db.execute(sa.insert(...))`.
