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
      "${verification_mode}" != "--project-controls-only" &&
      "${verification_mode}" != "--document-only" &&
      "${verification_mode}" != "--tooling-only" ]]; then
  echo "Usage: scripts/verify-frappe-runtime.sh [--gate-evidence-only|--gate-review-only|--project-controls-only|--document-only|--tooling-only]" >&2
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
  NPI_DOCUMENT_RUNTIME_RUN_ID \
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
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

document_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
key = "npi_p5_01_routes_disabled"
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

document_release_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
key = "npi_p5_02_routes_disabled"
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

document_baseline_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p5_03_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

engineering_bom_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p5_04_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

publish_request_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p5_05_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

controlled_print_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p5_06_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_01_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_set_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_02_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_revision_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_03_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_manufacturing_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_04_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_engineering_controls_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_05_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_acceptance_assets_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_06_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
    print("false")
else:
    print("invalid")' \
    "${bench_path}/sites/${site_name}/site_config.json"
}

tooling_import_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_07_routes_disabled"
if switch_name not in config:
    print("absent")
elif config[switch_name] is True:
    print("true")
elif config[switch_name] is False:
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

verify_document_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(document_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P5-01 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_document_release_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(document_release_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P5-02 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_document_baseline_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(document_baseline_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P5-03 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_engineering_bom_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(engineering_bom_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P5-04 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_publish_request_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(publish_request_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P5-05 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_controlled_print_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(controlled_print_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P5-06 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-01 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_set_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_set_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-02 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_revision_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_revision_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-03 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_manufacturing_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_manufacturing_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-04 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_engineering_controls_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_engineering_controls_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-05 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_acceptance_assets_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_acceptance_assets_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-06 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_tooling_import_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_import_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-07 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

route_disable_original_state="$(p405_route_switch_state)"
if [[ "${route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P4-05 route-disable switch." >&2
  exit 2
fi
document_route_disable_original_state="$(document_route_switch_state)"
if [[ "${document_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P5-01 route-disable switch." >&2
  exit 2
fi
document_release_route_disable_original_state="$(
  document_release_route_switch_state
)"
if [[ "${document_release_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P5-02 route-disable switch." >&2
  exit 2
fi
document_baseline_route_disable_original_state="$(
  document_baseline_route_switch_state
)"
if [[ "${document_baseline_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P5-03 route-disable switch." >&2
  exit 2
fi
engineering_bom_route_disable_original_state="$(
  engineering_bom_route_switch_state
)"
if [[ "${engineering_bom_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P5-04 route-disable switch." >&2
  exit 2
fi
publish_request_route_disable_original_state="$(
  publish_request_route_switch_state
)"
if [[ "${publish_request_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P5-05 route-disable switch." >&2
  exit 2
fi
controlled_print_route_disable_original_state="$(
  controlled_print_route_switch_state
)"
if [[ "${controlled_print_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P5-06 route-disable switch." >&2
  exit 2
fi
tooling_route_disable_original_state="$(tooling_route_switch_state)"
if [[ "${tooling_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-01 route-disable switch." >&2
  exit 2
fi
tooling_set_route_disable_original_state="$(tooling_set_route_switch_state)"
if [[ "${tooling_set_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-02 route-disable switch." >&2
  exit 2
fi
tooling_revision_route_disable_original_state="$(
  tooling_revision_route_switch_state
)"
if [[ "${tooling_revision_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-03 route-disable switch." >&2
  exit 2
fi
tooling_manufacturing_route_disable_original_state="$(
  tooling_manufacturing_route_switch_state
)"
if [[ "${tooling_manufacturing_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-04 route-disable switch." >&2
  exit 2
fi
tooling_engineering_controls_route_disable_original_state="$(
  tooling_engineering_controls_route_switch_state
)"
if [[ "${tooling_engineering_controls_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-05 route-disable switch." >&2
  exit 2
fi
tooling_acceptance_assets_route_disable_original_state="$(
  tooling_acceptance_assets_route_switch_state
)"
if [[ "${tooling_acceptance_assets_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-06 route-disable switch." >&2
  exit 2
fi
tooling_import_route_disable_original_state="$(tooling_import_route_switch_state)"
if [[ "${tooling_import_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-07 route-disable switch." >&2
  exit 2
fi
if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--document-only" ||
      "${verification_mode}" == "--tooling-only" ]]; then
  for _migration_attempt in 1 2; do
    (
      cd "${bench_path}"
      bench --site "${site_name}" migrate
    )
  done
fi
if curl --silent --output /dev/null \
  --connect-timeout 1 --max-time 2 "${base_url}/api/method/ping"; then
  echo "Runtime port ${port} is already serving before the controlled start." >&2
  exit 2
fi

runtime_log="$(mktemp)"
server_pid=""
route_disable_config_changed=false
document_route_disable_config_changed=false
document_release_route_disable_config_changed=false
document_baseline_route_disable_config_changed=false
engineering_bom_route_disable_config_changed=false
publish_request_route_disable_config_changed=false
controlled_print_route_disable_config_changed=false
tooling_route_disable_config_changed=false
tooling_set_route_disable_config_changed=false
tooling_revision_route_disable_config_changed=false
tooling_manufacturing_route_disable_config_changed=false
tooling_engineering_controls_route_disable_config_changed=false
tooling_acceptance_assets_route_disable_config_changed=false
tooling_import_route_disable_config_changed=false

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
      -u NPI_DOCUMENT_RUNTIME_RUN_ID \
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

set_document_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p5_01_routes_disabled "${value}"
  )
  verify_document_route_switch_state "${expected}"
}

set_document_release_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p5_02_routes_disabled "${value}"
  )
  verify_document_release_route_switch_state "${expected}"
}

set_document_baseline_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p5_03_routes_disabled "${value}"
  )
  verify_document_baseline_route_switch_state "${expected}"
}

set_engineering_bom_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p5_04_routes_disabled "${value}"
  )
  verify_engineering_bom_route_switch_state "${expected}"
}

set_publish_request_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p5_05_routes_disabled "${value}"
  )
  verify_publish_request_route_switch_state "${expected}"
}

set_controlled_print_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p5_06_routes_disabled "${value}"
  )
  verify_controlled_print_route_switch_state "${expected}"
}

set_tooling_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_01_routes_disabled "${value}"
  )
  verify_tooling_route_switch_state "${expected}"
}

set_tooling_set_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_02_routes_disabled "${value}"
  )
  verify_tooling_set_route_switch_state "${expected}"
}

set_tooling_revision_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_03_routes_disabled "${value}"
  )
  verify_tooling_revision_route_switch_state "${expected}"
}

set_tooling_manufacturing_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_04_routes_disabled "${value}"
  )
  verify_tooling_manufacturing_route_switch_state "${expected}"
}

set_tooling_engineering_controls_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_05_routes_disabled "${value}"
  )
  verify_tooling_engineering_controls_route_switch_state "${expected}"
}

set_tooling_acceptance_assets_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_06_routes_disabled "${value}"
  )
  verify_tooling_acceptance_assets_route_switch_state "${expected}"
}

