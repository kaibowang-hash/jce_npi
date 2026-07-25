#!/usr/bin/env bash
set -euo pipefail

expected_report="No packages with unreviewed install scripts."
report="$(npm approve-scripts --allow-scripts-pending)"
printf '%s\n' "${report}"
if [[ "${report}" != "${expected_report}" ]]; then
  echo "Unreviewed npm install scripts are prohibited." >&2
  exit 1
fi
