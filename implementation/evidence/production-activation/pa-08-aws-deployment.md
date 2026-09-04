# PA-08 AWS Deployment

Status: **IN PROGRESS — EXACT-SHA ORDINARY CI REQUIRED**

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
- Target package: `537b8e64e03cf2ed20f9e9df3e54d0a858f63eee`.
- Target LaunchFlow apps: `npi_core`, then `npi_integration` only.
- ERPNext-side `npi_erpnext_connector`: explicitly excluded.

No endpoint, host, user, key, password, token or server-only configuration
value is recorded here.

## Verification before production mutation

- Deployment-specific tests: 8/8 PASS.
- Repository: 3026/3026 PASS.
- Frontend: 1155/1155 PASS in 78 files.
- i18n: 9364 literal English sources, 100% zh/zh-TW.
- Production build, budgets, brand and install-script checks: PASS.
- `package-lock.json` checksum:
  `ead6cb76517681a2699d3dccbbbfb32d551713be27015d5ac98645af1b1449`.
- Same-day retained exact-lock audit: zero vulnerabilities.
- Fresh local and AWS npm audit POSTs: external timeout, no vulnerability result.
  The image build retains the unchanged mandatory audit and must fail closed.
- Ordinary CI `33858955369`: FAIL before Gitleaks because PA-08 had not yet
  replaced the completed P9-08 current-task manifest. Production unchanged.

## Required execution and rollback

One corrected exact-SHA ordinary CI PASS must precede: server worktree archive,
encrypted full backup, image build, guarded Site initialization/migration,
backend/SPA pair switch and health/login/API/scheduler verification. Retain the
old image pair. Rollback switches both images together and never attempts a
schema downgrade; use a forward fix or approved backup restore if schema
compatibility is uncertain.
