# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION} as base

# Setup env
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 -d /app NerdyBot
RUN chown -R NerdyBot /app

WORKDIR /app


FROM base AS venv

ARG categories="packages"

# Install pipenv and compilation dependencies
RUN pip install pipenv
RUN apt update && apt install -qqy --no-install-recommends \
      git

ADD Pipfile.lock Pipfile /app/

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy --categories ${categories}


FROM base as bot

COPY --from=venv --chown=1000 /app/.venv /app/.venv
COPY --chown=1000 NerdyPy /app

RUN apt update && apt install -qqy --no-install-recommends \
      ffmpeg \
      libopus0 \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

USER NerdyBot

CMD ["python", "NerdyPy.py"]

LABEL org.opencontainers.image.source=https://github.com/ethernerd-net/NerpyBot
LABEL org.opencontainers.image.description="NerpyBot, the nerdiest Python Bot"


FROM base as migrations

COPY --from=venv --chown=1000 /app/.venv /app/.venv
COPY --chown=1000 alembic.ini /app/
COPY --chown=1000 database-migrations /app/database-migrations/

USER NerdyBot

CMD ["python", "-m", "alembic", "upgrade", "head"]

LABEL org.opencontainers.image.source=https://github.com/ethernerd-net/NerpyBot
LABEL org.opencontainers.image.description="Database migrations for the nerdiest Python Bot"
