#!/usr/bin/env bash
set -euo pipefail

environment_file=/etc/launchflow/production.env
# shellcheck disable=SC1090
source "${environment_file}"
: "${SITE_NAME:?SITE_NAME is required}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required}"
: "${SECRETS_ROOT:?SECRETS_ROOT is required}"
: "${LAUNCHFLOW_IMAGE:?LAUNCHFLOW_IMAGE is required}"

archive="${1:-}"
if [[ -z "${archive}" ]]; then
  archive="$(find "${BACKUP_ROOT}/encrypted" -maxdepth 1 -type f -name 'launchflow-*.tar.gpg' -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)"
fi
if [[ -z "${archive}" || ! -f "${archive}" || ! -f "${archive}.sha256" ]]; then
  echo "A complete encrypted backup archive is required." >&2
  exit 2
fi

(
  cd "$(dirname "${archive}")"
  sha256sum --check "$(basename "${archive}.sha256")" >/dev/null
)

run_id="$(date -u +%Y%m%d%H%M%S)-$$"
network="launchflow-restore-${run_id}"
db_container="launchflow-restore-db-${run_id}"
redis_container="launchflow-restore-redis-${run_id}"
sites_volume="launchflow_restore_sites_${run_id}"
db_volume="launchflow_restore_db_${run_id}"
restore_root="$(mktemp -d /tmp/launchflow-restore.XXXXXX)"

cleanup() {
  docker container rm --force "${db_container}" "${redis_container}" >/dev/null 2>&1 || true
  docker volume rm "${sites_volume}" "${db_volume}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
  if [[ -d "${restore_root}" ]]; then
    find "${restore_root}" -depth -delete
  fi
}
trap cleanup EXIT

install -m 0400 -o 1000 -g 1000 "${SECRETS_ROOT}/mariadb_root_password" "${restore_root}/mariadb_root_password"
install -m 0400 -o 1000 -g 1000 "${SECRETS_ROOT}/administrator_password" "${restore_root}/administrator_password"
install -d -m 0700 -o 1000 -g 1000 "${restore_root}/material" "${restore_root}/gnupg"
GNUPGHOME="${restore_root}/gnupg" gpg --batch --quiet --pinentry-mode loopback \
  --passphrase-file "${SECRETS_ROOT}/backup_passphrase" \
  --decrypt "${archive}" |
  tar --extract --directory "${restore_root}/material"
chown -R 1000:1000 "${restore_root}/material"
(
  cd "${restore_root}/material"
  sha256sum --check SHA256SUMS >/dev/null
)

database_backup="$(find "${restore_root}/material" -maxdepth 1 -type f -name '*-database.sql.gz' -print -quit)"
public_backup="$(find "${restore_root}/material" -maxdepth 1 -type f \( -name '*-files.tar' -o -name '*-files.tgz' \) ! -name '*-private-files.*' -print -quit)"
private_backup="$(find "${restore_root}/material" -maxdepth 1 -type f \( -name '*-private-files.tar' -o -name '*-private-files.tgz' \) -print -quit)"
config_backup="$(find "${restore_root}/material" -maxdepth 1 -type f -name '*-site_config_backup.json' -print -quit)"
for required_file in "${database_backup}" "${public_backup}" "${private_backup}" "${config_backup}"; do
  if [[ -z "${required_file}" || ! -s "${required_file}" ]]; then
    echo "The restore rehearsal material is incomplete." >&2
    exit 1
  fi
done
chown -R 1000:1000 "${restore_root}"

docker network create --internal "${network}" >/dev/null
docker volume create "${sites_volume}" >/dev/null
docker volume create "${db_volume}" >/dev/null
docker run --detach --name "${db_container}" --network "${network}" --network-alias db \
  --mount "type=bind,src=${restore_root}/mariadb_root_password,dst=/run/secrets/mariadb_root_password,readonly" \
  --mount "type=volume,src=${db_volume},dst=/var/lib/mysql" \
  --env MARIADB_ROOT_PASSWORD_FILE=/run/secrets/mariadb_root_password \
  mariadb@sha256:92e50059ea0a5965a33ef751970eab37d421b91ebbd01ac909039cffe159e574 \
  --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci >/dev/null
