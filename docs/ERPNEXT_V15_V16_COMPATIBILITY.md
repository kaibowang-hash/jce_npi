# ERPNext v15/v16 Connector Compatibility Evidence

Date: 2026-09-06

## Scope

This evidence applies to the standalone `npi_erpnext_connector` custom app at
version `0.9.1`. It covers installation, schema and configured non-production
execution compatibility. Least-privilege service identities and explicit
project-bound profiles are installed only on `erpnext-test`.

## ERPNext v15 executable verification

The current working tree was installed into a disposable local Docker stack
using the official `frappe/erpnext:v15` image. The resulting versions were:

- ERPNext `15.121.0`
- Frappe `15.120.0`
- Python `3.11`
- MariaDB `10.6`
- `npi_erpnext_connector` `0.9.1`

`bench --site v15-compat.localhost migrate` completed successfully. The
following additive connector patches executed successfully:

- `v0_3.sync_mbom_doctypes`
- `v0_4.sync_tool_asset_schema`
- `v0_5.sync_project_schema`
- `v0_5.sync_trial_summary_schema`
- `v0_6.sync_master_data_schema`
- `v0_9.sync_engineering_change_schema`

The migrated site contained all 13 connector-owned support DocTypes and all
seven service/viewer roles. Runtime imports compiled successfully. Item, MBOM,
and Tool Asset capability endpoints returned app version `0.9.1`, advertised
Frappe majors 15 and 16, and remained disabled by default.

## ERPNext v16 target fact

The authorized `erpnext-test` target currently runs ERPNext `16.14.0` and
Frappe `16.16.0`. Connector `0.9.1` is installed and migrated there. All 13
connector support DocTypes exist; Item, MBOM, Tool Asset create/update, released
Trial Summary and Engineering Change receivers are enabled. Authorization,
Project and master-data senders are also enabled and their current deliveries
are confirmed by the live evidence in
`implementation/evidence/erpnext-test/full-integration-live-2026-09-06.md`.

## Compatibility controls

- Package metadata requires Python `>=3.10`.
- Connector code does not use `datetime.UTC` or `enum.StrEnum`.
- No ERPNext or Frappe core file is patched.
- Schema changes are additive custom fields and connector-owned DocTypes.
- Capability responses read the installed package version instead of a stale
  hard-coded version.
- Receivers fail closed by default and do not enable themselves during install
  or migration. The live test Site was enabled only through explicit bounded
  configuration after backup and least-privilege identity verification.

## Rollback boundary

For `erpnext-test`, take a site backup and a copy of the currently installed
custom app before deployment. If migration or smoke verification fails, restore
the site backup and the prior app copy together. This evidence does not
authorize or describe any production deployment.
