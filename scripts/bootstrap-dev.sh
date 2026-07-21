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

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required bootstrap command is missing: $1" >&2
    exit 1
  fi
}

for command_name in node npm docker bench sudo; do
  require_command "${command_name}"
done

installed_vite="$(vite --version 2>/dev/null || true)"
if [[ "${installed_vite}" != "vite/${VITE_EXPECTED_VERSION}"* ]]; then
  npm_command="$(command -v npm)"
  sudo "${npm_command}" install --global "vite@${VITE_EXPECTED_VERSION}"
fi

docker_wait_seconds="${NPI_DOCKER_WAIT_SECONDS:-120}"
if [[ ! "${docker_wait_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NPI_DOCKER_WAIT_SECONDS must be a positive integer." >&2
  exit 1
fi

docker_wait_started="${SECONDS}"
while true; do
  if docker info >/dev/null 2>&1; then
    break
  fi

  docker_wait_elapsed="$((SECONDS - docker_wait_started))"
  if (( docker_wait_elapsed >= docker_wait_seconds )); then
    echo "Docker daemon did not become ready after ${docker_wait_elapsed} seconds." >&2
    docker version >&2 || true
    docker context show >&2 || true
    if command -v ps >/dev/null 2>&1; then
      ps -ef | grep '[d]ockerd' >&2 || true
    fi
    for docker_log in /tmp/dockerd.log /var/log/docker.log; do
      if sudo test -r "${docker_log}"; then
        echo "Last 80 lines from ${docker_log}:" >&2
        sudo tail -n 80 "${docker_log}" >&2 || true
      fi
    done
    exit 1
  fi

  if (( docker_wait_elapsed % 10 == 0 )); then
    echo "Waiting for Docker daemon (${docker_wait_elapsed}/${docker_wait_seconds}s)..."
  fi
  sleep 2
done

bash "${repo_root}/scripts/verify-dev-environment.sh"
