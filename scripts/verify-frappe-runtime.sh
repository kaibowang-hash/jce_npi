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
      "${verification_mode}" != "--tooling-only" &&
      "${verification_mode}" != "--trial-only" &&
      "${verification_mode}" != "--projection-only" ]]; then
  echo "Usage: scripts/verify-frappe-runtime.sh [--gate-evidence-only|--gate-review-only|--project-controls-only|--document-only|--tooling-only|--trial-only|--projection-only]" >&2
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
  NPI_RUNTIME_FIXTURE_PASSWORD \
  NPI_P8_02_RUNTIME_ENABLED \
  NPI_P8_02_RUNTIME_ACTOR \
  NPI_P8_02_RUNTIME_OWNER \
  NPI_P8_02_RUNTIME_TEMPLATE_ID \
  NPI_P8_02_RUNTIME_SECRET_OLD \
  NPI_P8_02_RUNTIME_SECRET_NEW \
  NPI_P8_03_RUNTIME_ENABLED \
  NPI_P8_03_RUNTIME_MARKER \
  NPI_P8_03_RUNTIME_PROJECT_ID \
  NPI_P8_03_RUNTIME_REQUESTER \
  NPI_P8_03_RUNTIME_WORKER \
  NPI_P8_03_RUNTIME_LEGACY_REQUEST_ID \
  NPI_P8_03_RUNTIME_LEGACY_NODE_ID \
  NPI_P8_03_RUNTIME_LEGACY_STREAM_HASH \
  NPI_P8_03_RUNTIME_LEGACY_OUTBOX_ID \
  NPI_P8_04_RUNTIME_ENABLED \
  NPI_P8_04_RUNTIME_MARKER \
  NPI_P8_04_RUNTIME_PROJECT_ID \
  NPI_P8_04_RUNTIME_REQUESTER \
  NPI_P8_04_RUNTIME_WORKER \
  NPI_P8_07_RUNTIME_ENABLED \
  NPI_P8_07_RUNTIME_MARKER \
  NPI_P8_07_RUNTIME_PROJECT_ID \
  NPI_P8_07_RUNTIME_REQUESTER \
  NPI_P8_07_RUNTIME_WORKER \
  NPI_P9_01C_RUNTIME_ENABLED \
  NPI_P9_01C_RUNTIME_PROJECT_ID \
  NPI_P9_01C_RUNTIME_REQUESTER \
  NPI_P9_01C_RUNTIME_WORKER \
  NPI_P9_01C_RUNTIME_SECRET \
  NPI_P9_02D_RUNTIME_ENABLED \
  NPI_P9_02D_RUNTIME_PROJECT_ID \
  NPI_P9_02D_RUNTIME_ACTOR \
  NPI_P9_02D_RUNTIME_LIMITED_ACTOR

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

tooling_export_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p6_08_routes_disabled"
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

trial_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_01_routes_disabled"
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

trial_execution_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_02_routes_disabled"
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

trial_quality_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_03_routes_disabled"
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

trial_review_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_04_routes_disabled"
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

readiness_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_05_routes_disabled"
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

production_transition_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_06_routes_disabled"
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

released_summary_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p7_07_routes_disabled"
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

projection_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p8_01_routes_disabled"
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

integration_operations_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p8_07_routes_disabled"
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

engineering_change_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p9_01_routes_disabled"
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

reporting_collaboration_route_switch_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
switch_name = "npi_p9_02_routes_disabled"
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

