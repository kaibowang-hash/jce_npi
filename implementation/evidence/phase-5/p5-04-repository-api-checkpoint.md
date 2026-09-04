# P5-04 Repository, BFF, and OpenAPI Checkpoint

Recorded: `2026-08-05T11:06:55Z`

Status:
`PASS — LEVEL 1 REPOSITORY/BFF/OPENAPI`

Requirements:

- `FR-DS-011`; and
- `FR-DS-012`.

Starting synchronized checkpoint:
`7be6e3fea4dbf376f5543bcf900919107ab3366b` (`0 ahead / 0 behind` after
`git fetch origin`)

Reusable predecessor evidence:

- P5-04 domain/metadata foundation exact-SHA CI `30996305240` (`PASS`);
- P5-03 ordinary CI `30990594281` and final unchanged controlled-Site Gate
  `30991177478` (`PASS`, diagnostics closed); and
- P5-01 through P5-03 Level 2 evidence remains unchanged and is not rerun by
  this bounded Level 1 checkpoint.

## Delivered boundary

- Added one Project-authorized Frappe repository for NPI-owned EBOM list,
  detail, create, successor revision, submit/review/release and two-exact-
  revision comparison. Every protected flow authorizes the Project first and
  then revalidates the exact EBOM, policy, revision and lifecycle scope.
- Creation binds one explicit published synthetic policy and its exact actor
  authority before replay or mutation. The atomic order is receipt, stable
  root, immutable revision/lines and draft lifecycle, exact root pointer,
  audit, response and one-way receipt seal.
- Successor creation requires the exact current root optimistic version,
  predecessor revision ID and predecessor snapshot hash. It appends a new
  immutable content bundle and advances the latest pointer exactly once.
- Lifecycle commands require exact root version, revision snapshot,
  lifecycle version, policy identity/hash and separately bound policy actor.
  Release additionally requires `confirmed: true` and the exact intent
  `release_exact_ebom_revision`.
- Actor/tenant/Project/operation/idempotency-key and canonical request payload
  bind every receipt. Replay accepts only an exact sealed response whose hash
  revalidates; different input fails with stable `409` truth.
- Added exact BFF routes and an independent P5-04 route-disable recovery
  boundary without changing P5-01 through P5-03 routes. Every route retains
  request correlation and private no-store responses.
- Added closed and bounded OpenAPI requests/responses for all eight operations,
  with explicit authority, transaction and audit metadata. Comparison accepts
  only `fromRevisionId` and `toRevisionId`; no mutable-latest selector exists.
- Added stable unavailable, idempotency-conflict and engineering-key-conflict
  problems plus direct Simplified and Traditional Chinese translations. The
  generated catalog now contains `3,421` literal English sources with direct
  `100%` coverage in both Chinese catalogs.

This checkpoint does not create formal ERPNext Item/MBOM truth, stock-UOM
authority, manufacturing routing, production execution, a cross-database
read/write, a production policy default, a P5-05 publish request or optimistic
ERP success. It does not activate the end-user EBOM workspace.

## Requirement -> code -> test -> evidence

| Requirement | Code boundary | Direct proof |
|---|---|---|
| `FR-DS-011` | `npi_core.ebom.frappe_repository`; `npi_core.ebom_api`; exact BFF routes; closed OpenAPI EBOM operations | Project/EBOM authorize-before-lookup; exact policy actor; immutable first/successor content; lifecycle authority/version/confirmation; replay/conflict and public-response tests |
| `FR-DS-012` | exact repository comparison and OpenAPI comparison response | two explicit same-root revision IDs; deterministic typed added/removed/quantity/substitution/attribute changes; no mutable-latest route or selector |

## Changed files -> affected tests

| Changed boundary | Affected checks | Result |
|---|---|---|
| Frappe repository and transaction order | `tests.test_phase5_ebom_repository`; P5 Document/Baseline repository compatibility | PASS |
| API authorization, CSRF, closed fields, replay headers and BFF routes | `tests.test_phase5_ebom_api`; existing Document API suites | PASS |
| OpenAPI paths, references and closed schemas | `tests.test_phase5_ebom_contract`; Project/Document contract smoke; Ruby YAML parse | PASS |
| stable problems and EBOM domain compatibility | complete P5 Document/EBOM group | `217/217` PASS |
| complete tracked backend regression | `python3 -m unittest discover -s tests` | `939/939` PASS |
| generated catalogs and all user-visible source strings | generation check and complete frontend lint/i18n | `3,421` sources; direct `100%` `zh`/`zh-TW` PASS |
| shared generated catalog consumer | TypeScript, `671/671` frontend unit tests and production Vite bundle | PASS |
| reconciled trace and prohibited patterns | reconciliation verifier; `ignore_permissions`/raw SQL/TODO/FIXME scan; `git diff --check` | PASS; zero prohibited matches |

The unit runner emits the existing expected negative-path reporter diagnostics
while all assertions pass; they are not product failures. The production
bundle retains the existing size warning and completes successfully.

The clean exact-SHA ordinary CI remains mandatory because the catalog version
is visible in fixed-Linux snapshots and local user-owned untracked public
assets are intentionally excluded from this Checkpoint. No visual baseline is
changed before exact clean-run evidence isolates any affected pixels.

## Exact-SHA CI isolation and bounded visual evidence repair

