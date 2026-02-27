# syntax=docker/dockerfile:1

# ── uv binary ──
FROM ghcr.io/astral-sh/uv:latest AS uv

# ── Builder base: shared build tools and lockfile ──
FROM python:3.14-alpine AS builder-base
ENV UV_LINK_MODE=copy

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./

RUN apk add --no-cache git libffi-dev \
    gcc g++ musl-dev python3-dev pkgconf \
    freetype-dev libpng-dev

# ── Builder: bot dependencies only ──
FROM builder-base AS builder-bot

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-managed-python --only-group bot

# ── Builder: migration dependencies only ──
FROM builder-base AS builder-migrations

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-managed-python --only-group migrations

# ── Runtime base: shared env for bot and migrations ──
FROM python:3.14-alpine AS runtime
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    UID=10001

WORKDIR /app
RUN adduser -D -H -h /app -u "${UID}" NerdyBot \
 && chown NerdyBot:NerdyBot /app

USER NerdyBot


# ── Bot: minimal runtime ──
FROM runtime AS bot
ENV PYTHONFAULTHANDLER=1

USER root
RUN apk add --no-cache ffmpeg opus freetype libpng

USER NerdyBot
COPY --chown=${UID} --from=builder-bot /app/.venv /app/.venv
COPY --chown=${UID} NerdyPy /app

CMD ["python", "bot.py"]

LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="NerpyBot, the nerdiest Python Bot"


# ── Migrations: minimal runtime ──
FROM runtime AS migrations

COPY --chown=${UID} --from=builder-migrations /app/.venv /app/.venv
COPY --chown=${UID} alembic.ini ./
COPY --chown=${UID} database-migrations /app/database-migrations/

CMD ["alembic", "upgrade", "head"]

LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="Database migrations for the nerdiest Python Bot"
