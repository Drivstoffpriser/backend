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
uv run pre-commit install      # register git hooks
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

## Pre-commit hooks

[pre-commit](https://pre-commit.com/) is included as a dev dependency and runs ruff and mypy on staged files before each commit. After `uv sync`, run `uv run pre-commit install` once to register the git hooks. To run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Spell checking

We use CSpell for spell checking, which is enforced in CI. Install the
[CSpell extension for VS Code](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker)
to get inline feedback as you type.

To run it from the command line, install via npm:

```bash
npm install -g cspell
cspell "**/*.{py,md}"
```

If CSpell flags a false positive, add the word to `project-words.txt`.

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
