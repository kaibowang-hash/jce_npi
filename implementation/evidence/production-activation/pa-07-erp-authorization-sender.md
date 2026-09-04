# PA-07 ERPNext Authorization Sender

Status: **LOCAL LEVEL 3 PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-04 (Asia/Bangkok)

## Outcome

An independent `npi_erpnext_connector` Frappe custom app now implements the
missing ERPNext-owned authorization sender without changing the existing
LaunchFlow receiver, architecture, contracts or ownership. The app is installed
only on ERPNext and remains inert unless its Site switch is exactly `false` and
all closed non-secret mappings plus the runtime-only service token are present.

The sender reads one canonical System User's assigned roles and bounded
Project/Company/Customer/Supplier User Permissions, applies only explicit
owner-approved maps, and creates one immutable complete replacement in the
read-only `NPI ERP Authorization Delivery` outbox. User and User Permission
hooks, bounded recovery and hourly reconciliation use the same path. Missing
identity, role, Project UUID or Project-access decisions fail closed.

HTTP delivery uses one fixed HTTPS BFF route, no redirect, fixed connect/read
timeouts and a runtime environment credential. It stores no response body or
credential. Retryable failures use bounded exponential backoff; timeout after
receiver commit replays the exact event/request/hash. Nonretryable or exhausted
deliveries remain visible as `permanent_failure` and require an
operation-specific System Manager retry.

## Fixed safety boundary

- No ERPNext/Frappe core diff and no dependency on the LaunchFlow `npi_core`
  app.
- No generic DocType writer, caller-selected route/method, cross-database
  access, browser-to-ERP connection or dual-master field.
- No default role, automatic Project similarity mapping, password/MFA/cookie or
  provider-secret synchronization.
- Sender installation, Site configuration, process environment, service
  restart, activation and production reconciliation remain separate approved
  operations tasks.
- The LaunchFlow readiness result remains externally unverified until actual
  deployment and version-equivalent Sandbox/UAT evidence exist.

## Verification evidence

- Pure sender domain, receiver compatibility, transport, metadata, i18n,
  runtime-verifier and global permission-bypass focused suites: **22/22 PASS**.
- Exact Frappe `version-15` commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`: the app installed on disposable
  local Site `pa07.localhost`; a rollback-only runtime fixture proved default
  disabled behavior, three immutable deliveries, unchanged-current reuse,
  due-delivery recovery, historical-identity reconciliation, delivered
  revocation and exact timeout replay with no transport contact.
  Sanitized result checksum:
  `577a948aad3d3c2264499fcb0fab84f4e8e11fbbbdc86a113c9d9903a9118f65`.
- Full isolated exact-toolchain Gate: **PASS** on a clean detached
  `d21db6ff101a6e0189eae4c6c616ea70de3a12f2` base with only this staged
  change applied: repository Python **3018/3018**, frontend **1155/1155** in
  **78/78** files, **9364** literal English sources with **100% zh/zh-TW**
  coverage, production build/budgets/brand checks PASS, and npm audit reports
  **0 vulnerabilities**.

No production LaunchFlow Site, ERPNext Site, AWS resource, identity provider or
external endpoint was contacted or changed.

## Rollback and remaining activation holds

The first rollback is configuration-only: disable the ERP sender, disable
LaunchFlow projection enforcement and then close LaunchFlow ingress. Revoke the
service token while retaining both systems' audit/delivery history. App
uninstallation and schema removal require a separate reviewed change.

Production activation remains held on the approved canonical identity key,
exact role map, Project UUID/access map, dedicated LaunchFlow `NPI API User`
service actor, delivery/revocation SLA, deployment backup/rollback,
version-equivalent Sandbox and controlled UAT. No mapping is inferred by this
task.
