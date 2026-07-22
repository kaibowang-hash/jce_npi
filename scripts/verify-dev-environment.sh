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

for command_name in node npm yarn python docker bench uv vite; do
  require_command "${command_name}"
done

node_actual="$(node --version)"
npm_actual="$(npm --version)"
yarn_actual="$(yarn --version)"
python_actual="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
docker_client_actual="$(docker version --format '{{.Client.Version}}')"
docker_server_actual="$(docker version --format '{{.Server.Version}}')"
compose_actual="$(docker compose version --short)"
bench_actual="$(bench --version)"
uv_actual="$(uv --version)"
vite_actual="$(vite --version)"
uv_version_actual="${uv_actual#uv }"
uv_version_actual="${uv_version_actual%% *}"
vite_version_actual="${vite_actual%% *}"
docker_runtime_pattern="^${DOCKER_EXPECTED_VERSION//./\\.}(-[0-9]+)?$"

[[ "${node_actual}" == "${NODE_EXPECTED_VERSION}" ]] || { echo "Node mismatch: ${node_actual}" >&2; exit 1; }
[[ "${npm_actual}" == "${NPM_EXPECTED_VERSION}" ]] || { echo "npm mismatch: ${npm_actual}" >&2; exit 1; }
[[ "${yarn_actual}" == "${YARN_EXPECTED_VERSION}" ]] || { echo "Yarn mismatch: ${yarn_actual}" >&2; exit 1; }
[[ "${python_actual}" == "${PYTHON_EXPECTED_MAJOR_MINOR}" ]] || { echo "Python mismatch: ${python_actual}" >&2; exit 1; }
[[ "${docker_client_actual}" =~ ${docker_runtime_pattern} ]] || { echo "Docker client mismatch: ${docker_client_actual}" >&2; exit 1; }
[[ "${docker_server_actual}" =~ ${docker_runtime_pattern} ]] || { echo "Docker server mismatch: ${docker_server_actual}" >&2; exit 1; }
[[ "${compose_actual}" == 2.* ]] || { echo "Docker Compose v2 mismatch: ${compose_actual}" >&2; exit 1; }
[[ "${bench_actual}" == "${BENCH_EXPECTED_VERSION}" ]] || { echo "Bench mismatch: ${bench_actual}" >&2; exit 1; }
[[ "${uv_version_actual}" == "${UV_EXPECTED_VERSION}" ]] || { echo "uv mismatch: ${uv_actual}" >&2; exit 1; }
[[ "${vite_version_actual}" == "vite/${VITE_EXPECTED_VERSION}" ]] || { echo "Vite mismatch: ${vite_actual}" >&2; exit 1; }

docker info >/dev/null
docker compose -f "${repo_root}/docker-compose.yml" config -q

printf 'node=%s\n' "${node_actual}"
printf 'npm=%s\n' "${npm_actual}"
printf 'yarn=%s\n' "${yarn_actual}"
printf 'python=%s\n' "$(python --version 2>&1)"
printf 'docker_client=%s\n' "${docker_client_actual}"
printf 'docker_server=%s\n' "${docker_server_actual}"
printf 'compose=%s\n' "${compose_actual}"
printf 'bench=%s\n' "${bench_actual}"
printf 'uv=%s\n' "${uv_actual}"
printf 'vite=%s\n' "${vite_actual}"
printf 'frappe_branch=%s\n' "${FRAPPE_BRANCH}"
printf 'frappe_commit=%s\n' "${FRAPPE_COMMIT}"
echo "development environment verification passed"
