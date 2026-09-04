#!/usr/bin/env bash
set -euo pipefail

environment_file=/etc/launchflow/production.env
compose_file=deploy/production/compose.yml
# shellcheck disable=SC1090
source "${environment_file}"
: "${SITE_NAME:?SITE_NAME is required}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required}"
: "${SECRETS_ROOT:?SECRETS_ROOT is required}"

backup_key="${SECRETS_ROOT}/backup_passphrase"
if [[ ! -r "${backup_key}" ]]; then
  echo "The backup encryption key is unavailable." >&2
  exit 1
fi

compose() {
  docker compose --env-file "${environment_file}" -f "${compose_file}" "$@"
}

exec 9>"${BACKUP_ROOT}/.backup.lock"
flock -n 9 || {
  echo "Another LaunchFlow backup is already running." >&2
  exit 1
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
staging_parent="${BACKUP_ROOT}/staging"
encrypted_root="${BACKUP_ROOT}/encrypted"
install -d -m 0700 "${staging_parent}" "${encrypted_root}"
staging_dir="$(mktemp -d "${staging_parent}/backup-${timestamp}.XXXXXX")"
cleanup() {
  if [[ -d "${staging_dir}" ]]; then
    find "${staging_dir}" -depth -delete
  fi
}
trap cleanup EXIT

container_staging="/backups/staging/$(basename "${staging_dir}")"
compose exec -T backend bench --site "${SITE_NAME}" backup \
  --with-files --compress --backup-path "${container_staging}"

database_backup="$(find "${staging_dir}" -maxdepth 1 -type f -name '*-database.sql.gz' -print -quit)"
public_backup="$(find "${staging_dir}" -maxdepth 1 -type f \( -name '*-files.tar' -o -name '*-files.tgz' \) ! -name '*-private-files.*' -print -quit)"
private_backup="$(find "${staging_dir}" -maxdepth 1 -type f \( -name '*-private-files.tar' -o -name '*-private-files.tgz' \) -print -quit)"
config_backup="$(find "${staging_dir}" -maxdepth 1 -type f -name '*-site_config_backup.json' -print -quit)"
for required_file in "${database_backup}" "${public_backup}" "${private_backup}" "${config_backup}"; do
  if [[ -z "${required_file}" || ! -s "${required_file}" ]]; then
    echo "The full Site backup is incomplete." >&2
    exit 1
  fi
done

(
  cd "${staging_dir}"
  find . -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum
) > "${staging_dir}/SHA256SUMS"

archive="${encrypted_root}/launchflow-${SITE_NAME}-${timestamp}.tar.gpg"
GNUPGHOME="${staging_dir}/gnupg"
export GNUPGHOME
install -d -m 0700 "${GNUPGHOME}"
tar --create --directory "${staging_dir}" \
  --exclude ./gnupg --file - . |
  gpg --batch --yes --pinentry-mode loopback \
    --passphrase-file "${backup_key}" \
    --symmetric --cipher-algo AES256 --output "${archive}"
chmod 0600 "${archive}"
sha256sum "${archive}" > "${archive}.sha256"
chmod 0600 "${archive}.sha256"
gpg --batch --quiet --pinentry-mode loopback \
  --passphrase-file "${backup_key}" --decrypt "${archive}" |
  tar --list --file - >/dev/null

find "${encrypted_root}" -maxdepth 1 -type f \
  \( -name 'launchflow-*.tar.gpg' -o -name 'launchflow-*.tar.gpg.sha256' \) \
  -mtime +13 -delete

echo "BACKUP_ARCHIVE=${archive}"
