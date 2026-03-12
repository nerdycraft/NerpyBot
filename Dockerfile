# syntax=docker/dockerfile:1

# ── uv binary ──
FROM ghcr.io/astral-sh/uv:latest AS uv

# ── Builder base: shared build tools and lockfile ──
FROM python:3.14-alpine AS builder-base

# Version from git tag (passed via --build-arg in CI, defaults to dev)
ARG VERSION=0.0.0.dev0
ENV UV_LINK_MODE=copy \
    SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./

RUN apk add --no-cache git libffi-dev \
    gcc g++ musl-dev python3-dev pkgconf \
    freetype-dev libpng-dev

# ── Builder: bot dependencies + project metadata ──
FROM builder-base AS builder-bot

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-managed-python --group bot

# ── Builder: web dependencies ──
FROM builder-base AS builder-web

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-managed-python --group web

# ── Builder: Vue 3 frontend (SPA) ──
FROM node:22-alpine AS builder-frontend
WORKDIR /app/web/frontend
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend .
RUN npm run build

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
COPY --chown=${UID} alembic.ini ./
COPY --chown=${UID} database-migrations/ database-migrations/

HEALTHCHECK --interval=5s --timeout=3s --start-period=60s \
  CMD test -f /tmp/nerpybot_ready

CMD ["python", "bot.py"]

LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="NerpyBot, the nerdiest Python Bot"


# ── Web dashboard: FastAPI API ──
FROM runtime AS web

COPY --chown=${UID} --from=builder-web /app/.venv /app/.venv
COPY --chown=${UID} NerdyPy /app/NerdyPy/
COPY --chown=${UID} web /app/web/
COPY --chown=${UID} --from=builder-frontend /app/web/frontend/dist /app/web/frontend/dist/

ENV PYTHONPATH=/app/NerdyPy

CMD ["python", "-m", "uvicorn", "web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="NerpyBot Web Dashboard API"
