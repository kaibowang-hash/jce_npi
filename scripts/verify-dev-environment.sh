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
    echo "Required development command is missing: $1" >&2
    return 1
  fi
}

for command_name in node npm python docker bench vite; do
  require_command "${command_name}"
done

node_actual="$(node --version)"
npm_actual="$(npm --version)"
python_actual="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
docker_actual="$(docker version --format '{{.Client.Version}}')"
compose_actual="$(docker compose version --short)"
bench_actual="$(bench --version)"
vite_actual="$(vite --version)"

[[ "${node_actual}" == "${NODE_EXPECTED_VERSION}" ]] || { echo "Node mismatch: ${node_actual}" >&2; exit 1; }
[[ "${npm_actual%%.*}" == "${NPM_EXPECTED_MAJOR}" ]] || { echo "npm mismatch: ${npm_actual}" >&2; exit 1; }
[[ "${python_actual}" == "${PYTHON_EXPECTED_MAJOR_MINOR}" ]] || { echo "Python mismatch: ${python_actual}" >&2; exit 1; }
[[ "${docker_actual}" == "${DOCKER_EXPECTED_VERSION}" ]] || { echo "Docker mismatch: ${docker_actual}" >&2; exit 1; }
[[ -n "${compose_actual}" ]] || { echo "Docker Compose v2 is unavailable." >&2; exit 1; }
[[ "${bench_actual}" == "${BENCH_EXPECTED_VERSION}" ]] || { echo "Bench mismatch: ${bench_actual}" >&2; exit 1; }
[[ "${vite_actual}" == "vite/${VITE_EXPECTED_VERSION}"* ]] || { echo "Vite mismatch: ${vite_actual}" >&2; exit 1; }

docker info >/dev/null
docker compose -f "${repo_root}/docker-compose.yml" config -q

printf 'node=%s\n' "${node_actual}"
printf 'npm=%s\n' "${npm_actual}"
printf 'python=%s\n' "$(python --version 2>&1)"
printf 'docker=%s\n' "${docker_actual}"
printf 'compose=%s\n' "${compose_actual}"
printf 'bench=%s\n' "${bench_actual}"
printf 'vite=%s\n' "${vite_actual}"
printf 'frappe_branch=%s\n' "${FRAPPE_BRANCH}"
printf 'frappe_commit=%s\n' "${FRAPPE_COMMIT}"
echo "development environment verification passed"
