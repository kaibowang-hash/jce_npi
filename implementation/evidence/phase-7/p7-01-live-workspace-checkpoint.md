# P7-01 Live Trial Planning Workspace Checkpoint

Recorded: `2026-08-10T10:02:00Z`

Status:
`PASS — LEVEL 1 LIVE WORKSPACE, TRILINGUAL, ACCESSIBILITY AND VISUAL EVIDENCE`

Primary requirement: `FR-TR-001`

Exact stable product checkpoint:
`583c879c85831c1c31de237960e0521f7c599a5b`

Primary product commit:
`b36b5f60c4380be030676ce42f9260127b736ce2`

## Delivered boundary

- Added one strict Trial planning data source for the independently
  default-closed Project-first workspace/detail, create-Plan,
  append-revision, create-Round and generate-actions routes. Successful
  responses are accepted only when their Project, Plan, revision, Round,
  capability, receipt and replay identities match the reviewed request.
- Replaced the deterministic Trial prototype on the live Project path with a
  dense engineering workspace. It exposes immutable Plan history, distinct
  planned Rounds, governed actions and explicit proposed-resource booking
  state without representing any resource as available or reserved.
- Create, revise, create-Round and action-generation flows use one reviewed
  payload, one stable idempotency key per prepared command and explicit
  processing, success, replay, validation, conflict and retryable-failure
  states. A retry never silently prepares a different command identity.
- Loading, empty, no-permission, read-only, route-unavailable, retryable,
  validation, conflict, processing and successful projection states are
  explicit. Later input-lock, actual, sample, cavity, defect, conclusion,
  approval, readiness, Gate and ERP quality sections remain unavailable.
- The Shell and router expose the live Trial workspace only inside the exact
  selected Project context. Existing Project, Tooling, Gate and My Work
  navigation remains intact.
- All new visible sources are literal English and have direct Frappe CSV
  translations for Simplified Chinese and Traditional Chinese. The final
  catalog contains `6,001` governed sources at 100% direct `zh`/`zh-TW`
  coverage.

## Security and no-fake-success proof

- The browser cannot supply tenant, actor, booking state, reservation truth,
  current Plan tip, Round sequence/state, receipt owner or audit identity.
- Project authorization remains server-side and precedes secondary Plan,
  Tooling, member, document, Round or Work Item resolution. UI capability
  hiding does not replace backend permission checks.
- Proposed machine and material rows are always rendered as unavailable for
  booking. No ERPNext endpoint, network call, Outbox event or reservation
  adapter is present.
- Replay is displayed only from the sealed server response. Validation,
  conflict and retry failures never advance the visible immutable projection
  or claim command success.
- Trial planning does not expose prepare/start, physical input locks, actual
  values, defect/conclusion/approval, Gate or formal quality mutation.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
| --- | --- |
| strict Trial data source | focused schema, identity, error, replay, conflict and command-key tests |
| dense live Trial workspace | component tests for complete states, exact Plan successor, distinct Round and governed-action flows |
| Shell/router/Project composition | route and Shell unit regressions plus complete non-visual browser matrix |
| styles and shared inspector range | affected Trial and inspector component/E2E cases, deterministic repeat capture and complete governed visual matrix |
| catalogs and direct translations | generated-catalog check and `6,001`-source direct trilingual/mixed-language audit |
| P7-01 browser behavior | `7/7` direct non-visual cases, keyboard/Axe and three governed locale/viewport images |
| complete checkpoint | exact-SHA repository verification, dependency audits, build/brand checks and both secret lanes in CI below |

## Local affected evidence

- focused Trial data-source/workspace, router and Shell unit tests: PASS;
- complete frontend unit suite: `54` files and `822/822` PASS;
- direct P7-01 non-visual browser cases: `7/7` PASS;
- direct P7-01 visual cases: `3/3` PASS and manually reviewed at original
  resolution for English, Simplified Chinese and Traditional Chinese;
