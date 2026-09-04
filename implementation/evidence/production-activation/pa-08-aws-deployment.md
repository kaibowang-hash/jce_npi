# PA-08 AWS Deployment

Status: **DEPLOYED — FINAL ORDINARY CI AND LEVEL 3 PENDING**

Date: 2026-09-04 (Asia/Bangkok)

## Authorized outcome

Install the current LaunchFlow release through SSH alias `LaunchFlow` on the
existing AWS host. Reuse the current independent Docker/Frappe Site and named
volumes; do not clear the database merely because the visible UI is not ready.

## Pre-deployment facts

- SSH connection: PASS.
- Existing runtime: independent Dockerized Frappe v15 LaunchFlow stack.
- Existing backend/SPA revision: `d23d564d` (short display only).
- Existing Site/database/Redis/log storage: named persistent volumes.
- Existing server source tree: dirty, with a not-ready uncommitted experiment;
  it is not an immutable release input and must be archived before replacement.
- Target package: `003597014d18cc35d74caf695e8f201e52f1306a`.
- Target LaunchFlow apps: `npi_core`, then `npi_integration` only.
- ERPNext-side `npi_erpnext_connector`: explicitly excluded.

No endpoint, host, user, key, password, token or server-only configuration
value is recorded here.

## Verification before production mutation

- Deployment-specific tests: 9/9 PASS.
- Repository: 3027/3027 PASS.
- Frontend: 1155/1155 PASS in 78 files.
- i18n: 9364 literal English sources, 100% zh/zh-TW.
- Production build, budgets, brand and install-script checks: PASS.
- `package-lock.json` checksum:
  `ead6cb76517681a2699d3dccbbbfb32d551713be27015d5ac98645af1b1449`.
- Immutable image build executed the unchanged mandatory full and
  production-only audits: zero vulnerabilities.
- Exact-SHA ordinary CI `33866659603`, attempt 4: PASS. Repository, secret,
  frontend verification, both E2E shards, visual and aggregate lanes passed.
  Attempts 1-3 failed closed on transient registry 503 responses from the
  second audit request; no audit or workflow behavior was weakened.

## Preserved recovery inputs

- The dirty server worktree was not used as a release input. A root-owned
  source archive was created before the deployment with checksum
  `sha256:4319c6b354d4f648c4a7121409c2564b9530434e81e1c2d3692d4b1621099bfe`.
- The existing Site, database, public files, private files and Site
  configuration were captured in one encrypted full backup. Independent
  decryption/list verification passed; encrypted checksum:
  `sha256:a7121fdad7f39cbbe1f08d5a916c68a6caa95c0d5b1b29b9a9618cb630ca7d28`.
- The four named MariaDB, Redis queue, Site and log volumes were preserved.
- The previous backend and SPA image pair at `d23d564d` remains locally
  available with matching immutable revision labels. The previous root-only
  environment file is retained separately on the host.

## Exact release and activation

- The clean remote worktree and both OCI revision labels matched
  `003597014d18cc35d74caf695e8f201e52f1306a`.
- The immutable release directory contains 2433 tracked files. Its normalized
  package checksum is
  `sha256:0284169e6bf726b83b659931998976ab2696d33438c23aba39d3e6f7e441c172`.
- The server ran the fixed configurator, guarded Site initializer and Frappe
  migration against the preserved volumes before switching the release
  pointer and backend/SPA image pair together.
- One initial transport attempt entered maintenance mode and then ended before
  stopping any service because the nested Compose command consumed the
  remaining remote standard input. The previous pointer, image configuration
  and all ten services remained intact. The resumed command explicitly closed
  nested command input and completed the same frozen activation without a
  second migration or scope change.
- The release pointer switched at `2026-09-04T12:38:57Z`; the post-deployment
  health gate passed on its first attempt by `2026-09-04T12:39:30Z`.

## Post-deployment verification

| Check | Result |
| --- | --- |
| Required Compose services | PASS — all 10 running |
| HTTPS root, health and login entry | PASS — HTTP 200 with trusted TLS |
| Unauthenticated NPI session contract | PASS — HTTP 401 `AUTHENTICATION_REQUIRED` |
| Installed Site apps | PASS — `frappe`, `npi_core`, `npi_integration` only |
| Production ownership/environment markers | PASS |
| Developer mode/disposable marker | PASS — disabled/absent |
| Public self-signup | PASS — disabled |
| Scheduler | PASS — enabled |
| Backend and SPA running revision labels | PASS — exact deployed SHA |
| Previous image pair | PASS — retained |
| Full encrypted backup checksum | PASS — independently rechecked after activation |

The real ERP adapter and P9-04 authorization projection ingress remain
disabled. No ERPNext connection, ERPNext app installation, business-data
synchronization, credential disclosure or production volume deletion occurred.

## Remaining release evidence and rollback

Commit this sanitized checkpoint, require one exact-SHA ordinary CI PASS, then
run the PA-08 Level 3 release gate. Those evidence-only checks do not trigger a
second production deployment. Rollback switches both images together and never
attempts a schema downgrade; use a forward fix or approved backup restore when
schema compatibility is uncertain.
