# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:latest AS uv
FROM alpine AS base

# Setup env
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    UID=10001 \
    PATH="/app/.venv/bin:$PATH"

RUN adduser -D -H -h /app -u "${UID}" NerdyBot

# Install uv
COPY --from=uv /uv /usr/local/bin/uv

USER NerdyBot
WORKDIR /app

COPY --chown=${UID} pyproject.toml uv.lock ./


FROM base AS bot

USER root
RUN apk add --no-cache \
        ffmpeg \
        opus \
        git

USER NerdyBot
RUN uv sync --only-group bot

COPY --chown=${UID} NerdyPy /app

CMD ["python", "NerdyPy.py"]

LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="NerpyBot, the nerdiest Python Bot"


FROM base AS migrations

RUN uv sync --only-group migrations

COPY --chown=${UID} alembic.ini /app/
COPY --chown=${UID} database-migrations /app/database-migrations/

CMD ["uv", "run", "alembic", "upgrade", "head"]

LABEL org.opencontainers.image.source=https://github.com/nerdycraft/NerpyBot
LABEL org.opencontainers.image.description="Database migrations for the nerdiest Python Bot"
