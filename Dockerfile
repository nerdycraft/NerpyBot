FROM python:3-alpine

WORKDIR /app/NerdyPy

COPY setup.py /app/setup.py
COPY NerdyPy /app/NerdyPy

RUN apk add --no-cache build-base libffi-dev \
    && pip install --no-cache-dir --trusted-host pypi.python.org /app/ \
    && apk del build-base libffi-dev \
    && rm -rf /var/cache/apk/*

RUN apk add --no-cache gcc ffmpeg opus

CMD ["python", "/app/NerdyPy/NerdyPy.py"]
