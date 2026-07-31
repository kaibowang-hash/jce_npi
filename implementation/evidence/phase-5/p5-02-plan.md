# P5-02 Plan — Review and Release Workflow

Planned: `2026-07-31T07:19:37Z`

Starting remote checkpoint:
`7b145de8805178b638a58f9e12cba32ba4dfc388`

Task state:
**IN PROGRESS — REQUIREMENT/DOMAIN AUDIT PASS; IMPLEMENTATION READY**

Applicable requirements:

- `FR-DS-002`;
- `FR-DS-005`; and
- `FR-DS-010`.

Applicable Skills:

- `npi-domain-guard`;
- `frappe-safe-change`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Audit result

The bounded comparison of the exact Phase 5 anchor, the three indexed
Requirement rows, the P5-01 domain/DocTypes/repository/BFF/OpenAPI/frontend,
`contracts/data-ownership.yaml`, the current File Revision controller and the
retained P5-01 Level 2 evidence found one safe additive path.

P5-02 can append review and release behavior without changing the P5-01
revision snapshot, file association, lock history, retrieval rules or
transaction semantics:

1. keep the original `NPI Document Revision` and
   `NPI Document Revision File` rows immutable;
2. introduce one exact, separately versioned review/release policy whose
   published snapshot freezes explicit user bindings and supported rules;
3. append immutable review-cycle, confirmation and lifecycle-event records;
4. maintain a separately guarded lifecycle projection for the current
   controlled state and optimistic version;
5. derive the workspace state and capabilities from those records, never from
   Project ownership, RACI, `System Manager`, `NPI API User`, edit locks or
   browser visibility;
6. release only after revalidating the exact live private File identity,
   observed metadata, SHA-256 and scanner-owned `clean` state; and
7. block deletion of a released binary at the server-side Frappe `File`
   `on_trash` boundary.

No architecture ADR is required. This uses the approved independent Frappe
App, BFF command, immutable history, explicit policy and hook-extension
architecture. It patches no Frappe core, introduces no direct SQL, new
dependency, cross-database write, production integration or broad permission.

## 2. Scope

P5-02 delivers one Project-scoped vertical slice over one exact P5-01
controlled document revision:

> select an exact published synthetic review/release policy → submit a draft
> revision for review → record exact assigned reviewer approvals or rejection
> as authenticated electronic confirmations → resubmit a rejected revision in
> a new immutable cycle → reach approved only under the frozen policy count →
> release only by an exact release authority after live integrity/security
> revalidation → optionally supersede it with an exact later released revision
> or mark it obsolete through separately bound authority → inspect the complete
> immutable history

The controlled state family is exactly:

`draft → in_review → approved → released → superseded | obsolete`

A rejection returns the projection to `draft`; it does not add an unapproved
`rejected` contract state. The rejected confirmation and closed cycle remain
in immutable history, and resubmission always creates a new cycle.

## 3. Frozen non-scope and Class-B holds

P5-02 does not:

- infer or install production submitters, reviewers, approval counts, release,
  supersede or obsolete authorities;
- claim a regulated/legal digital-signature strength, reauthentication method
  or certificate-backed signature;
- infer production major/minor, effectivity, replacement, retention,
  watermark, download or archive policy;
- configure a production scanner, viewer, storage provider, CAD/PDM provider,
  external access policy or ERPNext endpoint;
- baseline released revisions or invalidate dependencies (`P5-03`);
- create EBOM revisions or comparisons (`P5-04`);
- create Item/MBOM publish requests or claim ERP execution (`P5-05`/Phase 8);
- change title, confidentiality, revision bytes, file association, revision
  reason/effectivity, predecessor, lock history or a released record in place;
  or
- authorize review/release from Project owner, Project membership, RACI,
  `System Manager`, `NPI API User`, lock ownership, assignment or UI state.

Production authority, quorum, delegation, signature/reauthentication,
retention and scanner-provider choices remain Class-B holds. They do not block
the safe generic mechanism because no production policy is installed and every
accepted test/runtime policy is visibly synthetic, explicit and immutable.

## 4. Domain and persistence design

### 4.1 Existing immutable identities

- `ControlledDocument` remains the stable Project-scoped identity and current
  draft-revision pointer from P5-01.
