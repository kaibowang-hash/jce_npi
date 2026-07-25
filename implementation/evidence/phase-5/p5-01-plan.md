# P5-01 Plan — Document and Design Revision

Planned: `2026-07-25T18:38:47Z`

Starting remote checkpoint:
`6099ac2351567665478ff911bc07c4ef55ab3ee1`

Task state: **IN PROGRESS — V1_2_RECONCILIATION_HOLD**

Checkpoint evidence:
`implementation/evidence/phase-5/p5-01-reconciliation-hold.md`

The user-directed hold freezes this plan after the bounded
backend/domain/DocType/repository/BFF/API/contract unit. It does not mark
P5-01 complete and no later planned sub-slice may start until reconciliation
is explicitly lifted.

Applicable requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Applicable Skills:

- `frappe-safe-change`
- `npi-domain-guard`
- `industrial-ux`
- `frappe-i18n`

## 1. Scope

P5-01 delivers one additive Project-scoped vertical slice for controlled
document identity, immutable draft revisions over exact private File
Revisions, typed object relationships, edit locks, internal confidentiality
and audited file retrieval, preview/download capability truth, and an explicit
unavailable CAD/PDM/external-sharing boundary.

The accepted path is:

> open one authorized Project → create a Controlled Document under one exact
> synthetic policy → check out its edit lease → upload and append an immutable
> draft Document Revision and exact private File Revision → inspect revision,
> hash, scan and relationship truth → release or administratively recover the
> lease → preview/download only when current authorization, private-file
> identity, integrity and scan state permit

No production document policy or fixture is installed.

## 2. Non-scope and Class-B holds

P5-01 does not implement review, approval, release, supersede, obsolete,
baseline, impact invalidation, EBOM, formal publish requests, production
ERPNext, actual external retrieval, a public/Guest link, Office/CAD rendering,
or a real CAD/PDM connector.

The following remain exact scoped holds:

- production document types, prefixes, uniqueness scope and numbering;
- production major/minor/effectivity/replacement rules;
- production confidentiality, retention, watermark and download restrictions;
- production scanner/provider, storage and archive policy;
- external principal, TTL, revocation and incident policy;
- production edit-lock lease/recovery authority;
- complete object-link and impact resolver matrix; and
- CAD/PDM provider, endpoint, credential, mapping, derivative and retry rules.

The implementation accepts only explicit versioned policies. Tests and browser
fixtures use visibly synthetic policies. Missing policy/provider facts produce
an unavailable state; they are never inferred.

## 3. Frozen domain design

### 3.1 Identities

- `ControlledDocument` is the stable Project-scoped identity and generated
  document number.
- `DocumentRevision` is an append-only exact major/minor draft revision.
- `FileRevision` remains the existing exact private binary identity and scan
  observation; its integer revision and `released` flag are not reinterpreted.
- `DocumentRevisionFile` is the append-only primary/source/derivative
  association between one Document Revision and one exact File Revision. It
  prevents the existing File Revision's evidence-oriented
  `document_global_id:integer` identity from being collapsed into the new
  business revision identity.
- `DocumentRelationship` is an append-only typed link validated against the
  same Project and an implemented resolver.
- `DocumentLockEvent` is append-only lock acquisition, release or recovery
  history. The Controlled Document contains only the current lease projection.
- `DocumentShareGrant` is a disabled-by-default future-access record. It does
  not authorize retrieval in P5-01.

### 3.2 Versioned policy

An administrator-configured Document Policy root and immutable published
version define:

- permitted document type keys and prefixes;
- permitted confidentiality keys;
- permitted file MIME observations and maximum file bytes;
- native preview MIME observations; and
- the edit-lease duration.

The server generates a unique document number from the exact type-prefix rule
and server-generated document identity. Browser input cannot choose a raw
prefix, sequence or Frappe Naming Series. The root document number key is
unique and insertion conflicts leave one winner with no partial record.

No policy is created by migration. A Project workspace with no accepted policy
shows document creation as unavailable.

### 3.3 Revisions, files and locks

- Creating a Controlled Document creates no fake revision or file.
- A new revision requires the exact current document version, exact current
  lease identity/version held by the actor, explicit major/minor values,
  reason, nullable effective date and exact predecessor when one exists.
- The multipart request contains one strict metadata JSON part and one binary
  part. It cannot contain SHA, MIME truth, size, privacy, scan, release, actor,
  tenant, Frappe File identity or URL.
- The server validates actual bytes, size and observed format, saves a private
  Frappe File, creates one exact File Revision in real scanner-owned `pending`
  state, then appends one immutable Document Revision and advances only the
  document's current-revision pointer.
- File, File Revision, Document Revision, pointer, audit and sealed
  idempotency result are one recoverable unit. A failed database transaction
  registers bounded cleanup for a newly orphaned physical file and never
  deletes shared/committed content.
