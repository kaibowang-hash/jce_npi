#!/usr/bin/env bash
set -euo pipefail

environment_file=/etc/launchflow/production.env
compose_file=deploy/production/compose.yml
# shellcheck disable=SC1090
source "${environment_file}"
: "${SITE_NAME:?SITE_NAME is required}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required}"
: "${SECRETS_ROOT:?SECRETS_ROOT is required}"

archive="${1:-}"
if [[ "${CONFIRM_RESTORE:-}" != "${SITE_NAME}" ]]; then
  echo "Set CONFIRM_RESTORE=${SITE_NAME} to authorize this exact Site restore." >&2
  exit 2
fi
if [[ -z "${archive}" || ! -f "${archive}" || ! -f "${archive}.sha256" ]]; then
  echo "A complete encrypted backup archive is required." >&2
  exit 2
fi

compose() {
  docker compose --env-file "${environment_file}" -f "${compose_file}" "$@"
}

./deploy/production/scripts/backup.sh
restore_root="$(mktemp -d "${BACKUP_ROOT}/staging/restore.XXXXXX")"
cleanup() {
  if [[ -d "${restore_root}" ]]; then
    find "${restore_root}" -depth -delete
  fi
}
trap cleanup EXIT

(
  cd "$(dirname "${archive}")"
  sha256sum --check "$(basename "${archive}.sha256")" >/dev/null
)
GNUPGHOME="${restore_root}/gnupg"
export GNUPGHOME
install -d -m 0700 "${GNUPGHOME}" "${restore_root}/material"
gpg --batch --quiet --pinentry-mode loopback \
  --passphrase-file "${SECRETS_ROOT}/backup_passphrase" \
  --decrypt "${archive}" |
  tar --extract --directory "${restore_root}/material"
(
  cd "${restore_root}/material"
  sha256sum --check SHA256SUMS >/dev/null
)

database_backup="$(find "${restore_root}/material" -maxdepth 1 -type f -name '*-database.sql.gz' -print -quit)"
public_backup="$(find "${restore_root}/material" -maxdepth 1 -type f \( -name '*-files.tar' -o -name '*-files.tgz' \) ! -name '*-private-files.*' -print -quit)"
private_backup="$(find "${restore_root}/material" -maxdepth 1 -type f \( -name '*-private-files.tar' -o -name '*-private-files.tgz' \) -print -quit)"
for required_file in "${database_backup}" "${public_backup}" "${private_backup}"; do
  test -n "${required_file}" && test -s "${required_file}"
done

container_material="/backups/staging/$(basename "${restore_root}")/material"
compose exec -T backend bench --site "${SITE_NAME}" set-maintenance-mode on
root_password="$(<"${SECRETS_ROOT}/mariadb_root_password")"
if ! printf '%s\n' "${root_password}" |
  compose exec -T backend bench --site "${SITE_NAME}" restore \
    "${container_material}/$(basename "${database_backup}")" \
    --db-root-username root \
    --with-public-files "${container_material}/$(basename "${public_backup}")" \
    --with-private-files "${container_material}/$(basename "${private_backup}")"; then
  unset root_password
  echo "Restore failed; maintenance mode remains enabled." >&2
  exit 1
fi
unset root_password
compose exec -T backend bench --site "${SITE_NAME}" migrate
compose exec -T backend bench --site "${SITE_NAME}" clear-cache
compose exec -T backend bench --site "${SITE_NAME}" set-maintenance-mode off
./deploy/production/scripts/healthcheck.sh
echo "Production Site restore completed and passed health checks."
