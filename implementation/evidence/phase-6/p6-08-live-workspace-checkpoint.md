# P6-08 Live Tooling List and Export Workspace Checkpoint

Recorded: `2026-08-09T23:24:00Z`

Status:
`PASS — LEVEL 1 LIVE WORKSPACE, TRILINGUAL, ACCESSIBILITY AND VISUAL EVIDENCE`

Requirement:
`UX-007`

Exact stable product checkpoint:
`82ebcaf712f78e48f6718d7cb0ac675712f9e689`

Primary product commit:
`70802d676c55ee5c1961b71011466593962f1a00`

## Delivered boundary

- Added one strict P6-08 frontend data source for the default-closed
  Project-first list, preference, export-create and creator-bound package
  download routes. Every response is checked against exact Project, view,
  query, snapshot, package and receipt identities before use.
- Added a dense Tooling List workspace using the shared `DenseGrid`, with the
  ten code-owned views, closed search/sort/group controls, stable server
  paging, fixed identity columns, optional column visibility/resize state and
  saved per-view query/layout preferences.
- Selection remains explicit across pages and separate from complete-filter
  export. The review step shows the exact mode, reviewed count, snapshot
  policy, redaction policy and one-hour validity before creation.
- The secondary Export action handles no-authority, validation, stale/
  conflict, processing, created, replay, expired and download-failure truth.
  It returns no raw private File URL and downloads only through the fixed
  creator-bound POST route.
- Selected Tooling Master navigation remains available from the list. The
  workspace does not add Tooling lifecycle, approval, ERP, mapping or
  destructive rollback authority.
- Loading, empty, retryable failure, read-only and unavailable states are
  explicit. The empty-state heading/body spacing was corrected without
  changing semantics or Gate criteria.
- All new visible sources are literal English with direct Simplified- and
  Traditional-Chinese Frappe CSV translations. The final catalog contains
  `5,753` governed sources at 100% direct `zh`/`zh-TW` coverage.

## Security and no-fake-success proof

- The browser cannot supply a DocType, field list, arbitrary filter/sort/group
  expression, File URL, Project-only relationship or ERP/lifecycle field.
- Selection export submits exact Master snapshot hashes; filtered export
  submits the complete server query snapshot. Stale membership fails as a
  conflict instead of silently refreshing the reviewed package.
- Selection and filtered modes are mutually exclusive in the UI, with an
  explicit reviewed count. Selection is not inferred from the visible page.
- The download path preserves CSRF, current Project/export authorization,
  creator binding, one-hour expiry, immutable package/File hashes,
  attachment-only headers and no-store behavior.
- Replayed creation remains honest and references the immutable existing
  package. Expired or failed downloads do not display success.
- No arbitrary database export, raw private URL, production mapping, ERPNext
  network call, Outbox, worker or Tooling/lifecycle mutation was introduced.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
| --- | --- |
| strict Tooling-list/export data source | focused parser, closed-route, stale/conflict, replay, expiry and download tests |
| dense ten-view Tooling List workspace | component tests for preferences, stable paging, across-page selection, selected/filtered review and all honest states |
| Tooling-page composition and shared grid | affected P6-01/P6-02/P6-03 browser regression plus complete non-visual matrix |
| styles and direct catalogs | complete industrial UI, formatting and `5,753`-source direct trilingual audits |
| P6-08 browser behavior | nine operational cases covering three-language purity, keyboard/Axe, overflow, export review, replay, expiry and failure |
| fixed-Linux evidence | three direct P6-08 views and reviewed affected/catalog baselines; final exact-zero-difference `94/94` matrix |
| complete checkpoint | exact-SHA repository verification, dependency audit, build/brand and both current/history secret lanes in CI below |

## Local affected and regression evidence

- focused Tooling-list data-source/workspace unit coverage: PASS;
- complete frontend unit suite: `52` files and `809/809` PASS;
- complete non-visual browser matrix: `352/352` PASS;
- direct P6-08 non-visual browser cases: `9/9` PASS;
- affected P6-01/P6-02/P6-03 non-visual browser cases: PASS;
- TypeScript, ESLint, Prettier, Stylelint, source-boundary, industrial-UI,
  generated-catalog and i18n checks: PASS;
