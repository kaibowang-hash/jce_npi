# P7-03 Repository, BFF and Single-Tip Checkpoint

Recorded: `2026-08-10T23:35:30Z`

Status:
`PASS — PROJECT-FIRST EXACT QUALITY COMMANDS AND ONE CROSS-STORE DEFECT TIP`

Primary requirements: `FR-TR-004`, `FR-TR-009` and the retained
`FR-TL-009` / `FR-TL-010` foundations.

Exact product checkpoint:
`21b3bdaf729d1607831566cc1db108e1b255ea3e`

## Delivered boundary

- Activated one Project-first quality read and five exact cavity-result,
  defect-successor and independent-verification commands. Every command is a
  closed BFF payload behind CSRF, the internal NPI role boundary and a separate
  default-closed `npi_p7_03_routes_disabled` recovery switch.
- Bound every write to the locked Project, running Round version/hash, current
  input-lock revision/hash, exact Sample Batch where applicable, locked Tooling
  Revision/Set and physical cavity. Clean Trial evidence and measurement-report
  evidence are resolved server-side; callers cannot supply safety truth.
- Enforced one logical defect identity across the P6 Tooling and P7 Trial
  stores. The first P7 successor consumes the exact current P6 tip, later P7
  revisions consume only the exact current P7 tip, and P6 now fails closed
  after any P7 successor exists under the same locked Project.
- Bound actions to current Project members and exact target Rounds. An action
  can become verified only with the latest successful verification revision
  for the same Project, defect, action and exact target Round.
- Kept verification attempts append-only and independent. Retry attempts retain
  the same stable verification, defect, action and target-Round identity; no
  verification command closes or reopens a defect automatically.
- Sealed actor-bound idempotent replay, target insert, append-only audit and
  response receipt inside one transaction. Stored snapshot/hash and chain
  integrity fail closed on read.
- Returned unioned P6/P7 defect history, exact cavity filters and server-derived
  Pareto truth while keeping NCR, formal quality, Gate and Tooling lifecycle
  effects explicitly unavailable.

## Deliberately inactive

- No SPA quality workspace, frontend fixture or controlled-Site runtime was
  added in this checkpoint.
- No NCR, ERPNext Quality Inspection, Gate, Tooling lifecycle, conclusion,
  approval, readiness, release, external projection or production-print command
  exists.
- The route switch remains disabled unless deployment configuration sets the
  exact P7-03 flag to `false`; recovery after retained rows is route-disable plus
  reviewed forward repair, never deletion or history rewriting.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| quality validation/repository | closed canonical payloads, exact containment, immutable chains, one P6/P7 tip and exact verification retry/target rules |
| BFF/API/receipt metadata | six Project-first routes, independent fail-closed switch, CSRF/role/idempotency and sealed response mapping |
| P6 shared-defect boundary | append denial after a P7 successor prevents a parallel Tooling tip |
| OpenAPI/translations/catalog | six live closed paths and complete direct English/zh/zh-TW error and operation text |
| scope/security guards | no external quality/Gate mutation, no raw File URL, no explicit commit and exact 18-file task diff |

## Local and exact-SHA CI evidence

- Focused repository/API/contract/seam checks passed, including the exact
  latest-pass/target-Round verification guard.
- The full local workspace Python discovery passed `1,557` tests before the
  final seam assertion; the final focused set passed `10/10`. Compile, JSON and
  YAML parsing, generated-catalog equality, typecheck, direct i18n, current-task,
  reconciliation, visual-governance and diff checks passed.
- Clean-checkout ordinary CI run `31442261342` passed exact SHA
  `21b3bdaf729d1607831566cc1db108e1b255ea3e`:
  - repository job `93629232884`: PASS with `1,552` tracked Python tests and the
    complete repository gate;
  - frontend job `93629232849`: PASS with `832/832` unit tests, `365/365`
    non-visual E2E tests, `6,440` direct English sources, `100%` zh/zh-TW
    coverage and zero vulnerabilities;
  - secret-scan job `93629232857`: PASS for task scope, current tree and full
    pull-request branch history; and
  - visual job `93629232835`: PASS at the unchanged `100/100` fixed-Linux
    governed matrix.
- Controlled runtime correctly skipped because checkpoint 2 intentionally
  introduces no runtime fixture and its ordinary CI prerequisite alone was
  required before the frontend checkpoint.
- Local full repository verification was blocked only at the devcontainer
  registry network lookup. The clean-checkout repository job proved that exact
  prerequisite and all repository checks; no PASS claim relies on bypassing it.

## Review, rollback and next checkpoint

Task Diff Review confirms the change is limited to the frozen repository/BFF
boundary and contains no UI, runtime fixture or external mutation. Retained
cavity-result, defect, verification, receipt and audit rows are append-only.
Rollback disables only the independent P7-03 routes/workspace and applies a
reviewed forward repair.

Checkpoint 2 is PASS. Checkpoint 3 alone is active: add the strict quality data
source and dense trilingual cavity-result, defect, action, verification and
Pareto workspace with honest loading, empty, read-only, permission, validation,
conflict, processing, retry and unavailable-external-effect states plus affected
Linux visuals. Controlled runtime and Level 2 remain checkpoint 4.
