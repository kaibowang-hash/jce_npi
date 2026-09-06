# P9-08 — Final ERPNext–LaunchFlow Read-Only Compatibility Reconciliation

Recorded: `2026-09-03`

Status: `PASS — ALL ACTUAL V1.2 ERP DEPENDENCIES VERIFIED; ASSESSED PRODUCTION DRIFT REQUIRES NO PRODUCT CHANGE`

Requirements: `UX-003`, `INT-001..008`, `INT-010`, `INT-012`,
`FR-INT-015`, `NFR-INT-001`, `NFR-SEC-001`, `NFR-SEC-003`

## Result and authority

The fixed final operation completed at `2026-09-03T09:16:57.085930Z` /
`2026-09-03T16:16:57.085930+07:00` from exact collector SHA
`194733fc72df6fc045727074991eb70acf0aab8f`, after exact-SHA ordinary CI
`33736966780` passed. It used only the standing `JCE-Core` fixed read-only
boundary and the private Site parameter. The Site, endpoint, host, user, key
and any secret are not retained.

The operation performed 268 bounded reads across twenty applications,
nineteen runtime metadata families, two Site fact families, the fixed P9-01
change scope and the fixed P9-04 security scope. It reports
`production_write=false`. The detailed sanitized result was held only in a
mode-0600 operating-system temporary file. Its canonical checksum was
independently recalculated and matched:

`sha256:466520fe71fdd9cb6de4acf5a8cb2eaefbb58df19b6f564e62474c091ca69ddb`.

No SQL, console, arbitrary method, caller-selected DocType/field/filter/path,
file or database write, migration, permission/service/scheduler action,
restart, replay, reconciliation action or production mutation ran. No raw
source diff, Script body, File URL, identity or business record is committed.

## Fresh production inventory

### Platform and current source

- Bench and private Site inventories remain exact matches to the accepted
  P8-07F baseline: Frappe `15.79.0`, ERPNext `15.77.0`, twenty Bench apps and
  eighteen anonymous custom apps. Bench checksum
  `sha256:bc5f2b2653647c21c6cee66e357951831f4e1e512ca9bcb641f8b017fef9b815`;
  Site checksum
  `sha256:cec7d8128c63e6b79bc6fcf9da558378d2c134a9f96a9a5a8b36a585b319c0fd`.
- Eighteen of twenty application HEAD and tracked-path signatures remain
  unchanged. Frappe remains clean and ERPNext retains its previously accepted
  single tracked drift. Thirteen of eighteen custom-app worktrees are now
  dirty, compared with twelve at P8-07F.
- `CUSTOM_APP_08` moved from accepted HEAD `0e77af58…` to `cd0240f4…`, from
  357 to 360 tracked paths and from 2 to 32 tracked drift rows. Current path
  checksum `sha256:80d8661c519d1f7cdb21255f0ec2e16803e8ae886d28ab9b42600cf69530962c`;
  worktree snapshot checksum
  `sha256:9cd85799a78dda83f3785ba3575e7ad468a902f2dd920e64eac510ac1bcd71fb`.
- `CUSTOM_APP_10` keeps HEAD `9572b2bc…` but moves from 53 to 113 tracked
  paths and from 4 to 65 tracked drift rows. Current path checksum
  `sha256:55ab27a0ad836d354713e8b34a3de1c21ac46ec47e8c40c08594df9ebf4555f7`;
  worktree snapshot checksum
  `sha256:87b5da7f0298e4b74f91fcc8dd2cdc02ce2e8d174361bb61a90d5e72874edf88`.
- `CUSTOM_APP_11`, `CUSTOM_APP_12` and `CUSTOM_APP_17` retain their accepted
  HEAD and path inventories but their drift-row counts change respectively
  `5→9`, `0→10` and `2→4`. Their current worktree snapshot checksums are
  `sha256:308402d5b6919ec1122b1ee7909b783e842e83a861ef0dabc696503d60784893`,
  `sha256:589d47e52d2b7e9d6b18d678e4f618d01f7a95d53f0a4ee0b6813027f11e741c`
  and
  `sha256:43a1eb549de0e904503bdcd5798ca42d897012a3dee6393bc103beee8522fd1f`.

