FROM python:3.11-alpine

ENV POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app/NerdyPy

COPY pyproject.toml poetry.lock README.md /app/
COPY NerdyPy /app/NerdyPy

RUN apk add --no-cache \
      libffi-dev \
      ffmpeg \
      opus \
    && pip install \
      --no-cache-dir \
      --trusted-host pypi.python.org \
      poetry

RUN poetry install \
    && rm -rf ~/.cache/pypoetry ~/.local/share/virtualenv

CMD ["poetry", "run", "python", "/app/NerdyPy/NerdyPy.py"]
