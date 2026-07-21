#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

python -m json.tool .devcontainer/devcontainer.json >/dev/null
python -m json.tool .devcontainer/devcontainer-lock.json >/dev/null
bash -n scripts/bootstrap-dev.sh scripts/init-frappe-bench.sh scripts/verify-dev-environment.sh scripts/verify-dev-config.sh

python scripts/verify_devcontainer.py

python - <<'PY'
from pathlib import Path

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
