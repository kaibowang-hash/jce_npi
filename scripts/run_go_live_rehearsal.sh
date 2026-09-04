#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
bench_path="${repo_root}/tmp/frappe-bench"
site_name="npi.localhost"
database_name="npi_one_runtime"
runtime_marker="npi-one-local-runtime-disposable-v1"
site_path="${bench_path}/sites/${site_name}"
verifier="${repo_root}/scripts/verify_go_live_rehearsal.py"
database_root_password="${NPI_P9_07_DATABASE_ROOT_PASSWORD:-dev-only-root}"
rehearsal_root="${RUNNER_TEMP:-/tmp}"
document_runtime_run_id="${NPI_DOCUMENT_RUNTIME_RUN_ID:-}"

if [[ "$#" -ne 0 ]]; then
  echo "P9-07 recovery rehearsal accepts no caller-selected target or command." >&2
  exit 2
fi
if [[ ! "${document_runtime_run_id}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "P9-07 recovery rehearsal requires the fixed runtime namespace." >&2
  exit 2
fi
if [[ -L "${repo_root}/tmp" || -L "${bench_path}" || -L "${site_path}" ||
      ! -x "${bench_path}/env/bin/python" || ! -f "${verifier}" ||
      "$(readlink -f "${bench_path}")" != "${bench_path}" ||
      "$(readlink -f "${site_path}")" != "${site_path}" ]]; then
  echo "P9-07 recovery rehearsal requires the fixed physical disposable Bench and Site." >&2
  exit 2
fi
if [[ ! -d "${rehearsal_root}" || -L "${rehearsal_root}" ]]; then
  echo "P9-07 recovery rehearsal temporary root is unavailable." >&2
  exit 2
fi
rehearsal_root="$(cd "${rehearsal_root}" && pwd -P)"
rehearsal_dir="$(mktemp -d "${rehearsal_root}/npi-p9-07-rehearsal.XXXXXX")"
chmod 0700 "${rehearsal_dir}"
export NPI_P9_07_REHEARSAL_ROOT="${rehearsal_root}"

public_files="${site_path}/public/files"
private_files="${site_path}/private/files"
quarantined_public="${rehearsal_dir}/quarantined-public-files"
quarantined_private="${rehearsal_dir}/quarantined-private-files"
files_quarantined=false
restore_completed=false
fixture_prepared=false

run_verifier() {
  local mode="$1"
  shift
  (
    cd "${bench_path}/sites"
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_P9_07_DATABASE_ROOT_PASSWORD
    exec "${bench_path}/env/bin/python" "${verifier}" \
      --mode "${mode}" "$@"
  )
}

restore_quarantined_files() {
  if [[ "${files_quarantined}" != true ]]; then
    return 0
  fi
  if [[ "$(readlink -f "${site_path}")" != "${site_path}" ||
        ! -d "${quarantined_public}" || ! -d "${quarantined_private}" ]]; then
    return 1
  fi
  rm -rf -- "${public_files}" "${private_files}"
  mv -- "${quarantined_public}" "${public_files}"
  mv -- "${quarantined_private}" "${private_files}"
  files_quarantined=false
}

cleanup() {
  local exit_status=$?
  trap - EXIT
  if [[ "${restore_completed}" != true ]]; then
    restore_quarantined_files || exit_status=1
  fi
  if [[ "${fixture_prepared}" == true ]]; then
    if ! run_verifier cleanup >/dev/null 2>/dev/null; then
      exit_status=1
    fi
  fi
  if [[ -d "${rehearsal_dir}" && ! -L "${rehearsal_dir}" &&
        "$(dirname "$(readlink -f "${rehearsal_dir}")")" == "${rehearsal_root}" &&
        "$(basename "${rehearsal_dir}")" =~ ^npi-p9-07-rehearsal\.[A-Za-z0-9]{6}$ ]]; then
    rm -rf -- "${rehearsal_dir}"
  else
    exit_status=1
  fi
  database_root_password=""
  exit "${exit_status}"
}
trap cleanup EXIT

run_verifier manifest >"${rehearsal_dir}/release-manifest.json"
chmod 0600 "${rehearsal_dir}/release-manifest.json"
run_verifier prepare >/dev/null
fixture_prepared=true
run_verifier capture-tree >"${rehearsal_dir}/pre-backup-files.json"
chmod 0600 "${rehearsal_dir}/pre-backup-files.json"

backup_started="${SECONDS}"
(
  cd "${bench_path}"
  bench --site "${site_name}" backup \
    --with-files \
    --compress \
    --backup-path-db "${rehearsal_dir}/database.sql.gz" \
    --backup-path-files "${rehearsal_dir}/public-files.tgz" \
    --backup-path-private-files "${rehearsal_dir}/private-files.tgz" \
    --backup-path-conf "${rehearsal_dir}/site-config.json" \
    >/dev/null 2>/dev/null
)
backup_seconds="$((SECONDS - backup_started))"
chmod 0600 \
  "${rehearsal_dir}/database.sql.gz" \
  "${rehearsal_dir}/public-files.tgz" \
  "${rehearsal_dir}/private-files.tgz" \
  "${rehearsal_dir}/site-config.json"
run_verifier backup-inventory \
  --rehearsal-dir "${rehearsal_dir}" \
  >"${rehearsal_dir}/backup-inventory.json"
chmod 0600 "${rehearsal_dir}/backup-inventory.json"

run_verifier post-backup >/dev/null
mv -- "${public_files}" "${quarantined_public}"
mv -- "${private_files}" "${quarantined_private}"
files_quarantined=true
mkdir -m 0700 -- "${public_files}" "${private_files}"

restore_started="${SECONDS}"
(
  cd "${bench_path}"
  bench --site "${site_name}" restore \
    "${rehearsal_dir}/database.sql.gz" \
    --db-root-username root \
    --db-root-password "${database_root_password}" \
    --with-public-files "${rehearsal_dir}/public-files.tgz" \
    --with-private-files "${rehearsal_dir}/private-files.tgz" \
    >/dev/null 2>/dev/null
)
restore_seconds="$((SECONDS - restore_started))"
restore_completed=true
files_quarantined=false

run_verifier verify-restore >/dev/null
run_verifier verify-tree --rehearsal-dir "${rehearsal_dir}" >/dev/null

forward_fix_started="${SECONDS}"
for _migration_attempt in 1 2; do
  (
    cd "${bench_path}"
    bench --site "${site_name}" migrate >/dev/null 2>/dev/null
  )
done
run_verifier forward-fix --rehearsal-dir "${rehearsal_dir}" >/dev/null
forward_fix_seconds="$((SECONDS - forward_fix_started))"

export NPI_P9_07_BACKUP_SECONDS="${backup_seconds}"
export NPI_P9_07_RESTORE_SECONDS="${restore_seconds}"
export NPI_P9_07_FORWARD_FIX_SECONDS="${forward_fix_seconds}"
run_verifier result --rehearsal-dir "${rehearsal_dir}"
run_verifier finalize >/dev/null
fixture_prepared=false

if [[ "${site_name}" != "npi.localhost" ||
      "${database_name}" != "npi_one_runtime" ||
      "${runtime_marker}" != "npi-one-local-runtime-disposable-v1" ]]; then
  echo "P9-07 recovery rehearsal target constants drifted." >&2
  exit 2
fi
