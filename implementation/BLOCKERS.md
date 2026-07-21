# Blockers

## Active hard blockers

None.

## Resolved: Phase 1.1 fresh target-container validation

The 2026-07-21 rebuilt Codespace created the intended Debian 12 target container
from the repaired branch. Its first post-create attempt exposed two additional
runtime facts that static inspection could not prove: `sudo npm` lost the Node
Feature PATH, and the selected Moby `28.3.3` package reports runtime version
`28.3.3-1`. Repair round 4 installs Vite through the writable remote-user npm
prefix, verifies Docker client/server against the selected semantic version and
records their complete package revision plus the actual Compose v2 runtime.

The repaired post-create path, `make verify-dev-environment`, `make verify` and
`git diff --check` all pass in the fresh target container. Phase 1.1 is closed
and Phase 3 is active.

Production ERPNext credentials and activation remain explicitly out of scope
and are not a development blocker. The missing sanitized ERPNext reconciliation
package pauses only later formal business logic that depends on actual ERP
customization facts; it does not block Phase 3.