- `DocumentRevision` remains the immutable creation snapshot, including exact
  major/minor, predecessor, reason/effectivity, P5-01 document policy, lock
  reference and file association. Its creation-time `state` remains `draft`;
  P5-02 never rewrites that snapshot to simulate lifecycle history.
- `DocumentRevisionFile` remains the immutable association to the exact
  private File Revision metadata observed at upload.
- `NPI File Revision` remains the exact file/evidence projection. Scanner
  observation may advance through its existing guarded scanner boundary.
  P5-02 may set `released` from `0` to `1` once through the existing controlled
  file-write boundary, only after `clean` and live-integrity checks. It can
  never return to `0`.
- Edit locks remain overwrite prevention only. No review/release capability is
  derived from a lock.

### 4.2 New versioned policy

`NPI Document Release Policy` is an administrative Project-scoped root.
`NPI Document Release Policy Version` is publish-once and immutable. Its
canonical snapshot freezes:

- policy/root/version identity and Project/tenant;
- exact `submitterUserIds`;
- exact reviewer slots `{slotKey, userId}` and
  `requiredApprovalCount`;
- exact `releaseAuthorityUserIds`;
- exact `supersedeAuthorityUserIds`;
- exact `obsoleteAuthorityUserIds`;
- `confirmationMethod = authenticated_session_confirmation`;
- `requiredScanState = clean`;
- `requireLivePrivateIdentity = true`;
- `requireSha256Match = true`;
- `supersedeRequiresReleasedSuccessor = true`;
- `supersedeRequiresLaterRevision = true`; and
- `supersedeRequiresSuccessorEffectiveDate = true`.

Only those fail-closed rule values are supported in P5-02; a policy cannot
disable integrity, scanner or replacement safeguards. Reviewer slots and
release authority are nonempty and disjoint. Supersede and obsolete authority
are separately declared and checked even when an administrator explicitly
binds the same person to more than one of those two operations.

No policy is created by migration. An absent, draft, mismatched or changed
policy makes the dependent command unavailable.

### 4.3 Review cycle and confirmations

`NPI Document Review Cycle` is append-only. It freezes:

- exact Project/document/revision identity and revision snapshot hash;
- exact File Revision identities, hashes, observed formats, sizes, uploader
  identity, upload time and scanner observation;
- exact release-policy reference, full policy/input snapshot and hash;
- exact reviewer slot assignments and required approval count;
- prior rejected cycle identity for resubmission;
- submitter, submission time, request and trace; and
- a unique monotonic cycle number for that revision.

`NPI Document Confirmation` is append-only and unique per cycle/slot or
lifecycle operation. It freezes:

- confirmation type (`review_approve`, `review_reject`, `release`,
  `supersede`, or `obsolete`);
- exact cycle, revision, file and policy snapshot hashes;
- actor, exact policy slot/binding, authenticated-session method;
- explicit stable confirmation intent and `confirmed = true`;
- bounded reason/comment where applicable;
- observed time, request, trace and confirmation evidence hash.

This is an authenticated electronic confirmation record. P5-02 does not call
it a qualified, certificate-backed or legally regulated digital signature.

One reject closes the active cycle and returns the lifecycle projection to
`draft`. Approvals are counted by unique frozen reviewer slots. Only the exact
required count moves the projection to `approved`; duplicate actors/slots,
late confirmations and stale cycles fail closed.

### 4.4 Lifecycle events and projection

`NPI Document Lifecycle Event` is append-only and freezes the exact
from/to state, lifecycle versions, revision/file/policy/cycle/confirmation
snapshots, replacement/effectivity information where applicable, actor, time,
request, trace and event hash.

`NPI Document Revision Lifecycle` is the only mutable state projection. It is
one-to-one with an immutable revision and contains:

- current state;
- current optimistic lifecycle version;
- active review-cycle identity, if any;
- approved cycle/event identity;
- release event and release snapshot hash;
- replacement revision/effective date for superseded state; and
- terminal event identity for superseded/obsolete state.

Legacy or retained P5-01 revisions with no lifecycle row are represented as
`draft` at lifecycle version `0`. The first submit/resubmit command atomically
creates version `1`; no destructive backfill is required.

