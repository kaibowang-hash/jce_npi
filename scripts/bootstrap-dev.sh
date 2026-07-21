#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
toolchain_file="${NPI_TOOLCHAIN_FILE:-${repo_root}/.devcontainer/toolchain.env}"

if [[ ! -f "${toolchain_file}" ]]; then
  echo "Toolchain definition not found: ${toolchain_file}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${toolchain_file}"

installed_vite="$(vite --version 2>/dev/null || true)"
if [[ "${installed_vite}" != "vite/${VITE_EXPECTED_VERSION}"* ]]; then
  sudo npm install --global "vite@${VITE_EXPECTED_VERSION}"
fi

for attempt in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == "30" ]]; then
    echo "Docker daemon did not become ready after 30 seconds." >&2
    exit 1
  fi
  sleep 1
done

bash "${repo_root}/scripts/verify-dev-environment.sh"