Candidate `ed2a7f87729b2f0e635969948e12f7625b0d52a3` was pushed and
matched the remote branch. Ordinary CI `31000405445` completed with exactly
one evidence failure:

- repository job `92287612411` passed in `7m23s`, including complete
  repository verification, non-visual browser, current-tree and complete
  branch-history secret lanes;
- controlled P5 runtime correctly remained skipped at this non-runtime stage;
- visual job `92287612467` passed `41/59` and failed only the exact eighteen
  normal 1440x900 P0 English/Simplified Chinese/Traditional Chinese cases;
- every Playwright strong delta was exactly `256` pixels (`0.01%`) and every
  reviewed actual changed only the bottom catalog fingerprint from
  `18fefcf811fde25b` to the generated `e24def7bfc10bf59`; and
- artifact `8928055413`, size `39,350,326` bytes, digest
  `sha256:0528cc2c344c1ed79a794727b543607a991a4aeca85e0c03e0431a43eb105b1e`,
  supplied the exact Linux actuals and diffs.

Pixel inspection found the strong changes only in the catalog text. Seventeen
raw difference boxes are within `y=882..891`; one Trial Simplified-Chinese
case additionally contains the same subthreshold twenty native-select corner
pixels previously classified at this shared status bar, keeping its entire
raw box within `y=879..898`. No product-workspace pixel changed.

The eighteen reviewed CI actuals are accepted byte-for-byte as only their
corresponding tracked fixed-Linux baselines. All `18/18` source/target SHA-256
values match after copying. No matrix, threshold, viewport, scale, language,
fixture state, product behavior or test is removed or weakened. A complete
unchanged ordinary CI rerun remains mandatory before this stage can pass.

Repair checkpoint `40e7b7036b9f39a8298b6bb44df9749c75337c5e` then
matched the remote branch and passed complete unchanged ordinary CI
`31001529719`:

- repository job `92291319560` passed in `7m07s`, including complete
  `verify.sh`, all `939/939` tracked Python tests, `671/671` frontend unit
  tests with coverage/build, `288/288` non-visual browser cases, direct
  `3,421`-source trilingual coverage, both zero-vulnerability audits and both
  current/complete-history secret scans;
- visual job `92291319718` passed the exact fixed-Linux `59/59` matrix in
  `2m20s` without changing a test or threshold;
- passing visual artifact `8928521452`, size `5,297,854` bytes, has digest
  `sha256:9646d1bce9564f3f18347b7a636fc448f3f6853d94b3dbd890a71c08e868d972`;
  and
- passing secret-scan artifact `8928653139`, size `6,760` bytes, has digest
  `sha256:95b767273af081b0250a336212f72b75e757dea7e62babea59d6038fdb27a1a4`.

This exact-SHA PASS closes the repository/BFF/OpenAPI stage. It does not claim
the frontend workspace, controlled-Site EBOM runtime or P5-04 Level 2 Task
Gate. Only the frontend workspace may activate next; P5-05 and Phase 6 remain
inactive.

## Domain, permission, security, UX and i18n review

- Domain/ownership: NPI One owns only immutable working EBOM revisions and
  their separate lifecycle. Formal Item Code, stock UOM, MBOM, routing and
  production execution remain ERPNext-owned.
- Permission/IDOR: queries require an authenticated internal Project viewer;
  commands additionally require an internal `NPI API User`, CSRF and current
  Project membership. Project authorization precedes protected EBOM lookup,
  and locked repository resolution revalidates tenant/Project/object scope.
- Security/transactions: no raw SQL, `ignore_permissions`, core patch,
  cross-database access, manual commit/rollback, secret, raw exception text or
  browser-supplied actor identity was introduced. The existing API wrapper
  retains non-2xx rollback behavior.
- UX: no end-user surface is activated by this slice. The response exposes
  exact lifecycle/capability truth for the later dense industrial workspace;
  it exposes no Desk form, ERP success or storage URL.
- i18n: all new user-visible sources are literal English with direct
  Simplified/Traditional translations. No concatenated sentence or translated
  enum/contract value is introduced.

## Risk, decision, blocker and rollback review

- `R-059` remains an open scoped production-policy hold. This implementation
  consumes only a published synthetic policy and installs no production fact.
- `R-060` is mitigated through repository and public-contract evidence but
  still requires controlled runtime, workspace and Level 2 proof.
- Decision Log entry `2026-08-05 / P5-04 immutable EBOM content revisions`
  remains sufficient; no architecture, ownership or product-policy decision
  changed, so no new ADR or Decision Request is required.
- No Hard Blocker exists. `implementation/BLOCKERS.md` remains historical plus
  the explicit scoped Class-B holds.
- Before retained P5-04 history exists, this additive slice can be reverted.
  After retained history exists, activate only `npi_p5_04_routes_disabled`,
  preserve every root/revision/line/lifecycle/event/audit/receipt and deploy a
  reviewed forward fix. P5-01 through P5-03 and ERPNext remain untouched.

## Next action

Implement only the P5-04 Project EBOM frontend workspace defined in the audit
plan: strict data-source/view-model contracts, dense industrial revision/
line/comparison views, exact lifecycle commands and complete English/zh/zh-TW
states. Do not begin controlled-Site runtime, P5-05 or Phase 6 before this
frontend checkpoint passes.
