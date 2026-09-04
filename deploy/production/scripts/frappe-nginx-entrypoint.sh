#!/usr/bin/env bash
set -euo pipefail

: "${BACKEND:?BACKEND is required}"
: "${SOCKETIO:?SOCKETIO is required}"
: "${FRAPPE_SITE_NAME_HEADER:?FRAPPE_SITE_NAME_HEADER is required}"
export PROXY_READ_TIMEOUT="${PROXY_READ_TIMEOUT:-120}"
export CLIENT_MAX_BODY_SIZE="${CLIENT_MAX_BODY_SIZE:-50m}"

# envsubst, rather than this shell, expands these names.
# shellcheck disable=SC2016
envsubst '${BACKEND} ${SOCKETIO} ${FRAPPE_SITE_NAME_HEADER} ${PROXY_READ_TIMEOUT} ${CLIENT_MAX_BODY_SIZE}' \
  < /templates/nginx/frappe.conf.template \
  > /etc/nginx/conf.d/frappe.conf
exec nginx -g 'daemon off;'