docker run --detach --name "${redis_container}" --network "${network}" \
  --network-alias redis-cache --network-alias redis-queue \
  redis@sha256:ccd6aa8d45ff3f033d6fa15b8cc1a50579f65c89f38cf9bb607a954c4f2128ed >/dev/null

for _attempt in $(seq 1 60); do
  if docker exec "${db_container}" healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec "${db_container}" healthcheck.sh --connect --innodb_initialized >/dev/null
docker exec "${redis_container}" redis-cli ping | grep -Fq PONG

restore_site=restore.launchflow.invalid
restore_db="restore_${run_id//[^0-9]/}"
docker run --rm --network "${network}" \
  --mount "type=volume,src=${sites_volume},dst=/home/frappe/frappe-bench/sites" \
  --mount "type=bind,src=${restore_root},dst=/restore,readonly" \
  --env "RESTORE_SITE=${restore_site}" \
  --env "RESTORE_DATABASE=${restore_db}" \
  --env "DATABASE_BACKUP=/restore/material/$(basename "${database_backup}")" \
  --env "PUBLIC_BACKUP=/restore/material/$(basename "${public_backup}")" \
  --env "PRIVATE_BACKUP=/restore/material/$(basename "${private_backup}")" \
  --env "CONFIG_BACKUP=/restore/material/$(basename "${config_backup}")" \
  "${LAUNCHFLOW_IMAGE}" bash -euc '
    cd /home/frappe/frappe-bench
    bench set-config -g db_host db
    bench set-config -gp db_port 3306
    bench set-config -g redis_cache redis://redis-cache:6379
    bench set-config -g redis_queue redis://redis-queue:6379
    bench set-config -g redis_socketio redis://redis-queue:6379
    printf "frappe\nnpi_core\nnpi_integration\n" > sites/apps.txt
    root_password="$(</restore/mariadb_root_password)"
    administrator_password="$(</restore/administrator_password)"
    printf "%s\n%s\n%s\n" "${root_password}" "${administrator_password}" "${administrator_password}" |
      bench new-site "${RESTORE_SITE}" --db-name "${RESTORE_DATABASE}" --db-host db --db-port 3306 --db-root-username root --mariadb-user-host-login-scope "%" --set-default
    python - "${CONFIG_BACKUP}" "sites/${RESTORE_SITE}/site_config.json" <<"PY"
import json
import pathlib
import sys

source = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
target_path = pathlib.Path(sys.argv[2])
target = json.loads(target_path.read_text(encoding="utf-8"))
if not isinstance(source.get("encryption_key"), str) or not source["encryption_key"]:
    raise SystemExit("The backup Site encryption key is unavailable.")
target["encryption_key"] = source["encryption_key"]
target_path.write_text(json.dumps(target, indent=1) + "\n", encoding="utf-8")
PY
    printf "%s\n" "${root_password}" |
      bench --site "${RESTORE_SITE}" restore "${DATABASE_BACKUP}" --db-root-username root \
        --with-public-files "${PUBLIC_BACKUP}" --with-private-files "${PRIVATE_BACKUP}"
    bench --site "${RESTORE_SITE}" migrate
    bench --site "${RESTORE_SITE}" list-apps --format json > /tmp/restored-apps.json
    python - /tmp/restored-apps.json <<"PY"
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
apps = {app for values in data.values() for app in values}
required = {"frappe", "npi_core", "npi_integration"}
if not required.issubset(apps):
    raise SystemExit("The restored Site application identity is incomplete.")
PY
    test -d "sites/${RESTORE_SITE}/public/files"
    test -d "sites/${RESTORE_SITE}/private/files"
  '

echo "Encrypted database/public/private-file restore rehearsal passed in an isolated network."