set_tooling_import_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_07_routes_disabled "${value}"
  )
  verify_tooling_import_route_switch_state "${expected}"
}

restore_p405_route_switch() {
  if ! set_p405_route_switch None absent; then
    return 1
  fi
  route_disable_config_changed=false
}

restore_document_route_switch() {
  if ! set_document_route_switch None absent; then
    return 1
  fi
  document_route_disable_config_changed=false
}

restore_document_release_route_switch() {
  if ! set_document_release_route_switch None absent; then
    return 1
  fi
  document_release_route_disable_config_changed=false
}

restore_document_baseline_route_switch() {
  if ! set_document_baseline_route_switch None absent; then
    return 1
  fi
  document_baseline_route_disable_config_changed=false
}

restore_engineering_bom_route_switch() {
  if ! set_engineering_bom_route_switch None absent; then
    return 1
  fi
  engineering_bom_route_disable_config_changed=false
}

restore_publish_request_route_switch() {
  if ! set_publish_request_route_switch None absent; then
    return 1
  fi
  publish_request_route_disable_config_changed=false
}

restore_controlled_print_route_switch() {
  if ! set_controlled_print_route_switch None absent; then
    return 1
  fi
  controlled_print_route_disable_config_changed=false
}

restore_tooling_route_switch() {
  if ! set_tooling_route_switch None absent; then
    return 1
  fi
  tooling_route_disable_config_changed=false
}

