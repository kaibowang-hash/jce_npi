# P6-07 Level 2 Validation — Controlled Tooling List Import

Recorded: `2026-08-09T19:14:27Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`d8e4897ed7a47ef61e5112ce628115d3bb051ef7`

Requirements:
`FR-TX-012`, `FR-TX-013`, `FR-TX-014`, `FR-TX-015`, `FR-TX-016`,
`FR-TX-017`, `FR-TX-018`, `UX-016`

## 1. Outcome

P6-07 delivers the frozen minimum complete vertical slice for controlled
Tooling List XLSX import:

- passive bounded XLSX archive/XML inspection of exact clean private File
  Revision bytes, with position-independent region detection and no formula,
  macro, external-link or relationship execution;
- immutable source, inspection, 43-column mapping proposal, preview,
  confirmation, job, row/field result, correction, reconciliation and target-
  binding truth;
- explicit Project-authorized confirmation for ambiguous image and
  relationship candidates before execution;
- bounded asynchronous execution with durable partial success, failed-row-
  only retry and no repeat of successful target mutations;
- allowlisted private correction CSV artifacts with exact file identity,
  byte length, BOM, SHA-256, audited download and immutable binding;
- rollback only for unchanged objects created solely by the exact batch with
  no downstream references, plus durable denial for downstream-used targets;
  and
- a dense eight-step English, Simplified-Chinese and Traditional-Chinese
  selected-Project workspace that exposes server truth without inventing
  mapping, target, rollback or ERP authority.

Production mapping remains unavailable under `DR-REC-007`. The only active
mapping in controlled proof is bound to the generated visibly synthetic
fixture. No customer workbook, production or sandbox ERPNext endpoint,
credential, network request, Outbox message or formal ERP target truth was
created. `DR-REC-008` continues to deny destructive downstream rollback.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TX-012` | `TECHNICAL_VERIFIED_FOUNDATION` | Passive position-independent inspection and immutable exact-byte provenance are live for sanitized XLSX sources. |
| `FR-TX-013` | `TECHNICAL_VERIFIED_FOUNDATION` | All 43 reviewed columns, raw values, formula errors, states, grades and image anchors retain provenance without executing formulas. |
| `FR-TX-014` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable proposal/preview and explicit ambiguous-image/relationship confirmation are live; production semantic approval remains held. |
| `FR-TX-015` | `TECHNICAL_VERIFIED_FOUNDATION` | Bounded execution persists immutable per-row/per-field partial truth and exact target bindings. |
| `FR-TX-016` | `TECHNICAL_VERIFIED_FOUNDATION` | Allowlisted correction export/download and failed-row-only retry are live with successful-row non-duplication. |
| `FR-TX-017` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable reconciliation and strict rollback eligibility/denial are live under the safe default. |
| `FR-TX-018` | `TECHNICAL_VERIFIED_FOUNDATION` | Project-first authorization, actor-bound replay, route recovery, redaction and no ERP traffic are runtime proven. |
| `UX-016` | `TECHNICAL_VERIFIED_FOUNDATION` | Durable import-job progress, results, retry, reconciliation and rollback truth are live; the shared Phase 8 execution-job center remains held. |

The 282-row trace and reconciliation verifier now enforce these exact states
and evidence sets. No production mapping, ERP execution or shared Phase 8 job
truth is mislabeled complete.

## 3. Ordinary, visual and controlled Gates

Exact-SHA ordinary pull-request CI `31330677928` passed:

- repository `93288333713`: `1,363/1,363` tracked Python tests, `796/796`
  frontend unit tests in `50/50` files, `343/343` non-visual E2E, statements
  `80.00%`, clean production build, zero-vulnerability complete/production
  audits and both current-tree/full-branch Gitleaks lanes;
- i18n audit: `5,553` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage; and
- visual `93288333688`: fixed-Linux governed matrix `91/91` PASS.

Ordinary visual artifact `9042864675` has digest
`sha256:33d0032670a98d32fd14c7f2f318ad7f27cfd24df5ec53571c2e10b36518bd41`.
Ordinary Gitleaks artifact `9042931934` has digest
`sha256:943ba30a4dc86d584a173d819563163696e36dc27d44fc7ec582468401ca08e6`.

