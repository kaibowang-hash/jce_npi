# Phase 2 backend foundation

## Scope and architecture

`npi_core` and `npi_integration` are independent Frappe v15-compatible custom Apps. They do not patch Frappe or ERPNext and never access the ERPNext database. Framework-independent modules hold rules testable without a site; Frappe controllers are thin persistence adapters. Desk access is administrative/support-only.

The foundation includes project/tenant authorization; stable UUID identity and optimistic versions; audit and trace context; problem responses; private hashed file revisions; and Outbox/Inbox metadata with explicit non-success states and duplicate quarantine.

## Installation and migration

After an exact Frappe v15 bench is available, install in dependency order with standard public bench commands:

```text
bench get-app /workspace/apps/npi_core
bench get-app /workspace/apps/npi_integration
bench --site <development-site> install-app npi_core
bench --site <development-site> install-app npi_integration
bench --site <development-site> migrate
```

All Phase 2 schema changes are additive DocTypes. Re-running `migrate` is the idempotency path. No backfill, destructive default or production activation exists.

## Rollback

Before business data exists, uninstall `npi_integration` and then `npi_core` from the development site, or remove the disposable development site. Once records exist, retain the additive tables, deploy a forward fix and restore application code from the Phase 1 checkpoint. Production ERPNext is unaffected.

## Verification

Run `make verify`. It compiles both Apps, validates DocType JSON, runs Phase 2 unit/permission/reliability tests, scans prohibited implementation patterns and checks the diff. A live bench install/migrate test becomes applicable when the repository supplies the pinned Frappe runtime; its current Compose file supplies a generic Python workspace, MariaDB and Redis only.
