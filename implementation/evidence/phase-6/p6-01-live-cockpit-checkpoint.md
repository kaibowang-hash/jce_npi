# P6-01 Live Tooling Cockpit Checkpoint

Date: `2026-08-07`

Status: `PASS — CHECKPOINT 3`; this is not the P6-01 Level 2 Task Gate.

## Delivered boundary

Product commit `a541cf9b96d3247a7d1c9561c1e328e06a377b4f` adds only the
server-backed live Tooling cockpit checkpoint:

- a strict browser data source for the two authorized queries and five narrow
  create commands already closed by checkpoint 2;
- Project-scoped live routes for the cockpit and exact logical Master while
  retaining the approved fixture Tooling prototype as a separate demo path;
- a dense square tree/table/inspector workspace showing distinct Part and
  Part Revision, Tooling Requirement, logical Tooling Master and immutable
  applicability truth;
- server-capability-driven Part, successor Revision, Requirement, Master and
  Applicability actions with one visible primary action per context;
- CSRF, actor/session and idempotency enforcement, including a regression that
  proves an uncertain retry keeps the same idempotency key and receives a new
  abort signal; and
- explicit normal, empty, loading, no-permission/unavailable, read-only,
  validation, conflict, processing, retryable and unsaved-context states with
  direct English, `zh` and `zh-TW`, keyboard/focus, accessible scroll regions
  and non-color-only status.

Lifecycle, Tooling Revision, physical Set, Trial and ERPNext projection remain
explicitly unavailable. This checkpoint installs no lifecycle or numbering
policy, production mapping, source adapter, ERPNext endpoint, credential,
dependency or production default.

## Local affected and full checks

- strict data-source and page/router/Shell focused unit checks: `64/64` PASS;
- complete frontend unit suite: `40` files and `730/730` PASS;
- complete tracked Python suite: `1,120/1,120` PASS;
- direct P6-01 browser matrix: `13/13` PASS, including three languages, exact
  Master route, command processing/conflict, unavailable/IDOR, validation and
  five visual cases;
- generated-source check, TypeScript, ESLint, Prettier, Stylelint, boundary and
  industrial UI audits: PASS;
- i18n audit: `4,059` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- P0 visual governance, prototype approval, V1.2 reconciliation,
  `git diff --check` and zero-vulnerability npm audit: PASS; and
- Linux actual review confirms the normal, empty and read-only cockpit remains
  flat, square, high-density and honest about every unavailable downstream
  capability.

## Evidence-only ordinary-CI repair sequence

Initial exact-SHA ordinary CI `31180308383` ran product commit `a541cf9`.
Repository `92871730526` passed `verify.sh` and `310` of `311` non-visual
browser cases; its sole failure was the inherited R1-03 Shell assertion that
still expected live Project Tooling to be unavailable. Visual
`92871730518` ran the unchanged `68`-case matrix: `12` cases without the
catalog footer passed and the other `56` failed only because the new direct
translations changed the rendered catalog fingerprint. Artifact `8994577675`,
digest
`sha256:e517ad8161c0f591f945e8a75c6934e5ad1b3be7c91da565210198d342b8455f`,
provided exactly those `56` stable actuals.

Repair commit `2f3de3f75fa468204ad18a23f1b35002b58da29b`:

- updates the single stale Shell assertion to require the live
  `Open Project Tooling` command with `aria-disabled="false"`;
- synchronizes only the `56` artifact-proved fixed-Linux baselines; and
- adds the five P6-01 visual cases and their artifact paths to the governed
  visual job without changing an assertion, threshold or PASS rule.

Ordinary CI `31182336001` then passed repository `92878385031`, complete
`311/311` non-visual E2E and both secret lanes. Visual `92878385176` passed
all prior `68` cases and failed only the five newly governed P6-01 cases
because their Linux baselines did not yet exist. Artifact `8995357252`, digest
`sha256:f56e9f1e7eec67bf5c0e953670f736bb7a28251da3dedd2f2a7053e77c27591f`,
contained exactly five CRC-validated P6-01 actual PNGs.

Baseline commit `1f11f3c3e88085e0615aaf3d08be397d29a7525e` adds only those
five byte-exact Linux images. Final exact-SHA ordinary CI `31183116349` is
PASS:

- repository `92880986264`: `verify.sh`, `311/311` non-visual E2E,
  current-tree Gitleaks and complete PR-history Gitleaks PASS;
- visual `92880986015`: the expanded fixed-Linux matrix passes `73/73`;
- visual artifact `8995663993`, digest
  `sha256:aae122bfd243e5da75090182be806e14d052a36e2bb6083271cdc2d91ea7b89b`;
- Gitleaks artifact `8995862579`, digest
  `sha256:4be64953d6cc5fef3924d50ed3730a33b5857bab63ebda8208d3495c79c59e36`;
  and
- controlled runtime `92880986862` correctly skipped.

## Task Diff Review and rollback

The checkpoint changes only the Tooling browser data source/page/routing,
direct translations/generated catalog, bounded shared-header typing, local
styles, focused component/E2E tests, governed visual workflow coverage and
artifact-proved baselines. It does not alter the frozen public BFF contract,
permissions, DocTypes, ownership, transaction, audit, replay rules, baseline
thresholds or PASS criteria. Every unrelated dirty or untracked user file was
excluded from all commits.

Before retained product use, rollback may revert the three cockpit commits.
After retained use, the checkpoint 2 independent route switch remains the
safe forward-only disable path; no retained Part, Revision, Requirement,
Master, Applicability, audit or idempotency row is deleted or rewritten.

## Decision and next boundary

Checkpoint 3 passes. The next unfinished boundary is checkpoint 4 only:
disposable-Site migration and controlled create/reuse/applicability/replay/
rollback/IDOR/route-disable proof, followed by complete ordinary CI and the
P6-01 Level 2 Task Gate. The controlled Site may run only after its verifier
and workflow changes pass affected checks and complete ordinary CI.
