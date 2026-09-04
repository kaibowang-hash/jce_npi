#!/usr/bin/env bash
set -euo pipefail

environment_file=/etc/launchflow/production.env
compose_file=deploy/production/compose.yml
# shellcheck disable=SC1090
source "${environment_file}"
current_backend="${LAUNCHFLOW_IMAGE:?LAUNCHFLOW_IMAGE is required}"
current_spa="${LAUNCHFLOW_SPA_IMAGE:?LAUNCHFLOW_SPA_IMAGE is required}"
target_sha="${1:-}"
if [[ ! "${target_sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Provide the exact 40-character release SHA to roll back to." >&2
  exit 2
fi
target_backend="launchflow-npi:${target_sha}"
target_spa="launchflow-npi-spa:${target_sha}"
for image in "${target_backend}" "${target_spa}"; do
  if [[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>/dev/null || true)" != "${target_sha}" ]]; then
    echo "The exact rollback image is unavailable or has an invalid release label." >&2
    exit 2
  fi
done

./deploy/production/scripts/backup.sh
docker compose --env-file "${environment_file}" -f "${compose_file}" \
  exec -T backend bench --site "${SITE_NAME}" set-maintenance-mode on

export LAUNCHFLOW_IMAGE="${target_backend}"
export LAUNCHFLOW_SPA_IMAGE="${target_spa}"
if ! docker compose --env-file "${environment_file}" -f "${compose_file}" up --detach --remove-orphans; then
  export LAUNCHFLOW_IMAGE="${current_backend}"
  export LAUNCHFLOW_SPA_IMAGE="${current_spa}"
  docker compose --env-file "${environment_file}" -f "${compose_file}" up --detach --remove-orphans
  echo "Rollback startup failed; the previous images were restored and maintenance mode remains enabled." >&2
  exit 1
fi

replacement="$(mktemp /etc/launchflow/production.env.XXXXXX)"
sed \
  -e "s|^LAUNCHFLOW_IMAGE=.*|LAUNCHFLOW_IMAGE=${target_backend}|" \
  -e "s|^LAUNCHFLOW_SPA_IMAGE=.*|LAUNCHFLOW_SPA_IMAGE=${target_spa}|" \
  "${environment_file}" > "${replacement}"
chmod 0600 "${replacement}"
install -m 0600 -o root -g root "${replacement}" "${environment_file}"
find "${replacement}" -maxdepth 0 -type f -delete
unset LAUNCHFLOW_IMAGE LAUNCHFLOW_SPA_IMAGE

docker compose --env-file "${environment_file}" -f "${compose_file}" \
  exec -T backend bench --site "${SITE_NAME}" clear-cache
docker compose --env-file "${environment_file}" -f "${compose_file}" \
  exec -T backend bench --site "${SITE_NAME}" set-maintenance-mode off
./deploy/production/scripts/healthcheck.sh
echo "LaunchFlow rolled back to exact SHA ${target_sha} without a schema downgrade."
