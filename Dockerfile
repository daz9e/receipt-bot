FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /data/receipts

ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/receipts.db
ENV RECEIPTS_DIR=/data/receipts

CMD ["python", "-m", "app.main"]