These source changes are `PRODUCTION_DRIFT`, but none is an active V1.2
LaunchFlow dependency: every production ERP adapter profile remains disabled,
and no accepted LaunchFlow contract names or trusts an anonymous custom-app
method. The complete current signatures become the new freshness baseline.
Any later adapter activation must inspect and lock its one exact
operation-specific method in a separate atomic Sandbox task; it may not infer
compatibility from HEAD or introduce a generic writer. This resolves the drift
for implementation closeout without accepting the dirty trees as clean
releases.

### Runtime metadata

| Family | Rows | Current sanitized checksum |
|---|---:|---|
| Custom Field | 840 | `sha256:fbbc9e08b59129e90572357bf075a6e3ce7fdc25a5df9d518212b62c31d474d8` |
| Property Setter | 630 | `sha256:4f57c81a0af09ac06c7b6c13070fa4d633e579b1d20a794f99bbceda78923521` |
| Workflow | 16 | `sha256:b35a7b23ff464f000b9bfb5a8bbfff23a2459e601e632e0ff0048becb9fedb05` |
| Workflow State | 103 | `sha256:a467bdf082afe58e85ed66858653bb4447d0c7d9d36a2d1e363330919fc96f4e` |
| Workflow Transition | 135 | `sha256:fa1e5eab62b91d8fd90b47f03f0f47eeef72a80e76444ac72debba3ef9612684` |
| Role | 74 | `sha256:f8024e7316d2fb85ab4440dc2701d456e237faba8b765353a4d205d2cf6d181d` |
| Custom DocPerm | 1,166 | `sha256:176853f898a59f708196097ce11ffef7a2608b2373c4acdee30b8c377adcaa4b` |
| Client Script | 100 | `sha256:9f413c0ccb11ce8890a74fa051e63c6862ec3da6d8250878197f4bf5e624b159` |
| Server Script | 48 | `sha256:055b7f37fbc48e2aa8f0aff37e71ad41bfc5e9ea4357eb4461cbb5b284cc7cfa` |
| Required DocType | 27 | `sha256:8506387ca0f59657110860127c360d45311038bf4b922ba6552774552e6b3db0` |
| Required DocField | 1,397 | `sha256:ae102d77b9116b1e81cc21da18f3d6ffd5bdcdbbf379e1fed811681e4979e449` |
| Required DocPerm | 120 | `sha256:61b485438675708641d5c03c448a9862f70b93f917f2ba4bfb1809c8f7f8a451` |
| Webhook | 15 | `sha256:e5311f8a97ac7a19c6d15ea417b0cad4b3f0a516bf020e3e6f3327bd9d803bd0` |
| Scheduled Job Type | 110 | `sha256:52246a84d1ba8727bb991ea999779f9ba7cc1c1a8974ff18092c0c70955a1d21` |
| Report | 257 | `sha256:00e664f88ffed2108a5814845ee3d3e758d415354c9379df861a072fee40d9c1` |
| Print Format | 118 | `sha256:cb14de4fe9ac4b5a39e1e05139aebfea1b293cd3e33c7056dcec5aeed0ff85e5` |
| Notification | 6 | `sha256:091d7c8a3029f935ef76af21734de04748e0bb472b97b027f1fdd51e61ecc236` |
| Document Naming Rule | 33 | `sha256:9639e457d0bfc33309c2f0d52fc0997cf8ae05ae8dd78f44103593c7d3a1d9be` |
| Naming Rule Condition | 33 | `sha256:a04c9bcf152ec814b46f113c110852c8b078bd408c7d8f35f578e1244fb912df` |

The required DocType, DocField and DocPerm checksums are unchanged. The
previously absent optional `Injection Molding Condition` remains outside the
27 present required-object rows and remains non-blocking.

Runtime metadata changed after the P8-07F baseline. The bounded comparison
finds two new/modified Client Scripts, both for Employee and outside the frozen
NPI object scope. No recently modified Custom Field, Server Script, Webhook,
Report or Naming Rule targets a required NPI object. Relevant changes are
additive Property Setters on Asset and Quality Inspection Template, active
Workflow revisions for Approval Form, DMR, Engineering Change Request, Mold
Alteration, Mold Repair and Quality Inspection Template, and Print Formats for
DMR/ECR. They do not remove a required field, change an ownership boundary or
create an NPI command target. LaunchFlow continues to store raw ERP codes and
never drives those Workflows. This is assessed `PRODUCTION_DRIFT` with
`NO_CHANGE` on the LaunchFlow side.