restore_tooling_set_route_switch() {
  if ! set_tooling_set_route_switch None absent; then
    return 1
  fi
  tooling_set_route_disable_config_changed=false
}

restore_tooling_revision_route_switch() {
  if ! set_tooling_revision_route_switch None absent; then
    return 1
  fi
  tooling_revision_route_disable_config_changed=false
}

restore_tooling_manufacturing_route_switch() {
  if ! set_tooling_manufacturing_route_switch None absent; then
    return 1
  fi
  tooling_manufacturing_route_disable_config_changed=false
}

restore_tooling_engineering_controls_route_switch() {
  if ! set_tooling_engineering_controls_route_switch None absent; then
    return 1
  fi
  tooling_engineering_controls_route_disable_config_changed=false
}

restore_tooling_acceptance_assets_route_switch() {
  if ! set_tooling_acceptance_assets_route_switch None absent; then
    return 1
  fi
  tooling_acceptance_assets_route_disable_config_changed=false
}

restore_tooling_import_route_switch() {
  if ! set_tooling_import_route_switch None absent; then
    return 1
  fi
  tooling_import_route_disable_config_changed=false
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
  if [[ "${document_route_disable_config_changed}" == true ]]; then
    if ! restore_document_route_switch; then
      echo "Failed to restore the P5-01 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${document_release_route_disable_config_changed}" == true ]]; then
    if ! restore_document_release_route_switch; then
      echo "Failed to restore the P5-02 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${document_baseline_route_disable_config_changed}" == true ]]; then
    if ! restore_document_baseline_route_switch; then
      echo "Failed to restore the P5-03 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${engineering_bom_route_disable_config_changed}" == true ]]; then
    if ! restore_engineering_bom_route_switch; then
      echo "Failed to restore the P5-04 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${publish_request_route_disable_config_changed}" == true ]]; then
    if ! restore_publish_request_route_switch; then
      echo "Failed to restore the P5-05 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${controlled_print_route_disable_config_changed}" == true ]]; then
    if ! restore_controlled_print_route_switch; then
      echo "Failed to restore the P5-06 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_route_switch; then
      echo "Failed to restore the P6-01 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_set_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_set_route_switch; then
      echo "Failed to restore the P6-02 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_revision_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_revision_route_switch; then
      echo "Failed to restore the P6-03 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_manufacturing_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_manufacturing_route_switch; then
      echo "Failed to restore the P6-04 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_engineering_controls_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_engineering_controls_route_switch; then
      echo "Failed to restore the P6-05 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_acceptance_assets_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_acceptance_assets_route_switch; then
      echo "Failed to restore the P6-06 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${tooling_import_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_import_route_switch; then
      echo "Failed to restore the P6-07 route-disable switch to absent." >&2
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

run_grid_controller_runtime_verifier() {
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
    cd "${bench_path}/sites"
    exec "${bench_path}/env/bin/python" \
      "${repo_root}/scripts/verify_grid_personalization_runtime.py"
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

document_runtime_run_id="$(
  "${bench_path}/env/bin/python" -c \
    'from uuid import uuid4; print(uuid4().hex)'
)"
if [[ ! "${document_runtime_run_id}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "Document runtime namespace generation failed." >&2
  exit 2
fi

run_document_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_document_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_document_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Document runtime verification mode." >&2
    exit 2
  )
}

run_document_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_document_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_document_release_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_document_runtime.py" \
      --base-url "${base_url}" \
      --release-route-disable-probe "${expected_mode}"
  )
}

run_document_baseline_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_document_runtime.py" \
      --base-url "${base_url}" \
      --baseline-route-disable-probe "${expected_mode}"
  )
}

run_engineering_bom_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_ebom_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_ebom_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown EBOM runtime verification mode." >&2
    exit 2
  )
}