runtime_disposable_marker_state() {
  "${bench_path}/env/bin/python" -c \
    'import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
value = config.get("npi_runtime_disposable_marker")
print(value if isinstance(value, str) else "invalid")' \
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

verify_tooling_export_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(tooling_export_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P6-08 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_trial_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(trial_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-01 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_trial_execution_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(trial_execution_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-02 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_trial_quality_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(trial_quality_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-03 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_trial_review_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(trial_review_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-04 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_readiness_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(readiness_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-05 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_production_transition_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(production_transition_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-06 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_released_summary_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(released_summary_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P7-07 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

verify_projection_route_switch_state() {
  local expected="$1"
  local actual
  actual="$(projection_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P8-01 route-disable switch state is ${actual}, expected ${expected}." >&2
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
tooling_export_route_disable_original_state="$(tooling_export_route_switch_state)"
if [[ "${tooling_export_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P6-08 route-disable switch." >&2
  exit 2
fi
trial_route_disable_original_state="$(trial_route_switch_state)"
if [[ "${trial_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-01 route-disable switch." >&2
  exit 2
fi
trial_execution_route_disable_original_state="$(trial_execution_route_switch_state)"
if [[ "${trial_execution_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-02 route-disable switch." >&2
  exit 2
fi
trial_quality_route_disable_original_state="$(trial_quality_route_switch_state)"
if [[ "${trial_quality_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-03 route-disable switch." >&2
  exit 2
fi
trial_review_route_disable_original_state="$(trial_review_route_switch_state)"
if [[ "${trial_review_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-04 route-disable switch." >&2
  exit 2
fi
readiness_route_disable_original_state="$(readiness_route_switch_state)"
if [[ "${readiness_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-05 route-disable switch." >&2
  exit 2
fi
production_transition_route_disable_original_state="$(
  production_transition_route_switch_state
)"
if [[ "${production_transition_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-06 route-disable switch." >&2
  exit 2
fi
released_summary_route_disable_original_state="$(
  released_summary_route_switch_state
)"
if [[ "${released_summary_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P7-07 route-disable switch." >&2
  exit 2
fi
projection_route_disable_original_state="$(projection_route_switch_state)"
if [[ "${projection_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P8-01 route-disable switch." >&2
  exit 2
fi
integration_operations_route_disable_original_state="$(
  integration_operations_route_switch_state
)"
if [[ "${integration_operations_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P8-07 route-disable switch." >&2
  exit 2
fi
engineering_change_route_disable_original_state="$(
  engineering_change_route_switch_state
)"
if [[ "${engineering_change_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P9-01 route-disable switch." >&2
  exit 2
fi
reporting_collaboration_route_disable_original_state="$(
  reporting_collaboration_route_switch_state
)"
if [[ "${reporting_collaboration_route_disable_original_state}" != "absent" ]]; then
  echo "Runtime Site must start without the P9-02 route-disable switch." >&2
  exit 2
fi
if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--document-only" ||
      "${verification_mode}" == "--tooling-only" ||
      "${verification_mode}" == "--trial-only" ||
      "${verification_mode}" == "--projection-only" ]]; then
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
tooling_export_route_disable_config_changed=false
trial_route_disable_config_changed=false
trial_execution_route_disable_config_changed=false
trial_quality_route_disable_config_changed=false
trial_review_route_disable_config_changed=false
readiness_route_disable_config_changed=false
production_transition_route_disable_config_changed=false
released_summary_route_disable_config_changed=false
projection_route_disable_config_changed=false
inbound_project_runtime_environment_active=false
item_publish_runtime_environment_active=false
mbom_publish_runtime_environment_active=false
tool_asset_runtime_environment_active=false
integration_operations_route_disable_config_changed=false
integration_operations_runtime_environment_active=false
engineering_change_route_disable_config_changed=false
engineering_change_runtime_environment_active=false
reporting_collaboration_route_disable_config_changed=false
reporting_collaboration_runtime_environment_active=false
runtime_disposable_marker_changed=false

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
      -u NPI_P9_02D_RUNTIME_ENABLED \
      -u NPI_P9_02D_RUNTIME_PROJECT_ID \
      -u NPI_P9_02D_RUNTIME_ACTOR \
      -u NPI_P9_02D_RUNTIME_LIMITED_ACTOR \
      bench --site "${site_name}" serve --port "${port}" --noreload
  ) >>"${runtime_log}" 2>&1 &
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

wait_until_runtime_server_ready() {
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
  [[ "${ready}" == true ]]
}

wait_for_runtime_server() {
  if wait_until_runtime_server_ready; then
    return 0
  fi
  echo "Local Frappe runtime did not become ready." >&2
  tail -100 "${runtime_log}" >&2
  return 1
}

wait_for_readiness_runtime_server() {
  if wait_until_runtime_server_ready; then
    return 0
  fi
  echo "Local Frappe runtime did not become ready." >&2
  report_readiness_runtime_failure
  return 1
}

wait_for_production_transition_runtime_server() {
  if wait_until_runtime_server_ready; then
    return 0
  fi
  echo "Local Frappe runtime did not become ready." >&2
  report_production_transition_runtime_failure
  return 1
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

set_tooling_export_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p6_08_routes_disabled "${value}"
  )
  verify_tooling_export_route_switch_state "${expected}"
}

set_trial_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_01_routes_disabled "${value}"
  )
  verify_trial_route_switch_state "${expected}"
}

set_trial_execution_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_02_routes_disabled "${value}"
  )
  verify_trial_execution_route_switch_state "${expected}"
}

set_trial_quality_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_03_routes_disabled "${value}"
  )
  verify_trial_quality_route_switch_state "${expected}"
}

set_trial_review_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_04_routes_disabled "${value}"
  )
  verify_trial_review_route_switch_state "${expected}"
}

set_readiness_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_05_routes_disabled "${value}"
  )
  verify_readiness_route_switch_state "${expected}"
}

set_production_transition_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_06_routes_disabled "${value}"
  )
  verify_production_transition_route_switch_state "${expected}"
}

set_released_summary_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p7_07_routes_disabled "${value}"
  )
  verify_released_summary_route_switch_state "${expected}"
}

set_projection_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p8_01_routes_disabled "${value}"
  )
  verify_projection_route_switch_state "${expected}"
}

set_integration_operations_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p8_07_routes_disabled "${value}"
  )
  local actual
  actual="$(integration_operations_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P8-07 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

set_engineering_change_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p9_01_routes_disabled "${value}"
  )
  local actual
  actual="$(engineering_change_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P9-01 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

set_reporting_collaboration_route_switch() {
  local value="$1"
  local expected="$2"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_p9_02_routes_disabled "${value}"
  )
  local actual
  actual="$(reporting_collaboration_route_switch_state)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "P9-02 route-disable switch state is ${actual}, expected ${expected}." >&2
    return 1
  fi
}

set_runtime_disposable_marker() {
  local value="$1"
  (
    cd "${bench_path}"
    bench --site "${site_name}" set-config \
      npi_runtime_disposable_marker "${value}"
  )
  if [[ "$(runtime_disposable_marker_state)" != "${value}" ]]; then
    echo "Runtime disposable marker state drifted." >&2
    return 1
  fi
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

restore_tooling_export_route_switch() {
  if ! set_tooling_export_route_switch None absent; then
    return 1
  fi
  tooling_export_route_disable_config_changed=false
}

restore_trial_route_switch() {
  if ! set_trial_route_switch None absent; then
    return 1
  fi
  trial_route_disable_config_changed=false
}

restore_trial_execution_route_switch() {
  if ! set_trial_execution_route_switch None absent; then
    return 1
  fi
  trial_execution_route_disable_config_changed=false
}

restore_trial_quality_route_switch() {
  if ! set_trial_quality_route_switch None absent; then
    return 1
  fi
  trial_quality_route_disable_config_changed=false
}

restore_trial_review_route_switch() {
  if ! set_trial_review_route_switch None absent; then
    return 1
  fi
  trial_review_route_disable_config_changed=false
}

restore_readiness_route_switch() {
  if ! set_readiness_route_switch None absent; then
    return 1
  fi
  readiness_route_disable_config_changed=false
}

restore_production_transition_route_switch() {
  if ! set_production_transition_route_switch None absent; then
    return 1
  fi
  production_transition_route_disable_config_changed=false
}

restore_released_summary_route_switch() {
  if ! set_released_summary_route_switch None absent; then
    return 1
  fi
  released_summary_route_disable_config_changed=false
}

restore_projection_route_switch() {
  if ! set_projection_route_switch None absent; then
    return 1
  fi
  projection_route_disable_config_changed=false
}

restore_integration_operations_route_switch() {
  if ! set_integration_operations_route_switch None absent; then
    return 1
  fi
  integration_operations_route_disable_config_changed=false
}

restore_engineering_change_route_switch() {
  if ! set_engineering_change_route_switch None absent; then
    return 1
  fi
  engineering_change_route_disable_config_changed=false
}

restore_reporting_collaboration_route_switch() {
  if ! set_reporting_collaboration_route_switch None absent; then
    return 1
  fi
  reporting_collaboration_route_disable_config_changed=false
}

restore_runtime_disposable_marker() {
  if ! set_runtime_disposable_marker "${runtime_marker}"; then
    return 1
  fi
  runtime_disposable_marker_changed=false
}

cleanup() {
  local exit_status=$?
  trap - EXIT
  if ! stop_runtime_server; then
    exit_status=1
  fi
  if [[ "${inbound_project_runtime_environment_active}" == true ]]; then
    clear_inbound_project_runtime_environment
    inbound_project_runtime_environment_active=false
  fi
  if [[ "${item_publish_runtime_environment_active}" == true ]]; then
    clear_item_publish_runtime_environment
    item_publish_runtime_environment_active=false
  fi
  if [[ "${mbom_publish_runtime_environment_active}" == true ]]; then
    clear_mbom_publish_runtime_environment
    mbom_publish_runtime_environment_active=false
  fi
  if [[ "${tool_asset_runtime_environment_active}" == true ]]; then
    clear_tool_asset_runtime_environment
    tool_asset_runtime_environment_active=false
  fi
  if [[ "${integration_operations_runtime_environment_active}" == true ]]; then
    clear_integration_operations_runtime_environment
    integration_operations_runtime_environment_active=false
  fi
  if [[ "${engineering_change_runtime_environment_active}" == true ]]; then
    clear_engineering_change_runtime_environment
    engineering_change_runtime_environment_active=false
  fi
  if [[ "${reporting_collaboration_runtime_environment_active}" == true ]]; then
    clear_reporting_collaboration_runtime_environment
    reporting_collaboration_runtime_environment_active=false
  fi
  if [[ "${runtime_disposable_marker_changed}" == true ]]; then
    if ! restore_runtime_disposable_marker; then
      echo "Failed to restore the disposable runtime marker." >&2
      exit_status=1
    fi
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
  if [[ "${tooling_export_route_disable_config_changed}" == true ]]; then
    if ! restore_tooling_export_route_switch; then
      echo "Failed to restore the P6-08 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${trial_route_disable_config_changed}" == true ]]; then
    if ! restore_trial_route_switch; then
      echo "Failed to restore the P7-01 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${trial_execution_route_disable_config_changed}" == true ]]; then
    if ! restore_trial_execution_route_switch; then
      echo "Failed to restore the P7-02 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${trial_quality_route_disable_config_changed}" == true ]]; then
    if ! restore_trial_quality_route_switch; then
      echo "Failed to restore the P7-03 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${trial_review_route_disable_config_changed}" == true ]]; then
    if ! restore_trial_review_route_switch; then
      echo "Failed to restore the P7-04 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${readiness_route_disable_config_changed}" == true ]]; then
    if ! restore_readiness_route_switch; then
      echo "Failed to restore the P7-05 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${production_transition_route_disable_config_changed}" == true ]]; then
    if ! restore_production_transition_route_switch; then
      echo "Failed to restore the P7-06 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${released_summary_route_disable_config_changed}" == true ]]; then
    if ! restore_released_summary_route_switch; then
      echo "Failed to restore the P7-07 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${projection_route_disable_config_changed}" == true ]]; then
    if ! restore_projection_route_switch; then
      echo "Failed to restore the P8-01 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${integration_operations_route_disable_config_changed}" == true ]]; then
    if ! restore_integration_operations_route_switch; then
      echo "Failed to restore the P8-07 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${engineering_change_route_disable_config_changed}" == true ]]; then
    if ! restore_engineering_change_route_switch; then
      echo "Failed to restore the P9-01 route-disable switch to absent." >&2
      exit_status=1
    fi
  fi
  if [[ "${reporting_collaboration_route_disable_config_changed}" == true ]]; then
    if ! restore_reporting_collaboration_route_switch; then
      echo "Failed to restore the P9-02 route-disable switch to absent." >&2
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

