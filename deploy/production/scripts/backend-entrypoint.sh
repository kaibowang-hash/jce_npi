#!/usr/bin/env bash
set -euo pipefail

assets_path=/home/frappe/frappe-bench/sites/assets
baked_path=/home/frappe/frappe-bench/image-assets
if [[ ! -d "${baked_path}" ]]; then
  echo "Baked Frappe assets are missing." >&2
  exit 1
fi
if [[ -e "${assets_path}" && ! -L "${assets_path}" ]]; then
  echo "Refusing to replace a non-symlink assets path." >&2
  exit 1
fi
ln -sfn "${baked_path}" "${assets_path}"
exec "$@"
