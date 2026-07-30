#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# shellcheck disable=SC1091
source "${repo_root}/.devcontainer/toolchain.env"
node_actual="$(node --version 2>/dev/null || true)"
npm_actual="$(npm --version 2>/dev/null || true)"
if [[ "${node_actual}" != "${NODE_EXPECTED_VERSION}" ||
      "${npm_actual}" != "${NPM_EXPECTED_VERSION}" ]]; then
  echo "repository verification requires Node ${NODE_EXPECTED_VERSION} and npm ${NPM_EXPECTED_VERSION}; found Node ${node_actual:-missing} and npm ${npm_actual:-missing}" >&2
  exit 1
fi
bash scripts/verify-dev-config.sh
python -m json.tool contracts/integration-event.schema.json >/dev/null
python -m json.tool design/design-tokens.json >/dev/null
find apps -name '*.json' -print0 | xargs -0 -r -n1 python -m json.tool >/dev/null
python -m compileall -q apps/npi_core apps/npi_integration scripts tests
python -m unittest discover -s tests -v
python scripts/verify_prototype_approvals.py
npm --prefix frontend run verify
python scripts/verify_v1_2_reconciliation.py
if ! command -v rg >/dev/null 2>&1; then
  echo "required verification command missing: rg" >&2
  exit 1
fi
scan_status=0
rg -n 'ignore_permissions|frappe\.db\.sql|TODO|FIXME' apps tests frontend/src frontend/tests || scan_status=$?
case "${scan_status}" in
  0)
    echo "prohibited backend pattern found" >&2
    exit 1
    ;;
  1) ;;
  *)
    echo "prohibited backend pattern scan failed with status ${scan_status}" >&2
    exit "${scan_status}"
    ;;
esac
git diff --check
echo "repository verification passed"
