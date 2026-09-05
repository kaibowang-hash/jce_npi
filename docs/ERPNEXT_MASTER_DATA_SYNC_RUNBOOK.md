# ERPNext Master Data Synchronization Runbook

Status: **CODE READY FOR ERPNEXT-TEST — NOT AUTHORIZED FOR PRODUCTION**

This runbook covers the operation-specific, full-catalog synchronization of
ERPNext-owned `Customer`, `Supplier`, `Item Group`, and `Item` reference data to
NPI One. ERPNext remains the only editable owner. NPI One stores read-only
snapshots and current catalog entries for selection and display; it does not
write these masters back, expose a generic DocType endpoint, or query the ERP
database directly.

## Accounts and credentials

Use one dedicated enabled LaunchFlow **System User** with the `NPI API User`
role for ERPNext-to-NPI transport. The existing authorization-projection
transport user may be reused because both routes are fixed, authenticated,
ERP-owned replacement operations. Do not create an ERPNext business user or
business document to enable synchronization.

Provide the complete HTTP `Authorization` header only to the ERPNext web,
short-worker, and scheduler processes through
`NPI_ERP_AUTHORIZATION_TOKEN`. Never store its value in Git, Site Config,
screenshots, evidence, logs, or command history.

## Exact source fields

The connector reads only these bounded ERPNext fields:

- `Customer`: `name`, `customer_name`, `disabled`, `customer_group`, `modified`;
- `Supplier`: `name`, `supplier_name`, `disabled`, `supplier_group`, `modified`;
- `Item Group`: `name`, `item_group_name`, `parent_item_group`, `is_group`,
  `modified`;
- `Item`: `name`, `item_name`, `disabled`, `item_group`, `stock_uom`,
  `is_stock_item`, `modified`.

Each catalog is sorted by ERPNext key and limited to 10,000 records. Exceeding
the limit, an invalid field shape, an unsupported environment, or ambiguous
configuration fails closed.

## Installation and disabled configuration

Install or upgrade `apps/npi_erpnext_connector` only through the approved
custom-app deployment procedure, then migrate the ERPNext test Site. Install
the matching NPI receiving code and migrate the LaunchFlow Site first. Both
sides remain inert until the exact booleans below are changed.

ERPNext test Site:

```text
bench --site <erpnext-test-site> set-config --parse npi_erp_master_data_sender_disabled true
bench --site <erpnext-test-site> set-config npi_erp_master_data_target_base_url <launchflow-https-origin>
bench --site <erpnext-test-site> set-config npi_erp_master_data_source_environment test
```

LaunchFlow Site:

```text
bench --site <launchflow-site> set-config --parse npi_erp_master_data_routes_disabled true
```

The connector supports Frappe/ERPNext majors 15 and 16 and uses Python 3.10
compatible code. No core file, standard DocType schema, or standard permission
is modified.

## ERPNext-test activation sequence

1. Verify the installed app versions and that the four NPI master-data support
   DocTypes migrated successfully.
2. Confirm the runtime token is visible to ERPNext web, short-worker, and
   scheduler processes without printing it.
3. Enable the LaunchFlow receiver first:

   ```text
   bench --site <launchflow-site> set-config --parse npi_erp_master_data_routes_disabled false
   ```

4. Enable the ERPNext test sender:

   ```text
   bench --site <erpnext-test-site> set-config --parse npi_erp_master_data_sender_disabled false
   ```

5. Queue one full, operation-specific reconciliation:

   ```text
   bench --site <erpnext-test-site> execute npi_erpnext_connector.master_data_worker.reconcile_master_catalogs
   ```

6. Inspect the read-only `NPI ERP Master Data Delivery` rows. All four catalog
   kinds must be `delivered`; `pending`, `retry`, and `permanent_failure` are
   not success.
7. On LaunchFlow, verify exactly four `NPI ERP Master Catalog Head` rows, each
   with the expected source environment, current source version, payload hash,
   record count, and recent synchronization time.
8. Compare bounded counts and selected known keys through the fixed
   `GET /api/npi/v1/integration/erpnext/master-data` route. Test an ERPNext test
   update, disable, and deletion: update/disable must replace the entry and a
   removed key must become a retained tombstone that is absent from the current
   API collection.
9. Requeue the same unchanged catalog and verify no second version or business
   record is created. Exercise a timeout-after-commit and confirm the same
   event/request/hash is retried as an exact replay.

The five-minute recovery job retries pending deliveries with bounded
exponential backoff. The fifteen-minute reconciliation queues all four source
catalogs and creates a new immutable version only when a catalog hash changes.
A reviewed permanent failure may be retried only through
`npi_erpnext_connector.master_data_worker.retry_failed_master_data_delivery`.

## Monitoring and rollback

Monitor oldest pending/retry age, permanent failures, four-head freshness,
source versions, counts, and hashes. Do not export event JSON or master record
values into deployment evidence.

Rollback order:

1. set `npi_erp_master_data_sender_disabled` to `true` on ERPNext test;
2. allow already accepted work to finish, then set
   `npi_erp_master_data_routes_disabled` to `true` on LaunchFlow;
3. revoke or rotate the dedicated transport credential if required;
4. retain delivery, snapshot, entry tombstone, and audit history;
5. uninstall the custom app only in a separately approved rollback after its
   additive-schema retention impact is reviewed.

No step in this runbook authorizes a production ERPNext connection or mutation.
