# P6-07 Live Industrial Import Workspace Checkpoint

Recorded: `2026-08-09T12:53:36Z`

Status:
`PASS — DENSE EIGHT-STEP PROJECT-FIRST IMPORT WORKSPACE AND FIXED-LINUX VISUAL GATE`

Requirements:
`FR-TX-012`, `FR-TX-013`, `FR-TX-014`, `FR-TX-015`, `FR-TX-016`,
`FR-TX-017`, `FR-TX-018` and `UX-016` technical workspace

Exact stable checkpoint:
`f42ba61d6b32eacd8dc32d47250a3871a569e682`

Primary product commit:
`13bd67b7cf588f1f31ca3d0375d50b28c571c7c5`

## Delivered boundary

- Added the strict Tooling List import data source and the lazy selected-
  Project route `/projects/{project_id}/tooling?workspace=import`; the existing
  Tooling cockpit opens it through one visible secondary action.
- Added a dense eight-step workspace for source registration, inspection,
  region detection, mapping proposal, preview, confirmation, execution and
  results. A stable step rail, table/tree work area, inspector and result strip
  retain engineering context without exposing Frappe Desk.
- Bound every screen to the closed Project-first P6-07 BFF. The browser cannot
  invent a mapping, target, customer, authority, correction or rollback
  decision through generic DocType CRUD.
- Kept one primary action per operational context and exposed explicit
  mapping-unavailable, confirmation-required, loading, empty, no-permission,
  read-only, conflict, queued, processing, partial, success, retryable, final-
  failure and rollback-allowed/denied states.
- Added authorized correction-file download, failed-row-only retry,
  reconciliation and exact rollback evaluation surfaces. Denial reasons remain
  visible truth and are not converted to optimistic success.
- Added direct English, `zh` and `zh-TW` translations, accessible names,
  keyboard/focus behavior, component tests, six live browser cases and three
  governed fixed-Linux visual cases.
- Added the new workspace to the complete visual-governance matrix while
  retaining all established P0 and P6-01 fingerprints.

## Deliberately unavailable

- `DR-REC-007` remains open. The UI reports production mapping as unavailable;
  it can exercise only the exact visibly synthetic fixture activation.
- No customer workbook is committed or read. The deterministic synthetic
  fixture remains the only executable workbook evidence.
- No ERPNext endpoint, credential, network call, Outbox row, Asset mapping or
  ERP-owned location, inventory, maintenance, procurement, manufacturing,
  quality, cost or finance truth is reachable.
- `DR-REC-008` continues to deny destructive rollback for changed,
  downstream-used, updated or pre-existing targets.
- Disposable-Site runtime and P6-07 Level 2 evidence remain checkpoint 5 work.

## Local affected and regression evidence

- focused import workspace component/data-source/router and contract tests:
  PASS;
- complete frontend unit suite: `796/796` PASS across `50` files;
- frontend coverage: statements `80.00%`, branches `78.98%`, functions
  `82.20%`, lines `82.21%`;
- P6-07 non-visual Playwright: `6/6` PASS;
- local Darwin P6-07 visual matrix: `3/3` PASS;
- i18n audit: `5,553` literal English sources with 100% direct `zh`/`zh-TW`
  coverage and no mixed-language violation;
- lint, typecheck, industrial static audit, generated-catalog check and
  `git diff --check`: PASS; and
- local clean production compilation passed. Its final static-directory guard
  was blocked only by the user's pre-existing untracked
  `frontend/public/images/npi-one-project-management-sketch.png`; the clean
  pinned GitHub job below passed the complete production build.

