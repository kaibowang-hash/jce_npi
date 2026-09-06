# Phase 2 Gate — PASS

Scope: M2-01 through M2-06. The checkpoint adds independent `npi_core` and `npi_integration` Frappe App packages, project/tenant authorization, immutable global identity and audit foundations, optimistic concurrency, problem/trace responses, private hashed file revisions, and explicit Outbox/Inbox state and idempotency rules.

## Requirement and task evidence

- M2-01: App metadata, hooks, modules and additive DocType JSON under `apps/npi_core` and `apps/npi_integration`.
- M2-02: `foundation/security.py` plus authentication, tenant, project access and external-user denial tests.
- M2-03: `identity.py`, `concurrency.py`, `audit.py` plus UUID immutability, stale-version, ETag and redaction tests.
- M2-04: `api.py`, `errors.py`, `tracing.py` plus problem content type/code/trace tests.
- M2-05: `files.py` and NPI File Revision metadata plus private/hash/scan/release immutability tests.
- M2-06: `reliable.py` and Inbox/Outbox metadata plus pending/processing/failure/success, duplicate and hash-conflict quarantine tests.

## Reproducible gate evidence

- Static/JSON/diff: `make verify` — PASS; Python compilation, all App DocType JSON, repository JSON and `git diff --check` passed.
- Unit/API/permission/security/integration: `python -m unittest discover -s tests -v` — PASS, 13 tests.
- Security pattern review: `rg -n 'ignore_permissions|frappe\.db\.sql|TODO|FIXME' apps tests` — PASS with no matches.
- Packaging: `python -m pip wheel ...` — not applicable in this checkout because the Phase 1 workspace image has no `pip`; no dependency was installed to conceal that fact.
- Live migration/rollback: live `bench install-app/migrate` is not applicable because the repository has no Frappe bench executable or pinned Frappe service. Additive DocType metadata and re-run invariants are tested; install order and forward-fix/rollback are documented in `docs/PHASE_2_BACKEND_FOUNDATION.md`.
- Compose runtime: `docker compose config -q` could not run because Docker CLI is absent in this execution environment. The unchanged Compose file was already accepted by the Phase 1 gate.
- Frontend/E2E/visual/i18n: not applicable; Phase 2 has no terminal UI or user-visible catalog change. Phase 3 owns those gates.

## Release review

No Frappe/ERPNext core patch, cross-database access, browser ERP call, generic DocType business API, `ignore_permissions`, direct SQL, secret, fake success, accepted-path TODO, dual-master field or destructive migration was found. Message state begins at `pending` and only explicit completion yields `succeeded`; duplicate event payload conflicts quarantine instead of overwriting. Desk permissions are System Manager support views only.

Rollback is additive and documented. The user's pre-existing `.gitignore` modification is excluded from the Phase 2 checkpoint. Gate result: **PASS**.
