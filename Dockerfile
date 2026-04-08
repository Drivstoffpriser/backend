FROM python:3.14-slim@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7@sha256:629240833dd25d03949509fc01ceff56ae74f5e5f0fd264da634dd2f70e9cc70 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# --- Dev target: includes uv, expects volume mount ---
FROM python:3.14-slim@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.7@sha256:629240833dd25d03949509fc01ceff56ae74f5e5f0fd264da634dd2f70e9cc70 /uv /usr/local/bin/uv

WORKDIR /app

# Pre-install dependencies so the named volume (venv) is populated from this
# image layer on first start — no uv sync needed on subsequent container starts.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-editable

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log"]

# --- Production target ---
FROM python:3.14-slim@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

COPY --from=builder /app /app
COPY start.sh .

USER app

EXPOSE 8000

CMD ["./start.sh"]
