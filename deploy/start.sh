#!/usr/bin/env bash
# Container entrypoint. START_MODE picks what runs:
#
#   all         gunicorn + celery worker with embedded beat, one container.
#               This is the Northflank FREE-TIER mode: the free plan allows only
#               2 services, and one of them has to be Redis, so web + worker +
#               beat share this container.
#   web         gunicorn only (runs migrations first)
#   worker      celery worker only
#   worker-beat celery worker with embedded beat (-B)
#   beat        celery beat only
#
# The split modes exist so the SAME image works unchanged after migrating to a
# paid plan: change START_MODE per service instead of rebuilding.
set -euo pipefail

MODE="${START_MODE:-all}"

if [ "$MODE" = "all" ] || [ "$MODE" = "web" ]; then
  python manage.py migrate --noinput

  # Optional first-boot admin bootstrap: set DJANGO_SUPERUSER_USERNAME,
  # DJANGO_SUPERUSER_PASSWORD (and optionally DJANGO_SUPERUSER_EMAIL) once,
  # deploy, log in, then remove them. Exits non-zero if the user already
  # exists, hence the || true.
  if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput || true
  fi
fi

GUNICORN_CMD=(
  gunicorn leads_app.wsgi:application
  --bind "0.0.0.0:${PORT:-8000}"
  --workers "${GUNICORN_WORKERS:-1}"
  --threads "${GUNICORN_THREADS:-4}"
  --timeout "${GUNICORN_TIMEOUT:-60}"
  --access-logfile -
  --error-logfile -
)

# threads pool + low concurrency: prefork would fork full Django processes and
# blow past small-container memory limits. Django's settings default the pool
# from CELERY_WORKER_POOL too, but passing it on the CLI keeps this script the
# single source of truth in containers.
WORKER_CMD=(
  celery -A leads_app worker
  -l info
  --pool "${CELERY_WORKER_POOL:-threads}"
  --concurrency "${CELERY_CONCURRENCY:-2}"
)

case "$MODE" in
  web)
    exec "${GUNICORN_CMD[@]}"
    ;;
  worker)
    exec "${WORKER_CMD[@]}"
    ;;
  worker-beat)
    exec "${WORKER_CMD[@]}" -B
    ;;
  beat)
    exec celery -A leads_app beat -l info
    ;;
  all)
    # Both processes in one container. If either dies, kill the other and exit
    # non-zero so the platform restarts the container as a unit.
    trap 'kill -TERM $(jobs -p) 2>/dev/null || true' TERM INT

    "${GUNICORN_CMD[@]}" &
    "${WORKER_CMD[@]}" -B &

    set +e
    wait -n
    STATUS=$?
    kill -TERM $(jobs -p) 2>/dev/null
    wait
    exit "$STATUS"
    ;;
  *)
    echo "Unknown START_MODE: $MODE (expected all|web|worker|worker-beat|beat)" >&2
    exit 64
    ;;
esac
