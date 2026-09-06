#!/usr/bin/env bash
set -euo pipefail

environment_file=/etc/launchflow/production.env
compose_file=deploy/production/compose.yml
if [[ ! -r "${environment_file}" ]]; then
  echo "Production environment file is unavailable." >&2
  exit 1
fi
# shellcheck disable=SC1090
source "${environment_file}"
: "${SITE_NAME:?SITE_NAME is required}"

compose() {
  docker compose --env-file "${environment_file}" -f "${compose_file}" "$@"
}

required_services=(
  backend db frappe-frontend queue-long queue-short redis-cache redis-queue scheduler spa websocket
)
mapfile -t running_services < <(compose ps --services --status running | sort)
if [[ "${running_services[*]}" != "${required_services[*]}" ]]; then
  echo "One or more required LaunchFlow services are not running." >&2
  compose ps >&2
  exit 1
fi

curl --fail --silent --show-error --max-time 15 "https://${SITE_NAME}/healthz" >/dev/null
status_file="$(mktemp /tmp/launchflow-health.XXXXXX)"
trap 'find "${status_file}" -maxdepth 0 -type f -delete' EXIT
http_status="$(curl --silent --show-error --max-time 15 \
  --output "${status_file}" --write-out '%{http_code}' \
  "https://${SITE_NAME}/api/npi/v1/session/bootstrap")"
if [[ "${http_status}" != 401 ]] ||
  ! jq -e '.code == "AUTHENTICATION_REQUIRED"' "${status_file}" >/dev/null; then
  echo "The unauthenticated NPI API contract is unhealthy." >&2
  exit 1
fi

compose exec -T backend bench --site "${SITE_NAME}" scheduler status |
  grep -Fq 'enabled'
echo "LaunchFlow production health check passed."
