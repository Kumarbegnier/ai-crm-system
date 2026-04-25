FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Persistent SQLite volume mount point
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/crm.db

EXPOSE 8000

# SQLite WAL serializes writes — more than 2 workers adds lock contention without throughput gain.
# Increase only if you migrate to PostgreSQL.
ENV WEB_CONCURRENCY=2

CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers $WEB_CONCURRENCY --bind 0.0.0.0:8000 --timeout 120 --graceful-timeout 30 --access-logfile -"]