inbound_project_runtime_actor="npi-inbound-${document_runtime_run_id:0:12}@example.invalid"
inbound_project_runtime_owner="npi-owner-${document_runtime_run_id:0:12}@example.invalid"
item_publish_runtime_actor="npi-document-${document_runtime_run_id:0:20}-baseline@example.invalid"
engineering_change_runtime_worker="npi-readiness-${document_runtime_run_id:0:20}-manager@example.invalid"
reporting_collaboration_runtime_actor="${engineering_change_runtime_worker}"
reporting_collaboration_runtime_limited_actor="${item_publish_runtime_actor}"
tool_asset_runtime_requester="npi-tooling-manufacturing-${document_runtime_run_id:0:12}-manager@example.invalid"
item_publish_runtime_project_id=""
item_publish_runtime_legacy_request_id=""
item_publish_runtime_legacy_node_id=""
item_publish_runtime_legacy_stream_hash=""
item_publish_runtime_legacy_outbox_id=""
inbound_project_runtime_template_id="$(
  "${bench_path}/env/bin/python" -c \
    'import sys; from uuid import UUID, uuid5; print(uuid5(UUID("be05ea93-4d1a-4ac0-a148-c3e7a8a80202"), sys.argv[1]))' \
    "${document_runtime_run_id}"
)"
inbound_project_runtime_secret_old="$(
  "${bench_path}/env/bin/python" -c \
    'import hashlib, sys; print(hashlib.sha256(("p8-old:" + sys.argv[1]).encode()).hexdigest())' \
    "${document_runtime_run_id}"
)"
inbound_project_runtime_secret_new="$(
  "${bench_path}/env/bin/python" -c \
    'import hashlib, sys; print(hashlib.sha256(("p8-new:" + sys.argv[1]).encode()).hexdigest())' \
    "${document_runtime_run_id}"
)"
engineering_change_runtime_secret="$(
  "${bench_path}/env/bin/python" -c \
    'import hashlib, sys; print(hashlib.sha256(("p9-change:" + sys.argv[1]).encode()).hexdigest())' \
    "${document_runtime_run_id}"
)"
if [[ ! "${inbound_project_runtime_template_id}" =~ ^[a-f0-9-]{36}$ ||
      ! "${inbound_project_runtime_secret_old}" =~ ^[a-f0-9]{64}$ ||
      ! "${inbound_project_runtime_secret_new}" =~ ^[a-f0-9]{64}$ ||
      ! "${engineering_change_runtime_secret}" =~ ^[a-f0-9]{64}$ ||
      ! "${item_publish_runtime_actor}" =~ ^npi-document-[a-f0-9]{20}-baseline@example[.]invalid$ ||
      ! "${engineering_change_runtime_worker}" =~ ^npi-readiness-[a-f0-9]{20}-manager@example[.]invalid$ ||
      "${reporting_collaboration_runtime_actor}" != "${engineering_change_runtime_worker}" ||
      "${reporting_collaboration_runtime_limited_actor}" != "${item_publish_runtime_actor}" ]]; then
  echo "Inbound Project runtime fixture generation failed." >&2
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

run_tooling_export_runtime_verifier() {
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
      exec python "${repo_root}/scripts/verify_tooling_export_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_tooling_export_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Tooling export runtime verification mode." >&2
    exit 2
  )
}

run_tooling_export_route_probe() {
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
    exec python "${repo_root}/scripts/verify_tooling_export_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_trial_runtime_verifier() {
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
      exec python "${repo_root}/scripts/verify_trial_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_trial_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Trial runtime verification mode." >&2
    exit 2
  )
}

run_trial_route_probe() {
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
    exec python "${repo_root}/scripts/verify_trial_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_readiness_runtime_verifier() {
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
      exec python "${repo_root}/scripts/verify_readiness_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_readiness_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown NPI readiness runtime verification mode." >&2
    exit 2
  )
}

run_readiness_route_probe() {
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
    exec python "${repo_root}/scripts/verify_readiness_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_production_transition_runtime_verifier() {
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
      exec python "${repo_root}/scripts/verify_production_transition_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_production_transition_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Production transition runtime verification mode." >&2
    exit 2
  )
}

run_production_transition_route_probe() {
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
    exec python "${repo_root}/scripts/verify_production_transition_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_released_summary_runtime_verifier() {
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
      exec python "${repo_root}/scripts/verify_released_trial_summary_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_released_trial_summary_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown Released Trial Summary runtime verification mode." >&2
    exit 2
  )
}

run_released_summary_route_probe() {
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
    exec python "${repo_root}/scripts/verify_released_trial_summary_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

run_projection_runtime_verifier() {
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
      export NPI_PROJECTION_FRESH_PREDECESSOR_DIAGNOSTIC_PATH="${RUNNER_TEMP:-/tmp}/p8-01-projection-fresh-predecessor-diagnostic.json"
      export NPI_P801_PROJECTION_FRESH_PREDECESSOR_DIAGNOSTIC_SCOPE="p8-01-projection-fresh-predecessor-v1"
      exec python "${repo_root}/scripts/verify_projection_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_projection_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown ERP projection runtime verification mode." >&2
    exit 2
  )
}

read_projection_fresh_predecessor_diagnostic() {
  local diagnostic_path="${RUNNER_TEMP:-/tmp}/p8-01-projection-fresh-predecessor-diagnostic.json"
  local expected_trace
  expected_trace="$(
    NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}" \
      python "${repo_root}/scripts/verify_projection_runtime.py" \
      --diagnostic-trace
  )" || return 1
  NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}" \
    python "${repo_root}/scripts/verify_projection_runtime.py" \
    --read-diagnostic "${diagnostic_path}" \
    --expected-trace "${expected_trace}"
}

run_projection_route_probe() {
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
    exec python "${repo_root}/scripts/verify_projection_runtime.py" \
      --base-url "${base_url}" \
      --route-disable-probe "${expected_mode}"
  )
}

export_inbound_project_runtime_environment() {
  export NPI_P8_02_RUNTIME_ENABLED=1
  export NPI_P8_02_RUNTIME_ACTOR="${inbound_project_runtime_actor}"
  export NPI_P8_02_RUNTIME_OWNER="${inbound_project_runtime_owner}"
  export NPI_P8_02_RUNTIME_TEMPLATE_ID="${inbound_project_runtime_template_id}"
  export NPI_P8_02_RUNTIME_SECRET_OLD="${inbound_project_runtime_secret_old}"
  export NPI_P8_02_RUNTIME_SECRET_NEW="${inbound_project_runtime_secret_new}"
}

clear_inbound_project_runtime_environment() {
  unset \
    NPI_P8_02_RUNTIME_ENABLED \
    NPI_P8_02_RUNTIME_ACTOR \
    NPI_P8_02_RUNTIME_OWNER \
    NPI_P8_02_RUNTIME_TEMPLATE_ID \
    NPI_P8_02_RUNTIME_SECRET_OLD \
    NPI_P8_02_RUNTIME_SECRET_NEW
}

run_inbound_project_runtime_verifier() {
  local mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    export_inbound_project_runtime_environment
    if [[ "${mode}" == "disabled" ]]; then
      exec python "${repo_root}/scripts/verify_inbound_project_runtime.py" \
        --base-url "${base_url}" \
        --disabled-probe
    fi
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_inbound_project_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_inbound_project_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    echo "Unknown inbound Project runtime verification mode." >&2
    exit 2
  )
}

capture_item_publish_runtime_project_id() {
  local captured
  captured="$({
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD \
      NPI_P8_03_RUNTIME_ENABLED \
      NPI_P8_03_RUNTIME_MARKER \
      NPI_P8_03_RUNTIME_PROJECT_ID \
      NPI_P8_03_RUNTIME_REQUESTER \
      NPI_P8_03_RUNTIME_WORKER
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    cd "${bench_path}/sites"
    exec "${bench_path}/env/bin/python" \
      "${repo_root}/scripts/verify_item_publish_runtime.py" \
      --bench-fixture capture_project \
      --fixture-kwargs "{\"fixture_run_id\":\"${document_runtime_run_id}\"}"
  })"
  "${bench_path}/env/bin/python" -c \
    'import json, sys
lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
value = json.loads(lines[-1]) if lines else {}
project_id = value.get("projectGlobalId")
if not isinstance(project_id, str):
    raise SystemExit(1)
print(project_id)' <<<"${captured}"
}

seed_item_publish_runtime_legacy() {
  local captured
  captured="$({
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    export NPI_P8_03_RUNTIME_ENABLED=1
    export NPI_P8_03_RUNTIME_MARKER=npi-one-item-publish-disposable-v1
    export NPI_P8_03_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
    export NPI_P8_03_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
    export NPI_P8_03_RUNTIME_WORKER="${inbound_project_runtime_actor}"
    cd "${bench_path}/sites"
    exec "${bench_path}/env/bin/python" \
      "${repo_root}/scripts/verify_item_publish_runtime.py" \
      --bench-fixture seed_legacy \
      --fixture-kwargs "{\"fixture_run_id\":\"${document_runtime_run_id}\",\"project_id\":\"${item_publish_runtime_project_id}\"}"
  })"
  "${bench_path}/env/bin/python" -c \
    'import json, sys
lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
value = json.loads(lines[-1]) if lines else {}
for key in ("legacyOutboxId", "legacyRequestId", "selectedPublishNodeGlobalId", "sourceStreamKeyHash", "preMigrationDuplicateAttemptCount"):
    if not isinstance(value.get(key), str):
        if key == "preMigrationDuplicateAttemptCount" and value.get(key) == 0:
            continue
        raise SystemExit(1)
print(json.dumps({key: value[key] for key in ("legacyOutboxId", "legacyRequestId", "selectedPublishNodeGlobalId", "sourceStreamKeyHash", "preMigrationDuplicateAttemptCount")}, separators=(",", ":"), sort_keys=True))' <<<"${captured}"
}

prepare_item_publish_runtime_legacy_probe() {
  local captured
  captured="$({
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD \
      NPI_RUNTIME_ADMINISTRATOR_PASSWORD \
      NPI_RUNTIME_FIXTURE_PASSWORD
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    export NPI_P8_03_RUNTIME_ENABLED=1
    export NPI_P8_03_RUNTIME_MARKER=npi-one-item-publish-disposable-v1
    export NPI_P8_03_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
    export NPI_P8_03_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
    export NPI_P8_03_RUNTIME_WORKER="${inbound_project_runtime_actor}"
    cd "${bench_path}/sites"
    exec "${bench_path}/env/bin/python" \
      "${repo_root}/scripts/verify_item_publish_runtime.py" \
      --bench-fixture prepare_legacy_probe \
      --fixture-kwargs "{\"fixture_run_id\":\"${document_runtime_run_id}\",\"project_id\":\"${item_publish_runtime_project_id}\",\"legacy_request_id\":\"${item_publish_runtime_legacy_request_id}\",\"source_stream_key_hash\":\"${item_publish_runtime_legacy_stream_hash}\"}"
  })"
  "${bench_path}/env/bin/python" -c \
    'import json, sys
lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
value = json.loads(lines[-1]) if lines else {}
if set(value) != {"guardRowsRemoved", "legacyRowRetained"}:
    raise SystemExit(1)
if value["guardRowsRemoved"] not in {0, 1} or value["legacyRowRetained"] is not True:
    raise SystemExit(1)' <<<"${captured}"
}

export_item_publish_runtime_environment() {
  export NPI_P8_03_RUNTIME_ENABLED=1
  export NPI_P8_03_RUNTIME_MARKER=npi-one-item-publish-disposable-v1
  export NPI_P8_03_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
  export NPI_P8_03_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
  export NPI_P8_03_RUNTIME_WORKER="${inbound_project_runtime_actor}"
  if [[ -n "${item_publish_runtime_legacy_request_id:-}" ]]; then
    export NPI_P8_03_RUNTIME_LEGACY_REQUEST_ID="${item_publish_runtime_legacy_request_id}"
    export NPI_P8_03_RUNTIME_LEGACY_NODE_ID="${item_publish_runtime_legacy_node_id}"
    export NPI_P8_03_RUNTIME_LEGACY_STREAM_HASH="${item_publish_runtime_legacy_stream_hash}"
    export NPI_P8_03_RUNTIME_LEGACY_OUTBOX_ID="${item_publish_runtime_legacy_outbox_id}"
  fi
}

clear_item_publish_runtime_environment() {
  unset \
    NPI_P8_03_RUNTIME_ENABLED \
    NPI_P8_03_RUNTIME_MARKER \
    NPI_P8_03_RUNTIME_PROJECT_ID \
    NPI_P8_03_RUNTIME_REQUESTER \
    NPI_P8_03_RUNTIME_WORKER \
    NPI_P8_03_RUNTIME_LEGACY_REQUEST_ID \
    NPI_P8_03_RUNTIME_LEGACY_NODE_ID \
    NPI_P8_03_RUNTIME_LEGACY_STREAM_HASH \
    NPI_P8_03_RUNTIME_LEGACY_OUTBOX_ID
}

run_item_publish_runtime_verifier() {
  local mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "disabled" ]]; then
      clear_item_publish_runtime_environment
      exec python "${repo_root}/scripts/verify_item_publish_runtime.py" \
        --base-url "${base_url}" \
        --disabled-probe
    fi
    export_item_publish_runtime_environment
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_item_publish_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_item_publish_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    if [[ "${mode}" == "legacy-only" ]]; then
      exec python "${repo_root}/scripts/verify_item_publish_runtime.py" \
        --base-url "${base_url}" \
        --legacy-only \
        --legacy-request-id "${NPI_P8_03_RUNTIME_LEGACY_REQUEST_ID}" \
        --legacy-node-id "${NPI_P8_03_RUNTIME_LEGACY_NODE_ID}"
    fi
    echo "Unknown Item publish runtime verification mode." >&2
    exit 2
  )
}

export_mbom_publish_runtime_environment() {
  export NPI_P8_04_RUNTIME_ENABLED=1
  export NPI_P8_04_RUNTIME_MARKER=npi-one-mbom-publish-disposable-v1
  export NPI_P8_04_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
  export NPI_P8_04_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
  export NPI_P8_04_RUNTIME_WORKER="${inbound_project_runtime_actor}"
}

clear_mbom_publish_runtime_environment() {
  unset \
    NPI_P8_04_RUNTIME_ENABLED \
    NPI_P8_04_RUNTIME_MARKER \
    NPI_P8_04_RUNTIME_PROJECT_ID \
    NPI_P8_04_RUNTIME_REQUESTER \
    NPI_P8_04_RUNTIME_WORKER
}

run_mbom_publish_runtime_verifier() {
  local mode="$1"
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "disabled" ]]; then
      clear_mbom_publish_runtime_environment
      exec python "${repo_root}/scripts/verify_mbom_publish_runtime.py" \
        --base-url "${base_url}" \
        --disabled-probe
    fi
    export_mbom_publish_runtime_environment
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_mbom_publish_runtime.py" \
        --base-url "${base_url}"
    fi
    echo "Unknown MBOM publish runtime verification mode." >&2
    exit 2
  )
}

export_tool_asset_runtime_environment() {
  export NPI_TOOL_ASSET_RUNTIME_MARKER=npi-one-tool-asset-disposable-v1
  export NPI_TOOL_ASSET_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
  export NPI_TOOL_ASSET_REQUESTER_USER="${tool_asset_runtime_requester}"
  export NPI_TOOL_ASSET_WORKER_USER="${inbound_project_runtime_actor}"
}

clear_tool_asset_runtime_environment() {
  unset \
    NPI_TOOL_ASSET_RUNTIME_MARKER \
    NPI_TOOL_ASSET_RUNTIME_PROJECT_ID \
    NPI_TOOL_ASSET_REQUESTER_USER \
    NPI_TOOL_ASSET_WORKER_USER
}

run_tool_asset_runtime_verifier() {
  local mode="$1"
  (
    unset FRAPPE_DB_HOST FRAPPE_DB_PORT FRAPPE_DB_SOCKET FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "disabled" ]]; then
      clear_tool_asset_runtime_environment
      exec python "${repo_root}/scripts/verify_tool_asset_execution_runtime.py" \
        --base-url "${base_url}" --disabled-probe
    fi
    export_tool_asset_runtime_environment
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_tool_asset_execution_runtime.py" \
        --base-url "${base_url}"
    fi
    echo "Unknown Tool Asset runtime verification mode." >&2
    exit 2
  )
}

export_integration_operations_runtime_environment() {
  export NPI_P8_07_RUNTIME_ENABLED=1
  export NPI_P8_07_RUNTIME_MARKER=npi-one-integration-operations-disposable-v1
  export NPI_P8_07_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
  export NPI_P8_07_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
  export NPI_P8_07_RUNTIME_WORKER="${inbound_project_runtime_actor}"
}

clear_integration_operations_runtime_environment() {
  unset \
    NPI_P8_07_RUNTIME_ENABLED \
    NPI_P8_07_RUNTIME_MARKER \
    NPI_P8_07_RUNTIME_PROJECT_ID \
    NPI_P8_07_RUNTIME_REQUESTER \
    NPI_P8_07_RUNTIME_WORKER
}

