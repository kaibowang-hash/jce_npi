# LaunchFlow Go-live and Recovery Runbook

Status: technical non-production rehearsal procedure; production inputs and
execution remain unapproved.

Requirements: `NFR-BCP-001`, `NFR-MNT-001`

## Purpose and evidence boundary

This runbook binds one exact LaunchFlow release to a repeatable database,
public-file and private-file recovery rehearsal. The executable proof runs only
inside the repository's guarded disposable `npi.localhost` Site and
`npi_one_runtime` database. It proves backup integrity, meaningful restore,
same-version migration/forward-fix compatibility and cleanup without contacting
production LaunchFlow, ERPNext, `jce.1` or external storage.

The rehearsal is engineering evidence, not a production operation. It does not
prove that daily production backups exist, that a remote copy is current, that
keys are recoverable, or that production data can meet an RPO/RTO. Suggested
targets of `RPO <= 24h` and `RTO <= 8h` remain pending business and IT approval.

## Fixed automated rehearsal

The Level 3 command remains:

```text
bash scripts/verify-frappe-runtime.sh --projection-only
```

The existing guard first verifies the physical repository Bench, exact pinned
Frappe commit, fixed Site/database, loopback database identity and disposable
marker. The cumulative application runtime then passes before P9-07 stops the
local server and performs this closed sequence:

1. Generate a value-free manifest containing the exact repository and Frappe
   SHAs, the three installed app names, app/schema tree fingerprints and a hash
   of Site configuration keys. Configuration values are excluded.
2. Add one deterministic synthetic database canary and one public plus one
   private file canary. Capture a bounded content-addressed file-tree inventory.
3. Use Frappe's public full-Site backup command to create database, public-file,
   private-file and configuration backups in a new mode-`0700` temporary
   directory. Hash and size the four mode-`0600` members. Command output and
   backup bytes are never uploaded or committed.
4. Add distinct post-backup database/public/private canaries, quarantine the
   disposable file trees and restore the backup into the same fixed disposable
   Site. No downgrade or caller-selected `--force` is used.
5. Require the pre-backup canaries and exact file-tree inventory to return and
   require every post-backup canary to be absent.
6. Run migration twice, recompute the exact release identity, and require it to
   match the pre-backup manifest. The enclosing cumulative Gate can pass only
   after this forward-fix check.
7. Emit only schema version, bounded durations, counts and SHA-256 fingerprints
   with `productionContact=false`; remove canaries and temporary backup bytes.
   Any cleanup failure fails the Gate.

The runner accepts no command-line arguments. Site, database, Bench, marker,
member names, stages and temporary-directory shape are fixed in source. Any
backup, checksum, restore, canary, file-tree, migration, release-identity or
cleanup mismatch is an honest failure.

## Production go-live prerequisites

Before an authorized production change, the named release owner and IT/
operations owner must record all of the following outside source control where
values are sensitive:

- approved exact application SHA, Frappe version and compatible migration set;
- environment-specific Site/database identity and confirmed independent-app
  installation, without changing Frappe or ERPNext core;
- exact non-secret LaunchFlow Site classification: `production` for the live
  user-facing Site or `sandbox` for a controlled non-production Site;
- backup schedule, last successful database/files/config backup, encrypted
  storage location, retention, access control and key-custody/recovery owners;
- measured production-like backup and restore duration at representative data
  volume, plus business-approved RPO and RTO;
- maintenance window, user communication, change ticket, approvers and named
  rollback decision authority;
- migration, smoke-test, monitoring, route-switch and ERP integration order;
- final full production ERPNext–LaunchFlow read-only compatibility
  reconciliation and resolved drift evidence.

Missing or stale evidence blocks production-ready. No credential, endpoint,
host, user, token, key, cookie, raw backup, business record or sensitive config
value belongs in Git, CI logs or the release manifest.

## Deployment environment identity

LaunchFlow reads its displayed environment only from the Frappe Site key
`npi_deployment_environment`. The only accepted values are `production` and
`sandbox`; the browser cannot choose or override the value. A missing, mixed-
case or different value makes session bootstrap fail closed with
`DEPLOYMENT_ENVIRONMENT_UNAVAILABLE` instead of showing a misleading label.

During an approved LaunchFlow Site change, the operator sets the non-secret
classification on the exact target Site before the new application version
receives traffic:

```text
bench --site <launchflow-site> set-config npi_deployment_environment production
```

Use `sandbox` only on an actual controlled non-production Site. After restart
or process recycle through the approved deployment mechanism, an authenticated
`GET /api/npi/v1/session/bootstrap` smoke check must return the exact
`deploymentEnvironment` value expected for that Site. Do not infer Production
from the hostname, build mode, browser profile or an operator's laptop config.

