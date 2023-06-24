FROM python:3.11-alpine

WORKDIR /app/NerdyPy

COPY pyproject.toml poetry.lock /app/
COPY NerdyPy /app/NerdyPy

RUN apk add --no-cache \
      libffi-dev \
      ffmpeg \
      opus \
    && poetry install

CMD ["python", "/app/NerdyPy/NerdyPy.py"]
