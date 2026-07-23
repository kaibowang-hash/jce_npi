#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
toolchain_file="${repo_root}/.devcontainer/toolchain.env"
bench_path="${repo_root}/tmp/frappe-bench"
site_name="npi.localhost"
tenant_id="runtime-tenant"
runtime_marker="npi-one-local-runtime-disposable-v1"
port="8003"
base_url="http://127.0.0.1:${port}"
runtime_administrator_password="${NPI_ADMINISTRATOR_PASSWORD:-dev-only-admin}"
runtime_fixture_password="${NPI_RUNTIME_FIXTURE_PASSWORD:-DevOnly_Runtime_2026!}"
site_guard="${repo_root}/scripts/verify_local_frappe_site.py"

unset \
  FRAPPE_DB_HOST \
  FRAPPE_DB_PORT \
  FRAPPE_DB_SOCKET \
  FRAPPE_DB_TYPE \
  NPI_ADMINISTRATOR_PASSWORD \
  NPI_DATABASE_ROOT_PASSWORD \
  NPI_PROJECT_WORK_RUNTIME_RUN_ID \
  NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
  NPI_RUNTIME_FIXTURE_PASSWORD

# shellcheck disable=SC1090
source "${toolchain_file}"

if [[ -L "${repo_root}/tmp" || -L "${bench_path}" ||
      ! -d "${bench_path}" ||
      "$(readlink -f "${bench_path}")" != "${bench_path}" ]]; then
  echo "Runtime verification requires the fixed physical repository Bench." >&2
  exit 2
fi
if [[ ! -d "${bench_path}/sites/${site_name}" ||
      -L "${bench_path}/sites/${site_name}" ||
      "$(readlink -f "${bench_path}/sites/${site_name}")" != "${bench_path}/sites/${site_name}" ]]; then
  echo "Local Site is missing; run make frappe-site-init first." >&2
  exit 2
fi
if [[ ! -x "${bench_path}/env/bin/python" ||
      ! -d "${bench_path}/apps/frappe/.git" ]]; then
  echo "Runtime verification requires the pinned Frappe application." >&2
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

run_site_guard() {
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_LOCAL_DATABASE_ROOT_PASSWORD \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    exec "${bench_path}/env/bin/python" "${site_guard}" --mode live
  )
}

# This read-only probe must pass before serve can open the Site or any verifier
# can write a disposable fixture.
run_site_guard
if [[ "${tenant_id}" != "runtime-tenant" ||
      "${runtime_marker}" != "npi-one-local-runtime-disposable-v1" ]]; then
  echo "Runtime safety constants drifted." >&2
  exit 2
fi

runtime_log="$(mktemp)"
server_pid=""
cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  rm -f "${runtime_log}"
}
trap cleanup EXIT

(
  cd "${bench_path}"
  exec env \
    -u FRAPPE_DB_HOST \
    -u FRAPPE_DB_PORT \
    -u FRAPPE_DB_SOCKET \
    -u FRAPPE_DB_TYPE \
    -u NPI_ADMINISTRATOR_PASSWORD \
    -u NPI_DATABASE_ROOT_PASSWORD \
    -u NPI_PROJECT_WORK_RUNTIME_RUN_ID \
    -u NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
    -u NPI_RUNTIME_FIXTURE_PASSWORD \
    bench --site "${site_name}" serve --port "${port}" --noreload
) >"${runtime_log}" 2>&1 &
server_pid="$!"

ready=false
for _attempt in $(seq 1 60); do
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    break
  fi
  if curl --fail --silent --show-error --output /dev/null \
    "${base_url}/api/method/ping"; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "${ready}" != true ]]; then
  echo "Local Frappe runtime did not become ready." >&2
  tail -100 "${runtime_log}" >&2
  exit 1
fi

run_runtime_verifier() {
  local verifier_path="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    exec python "${verifier_path}" --base-url "${base_url}"
  )
}

project_work_runtime_run_id="$(
  "${bench_path}/env/bin/python" -c \
    'from uuid import uuid4; print(uuid4().hex)'
)"
if [[ ! "${project_work_runtime_run_id}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "Project work runtime namespace generation failed." >&2
  exit 2
fi

run_project_work_runtime_verifier() {
  local mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_PROJECT_WORK_RUNTIME_RUN_ID="${project_work_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_project_work_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_project_work_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Project work runtime verification mode." >&2
    exit 2
  )
}

if ! run_runtime_verifier "${repo_root}/scripts/verify_frappe_runtime.py"; then
  echo "Local Frappe runtime verification failed." >&2
  tail -100 "${runtime_log}" >&2
  exit 1
fi

if ! run_runtime_verifier "${repo_root}/scripts/verify_project_runtime.py"; then
  echo "Local Frappe Project runtime verification failed." >&2
  tail -100 "${runtime_log}" >&2
  exit 1
fi

if ! run_project_work_runtime_verifier fresh; then
  echo "Local Frappe Project work runtime verification failed." >&2
  tail -100 "${runtime_log}" >&2
  exit 1
fi

if ! run_project_work_runtime_verifier replay-only; then
  echo "Local Frappe Project work cross-process replay verification failed." >&2
  tail -100 "${runtime_log}" >&2
  exit 1
fi