## Administration, users and access activation

An authenticated internal System Manager opens `/administration` to inspect the
non-secret production-activation status. The page reads the current LaunchFlow
Site only; it does not infer readiness from a deployment profile on an
operator's computer. **Open Frappe administration** goes to the same Site's
standard `/app` support Desk. That Desk remains for Site support and identity
setup, not for ordinary LaunchFlow work or a second editable permission master.

The approved ownership is fixed:

- Microsoft Entra owns sign-in and MFA. Configure the supported Office 365
  Social Login Key on the LaunchFlow Site through Frappe's standard
  administration and keep provider secrets outside Git, commands and evidence.
- Frappe owns the authenticated LaunchFlow session. Global self signup and any
  provider-level signup override must be disabled; unknown users receive no
  default access.
- JCE Core owns whether an internal user is enabled plus the approved NPI roles
  and Project/Company/Customer/Supplier scopes. LaunchFlow displays this as an
  external authority and does not provide a permission editor.
- LaunchFlow stores and enforces only the complete, versioned read-only
  authorization projection received through the operation-specific service
  route.

The current V1.2 code requires the target Frappe System User to exist before an
authorization projection is accepted. Automated, idempotent internal-user
provisioning and the ERPNext sender are therefore shown as incomplete and both
authorization switches must remain disabled. Do not use self signup or manual
role duplication as a workaround.

After a separately reviewed provisioning/sender task and version-equivalent
Sandbox tests pass, configure the exact approved non-secret policy before
activation:

```text
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_role_allowlist '<approved-sorted-json-role-array>'
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_max_ttl_seconds '<approved-integer-300-to-86400>'
```

The two activation switches are intentionally independent. Enable ingress
first, backfill and reconcile every approved active user, prove disable/
revocation, stale/conflict and timeout-after-commit behavior, then enable
enforcement last:

```text
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_projection_routes_disabled false
bench --site <launchflow-site> set-config --parse npi_p9_04_authorization_projection_enforced true
```

Rollback sets enforcement to `false` first and closes ingress by setting
`npi_p9_04_authorization_projection_routes_disabled` to `true`. It does not
create local fallback roles, enable signup or delete projection/audit history.
ERPNext business projections and commands remain separately operation-specific;
their production adapters cannot be activated merely because user authorization
is ready.

## Rollout order

1. Freeze the exact SHA and verify ordinary CI plus Level 3 at that SHA.
2. Verify the environment backup and restore plan, storage capacity, key access,
   monitoring and rollback authority before the change window.
3. Set and verify the exact Site `npi_deployment_environment` classification,
   then deploy the independent apps with existing feature/route switches retaining
   their reviewed default states; do not patch Frappe/ERPNext core.
4. Run migrations through the approved environment procedure and verify app/
   schema/config-key fingerprints.
5. Run permission, session, Project, document, Tooling, Trial, integration,
   reporting and Data Exchange smoke checks. HTTP success alone is not external
   execution success; inspect durable Inbox/Outbox/receipt/audit truth.
6. Activate only approved routes/profiles/adapters in dependency order and
   monitor before widening traffic.

## Monitoring and stop conditions

Monitor migration duration and failures, application health, permission
denials, queue depth, Inbox/Outbox lag, retry/DLQ counts, reconciliation drift,
file access errors, database/storage capacity, backup status and stable problem
codes with request/trace IDs. Stop activation when release fingerprints drift,
backup/key access is unverified, migrations fail, permissions widen, durable
state disagrees with HTTP responses, ERP compatibility drifts, or recovery
evidence is incomplete.

Do not improvise a write, generic DocType operation, direct SQL, cross-database
change, replay, production ERPNext customization or permission bypass during
triage. Each requires its separately approved atomic task and evidence.

## Rollback and forward-fix

Rollback authority belongs to the named production change owner. First stop
new activation and preserve immutable audit, command, Inbox/Outbox, export,
archive and receipt history. Restore only the reviewed environment backup using
the approved platform procedure, validate database and both file sets, rerun
smoke checks, and record the exact recovered release identity. Never delete
history or report Mock/HTTP success to conceal a failed external execution.

When schema or retained newer truth makes destructive downgrade unsafe, keep
routes disabled and deploy a reviewed successor exact SHA as a forward-fix.
Run migrations and the same smoke/reconciliation checks again. Any production
restore, migration, adapter activation, ERPNext customization or replay remains
a separate approved operation; this repository rehearsal grants none of those
permissions.
