#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
toolchain_file="${repo_root}/.devcontainer/toolchain.env"
bench_path="${repo_root}/tmp/frappe-bench"
site_name="npi.localhost"
database_host="127.0.0.1"
database_port="3306"
database_name="npi_one_runtime"
database_type="mariadb"
database_root_user="root"
database_root_password="${NPI_DATABASE_ROOT_PASSWORD:-dev-only-root}"
administrator_password="${NPI_ADMINISTRATOR_PASSWORD:-dev-only-admin}"
tenant_id="runtime-tenant"
runtime_marker="npi-one-local-runtime-disposable-v1"
site_guard="${repo_root}/scripts/verify_local_frappe_site.py"

unset \
  FRAPPE_DB_HOST \
  FRAPPE_DB_PORT \
  FRAPPE_DB_SOCKET \
  FRAPPE_DB_TYPE \
  NPI_ADMINISTRATOR_PASSWORD \
  NPI_DATABASE_ROOT_PASSWORD \
  NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
  NPI_RUNTIME_FIXTURE_PASSWORD

# shellcheck disable=SC1090
source "${toolchain_file}"
export UV_LINK_MODE=copy

for command_name in bench docker git python setsid uv; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required local Site command is missing: ${command_name}" >&2
    exit 1
  fi
done

if [[ -L "${repo_root}/tmp" || -L "${bench_path}" ]]; then
  echo "Runtime Bench path must be a physical directory inside this repository." >&2
  exit 2
fi
if [[ -e "${bench_path}" && "$(readlink -f "${bench_path}")" != "${bench_path}" ]]; then
  echo "Runtime Bench resolves outside the fixed repository path: ${bench_path}" >&2
  exit 2
fi
if [[ ! -x "${bench_path}/env/bin/python" || ! -d "${bench_path}/apps/frappe/.git" ]]; then
  echo "Pinned Bench is missing at ${bench_path}; run make frappe-init first." >&2
  exit 2
fi
if [[ "$(readlink -f "${bench_path}")" != "${bench_path}" ]]; then
  echo "Runtime Bench is not the fixed physical repository Bench: ${bench_path}" >&2
  exit 2
fi

actual_commit="$(git -C "${bench_path}/apps/frappe" rev-parse HEAD)"
if [[ "${actual_commit}" != "${FRAPPE_COMMIT}" ]]; then
  echo "Frappe commit mismatch: ${actual_commit}" >&2
  exit 1
fi
if ! {
  git -C "${bench_path}/apps/frappe" diff --name-only -z --no-ext-diff &&
    git -C "${bench_path}/apps/frappe" diff --cached --name-only -z --no-ext-diff
} |
  "${bench_path}/env/bin/python" -c \
    'import re, sys
allowed = re.compile(rb"frappe/translations/[A-Za-z0-9-]+[.]csv")
paths = {path for path in sys.stdin.buffer.read().split(b"\0") if path}
raise SystemExit(0 if all(allowed.fullmatch(path) for path in paths) else 1)'; then
  echo "Pinned Frappe core has tracked changes outside generated translation catalogs." >&2
  exit 2
fi

run_bench() {
  (cd "${bench_path}" && bench "$@")
}

run_bench_from_stdin() {
  (
    cd "${bench_path}"
    setsid --fork --wait bench "$@"
  )
}

run_site_guard() {
  local guard_mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_LOCAL_DATABASE_ROOT_PASSWORD \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    exec "${bench_path}/env/bin/python" "${site_guard}" --mode "${guard_mode}"
  )
}

run_database_server_guard() {
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_LOCAL_DATABASE_ROOT_PASSWORD="${database_root_password}"
    exec "${bench_path}/env/bin/python" "${site_guard}" --mode server
  )
}

