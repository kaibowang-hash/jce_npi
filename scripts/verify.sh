#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# shellcheck disable=SC1091
source "${repo_root}/.devcontainer/toolchain.env"
verification_mode="${1:---all}"
case "${verification_mode}" in
  --all)
    verify_repository=true
    verify_frontend=true
    ;;
  --repository)
    verify_repository=true
    verify_frontend=false
    ;;
  --frontend)
    verify_repository=false
    verify_frontend=true
    ;;
  *)
    echo "Usage: scripts/verify.sh [--all|--repository|--frontend]" >&2
    exit 2
    ;;
esac

if [[ "${verify_frontend}" == true ]]; then
  node_actual="$(node --version 2>/dev/null || true)"
  npm_actual="$(npm --version 2>/dev/null || true)"
  if [[ "${node_actual}" != "${NODE_EXPECTED_VERSION}" ||
        "${npm_actual}" != "${NPM_EXPECTED_VERSION}" ]]; then
    echo "frontend verification requires Node ${NODE_EXPECTED_VERSION} and npm ${NPM_EXPECTED_VERSION}; found Node ${node_actual:-missing} and npm ${npm_actual:-missing}" >&2
    exit 1
  fi
fi

if [[ "${verify_repository}" == true ]]; then
  bash scripts/verify-dev-config.sh
  python -m json.tool contracts/integration-event.schema.json >/dev/null
  python -m json.tool design/design-tokens.json >/dev/null
  find apps -name '*.json' -print0 | xargs -0 -r -n1 python -m json.tool >/dev/null
  python -m compileall -q apps/npi_core apps/npi_integration scripts tests
  python -m unittest tests.test_phase8_item_publish_security -v
  python -m unittest discover -s tests -v
  python scripts/verify_prototype_approvals.py
  python scripts/verify_p0_visual_governance.py
  python scripts/verify_v1_2_reconciliation.py
  if ! command -v rg >/dev/null 2>&1; then
    echo "required verification command missing: rg" >&2
    exit 1
  fi
  run_zero_match_scan() {
    local scan_name="$1"
    shift
    local scan_status
    if "$@"; then
      scan_status=0
    else
      scan_status=$?
    fi
    case "${scan_status}" in
      0)
        echo "${scan_name} found a prohibited pattern" >&2
        return 1
        ;;
      1)
        return 0
        ;;
      *)
        echo "${scan_name} scan failed with status ${scan_status}" >&2
        return "${scan_status}"
        ;;
    esac
  }
  run_zero_match_scan "non-Python permission bypass" \
    rg -n --glob '!**/*.py' 'ignore_permissions' apps frontend/src
  run_zero_match_scan "direct Frappe SQL" \
    rg -n 'frappe[.]db[.]sql' apps tests frontend/src frontend/tests
  run_zero_match_scan "marker scan" \
    rg -n '[T]ODO|[F]IXME' apps tests frontend/src frontend/tests scripts
fi

if [[ "${verify_frontend}" == true ]]; then
  npm --prefix frontend run verify
fi

git diff --check
echo "${verification_mode#--} verification passed"