### Locale, files, change and authorization

- Locale is `STILL_MATCHES`: the accepted country, system language and timezone
  are unchanged. Checksum
  `sha256:cc94b21fbc7a0556244ef71b117359ab7ee38022e8b32e5999d5b417fdcbe355`.
- File URL categories are unchanged, while aggregate volume moves from 47,376
  to 48,752 rows: local public `1,632→1,647`, local private
  `45,470→46,829`, external HTTP `272→274`, with two rows still outside those
  three fixed categories. This is compatible `PRODUCTION_DRIFT`; LaunchFlow
  already preserves private/local/external shape rather than trusting a URL or
  copying file bytes. Current checksum
  `sha256:98898dad738514fb8623a5572910a4a51b286b258f14c1d8c64cd726367ff17f`.
- P9-01 current change result checksum is
  `sha256:cffa755cf5955e20f905b101d88863985dcd9c96b23fc540e380011dc20b85e6`.
  ECR remains the sole present formal change master; ECO and ECN remain absent;
  all 53 fields and five permissions are unchanged. The active ECR Workflow
  was modified on 2026-09-02, but retains Draft, Impact Review, Pending
  Validation, Pending Approval, Approved, Implementing, Effective, Closed and
  Cancelled with the same forward/revision paths. Additional editable-role
  rows do not alter LaunchFlow ownership. `track_changes=0` and self approval
  remain the already recorded production-activation hardening gap, not a new
  implementation incompatibility.
- P9-04 authorization is an exact `STILL_MATCHES` at
  `sha256:0919d57016166b07899a3a0648ef975755413027e6e2d29606720308df84afb8`:
  28 aggregate System Users, 21 enabled and 7 disabled; 14 aggregate User
  Permissions, of which 7 are Company and none are Project, Customer or
  Supplier; six Role Profiles; two enabled federated-login providers; self
  signup disabled. Identity and provider-secret fields remain excluded.

## Capability reconciliation

`STILL_MATCHES` means the current production fact and the approved LaunchFlow
implementation remain compatible. A `PRODUCTION_DRIFT` row below is closed
only where the current evidence proves that the changed fact is additive,
shape-only or not consumed by an active adapter. No row is
`LAUNCHFLOW_DRIFT`, `BOTH_DRIFTED` or `UNVERIFIED` for an actual V1.2 ERP
dependency.

