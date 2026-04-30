#!/bin/sh
set -e
cd /app
export PATH="/app/.venv/bin:$PATH"
python manage.py migrate --noinput
exec gunicorn core.wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
