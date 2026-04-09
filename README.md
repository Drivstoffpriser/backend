# Drivstoffpriser Backend

REST API for drivstoffpriser — fuel price tracking across Norwegian stations.

## Tech stack

| Layer | Technology |
|---|---|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | PostgreSQL 18 + [PostGIS](https://postgis.net/) (via Docker) |
| ORM / queries | [SQLAlchemy 2.0](https://docs.sqlalchemy.org/) async core + [asyncpg](https://github.com/MagicStack/asyncpg) |
| Geography | [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/) + [Shapely](https://shapely.readthedocs.io/) |
| Auth | [Firebase Admin](https://firebase.google.com/docs/admin/setup) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Task runner | [Task](https://taskfile.dev/) |
| Scheduler | [APScheduler](https://apscheduler.readthedocs.io/) |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Docker](https://www.docker.com/) — runs PostgreSQL with PostGIS
- [Task](https://taskfile.dev/) — task runner (optional, but recommended)

## First-time setup

```bash
cp .env.example .env          # configure environment variables
uv sync                       # install dependencies
uv run pre-commit install     # register git hooks
task database:default         # start postgres, apply migrations, and seed all data
docker compose up api         # start API with hot reload on http://localhost:8000
```

## Available tasks

```bash
task database:default         # start postgres, migrate, and seed everything (first-time setup)
task database:initialize      # start postgres and apply migrations (no seed)
task database:start           # start postgres container and wait until ready
task database:migrate         # apply all Alembic migrations
task database:seed            # seed stations and price history
task database:seed:stations   # seed station data only
task database:seed:prices     # seed sample price history only
task lint                     # run ruff (format, check) and mypy
```

## Development

```bash
docker compose up api      # start API with hot reload at http://localhost:8000
docker compose up          # start postgres + API together
```

## Testing

Tests run against a real local PostgreSQL instance. Each test wraps its work in a transaction that is rolled back on completion, so no data persists between tests.

```bash
uv run pytest tests                                      # run all tests
uv run pytest tests/test_health.py::test_health          # run a single test
```

## Linting and formatting

```bash
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy .          # type check
```

Pre-commit hooks run ruff automatically on staged files before each commit. After `uv sync`, run `uv run pre-commit install` once to register them. To run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Migrations

```bash
uv run alembic revision --autogenerate -m "description"  # generate migration
uv run alembic upgrade head                               # apply migrations
```

## Spell checking

[CSpell](https://cspell.org/) is not enforced in CI but encouraged. Install the [VS Code extension](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker) for inline feedback, or run from the command line:

```bash
npm install -g cspell
cspell "**/*.{py,md}"
```

Add false positives to `project-words.txt`.

## Production

The Dockerfile uses a multi-stage build. Migrations run automatically on container startup via `start.sh`.

```bash
docker build --target production -t drivstoffpriser-api .
```
