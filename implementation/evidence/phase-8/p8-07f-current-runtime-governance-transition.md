# P8-07F Current-Worktree and Runtime-Metadata Governance Transition

Date: `2026-08-30`

Task: `P8-07F-CURRENT-RUNTIME-GOVERNANCE`

Status: **LEVEL 3 BLOCKED AT MIGRATED-LEGACY; EXACT-39 DIAGNOSTIC PENDING; ZERO PRODUCTION CONTACT**

## Authorization received

The user explicitly expanded the standing P8-07F read-only authorization on
2026-08-30. The next facts epoch may, after this transition and a separate
facts activation pass their required Gates:

1. treat the current tracked production worktree, including uncommitted
   tracked changes, as candidate current source truth instead of assuming Git
   `HEAD` equals the running code;
2. read and structurally summarize the two relevant DocType candidates that
   previously stopped at sensitive-content preflight, without changing them or
   persisting raw or sensitive content; and
3. collect the exact runtime metadata needed for Custom Fields, Property
   Setters, Workflows, roles and permissions, Client/Server Scripts, Naming
   Series and other already-approved P8-01 through P8-09 compatibility facts.

This authorization resumes the work from the old external-evidence hold. It is
not production modification authority and is not permission to redesign the
LaunchFlow integration.

## Mandatory sequencing

1. This governance transition changes repository governance only. It performs
   zero SSH, Site, ERP connector, production request or other external-state
   action.
2. The transition must be committed as an exact manifest and obtain exact-SHA
   ordinary CI plus Level 3 PASS.
3. The controller must then activate a separate `P8-07F-FACTS` collector
   expansion commit. That commit must freeze implementation and tests for every
   new operation and obtain its own exact-SHA ordinary CI PASS.
4. Only the separately activated facts task may reconnect through `JCE-Core`.
   P8-08 remains inactive until the facts reconciliation and its Level 3 pass.

## Frozen source-current operation

The next collector may add one operation-specific current-worktree source
operation. It must use only the already accepted fixed `frappe-bench` root and
an allowlisted app/path previously returned by the tracked-path inventory. The
remote operation must derive a bounded, no-renames, no-external-diff textual
delta from `HEAD` for that exact tracked path and reconstruct the current file
in local private memory. It must reject symlinks, binary patches, path changes,
deletes, multiple-file patches, truncated context, malformed hunks, excessive
bytes or any path/shape mismatch. Clean paths continue to use the accepted
immutable `HEAD` object.

Only a structural summary and checksums may leave private state. Raw diff,
source, literals, path identities, business values and sensitive values must
not be written to Git. The two previously stopped DocType candidates are
eligible only for the same structural summarizer and redaction contract; user
authorization does not permit product-file mutation or raw persistence.

## Frozen runtime-metadata operation family

The next collector may add fixed application-layer read operations for exact
metadata families required by the compatibility matrix. Every operation must
hardcode the DocType, safe field projection, filters, ordering, deterministic
page size, maximum pages, result shape and maximum bytes. Caller-supplied
methods, DocTypes, fields, filters, order, pagination or arbitrary code are
forbidden.

Allowed fact families are limited to non-business metadata required by the
current P8-01 through P8-09 contracts:

- DocType/DocField/DocPerm structure and safe checksums;
- Custom Field and Property Setter definitions;
- Workflow, Workflow State and Workflow Transition structure;
- roles, custom permissions and service-scope structure without principals,
  credentials or secret values;
- Client Script and Server Script structure/checksum without script text;
- Naming Series structure without generated business identifiers;
- Webhook, Scheduled Job Type, Report, Print Format and Notification structure
  without endpoints, headers, credentials, message bodies or business rows;
- non-sensitive system locale/storage-type facts already required by the
  inventory.

The implementation must use only a fixed Frappe application-layer read call on
the user-confirmed Site. Direct SQL, `bench console`, export-fixtures, generic
DocType access and arbitrary `bench execute` methods remain prohibited. If the
chosen fixed framework read path has an implicit empty commit, tests and the
activation evidence must prove that no document mutation, hook execution,
enqueue, scheduler, outbound network or nonzero write can occur. Otherwise the
operation is not admissible.

## Transport, evidence and stop rules

The accepted SSH transport remains unchanged: alias `JCE-Core`, `BatchMode`,
strict host-key verification, no TTY, no forwarding, no agent forwarding, one
short connection and bounded whole-command timeout. Each accepted record must
contain task ID, purpose, UTC/local timestamp, operation ID, sanitized source
label, version/mtime/hash/checksum, finding, unknown and compatibility impact.

Stop the affected area immediately on permission failure, version drift,
unknown output shape, pagination/order instability, allowlist/path drift,
possible sensitive value, excessive output or any need for a write. Do not use
`sudo`, direct SQL, console, file/config/core/permission/service/queue changes,
migrate/update/restart/reload/clear-cache/scheduler, DocType mutation,
webhook/job/adapter/target commands, replay or reconciliation actions.

## Compatibility and non-scope

The approved LaunchFlow architecture, ownership, OpenAPI/event contracts and
P8-01 through P8-09 design/code remain the default-correct baseline. Results
use only `DIRECT_MATCH`, `CONFIG_OR_MAPPING_ONLY`,
`MINOR_LAUNCHFLOW_ADJUSTMENT`, `MINOR_ERPNEXT_CUSTOM_APP_ADJUSTMENT`,
`BUSINESS_DECISION_REQUIRED` or `NOT_APPLICABLE`. No proven difference means
`DIRECT_MATCH` and `NO_CHANGE`.

This transition implements no collector, product, contract, schema, metadata,
permission, configuration, ERP customization, compatibility adjustment, P8-08
or P8-09 change. M9-04 and M9-05 remain
`USER_APPROVED_POST_V1_2_DEFERRED`; controlled non-production UAT remains and
no real-pilot or real-user adoption claim is created.

## Gate and rollback

The exact transition requires Level 1 governance checks, exact-SHA ordinary CI
and one Level 3 Gate. Before the separate facts activation passes, rollback is
reverting only this transition while retaining all accepted prior P8-07F
evidence and keeping production contact/P8-08 inactive. After a future
read-only operation, rollback is to stop, delete private state, retain only
already-redacted accepted provenance and mark affected facts stale or
unverified. No remote rollback command exists because no remote mutation is
authorized.

## First Level 3 result and migrated-legacy diagnostic handoff

Exact transition SHA `6aa9f9b6db338d20713a2ccece84fb59a0284450`
passes ordinary `33301387305` in all four lanes. Level 3 `33302018921` passes
visual `99231830409`, repository `99231830472`, secret `99231830495`, frontend
`99231830504` and controlled preflight `99233030654`. Runtime
`99233052613` initializes the fixed disposable Bench/Site and fails only in
cumulative verification; cleanup passes.

Fixed-label filtering yields exactly
`Local Frappe Item publish migrated-legacy runtime verification failed.` No
raw/child output, response content, business value, identity, message or stack
was read. The transition product/contract/schema/workflow diff is zero, but a
failed Level 3 cannot be waived.

Open one product-zero diagnostic subcycle at `0/1,0/1,0/1`. It reuses the
existing collection-fallback activation and exact 39 outer/collection/server
safe codes. One new exact-SHA ordinary PASS must precede one Level 2 controlled
run. A failed run may expose only one strict code/type/exact-trace tuple; a
successful run emits zero diagnostic records. No repair, production read or
P8-08 activation is authorized without the required proof and later final
Level 3 PASS.