- Check-in releases a lease only; it never changes a Document Revision.
- Administrative recovery requires the exact current lease version and a
  bounded reason and retains the former holder and complete audit.

### 3.4 Relationships

P5-01 supports only exact, same-Project resolvers available now:

- the Project itself;
- a typed Project reference (`customer`, `product`, `part`, `tooling`, or
  `order`) matching the Project's frozen reference tuple;
- an exact Project Gate;
- an exact WBS item; and
- an exact Domain Work Item.

Query filtering uses only these typed identities. It accepts no DocType name,
SQL/filter expression, raw URL or future Tooling/Trial/change/CAD identity.
Future resolvers are returned as unavailable, not guessed.

### 3.5 Authorization and confidentiality

- Route parsing and the independent P5-01 route switch run before protected
  object resolution.
- Guest, Website/external, tenant-mismatched, unrelated and unavailable
  Project cases expose no protected identity or validation detail.
- The existing bounded current-Project access remains unchanged: an internal
  System Manager may administer/contribute; the internal Project owner and one
  exact current, enabled System User Project member may view; external,
  duplicate/ambiguous member and other access remains unavailable. Project
  membership alone does not grant document create/revise/recover authority
  until an approved role policy exists.
- View, create, upload/revise, lock, recover, capability, preview, download,
  share, review, approve and release are independent server decisions.
- Confidentiality keys are policy-owned metadata only in P5-01. No unapproved
  key silently grants or denies a new principal class.
- Every command requires Frappe CSRF, request/trace IDs, actor-bound
  idempotency and exact optimistic versions. Every query and content request
  is `private, no-store`.

### 3.6 Preview, download, external and connector truth

- A capability response revalidates document containment, exact revision/file,
  live private-file identity, SHA-256, current scan observation, authorization,
  route state and policy.
- Browser-native PDF/image preview can be `available` only for an approved
  MIME observation and `clean` exact file. Office/CAD preview is
  `unavailable`; infected/failed/pending/drifted files are `blocked`.
- The capability response contains no raw URL, token or content.
- The content BFF streams the exact bytes directly after reauthorization and a
  successful append-only audit write. It never redirects to a Frappe URL.
- Content responses use a validated filename, `private, no-store`,
  `nosniff`, exact length, disposition, request and trace headers.
- External retrieval is always `unavailable` in P5-01. A share-grant row
  never grants access by itself.
- The CAD/PDM adapter reports only `unavailable` or an isolated failure. It
  performs no outbound request and never claims connection success.

## 4. Planned BFF contract

| Method and path | Purpose |
|---|---|
| `GET /projects/{projectId}/documents` | bounded signed-keyset list, exact typed reverse filter, policy and capability summary |
| `POST /projects/{projectId}/documents` | create one document root from an exact policy |
| `GET /projects/{projectId}/documents/{documentId}` | exact detail, complete revision/relationship/lock history |
| `POST /projects/{projectId}/documents/{documentId}:check-out` | acquire exact edit lease |
| `POST /projects/{projectId}/documents/{documentId}:check-in` | release exact actor-held lease |
| `POST /projects/{projectId}/documents/{documentId}:recover-lock` | administrator recovery with reason |
| `POST /projects/{projectId}/documents/{documentId}/revisions` | strict multipart append of one exact revision/file |
| `GET /projects/{projectId}/documents/{documentId}/revisions/{revisionId}/files/{fileRevisionId}/capabilities` | URL-free capability truth |
| `POST /projects/{projectId}/documents/{documentId}/revisions/{revisionId}/files/{fileRevisionId}:content` | reauthorized, CSRF/idempotency-protected and audited inline/download content |

All JSON objects are closed. Collections, strings, metadata and binary sizes
are bounded. Missing/unauthorized document resources use one
`DOCUMENT_UNAVAILABLE` 404 representation.

Stable task errors include:

- `DOCUMENT_UNAVAILABLE`
- `DOCUMENT_POLICY_UNAVAILABLE`
- `DOCUMENT_NUMBER_CONFLICT`
- `DOCUMENT_VERSION_CONFLICT`
- `DOCUMENT_LOCK_CONFLICT`
- `DOCUMENT_FILE_UNAVAILABLE`
- `IDEMPOTENCY_KEY_CONFLICT`
- `DOCUMENT_ROUTES_DISABLED`
- the existing authentication, CSRF, validation and internal-error families.

## 5. Persistence and migration

Planned additive DocTypes:

- `NPI Document Policy`
- `NPI Document Policy Version`
- `NPI Controlled Document`
- `NPI Document Revision`
- `NPI Document Revision File`
- `NPI Document Relationship`
- `NPI Document Lock Event`
- `NPI Document Command Idempotency`
- `NPI Document Share Grant`

All normal-user writes run only through controlled BFF command flags.
Revisions, relationships, lock history, grants, audit and idempotency are
append-only or transition-constrained and cannot be deleted through generic
CRUD. Existing File Revision fields and P4 evidence semantics remain
unchanged.

