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
verification_mode="${1:-all}"

if [[ "${verification_mode}" != "all" &&
      "${verification_mode}" != "--gate-evidence-only" &&
      "${verification_mode}" != "--gate-review-only" &&
      "${verification_mode}" != "--project-controls-only" ]]; then
  echo "Usage: scripts/verify-frappe-runtime.sh [--gate-evidence-only|--gate-review-only|--project-controls-only]" >&2
  exit 2
fi

unset \
  FRAPPE_DB_HOST \
  FRAPPE_DB_PORT \
  FRAPPE_DB_SOCKET \
  FRAPPE_DB_TYPE \
  NPI_ADMINISTRATOR_PASSWORD \
  NPI_DATABASE_ROOT_PASSWORD \
  NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
  NPI_GATE_REVIEW_RUNTIME_RUN_ID \
  NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
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
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
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

p405_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
key = "npi_p4_05_routes_disabled"
if key not in config:
    print("absent")
elif config[key] is True:
    print("true")
elif config[key] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

verify_p405_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(p405_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P4-05 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

route_disable_original_state="$(p405_route_switch_state)"
if [[ "${route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P4-05 route-disable switch." >&2
  exit 2
fi
if curl --silent --output /dev/null \
  --connect-timeout 1 --max-time 2 "${base_url}/api/method/ping"; then
  echo "Runtime port ${port} is already serving before the controlled start." >&2
  exit 2
fi

runtime_log="$(mktemp)"
server_pid=""
route_disable_config_changed=false

start_runtime_server() {
  if curl --silent --output /dev/null \
    --connect-timeout 1 --max-time 2 "${base_url}/api/method/ping"; then
    echo "Runtime port ${port} is still serving before restart." >&2
    return 1
  fi
  (
    cd "${bench_path}"
    exec env \
      -u FRAPPE_DB_HOST \
      -u FRAPPE_DB_PORT \
      -u FRAPPE_DB_SOCKET \
      -u FRAPPE_DB_TYPE \
      -u NPI_ADMINISTRATOR_PASSWORD \
      -u NPI_DATABASE_ROOT_PASSWORD \
      -u NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      -u NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      -u NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      -u NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      -u NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      -u NPI_RUNTIME_FIXTURE_PASSWORD \
      bench --site "${site_name}" serve --port "${port}" --noreload
  ) >"${runtime_log}" 2>&1 &
  server_pid="$!"
}

stop_runtime_server() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  server_pid=""
  for _attempt in $(seq 1 30); do
    if ! curl --silent --output /dev/null \
      --connect-timeout 1 --max-time 2 "${base_url}/api/method/ping"; then
      return 0
    fi
    sleep 1
  done
  echo "Local Frappe runtime did not release port ${port}." >&2
  return 1
}

wait_for_runtime_server() {
  local ready=false
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
    return 1
  fi
}

set_p405_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p4_05_routes_disabled "${value}"
  )
  verify_p405_route_switch_state "${expected}"
}

restore_p405_route_switch() {
  if ! set_p405_route_switch None absent; then
    return 1
  fi
  route_disable_config_changed=false
}

cleanup() {
  local exit_status=$?
  trap - EXIT
  if ! stop_runtime_server; then
    exit_status=1
  fi
  if [[ "${route_disable_config_changed}" == true ]]; then
    if ! restore_p405_route_switch; then
      echo "Failed to restore the P4-05 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  rm -f "${runtime_log}"
  exit "${exit_status}"
}
trap cleanup EXIT

start_runtime_server
wait_for_runtime_server

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
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
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
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
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

gate_evidence_runtime_run_id="$(
  "${bench_path}/env/bin/python" -c \
    'from uuid import uuid4; print(uuid4().hex)'
)"
if [[ ! "${gate_evidence_runtime_run_id}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "Gate evidence runtime namespace generation failed." >&2
  exit 2
fi

run_gate_evidence_runtime_verifier() {
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_GATE_EVIDENCE_RUNTIME_RUN_ID="${gate_evidence_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_gate_evidence_runtime.py" \
      --base-url "${base_url}"
  )
}

gate_review_runtime_run_id="$(
  "${bench_path}/env/bin/python" -c \
    'from uuid import uuid4; print(uuid4().hex)'
)"
if [[ ! "${gate_review_runtime_run_id}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "Gate review runtime namespace generation failed." >&2
  exit 2
fi

run_gate_review_runtime_verifier() {
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_GATE_EVIDENCE_RUNTIME_RUN_ID="${gate_review_runtime_run_id}"
    export NPI_GATE_REVIEW_RUNTIME_RUN_ID="${gate_review_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_gate_review_runtime.py" \
      --base-url "${base_url}"
  )
}

project_controls_runtime_run_id="$(
  "${bench_path}/env/bin/python" -c \
    'from uuid import uuid4; print(uuid4().hex)'
)"
if [[ ! "${project_controls_runtime_run_id}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "Project controls runtime namespace generation failed." >&2
  exit 2
fi

run_project_controls_runtime_verifier() {
  local mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID="${project_controls_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_project_controls_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_project_controls_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Project controls runtime verification mode." >&2
    exit 2
  )
}

run_project_controls_route_probe() {
  local expected_mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_GATE_EVIDENCE_RUNTIME_RUN_ID \
      NPI_GATE_REVIEW_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID="${project_controls_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_project_controls_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

if [[ "${verification_mode}" == "all" ]]; then
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
fi

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--gate-evidence-only" ]]; then
  if ! run_gate_evidence_runtime_verifier; then
    echo "Local Frappe Gate evidence runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
fi

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--gate-review-only" ]]; then
  if ! run_gate_review_runtime_verifier; then
    echo "Local Frappe Gate review runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
fi

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--project-controls-only" ]]; then
  if ! run_project_controls_runtime_verifier fresh; then
    echo "Local Frappe Project controls runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  route_disable_config_changed=true
  stop_runtime_server
  set_p405_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_project_controls_route_probe disabled; then
    echo "Local Frappe Project collaboration route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_p405_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_project_controls_route_probe recovered; then
    echo "Local Frappe Project collaboration route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_project_controls_runtime_verifier replay-only; then
    echo "Local Frappe Project controls cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
fi
