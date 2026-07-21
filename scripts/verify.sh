#!/usr/bin/env bash
set -euo pipefail
python -m json.tool contracts/integration-event.schema.json >/dev/null
python -m json.tool design/design-tokens.json >/dev/null
python - <<'PY'
import csv
r=list(csv.DictReader(open('implementation/REQUIREMENT_TRACEABILITY.csv')))
assert len(r)==173 and len({x['requirement_id'] for x in r})==173
PY
git diff --check
echo "repository verification passed"
