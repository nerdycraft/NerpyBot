FROM python:3.11

ENV POETRY_VIRTUALENVS_IN_PROJECT=true

COPY pyproject.toml poetry.lock README.md /app/
COPY HumanMusic /app/NerdyPy

WORKDIR /app/NerdyPy
RUN apt update && apt install -qqy --no-install-recommends \
      build-essential \
      libffi-dev \
      ffmpeg \
      libopus0 \
    && pip install \
      --no-cache-dir \
      --trusted-host pypi.python.org \
      poetry \
    && apt purge -qqy --autoremove build-essential libffi-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

RUN poetry install --no-interaction --no-ansi --only main \
    && rm -rf ~/.cache/pypoetry ~/.local/share/virtualenv

CMD ["poetry", "run", "python", "/app/NerdyPy/NerdyPy.py"]