Every transition requires the exact expected document version and expected
lifecycle version. The server appends the event/confirmation first, advances
the guarded projection in the same transaction, appends audit, and seals the
actor-bound idempotency receipt last. Failure rolls back all database changes.

Allowed projection transitions are closed:

| Command/event | From | To |
|---|---|---|
| submit | `draft` with no rejected predecessor | `in_review` |
| resubmit | `draft` with exact rejected predecessor | `in_review` |
| reject | `in_review` | `draft` |
| final required approval | `in_review` | `approved` |
| release | `approved` | `released` |
| supersede | `released` | `superseded` |
| obsolete | `released` | `obsolete` |

Partial reviewer approval keeps the projection `in_review` but appends the
confirmation and increments the lifecycle version, preventing stale parallel
decisions.

### 4.5 Release integrity and retained binary

Approval freezes the exact revision/file metadata present in the cycle.
Release independently revalidates all of it:

- same tenant, Project, document and revision;
- same immutable revision and association hashes;
- same Frappe File identity, private path, filename, content hash and size;
- actual bytes produce the frozen SHA-256;
- observed MIME remains policy-allowed;
- scanner-owned state is exactly `clean` with an observation time; and
- the File Revision has not been substituted or reopened.

Only then does the transaction mark the exact `NPI File Revision` released,
append release confirmation/event/audit, advance the lifecycle projection and
seal the receipt.

The Frappe `File` `on_trash` hook rejects deletion when any exact
`NPI File Revision` referring to it is released. It emits no raw path, URL or
protected identity. Existing dependency-evaluation hooks remain present and
ordered after the protection check. Revision, association, review,
confirmation, event, lifecycle, policy and receipt controllers all deny
delete; history rows deny update.

Released, superseded and obsolete states remain retained. A content change
must use the existing P5-01 new-revision command and can never overwrite the
released revision.

## 5. BFF and OpenAPI contract

The P5-01 independent document route switch continues to guard all document
routes. P5-02 adds no anonymous, Desk CRUD or raw File route.

| Method and path | Purpose |
|---|---|
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}:submit-review` | start the first immutable cycle under one exact published policy |
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}:review` | append one exact assigned reviewer approve/reject confirmation |
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}:resubmit-review` | create a new cycle from the exact rejected predecessor |
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}:release` | authenticated release confirmation after fresh integrity/security validation |
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}:supersede` | retain a released revision and bind one exact later released effective successor |
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}:obsolete` | retain and mark a released revision obsolete with a bounded reason |

The existing document detail response adds:

- available exact published release-policy options visible to the authorized
  internal workspace without exposing member existence to unauthorized users;
- current lifecycle state/version and operation capabilities per revision;
- review cycles and immutable confirmations;
- lifecycle events and exact release/replacement summaries; and
- independent `submitReview`, `review`, `approve`, `release`, `supersede` and
  `obsolete` permissions.

All request/response schemas are closed and bounded. Every command requires:

- authenticated internal principal and transport permission;
- opaque Project/document/revision resolution after authorization;
- trusted Frappe CSRF;
- actor-bound idempotency key;
- expected document and lifecycle versions;
- exact policy/cycle/replacement references as applicable; and
- stable confirmation intent plus `confirmed: true`.

Stable P5-02 problem codes are:

- `DOCUMENT_RELEASE_POLICY_UNAVAILABLE`;
- `DOCUMENT_REVIEW_STATE_CONFLICT`;
- `DOCUMENT_REVIEW_ASSIGNMENT_UNAVAILABLE`;
- `DOCUMENT_RELEASE_AUTHORITY_UNAVAILABLE`;
- `DOCUMENT_RELEASE_INTEGRITY_BLOCKED`; and
- existing authentication, CSRF, `DOCUMENT_UNAVAILABLE`,
  `DOCUMENT_VERSION_CONFLICT`, validation, idempotency and route-disabled
  families.

Object existence, user bindings, File IDs, URLs, hashes and scanner detail are
not disclosed to an unauthorized caller.

## 6. Authorization

Existing Project containment remains a necessary precondition, never business
authority. Exact policy membership is independently checked for every command:

- submit/resubmit: actor is in `submitterUserIds`;
- approve/reject: actor matches the exact active reviewer slot;
- release: actor is in `releaseAuthorityUserIds`;
- supersede: actor is in `supersedeAuthorityUserIds`;
- obsolete: actor is in `obsoleteAuthorityUserIds`.