All user-owned files, Darwin screenshots, local evidence and
`implementation/LAST_RUN.md` were preserved and excluded.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| strict import data source | closed route and response parsing, binary correction download, retry/reconcile/rollback action and error-state unit tests |
| lazy Project route and Tooling cockpit action | router/data-source contract tests plus selected-Project live navigation case |
| eight-step workspace and state model | loading, empty, permission, read-only, conflict, confirmation, progress, partial, terminal, retry and rollback-denial component/browser tests |
| dense industrial CSS and accessibility | keyboard/focus assertions, industrial static audit, three-language browser matrix and reviewed visual candidates |
| translation sources/catalogs | generated-catalog check, direct `zh`/`zh-TW` coverage and mixed-language audit |
| governed visual matrix | all three new P6-07 cases, five affected P6-01 Tooling cockpit cases and eighteen catalog-footer fingerprints; complete `91/91` fixed-Linux CI |

## Exact-SHA CI and bounded visual repair

Primary product commit `13bd67b7cf588f1f31ca3d0375d50b28c571c7c5`
ran ordinary CI
[`31313236719`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31313236719).
Repository job `93244249404` passed the complete repository Gate. Visual job
`93244249415` passed `65/91` and failed exactly the three new P6-07 baselines,
five P6-01 Tooling cockpit baselines affected by the reviewed import action and
eighteen durable P0 catalog-footer fingerprints. Controlled runtime job
`93244249656` correctly skipped.

Artifact `9038021540`, digest
`sha256:0be137f4cde5114e50f72f4b8c211ebd330997971a6f075465e87f1a5af7fade`,
retains all actual/diff evidence. The three new P6-07 screens were reviewed as
the intended dense trilingual workspace. The five P6-01 deltas were confined
to the added secondary action around `y=161..192` apart from minor text anti-
aliasing. Exact RGB comparison of all eighteen P0 images found their material
deltas only in the catalog footer at approximately `y=879..899`; no business
component or operational state changed.

Isolated repair `f42ba61d6b32eacd8dc32d47250a3871a569e682` copied only those
twenty-six reviewed CI actuals byte-for-byte to their exact tracked Linux
targets. It changed no source component, assertion, visual case, matrix,
tolerance, threshold or PASS rule and staged no user-owned or Darwin file.

Final ordinary CI
[`31313899335`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31313899335)
passed exact stable checkpoint `f42ba61`:

- repository job `93245913680`: PASS — `1,341/1,341` tracked Python tests,
  `796/796` frontend unit tests, `343/343` non-visual E2E, `5,553` literal
  English sources with 100% direct `zh`/`zh-TW`, statements `80.00%`, branches
  `78.98%`, functions `82.20%`, lines `82.21%`, the complete clean production
  build, zero dependency vulnerabilities and both current/history secret lanes;
- visual job `93245913727`: PASS — `91/91` fixed-Linux cases;
- controlled runtime job `93245914101`: correctly skipped;
- visual artifact `9038197971`, digest
  `sha256:3a0f10ea721b12c24d51f1d849d1c6ea28f5613ac1b1434d314303ae0671023`;
  and
- Gitleaks artifact `9038273601`, digest
  `sha256:0169b501df654cad3c0d451094240132b6f7ca281e05218087e529799e5cc2a8`.

## Review, rollback and next checkpoint

Task Diff Review confirms the workspace is Project-first, industrial, bounded
to the closed P6-07 API and truthful about partial, unavailable and denied
states. It grants no new mapping, data-owner, target-mutation, rollback or ERP
authority. Rollback is a reviewed forward operation: disable the independent
P6-07 route switch and remove the live composition while retaining all source,
mapping, preview, job, result, correction, reconciliation, audit and receipt
history.

Checkpoint 4 is PASS. P6-07 remains in progress. Autopilot next executes only
checkpoint 5: extend the disposable-Site verifier/workflow through P6-07;
generate and inspect the exact sanitized synthetic fixture; seed only its
synthetic mapping; exercise the complete cross-process inspect/map/preview/
confirm/execute/partial/retry/reconcile/rollback allowed-and-denied path; prove
migration, independent route disable/recovery, permission/IDOR, no raw-log
leak, no production mapping/ERP network and cleanup; then reconcile
Requirements and run the P6-07 Level 2 Task Gate before P6-08.
