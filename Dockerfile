FROM python:3.12-slim as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base AS builder

# Install pipenv and compilation dependencies
RUN pip install pipenv
RUN apt update && apt install -qqy --no-install-recommends \
      git

ADD Pipfile.lock Pipfile /tmp/

WORKDIR /tmp
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy


FROM base as runtime

COPY --from=builder /tmp/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY NerdyPy /app
RUN apt update && apt install -qqy --no-install-recommends \
      ffmpeg \
      libopus0 \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -d /app NerdyBot
USER NerdyBot

WORKDIR /app
CMD ["python", "NerdyPy.py"]
