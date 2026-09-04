# P6-05 Repository and API Checkpoint

Recorded: `2026-08-08T18:42:56Z`

Status:
`PASS — LEVEL 1 REPOSITORY, BFF AND CLOSED UNAVAILABLE DEPENDENCY BOUNDARY`

Requirements:
`FR-TX-009`, `FR-TX-010`, `FR-TX-011`, `FR-TX-019`, `FR-TX-020`,
`FR-TL-009`, `FR-TL-010`, `FR-TL-017`, `FR-TL-018`

Exact product checkpoint:
`6207072f643dc422cbb3be0cd07217183c824610`

## Delivered boundary

- Activated exactly four independently guarded P6-05 routes: one bounded
  Project-first engineering-controls read and three immutable append commands
  for defect, Customer Standard process-profile and capacity-scenario
  revisions.
- Added a dedicated engineering-controls repository before the existing
  Tooling repositories in method resolution. It reuses the established
  command transaction boundary and adds no independent commit or rollback.
- Every command authenticates the Project and exact Tooling Master before body
  validation, requires System Manager as management transport, binds
  idempotency to the authenticated actor and retains receipt, audit and sealed
  replay truth in one transaction.
- Defect append re-resolves the exact predecessor, responsible Project member,
  Tooling context, clean private File evidence and optional target-round
  intention. Severity and explicit blocking intent remain separate stored
  facts; neither creates or mutates a Domain Work Item or Gate.
- Customer Standard process-profile append re-resolves the exact Tooling
  Revision and predecessor. Trial Actual remains `not_measured` and Approved
  Baseline remains `unavailable`; neither value can be supplied by the caller.
- Capacity append re-resolves exact Tooling Revision, Part Revision,
  Applicability, Set and predecessor containment, then derives every output
  server-side under published `capacity.v1`, visible `3600` conversion and
  `decimal-6-half-even` result rule.
- Reads are bounded and project-scoped, preserve append-only lineage and return
  only closed public response fields. Exact dependency snapshots remain in the
  immutable row and audit evidence.
- Added closed OpenAPI paths, requests, responses and schemas plus domain,
  repository, contract, API, permission, IDOR, replay, conflict, rollback,
  no-fake-actual and no-ERP-write tests.

## Deliberately unavailable

- The live SPA remains inactive at this checkpoint. No engineering-control
  command is exposed to a normal user until the trilingual workspace passes
  its affected state, accessibility and visual checks.
- Trial Actual is exactly `not_measured`; no Trial aggregate or observation is
  fabricated. Approved Process Baseline is exactly `unavailable`; no approval,
  release or copy-from-standard command exists.
- ERPNext/IoT shot count, calibration, maintenance and computed health remain
  explicitly unavailable. There is no production endpoint, credential,
  adapter, read, write, dispatch, retry, replay or successful target fixture.
- Defect severity does not imply blocking, create a Project Work item, change a
  Gate, or advance Tooling Requirement, Revision or Set lifecycle.
- Production exception-color semantics remain held by `DR-REC-002`; the API
  exposes textual state only. Exact lifecycle and manufacturing authority
  remain held by `DR-REC-010`.
- This is checkpoint 2, not the P6-05 Level 2 Task Gate. The live workspace and
  disposable controlled-Site evidence remain required.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/engineering_controls_repository.py` and Tooling repository composition | append-only defect/process/capacity persistence, predecessor and dependency resolution, bounded read, membership/evidence/Part/Applicability/Set containment, server-derived capacity outputs, transaction/audit/receipt order, replay/conflict/rollback and IDOR cases in `test_phase6_tooling_engineering_controls_repository.py` |
| `tooling_api.py`, `request_security.py`, `bff.py`, errors | exact four-route dispatch, Project-first authorization, strict body parsing, independent fail-closed switch, System Manager command transport, safe errors and no sibling-route regression in `test_phase6_tooling_api.py` |
| engineering-controls domain and OpenAPI | negative-zero canonicalization, closed caller inputs/server outputs, fixed paths and complete reference traversal in `test_phase6_tooling_engineering_controls_domain.py` and `test_phase6_tooling_engineering_controls_contract.py` |
| complete repository | clean exact-SHA CI repository, non-visual browser, history-secret and visual jobs below |

## Local affected and regression evidence

- relevant Python compilation: PASS;
- focused engineering-controls repository/API/contract/domain set: `45/45`
  PASS;
- complete Phase 6 Tooling discovery: `162/162` PASS;
- complete local Python discovery: `1,249/1,249` PASS, including six
  pre-existing user-owned untracked local-prerequisite tests;
- OpenAPI parse/reference traversal: PASS — `90` paths, `398` schemas,
  `1,905` resolved internal references and `103` unique operation IDs;
- V1.2 reconciliation and `git diff --check`: PASS;
- P0 visual-governance verifier: PASS — all eighteen fixed-Linux governed
  baselines remained byte-exact; and
- no production ERPNext/IoT endpoint, credential, read, write, target result,
  Trial fabrication, Gate mutation or lifecycle command was introduced.

## Exact-SHA ordinary CI

Ordinary CI `31272151598` passed exact product checkpoint `6207072`:

- repository job `93139826646`: PASS — complete repository verification,
  `1,243` tracked Python tests, `756` frontend unit tests, `326` non-visual E2E,
  `4,795` literal English sources at 100% direct `zh`/`zh-TW`, statements
  `80.03%`, zero dependency vulnerabilities and both current/history secret
  lanes;
- visual job `93139826601`: PASS — `82/82` fixed-Linux governed cases;
- controlled runtime job `93139826885`: correctly skipped because the live
  workspace and runtime checkpoint are not active;
- visual artifact `9025961533`, digest
  `sha256:d2c0c38d3f75b7df1572aac67701e60d54a00c18d3d0b97838bfb4f1420a0952`;
  and
- Gitleaks artifact `9026031821`, digest
  `sha256:709646e7b609d9573420d23252b682671cd826b0a7024a91ee71409c667f8713`.

No catalog source or visual surface changed in checkpoint 2, so every existing
governed visual passed without baseline repair.

## Review, rollback and next checkpoint

The active routes are independently fail-closed by
`npi_p6_05_routes_disabled`; missing or non-false configuration disables only
P6-05. Rollback disables those routes and unavailable dependency readers,
preserves every immutable defect/process/capacity row, audit and receipt, and
uses a reviewed forward repair. It does not alter P6-01 through P6-04 objects,
controlled Document or Gate lifecycle, Trial truth or any ERPNext object.

Checkpoint 2 is PASS. P6-05 remains in progress. Autopilot next implements
only checkpoint 3: the strict engineering-controls data source and dense live
selected-Master workspace with defect/action/verification, three fixed process
fact columns, input-versioned capacity scenarios and separate unavailable
health presentation; complete loading/empty/no-permission/read-only/
unavailable/not-measured/validation/conflict/processing/retry states; complete
direct English/`zh`/`zh-TW`; keyboard/accessibility checks; and affected visual
evidence. Trial/Gate/lifecycle/ERP/IoT writes, deterministic prototypes and the
controlled Site remain inactive until that checkpoint passes.
