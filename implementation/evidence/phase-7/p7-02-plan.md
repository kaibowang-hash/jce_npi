# P7-02 Plan — Locked Inputs, Trial Actuals, Samples and Evidence

Recorded: `2026-08-10`

Status: `PASS — ALL FOUR CHECKPOINTS AND LEVEL 2 TASK GATE`

Starting controller checkpoint:
`fbac85b49b020a356554ab0e5540b8028ce5862f`

Retained product checkpoint:
`78efa3ec5c584928f510e4b095ead5a36f2fb376`

Primary requirements:

- `FR-TR-002`;
- `FR-TR-003`;
- `FR-TR-010`;
- `FR-NP-004`;
- `FR-NP-005`; and
- `FR-TX-019` foundation.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is `PASS`. P7-02 can
proceed without a new business decision if it preserves the accepted fail-
closed technical authority and the scoped external holds.

P7-01 provides immutable Plan revisions, one distinct planned Round, Project-
first authorization, exact Tooling Master containment, append-only lifecycle
events, actor-bound idempotency and a live trilingual Trial workspace. It does
not contain an input lock, actual execution context, versioned parameters,
Sample Batch, persisted Trial evidence or a transition beyond `planned`.

Phase 6 provides exact Part/Tooling Revision/physical Set/cavity/process-chain
identities, clean private File Revisions and a separated process-profile
foundation. Its Tooling engineering-control projection deliberately returns
`trialActual=not_measured`; the only live create path owns Customer Standard
rows, and its six comparable metric codes are not a complete Trial parameter
record. The deterministic Trial prototype and local photo selector remain UX
evidence only.

The controlled-document path already proves bounded multipart observation,
private Frappe File persistence, scanner-pending File Revision registration,
hash/size/MIME verification, orphan cleanup, audited access and no raw stable
URL. P7-02 reuses those security mechanics; it does not create a second file
system or weaken scan-state truth.

## 2. Frozen outcome

P7-02 delivers one minimum complete vertical slice:

> open one exact planned Round -> freeze one immutable input-lock revision over
> exact product/design, Part, Tooling Revision, physical Set/cavity/process,
> material, parameter-definition, inspection-document and controlled-evidence
> inputs -> atomically transition the Round to `prepared` -> start the exact
> prepared Round under the retained technical authority and freeze actual
> machine/material/environment context -> append immutable Trial Actual
> revisions with explicit measured/not-measured values, units, source,
> acquisition mode and timestamps -> create/revise exact Sample Batches with
> cavity, material, packaging, destination and feedback truth -> upload one
> bounded private file into scanner-pending state -> bind only an exact clean
> File Revision as Round/Sample evidence -> reopen the Trial workspace and
> observe versions, completeness, history, scan/capability and audit truth

P7-02 owns the single NPI Trial input/actual/sample/evidence fact layer. The
Tooling engineering-control page may read a derived `trial_actual` comparison
projection from this exact layer; it must not persist a competing Trial Actual
row or copy Customer Standard values into measured truth.

`FR-TR-010` advances only to a truthful manual-input foundation. Automatic
machine/acquisition-system import remains `unavailable` because there is no
approved source adapter, authentication, mapping or confirmation policy.

## 3. Domain invariants

### 3.1 Input-lock revision

- `TrialRoundInputLockRevision` is an immutable versioned aggregate bound to
  one exact Project, Plan revision and Trial Round. A later source never moves
  an existing lock to `latest`.
- The first lock requires exact server-resolved identities, versions and
  hashes for the current product/design baseline, Part Revision, Tooling
  Revision, physical Tooling Set, Tooling Set binding, cavity/insert and
  process-chain configuration, inspection plan/drawing or released controlled
  document, and every included controlled reference.
- Material/color/additive/batch truth is an NPI observation over a bounded
  source-system/object key, lot/batch code, label and actor/time. It never
  claims ERPNext Item/Batch verification, availability or reservation.
- The lock owns one closed parameter-definition set. Every definition has a
  stable key, category, value kind, unit where numeric, required flag and
  optional target/window. Actual revisions bind these definitions exactly;
  they cannot change the definition, unit or window.
- Drift is returned as an explicit difference. Preparing against stale,
  missing, cross-Project, ambiguous or hash-mismatched input fails closed.
- A successor lock is permitted only before execution under exact optimistic
  version/predecessor/hash and a non-empty reason. It appends history and never
  rewrites the first lock.

### 3.2 Round lifecycle and Trial Actual

