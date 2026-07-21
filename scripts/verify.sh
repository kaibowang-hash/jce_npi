#!/usr/bin/env bash
set -euo pipefail
bash scripts/verify-dev-config.sh
python -m json.tool contracts/integration-event.schema.json >/dev/null
python -m json.tool design/design-tokens.json >/dev/null
find apps -name '*.json' -print0 | xargs -0 -r -n1 python -m json.tool >/dev/null
python -m compileall -q apps/npi_core apps/npi_integration tests
python -m unittest discover -s tests -v
python - <<'PY'
import csv
r=list(csv.DictReader(open('implementation/REQUIREMENT_TRACEABILITY.csv')))
assert len(r)==173 and len({x['requirement_id'] for x in r})==173
PY
if rg -n 'ignore_permissions|frappe\.db\.sql|TODO|FIXME' apps tests; then
  echo "prohibited backend pattern found" >&2
  exit 1
fi
git diff --check
echo "repository verification passed"
