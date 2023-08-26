FROM python:3.11

ENV POETRY_VIRTUALENVS_IN_PROJECT=true

COPY pyproject.toml poetry.lock README.md alembic.ini /app/
COPY database-migrations /app/

WORKDIR /app/
RUN apt update && apt install -qqy --no-install-recommends \
      build-essential \
      libffi-dev \
    && pip install \
      --no-cache-dir \
      --trusted-host pypi.python.org \
      poetry \
    && apt purge -qqy --autoremove build-essential libffi-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

RUN poetry install --no-interaction --no-ansi --only migrations \
    && rm -rf ~/.cache/pypoetry ~/.local/share/virtualenv

CMD ["poetry", "run", "alembic", "upgrade", "head"]