- P7-02 activates only `planned -> prepared -> running`. It activates no
  `analysis`, `submitted`, `approved`, `rejected`, conclusion, Gate, quality or
  Tooling transition.
- `prepare` atomically validates the exact lock, appends a lifecycle event and
  updates only the guarded Round projection. `start` requires the exact current
  prepared lock and freezes the first actual execution context before appending
  the running event.
- `TrialRoundActualRevision` is immutable and versioned. It records actual
  machine/auxiliary references, material/batch observation, environment,
  operator/confirmation, source/acquisition mode, observed timestamps and one
  entry for every locked parameter definition.
- Public commands allow only `manual` acquisition. Controlled synthetic
  fixtures are separately marked and can run only on the disposable runtime.
  `machine_import` remains an unavailable capability and cannot be selected by
  the browser.
- A parameter entry is explicitly `measured` with exact value/unit/source/time
  or `not_measured`; absence, copied Standard value and empty string are not
  measurement. Successor actual revisions retain exact predecessor lineage.
- P7-04, not P7-02, owns conclusion submission and its critical-completeness
  decision. P7-02 exposes deterministic missing/available facts without
  claiming approval readiness.

### 3.3 Sample Batch and evidence

- `TrialSampleBatchRevision` has a stable immutable batch UUID and append-only
  revisions. It binds the exact Round, input lock, material batch observation,
  quantity, unique bounded label, defined cavity UUIDs, packaging, destination
  and customer-feedback text/source/time.
- Updating packaging, destination or feedback creates a successor revision;
  it never overwrites what was sent or observed. A count is never substituted
  for a Sample Batch identity.
- Trial evidence roles are exactly `photo`, `video`, `parameter_curve`,
  `measurement_report` and `customer_feedback`. An evidence reference binds
  one exact Round and optional exact Sample Batch revision to one exact clean,
  private, live File Revision plus immutable file hash/size/MIME metadata.
- Upload and evidence binding are separate. Upload observes bounded bytes,
  saves a private File and registers a scanner-pending File Revision. No
  evidence capability is implied until a separately authorized scanner marks
  that exact revision clean.
- Preview/download reauthorizes Project/Round/reference/File identity, scan
  state and hash, appends access audit and returns bytes directly. No response,
  snapshot or audit contains a raw private URL or bearer token.

## 4. Authorization, ownership and transaction boundary

- Existing Project visibility is required before resolving a Round, Plan,
  Part, Tooling, Set, cavity, document, material, Sample Batch or File identity.
- Until an approved production Trial responsibility policy exists, only an
  enabled same-tenant internal System Manager may prepare/start a Round, append
  Actual/Sample revisions, upload or bind evidence. This retains the P7-01
  technical boundary and is not a production-role decision.
- Every command uses exact optimistic version/predecessor/hash, a closed
  canonical payload, CSRF, actor-bound idempotency, one transaction, append-
  only audit and a sealed replay response. Same key/different payload fails.
- The browser cannot submit tenant, actor, hash, scan state, privacy, current
  lifecycle, derived completeness, file URL, automatic-import state, ERP
  verification, booking, approval or Gate effect.
- NPI One owns input locks, observed Trial Actuals, Sample Batches and Trial
  evidence references. Existing source aggregates retain their own truth;
  ERPNext retains formal master, Quality Inspection/NCR and production truth.

## 5. Corrected closed BFF boundary

The audit authorizes these bounded paths only after their checkpoint tests:

| Method and path | Purpose |
|---|---|
| `GET /projects/{projectId}/trial-rounds/{trialRoundId}/execution` | exact input-lock/actual/sample/evidence history, drift, completeness, capabilities and permissions |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}:prepare` | append exact input-lock revision and transition planned to prepared |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}:start` | freeze first actual execution context and transition prepared to running |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/actual-revisions` | append one exact Trial Actual successor |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/sample-batches` | create one stable Sample Batch and initial immutable revision |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/sample-batches/{sampleBatchId}/revisions` | append packaging/destination/feedback/sample truth |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/files` | bounded multipart private upload and pending File Revision registration only |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/evidence` | bind one exact clean private File Revision to Round/Sample truth |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/evidence/{evidenceId}:content` | audited exact-byte access with no redirect or stable URL |

The existing P7-01 Plan paths remain unchanged. P7-02 exposes no clone,
defect, conclusion, submission, approval, Gate, ERP quality, reservation,
machine-import or Tooling lifecycle command.

