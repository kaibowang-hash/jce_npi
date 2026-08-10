# P7-03 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-10T22:36:19Z`

Status:
`PASS — EXACT CAVITY RESULTS, SINGLE DEFECT IDENTITY, ACTION TARGETS AND INDEPENDENT VERIFICATION DOMAIN`

Primary requirements: `FR-TR-004`, `FR-TR-009` and the retained
`FR-TL-009` / `FR-TL-010` foundations.

Exact product checkpoint:
`42812c3162a6d3e72508ecc12bf0a5c944e334c7`

## Delivered boundary

- Added immutable exact-cavity result revisions bound to one Project, running
  Trial Round, input-lock revision, Sample Batch revision, Tooling Revision,
  physical Set and cavity. Dimensional observations preserve explicit
  `measured` / `not_measured` truth; missing values are never imputed.
- Added immutable Trial defect revisions that reuse the same stable
  `defectGlobalId` as the P6 Tooling defect stream. The pure successor contract
  accepts only the exact current P6 or P7 predecessor version and snapshot hash
  and rejects latest-value substitution or cross-context forks.
- Added containment, corrective and preventive action snapshots bound to an
  exact responsible Project member and exact target Trial Round.
- Added append-only independent verification attempts bound to one exact
  action, verification Round, cavity result and clean Trial evidence set. The
  verifier cannot be the responsible member, and a verification result never
  closes or reopens a defect automatically.
- Added three UUID-based create-only guarded DocTypes, strict metadata
  validation, additive single-owner declarations, closed future OpenAPI schemas
  and complete direct Simplified and Traditional Chinese translations.
- Kept every external effect explicit and unavailable: no NCR, formal Quality
  Inspection, Gate mutation, Tooling lifecycle mutation, conclusion, approval,
  readiness, release, projection or production print authority was introduced.

## Deliberately inactive

- This checkpoint activates no handler, BFF route, repository command,
  business row, UI, runtime fixture, lifecycle transition or external call.
- Cross-store single-tip locking is specified and tested as a pure invariant;
  its transactional P6-to-P7 enforcement remains checkpoint 2 work.
- Pareto truth, cavity filters and the unioned P6/P7 defect history are future
  response schemas only until the Project-first repository/BFF boundary passes.
- P7-02 remains the sole live source of exact Round, input-lock, Sample Batch,
  cavity and clean private evidence truth. No second File or defect system was
  introduced.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| pure quality domains | exact result identity/version/hash, no-imputation, cross-store successor, exact action target and independent verification invariants |
| metadata/controllers | three exact additive DocTypes, closed snapshots, UUID identity, create-only permissions and generic mutation denial |
| OpenAPI/ownership | closed future Project-first schemas, one cross-store tip owner and unavailable external effects |
| translations/generated catalog | generated-catalog equality, `6,425` direct English sources and `100%` `zh` / `zh-TW` coverage |
| checkpoint guard | current-task path scope, YAML parsing, reconciliation and clean diff |

## Local and exact-SHA CI evidence

- Focused P7-03 domain/metadata/contract checks passed `57/57`.
- The complete tracked Python suite passed `1,544/1,544`; OpenAPI and ownership
  YAML parsed, direct i18n coverage passed, generated catalogs matched and the
  task/reconciliation/diff guards passed.
- Clean-checkout ordinary CI run `31438191274` passed exact SHA
  `42812c3162a6d3e72508ecc12bf0a5c944e334c7`:
  - repository job `93617010649`: PASS with the complete repository gate;
  - frontend job `93617010756`: PASS with the complete unit, build, dependency,
    brand and non-visual E2E gate;
  - secret-scan job `93617010700`: PASS for the task guard, current tree and
    complete pull-request branch history; and
  - visual job `93617010730`: PASS at the unchanged `100/100` fixed-Linux
    governed matrix.
- Controlled runtime correctly skipped because checkpoint 1 intentionally
  activates no live persistence or route boundary.
- Local full repository verification was blocked only at the devcontainer
  registry network check. The same clean-checkout repository job, individual
  full Python suite and all affected checks passed; no acceptance claim relies
  on the blocked local registry call.

## Review, rollback and next checkpoint

Task Diff Review confirms checkpoint 1 is additive and creates no runtime
behavior. Before retained P7-03 rows exist, this foundation can be reverted and
a disposable Site migrated fresh. After checkpoint 2 activation, rollback must
disable only the independent P7-03 quality routes/workspace and use reviewed
forward repair; immutable cavity-result, defect, verification, receipt and
audit history must never be deleted or rewritten.

Checkpoint 1 is PASS. Checkpoint 2 alone is active: implement Project-first
quality reads and exact cavity-result/defect/verification commands, enforce one
cross-store defect tip under transaction locks, actor-bound idempotency, one
transaction, append-only audit and an independent default-closed P7-03 route
switch. UI and controlled runtime remain later checkpoints.
