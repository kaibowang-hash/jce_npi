# P6-08 Plan — Controlled Tooling Selection, Filter and Object-package Export

Recorded: `2026-08-09T19:26:44Z`

Decision: `PASS — BOUNDED FOUR-CHECKPOINT PLAN`

Starting synchronized checkpoint:
`d5d6064b6db8a5c0e82c1f8e398272b1b432d6a0`

Task: `P6-08 — Selection/filter and controlled object-package export`

Primary requirement: `UX-007`

Canonical support: `FR-UX-007`, `FR-UX-025`, `FR-UX-030`, plus the accepted
Phase 6 security/localization boundaries in `NFR-SEC-003` and `NFR-LOC-001`.

The exact starting/controller checkpoint passes ordinary CI `31331504738`:
repository `93290380976` and fixed-Linux visual `93290380955` at `91/91` are
PASS; the controlled job correctly skips because no product/runtime behavior
changed at the P6-07 evidence/trace closure boundary.

## 1. Audit outcome

P6-08 requires a real Tooling engineering list and a controlled export
vertical slice. The accepted repository has a reusable dense-grid component,
fixed My Work personalization and safe binary-response/file/audit patterns,
but it has no Tooling-list query contract, Tooling personal-view persistence,
export authority, package renderer, immutable export artifact, download route
or live export action.

The minimum complete slice will:

- expose one Project-first Tooling list with ten code-owned common views,
  closed filter/sort/group values, stable server paging and exact snapshot
  fingerprints;
- restore each actor's per-Project/per-view/per-table-schema layout and query
  state without turning the accepted My Work preference route into a generic
  settings service;
- export either exact selected Tooling Masters or the exact current filtered
  result, never both and never a caller-selected DocType/query/field list;
- freeze an immutable, private, actor-bound `tooling-object-package-v1` ZIP
  containing a machine manifest, localized safe CSV and localized readme;
- revalidate Project visibility, the separate conservative export authority,
  exact object snapshot hashes and current filter-result hash before package
  creation;
- omit private File URLs/content, raw import values, customer/supplier external
  identifiers, repair authorization, custody/return text, cost and free-form
  evidence; record those omissions in the manifest;
- audit creation and download using hashes/counts rather than exported values;
  and
- block download after a fixed one-hour technical validity window while
  retaining immutable artifact/audit truth.

This is not an arbitrary database dump, generic Data Exchange service, report
builder, customer workbook export, ERPNext projection or shared-view publisher.

## 2. Requirement and authority interpretation

`UX-007` requires a high-density Tooling List with at least ten common views,
personal restoration, column selection/fixing, grouping, filtering, sorting,
bulk behavior and export. R1-04 accepted only the reusable grid/personalization
foundation and intentionally left export unavailable under
`export_contract_required`. P6-08 closes the Tooling-specific foundation while
retaining representative production-scale performance as external evidence.

The exact ten common views are code-owned projections over already accepted
Tooling facts:

1. `all` — every visible logical Tooling Master;
2. `missing_applicability` — no visible exact Applicability;
3. `single_part` — one distinct visible Part Revision Applicability;
4. `shared_parts` — more than one distinct visible Part Revision Applicability;
5. `missing_physical_set` — no visible physical Tooling Set;
6. `single_physical_set` — one visible physical Tooling Set;
7. `multiple_physical_sets` — more than one visible physical Tooling Set;
8. `missing_design_revision` — no immutable Tooling Revision;
9. `has_design_revision` — at least one immutable Tooling Revision; and
10. `customer_owned_set` — at least one exact customer-owned physical Set.

These views use presence/count truth only. They do not infer lifecycle,
approval, health, ERP state, production exception color or customer mapping.

Closed user controls are:

- bounded case-insensitive search over Tooling title and canonical identity;
- sort by title, Applicability count, Set count or latest revision number in a
  closed ascending/descending vocabulary;
