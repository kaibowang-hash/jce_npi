#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bench_path="${NPI_FRAPPE_BENCH_PATH:-${repo_root}/tmp/frappe-bench}"
site_name="${NPI_FRAPPE_SITE_NAME:-npi.localhost}"
port="${NPI_FRAPPE_RUNTIME_PORT:-8003}"
administrator_user="${NPI_ADMINISTRATOR_USER:-Administrator}"
administrator_password="${NPI_ADMINISTRATOR_PASSWORD:-dev-only-admin}"
fixture_user="${NPI_RUNTIME_FIXTURE_USER:-npi-runtime-user@example.invalid}"
fixture_password="${NPI_RUNTIME_FIXTURE_PASSWORD:-DevOnly_Runtime_2026!}"

if [[ ! "${port}" =~ ^[0-9]+$ || "${port}" -lt 1024 || "${port}" -gt 65535 ]]; then
  echo "Invalid local Frappe runtime port: ${port}" >&2
  exit 2
fi
if [[ ! -d "${bench_path}/sites/${site_name}" ]]; then
  echo "Local Site is missing; run make frappe-site-init first." >&2
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
  exec bench --site "${site_name}" serve --port "${port}" --noreload
) >"${runtime_log}" 2>&1 &
server_pid="$!"

ready=false
for _attempt in $(seq 1 60); do
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    break
  fi
  if curl --silent --output /dev/null "http://127.0.0.1:${port}/api/npi/v1/session/bootstrap"; then
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

if ! python "${repo_root}/scripts/verify_frappe_runtime.py" \
  --base-url "http://127.0.0.1:${port}" \
  --administrator-user "${administrator_user}" \
  --administrator-password "${administrator_password}" \
  --fixture-user "${fixture_user}" \
  --fixture-password "${fixture_password}"; then
  echo "Local Frappe runtime verification failed." >&2
  tail -100 "${runtime_log}" >&2
  exit 1
fi
