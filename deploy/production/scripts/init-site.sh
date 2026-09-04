#!/usr/bin/env bash
set -euo pipefail

: "${SITE_NAME:?SITE_NAME is required}"
: "${DATABASE_NAME:?DATABASE_NAME is required}"
: "${NPI_TENANT_ID:?NPI_TENANT_ID is required}"

bench_root=/home/frappe/frappe-bench
site_path="${bench_root}/sites/${SITE_NAME}"
production_marker="${site_path}/.launchflow-production-site"
marker_value=launchflow-production-site-v1

cd "${bench_root}"
if [[ -e "${site_path}" && ! -d "${site_path}" ]]; then
  echo "The production Site path is not a directory." >&2
  exit 2
fi

if [[ -d "${site_path}" ]]; then
  if [[ -L "${site_path}" || ! -f "${production_marker}" ]]; then
    echo "Refusing to mutate an existing unowned Site." >&2
    exit 2
  fi
  if [[ "$(<"${production_marker}")" != "${marker_value}" ]]; then
    echo "The production Site ownership marker is invalid." >&2
    exit 2
  fi
else
  database_root_password="$(</run/secrets/mariadb_root_password)"
  administrator_password="$(</run/secrets/administrator_password)"
  printf '%s\n%s\n%s\n' \
    "${database_root_password}" \
    "${administrator_password}" \
    "${administrator_password}" |
    bench new-site "${SITE_NAME}" \
      --db-name "${DATABASE_NAME}" \
      --db-type mariadb \
      --db-host db \
      --db-port 3306 \
      --db-root-username root \
      --mariadb-user-host-login-scope '%' \
      --set-default
  unset database_root_password administrator_password
  printf '%s\n' "${marker_value}" > "${production_marker}"
fi

python - "${site_path}/site_config.json" "${DATABASE_NAME}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
expected_database = sys.argv[2]
config = json.loads(path.read_text(encoding="utf-8"))
if config.get("db_name") != expected_database:
    raise SystemExit("The existing Site database identity does not match production.")
if config.get("developer_mode") not in (None, 0, False):
    raise SystemExit("developer_mode must remain disabled in production.")
if "npi_runtime_disposable_marker" in config:
    raise SystemExit("A disposable runtime marker is forbidden in production.")
PY

site_has_app() {
  bench --site "${SITE_NAME}" list-apps --format json |
    python -c 'import json,sys; app=sys.argv[1]; data=json.load(sys.stdin); raise SystemExit(0 if any(app in value for value in data.values()) else 1)' "$1"
}

if ! site_has_app npi_core; then
  bench --site "${SITE_NAME}" install-app npi_core
fi
if ! site_has_app npi_integration; then
  bench --site "${SITE_NAME}" install-app npi_integration
fi

bench --site "${SITE_NAME}" set-config --parse developer_mode 0
bench --site "${SITE_NAME}" set-config host_name "https://${SITE_NAME}"
bench --site "${SITE_NAME}" set-config npi_tenant_id "${NPI_TENANT_ID}"
bench --site "${SITE_NAME}" set-config npi_deployment_environment production

enabled_route_switches=(
  npi_p4_05_routes_disabled
  npi_p5_01_routes_disabled npi_p5_02_routes_disabled
  npi_p5_03_routes_disabled npi_p5_04_routes_disabled
  npi_p5_05_routes_disabled npi_p5_06_routes_disabled
  npi_p6_01_routes_disabled npi_p6_02_routes_disabled
  npi_p6_03_routes_disabled npi_p6_04_routes_disabled
  npi_p6_05_routes_disabled npi_p6_06_routes_disabled
  npi_p6_07_routes_disabled npi_p6_08_routes_disabled
  npi_p7_01_routes_disabled npi_p7_02_routes_disabled
  npi_p7_03_routes_disabled npi_p7_04_routes_disabled
  npi_p7_05_routes_disabled npi_p7_06_routes_disabled
  npi_p7_07_routes_disabled
  npi_p8_01_routes_disabled npi_p8_07_routes_disabled
  npi_p9_01_routes_disabled npi_p9_02_routes_disabled
  npi_p9_05_routes_disabled npi_p9_06_routes_disabled
)
for switch_name in "${enabled_route_switches[@]}"; do
  bench --site "${SITE_NAME}" set-config --parse "${switch_name}" False
done

# Production ERP authorization ingress and every real ERP adapter stay closed.
bench --site "${SITE_NAME}" set-config --parse npi_p9_04_authorization_projection_routes_disabled True
bench --site "${SITE_NAME}" migrate
bench --site "${SITE_NAME}" execute npi_core.production_setup.enforce_production_auth_settings
bench --site "${SITE_NAME}" clear-cache
bench --site "${SITE_NAME}" enable-scheduler
bench --site "${SITE_NAME}" set-maintenance-mode off

site_has_app npi_core
site_has_app npi_integration
echo "Production Site initialization completed without enabling ERP adapters."