| Capability | ERPNext current fact and owner | LaunchFlow current implementation and owner | Result | Impact, minimum remediation, tests and rollback |
|---|---|---|---|---|
| P8-01 projections / `INT-001`, `INT-006`, `INT-010` | ERP owns Customer, Supplier, Item, PO/cost, Quality Inspection/DMR and Asset/Mold formal truth. Required object/field/permission checksums are unchanged. | NPI owns immutable `npi.erp-projection.v1` observation/head truth, source version/time/hash and unavailable/stale/conflict states. | `STILL_MATCHES` | `NO_CHANGE`. Keep fixed read maps and least-privilege profile default-disabled until Sandbox. Existing normal/empty/permission/pagination/order/stale/hash tests remain applicable; rollback disables the reader and retains observations. |
| P8-02 signed Project ingress / `INT-002` | ERP owns submitted Quotation/Sales Order source and configured event. No recent required-object Webhook or Server Script change creates a conflicting NPI event. | NPI owns the fixed signed endpoint, raw-body verification, Inbox-first receipt and one Project draft. | `STILL_MATCHES` | `NO_CHANGE`. Configure exact source states/signing in Sandbox; use the previously approved independent-app emitter only if configuration cannot sign/version/idempotently identify the event. Signature, duplicate, reorder, restart and timeout tests remain mandatory; rollback disables the sender. |
| P8-03 Item publish / `INT-003` | ERP owns Item identity, UOM/group/naming and target version; Item schema/permission facts are unchanged. | NPI owns released source/hash, request/Outbox/attempt/result/mapping and uncertain timeout truth. | `STILL_MATCHES` | `NO_CHANGE`. Supply a versioned map and operation-specific actor in Sandbox. Validation, missing map, duplicate, CAS conflict, partial, timeout-after-commit and reconciliation tests remain; rollback disables the profile. |
| P8-04 MBOM publish / `INT-004` | ERP owns BOM, routing/operation and submitted manufacturing truth; BOM/Item/Work Order/Job Card schema remains present and unchanged. | NPI owns released topology, authenticated Item mappings, immutable nodes and per-node results. | `STILL_MATCHES` | `NO_CHANGE`. Configure exact node/UOM/routing maps; add the already bounded custom-app operation only if direct APIs fail Sandbox. Submitted BOM is never overwritten; rollback disables publish. |
| P8-05 Tool Asset / `INT-005` | ERP owns Asset/Mold, movement, maintenance, repair, spares, location and shot truth. Asset Property Setters and Mold workflows changed additively; required fields remain unchanged. | NPI owns immutable Tooling acceptance request/evidence and a zero-or-one Tooling Set mapping; P8-01 remains the sole status projection owner. | `PRODUCTION_DRIFT` — assessed compatible | `NO_CHANGE`. Refresh the Asset/Mold map against current Property Setters in Sandbox and keep separate create/update scopes. Test zero-or-one, movement/repair, stale projection, partial and timeout; rollback disables command and reader profiles. |
| P8-06 formal quality reference / `INT-007` | ERP owns Quality Inspection/DMR identity, raw status/result and lifecycle. DMR/quality-template Workflow and print changes are production-owned; core fields and permissions are unchanged. | NPI owns only the immutable current-observation reference and raw-code display; it never asserts quality pass or drives ERP Workflow. | `PRODUCTION_DRIFT` — assessed compatible | `NO_CHANGE`. Owner approves the raw reference/status map in Sandbox. Existing current/drifted/unavailable, invalid-type, tamper, permission and rollback tests remain; no ERP writer is introduced. |
| P8-07 operations / `FR-RP-009`, `UX-016` | ERP target semantics remain operation-specific. Current job/Webhook/script/permission families are fully checksum-bound; no active NPI target is assumed. | NPI owns immutable request/attempt/result, logical DLQ, exact retry eligibility and read-only reconciliation intent. | `STILL_MATCHES` | `NO_CHANGE`. Anonymous app source drift cannot become a target implicitly. Lock one exact method and actor only in the later activation task; test 4xx/429/5xx, uncertainty, duplicate, replay and cross-Project denial; rollback disables the profile. |
| P8-08 Released Trial Summary / `FR-INT-015` | ERP owns Mold Trial Report corroborating fields; required schema remains unchanged. | NPI owns the immutable Released Trial Summary, presentation/redaction hashes and the existing read-only projection seam with explicit unavailable state. | `STILL_MATCHES` | `NO_CHANGE`. Keep the fixed permission-safe Mold Trial Report map; test empty/permission/redaction/stale/conflict/timeout and source removal. Rollback disables the reader; the immutable NPI summary remains. |
| P8-09 JCE Core identity / `FR-BR-002` | ERP business ownership is unchanged; display identity does not alter an ERP field or method. | NPI displays approved JCE Core identity only in presentation contexts while technical contract/event code stays `ERPNEXT`. | `STILL_MATCHES` | `NO_CHANGE`. Existing asset/hash/accessibility/i18n scans apply. Rollback removes only the display adapter. |
| P9-01 change control / `INT-008`, `FR-CH-001..010` | ERP ECR fields/permissions remain stable; its Workflow was edited but retains the accepted state/effectivity model. ERP still owns formal number/raw state/effective truth. | NPI owns the Project-scoped immutable change revision, impacts, linked work/evidence, readiness and source-labelled ERP observation. | `PRODUCTION_DRIFT` — assessed compatible | `NO_CHANGE`. Refresh the raw state/role map in Sandbox. Before production activation, separately enable ERP change tracking, disable self approval and approve a service scope. Test reordered/duplicate/stale/permission/timeout and Workflow drift; rollback disables the adapter, never drives ERP state. |
| P9-04 authorization / `INT-012`, `NFR-SEC-001`, `NFR-SEC-003` | Entra owns authentication/MFA; ERP owns editable enabled-user, role/profile and scope truth. Aggregate checksum is unchanged. | NPI owns Frappe session/domain authorization plus the default-disabled full-replacement ERP authorization projection with fail-closed unknown/stale/unmapped behavior. | `STILL_MATCHES` | `NO_CHANGE`. Project/Customer/Supplier mapping, NPI role profile, identity key and service actor remain a separate owner/Sandbox activation input. Existing exact replacement, revoke, escalation, replay, stale/conflict and rollback tests apply. |
| P9-02/03/05/06/07/08 closeout | No new production ERP writer or data owner is introduced by collaboration, reporting, recovery evidence or controlled technical UAT. | Existing Project/portfolio/export/notification/recovery domains and P9-08 evidence remain within approved NPI ownership. | `STILL_MATCHES` | `NO_CHANGE`. AT-01/AT-02 remain controlled non-production evidence only. M9-04/M9-05 real pilots remain post-V1.2; rollback follows each accepted task's existing evidence. |

