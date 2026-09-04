# P7-06 Checkpoint 3 — Live Project Production Transition Workspace

Recorded: `2026-08-14T16:14:37Z`

Decision: `PASS — CHECKPOINT 3`

Exact product implementation:
`796712f7af6695549f611abdaf1bf53bd14c3e82`

Exact final checkpoint:
`b11e892128e3b9832b0cf92e48e0c331bf80eac4`

Final ordinary pull-request CI:
`31817424246` (`PASS`)

## 1. Bounded outcome

Checkpoint 3 delivers only the frozen live Project Production Transition
workspace:

- one strict data source for the complete Project workspace GET and exact-slot
  acknowledgement command, with closed response parsing, exact Project-route
  correlation, canonical identity/hash/lineage validation, abort support and
  actor-bound idempotency;
- the existing `App` to `ProjectPage` to `ProjectWorkspace` dependency-
  injection chain, without constructing hidden live transport inside the
  workspace;
- a dense Project tab with exact immutable handover manifest, receiving-group
  and frozen acknowledgement-slot truth, acknowledgements, unresolved actions,
  package history, independent observation history, context and retrospective
  references and all five identity-free unavailable external providers;
- acknowledgement only after authenticated-session verification and only for
  the current actor's exact unacknowledged eligible slot on the unique current
  package, with automatic selection for one slot and an explicit locked choice
  when more than one slot is eligible;
- one reviewed acknowledgement command, processing lock, same-key explicit
  retry and replay truth, conflict reload instead of blind retry, and honest
  accepted-command truth when the following GET refresh fails;
- honest loading, empty, read-only, permission, validation, conflict,
  processing, retry, replay, superseded, drift and external-provider-
  unavailable states; and
- English, Simplified Chinese and Traditional Chinese coverage, keyboard tab
  and acknowledgement operation, accessible labels, Axe checks and bounded
  desktop/zoom overflow behavior.

The live data source and UI expose no policy create, edit, publish or successor
transport; no package create or supersede transport; and no observation create
or revise transport. An acknowledgement remains a fact, not an electronic
signature, approval, formal acceptance or G7 decision. This checkpoint creates
no Gate input/evidence/mutation, Project/Work Item/Tooling mutation, production
actual, ERP/network/Outbox effect, external projection, release or print.

## 2. Diagnostic CI and exact root isolation

Diagnostic pull-request run `31815647237` used exact product SHA
`796712f7af6695549f611abdaf1bf53bd14c3e82`:

- repository job `94816548050` passed `1,851` tracked Python tests plus
  repository and reconciliation verification;
- frontend job `94816548288` passed `58/58` files and `908/908` unit tests,
  `399/399` non-visual E2E tests, `7,307` direct literal sources with `100%`
  `zh`/`zh-TW` coverage, statements `80.36%`, branches `80.24%`, functions
  `83.05%`, lines `83.00%` and zero vulnerabilities;
- secret scan `94816548211` passed the `64` committed current-task paths, `26`
  pull-request commits and `457` complete branch commits;
- visual job `94816548086` reported `97` passed and `15` failed out of `112`;
  all failures were screenshot-only differences, with no functional,
  accessibility, localization, content, state or geometry failure; and
- controlled preflight `94819524570` and controlled runtime `94819525297`
  skipped as required for ordinary checkpoint CI.

Visual artifact `9225012703`, digest
`sha256:c7948ad977006788412ae4a1267aa33cf4b3f3dd7bcfde20218784fa740b28c6`,
proves twelve differences were the expected shared Project navigation shift
after adding the Production transition tab: P5-01 Documents, P5-04 EBOM,
P5-06 Controlled Print and P7-05 Readiness in English, `zh` and `zh-TW`. The
three new P7-06 images differed only at Linux font and icon edge raster pixels
between the calibrated local image and the canonical CI runner. The Gitleaks
artifact is `9224881030`, digest
`sha256:4a22108cb7408189619bcff94ebccc00a5982672dca5339710062cf14d390744`.
This run is diagnostic evidence and is not used as a PASS Gate.

## 3. Bounded baseline repair

Final checkpoint `b11e892128e3b9832b0cf92e48e0c331bf80eac4` changes only:

- the twelve independently reviewed retained Project-navigation fixed-Linux
  baselines;
- the three independently reviewed P7-06 fixed-Linux baselines; and
- the twelve retained baseline paths newly required in
  `implementation/CURRENT_TASK.json`; the existing P7-06 snapshot glob already
  authorized the three new P7-06 paths.

The fifteen repository baselines are exact copies of the corresponding CI
actual images. The repair changes no product DOM, CSS, copy, test case, visual
matrix, assertion, threshold, tolerance or PASS criterion. No Darwin image or
local Playwright artifact is committed.

## 4. Final exact-SHA ordinary CI

Pull-request run `31817424246` completed successfully for event
`pull_request` at exact head
`b11e892128e3b9832b0cf92e48e0c331bf80eac4`:

- repository `94822344253`: `1,851/1,851` tracked Python tests plus current-
  task, repository and V1.2 reconciliation verification;
- frontend `94822344360`: `58/58` files, `908/908` unit tests, `399/399`
  non-visual E2E tests, `7,307` direct literal sources with `100%` `zh`/
  `zh-TW` coverage, statements `80.36%`, branches `80.24%`, functions
  `83.05%`, lines `83.00%` and zero vulnerabilities;
- secret scan `94822344279`: `76` committed current-task paths, `26` pull-
  request commits and `458` complete branch commits passed with no leaks;
- visual `94822344387`: the complete fixed-Linux matrix passed `112/112`;
- controlled runtime `94825306276` and controlled preflight `94825306398`
  skipped as required.

The final visual artifact is `9225687611`, digest
`sha256:2c79fdbe95624b9a32913eef09ece2c809a8e82ccc1a0c84ba6b02896c876a61`.
The Gitleaks artifact is `9225570279`, digest
`sha256:4efad34b5936bbf96d46881a46bb520a03f62bd2729d2c1006d4986bdc429955`.

## 5. Task-scope review

The exact checkpoint-3 range
`6b913b94fe307447d56e0baca21644afc65d6dc0..b11e892128e3b9832b0cf92e48e0c331bf80eac4`
contains `30` paths and `7,372` insertions with `1` deletion, excluding binary
baseline byte counts; `15` paths are binary baselines. Product implementation
`796712f` contains the bounded source/workspace/translation/test/CI files and
three new P7-06 Linux visuals. Final checkpoint `b11e892` contains only
fifteen reviewed Linux PNGs and the exact task-path guard. Every path is
authorized by the P7-06 manifest.

Existing unrelated dirty Makefile, README, development docs, `LAST_RUN.md`,
Phase 4 local evidence, Darwin screenshots, public assets and local runtime
helpers were not staged or changed by these commits.

## 6. Security and rollback

The boundary remains Project-first and fail closed. It accepts only the closed
canonical Production Transition workspace, recalculates exact identity, hash,
lineage, current-tip, slot and acknowledgement truth, binds commands to CSRF
and actor idempotency, and permits no proxy or caller-selected actor. A
superseded package is read-only, an acknowledgement is appended only to the
unique current package, and no protected stale response is displayed as
confirmed current truth.

Rollback before retained data may disable the independent P7-06 route and
workspace switches. After retained policy, package, acknowledgement,
observation, receipt or audit history exists, rollback is route/workspace
disable plus a reviewed forward repair; retained revisions, source snapshots,
acknowledgements, receipts and audits are not deleted, rewritten, renumbered or
inherited.

## 7. Transition

This evidence closes checkpoint 3 only. It does not claim controlled runtime,
P7-06 Level 2 or Level 3. Standing authorization activates only checkpoint 4:
extend the cumulative disposable-Site fixture through P7-06 and prove policy
publication, package supersession, exact actor acknowledgements, independent
observation revisions, identity-free offline providers, immutable
reconstruction, same- and cross-process replay, stale/fork/conflict/rollback,
IDOR, route recovery, migrations, redaction, zero Gate/Project/Work Item/
Tooling/ERP/network/Outbox effects and cleanup; then complete traceability,
Task Diff Review and Level 2.

No further UI or formal receiving/signature/G7/external-production authority
is activated. The latest complete Level 3 remains workflow `31392474781` at
exact SHA `22cb24d42174a5b75f475127ac3aa9fee5a08606`.
