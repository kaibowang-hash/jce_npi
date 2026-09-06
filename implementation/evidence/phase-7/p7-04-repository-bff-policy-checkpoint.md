# P7-04 Repository, BFF and Policy Checkpoint

Recorded: `2026-08-11T07:53:20Z`

Status:
`PASS — PROJECT-FIRST EXACT REVIEW COMMANDS AND FAIL-CLOSED POLICY`

Primary requirements: `FR-TR-005`, `FR-TR-006`, `FR-TR-007` and
`FR-TR-008`.

Exact product checkpoint:
`b65415f8789be3b24c8f3ab8be0a85a5f5f636b3`

## Delivered boundary

- Activated one Project-first review read and exact begin-analysis,
  comparison, controlled-reference, conclusion submission, decision and
  reopen commands. Every command uses a closed BFF payload behind CSRF, the
  internal NPI role boundary and a separate default-closed
  `npi_p7_04_routes_disabled` recovery switch.
- Required an exact published conclusion policy and server-resolved eligible
  authority. Missing policy, inactive membership, stale versions, mismatched
  hashes and cross-Project/cross-Plan/cross-Round references fail closed.
- Built comparisons from at least two exact immutable same-Project/same-Plan
  Round source tuples. Missing cycle, yield, formal quality or dimension truth
  remains explicitly unavailable and is never converted to zero, success or a
  latest-value substitute.
- Bound internal-quality, internal-sample, customer-evidence and deviation-or-
  waiver references only to controlled exact product, Tooling and clean private
  File revisions. Evidence presence remains distinct from approval.
- Kept analysis lifecycle and conclusion decisions as separate policy-bound
  immutable facts. Conclusion blockers are derived server-side; approve,
  reject and controlled reopen create append-only successors rather than
  rewriting history.
- Sealed actor-bound replay, exact target, lifecycle event, Round state,
  append-only audit and response receipt in one transaction. Snapshot/hash and
  chain integrity fail closed on read.
- Kept ERPNext formal quality, customer signature, Gate, Tooling lifecycle,
  Work Item, readiness, release, projection and print effects unavailable or
  proposal-only. No external traffic, target mutation or optimistic success is
  introduced.

## Deliberately inactive

- No SPA comparison/conclusion workspace or controlled-Site runtime fixture was
  added in this checkpoint.
- No automatic Gate, Tooling lifecycle or Work Item mutation, production
  ERPNext adapter, customer-signature authority, Released Trial Summary,
  external projection or production-print command exists.
- The route switch remains disabled unless deployment configuration sets the
  exact P7-04 flag to `false`; after retained rows, rollback is route-disable
  plus reviewed forward repair, never deletion or history rewriting.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| review validation/repository | closed canonical payloads, exact containment, immutable source tuples, policy/authority checks, blocker derivation and actor-bound replay |
| BFF/API/lifecycle/receipt metadata | seven Project-first routes, independent fail-closed switch, CSRF/role/idempotency and one-transaction response sealing |
| exact comparison/reference/conclusion domains | no latest substitution, unavailable-not-zero truth, evidence-not-approval and distinct lifecycle/conclusion successors |
| OpenAPI/translations/catalog | seven live closed paths and complete direct English/zh/zh-TW operation, state and error text |
| scope/security guards | no raw private File URL, external mutation, direct SQL, explicit commit or out-of-scope task diff |

## Local and exact-SHA CI evidence

- Focused Phase 7 repository/API/domain/contract/metadata/seam checks passed
  `86/86` after the final policy, lifecycle-enum, unavailable-dimension and
  repository-interface repairs.
- The complete local repository gate passed `1,607` tests; compile, JSON/YAML,
  generated-catalog, current-task, reconciliation, visual-governance,
  prohibited-surface and diff checks passed. The local frontend gate passed
  typecheck, lint, format, style/boundary/i18n checks, `843/843` unit tests,
  production build and `371/371` E2E. Its final static-brand audit correctly
  rejected an unrelated untracked local image under `frontend/public`; the
  file was preserved and excluded from this checkpoint.
- Clean-checkout ordinary CI run `31469876418` passed exact SHA
  `b65415f8789be3b24c8f3ab8be0a85a5f5f636b3`:
  - repository job `93710640289`: PASS with `1,601` tracked Python tests and
    the complete repository gate;
  - frontend job `93710640314`: PASS with `843/843` unit tests, `371/371`
    non-visual E2E tests, `6,670` direct English sources, `100%` zh/zh-TW
    coverage, production build and zero vulnerabilities;
  - secret-scan job `93710640333`: PASS for task scope, current tree and full
    pull-request branch history; and
  - visual job `93710640286`: PASS at the unchanged `103/103` fixed-Linux
    governed matrix. Artifact `9093023227` has SHA-256
    `de7eba53691d9da6c75b096a32cee5d8a5988dc1206ea6fd6aa3368a06136534`.
- Controlled runtime correctly skipped because checkpoint 2 intentionally
  introduces no runtime fixture. Level 2 and Level 3 are not claimed here.

## Review, rollback and next checkpoint

Task Diff Review confirms the product commit contains only the frozen
repository/BFF/policy boundary. Retained comparison, reference, conclusion,
lifecycle, receipt and audit rows are append-only. Rollback disables only the
independent P7-04 routes/workspace and applies a reviewed forward repair.

Checkpoint 2 is PASS. Checkpoint 3 alone is active: add the strict Trial review
data source and dense trilingual comparison/conclusion workspace with honest
loading, empty, read-only, permission, validation, conflict, processing,
retry and unavailable-external-effect states plus affected Linux visuals.
Controlled runtime and Level 2 remain checkpoint 4; Level 3 remains reserved
for the applicable PR/Phase/release boundary.