## Drift and decision register

| ID | Finding | Resolution | Owner / future trigger |
|---|---|---|---|
| `P9-08-DRIFT-01` | Five anonymous custom-app worktree drift counts changed; one HEAD and two path inventories changed. | `PRODUCTION_DRIFT`, closed for current implementation because no enabled LaunchFlow profile consumes an anonymous method. Adopt the current signatures as freshness evidence; do not call them clean releases. | ERP owner; inspect one exact method only when a separately approved adapter-activation task names it. |
| `P9-08-DRIFT-02` | Runtime metadata was updated, including Employee scripts and additive Asset/quality/change workflow/print configuration. | `PRODUCTION_DRIFT`, closed as compatible: required DocType/DocField/DocPerm identities remain exact, recent scripts/webhooks do not target a required NPI object, and LaunchFlow consumes raw states without driving ERP Workflows. | ERP configuration owner; revalidate exact map in version-equivalent Sandbox before profile enablement. |
| `P9-08-DRIFT-03` | File-row counts increased while URL-shape categories stayed stable. | `PRODUCTION_DRIFT`, closed as volume-only. Current adapter rules already distinguish private/local/external references and never copy by assumption. | File-policy owner; monitor category distribution, not business URLs. |
| `P9-08-HOLD-01` | ECR change tracking remains disabled and Workflow self approval remains enabled. | Existing production-activation hold, not LaunchFlow drift. No production change in P9-08. | Quality/change owner; separate smallest configuration/custom-app task before enabling the P9-01 production adapter. |
| `P9-08-HOLD-02` | Exact NPI service actor/role profile and Project/Customer/Supplier permission-source mapping are not configured as active V1.2 production dependencies. | Existing production-activation hold. Default-disabled profiles and fail-closed authorization mean there is no unverified active dependency. | Security/ERP owner; separate mapping and Sandbox/UAT task before enablement. |

No concrete incompatibility justifies a LaunchFlow adjustment task. No ADR or
business decision is newly required for implementation closeout. A future
activation task may be created only after it names one exact missing mapping or
operation and proves configuration alone cannot satisfy the approved contract.

## No-change boundary and final verdict

- Do not modify ERPNext/Frappe core, use cross-database writes, expose a generic
  DocType writer, let the browser call ERP, create dual-master fields or treat
  Mock/HTTP success as target success.
- Do not redesign, rename or generalize the approved LaunchFlow architecture,
  domains, ownership, OpenAPI/event contracts, workflows, roles or technology.
- No production ERP modification, migration, role change, service action,
  Workflow action, replay or adapter enablement is authorized by this evidence.
- All actual V1.2 ERP dependencies are current and compatible. Assessed
  production drift has explicit evidence, owner, impact and forward action;
  there is no unresolved `UNVERIFIED`, `LAUNCHFLOW_DRIFT` or `BOTH_DRIFTED`
  dependency.
- This evidence was the accepted input to P9-08's final exact-SHA ordinary CI
  and diagnostics-off Level 3/release-gate. Those gates permit technical
  `IMPLEMENTATION_COMPLETE`; they do not claim a real pilot, real-user adoption
  or production adapter activation.

## Final gate binding

Final product/evidence SHA
`67290c57c6fde24883f6b069e06ae45a6af7bcb5` passes exact-SHA ordinary CI
`33741955643` and diagnostics-off Level 3 `33742476664`. Controlled runtime
`100608924712` and cleanup pass with `productionContact=false`; release-gate is
PASS. The compatibility verdict above therefore closes the mandatory V1.2
implementation reconciliation without a LaunchFlow or ERPNext product change.
Production adapter activation and every listed hardening/owner input remain
separately held.