link_application() {
  local application="$1"
  local source_path="${repo_root}/apps/${application}"
  local target_path="${bench_path}/apps/${application}"

  if [[ -L "${target_path}" ]]; then
    if [[ "$(readlink -f "${target_path}")" != "$(readlink -f "${source_path}")" ]]; then
      echo "Bench app link points outside this repository: ${target_path}" >&2
      exit 2
    fi
  elif [[ -e "${target_path}" ]]; then
    echo "Refusing to replace an existing Bench app path: ${target_path}" >&2
    exit 2
  else
    ln -s "${source_path}" "${target_path}"
  fi

  uv pip install --python "${bench_path}/env/bin/python" --no-deps --editable "${source_path}"
  if ! grep -Fqx "${application}" "${bench_path}/sites/apps.txt"; then
    printf '%s\n' "${application}" >>"${bench_path}/sites/apps.txt"
  fi
}

site_created=false
site_path="${bench_path}/sites/${site_name}"
if [[ -e "${site_path}" && ! -d "${site_path}" ]]; then
  echo "Runtime Site path exists but is not a directory." >&2
  exit 2
fi
if [[ -d "${site_path}" ]]; then
  if [[ -L "${site_path}" ||
        "$(readlink -f "${site_path}")" != "${site_path}" ]]; then
    echo "Runtime Site is not the fixed physical repository Site." >&2
    exit 2
  fi
  # Configuration-only validation happens before starting services or invoking
  # any command that can mutate the existing Site.
  run_site_guard config
else
  site_created=true
fi

docker compose --project-directory "${repo_root}" -f "${repo_root}/docker-compose.yml" up -d --wait

if [[ "${site_created}" == true ]]; then
  # Prove that the fixed loopback endpoint is the controlled local MariaDB
  # service and that the dedicated identity is unused before creating it.
  run_database_server_guard
  printf '%s\n%s\n%s\n' \
    "${database_root_password}" \
    "${administrator_password}" \
    "${administrator_password}" |
    run_bench_from_stdin new-site "${site_name}" \
      --db-name "${database_name}" \
      --db-type "${database_type}" \
      --db-host "${database_host}" \
      --db-port "${database_port}" \
      --db-root-username "${database_root_user}" \
      --mariadb-user-host-login-scope "%" \
      --set-default
  database_root_password=""
  if [[ -L "${site_path}" ||
        "$(readlink -f "${site_path}")" != "${site_path}" ]]; then
    echo "Runtime Site is not the fixed physical repository Site." >&2
    exit 2
  fi
  # new-site created only the explicitly named Frappe database. Prove its live
  # database/user identity before installing apps or changing Site settings.
  run_site_guard database
else
  # The strict configuration anchor above is followed by a live identity probe
  # before any existing-Site command is allowed to run.
  run_site_guard live
fi

run_bench set-config -g redis_cache redis://127.0.0.1:6379/0
run_bench set-config -g redis_queue redis://127.0.0.1:6379/1
run_bench set-config -g redis_socketio redis://127.0.0.1:6379/2

link_application npi_core
link_application npi_integration

run_bench --site "${site_name}" set-config npi_tenant_id "${tenant_id}"
run_bench --site "${site_name}" set-config npi_runtime_disposable_marker "${runtime_marker}"
run_bench --site "${site_name}" set-config --parse developer_mode 1
run_site_guard live

site_has_application() {
  run_bench --site "${site_name}" list-apps --format json | python -c \
    'import json, sys; app=sys.argv[1]; data=json.load(sys.stdin); raise SystemExit(0 if any(app in apps for apps in data.values()) else 1)' \
    "$1"
}

for application in npi_core npi_integration; do
  if ! site_has_application "${application}"; then
    run_bench --site "${site_name}" install-app "${application}"
  fi
done

# Re-prove the exact live target immediately before password, migration, and
# cache mutations, even after application installation.
run_site_guard live
printf '%s\n' "${administrator_password}" |
  run_bench_from_stdin --site "${site_name}" set-admin-password
run_bench --site "${site_name}" migrate
run_bench --site "${site_name}" clear-cache

site_has_application npi_core
site_has_application npi_integration
run_site_guard live
printf 'site=%s\n' "${site_name}"
printf 'frappe_commit=%s\n' "${actual_commit}"
echo "local NPI One Site initialization passed"
