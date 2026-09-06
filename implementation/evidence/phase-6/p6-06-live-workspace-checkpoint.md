# P6-06 Live Acceptance and Asset Workspace Checkpoint

Recorded: `2026-08-09T01:46:02Z`

Status:
`PASS — LEVEL 1 LIVE WORKSPACE, TRILINGUAL, ACCESSIBILITY AND VISUAL EVIDENCE`

Requirements:
`FR-TL-011`, `FR-TL-012`, `FR-TL-013`, `FR-TL-014`, `FR-TL-015`,
`FR-TL-016`

Exact stable product checkpoint:
`4e2021e6d2ce3d25075bca57b80e8dbbcf79f532`

Primary product commit:
`cf453a29c7ef4f91062df9079f526136f793037c`

## Delivered boundary

- Added one strict fail-closed frontend contract for immutable acceptance
  evidence, the nine frozen evidence categories, Project evidence for Asset
  actions/spares/repairs, operation-specific Tool Asset requests and the
  unavailable/future ERP Asset projection.
- Added all five exact Project-first checkpoint-2 routes to the live Tooling
  data source. Response validators bind Project, Master, physical Set,
  acceptance revision and snapshot identities before protected data reaches
  the page.
- Added a dense selected-Master workspace for immutable evidence lineage,
  nine-category coverage, exact Set/binding/Tooling Revision truth, related
  action/spare/repair evidence counts, Mock request preparation and a separate
  read-only ERPNext Asset projection.
- Acceptance authoring always submits exactly nine categories with one closed
  disposition per category. An append command cannot supply approval,
  lifecycle, target or ERP fields.
- Mock preparation requires the fixed translated acknowledgement. The visible
  axes remain `draft`, `validated_mock`, approval `unavailable`, dispatch
  `prohibited` and target result `not_requested`; the page renders no approve,
  dispatch, retry-target, mapping or formal Asset action.
- Loading, empty, retryable failure, read-only capability, validation,
  conflict, processing and unavailable target truth remain explicit. Dirty
  editors participate in the existing application navigation guard.
- All user-visible sources are literal English and have direct Simplified- and
  Traditional-Chinese Frappe CSV translations. The final catalog contains
  `5,087` governed sources at 100% direct `zh`/`zh-TW` coverage.

## Security and no-fake-success proof

- The browser supplies no operation name, arbitrary target payload, formal
  Asset ID, Asset state, location, shot/life, maintenance, approval or target
  result. The operation remains server-fixed
  `create_or_update_tool_asset`.
- The data source preserves CSRF, actor-bound idempotency, private no-store,
  request/trace identity and exact response validation. Invalid success
  envelopes fail closed.
- Browser tests assert that acceptance and Mock commands contain no
  `approvalState`, `dispatch` or `targetPayload` field and use only exact
  Project/Master/Set routes.
- The workspace does not add an endpoint, credential, network client, Outbox,
  worker, Webhook, target retry, mapping or ERPNext mutation. Production and
  sandbox ERPNext remain untouched.
- Evidence coverage is not shown as Tooling acceptance. Formal approval,
  Trial/official-quality truth, lifecycle and Gate behavior remain
  unavailable under the frozen P6-06 boundary.

## Changed-files -> affected-tests

| Change surface                                | Direct evidence                                                                                                                      |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| strict contract and five data-source methods  | four route/parser/cross-scope/command-envelope tests plus complete type and boundary checks                                          |
| selected-Master acceptance/Asset workspace    | five component tests for load/retry, read-only truth, exact nine-category append and acknowledged Mock preparation                   |
| Tooling-page composition and request fixtures | complete `337/337` non-visual browser regression, including all predecessor Tooling pages                                            |
| styles and catalogs                           | complete industrial UI, formatting and `5,087`-source direct trilingual audits                                                       |
| P6-06 browser behavior                        | five operational cases for three-language purity, overflow, industrial geometry, Axe, exact acceptance command and Mock-only request |
| fixed-Linux evidence                          | three direct P6-06 views plus eighteen catalog-footer updates; final exact-zero-difference `88/88` matrix                            |
| complete checkpoint                           | exact-SHA repository verification, dependency audit and both current/history secret lanes in CI below                                |