- direct i18n audit: `5,753` literal English sources with 100% direct `zh` and
  `zh-TW` coverage;
- frontend statement coverage: `80.07%`;
- Vite package compilation: PASS. The host-only final display-brand scan sees
  the user's pre-existing untracked
  `frontend/public/images/npi-one-project-management-sketch.png`; it was not
  changed or staged. Clean pinned-runtime CI below passes the complete build,
  install-script, dependency and brand gates;
- local npm registry audit was unavailable and the host npm install-script
  check used a mismatched local npm runtime; the clean pinned CI evidence
  below is authoritative and passes both checks;
- `git diff --check`: PASS; and
- Task Diff Review range `c51bffc..82ebcaf`: `57` bounded files, `4,677`
  insertions and `7` deletions, including product, test, CI and reviewed Linux
  evidence only. No user-owned dirty file or Darwin snapshot was staged.

## Visual failure and evidence repair

Initial exact product run `31340097667` passed repository job `93312344555`
and failed only its visual job with `37` failures. Artifact `9045601634`
retained all candidates/diffs. Review identified twenty-five legitimate
affected/new Linux actuals plus one P6-08 empty-state title/body spacing issue.
The source repair separated that heading and body; the workflow repair added
the missing P6-08 governed cases and corrected the truncated P6-03 result-
artifact glob. Neither repair changed an assertion, tolerance, language rule,
permission or product authority.

Second run `31340946452` produced sixteen remaining visual candidates in
artifact `9045839098`; its repository job was superseded and automatically
cancelled by the next push, so it is not used as PASS evidence. Original-
resolution review accepted the corrected P6-08 empty state, the three direct
P6-08 locales and affected P6-03 through P6-06 screens. One localized P6-01
candidate was retained only after the final run proved it stable.

Baseline repair commits copied only reviewed Linux actuals to their exact
targets. They changed no production component, source copy, assertion, test
matrix, threshold, tolerance or PASS criterion. User-owned Darwin snapshots
were not staged.

## Exact-SHA ordinary CI

Ordinary CI `31341354013` passed exact stable checkpoint `82ebcaf`:

- repository job `93315593607`: PASS — `1,405` tracked Python tests, `52`
  frontend test files and `809` unit tests, `352` non-visual E2E, `5,753`
  literal English sources at 100% direct `zh`/`zh-TW`, statements `80.07%`,
  branches `78.94%`, functions `82.52%`, lines `82.39%`, zero dependency
  vulnerabilities, install-script and brand checks, full verification and
  both current/history Gitleaks lanes;
- visual job `93315593576`: PASS — `94/94` fixed-Linux governed cases,
  including all three P6-08 locales and the affected predecessor surfaces;
- controlled runtime job `93315593910`: correctly skipped because checkpoint
  4 is not active at this SHA;
- visual artifact `9045957771`, digest
  `sha256:4538ab66dade6fb00f4b8a32f50691fd3258b9a2b4031afb1078f86d48cfbc6a`;
  and
- Gitleaks artifact `9046041149`, digest
  `sha256:f8833cbabc3b15c2cd2735c6f7ce464b5561a01a5151c445ee8bde9048673fd0`.

## Review, rollback and next checkpoint

Checkpoint 3 is PASS, not P6-08 Level 2. Rollback is a reviewed forward fix:
disable only the P6-08 workspace/routes while preserving immutable packages,
private Files, audits and receipts. Never delete package history, expose a raw
File URL, contact ERPNext or change P6-01 through P6-07 truth.

Standing transition authority activates only checkpoint 4: extend the
cumulative disposable-Site verifier/workflow through P6-08; seed bounded
Tooling truth; prove every view, stable selection/filter packages, localized
members, formula neutralization, hashes, one-hour expiry, cross-process
replay, actor/Project/IDOR/expiry/stale denials, route disable/recovery, two
migrations, raw-log redaction, no ERP/network/Outbox and cleanup. Then execute
the P6-08 Level 2 Task Gate, reconcile `UX-007`, and run the Phase 6 Level 3
release gate. Production-scale performance remains external evidence.