- group by none, Applicability scope, physical-Set presence or design-revision
  presence; and
- code-owned columns for selection, Tooling identity, Applicability, exact
  Part Revision count, physical Sets, design revisions, origin, source/version
  and open-object action.

The server is authoritative for membership, ordering, page cursor, aggregate
counts, current object snapshots and query-result hash. The browser may not
relabel a locally filtered subset as the current server filter result.

## 3. Export contract

### 3.1 Modes and bounds

The create command accepts exactly one mode:

- `selection`: one to one hundred unique `{toolingMasterGlobalId,
  snapshotHash}` references selected by the actor; or
- `filtered`: the exact closed view/search/sort/group query plus the server
  `querySnapshotHash` returned by the live list.

Filtered exports must resolve to `1..100` current authorized Masters. Empty or
larger results fail with a translated validation error that asks the actor to
narrow the filter. Page size and cursor are never export inputs, so "current
filtered result" means the complete bounded result, not only the visible page.

Selection and filter inputs are mutually exclusive. Stale object/query hashes,
duplicates, inaccessible shared Masters, altered replays and unsupported
fields fail closed.

### 3.2 Separate export authority

Ordinary Project visibility can list Tooling but cannot export it. The initial
conservative live authorizer requires all of:

- authenticated internal actor;
- exact tenant and Project `VIEW` authorization; and
- existing `System Manager` role.

This grants no new role or Project access and does not treat `System Manager`
as business approval, shared-view publisher or lifecycle authority. The BFF
returns explicit `canExport` truth; non-export actors see the list and a
translated unavailable reason. A future dedicated export authority may
replace this conservative bound through an approved contract.

### 3.3 Package content and redaction

The private ZIP contains exactly three fixed member names:

- `manifest.json`: stable machine keys, package/project/mode/query identities,
  actor, generated/expiry instants, Frappe language, confidentiality class,
  immutable object references/hashes, member SHA-256 values and omitted data
  classes;
- `tooling-objects.csv`: UTF-8 BOM, CRLF, localized headers and one allowlisted
  summary row per exact Tooling Master; and
- `README.txt`: localized scope, redaction, validity and no-ERP/no-lifecycle
  statements.

The CSV allowlist contains only Project code, Tooling Master canonical ID,
title, Master snapshot hash, originating Project canonical ID, Applicability
count, distinct Part Revision count, physical-Set count, latest immutable
Tooling Revision number or explicit unavailable value, source system and
package-generated instant. It contains no raw private URLs, file bytes,
workbook values, external customer/supplier identifiers, cost, evidence names,
free-form reasons, custody/repair/return text or ERP target truth.

Every text cell beginning with `=`, `+`, `-` or `@` is neutralized before CSV
serialization. ZIP member names are fixed ASCII, member count/size is bounded,
ordering is deterministic and no renderer executes formulas, macros, links or
external content.

### 3.4 Artifact, validity and download

Creation persists one immutable export-package record, one private Frappe File
and an actor-bound sealed idempotency receipt in a single transaction. The
record retains exact File identity, file name, MIME, bytes, SHA-256, manifest
hash, selection/filter snapshot, object refs, source hashes, language,
confidentiality, created instant and `expiresAt = createdAt + 60 minutes`.

Download is a CSRF-protected POST with a separate actor-bound idempotency key.
It reauthorizes the same Project, export authority, package creator, exact
artifact/hash and unexpired instant, verifies private File bytes/digest, audits
the download and returns attachment-only security headers. Expiry blocks new
downloads but never deletes or rewrites the artifact, receipt or audit rows.

## 4. Existing-capability audit

### Reusable

- `frontend/src/ui-adapters/dense-grid.tsx` and layout helpers already provide
  bounded resize, auto-fit, hidden/fixed columns, keyboard behavior and one
  internal scroll owner.
- R1-04 proves fixed authenticated preference storage, strict closed schemas,
  optimistic conflict reconciliation and corrupt-storage fallback, but its
  My Work route/domain must remain fixed.