- TypeScript, ESLint, Prettier, Stylelint, source-boundary, industrial-UI,
  generated-catalog and i18n checks: PASS;
- direct i18n audit: `6,001` literal English sources with 100% direct `zh` and
  `zh-TW` coverage;
- frontend coverage: statements `80.10%`, branches `79.22%`, functions
  `82.57%`, lines `82.50%`;
- Vite build: PASS; and
- local product checks intentionally excluded the user's pre-existing
  untracked `frontend/public/images/npi-one-project-management-sketch.png`,
  local Darwin images and generated local reports. Clean CI below passed the
  authoritative brand and repository gates.

## Visual repair and stability evidence

The first complete live-workspace run exposed one obsolete Shell assertion,
the three new P7-01 baselines and catalog/Trial-navigation changes on governed
predecessor screens. Each candidate set was retained and reviewed before
promotion. The obsolete assertion was corrected to the now-enabled Trial
navigation; no behavior or Gate criterion was weakened.

After promotion, one native range control rendered one pixel differently on
the fixed Linux runner. The source repair assigned deterministic block layout,
padding, line height, height and margin to the shared inspector range. Local
repeat captures were byte-identical and focused inspector E2E passed `5/5`.
The subsequent Linux artifact contained `42` expected affected candidates;
high-delta pixels in every image were confined to the range-control bounding
box, with representative P6 Tooling, P7 English and P7 Traditional-Chinese
images reviewed at original resolution. Commit `583c879` copied only those
reviewed Linux actuals.

No visual case, locale, viewport, scale, assertion, threshold or tolerance was
removed or weakened. User-owned Darwin snapshots were not staged.

## Exact-SHA ordinary CI

Ordinary CI run `31375548428` passed exact stable checkpoint `583c879`:

- repository job `93413841285`: PASS — `1,475/1,475` tracked Python tests,
  `54` frontend files and `822/822` unit tests, `359/359` non-visual E2E,
  `6,001` literal English sources at 100% direct `zh`/`zh-TW`, statements
  `80.10%`, branches `79.22%`, functions `82.57%`, lines `82.50%`, clean
  generation/type/lint/build, zero dependency vulnerabilities, complete
  repository verification and both current-tree/full-branch secret scans;
- visual job `93413841113`: PASS — `97/97` fixed-Linux governed cases,
  including all three direct P7-01 locales and every affected predecessor;
- controlled runtime job `93413841564`: correctly skipped because checkpoint
  4 is not yet committed;
- visual artifact `9057843671`, digest
  `sha256:1a1c754cf4f7a125e0557b55049232874131c7a2aaa98d3017b7e7c5da3ad86f`;
  and
- Gitleaks artifact `9057989926`, digest
  `sha256:93cb2b76c15f4efd9195446dbb689c2c6760efc5b04d3d3cf224149c86fa9009`.

## Review, rollback and next checkpoint

Task Diff Review range `620b388..583c879` contains only the bounded strict
data source, live workspace, Shell/router integration, direct tests,
trilingual sources, workflow coverage, deterministic shared range repair and
reviewed Linux evidence. No user-owned dirty file, Darwin snapshot, local
report or untracked production asset is included.

Checkpoint 3 is PASS, not the P7-01 Level 2 Task Gate. After retained Trial
history, rollback disables only the independent P7-01 routes/workspace and
uses a reviewed forward repair; it never deletes Plan revisions, Rounds,
events, Work Items, links, receipts or audits.

Standing transition authority activates only checkpoint 4: extend the
cumulative disposable-Site verifier and controlled workflow through P7-01;
prove Plan successor, distinct Round, governed actions/links, same- and
cross-process replay/conflict, transaction rollback, Project/actor/IDOR
denials, independent route disable/recovery, two migrations, zero ERP/network/
Outbox activity and cleanup. Then execute the P7-01 Level 2 Task Gate and
reconcile `FR-TR-001` without claiming resource reservation.
