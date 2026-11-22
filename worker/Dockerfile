FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Piper CLI from PyPI (and known missing runtime dependency in slim images)
RUN pip install --no-cache-dir piper-tts pathvalidate

# Preload a default Piper voice model used by backend/.env fallback settings
RUN mkdir -p /app/models \
    && curl -fsSL -o /app/models/en_US-amy-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx \
    && curl -fsSL -o /app/models/en_US-amy-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json

COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY worker /app

CMD ["python", "main.py", "start"]