- `FrappeToolingRepository` already enforces tenant/Project-first visibility,
  distinguishes Masters/Applicability/Revisions/Sets and uses bounded reads.
- P6-07 correction artifacts prove private Frappe File creation, exact hash/
  byte verification, attachment security headers, actor-bound receipt replay,
  audited download and no raw value leakage.
- The controlled-print and document paths provide additional binary response,
  content-disposition and exact immutable-reference patterns.
- Existing audit, request tracing, idempotency, route-switch, migrations,
  English-source translation and trilingual visual/runtime infrastructure are
  reusable.

### Missing

- no fixed Tooling list query/page/filter/view schema or server query snapshot;
- no Tooling-grid preference and no ten Tooling common views;
- no Tooling export permission projection;
- no selection/filter export command, safe CSV/ZIP renderer or redaction
  manifest;
- no immutable Tooling export artifact/receipt or private download route;
- no live review step, progress/error/expiry/download state or trilingual
  Tooling-list visuals; and
- no independent P6-08 route switch or cumulative runtime verification.

### Explicitly not reusable as completion

- the full P6-01 cockpit response is a bounded object workspace, not a stable
  paged Tooling List contract;
- browser-only selection/filter state is not export authority or a server
  query snapshot;
- My Work `canExport: false` is honest foundation, not a dormant generic route;
- correction CSV is job-specific remediation, not a Tooling object package;
  and
- Frappe Desk export or raw DocType report APIs are prohibited product paths.

## 5. Delivery checkpoints

### Checkpoint 1 — domain, contracts and additive metadata

- Add pure Tooling-list query/view/layout/preference/export/package domains,
  deterministic safe CSV/ZIP rendering and fixed redaction vocabulary.
- Add closed OpenAPI schemas, data-ownership rows and receipt operation values.
- Add guarded additive DocTypes for one Tooling-list preference and immutable
  export package/receipt truth.
- Prove all ten views, exact query fingerprinting, closed inputs, formula
  neutralization, deterministic member hashes, expiry and immutable snapshots.
- Keep routes, business rows, private files and SPA actions inactive.

### Checkpoint 2 — repository, BFF and private artifact/download

- Add the independent P6-08 route switch and Project-first list/preference/
  export/download routes.
- Implement stable bounded paging, per-view optimistic preference persistence,
  current selection/filter revalidation and conservative separate export
  authority.
- Persist the immutable actor-bound private package and receipt; return binary
  content only after exact digest/expiry/creator reauthorization.
- Prove query-before-secondary-filter authorization, IDOR, external/non-export
  denial, stale/conflict/replay, generic CRUD denial, transaction rollback,
  raw-value log redaction and no ERP/network/Outbox behavior.

### Checkpoint 3 — dense trilingual Tooling List workspace

- Add a P6-08 list section to the selected Project Tooling workspace using the
  shared DenseGrid and fixed P6-08 preference data source.
- Deliver ten views, saved layout/query state, closed search/sort/group,
  stable server pages, accessible row selection/count/status and preserved
  selected-object navigation.
- Add one secondary Export action and a review step showing mode, exact count,
  one-hour validity, redactions, immutable-version policy and failure handling.
- Expose loading, empty, read-only/no-export, validation, stale/conflict,
  processing, success, expired, download-failure and replay truth in English,
  Simplified Chinese and Traditional Chinese.
- Prove keyboard/focus, 1366/1440/1920 layouts, 100/125/150 scaling, no card
  wall, no page-level overflow and affected fixed-Linux visual matrices.

### Checkpoint 4 — cumulative controlled runtime, Level 2 and Phase 6 Gate

- Extend the disposable-Site verifier/workflow through P6-08.
- Seed bounded synthetic Tooling truth; prove every common view, selection and
  filtered packages, localized members, formula neutralization, exact hashes,
  one-hour boundary, same/cross-process replay, actor/Project/IDOR/expiry/stale
  denials, route disable/recovery, two migrations, raw-log redaction, no
  ERP/network/Outbox and cleanup.
