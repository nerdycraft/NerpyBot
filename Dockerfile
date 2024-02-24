FROM python:3.12 as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV PATH="/app/.venv/bin:$PATH"

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

COPY --from=venv /app/.venv /app/.venv
COPY NerdyPy /app

RUN apt update && apt install -qqy --no-install-recommends \
      ffmpeg \
      libopus0 \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -d /app NerdyBot
USER NerdyBot

CMD ["python", "NerdyPy.py"]


FROM base as migrations

COPY --from=venv /app/.venv /app/.venv
COPY alembic.ini /app/
COPY database-migrations /app/database-migrations/

RUN useradd -m -d /app NerdyBot
USER NerdyBot

CMD ["python", "-m", "alembic", "upgrade", "head"]
