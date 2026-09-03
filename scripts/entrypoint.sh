#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  python manage.py migrate --noinput
fi

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
