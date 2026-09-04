# P6-07 Plan — Controlled Tooling List Import

Recorded: `2026-08-09T03:50:21Z`

Starting product and synchronized controller checkpoint:
`25db3ae4b97ce47ca74424d6560691ee9a746b74`

Starting exact-SHA ordinary CI:
[`31292919974`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31292919974)
(`PASS`; repository `93193123207`, fixed-Linux visual `93193123198` at
`88/88`, controlled runtime correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN/EXISTING-CAPABILITY AUDIT;
DOMAIN/INSPECTION/METADATA FOUNDATION NEXT**

Requirements:

- `FR-TX-012..018`; and
- `UX-016` operation-specific durable asynchronous-job foundation.

Applicable Skills:

- `repo-discovery`;
- `npi-domain-guard`;
- `frappe-safe-change`;
- `xlsx-tooling-import`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Audited sources and repository facts

The audit used the Phase 6 Requirement anchor, reconciled DOCX rows and Pack
coverage, `TOOLING_LIST_IMPORT_SPEC.md`, the complete reviewed 43-column CSV,
Tooling domain and ownership specifications, Decision Requests
`DR-REC-007/008`, the R1-01 passive inspector and its adversarial tests, the
current private File Revision implementation and P6-01 through P6-06
repositories/evidence.

Repository truth is:

- the existing 531-line R1-01 inspector is a bounded, read-only security
  foundation. It hashes `.xlsx`, applies input/archive/XML/depth/row/cell/
  merge/image limits, rejects traversal, collision, encryption, macros/XLM,
  ActiveX, embedded binaries, DTD/entities and external relationships, and
  inventories sheets, formulas, safe error codes and floating anchors without
  logging cell contents;
- that inspector intentionally does not read business values, detect semantic
  regions, map the 43 columns, transform rows, create a preview, persist an
  import batch or execute an import. Runtime code must reuse its reviewed
  behavior inside the product App rather than importing an execution Skill
  path;
- `docs/reference/TOOLING_LIST_FIELD_MAPPING.csv` contains all 43 observed
  source columns and reviewed candidate targets, but remains a proposal. It
  does not authorize production customer aliases or decide whether numeric
  columns are Customer Standard, estimate, measured actual or calculated
  output (`DR-REC-007`);
- no customer workbook or sanitized `.xlsx` acceptance fixture is committed.
  The observed production workbook must not be committed or read by P6-07;
- immutable private File Revision identity, hash, confidentiality and clean
  malware-scan truth already exist. A browser URL, filename or local path is
  not accepted as source authority;
- P6-01 through P6-06 provide the distinct Project, Part/Part Revision,
  Tooling Requirement/Master/Applicability/Revision/physical Set/Cavity/
  Insert/process/capacity identities needed by an import. A spreadsheet row
  is not any of those aggregates;
- there is no import route, mapping activation row, inspection/preview/batch/
  row-result DocType, worker, correction artifact or rollback command;
- the current Tooling idempotency aggregate is scoped to existing Tooling
  commands and cannot be silently overloaded with an unrelated asynchronous
  batch protocol; and
- no production ERPNext endpoint or write is needed. P6-07 imports NPI-owned
  engineering facts only. ERP-owned Asset, location, inventory, maintenance,
  formal quality, purchasing, manufacturing and cost truth remains outside
  this task.

The safe implementation is additive and needs no architecture ADR. Production
semantic activation and downstream-used destructive rollback stay closed,
but passive inspection, immutable provenance, proposal mechanics, validation,
preview, a visibly synthetic controlled execution, partial results, safe
retry and rollback denial can continue.

## 2. Truthful completion boundary

P6-07 delivers this minimum complete vertical slice:

> select an authorized exact clean private File Revision -> create an
> immutable import batch bound to its content hash -> safely inspect archive,
> sheets, formulas and image anchors -> detect title/header/data/shared-
> Tooling/summary regions without fixed row numbers -> compare every detected
> source column with one exact versioned mapping revision -> retain raw values
> while producing bounded transformations and validation findings -> show an
> immutable create/update/skip/confirmation preview -> execute only when an
> exact server-authorized mapping activation exists -> expose a durable
> asynchronous job with per-row/per-field partial truth -> generate an
> authorized correction artifact -> retry only failed eligible rows -> permit
> rollback only for batch-created unused objects and otherwise record an
> explicit audited denial

The production App has no installed customer mapping. Its default state is
therefore inspect/preview-capable with execution unavailable. Controlled Site
proof seeds one visibly synthetic, fixture-scoped mapping activation after
migration; it is not a migration default and cannot authorize another
customer, Project, source hash or production context.

Expected evidence-driven trace truth at Level 2 is:

- `FR-TX-012..018`: `TECHNICAL_VERIFIED_FOUNDATION` for the complete controlled
  import mechanics and synthetic runtime proof; production semantic activation
  remains held by `DR-REC-007`; and
- `UX-016`: `TECHNICAL_VERIFIED_FOUNDATION` for this operation-specific
  durable queued/processing/partial/success/failure/retry/result-log surface.
  Phase 8 still owns the shared cross-operation job center and ERP execution
  truth represented by canonical `FR-UX-012`.

## 3. Explicit non-scope and held behavior

P6-07 does not:

- commit, sanitize by assumption, print or export the observed production
  customer workbook;
- install a production customer mapping, infer A/B/C meaning or classify an
  ambiguous numeric column as standard/estimate/actual/calculated output;
- treat a blank cell, merged region, formatting, prior row, remark or image
  proximity as authority for a relationship;
- execute formulas, trust cached formula values, fetch external content,
  accept macros or emit raw confidential cell values to ordinary logs;
- copy Customer Standard into Trial Actual or Approved Process Baseline,
  create a physical Set from a planned copy count or duplicate a shared
  Tooling Master per Project;
- change Tooling lifecycle, Gate, approval, Trial, formal quality, Asset,
  location, inventory, maintenance, procurement, manufacturing or cost truth;
- contact ERPNext, create an Outbox message or add a production credential;
- delete or rewrite downstream-used data; or
- deliver the generic Phase 8 asynchronous job center, publish/reconciliation
  adapters, P6-08 export or any Phase 7 behavior.

## 4. Frozen domain and provenance model

### 4.1 Source and inspection

`ToolingImportBatch` has one stable UUID identity and binds one authorized
Project/customer scope, exact private clean File Revision UUID/version/hash,
source filename/media type, actor, request/trace identity and creation time.
The source binding never changes.

`ToolingImportInspectionRevision` is immutable and retains inspector policy
version, archive limits/report, worksheets, detected regions and columns,
formula/error inventory, drawing/image anchors, rejected-safety findings and a
canonical report hash. Unsafe files fail closed before business values are
persisted. The business reader shares the same prevalidated archive manifest
and bounded XML policy; it does not reopen unchecked members.

Detection is content/structure based. It records evidence for each proposed
title/header/data/shared/summary region plus a confidence and required-human-
confirmation state. Row numbers are results, never configured defaults.

### 4.2 Versioned mapping and transformation

`ToolingImportMappingRevision` is immutable and contains all detected source
columns, including explicitly `unmapped` columns. Every entry retains source
header/ordinal, target aggregate/field candidate, transformation key/version,
validation rule keys, semantic classification and review state. Removing a
column, silently changing its meaning or activating a proposal in place is
forbidden.

Mapping state is one of `proposal`, `approved_fixture` or
`approved_production`. P6-07 can create proposals. Only a server-side mapping
authority may create an activation that binds exact customer, template,
mapping revision/hash, source signature and effective window. The live
production authority returns unavailable until `DR-REC-007` is resolved.
Controlled proof may seed only `approved_fixture` for the named sanitized
fixture and synthetic Project/customer.

Transformations are closed, deterministic functions. They retain worksheet,
row, source column, raw typed value, normalized candidate, transformation
key/version and all findings. They may split bounded multi-values, separate
state text from identifier candidates and parse a value/unit candidate, but
never discard the raw value or infer relationships/semantics.

`A/B/C` is retained only as `Legacy Grade`. `New Tooling` remains raw and may
become a separate candidate state while being excluded from a candidate
Tooling number. `#REF!` and other formula errors remain validation errors and
never become an approved calculated value.

### 4.3 Immutable preview and confirmations

`ToolingImportPreviewRevision` binds exact source, inspection and mapping
revision/hash plus transformation policy version. It retains every source row
and field outcome, candidate action (`create`, `update`, `skip` or `blocked`),
candidate target identities, warnings/errors and required confirmations.

Image candidates use bounded deterministic facts and retain drawing/image
relationship, worksheet anchor, candidates and confidence. Ambiguous images
and relationships are always blocked until a Project-authorized human records
the selected exact target, actor, time and reason in a successor preview.

Preview creation never mutates a Tooling aggregate. It exposes execution
eligibility and every reason for denial. An eligible preview must have no
unconfirmed relation/image, no unmapped required source column, no unsafe
formula value, and one exact active mapping authorization.

### 4.4 Asynchronous execution and partial truth

Execution creates one durable job and enqueues it only after the request
transaction commits. The worker reauthorizes the preserved actor, Project,
customer, source File Revision/hash, mapping activation and exact preview/hash
before every bounded run. It never accepts a caller-selected operation or raw
target payload.

Job states are `queued`, `processing`, `partially_succeeded`, `succeeded`,
`failed_retryable`, `failed_final`, `rolled_back` or `rollback_denied`.
Terminal success is impossible while an item is failed or awaiting
confirmation. Each immutable row result records create/update/skip/error,
each field result, exact target object/version/hash when applicable, stable
code, complete English source message, request/trace identity and source
provenance.

Actor-bound idempotency seals exact command, batch, preview, expected version
and payload hash. Replay returns the original sealed receipt; key reuse with a
different actor or payload conflicts. Retry creates a successor attempt for
only failed retryable rows and cannot repeat successful mutations.

### 4.5 Correction, reconciliation and rollback

Correction output is a newly registered private artifact whose CSV columns
are allowlisted. It contains stable row/field codes and authorized correction
values only; confidential raw fields are omitted or redacted. Every download
is permission checked and audited.

Reconciliation proves each created/updated object against batch, worksheet,
row, source column/raw-value hash, transformation version, mapping revision
and execution result. Missing or changed targets are explicit discrepancies,
not silently repaired.

Rollback eligibility is computed server-side. P6-07 permits reversal only for
an object created solely by the exact batch, still at its exact imported
version/hash and with zero downstream references. Updated pre-existing
objects, changed objects and any downstream-used object are denied and require
forward correction. A denial is a durable audited result, not an exception
hidden in logs. This implements the safe `DR-REC-008` default without
inventing a broader destructive cutoff.

## 5. Sanitized acceptance fixture

Checkpoint 1 adds a deterministic fixture builder, fixture manifest and exact
SHA-256 expectation. It uses only visibly synthetic names/identifiers and
creates no customer-derived values. The generated workbook covers inserted
and deleted title-row variants, data/shared/summary regions, multi-line
identifiers, state text in the Tooling-number column, `#REF!`, missing required
values, mixed units, undefined A/B/C, dual-shot/overmold and insert notes, one
confident and one ambiguous floating image.

The builder uses the standard library and deterministic ZIP/XML metadata so
CI can prove the exact artifact without adding a production dependency or an
opaque binary source. Its manifest records purpose, synthetic provenance,
generator version and expected hash. The production/customer workbook remains
absent.

## 6. Security and authorization invariants

- All routes are Project-first, authenticated and independently fail closed.
- System Manager remains the management transport authority; Project/customer
  membership, File confidentiality/clean status and target containment are
  rechecked server-side.
- Browser input contains UUIDs, expected versions/hashes, bounded decisions
  and acknowledgement only. It never carries a filesystem path, arbitrary
  aggregate payload, target SQL name, trusted actor, mapping approval or job
  state.
- Raw workbook values are absent from standard logs, trace messages and audit
  summaries. Detailed values are returned only through authorized batch
  detail/correction surfaces.
- Archive and XML limits apply before allocation-heavy work. Worker processing
  is bounded by rows/fields/images and can resume only from durable row truth.
- Metadata migration is additive and guarded. It installs no business batch,
  customer mapping, fixture activation, job or default business rule.
- No production ERPNext network path, endpoint, credential, adapter or Outbox
  row is reachable.

## 7. Five serial implementation checkpoints

### Checkpoint 1 — domain, passive inspection, contracts and guarded metadata

- move the reviewed passive-inspection behavior into a product-owned Tooling
  import module and keep the execution-Skill wrapper compatible;
- add pure source/inspection/mapping/transformation/preview/job/result/
  rollback domain types and invariants;
- add the deterministic sanitized fixture builder and manifest;
- close OpenAPI/ownership schemas and guarded additive DocTypes without routes
  or business rows;
- add stable receipt values and complete direct English/`zh`/`zh-TW` message
  coverage; and
- prove archive/XML safety, position-independent detection, all 43 columns,
  raw retention, state/grade/formula/image behavior and immutability.

### Checkpoint 2 — repository and inspect/map/preview BFF

- activate only bounded Project-first source registration, batch/detail,
  inspect, mapping-proposal and immutable preview/confirmation routes behind
  an independent default-closed switch;
- implement exact File/customer/Project authorization, mapping activation
  provider, one-transaction append, audit and actor-bound idempotency;
- expose production mapping as unavailable by default; and
- prove permission, IDOR, replay, conflict, rollback, raw-log redaction and
  no-target-mutation behavior.

### Checkpoint 3 — bounded worker, partial result, correction, retry and rollback

- add after-commit enqueue plus a resumable bounded worker and immutable
  row/field result persistence;
- create/update only exact NPI-owned targets authorized by an exact active
  mapping, with a synthetic controlled mapping seed outside migrations;
- add durable status/detail, correction artifact, retry, reconciliation and
  eligibility/rollback commands;
- prove partial success, no duplicate successful mutation, retryable/final
  failure, rollback-allowed for unused batch-only objects, rollback denial for
  changed/downstream-used objects, worker reauthorization and no ERP contact.

### Checkpoint 4 — live industrial import workspace

- implement the dense eight-step selected-Project import workspace with stable
  step rail, table/tree work area, inspector, progress/result strip and one
  primary action per context;
- show mapping-unavailable, confirmation-required, loading, empty, no-
  permission, read-only, conflict, queued/processing/partial/success/
  retryable/final/rollback states without color-only meaning;
- provide authorized correction download/retry/rollback-denial details; and
- pass direct English/`zh`/`zh-TW`, mixed-language, keyboard, focus, component,
  browser and fixed-Linux visual checks.

### Checkpoint 5 — cumulative controlled Site and Level 2 Task Gate

- extend the disposable-Site verifier and controlled workflow through P6-07;
- generate/inspect the exact sanitized fixture, seed only synthetic mapping
  authority and exercise detect/map/preview/confirm/execute/partial/retry/
  reconcile/rollback-allowed/rollback-denied truth across fresh and
  cross-process requests;
- prove migration, route-disable/recovery, permission/IDOR, no raw-log leak,
  no production mapping/ERP network and cleanup; and
- run complete ordinary CI, controlled Site, Requirement reconciliation and
  the P6-07 Level 2 Task Gate before activating P6-08.

No checkpoint is authorization for the next. Each transition requires exact-
SHA evidence and a controller update. A failing CI or controlled Site opens
only a bounded diagnostic/repair loop under the frozen contracts above.

## 8. Changed-files to affected-tests map

| Change family | Required affected verification |
|---|---|
| Inspector/domain/fixture | passive adversarial suite; P6-07 domain, detection, mapping, validation, preview and deterministic fixture tests |
| DocTypes/hooks/contracts/ownership | metadata, schema, ownership, forbidden-default, migration and direct translation tests |
| Repository/BFF | repository, API, permission, CSRF, IDOR, replay/conflict/rollback, audit and no-network tests |
| Worker/results/correction | bounded worker, partial/retry/idempotency, artifact authorization/redaction, reconciliation and rollback eligibility tests |
| Frontend | focused unit/type/lint/i18n/accessibility and affected Playwright/visual matrix |
| Controlled verifier/controller | verifier unit, full tracked Python, complete repository CI and disposable-Site runtime |

If a shared File, Tooling, job, translation or design-system change makes the
impact boundary unreliable, verification escalates to Level 3 rather than
guessing.

## 9. Principal risks and rollback

- unsafe XLSX content or resource exhaustion: retain the passive fail-closed
  limits and prevalidated member manifest;
- guessed semantics/relationships: persist proposals and confirmation gates;
  default production execution remains unavailable;
- partial-job false success or duplicate mutation: immutable per-row truth,
  sealed idempotency, exact target versions and terminal-state derivation;
- confidential value leakage: raw-value access control, hashed audit summary,
  allowlisted correction columns and log tests;
- ambiguous floating images: candidate-only detection and mandatory human
  confirmation;
- destructive rollback: permit only exact unchanged batch-created unused
  objects and otherwise record `rollback_denied`; and
- queue interruption: durable state and bounded successor retry rather than
  resetting or replaying successful rows.

Rollback for any checkpoint is a reviewed forward change: disable the P6-07
route/worker switches, retain immutable source/mapping/preview/job/audit rows
and remove no schema or imported downstream-used object. Production mapping
and ERP contact remain absent throughout.
