# syntax=docker/dockerfile:1

# ── uv binary ──
FROM ghcr.io/astral-sh/uv:latest AS uv

# ── Builder: installs all dependency groups ──
FROM python:3.14-alpine AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN apk add --no-cache git libffi-dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-managed-python --only-group bot
RUN cp -a .venv .venv-bot && rm -rf .venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-managed-python --only-group migrations
RUN cp -a .venv .venv-migrations && rm -rf .venv

# ── Runtime base: shared env for bot and migrations ──
FROM python:3.14-alpine AS runtime
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    UID=10001
RUN adduser -D -H -h /app -u "${UID}" NerdyBot
WORKDIR /app

# ── Bot: minimal runtime ──
FROM runtime AS bot
ENV PYTHONFAULTHANDLER=1
RUN apk add --no-cache ffmpeg opus
COPY --chown=${UID} --from=builder /app/.venv-bot /app/.venv
COPY --chown=${UID} NerdyPy /app
USER NerdyBot
CMD ["python", "NerdyPy.py"]
LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="NerpyBot, the nerdiest Python Bot"

# ── Migrations: minimal runtime ──
FROM runtime AS migrations
ENV ALEMBIC_CONFIG=alembic-nerpybot.ini
COPY --chown=${UID} --from=builder /app/.venv-migrations /app/.venv
COPY --chown=${UID} alembic-nerpybot.ini alembic-humanmusic.ini ./
COPY --chown=${UID} database-migrations /app/database-migrations/
USER NerdyBot
CMD ["sh", "-c", "alembic -c ${ALEMBIC_CONFIG} upgrade head"]
LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="Database migrations for the nerdiest Python Bot"
