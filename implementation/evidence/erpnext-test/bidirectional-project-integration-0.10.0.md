# ERPNext-test Bidirectional Project Integration 0.10.0

Date: 2026-09-06 (Asia/Bangkok)

Status: **READY FOR TEST TRIAL — PRODUCTION ERPNext NOT ACTIVATED**

LaunchFlow Site: launchflow.whjichen.cn

ERPNext test Site: jce.1 at test.core.whjichen.cn

Product release: 3fd0f084d8d63549affbecd2b1b8ccc07107e4c3

Connector release: 0.10.0

Pull request: #6

The production ERPNext alias JCE-Core was not contacted or modified.

## Delivered boundary

- ERPNext-test remains authoritative for users, roles, User Permissions,
  Customer, Supplier, Item Group, Item, formal Project identity and formal
  manufacturing execution. Microsoft Entra remains the separately configured
  authentication and MFA authority.
- ERPNext-test continues to send Project source events, complete user
  authorization replacements and four ERP-owned master-data catalogs to NPI
  One.
- An NPI-created Project now sends one signed, operation-specific command to
  ERPNext-test. ERPNext assigns the formal Project ID and returns it to the NPI
  request, result and Project view.
- The NPI business actor becomes the ERPNext Project owner; the existing
  least-privilege integration user remains only the transport identity.
- Request, attempt, result, mapping and receipt records are durable. Exact
  replay, uncertain-result reconciliation and loop suppression are active.
- A newly bound Project inherits the already-approved test profiles for Item,
  MBOM, Tool Asset, released Trial Summary and Engineering Change. This does
  not make ERP-owned fields dual-master.

## Build and release gates

- Exact product SHA ordinary CI 34026885838: PASS.
- Exact product SHA diagnostics-off Level 3 34026883237: PASS, including
  repository, secret scan, frontend, both browser E2E shards, governed visual
  matrix, controlled preflight and cumulative disposable Frappe runtime.
- Local repository verification passed 3173/3173 checks.
- Frontend verification passed 1174/1174 tests, 475/475 browser E2E cases,
  9502 English source entries with complete zh and zh-TW catalogs, and 102/102
  fixed-Linux visual cases.
- The connector installed and migrated twice on a disposable ERPNext
  15.121.0 / Frappe 15.120.0 Site. All 15 connector-owned DocTypes were present
  after both migrations.

## Immutable artifacts and backups

- Connector artifact npi-erpnext-connector-0.10.0.tar.gz has SHA-256
  c347482dfb3738f3373a22af6be189beb97eb1938ac94cf2d05c770afc66e44c.
- LaunchFlow backend image has digest
  sha256:4f8f8befb2892670dc84b5405bafa6fe4b8b61d716a9ee57b5bce2d913c92f61.
- LaunchFlow SPA image has digest
  sha256:0bcf1a7b6ae31e40d27ada3a7fbea955c7e9dfe3babb50c40565065435f77c55.
- Both image revision labels equal the exact product release SHA.
- LaunchFlow encrypted full backup
  launchflow-launchflow.whjichen.cn-20260906T100107Z.tar.gpg has SHA-256
  6033c53730c2e6c76a0ebe1d762f141bf93d5c65b54b2467063dbef5d15de6ef.
- ERPNext-test database backup
  20260906_180107-jce_1-database.sql.gz has SHA-256
  7cd68310db4cbe658db217a9349ffdc0a927bdcd2232ea3c4014df68f0e83fc8.
- ERPNext-test public/private file backups have SHA-256
  a6f3830070ab2f739e739cf8c09175c5f399f5b67bd4dfa25bbac259531a7414
  and
  831fd8b34d798baed38a291f6c45345ed6a41480dba4b83cfa4191eb4f882dd2.
- Root-only environment/Site configuration copies and the previous connector
  source tree were retained. The previous LaunchFlow release and exact image
  pair remain available for code rollback without a schema downgrade.

## Deployment result