## Local affected and regression evidence

- focused acceptance data-source/workspace unit suite: `9/9` PASS;
- complete frontend unit suite: `48` files and `777/777` PASS;
- complete non-visual browser matrix: `337/337` PASS;
- TypeScript, ESLint, Prettier, Stylelint, source-boundary, industrial-UI,
  generated-catalog and i18n checks: PASS;
- direct i18n audit: `5,087` literal English sources with 100% direct `zh` and
  `zh-TW` coverage;
- Vite compilation and brand test compilation: PASS. The host-only final
  display-brand scan sees the user's pre-existing untracked
  `frontend/public/images/npi-one-project-management-sketch.png`; it was not
  changed or staged. Clean pinned-runtime CI below passes the complete build
  and brand gate;
- `git diff --check`: PASS; and
- Task Diff Review range `b6c2ae4..4e2021e`: `36` bounded files, `4,007`
  insertions and `6` deletions. It contains fifteen implementation/test/CI
  files and twenty-one reviewed Linux images, with no user-owned dirty file or
  Darwin snapshot.

## Visual failure and evidence repair

Initial exact product run `31288008973` passed repository job `93180234324`,
including `1,282` tracked Python tests, `777` frontend unit tests, `337`
non-visual E2E and both secret lanes. It failed only visual job `93180234336`:

- the three new English, Simplified-Chinese and Traditional-Chinese P6-06
  Linux snapshots did not yet exist; and
- the eighteen durable P0 snapshots differed only in the bottom status-bar
  catalog digest after direct translations were added (`244` English pixels,
  `226` Chinese pixels; ratio `0.01`).

Artifact `9030496973`, digest
`sha256:726fed5c0d9b2adf455b0aab167f470f10cfb95ba861eefce48298f95da083f0`,
retained the complete report, all eighteen actual/diff pairs and the three new
P6-06 Linux candidates. The three P6-06 screens were inspected at original
resolution; representative English, Simplified-Chinese and Traditional-
Chinese P0 diffs confined all visible change to the catalog footer.

Repair `4e2021e` copied only those twenty-one reviewed CI images to their
exact Linux targets. It changed no production component, source copy,
assertion, visual case, threshold, tolerance, language rule or PASS criterion.
The user's untracked Darwin snapshots were not staged.

## Exact-SHA ordinary CI

Ordinary CI `31288565243` passed exact stable checkpoint `4e2021e`:

- repository job `93181709786`: PASS — `1,282` tracked Python tests, `48`
  frontend test files and `777` unit tests, `337` non-visual E2E, `5,087`
  literal English sources at 100% direct `zh`/`zh-TW`, statements `80.20%`,
  branches `79.05%`, functions `82.10%`, lines `82.35%`, zero dependency
  vulnerabilities and both secret lanes;
- visual job `93181709805`: PASS — `88/88` fixed-Linux governed cases,
  including the three direct P6-06 views;
- controlled runtime job `93181710008`: correctly skipped because checkpoint
  4 is not active at this SHA;
- visual artifact `9030679710`, digest
  `sha256:e4232947ba7bdc5122465b7a52c0d5926bb8a7937a0d8f6a7e3078ef4e8dc991`;
  and
- Gitleaks artifact `9030743748`, digest
  `sha256:90b786756de1e2961d67753428b63c73d47283b4e9174d3b6d3d66c971ac0206`.

## Review, rollback and next checkpoint

Checkpoint 3 is PASS, not P6-06 Level 2. Rollback is a reviewed forward fix:
disable only the P6-06 workspace/routes while preserving immutable acceptance
revisions, requests, audits and receipts. Never delete history, contact
ERPNext or change P6-01 through P6-05 truth.

Standing transition authority activates only checkpoint 4: extend the
cumulative disposable-Site verifier and controlled workflow through P6-06;
prove two migrations, immutable evidence succession, customer-owned repair
authorization, Mock request preparation, replay/conflict/rollback/IDOR,
generic-mutation denial, no network/Outbox/target truth and independent route
disable/recovery; then run the P6-06 Level 2 Task Gate and update Requirement
trace truth. Formal acceptance, lifecycle, Trial/Gate and real ERPNext/Asset
execution remain inactive.
