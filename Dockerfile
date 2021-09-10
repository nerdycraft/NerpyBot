FROM python:3

WORKDIR /app/NerdyPy

COPY setup.py /app/setup.py
COPY NerdyPy /app/NerdyPy

RUN apt update && apt install -qqy --no-install-recommends \
      build-essential \
      libffi-dev \
      ffmpeg \
      libopus0 \
    && pip install --no-cache-dir --trusted-host pypi.python.org /app/ \
    && apt purge -qqy --autoremove build-essential libffi-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

CMD ["python", "/app/NerdyPy/NerdyPy.py"]
