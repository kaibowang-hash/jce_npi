# ERPNext Authorization Sender Runbook

Status: **CODE READY FOR SANDBOX — NOT INSTALLED OR ENABLED IN PRODUCTION**

This runbook covers the independent `npi_erpnext_connector` custom app. The app
does one thing: it sends a complete, versioned replacement of one ERPNext-owned
internal user's LaunchFlow roles and approved scopes to the existing LaunchFlow
authorization-projection route. It does not change ERPNext/Frappe core, copy
passwords or MFA factors, provide a generic DocType writer, or make LaunchFlow a
second permission master.

## Where administrators work

- Microsoft Entra remains the sign-in and MFA authority.
- JCE Core Desk remains the only editable administration surface for internal
  User enabled state, ERP roles/Role Profiles and User Permissions.
- LaunchFlow `/app` is for System Manager configuration and support only. It is
  not a second user-role editor.
- The LaunchFlow application opens only after a valid Frappe session exists.
  Unknown, disabled, expired or unmapped authorization projections fail closed
  after projection enforcement is enabled.

## Required owner-approved inputs

Do not enable either side until all of the following are approved and recorded
outside Git where appropriate:

1. the canonical lowercase email match between Entra, JCE Core User and the
   LaunchFlow Frappe User;
2. an exact ERP role to LaunchFlow role map, with no default role;
3. an exact ERP Project key to LaunchFlow Project UUID map for every Project
   User Permission in scope;
4. an ERP-role to Project access map using only `view`, `contribute`, `approve`
   or `administer`;
5. the LaunchFlow HTTPS origin, projection validity window and delivery SLA;
6. a dedicated enabled LaunchFlow System User with only the `NPI API User`
   transport role and a separately managed API credential.

Company, Customer and Supplier User Permissions keep their ERP reference keys.
Project permissions are rejected unless the Project UUID mapping is explicit.
A noncanonical identity, missing role map, missing Project map, unsupported
value or more than 500 System Users stops the affected run; the sender never
guesses.

## Installation boundary

Installation is a production ERPNext mutation and therefore requires its own
approved deployment task, backup and rollback window. The reviewed app source
is `apps/npi_erpnext_connector`. Install it into the ERPNext Bench by the normal
custom-app release procedure, migrate the target Site, and verify that
`NPI ERP Authorization Delivery` exists. Installation is inert because the
sender switch is absent/default-disabled.

The app must be installed only on the ERPNext Site. Do not install it on the
LaunchFlow Site; LaunchFlow already has the receiving implementation in
`npi_integration`.

## Non-secret configuration

Keep the sender disabled while applying configuration. Values below are
placeholders; role, Project and origin values must come from the approved
mapping, not from this document.

```text
bench --site <erp-site> set-config --parse npi_erp_authorization_sender_disabled true
bench --site <erp-site> set-config npi_erp_authorization_target_base_url <launchflow-https-origin>
bench --site <erp-site> set-config --parse npi_erp_authorization_role_map '<approved-json-object>'
bench --site <erp-site> set-config --parse npi_erp_authorization_project_map '<approved-json-object>'
bench --site <erp-site> set-config --parse npi_erp_authorization_project_access_by_role '<approved-json-object>'
bench --site <erp-site> set-config --parse npi_erp_authorization_ttl_seconds <approved-300-to-86400>
```

Provide the complete HTTP `Authorization` value to ERPNext web, short-worker
and scheduler processes through the runtime environment variable
`NPI_ERP_AUTHORIZATION_TOKEN`. Never place its value in Git, Site Config,
terminal history, screenshots or evidence. Restarting services to load that
environment is a separate approved operations action.

On LaunchFlow, keep projection enforcement off and enable only ingress for the
initial seed:

```text
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_role_allowlist '<approved-sorted-json-role-array>'
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_max_ttl_seconds '<approved-integer-300-to-86400>'
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_projection_enforced false
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_projection_routes_disabled false
```

## Sandbox activation sequence

1. Prove the exact app/version and non-secret mapping on version-equivalent
   Sandbox Sites. Confirm self signup remains disabled.
2. Set `npi_erp_authorization_sender_disabled` to `false` on ERPNext. This exact
   boolean is required; missing, `0`, `1`, strings and all other shapes remain
   disabled.
3. Run the operation-specific full reconciliation once, without user values in
   the command:

   ```text
   bench --site <erp-site> execute npi_erpnext_connector.worker.reconcile_all_users
   ```

4. In ERPNext Desk, inspect the read-only
   `NPI ERP Authorization Delivery` list. Every intended user must be
   `delivered`; `retry` and `permanent_failure` are not success.
5. Test enabled, disabled, unmapped-role, Project-scope, duplicate, stale,
   timeout-after-commit and credential-revocation cases. Confirm exact retry
   keeps the same event/request/hash.
6. Test Entra login for the positive and negative role/Project matrix. Only
   after every required projection is current may LaunchFlow enforcement be set
   to `true`.

User and User Permission changes enqueue a complete replacement after commit.
The five-minute recovery job retries pending deliveries with bounded exponential
backoff; the hourly reconciliation repairs missed events and refreshes
near-expiry projections. After ten failed attempts, or any nonretryable HTTP
response, the row becomes `permanent_failure`. A System Manager may retry one
reviewed failed row through the fixed
`npi_erpnext_connector.worker.retry_failed_delivery` method; there is no generic
retry or target-method input.

## Monitoring and rollback

Monitor pending/retry age, permanent failures, expiry margin and LaunchFlow
projection/audit counts. Logs and evidence may contain only event/request/trace
IDs, status, version and hashes; do not export event JSON, identities, roles,
scopes, tokens or response bodies.

Rollback order:

1. set ERPNext `npi_erp_authorization_sender_disabled` to `true`;
2. set LaunchFlow `npi_p9_04_authorization_projection_enforced` to `false`;
3. set LaunchFlow
   `npi_p9_04_authorization_projection_routes_disabled` to `true`;
4. revoke/rotate the dedicated service credential;
5. retain delivery and LaunchFlow audit history; do not delete it or restore
   local NPI role editing as a fallback;
6. uninstall the ERPNext custom app only in a separately approved rollback task
   after its schema/data retention impact is reviewed.

Production activation still requires exact-SHA CI/Gate evidence, owner-approved
mappings, version-equivalent Sandbox/UAT and the final read-only
ERPNext–LaunchFlow compatibility reconciliation.
