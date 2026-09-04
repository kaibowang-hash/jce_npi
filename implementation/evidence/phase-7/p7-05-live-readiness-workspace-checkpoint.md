# P7-05 Checkpoint 3 — Live Project Readiness Workspace

Recorded: `2026-08-12T05:43:01Z`

Decision: `PASS — CHECKPOINT 3`

Exact product implementation:
`583f3474133e7044bbfb11643b79342f75146d5f`

Exact final checkpoint:
`680877f8a12886f3aff42f07569a6bb4787a844f`

Final ordinary pull-request CI:
`31566736104` (`PASS`)

## 1. Bounded outcome

Checkpoint 3 delivers only the frozen live Project readiness workspace:

- one strict seven-route readiness data source with closed response parsing,
  exact Project-route correlation, UUIDv5 identities, canonical SHA-256 hashes,
  linear revision validation, abort support and actor-bound idempotency;
- the existing `App` to `ProjectPage` to `ProjectWorkspace` dependency-
  injection chain, without constructing a hidden live source inside the page;
- a dense blocker-first Project tab with category/item inspection, exact owner,
  due date, confirmation, evidence/source state, server-derived category/total
  score, dominant blockers and immutable revision history;
- exact Project-member owner candidates and only server-returned source options;
  retained unsupported exact sources remain read-only rather than becoming a
  generic picker;
- safe initialization for the client-provable applicability subset, with an
  impact review; Project/customer-selector ambiguity fails closed without a
  write;
- one-item revision through an impact review, same-key retry/replay, explicit
  conflict reload and preservation of non-Work-Item exact sources;
- honest loading, empty, read-only, permission, validation, conflict,
  processing, retry, replay, drift and five external-provider-unavailable
  states; and
- English, Simplified Chinese and Traditional Chinese coverage, keyboard
  navigation, dirty-draft transition protection, Axe checks and bounded
  desktop/zoom overflow behavior.

The browser cannot submit or derive readiness score, blocker, ready-state or
Gate truth. This checkpoint performs no Gate decision/transition, ERP contact,
Outbox write, Work Item or Tooling mutation, handover, release, projection or
print operation.

## 2. Diagnostic CI and exact root isolation

Diagnostic pull-request run `31565808057` used exact product SHA
`583f3474133e7044bbfb11643b79342f75146d5f`:

- repository job `94017246048` passed `1,715` tracked Python tests;
- frontend job `94017246145` passed `56/56` files and `881/881` unit tests,
  `388/388` non-visual E2E tests, `7,003` direct literal sources with `100%`
  `zh`/`zh-TW` coverage, statements `80.14%`, branches `80.14%`, functions
  `82.78%`, lines `82.80%` and zero vulnerabilities;
- secret scan `94017246049` passed;
- visual job `94017246071` reported `100` passed and `9` failed out of `109`;
  all three new P7-05 visuals passed, and the only failures were the retained
  P5-01 Documents, P5-04 EBOM and P5-06 Controlled Print Project screenshots
  in English, `zh` and `zh-TW`; and
- controlled preflight `94017246466` and controlled runtime `94017246457`
  skipped as required for ordinary checkpoint CI.

Artifact `9129472699`, digest
`sha256:5d7014b3579d03522bf0f6ff7b16bfb031b2f88133a212c696dd777dc0aa3071`,
shows the nine differences were the expected shared Project navigation change
from adding the NPI readiness tab. This run is a diagnostic failure and is not
used as PASS evidence.

## 3. Bounded baseline repair

Final checkpoint `680877f8a12886f3aff42f07569a6bb4787a844f` changes only:

- the nine independently reviewed fixed-Linux retained Project-navigation
  baselines; and
- their nine exact paths in `implementation/CURRENT_TASK.json`.

It changes no product DOM, CSS, copy, test case, visual matrix, assertion,
threshold, tolerance or PASS criterion. No Darwin or local Playwright artifact
is committed.

## 4. Final exact-SHA ordinary CI

Pull-request run `31566736104` completed successfully at exact head
`680877f8a12886f3aff42f07569a6bb4787a844f`:

- repository `94019970901`: `1,715/1,715` tracked Python tests;
- frontend `94019970910`: `56/56` files, `881/881` unit tests, `388/388`
  non-visual E2E tests, `7,003` direct literal sources with `100%` `zh`/`zh-TW`
  coverage, statements `80.14%`, branches `80.14%`, functions `82.78%`, lines
  `82.80%` and zero vulnerabilities;
- secret scan `94019970998`: current task and full pull-request branch history
  passed;
- visual `94019970973`: the complete fixed-Linux matrix passed `109/109`;
- controlled preflight `94019971431` and controlled runtime `94019971505`
  skipped as required.

The final visual artifact is `9129807135`, digest
`sha256:e20dfe9b419427b6e9ef2b0ae5c522e5ba25b00fb48dbc3ca8407e11e788f810`.
The Gitleaks artifact is `9129723639`, digest
`sha256:19e9e801da100b1fcb3761a7a3ccac4b7379523edf0759bda4ab4dd5d76b743e`.

## 5. Task-scope review

The exact checkpoint-3 range
`e98c50b6b6e686322d095605b3ee8272a4f988d5..680877f8a12886f3aff42f07569a6bb4787a844f`
contains `27` paths and `8,171` insertions with `4` deletions, excluding binary
baseline byte counts. Product implementation `583f347` contains the bounded
source/workspace/translation/test/CI files and three new P7-05 Linux visuals;
final checkpoint `680877f` contains only nine reviewed retained Linux PNGs and
the exact task-path guard. Every path is authorized by the current P7-05
manifest. Existing unrelated dirty Makefile, README, development docs, local
evidence, Darwin screenshots and public assets were not staged or changed by
these commits.

## 6. Security and rollback

The boundary remains Project-first and fail closed. It accepts only closed
canonical readiness snapshots, recalculates exact UUID/hash/lineage truth,
binds commands to CSRF and actor idempotency, limits owner/source choices to
exact authorized candidates and retains immutable history. No protected stale
response is displayed as current truth.

Rollback before retained data may disable the independent P7-05 route,
workspace and Gate-input switches. After retained readiness history exists,
rollback is route/workspace/Gate-input disable plus reviewed forward repair;
templates, Project instances, evidence, receipts, audits and derived snapshots
are not rewritten.

## 7. Transition

This evidence closes checkpoint 3 only. It does not claim controlled runtime,
P7-05 Level 2 or Level 3. Standing authorization activates only checkpoint 4:
extend the cumulative disposable-Site fixture through P7-05, execute the
exact-SHA controlled runtime and complete traceability and Task Diff Review.
The latest complete Level 3 remains `31392474781` at
`22cb24d42174a5b75f475127ac3aa9fee5a08606`.