Only enabled internal System Users can be frozen in a published synthetic
policy. Guest, Website/external, disabled, tenant-mismatched, unrelated or
ambiguous identities fail closed. `System Manager` and `NPI API User` do not
implicitly appear in any business-authority set.

Frontend controls mirror server capability truth but never grant permission.

## 7. Workspace and i18n

The existing Project Document workspace is extended; no Frappe Desk form
becomes a normal-user path.

The compact industrial layout adds:

- lifecycle state and lifecycle-version columns in revision history;
- one policy/review action area with at most one visible primary action;
- a dense reviewer-assignment/progress table;
- immutable confirmation and release-history tables;
- exact file integrity/scan/release status using text plus shape/icon; and
- nonnormal loading, no-permission, read-only, validation, conflict,
  processing, retryable/final failure, integrity-blocked, rejected,
  partially-approved, approved, released and terminal states.

All new source copy is literal English through `t()` or Frappe `_()`, with
direct `zh` and `zh-TW` translations. Stable state/intent/reason codes,
business data, hashes, identifiers and units remain language exempt under the
existing allowlist. Keyboard/focus, labels, confirmation focus recovery,
125%/150% layout and zero-tolerance visual checks remain required.

## 8. Changed files to affected tests

| Change boundary | Minimum affected proof |
|---|---|
| domain states/policy/cycle/confirmation/transitions | new P5-02 domain unit tests plus existing P5-01 document domain tests |
| new DocTypes/controllers and guarded projection | P5-02 controller/metadata tests, existing document controller tests, additive two-migration runtime |
| repository commands, integrity and File delete hook | repository transaction/rollback/idempotency/authority/integrity/delete tests plus existing document repository tests |
| BFF/API/OpenAPI | route/auth/CSRF/IDOR/closed-schema/replay/conflict tests plus existing document API/contract tests |
| workspace/data source/i18n | direct catalogs, TypeScript/lint/unit/component/a11y tests and three-language browser cases |
| visual layout | fixed-Linux exact EN/zh/zh-TW screenshots at approved sizes/scales and original-resolution review |
| verifier/workflow | static verifier tests, controlled-Site two migrations, normal/reject/resubmit/approve/release/replay/route-disable-recovery and retained-file deletion rejection |
| trace/ownership/evidence | trace reconciler, metadata/verifier and Task Diff Review |

Level 1 runs are grouped by root cause. P5-02 Level 2 runs the complete
document module, affected BFF/security/i18n/UI/runtime matrix, Requirement
trace and Task Diff Review. It does not replace the Phase 5 Level 3 Gate.

## 9. Migration and rollback

The migration is additive:

- install the new root/version, lifecycle projection, review cycle,
  confirmation and lifecycle-event DocTypes;
- add only the required indexes/uniqueness constraints;
- add no production policy, user binding, authority, retained-history rewrite
  or destructive backfill; and
- prove install plus two consecutive migrations on the controlled Site.

Rollback is:

1. activate a new independent `npi_p5_02_routes_disabled` switch for only the
   review/release commands and capabilities;
2. leave P5-01 create/list/detail/lock/revision/content routes operational;
3. stop new P5-02 writes;
4. retain every policy version, cycle, confirmation, lifecycle event,
   lifecycle projection, released File Revision, Frappe File, audit and
   idempotency receipt; and
5. deploy a reviewed forward fix.

No rollback deletes or reopens released history or the retained binary.

## 10. Acceptance and next implementation slice

The audit passes because each P5-02 Requirement has an exact implementation
boundary, no held production fact is invented, and the plan changes no
P5-01 Requirement, permission, schema semantics, lock, retrieval,
idempotency, audit or transaction ordering.

The first implementation slice is the smallest complete controlled-metadata
foundation:

1. domain states, exact synthetic release-policy validation and closed
   transitions;
2. additive policy/lifecycle/cycle/confirmation/event DocTypes and immutable
   controllers;
3. independent release write flag and P5-02 route-disable setting;
4. exact File delete protection; and
5. focused metadata/controller/domain tests.

Repository/BFF/OpenAPI/frontend/runtime work follows within the same atomic
P5-02 task and cannot report completion until the complete Level 2 Task Gate
passes.