run_integration_operations_runtime_verifier() {
  local mode="$1"
  (
    unset FRAPPE_DB_HOST FRAPPE_DB_PORT FRAPPE_DB_SOCKET FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    if [[ "${mode}" == "disabled" ]]; then
      clear_integration_operations_runtime_environment
      exec python "${repo_root}/scripts/verify_integration_operations_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --disabled-probe
    fi
    export_integration_operations_runtime_environment
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_integration_operations_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_integration_operations_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --replay-only
    fi
    if [[ "${mode}" == "recovered" ]]; then
      exec python "${repo_root}/scripts/verify_integration_operations_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --recovered-probe
    fi
    if [[ "${mode}" == "post-migration-cleanup" ]]; then
      exec python "${repo_root}/scripts/verify_integration_operations_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --post-migration-cleanup
    fi
    echo "Unknown P8-07 integration operations runtime verification mode." >&2
    exit 2
  )
}

export_engineering_change_runtime_environment() {
  export NPI_P9_01C_RUNTIME_ENABLED=1
  export NPI_P9_01C_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
  export NPI_P9_01C_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
  export NPI_P9_01C_RUNTIME_WORKER="${engineering_change_runtime_worker}"
  export NPI_P9_01C_RUNTIME_SECRET="${engineering_change_runtime_secret}"
  export NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH="${RUNNER_TEMP:-/tmp}/p9-01-engineering-change-runtime-diagnostic.json"
}

clear_engineering_change_runtime_environment() {
  unset \
    NPI_P9_01C_RUNTIME_ENABLED \
    NPI_P9_01C_RUNTIME_PROJECT_ID \
    NPI_P9_01C_RUNTIME_REQUESTER \
    NPI_P9_01C_RUNTIME_WORKER \
    NPI_P9_01C_RUNTIME_SECRET \
    NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH
}

run_engineering_change_runtime_verifier() {
  local mode="$1"
  (
    unset FRAPPE_DB_HOST FRAPPE_DB_PORT FRAPPE_DB_SOCKET FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    export NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH="${RUNNER_TEMP:-/tmp}/p9-01-engineering-change-runtime-diagnostic.json"
    if [[ "${mode}" == "disabled" ]]; then
      clear_engineering_change_runtime_environment
      export NPI_P9_01C_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
      export NPI_P9_01C_RUNTIME_REQUESTER="${item_publish_runtime_actor}"
      export NPI_P9_01C_RUNTIME_WORKER="${engineering_change_runtime_worker}"
      export NPI_P9_01C_RUNTIME_SECRET="${engineering_change_runtime_secret}"
      exec python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --disabled-probe
    fi
    export_engineering_change_runtime_environment
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}"
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --replay-only
    fi
    if [[ "${mode}" == "recovered" ]]; then
      exec python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --recovered-probe
    fi
    if [[ "${mode}" == "cleanup" ]]; then
      exec python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
        --base-url "${base_url}" \
        --project-id "${item_publish_runtime_project_id}" \
        --cleanup
    fi
    echo "Unknown P9-01 engineering change runtime verification mode." >&2
    exit 2
  )
}

export_reporting_collaboration_runtime_environment() {
  export NPI_P9_02D_RUNTIME_ENABLED=1
  export NPI_P9_02D_RUNTIME_PROJECT_ID="${item_publish_runtime_project_id}"
  export NPI_P9_02D_RUNTIME_ACTOR="${reporting_collaboration_runtime_actor}"
  export NPI_P9_02D_RUNTIME_LIMITED_ACTOR="${reporting_collaboration_runtime_limited_actor}"
}

clear_reporting_collaboration_runtime_environment() {
  unset \
    NPI_P9_02D_RUNTIME_ENABLED \
    NPI_P9_02D_RUNTIME_PROJECT_ID \
    NPI_P9_02D_RUNTIME_ACTOR \
    NPI_P9_02D_RUNTIME_LIMITED_ACTOR
}

run_reporting_collaboration_runtime_verifier() {
  local mode="$1"
  (
    unset FRAPPE_DB_HOST FRAPPE_DB_PORT FRAPPE_DB_SOCKET FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    export_reporting_collaboration_runtime_environment
    if [[ "${mode}" == "fresh" ]]; then
      exec python "${repo_root}/scripts/verify_reporting_collaboration_runtime.py" \
        --base-url "${base_url}"
    fi
    if [[ "${mode}" == "disabled" ]]; then
      exec python "${repo_root}/scripts/verify_reporting_collaboration_runtime.py" \
        --base-url "${base_url}" \
        --disabled-probe
    fi
    if [[ "${mode}" == "replay-only" ]]; then
      exec python "${repo_root}/scripts/verify_reporting_collaboration_runtime.py" \
        --base-url "${base_url}" \
        --replay-only
    fi
    if [[ "${mode}" == "recovered" ]]; then
      exec python "${repo_root}/scripts/verify_reporting_collaboration_runtime.py" \
        --base-url "${base_url}" \
        --recovered-probe
    fi
    if [[ "${mode}" == "cleanup" ]]; then
      exec python "${repo_root}/scripts/verify_reporting_collaboration_runtime.py" \
        --base-url "${base_url}" \
        --cleanup
    fi
    echo "Unknown P9-02 reporting and collaboration runtime verification mode." >&2
    exit 2
  )
}

read_engineering_change_runtime_diagnostic() {
  local diagnostic_path="${RUNNER_TEMP:-/tmp}/p9-01-engineering-change-runtime-diagnostic.json"
  local expected_trace
  expected_trace="$(
    NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}" \
      python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
      --diagnostic-trace
  )" || return 1
  NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}" \
    python "${repo_root}/scripts/verify_engineering_change_runtime.py" \
    --read-diagnostic "${diagnostic_path}" \
    --expected-trace "${expected_trace}"
}

run_quality_link_runtime_verifier() {
  (
    unset \
      FRAPPE_DB_HOST \
      FRAPPE_DB_PORT \
      FRAPPE_DB_SOCKET \
      FRAPPE_DB_TYPE \
      NPI_ADMINISTRATOR_PASSWORD \
      NPI_DATABASE_ROOT_PASSWORD
    export NPI_RUNTIME_ADMINISTRATOR_PASSWORD="${runtime_administrator_password}"
    export NPI_RUNTIME_FIXTURE_PASSWORD="${runtime_fixture_password}"
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    export NPI_QUALITY_LINK_RUNTIME_DIAGNOSTIC_PATH="${RUNNER_TEMP:-/tmp}/p8-06-quality-link-runtime-diagnostic.json"
    exec python "${repo_root}/scripts/verify_quality_link_runtime.py" \
      --base-url "${base_url}"
  )
}

run_authorization_projection_runtime_verifier() {
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
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_authorization_projection_runtime.py"
  )
}

run_historical_migration_runtime_verifier() {
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
    export NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"
    exec python "${repo_root}/scripts/verify_historical_migration_runtime.py"
  )
}

read_quality_link_runtime_diagnostic() {
  local diagnostic_path="${RUNNER_TEMP:-/tmp}/p8-06-quality-link-runtime-diagnostic.json"
  local expected_trace
  expected_trace="$(
    NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}" \
      python "${repo_root}/scripts/verify_quality_link_runtime.py" \
      --diagnostic-trace
  )" || return 1
  NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}" \
    python "${repo_root}/scripts/verify_quality_link_runtime.py" \
    --read-diagnostic "${diagnostic_path}" \
    --expected-trace "${expected_trace}"
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

