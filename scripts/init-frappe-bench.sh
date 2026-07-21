#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
toolchain_file="${NPI_TOOLCHAIN_FILE:-${repo_root}/.devcontainer/toolchain.env}"
bench_path="${NPI_FRAPPE_BENCH_PATH:-${repo_root}/tmp/frappe-bench}"

# shellcheck disable=SC1090
source "${toolchain_file}"

if [[ -e "${bench_path}" ]]; then
  echo "Refusing to overwrite existing Bench path: ${bench_path}" >&2
  exit 2
fi

source_checkout="$(mktemp -d)"
cleanup() { rm -rf "${source_checkout}"; }
trap cleanup EXIT

git -C "${source_checkout}" init -q
git -C "${source_checkout}" remote add origin https://github.com/frappe/frappe.git
git -C "${source_checkout}" fetch --depth 1 origin "${FRAPPE_COMMIT}"
git -C "${source_checkout}" checkout -q --detach FETCH_HEAD

bench init \
  --frappe-path "${source_checkout}" \
  --frappe-branch "${FRAPPE_BRANCH}" \
  --python python3.11 \
  "${bench_path}"

actual_commit="$(git -C "${bench_path}/apps/frappe" rev-parse HEAD)"
if [[ "${actual_commit}" != "${FRAPPE_COMMIT}" ]]; then
  echo "Frappe commit mismatch: ${actual_commit}" >&2
  exit 1
fi

printf 'bench_path=%s\n' "${bench_path}"
printf 'frappe_commit=%s\n' "${actual_commit}"
echo "pinned Frappe Bench initialization passed"
