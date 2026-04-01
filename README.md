# Drivstoffpriser Backend

FastAPI backend for drivstoffpriser. Uses async PostgreSQL (SQLAlchemy 2.0 + asyncpg) with PostGIS for geography.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com/)
- [Task](https://taskfile.dev/) (optional)

## Getting started

```bash
cp .env.example .env          # configure environment variables
uv sync                       # install dependencies
docker compose up              # start postgres and api with hot reload
task database:migrate          # apply migrations (first time and after schema changes)
```

## Running tests

```bash
uv run pytest tests
```

## Linting and formatting

```bash
uv run ruff check .
uv run ruff format .
```

## Migrations

```bash
uv run alembic revision --autogenerate -m "description"   # generate
uv run alembic upgrade head                                # apply
```

## Production

The Dockerfile uses a multi-stage build. Migrations run automatically on container startup via `start.sh`.

```bash
docker build --target production -t drivstoffpriser-api .
```