- Reconcile `UX-007` only to the exact evidence-backed state and run its Level
  2 Task Gate.
- Because P6-08 closes Phase 6 and changes public contracts, metadata, shared
  grid use and translation, run the cumulative Phase 6 Level 3 `release-gate`
  before activating Phase 7.

## 6. Changed-files to affected-tests

| Change boundary | Required evidence |
|---|---|
| Query/view/filter/sort/group domains | ten-view membership, closed values, stable order/cursor, page/full-result hashes and bounds |
| Preference domain/DocType | per-actor/Project/view/schema isolation, layout/query validation, optimistic conflict, corrupt fallback and generic-write denial |
| CSV/ZIP renderer | localized headers/readme, fixed members, deterministic order/hash, formula injection, Unicode/CRLF/BOM, redaction and size bounds |
| Export package/receipt/File | immutable refs, exact private File bytes, creator/expiry/hash, replay/conflict, transaction rollback and audit summaries |
| Project-first BFF | guest/external/non-export/IDOR, authorization order, stale snapshot, unexpected field, CSRF, route switch and binary headers |
| Tooling-list data source/workspace | request parsing, ten views, paging, selection/filter mode, preference restore, review/error/expiry/download states |
| Shared DenseGrid/style/i18n | unit/accessibility, affected browser cases, direct English/zh/zh-TW catalogs, mixed-language scan and governed visuals |
| Runtime/controller/trace | migrations, fresh-process replay, route recovery, redacted artifacts/logs, no ERP traffic, reconciliation and Gate evidence |

## 7. Risks and controls

| Risk | Control |
|---|---|
| Caller turns export into a DocType/query/field dump | Fixed P6-08 routes, views, fields and package members; reject arbitrary expressions and unknown fields |
| Shared Master exposes another Project/customer relationship | Project-first authorization and Project-relative aggregate; package includes only relations visible in the selected Project |
| UI selection/filter drifts before export | Exact Master snapshot hashes or complete querySnapshotHash; revalidate and fail stale rather than export newer truth silently |
| CSV formula or confidential value leaks | Strict allowlist, leading-character neutralization, omission manifest and sentinel scans of logs/artifacts |
| Export exhausts request memory/CPU | Maximum 100 Masters, existing 200-source bound, fixed member count, byte limits and no recursive/file content inclusion |
| Private package URL or expired artifact stays downloadable | Never return raw URL; creator-bound POST download, digest verification, security headers and fixed one-hour expiry |
| Localized headers break machine interpretation | Stable manifest keys/schema and member hashes remain language-neutral; CSV/readme language is frozen and explicit |
| Paging selection is mistaken for all filtered rows | Separate selection/filter modes, visible selected count and complete server result hash independent of current page |

## 8. Migration and rollback

Metadata is additive and creates no production policy, external adapter,
customer fixture or ERP identifier. Before retained P6-08 rows, commits may be
reverted and a disposable Site recreated. After preferences/packages/receipts/
audit rows exist, rollback disables only the independent P6-08 routes and live
composition and ships a reviewed forward fix. It leaves private artifact,
immutable hashes, receipts and audits intact until the approved retention path
handles them; it never exposes raw File URLs or deletes history to simulate a
rollback.

## 9. Trace target and transition

At P6-08 Level 2, `UX-007` may advance only to
`TECHNICAL_VERIFIED_FOUNDATION`: ten Tooling views, personal restoration,
selection/filter export, exact private object packages, redaction/audit/
language and bounded stable server paging are technically proven. The
canonical `FR-UX-030` representative production-scale performance claim
remains external until real-scale evidence exists.

Standing transition authority activates checkpoint 1 only after this audit
controller checkpoint passes ordinary CI. No P6-08 route, row, package, File
or UI action is active at the audit boundary.