run_engineering_bom_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_ebom_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_publish_request_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_publish_request_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_publish_request_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown publish-request runtime verification mode." >&2
    exit 2
  )
}

run_publish_request_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_publish_request_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_controlled_print_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_controlled_print_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_controlled_print_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown controlled-print runtime verification mode." >&2
    exit 2
  )
}

run_controlled_print_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_controlled_print_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_tooling_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling runtime verification mode." >&2
    exit 2
  )
}

run_tooling_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_tooling_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_tooling_revision_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_revision_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_revision_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling Revision runtime verification mode." >&2
    exit 2
  )
}

run_tooling_revision_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_tooling_revision_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_tooling_manufacturing_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_manufacturing_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_manufacturing_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling manufacturing runtime verification mode." >&2
    exit 2
  )
}

run_tooling_manufacturing_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_tooling_manufacturing_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_tooling_engineering_controls_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_engineering_controls_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_engineering_controls_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling engineering-controls runtime verification mode." >&2
    exit 2
  )
}

run_tooling_engineering_controls_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_tooling_engineering_controls_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_tooling_acceptance_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_acceptance_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_acceptance_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling acceptance runtime verification mode." >&2
    exit 2
  )
}

run_tooling_acceptance_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_tooling_acceptance_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_tooling_import_runtime_verifier() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_import_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_import_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling import runtime verification mode." >&2
    exit 2
  )
}

run_tooling_import_route_probe() {
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
      NPI_DOCUMENT_RUNTIME_RUN_ID \
      NPI_PROJECT_CONTROLS_RUNTIME_RUN_ID \
      NPI_PROJECT_WORK_RUNTIME_RUN_ID \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_tooling_import_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

verify_tooling_import_runtime_log_redaction() {
  local marker
  for marker in \
    "Synthetic Housing" \
    "Synthetic Shared Cover" \
    "Synthetic corrected part" \
    "SYN-COLOR-CN" \
    "合成外壳"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P6-07 raw workbook value leaked into the runtime log." >&2
      return 1
    fi
  done
}

if [[ "${verification_mode}" == "all" ]]; then
  if ! run_runtime_verifier "${repo_root}/scripts/verify_frappe_runtime.py"; then
    echo "Local Frappe runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi

  if ! run_grid_controller_runtime_verifier; then
    echo "Local Frappe grid controller runtime verification failed." >&2
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

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--document-only" ||
      "${verification_mode}" == "--tooling-only" ]]; then
  if ! run_document_runtime_verifier fresh; then
    echo "Local Frappe Document runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  document_route_disable_config_changed=true
  stop_runtime_server
  set_document_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_document_route_probe disabled; then
    echo "Local Frappe Document route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_document_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_document_route_probe recovered; then
    echo "Local Frappe Document route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  document_release_route_disable_config_changed=true
  stop_runtime_server
  set_document_release_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_document_release_route_probe disabled; then
    echo "Local Frappe Document release route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_document_release_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_document_release_route_probe recovered; then
    echo "Local Frappe Document release route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  document_baseline_route_disable_config_changed=true
  stop_runtime_server
  set_document_baseline_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_document_baseline_route_probe disabled; then
    echo "Local Frappe Document baseline route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_document_baseline_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_document_baseline_route_probe recovered; then
    echo "Local Frappe Document baseline route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_engineering_bom_runtime_verifier fresh; then
    echo "Local Frappe EBOM runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  engineering_bom_route_disable_config_changed=true
  stop_runtime_server
  set_engineering_bom_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_engineering_bom_route_probe disabled; then
    echo "Local Frappe EBOM route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_engineering_bom_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_engineering_bom_route_probe recovered; then
    echo "Local Frappe EBOM route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_engineering_bom_runtime_verifier replay-only; then
    echo "Local Frappe EBOM cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_publish_request_runtime_verifier fresh; then
    echo "Local Frappe publish-request runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  publish_request_route_disable_config_changed=true
  stop_runtime_server
  set_publish_request_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_publish_request_route_probe disabled; then
    echo "Local Frappe publish-request route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_publish_request_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_publish_request_route_probe recovered; then
    echo "Local Frappe publish-request route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_publish_request_runtime_verifier replay-only; then
    echo "Local Frappe publish-request cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_document_runtime_verifier replay-only; then
    echo "Local Frappe Document cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_controlled_print_runtime_verifier fresh; then
    echo "Local Frappe controlled-print runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  controlled_print_route_disable_config_changed=true
  stop_runtime_server
  set_controlled_print_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_controlled_print_route_probe disabled; then
    echo "Local Frappe controlled-print route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_controlled_print_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_controlled_print_route_probe recovered; then
    echo "Local Frappe controlled-print route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_controlled_print_runtime_verifier replay-only; then
    echo "Local Frappe controlled-print cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
