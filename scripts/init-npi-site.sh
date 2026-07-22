#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
toolchain_file="${NPI_TOOLCHAIN_FILE:-${repo_root}/.devcontainer/toolchain.env}"
bench_path="${NPI_FRAPPE_BENCH_PATH:-${repo_root}/tmp/frappe-bench}"
site_name="${NPI_FRAPPE_SITE_NAME:-npi.localhost}"
database_host="${NPI_DATABASE_HOST:-127.0.0.1}"
database_port="${NPI_DATABASE_PORT:-3306}"
database_root_password="${NPI_DATABASE_ROOT_PASSWORD:-dev-only-root}"
administrator_password="${NPI_ADMINISTRATOR_PASSWORD:-dev-only-admin}"

# shellcheck disable=SC1090
source "${toolchain_file}"
export UV_LINK_MODE=copy

for command_name in bench docker git uv; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required local Site command is missing: ${command_name}" >&2
    exit 1
  fi
done

if [[ ! "${site_name}" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]]; then
  echo "Invalid local Frappe Site name: ${site_name}" >&2
  exit 2
fi
if [[ ! -x "${bench_path}/env/bin/python" || ! -d "${bench_path}/apps/frappe/.git" ]]; then
  echo "Pinned Bench is missing at ${bench_path}; run make frappe-init first." >&2
  exit 2
fi

actual_commit="$(git -C "${bench_path}/apps/frappe" rev-parse HEAD)"
if [[ "${actual_commit}" != "${FRAPPE_COMMIT}" ]]; then
  echo "Frappe commit mismatch: ${actual_commit}" >&2
  exit 1
fi

docker compose --project-directory "${repo_root}" -f "${repo_root}/docker-compose.yml" up -d --wait

run_bench() {
  (cd "${bench_path}" && bench "$@")
}

run_bench set-config -g redis_cache redis://127.0.0.1:6379/0
run_bench set-config -g redis_queue redis://127.0.0.1:6379/1
run_bench set-config -g redis_socketio redis://127.0.0.1:6379/2

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

link_application npi_core
link_application npi_integration

if [[ ! -d "${bench_path}/sites/${site_name}" ]]; then
  run_bench new-site "${site_name}" \
    --db-host "${database_host}" \
    --db-port "${database_port}" \
    --db-root-password "${database_root_password}" \
    --admin-password "${administrator_password}" \
    --install-app npi_core \
    --set-default
fi

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

run_bench --site "${site_name}" migrate
run_bench --site "${site_name}" clear-cache

site_has_application npi_core
site_has_application npi_integration
printf 'site=%s\n' "${site_name}"
printf 'frappe_commit=%s\n' "${actual_commit}"
echo "local NPI One Site initialization passed"