Final unchanged workflow `31330684809` retained the same exact SHA and passed
repository `93288346191`, visual `93288346156` at `91/91`, and controlled
runtime `93288346195`. Runtime artifact `9042876293`,
`p6-tooling-runtime-31330684809`, has digest
`sha256:ba966c30fd334e5572d8fe88f23c175f76413d2e5f8234467651aa87f3be562f`.
Its summary records `result=PASS`, exact head SHA, Site `npi.localhost`,
database `npi_one_runtime`, fixed Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1` and cumulative scope
`p5-01-through-p6-07`.

Final visual artifact `9042865852` has digest
`sha256:122261b42be4f552de310d1a0b9b57b79c2af486acdcd60a4c2b7d4384b969a9`.
Final Gitleaks artifact `9042940761` has digest
`sha256:4fa443c07e296b60f19f658cf56b7fbddd1632343895a7416c846399052236bb`.

## 4. Controlled truth and negative matrix

The cumulative disposable Site proves two sanitized 43-column fixtures with
different title-row positions through source registration, passive inspection,
mapping proposal/activation, preview, confirmation, execution, partial result,
correction artifact download, retry, reconciliation and both rollback paths.
The retained truth includes:

- three preview rows per scenario; one initially created target and two exact
  retryable failures per scenario;
- correction of only both failed validation inputs and five immutable row
  results per scenario after retry, with no duplicate successful mutation;
- one rollback-allowed result for unchanged batch-created unused targets and
  one durable rollback-denied result after an exact downstream reference;
- same-process and cross-process sealed replay of source, inspection, mapping,
  preview, confirmation and execution without cardinality changes;
- idempotency conflict, stale version/reference, permission, IDOR, generic
  mutation, route-disable and route-recovery denial paths;
- exact correction File identity/privacy/name/Frappe-size representation plus
  true UTF-8 byte size and SHA-256 checks; and
- zero production mapping activation, ERP integration traffic or raw fixture
  sentinel leakage outside authorized import surfaces.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Passive XLSX reader, fixture and immutable domains | safety, archive/XML, domain, fixture-manifest and 43-column mapping tests |
| Guarded DocTypes and additive migration | metadata/controller, generated catalog, additive/idempotent migration and controlled-Site tests |
| Repository, BFF, worker and route switch | repository/API/execution suites plus authorization, replay, conflict, transaction, partial/retry/reconcile/rollback and IDOR |
| OpenAPI, ownership and receipt values | closed-schema, exact-ownership and no-production-authority assertions |
| Data source, workspace, styles and catalogs | `796/796` unit, `343/343` browser, i18n/UI/accessibility audits and `91/91` Linux visuals |
| Runtime verifier and workflow | `70/70` focused Tooling-import regressions plus exact-SHA ordinary and cumulative controlled Gates |
| Trace/controller/evidence | 282-row uniqueness, P6-07 evidence-set reconciliation, YAML parse, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and repair analysis

The bounded review covers `25db3ae..d8e4897`: `130` files, `30,224`
insertions and `4,272` deletions across `43` task commits. Every commit belongs
to one frozen P6-07 checkpoint, an evidence-only reviewed Linux baseline sync,
or a serial evidence-proved controlled-runtime repair. No user-owned dirty,
Darwin, local-runtime or untracked file appears in a task commit.

The controlled boundary exposed later paths that ordinary mock/unit evidence
could not reach. Repairs were grouped by exact proven root:

1. preserve the generated workbook's exact private File identity/name and
   use deterministic UUIDv4 identities accepted by the domain;
2. resolve stable Project/Part references after import-created target growth
   and hash immutable row-result payloads before insertion;
3. correct both deliberately invalid fixture fields while retaining partial
   truth and isolate exact target/correction persistence substages;
4. bind correction artifacts to exact Frappe File truth, normalize the pinned
   Frappe text representation while preserving BOM, and distinguish Frappe
   character count from authoritative UTF-8 byte length and digest;
5. use UUIDv4 reconciliation request identity, a valid alternate reference
   for idempotency-conflict proof and the exact ten-row immutable retry
   cardinality;
6. decouple route/replay probes from the pre-import single-Part fixture and
   retain the exact Project identity across processes; and
7. reconstruct confirmation replay from only the eight allowed command input
   fields, then query an exact sealed receipt after Project/batch authorization
   but before the now-mutated latest-preview version check.

Each repair advanced the same controlled path; earlier roots did not recur.
The final workflow passed with diagnostic activations closed. No Requirement,
public route, permission, ownership, Schema, transaction, idempotency, audit,
visual matrix, threshold or PASS rule was weakened.

## 7. Security, migration, rollback and limitations

- Authorization precedes protected Project/batch/object resolution. Commands
  require the closed transport, CSRF, exact tenant/Project/customer/File
  containment and actor-bound idempotency.
- Generic Desk writes, cross-Project references, stale snapshots, altered
  replays, unconfirmed candidates and route-disabled commands fail closed.
- Audit/ordinary logs contain structural hashes and counts rather than raw
  workbook values; correction content requires the exact authorized private
  artifact route and is audited.
- Migration is additive/idempotent and the controlled Site passed two
  migrations before the full cumulative lifecycle.
- Before retained use, task commits may be reverted. After retained rows,
  rollback disables the independent P6-07 routes/worker and uses a reviewed
  forward repair; it never deletes or rewrites immutable source, result,
  audit, receipt, correction or reconciliation truth.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not fail a Gate.
- Customer workbooks, production semantic mapping approval, production or
  sandbox ERPNext access, shared Phase 8 job-center aggregation and destructive
  rollback after downstream use remain unavailable.

## 8. Decision and transition

P6-07 passes its Level 2 Task Gate. Standing transition authority activates
only the bounded P6-08 Requirement/domain/existing-capability audit for
controlled selection/filter and object-package export. It must not become an
arbitrary database dump or expose raw private File URLs, and it cannot weaken
the production mapping, ERPNext or rollback holds retained above.
