# P8-07F Current-Worktree and Runtime-Metadata Governance Transition

Date: `2026-08-30`

Task: `P8-07F-CURRENT-RUNTIME-GOVERNANCE`

Status: **PASS — EXACT-SHA ORDINARY AND FINAL LEVEL 3; ZERO PRODUCTION CONTACT**

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

## Migrated-legacy diagnostic result

Product-zero exact SHA `b366b2a7f49d6443aa3f9ebaaec8cdac839a36b2`
passes ordinary `33303116320`: repository `99234782632`, frontend
`99234782634`, visual `99234782659` and secret `99234782690` all pass. Its sole
Level 2 controlled `33303731224` passes preflight `99236455019` and runtime
`99236480700`. The exact-39 success contract emits no safe tuple; no raw or
child output, response content, business value, identity, message or stack was
read.

Freeze the diagnostic cycle at `1/1,0/1,0/1`. All diagnostic activations return
to false. A new exact-SHA ordinary PASS and one diagnostics-off Level 3 remain
mandatory before this governance transition can pass. Production access,
collector expansion and P8-08 remain closed until their later gates.

## Diagnostics-off final Gate

Exact SHA `fccf62feaba2d3ed092efcd06174f16f66193540` passes ordinary CI
`33304191319`: repository `99237696176`, visual `99237696204`, secret
`99237696113` and frontend `99237696206` all pass. Its sole Level 3
`33304710306` passes repository `99239078784`, visual `99239078865`, secret
`99239078878`, frontend `99239078880`, controlled preflight `99240538309` and
cumulative runtime `99240558054`.

Freeze the migrated-legacy cycle at diagnostic `1/1`, repair `0/1`, final
`1/1`. All diagnostic activations are false. The governance transition is now
PASS and made zero SSH, connector, Site or production contact. A separate
`P8-07F-FACTS` collector-expansion exact-SHA ordinary PASS remains mandatory
before any new production read.

## Accepted current-source read and fixed remainder

Collector repair SHA `085e9124328afdb13668de452cd8cba21e282c28`
passes exact-SHA ordinary CI `33307715636`. The following production read uses
the authorized current tracked worktrees, including uncommitted tracked
changes, as current source truth. It accepts sanitized structural/checksum
evidence for the two formerly protected DocType candidates and for fixed
runtime metadata families, then removes the private mode-0600 state. No raw
source, diff, path, Script text, endpoint, principal, credential or business
record is persisted.

The remaining collector boundary is mechanical: the production Frappe v15
Client Script schema has no `script_type`; protected multiline DocType JSON
scalars require checksum-only representation; and exact locale plus aggregate
File URL-shape facts require fixed application-layer operations. The next
collector revision therefore uses only hard-coded `frappe.client.get_value`
and `frappe.client.get_count` calls in addition to the accepted fixed reads.
The user's broader read-only authorization does not require direct SQL,
console or a generic execute surface; those remain prohibited. A new
exact-SHA ordinary PASS is mandatory before the remaining production contact.

## Client Script bounded-page stop

Fixed site-fact collector SHA `573fdd4b61fae2d968933272bd9f9f3e87b2b8c0`
passes ordinary CI `33309768019`. Its discovery confirms the unchanged
accepted platform/app/Site inventory. The first `CLIENT_SCRIPTS` page then
exceeds the existing bounded-output ceiling because the fixed 200-row request
contains Script content. The collector accepts no result, runs no later remote
operation and removes private state.

The fail-closed repair keeps the byte ceiling and every query field/filter/order
unchanged, but fixes Client Script at 20 rows per page with the existing
25-page maximum. All other families remain at 200. Script content remains
checksum/byte-count only. A new exact-SHA ordinary is required before retry.

## Accepted bounded Client Scripts and inventory-bound parent handoff

Exact SHA `e6e28cfc0230e9f22f75f1e9ab02e821f860ced3` passes ordinary
`33310528823` in repository `99254638395`, visual `99254638427`, secret
`99254638459` and frontend `99254638482`. The subsequent read at
`2026-08-30T12:18:59.936275Z` accepts 98 Client Script summaries over five
20-row-bounded pages; Script bodies remain checksum/byte-count only and the
result checksum is
`sha256:49a8951fc934b064368bc1dc22f0def7f766a04901170c79792629b31faf9dbb`.

The same window accepts 27 present frozen DocType summaries with checksum
`sha256:8506387ca0f59657110860127c360d45311038bf4b922ba6552774552e6b3db0`.
`Injection Molding Condition` is explicitly absent. The collector stops before
the first parent read because a fixed allowlist is not evidence that every
allowed document exists on this Site. No later operation runs and private state
is deleted.

The next fail-closed change makes the accepted DocType inventory the only
source of DocField/DocPerm parent names. It rejects any cached nonallowlisted
name and checksum-binds the explicit missing-parent list. It does not broaden
the method, DocType or field surface. Another exact-SHA ordinary PASS is
required before reconnecting; SQL, console, generic execute and all writes
remain prohibited.

## Accepted inventory-bound parents and final Single DocType handoff

Inventory-bound parent SHA
`515de965d3a4e2eb4a6a2dba0be7e05b4dcd9d62` passes ordinary CI
`33311432825` in secret `99257083918`, visual `99257084023`, repository
`99257084057` and frontend `99257084073`. The subsequent bounded read verifies
the unchanged Frappe `15.79.0`, ERPNext `15.77.0`, twenty-app and Site
inventories. It accepts 27 DocField parents with checksum
`sha256:ae102d77b9116b1e81cc21da18f3d6ffd5bdcdbbf379e1fed811681e4979e449`,
120 DocPerm rows with checksum
`sha256:61b485438675708641d5c03c448a9862f70b93f917f2ba4bfb1809c8f7f8a451`,
and File URL shape counts `47376` total, `1632` local public, `45470` local
private and `272` external HTTP with checksum
`sha256:64812dc22706aa9b7886eb9b34e37b80eeeaf9d53da3e1a6c3f527c3fa08a785`.
It also accepts checksum-bound current dirty tracked structural summaries for
Mold, Mold Management Settings, Mold Outsource, Mold Repair and Mold Trial
Report. `Injection Molding Condition` remains the sole explicit missing frozen
DocType. Private state is deleted after the window.

The only unaccepted family is System Settings locale. That operation stops on
an empty object. Exact production Frappe v15 source proves System Settings is a
Single DocType and that `frappe.client.get_value` reads its Singles mapping;
the supplied document-name filter cannot match that mapping. The bounded
repair removes only the filter and retains the fixed method and exact
`language`, `time_zone`, `country` fields. It requires its own exact-SHA
ordinary before the single final read; no accepted family is repeated. SQL,
console, generic execute, sensitive values and all writes remain prohibited.

## Final facts handoff

Exact SHA `77b4258f3b086420e0ae7769bd95830bf9dabfaa` passes ordinary CI
`33312664804`, after which the sole remaining filterless Single DocType locale
read succeeds. The operation accepts only the frozen locale fields and
checksums; private state is removed and no previously accepted family is
re-read. This closes the expanded read authority for P8-07F. The resulting
facts are handed to the consolidated product-zero compatibility checkpoint;
no further production connection is required before its single ordinary and
final Level 3.
