FROM python:3.13-slim

LABEL org.opencontainers.image.title="raptio" \
      org.opencontainers.image.description="Polls the KegLand RAPT API and publishes devices to MQTT for Home Assistant" \
      org.opencontainers.image.source="https://github.com/duarte-hub/raptio" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rapt2mqtt.py .

USER nobody

CMD ["python", "rapt2mqtt.py"]