- ERPNext-test runs ERPNext 16.14.0, Frappe 16.16.0 and connector 0.10.0. The
  additive v0_10.sync_project_publish_schema patch completed, both new Project
  publish support DocTypes migrated, the test-only receiver profile is enabled,
  all Supervisor services are RUNNING, and the public ping returns pong.
- LaunchFlow migrated the additive v0_4.sync_project_publish_schema patch and
  switched both images to the exact product release. All ten required services
  are healthy, scheduler status and the public health contract pass.
- During deployment, Frappe v16 required the Python literal True for
  bench set-config --parse; the rejected lowercase value made no setting
  change. LaunchFlow Compose health intentionally stayed pending while Frappe
  maintenance mode returned HTTP 503. Maintenance mode was then disabled
  before the unchanged health gate; no rollback or data repair was required.

## Live bidirectional exchange

Existing ERPNext-to-NPI direction remains bound:

| ERPNext Project | NPI Project global ID | State |
| --- | --- | --- |
| PROJ-0027 | 0f7af44c-3859-58e4-83e2-d484dcae6941 | bound |
| PROJ-0028 | 503e9075-c77b-5e16-b7b3-5375ce410ee6 | bound |

The existing user-created NPI Project was used for the opposite direction; no
filler Project was created:

| Fact | Verified value |
| --- | --- |
| NPI business code | MM-35029 |
| NPI Project global ID | 37ecca80-dc03-53eb-8412-c68427f5a3e6 |
| NPI actor | kaibo_wang@whjichen.cn |
| NPI request | 3cb844cf-966f-47a2-94b6-0af6ecc63258 |
| NPI terminal state | succeeded, attempt 1 |
| ERPNext formal Project | PROJ-0030 |
| ERPNext owner | kaibo_wang@whjichen.cn |
| Transport user | npi-item-integration@erpnext-test.invalid |
| Company | Jichen (Thailand) Co., Ltd |

ERPNext retained exactly one mapping and one receipt for the request. A live
signed replay returned HTTP 200 with authenticated and contract-valid results,
exact_replay=true and the same formal Project ID. A separate live signed
uncertain-result reconciliation returned HTTP 200 with authenticated and
contract-valid results, found=true and the same formal Project ID. The ERP
Project still exists exactly once.

The ERP-origin Project sender has no delivery row for PROJ-0030, proving the
NPI-origin mapping suppresses the reverse loop. Its two existing deliveries for
PROJ-0027 and PROJ-0028 remain succeeded.

All five inherited downstream profiles resolve for the new NPI Project: Item,
MBOM, Tool Asset, Trial Summary and Engineering Change. Each binds the exact
new Project identity and validates a non-production target.

## User, permission and master-data result

- The canonical user authorization projection is enabled, source version 19,
  with the ERP-owned role and Project-scope replacement applied at
  2026-09-06 10:40:02Z. No user or role was edited in NPI One.
- ERPNext-test master-data deliveries are delivered with no error: Customer 13,
  Supplier 35, Item Group 24 and Item 816, all at source version 10.
- The NPI connection endpoint reports environment test, state connected, and
  all five capabilities true: authorization synchronization, Item commands,
  Project synchronization, master-data synchronization and reporting
  synchronization.
- Portfolio and Project pages now show the independent Project binding and
  formal ERPNext ID. A Project may still truthfully show “no ERP fact
  observations yet” until formal downstream ERP reporting observations exist.
  Empty Tooling, Trial or change tables mean those business objects have not
  yet been entered; they are not used to fake a connection failure.

## Rollback and remaining production hold

Rollback first disables the NPI Project sender and ERPNext-test receiver, then
preserves all request, mapping and receipt evidence. The previous connector
tree and root-only configuration copy can be restored, and the previous
LaunchFlow image pair/release pointer can be selected without a schema
downgrade. The new additive
support DocTypes and retained history must not be deleted.

This result is ready for controlled test trial against ERPNext-test. It is not
authorization to connect to or modify production ERPNext. Production readiness
remains false until the separate production activation, owner-approved mappings
and production-change readiness gates are satisfied.