The migration is metadata-only, additive and idempotent. It installs no policy,
document, file, relationship, grant, connector, external access or business
record. It does not backfill legacy File Revisions into Document Revisions.

Before retained P5-01 history exists, a disposable environment may restore
`6099ac2351567665478ff911bc07c4ef55ab3ee1`. After history exists, set
`npi_p5_01_routes_disabled=true`, preserve every file/revision/history/audit/
receipt row and deploy a reviewed forward fix. Never uninstall the App or
delete controlled history as rollback.

## 6. Requirement → code → test → evidence

| Requirement | Planned code | Planned tests/evidence |
|---|---|---|
| `FR-DS-001` | policy/version, server document-number generation and unique root | domain, controller, metadata, repository concurrency/conflict, API, contract, runtime, UI |
| `FR-DS-003` | immutable major/minor revision, reason/effectivity/predecessor and revision history | domain, immutable-controller, repository replay/rollback, API/parser/UI history |
| `FR-DS-004` | typed same-Project relationships and reverse filter | resolver/IDOR/version tests, contract, query/runtime/UI |
| `FR-DS-007` | current lease projection plus append-only acquire/release/recovery events | lease conflict/expiry/stale/recovery/replay/audit tests and UI commands |
| `FR-DS-008` | policy confidentiality, Project authorization, access audit and unavailable share retrieval | permission matrix, URL/Guest/expiry/revocation/static contract and UI truth |
| `FR-DS-009` | exact file capability and audited BFF content | MIME/hash/scan/drift/header/filename/audit-failure tests plus PDF/image/unavailable UI |
| `FR-DS-014` | connector-neutral provenance/capability contract with unavailable adapter | no-outbound/failure-isolation contract, unit and UI unavailable-state evidence |

Final task evidence will be recorded in
`implementation/evidence/phase-5/p5-01-validation.md`.

## 7. Expected files and changed-files → affected-tests

| Expected change surface | Direct affected checks |
|---|---|
| `apps/npi_core/npi_core/document_design/**`, `document_api.py` | new domain/repository/API/controller suites; focused Python compilation |
| new controlled DocTypes, `hooks.py`, `patches.txt` if required | metadata/controller tests; additive/idempotent Site migration; complete runtime compatibility |
| `bff.py`, `request_security.py`, foundation errors | exact route/method/direct-handler/route-disable/error-envelope regression |
| existing File Revision validation | existing Gate evidence/review/File Revision controller and runtime regression |
| OpenAPI and data ownership | OpenAPI parse/reference/closed-schema tests; ownership assertions |
| document data source/view models/Project workspace/App wiring | parser/transport/page/component/type/lint/style/boundary tests |
| `app.css`, direct translation catalogs | affected three-language pages, mixed-language/coverage/accessibility/visual cases |
| P5-01 Playwright support/spec/snapshots | normal, empty, no-permission, read-only, validation, conflict, processing, retryable/final, unsafe/unavailable, lock and content cases |
| implementation status/evidence | trace/current-state/Task Diff/whitespace review |

## 8. Validation sequence

During repair batches, run only direct domain/controller/repository/API/parser/
component tests, affected static checks, translation coverage and
`git diff --check`.

At the P5-01 Level 2 Task Gate run:

1. all P5-01 Python/domain/controller/metadata/repository/API/contract tests;
2. affected existing File Revision, Gate Evidence, BFF, Project authorization,
   audit, idempotency and rollback regressions;
3. new metadata synchronization plus an idempotent rerun;
4. complete prior runtime compatibility plus focused document runtime,
   rollback, replay, file cleanup/content, audit and route-disable evidence;
5. all affected frontend unit/component/parser/type/lint/format/style/boundary
   checks and coverage floor;
6. literal-English extraction, complete direct `zh`/`zh-TW`, terminology and
   mixed-language checks;
7. the affected live Project/Documents Playwright matrix, exact
   zero-tolerance trilingual visuals and original-resolution review;
8. requirement trace, changed-files-to-tests, migration/rollback, security,
   Task Diff and independent bounded review; and
9. final `git diff --check`, checkpoint commit, push and remote-SHA
   confirmation.

P5-01 is not a Phase, PR, shared architecture, authentication/permission-model
or release boundary. The final Task Diff will reassess impact. If the change
cannot remain a bounded additive module, validation escalates to Level 3
instead of guessing.

The live document forms must report real dirty state to the existing App
navigation guard. App navigation, browser history, Project-tab changes and
`beforeunload` all require confirmation; cancel restores focus and preserves
input. This does not use the prototype scenario query as live state.

## 9. First implementation action

Implement the pure document-policy/document-revision/lock domain model and its
focused unit tests, then add controlled DocType metadata/controllers. Do not
start frontend or contract work until the domain invariants pass a Level 1
check.