fi

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--tooling-only" ]]; then
  tooling_route_disable_config_changed=true
  tooling_set_route_disable_config_changed=true
  tooling_revision_route_disable_config_changed=true
  tooling_manufacturing_route_disable_config_changed=true
  tooling_engineering_controls_route_disable_config_changed=true
  tooling_acceptance_assets_route_disable_config_changed=true
  tooling_import_route_disable_config_changed=true
  stop_runtime_server
  set_tooling_route_switch false false
  set_tooling_set_route_switch false false
  set_tooling_revision_route_switch true true
  set_tooling_manufacturing_route_switch true true
  set_tooling_engineering_controls_route_switch true true
  set_tooling_acceptance_assets_route_switch true true
  set_tooling_import_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_runtime_verifier fresh; then
    echo "Local Frappe Tooling runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_revision_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_revision_runtime_verifier fresh; then
    echo "Local Frappe Tooling Revision runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_route_switch true true
  set_tooling_set_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_route_probe disabled; then
    echo "Local Frappe Tooling route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_route_switch false false
  set_tooling_set_route_switch false false
  set_tooling_revision_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_route_probe recovered; then
    echo "Local Frappe Tooling route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_runtime_verifier replay-only; then
    echo "Local Frappe Tooling cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_revision_route_probe disabled; then
    echo "Local Frappe Tooling Revision route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_revision_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_revision_route_probe recovered; then
    echo "Local Frappe Tooling Revision route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_revision_runtime_verifier replay-only; then
    echo "Local Frappe Tooling Revision cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_manufacturing_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_manufacturing_runtime_verifier fresh; then
    echo "Local Frappe Tooling manufacturing runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_manufacturing_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_manufacturing_route_probe disabled; then
    echo "Local Frappe Tooling manufacturing route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_manufacturing_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_manufacturing_route_probe recovered; then
    echo "Local Frappe Tooling manufacturing route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_manufacturing_runtime_verifier replay-only; then
    echo "Local Frappe Tooling manufacturing cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_engineering_controls_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_engineering_controls_runtime_verifier fresh; then
    echo "Local Frappe Tooling engineering-controls runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_engineering_controls_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_engineering_controls_route_probe disabled; then
    echo "Local Frappe Tooling engineering-controls route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_engineering_controls_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_engineering_controls_route_probe recovered; then
    echo "Local Frappe Tooling engineering-controls route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_engineering_controls_runtime_verifier replay-only; then
    echo "Local Frappe Tooling engineering-controls cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_acceptance_assets_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_acceptance_runtime_verifier fresh; then
    echo "Local Frappe Tooling acceptance runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_acceptance_assets_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_acceptance_route_probe disabled; then
    echo "Local Frappe Tooling acceptance route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_acceptance_assets_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_acceptance_route_probe recovered; then
    echo "Local Frappe Tooling acceptance route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_acceptance_runtime_verifier replay-only; then
    echo "Local Frappe Tooling acceptance cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_import_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_import_runtime_verifier fresh; then
    echo "Local Frappe Tooling import runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_import_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_import_route_probe disabled; then
    echo "Local Frappe Tooling import route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_import_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_import_route_probe recovered; then
    echo "Local Frappe Tooling import route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_import_runtime_verifier replay-only; then
    echo "Local Frappe Tooling import cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! verify_tooling_import_runtime_log_redaction; then
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
fi
