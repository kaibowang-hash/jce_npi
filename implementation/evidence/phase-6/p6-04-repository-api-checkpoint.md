# P6-04 Repository and API Checkpoint

Recorded: `2026-08-08T13:23:38Z`

Status:
`PASS — LEVEL 1 REPOSITORY, BFF AND CLOSED READ-ONLY ERP BOUNDARY`

Requirements:
`FR-TL-005`, `FR-TL-006`, `FR-TL-007`, `FR-TL-008`

Exact product checkpoint:
`5a925693ffef317b0cb8adde7924eeee78b88e2d`

## Delivered boundary

- Activated exactly four independently guarded P6-04 routes: bounded Project-
  first plan-history read, exact plan-revision read, immutable plan append and
  exact milestone-observation append.
- Added a dedicated manufacturing repository before the existing Tooling
  revision repository in method resolution. It reuses the established command
  transaction boundary and adds no commit or rollback of its own.
- Every command authenticates the Project and exact Tooling Master before body
  validation, requires System Manager as management transport, binds
  idempotency to the authenticated actor and retains receipt, audit and sealed
  replay truth in one write transaction.
- Plan creation re-resolves exact Tooling Revision hash/member/lifecycle,
  controlled-document release event/hash/File evidence and predecessor
  lineage. Observation creation re-resolves the exact plan, milestone,
  reporter membership, evidence containment and observation predecessor.
- Reads are bounded to `200` plans, `1,000` observations, `500` Project
  members and two exact Tooling lifecycles. API responses select only closed
  public contract fields while the complete immutable snapshot remains in the
  audit record.
- Added a dependency-injected, strictly read-only procurement/cost reader.
  Production supplies no reader, so the exact default is the closed ERPNext
  unavailable branch. The implementation contains no ERP endpoint,
  credential, write, dispatch, retry, replay or portal capability.
- Added closed OpenAPI paths, requests, responses and schemas plus repository,
  contract, API, permission, IDOR, replay, conflict, rollback and no-ERP-write
  tests.

## Deliberately unavailable

- The live SPA remains inactive at this checkpoint. No plan or observation
  command is exposed to a normal user until the trilingual workspace passes
  its own affected state, accessibility and visual checks.
- `designReleaseEvidence` is recomputed from exact released controlled-
  document truth. It does not release the Tooling Revision or authorize
  manufacturing.
- `manufacturingAuthorization` remains exactly `unavailable` under
  `DR-REC-010`; no caller approval, G3 pass, funding, PO-readiness or start-
  manufacturing flag is accepted.
- Formal Supplier, PO, receipt, invoice and actual-cost truth remains ERPNext-
  owned and read-only. No production adapter, connection, target row or
  successful target result was added.
- Supplier-responsible milestones are still reported by authenticated internal
  Project members. There is no external principal, supplier login, upload or
  supplier-submitted claim.
- This is checkpoint 2, not the P6-04 Level 2 Task Gate. The live workspace and
  disposable controlled-Site evidence remain required.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/manufacturing_repository.py` and Tooling repository composition | immutable plan/observation persistence, predecessor/hash/dependency resolution, bounded reads, exact membership/evidence/release containment, read-only ERP injection, transaction/audit/receipt order, replay/conflict/rollback and IDOR cases in `test_phase6_tooling_manufacturing_repository.py` |
| `tooling_api.py`, `request_security.py`, `bff.py`, errors | exact four-route dispatch, Project-first authorization, independent fail-closed switch, System Manager command transport, safe errors and no sibling-route regression in `test_phase6_tooling_api.py` |
| OpenAPI | fixed paths, closed request/response/reference traversal and no Supplier/ERP mutation contract in `test_phase6_tooling_manufacturing_contract.py` |
| complete repository | clean exact-SHA CI repository, non-visual browser, history-secret and visual jobs below |

## Local affected and regression evidence

- relevant Python compilation: PASS;
- complete Phase 6 Tooling discovery: `127/127` PASS;
- focused new repository/API/contract set: `33/33` PASS;
- complete local Python discovery: `1,214/1,214` PASS, including six
  pre-existing user-owned untracked local-prerequisite tests;
- OpenAPI parse/reference traversal: PASS — `86` paths and `364` schemas;
- frontend generation/check, TypeScript, ESLint, formatting, style, boundary,
  industrial-UI and i18n audits: PASS — `4,528` governed sources with complete
  direct `zh` and `zh-TW` coverage;
- frontend unit suite: `744/744` PASS, statement coverage `80.07%`, and Vite
  product compilation: PASS;
- P0 visual-governance verifier and prototype-approval verifier: PASS;
- V1.2 reconciliation and `git diff --check`: PASS; and
- no production ERP endpoint/credential/write/portal or prohibited security
  pattern found in the checkpoint diff.

The local build's final static-asset guard continued to report only the
pre-existing user-owned untracked
`frontend/public/images/npi-one-project-management-sketch.png`. It was
preserved and excluded from the product commit. Clean CI sanitizes canonical
visual package sources and is authoritative for the exact tracked checkpoint.

## Exact-SHA ordinary CI

Ordinary CI `31259073916` passed exact product checkpoint `5a92569`:

- repository job `93106930476`: PASS — complete repository verification,
  `1,208` tracked Python tests, `744` frontend unit tests, `321` non-visual E2E,
  `4,528` literal English sources at 100% direct `zh`/`zh-TW`, statements
  `80.07%`, dependency and both current/history secret lanes;
- visual job `93106930464`: PASS — `79/79` fixed-Linux governed cases;
- controlled runtime job `93106930717`: correctly skipped because the live
  workspace and runtime checkpoint are not active;
- visual artifact `9022271760`, digest
  `sha256:4e8b32fcd50445b6e53b17b1613c44be6885f446ece8cc73f09d35aad1f87ec4`;
  and
- Gitleaks artifact `9022334863`, digest
  `sha256:b9e0d4fea85e95d21b1391259039a419fdb3767c75bd39342fcb20b42711e5ea`.

No catalog source changed in checkpoint 2, so the existing eighteen governed
footer fingerprints and all other visuals passed without any baseline repair.

## Review, rollback and next checkpoint

The active routes are independently fail-closed by
`npi_p6_04_routes_disabled`; missing or non-false configuration disables only
P6-04. Rollback disables those routes and the injected projection reader,
preserves every immutable plan, observation, evidence, audit and receipt, and
uses a reviewed forward repair. It does not alter P6-01 through P6-03 objects,
controlled Document lifecycle or any ERPNext object.

Checkpoint 2 is PASS. P6-04 remains in progress. Autopilot next implements
only checkpoint 3: the strict manufacturing data source and dense live Tooling
workspace with separate plan, milestone, release, manufacturing-authorization
and ERP sections; complete loading/empty/error/no-permission/read-only/
unavailable/validation/conflict/processing/retry states; complete direct
English/`zh`/`zh-TW`; keyboard/accessibility checks; and affected visual
evidence. The deterministic prototype, supplier portal, production ERP and
controlled-Site runtime remain inactive until that checkpoint passes.