verify_tooling_export_runtime_log_redaction() {
  local marker
  for marker in \
    "=P6-08 controlled formula sentinel" \
    "项目编码" \
    "專案編碼" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P6-08 raw package value or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

verify_trial_runtime_log_redaction() {
  # Preserved predecessor evidence: P7-03 raw Trial quality value leaked into the runtime log.
  local marker
  for marker in \
    "Synthetic controlled Trial planning objective" \
    "Synthetic successor Trial planning objective" \
    "SYN-MATERIAL-" \
    "Verify synthetic dimensional evidence" \
    "Controlled PA66 material observation" \
    "P702-MATERIAL-" \
    "P702-SAMPLE-" \
    "P703-SAMPLE-" \
    "Controlled dimensional laboratory" \
    "Controlled synthetic cavity width" \
    "Controlled exact-cavity defect observation for runtime proof." \
    "Independent controlled verification passed." \
    "Begin the exact controlled Trial review analysis." \
    "Seal the exact chronological T0 to T1 comparison." \
    "Proposal only; no Gate mutation is authorized." \
    "Reject the corrected proposal without mutating external authorities." \
    "p7-02-controlled-parameters.csv" \
    "melt_temperature,287,degC"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P7-04 raw Trial review value leaked into the runtime log." >&2
      return 1
    fi
  done
}

verify_readiness_runtime_log_redaction() {
  local marker
  for marker in \
    "Synthetic controlled readiness template" \
    "Synthetic readiness confirmation sentinel" \
    "P705-CAPACITY-SOURCE-SENTINEL" \
    "P705-TRIAL-REFERENCE-SENTINEL" \
    "P705-ERP-MATERIAL-SENTINEL" \
    "P705-GATE-DRIFT-SENTINEL" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P7-05 raw readiness value or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_readiness_runtime_failure() {
  echo "P7-05 runtime log output withheld because it may contain controlled readiness values or private paths." >&2
}

verify_production_transition_runtime_log_redaction() {
  local marker
  for marker in \
    "P706-POLICY-SENTINEL" \
    "P706-HANDOVER-SENTINEL" \
    "P706-OBSERVATION-SENTINEL" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P7-06 raw Production transition value or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_production_transition_runtime_failure() {
  echo "P7-06 runtime log output withheld because it may contain controlled Production transition values or private paths." >&2
}

verify_released_summary_runtime_log_redaction() {
  local marker
  for marker in \
    "P707-RETAIN-APPROVED-SUMMARY" \
    "P707-RETAIN-REJECTED-SUMMARY" \
    "P707-DISPOSABLE-CONTROLLED-OUTPUT" \
    "P707 decide exact technical conclusion" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P7-07 raw summary value or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_released_summary_runtime_failure() {
  echo "P7-07 runtime log output withheld because it may contain controlled Released Trial Summary values or private paths." >&2
}

verify_projection_runtime_log_redaction() {
  local marker
  for marker in \
    "Controlled Runtime Customer" \
    "Controlled Runtime Supplier" \
    "Controlled Runtime Tool Room" \
    "CUSTOMER-RUNTIME-001" \
    "SUPPLIER-RUNTIME-001" \
    "ASSET-RUNTIME-001" \
    "secrets/p8-runtime-sandbox-read" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P8-01 raw ERP projection value, secret reference or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_projection_runtime_failure() {
  echo "P8-01 runtime log output withheld because it may contain controlled ERP projection values or private paths." >&2
}

verify_inbound_project_runtime_log_redaction() {
  local marker
  for marker in \
    "${inbound_project_runtime_secret_old}" \
    "${inbound_project_runtime_secret_new}" \
    "Synthetic inbound Project" \
    "Synthetic conflict" \
    "QTN-P802-" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P8-02 raw inbound value, secret or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_inbound_project_runtime_failure() {
  echo "P8-02 runtime log output withheld because it may contain signed inbound values or private paths." >&2
}

verify_item_publish_runtime_log_redaction() {
  local marker
  for marker in \
    "I confirm this request uses the exact released Item source" \
    "Synthetic front housing" \
    "Synthetic shared front housing" \
    "formalItemCode" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P8-03 raw Item source, target identity or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

verify_integration_operations_runtime_log_redaction() {
  local marker
  for marker in \
    "P807-RTRY-" \
    "P807_DISPOSABLE_TARGET_UNAVAILABLE" \
    "network-free-synthetic-v1" \
    "targetRequest" \
    "targetResponse" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P8-07 runtime fixture, target or private value leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_integration_operations_runtime_failure() {
  echo "P8-07 runtime log output withheld because it may contain integration history or target identities." >&2
}

verify_engineering_change_runtime_log_redaction() {
  local marker
  for marker in \
    "${engineering_change_runtime_secret}" \
    "P9 runtime engineering change" \
    "ECR-RUNTIME-" \
    "erpnext-disposable-runtime" \
    "network-free-engineering-change-v1" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P9-01 runtime fixture, signed value, target identity or private path leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_engineering_change_runtime_failure() {
  local diagnostic
  if diagnostic="$(read_engineering_change_runtime_diagnostic)"; then
    echo "P9-01 Engineering Change runtime diagnostic [${diagnostic}]" >&2
  fi
  echo "P9-01 runtime log output withheld because it may contain signed change values or target identities." >&2
}

verify_reporting_collaboration_runtime_log_redaction() {
  local marker
  for marker in \
    "${MEETING_TITLE:-P9 reporting review}" \
    "Synthetic local email queue failure" \
    "/private/files/"; do
    if grep --fixed-strings --quiet -- "${marker}" "${runtime_log}"; then
      echo "P9-02 runtime fixture or private value leaked into the runtime log." >&2
      return 1
    fi
  done
}

report_reporting_collaboration_runtime_failure() {
  echo "P9-02 runtime log output withheld because it may contain collaboration values or identities." >&2
}

report_item_publish_runtime_failure() {
  echo "P8-03 runtime log output withheld because it may contain released Item values or target identities." >&2
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
      "${verification_mode}" == "--tooling-only" ||
      "${verification_mode}" == "--trial-only" ||
      "${verification_mode}" == "--projection-only" ]]; then
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
      "${verification_mode}" == "--tooling-only" ||
      "${verification_mode}" == "--trial-only" ||
      "${verification_mode}" == "--projection-only" ]]; then
  tooling_route_disable_config_changed=true
  tooling_set_route_disable_config_changed=true
  tooling_revision_route_disable_config_changed=true
  tooling_manufacturing_route_disable_config_changed=true
  tooling_engineering_controls_route_disable_config_changed=true
  tooling_acceptance_assets_route_disable_config_changed=true
  tooling_import_route_disable_config_changed=true
  tooling_export_route_disable_config_changed=true
  stop_runtime_server
  set_tooling_route_switch false false
  set_tooling_set_route_switch false false
  set_tooling_revision_route_switch true true
  set_tooling_manufacturing_route_switch true true
  set_tooling_engineering_controls_route_switch true true
  set_tooling_acceptance_assets_route_switch true true
  set_tooling_import_route_switch true true
  set_tooling_export_route_switch true true
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
  stop_runtime_server
  set_tooling_export_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_export_runtime_verifier fresh; then
    echo "Local Frappe Tooling export runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_export_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_export_route_probe disabled; then
    echo "Local Frappe Tooling export route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_tooling_export_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_tooling_export_route_probe recovered; then
    echo "Local Frappe Tooling export route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_tooling_export_runtime_verifier replay-only; then
    echo "Local Frappe Tooling export cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! verify_tooling_export_runtime_log_redaction; then
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
fi

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--trial-only" ||
      "${verification_mode}" == "--projection-only" ]]; then
  trial_route_disable_config_changed=true
  trial_execution_route_disable_config_changed=true
  trial_quality_route_disable_config_changed=true
  trial_review_route_disable_config_changed=true
  stop_runtime_server
  set_trial_route_switch false false
  set_trial_execution_route_switch false false
  set_trial_quality_route_switch false false
  set_trial_review_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_runtime_verifier fresh; then
    echo "Local Frappe Trial runtime verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe planning-disabled; then
    echo "Local Frappe Trial planning route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe planning-recovered; then
    echo "Local Frappe Trial planning route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_execution_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe execution-disabled; then
    echo "Local Frappe Trial execution route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_execution_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe execution-recovered; then
    echo "Local Frappe Trial execution route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_quality_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe quality-disabled; then
    echo "Local Frappe Trial quality route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_quality_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe quality-recovered; then
    echo "Local Frappe Trial quality route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_review_route_switch true true
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe review-disabled; then
    echo "Local Frappe Trial review route-disable probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  stop_runtime_server
  set_trial_review_route_switch false false
  start_runtime_server
  wait_for_runtime_server
  if ! run_trial_route_probe review-recovered; then
    echo "Local Frappe Trial review route recovery probe failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! run_trial_runtime_verifier replay-only; then
    echo "Local Frappe Trial cross-process replay verification failed." >&2
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  if ! verify_trial_runtime_log_redaction; then
    tail -100 "${runtime_log}" >&2
    exit 1
  fi
  readiness_route_disable_config_changed=true
  stop_runtime_server
  set_readiness_route_switch false false
  start_runtime_server
  wait_for_readiness_runtime_server
  if ! run_readiness_runtime_verifier fresh; then
    echo "Local Frappe NPI readiness runtime verification failed." >&2
    report_readiness_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_readiness_route_switch true true
  start_runtime_server
  wait_for_readiness_runtime_server
  if ! run_readiness_route_probe disabled; then
    echo "Local Frappe NPI readiness route-disable probe failed." >&2
    report_readiness_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_readiness_route_switch false false
  start_runtime_server
  wait_for_readiness_runtime_server
  if ! run_readiness_route_probe recovered; then
    echo "Local Frappe NPI readiness route recovery probe failed." >&2
    report_readiness_runtime_failure
    exit 1
  fi
  if ! run_readiness_runtime_verifier replay-only; then
    echo "Local Frappe NPI readiness cross-process replay verification failed." >&2
    report_readiness_runtime_failure
    exit 1
  fi
  if ! verify_readiness_runtime_log_redaction; then
    report_readiness_runtime_failure
    exit 1
  fi
  production_transition_route_disable_config_changed=true
  stop_runtime_server
  set_production_transition_route_switch false false
  start_runtime_server
  wait_for_production_transition_runtime_server
  if ! run_production_transition_runtime_verifier fresh; then
    echo "Local Frappe Production transition runtime verification failed." >&2
    report_production_transition_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_production_transition_route_switch true true
  start_runtime_server
  wait_for_production_transition_runtime_server
  if ! run_production_transition_route_probe disabled; then
    echo "Local Frappe Production transition route-disable probe failed." >&2
    report_production_transition_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_production_transition_route_switch false false
  start_runtime_server
  wait_for_production_transition_runtime_server
  if ! run_production_transition_route_probe recovered; then
    echo "Local Frappe Production transition route recovery probe failed." >&2
    report_production_transition_runtime_failure
    exit 1
  fi
  if ! run_production_transition_runtime_verifier replay-only; then
    echo "Local Frappe Production transition cross-process replay verification failed." >&2
    report_production_transition_runtime_failure
    exit 1
  fi
  if ! verify_production_transition_runtime_log_redaction; then
    report_production_transition_runtime_failure
    exit 1
  fi
  released_summary_route_disable_config_changed=true
  stop_runtime_server
  set_released_summary_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_released_summary_runtime_failure
    exit 1
  fi
  if ! run_released_summary_runtime_verifier fresh; then
    echo "Local Frappe Released Trial Summary runtime verification failed." >&2
    report_released_summary_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_released_summary_route_switch true true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_released_summary_runtime_failure
    exit 1
  fi
  if ! run_released_summary_route_probe disabled; then
    echo "Local Frappe Released Trial Summary route-disable probe failed." >&2
    report_released_summary_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_released_summary_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_released_summary_runtime_failure
    exit 1
  fi
  if ! run_released_summary_route_probe recovered; then
    echo "Local Frappe Released Trial Summary route recovery probe failed." >&2
    report_released_summary_runtime_failure
    exit 1
  fi
  if ! run_released_summary_runtime_verifier replay-only; then
    echo "Local Frappe Released Trial Summary cross-process replay verification failed." >&2
    report_released_summary_runtime_failure
    exit 1
  fi
  if ! verify_released_summary_runtime_log_redaction; then
    report_released_summary_runtime_failure
    exit 1
  fi
fi

if [[ "${verification_mode}" == "all" ||
      "${verification_mode}" == "--projection-only" ]]; then
  projection_route_disable_config_changed=true
  stop_runtime_server
  set_projection_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_projection_runtime_failure
    exit 1
  fi
  if ! run_projection_runtime_verifier fresh; then
    if diagnostic="$(read_projection_fresh_predecessor_diagnostic)"; then
      echo "P8-01 projection fresh predecessor diagnostic [${diagnostic}]" >&2
    fi
    echo "Local Frappe ERP projection runtime verification failed." >&2
    report_projection_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_projection_route_switch true true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_projection_runtime_failure
    exit 1
  fi
  if ! run_projection_route_probe disabled; then
    echo "Local Frappe ERP projection route-disable probe failed." >&2
    report_projection_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_projection_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_projection_runtime_failure
    exit 1
  fi
  if ! run_projection_route_probe recovered; then
    echo "Local Frappe ERP projection route recovery probe failed." >&2
    report_projection_runtime_failure
    exit 1
  fi
  if ! run_projection_runtime_verifier replay-only; then
    echo "Local Frappe ERP projection cross-process replay verification failed." >&2
    report_projection_runtime_failure
    exit 1
  fi
  if ! verify_projection_runtime_log_redaction; then
    report_projection_runtime_failure
    exit 1
  fi

  if ! run_quality_link_runtime_verifier >/dev/null 2>/dev/null; then
    if diagnostic="$(read_quality_link_runtime_diagnostic)"; then
      echo "P8-06 formal quality link runtime diagnostic [${diagnostic}]" >&2
    fi
    echo "Local Frappe formal quality link runtime verification failed." >&2
    report_projection_runtime_failure
    exit 1
  fi

  if ! run_authorization_projection_runtime_verifier >/dev/null 2>/dev/null; then
    echo "Local Frappe authorization projection runtime verification failed." >&2
    exit 1
  fi

  if ! run_historical_migration_runtime_verifier >/dev/null 2>/dev/null; then
    echo "Local Frappe historical migration runtime verification failed." >&2
    exit 1
  fi

  # P8-02 remains disabled with no explicit disposable process environment.
  if ! run_inbound_project_runtime_verifier disabled; then
    echo "Local Frappe inbound Project default-disabled probe failed." >&2
    report_inbound_project_runtime_failure
    exit 1
  fi
  stop_runtime_server
  export_inbound_project_runtime_environment
  inbound_project_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_inbound_project_runtime_failure
    exit 1
  fi
  if ! run_inbound_project_runtime_verifier fresh; then
    echo "Local Frappe inbound Project runtime verification failed." >&2
    report_inbound_project_runtime_failure
    exit 1
  fi
  stop_runtime_server
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_inbound_project_runtime_failure
    exit 1
  fi
  if ! run_inbound_project_runtime_verifier replay-only; then
    echo "Local Frappe inbound Project cross-process replay verification failed." >&2
    report_inbound_project_runtime_failure
    exit 1
  fi
  if ! verify_inbound_project_runtime_log_redaction; then
    report_inbound_project_runtime_failure
    exit 1
  fi

  # P8-03 stays closed until the exact disposable Project/actor binding is
  # exported into a newly started process.
  if ! run_item_publish_runtime_verifier disabled; then
    echo "Local Frappe Item publish default-disabled probe failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  stop_runtime_server
  item_publish_runtime_project_id="$(capture_item_publish_runtime_project_id)"
  if [[ ! "${item_publish_runtime_project_id}" =~ ^[a-f0-9-]{36}$ ]]; then
    echo "P8-03 retained Project identity capture failed." >&2
    exit 1
  fi
  export_item_publish_runtime_environment
  item_publish_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! run_item_publish_runtime_verifier fresh; then
    echo "Local Frappe Item publish worker runtime verification failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  stop_runtime_server
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! run_item_publish_runtime_verifier replay-only; then
    echo "Local Frappe Item publish cross-process replay verification failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  # P8-04 reuses only the retained released EBOM and disposable actors. Its
  # own profile remains independently default-disabled and its sole built-in
  # adapter is a network-free Synthetic batch proof with no formal MBOM IDs.
  if ! run_mbom_publish_runtime_verifier disabled; then
    echo "Local Frappe MBOM publish default-disabled probe failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  stop_runtime_server
  export_mbom_publish_runtime_environment
  mbom_publish_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! run_mbom_publish_runtime_verifier fresh; then
    echo "Local Frappe MBOM publish worker runtime verification failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  # P8-05 reuses only retained P6 Tooling evidence and disposable actors. Its
  # operation-specific registry remains independently default-disabled and the
  # sole fixture is network-free Synthetic proof with no formal Asset identity.
  if ! run_tool_asset_runtime_verifier disabled; then
    echo "Local Frappe Tool Asset default-disabled probe failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  stop_runtime_server
  export_tool_asset_runtime_environment
  tool_asset_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! run_tool_asset_runtime_verifier fresh; then
    echo "Local Frappe Tool Asset worker runtime verification failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  # P8-07 is a derived Project-scoped view over the exact retained P8-02
  # through P8-05 rows.  Its route remains default-disabled until the fixed
  # disposable Project/actors are bound into a newly started process.
  if ! run_integration_operations_runtime_verifier disabled; then
    echo "Local Frappe integration operations default-disabled probe failed." >&2
    report_integration_operations_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_integration_operations_route_switch false false
  integration_operations_route_disable_config_changed=true
  export_integration_operations_runtime_environment
  integration_operations_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_integration_operations_runtime_failure
    exit 1
  fi
  if ! run_integration_operations_runtime_verifier fresh; then
    echo "Local Frappe integration operations runtime verification failed." >&2
    report_integration_operations_runtime_failure
    exit 1
  fi
  stop_runtime_server
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_integration_operations_runtime_failure
    exit 1
  fi
  if ! run_integration_operations_runtime_verifier replay-only; then
    echo "Local Frappe integration operations cross-process replay verification failed." >&2
    report_integration_operations_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_integration_operations_route_switch true true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_integration_operations_runtime_failure
    exit 1
  fi
  if ! run_integration_operations_runtime_verifier disabled; then
    echo "Local Frappe integration operations route-disable verification failed." >&2
    report_integration_operations_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_integration_operations_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_integration_operations_runtime_failure
    exit 1
  fi
  if ! run_integration_operations_runtime_verifier recovered; then
    echo "Local Frappe integration operations route recovery verification failed." >&2
    report_integration_operations_runtime_failure
    exit 1
  fi
  # P9-01 reuses the retained disposable Project and the two already-bound
  # non-Administrator service actors. Its target is the reviewed network-free
  # Synthetic adapter only; production profiles and transport remain absent.
  if ! run_engineering_change_runtime_verifier disabled; then
    echo "Local Frappe Engineering Change default-disabled probe failed." >&2
    report_engineering_change_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_engineering_change_route_switch false false
  engineering_change_route_disable_config_changed=true
  export_engineering_change_runtime_environment
  engineering_change_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_engineering_change_runtime_failure
    exit 1
  fi
  if ! run_engineering_change_runtime_verifier fresh; then
    echo "Local Frappe Engineering Change runtime verification failed." >&2
    report_engineering_change_runtime_failure
    exit 1
  fi
  stop_runtime_server
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_engineering_change_runtime_failure
    exit 1
  fi
  if ! run_engineering_change_runtime_verifier replay-only; then
    echo "Local Frappe Engineering Change cross-process replay verification failed." >&2
    report_engineering_change_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_engineering_change_route_switch true true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_engineering_change_runtime_failure
    exit 1
  fi
  if ! run_engineering_change_runtime_verifier disabled; then
    echo "Local Frappe Engineering Change route-disable verification failed." >&2
    report_engineering_change_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_engineering_change_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_engineering_change_runtime_failure
    exit 1
  fi
  if ! run_engineering_change_runtime_verifier recovered; then
    echo "Local Frappe Engineering Change route recovery verification failed." >&2
    report_engineering_change_runtime_failure
    exit 1
  fi
  if ! run_engineering_change_runtime_verifier cleanup; then
    echo "Local Frappe Engineering Change cleanup verification failed." >&2
    report_engineering_change_runtime_failure
    exit 1
  fi
  if ! verify_engineering_change_runtime_log_redaction; then
    report_engineering_change_runtime_failure
    exit 1
  fi
  stop_runtime_server
  clear_engineering_change_runtime_environment
  engineering_change_runtime_environment_active=false
  restore_engineering_change_route_switch
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_engineering_change_runtime_failure
    exit 1
  fi
  # P9-02 reuses only the retained disposable Project and the two existing
  # non-Administrator actors. Its routes remain independently default-disabled
  # until those exact fixture identities are exported into a new process.
  if ! run_reporting_collaboration_runtime_verifier disabled; then
    echo "Local Frappe reporting and collaboration default-disabled probe failed." >&2
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_reporting_collaboration_route_switch false false
  reporting_collaboration_route_disable_config_changed=true
  export_reporting_collaboration_runtime_environment
  reporting_collaboration_runtime_environment_active=true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  if ! run_reporting_collaboration_runtime_verifier fresh; then
    echo "Local Frappe reporting and collaboration runtime verification failed." >&2
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  stop_runtime_server
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  if ! run_reporting_collaboration_runtime_verifier replay-only; then
    echo "Local Frappe reporting and collaboration cross-process replay verification failed." >&2
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_reporting_collaboration_route_switch true true
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  if ! run_reporting_collaboration_runtime_verifier disabled; then
    echo "Local Frappe reporting and collaboration route-disable verification failed." >&2
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  stop_runtime_server
  set_reporting_collaboration_route_switch false false
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  if ! run_reporting_collaboration_runtime_verifier recovered; then
    echo "Local Frappe reporting and collaboration route recovery verification failed." >&2
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  if ! run_reporting_collaboration_runtime_verifier cleanup; then
    echo "Local Frappe reporting and collaboration cleanup verification failed." >&2
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  if ! verify_reporting_collaboration_runtime_log_redaction; then
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  stop_runtime_server
  clear_reporting_collaboration_runtime_environment
  reporting_collaboration_runtime_environment_active=false
  restore_reporting_collaboration_route_switch
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_reporting_collaboration_runtime_failure
    exit 1
  fi
  # Insert one marker-gated 8dd-shaped row after the executable proof, run the
  # pinned migration twice, and prove the old row is readable but cannot be
  # promoted or claimed.  The fixture removes its exact rows after inspection.
  stop_runtime_server
  legacy_seed="$(seed_item_publish_runtime_legacy)"
  item_publish_runtime_legacy_request_id="$(${bench_path}/env/bin/python -c 'import json,sys; print(json.loads(sys.stdin.read())['"'"'legacyRequestId'"'"'])' <<<"${legacy_seed}")"
  item_publish_runtime_legacy_outbox_id="$(${bench_path}/env/bin/python -c 'import json,sys; print(json.loads(sys.stdin.read())['"'"'legacyOutboxId'"'"'])' <<<"${legacy_seed}")"
  item_publish_runtime_legacy_node_id="$(${bench_path}/env/bin/python -c 'import json,sys; print(json.loads(sys.stdin.read())['"'"'selectedPublishNodeGlobalId'"'"'])' <<<"${legacy_seed}")"
  item_publish_runtime_legacy_stream_hash="$(${bench_path}/env/bin/python -c 'import json,sys; print(json.loads(sys.stdin.read())['"'"'sourceStreamKeyHash'"'"'])' <<<"${legacy_seed}")"
  legacy_duplicate_attempt_count="$(${bench_path}/env/bin/python -c 'import json,sys; print(json.loads(sys.stdin.read())['"'"'preMigrationDuplicateAttemptCount'"'"'])' <<<"${legacy_seed}")"
  if [[ ! "${item_publish_runtime_legacy_request_id}" =~ ^[a-f0-9-]{36}$ ||
        ! "${item_publish_runtime_legacy_outbox_id}" =~ ^[a-f0-9-]{36}$ ||
        ! "${item_publish_runtime_legacy_node_id}" =~ ^[a-f0-9-]{36}$ ||
        ! "${item_publish_runtime_legacy_stream_hash}" =~ ^[a-f0-9]{64}$ ||
        "${legacy_duplicate_attempt_count}" != 0 ]]; then
    echo "P8-03 legacy fixture identity capture failed." >&2
    exit 1
  fi
  for _migration_attempt in 1 2; do
    (
      cd "${bench_path}"
      bench --site "${site_name}" migrate
    )
  done
  if ! prepare_item_publish_runtime_legacy_probe; then
    echo "P8-03 post-migration legacy stream probe isolation failed." >&2
    exit 1
  fi
  export NPI_P8_03_RUNTIME_LEGACY_REQUEST_ID="${item_publish_runtime_legacy_request_id}"
  export NPI_P8_03_RUNTIME_LEGACY_OUTBOX_ID="${item_publish_runtime_legacy_outbox_id}"
  export NPI_P8_03_RUNTIME_LEGACY_NODE_ID="${item_publish_runtime_legacy_node_id}"
  export NPI_P8_03_RUNTIME_LEGACY_STREAM_HASH="${item_publish_runtime_legacy_stream_hash}"
  start_runtime_server
  if ! wait_for_runtime_server; then
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! run_item_publish_runtime_verifier legacy-only; then
    echo "Local Frappe Item publish migrated-legacy runtime verification failed." >&2
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! run_integration_operations_runtime_verifier post-migration-cleanup; then
    echo "Local Frappe integration operations post-migration cleanup verification failed." >&2
    report_integration_operations_runtime_failure
    exit 1
  fi
  if ! verify_item_publish_runtime_log_redaction; then
    report_item_publish_runtime_failure
    exit 1
  fi
  if ! verify_integration_operations_runtime_log_redaction; then
    report_integration_operations_runtime_failure
    exit 1
  fi
fi
