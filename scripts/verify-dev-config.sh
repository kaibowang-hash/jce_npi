#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

python -m json.tool .devcontainer/devcontainer.json >/dev/null
bash -n scripts/bootstrap-dev.sh scripts/init-frappe-bench.sh scripts/verify-dev-environment.sh scripts/verify-dev-config.sh

python - <<'PY'
from pathlib import Path

values = {}
for line in Path('.devcontainer/toolchain.env').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith('#'):
        key, value = line.split('=', 1)
        values[key] = value

required = {
    'PYTHON_EXPECTED_MAJOR_MINOR', 'NODE_EXPECTED_VERSION', 'NPM_EXPECTED_MAJOR',
    'DOCKER_EXPECTED_VERSION', 'BENCH_EXPECTED_VERSION', 'VITE_EXPECTED_VERSION',
    'FRAPPE_BRANCH', 'FRAPPE_COMMIT',
}
assert values.keys() >= required
assert values['FRAPPE_BRANCH'] == 'version-15'
assert len(values['FRAPPE_COMMIT']) == 40
assert all(character in '0123456789abcdef' for character in values['FRAPPE_COMMIT'])

devcontainer = Path('.devcontainer/devcontainer.json').read_text(encoding='utf-8')
assert 'ghcr.io/devcontainers/features/node:2.1.0' in devcontainer
assert 'ghcr.io/devcontainers/features/docker-in-docker:3.0.1' in devcontainer
assert 'scripts/bootstrap-dev.sh' in devcontainer

dockerfile = Path('.devcontainer/Dockerfile').read_text(encoding='utf-8')
assert 'mcr.microsoft.com/devcontainers/python:1-3.11-bookworm@sha256:' in dockerfile

bench_init = Path('scripts/init-frappe-bench.sh').read_text(encoding='utf-8')
assert 'git -C "${source_checkout}" fetch --depth 1 origin "${FRAPPE_COMMIT}"' in bench_init
assert 'actual_commit="$(git -C "${bench_path}/apps/frappe" rev-parse HEAD)"' in bench_init

compose = Path('docker-compose.yml').read_text(encoding='utf-8')
assert 'mariadb:10.6' in compose
assert 'redis:7.2-alpine' in compose
assert compose.count('@sha256:') == 2
assert '127.0.0.1:3306:3306' in compose
assert '127.0.0.1:6379:6379' in compose
PY

echo "development environment configuration verification passed"
