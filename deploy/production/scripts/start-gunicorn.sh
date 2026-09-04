#!/usr/bin/env bash
set -euo pipefail

exec /home/frappe/frappe-bench/env/bin/gunicorn \
  --chdir=/home/frappe/frappe-bench/sites \
  --bind=0.0.0.0:8000 \
  --threads="${GUNICORN_THREADS:-4}" \
  --workers="${GUNICORN_WORKERS:-2}" \
  --worker-class=gthread \
  --worker-tmp-dir=/dev/shm \
  --timeout="${GUNICORN_TIMEOUT:-120}" \
  --preload \
  --access-logfile=- \
  --error-logfile=- \
  frappe.app:application