## 6. Additive persistence

Checkpoint 1 adds only four guarded DocTypes:

- `NPI Trial Input Lock Revision`;
- `NPI Trial Actual Revision`;
- `NPI Trial Sample Batch Revision`; and
- `NPI Trial Evidence Reference`.

The existing Trial Round, lifecycle event and command-idempotency objects are
reused. New objects use UUID identity, exact parent/version/hash fields,
canonical snapshot/hash, immutable or append-only controllers, System Manager/
NPI API create-only DocPerms and denied generic update/delete. Metadata creates
no business row, default policy, fixture, production mapping, adapter or
external call.

## 7. Checkpoints

1. **Domain/contract/additive metadata** — pure input-lock, actual, parameter,
   Sample Batch and evidence invariants; closed OpenAPI/ownership; four guarded
   DocTypes; direct translations and focused tests. No live route, business
   row, file write, UI or runtime fixture.
2. **Repository/BFF/private-file boundary** — Project-first reads and prepare/
   start/actual/sample/upload/evidence/content commands, exact containment,
   lifecycle, idempotency, transaction, audit, cleanup and route-switch tests.
3. **Live Trial execution workspace** — strict data source and dense
   trilingual locked-input/parameter/sample/evidence work area with loading,
   empty, pending-scan, read-only, permission, validation, conflict, processing,
   retry and unavailable-import states plus affected Linux visual evidence.
4. **Controlled runtime and Level 2** — disposable-Site prepare/start, Actual
   successor, Sample successor, pending upload, clean evidence bind/access,
   replay/conflict/rollback/IDOR/route recovery/migrations/redaction, no ERP/
   network/Outbox and cleanup; then trace, diff and Level 2 Task Gate.

Complete ordinary CI passes before every controlled-Site dispatch. The new
optimized `level_2_controlled` path may reuse only the exact successful prior
pull-request Gate after machine verification. Any unbounded public-contract,
permission or shared-infrastructure impact escalates to Level 3.

## 8. Requirement acceptance map

| Requirement | P7-02 evidence boundary |
|---|---|
| `FR-TR-002` | exact machine/material/product/Tooling/environment/parameter actual revisions; critical missing facts remain explicit and later block conclusion |
| `FR-TR-003` | bounded pending upload plus exact clean private evidence reference for photo/video/curve/report/feedback, bound to Round/Sample |
| `FR-TR-010` | explicit manual acquisition with source/time/confirmation and `machine_import=unavailable`; no false automatic-import claim |
| `FR-NP-004` | immutable parameter-definition/window lock and exact versioned Trial Actual successor chain |
| `FR-NP-005` | stable Sample Batch identity/revisions with quantity/cavity/material/packaging/destination/feedback trace |
| `FR-TX-019` | Trial is the single actual owner; Standard/Trial Actual/Approved Baseline stay disjoint and Tooling comparison is read-only derived truth |

Expected truthful Task-Gate disposition is
`TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD`. If a smaller
boundary remains incomplete, each Requirement keeps its narrower status; no
aggregate PASS may hide the hold.

## 9. Changed-files to affected-tests

| Surface | Required evidence |
|---|---|
| domain/contract/ownership | non-collapse, immutable successor/hash, closed schema, single owner and no Standard-to-Actual copy |
| DocTypes/controllers | additive migration, exact projection, generic mutation/delete denial, DocPerm and no seeded rows |
| repository/BFF | Project-first IDOR, reference containment, prepare/start state, stale/hash conflict, actor-bound replay, transaction/audit/rollback and independent switch |
| private upload/evidence | size/MIME/hash/privacy, pending/clean/infected/failed, orphan cleanup, exact Sample bind, no raw URL and audited content access |
| frontend | unit/state/keyboard/axe, direct English/zh/zh-TW, mixed-language scan, density/geometry and affected P7 visuals |
| runtime | two+ additive migrations, cumulative predecessor, fresh-process replay, route recovery, raw-log sentinels, no integration traffic and cleanup |
| trace/controller | six Requirement rows, current-task manifest, Task Diff Review and `git diff --check` |

## 10. Rollback

Before retained P7-02 rows, restore the starting checkpoint and migrate a
disposable Site fresh. After retained input/actual/sample/file/evidence/
lifecycle/receipt/audit history, disable only the independent P7-02 execution
routes/workspace and deliver a reviewed forward fix. Never delete files or
rewrite immutable snapshots, scan state, Round lifecycle or evidence to
simulate rollback.
