# P7-08 Checkpoint 2 — Live Trial Field Actions

Recorded: `2026-08-15`

Decision: `PASS — CHECKPOINT 2; CHECKPOINT 3 AUTHORIZED`

Product implementation commit:
`a0a024d45341739fc6441faee876d4876932b2eb`

Final checkpoint:
`290c66fe3e2e5c53058b5253b844c6332902f189`

Ordinary pull-request CI: `31894667043`

## Scope delivered

- Added a mobile-only Trial field summary before the engineering workspace.
  It displays exact authorized Project, Plan, Round, state/version, non-clean
  file count, latest open blocking-defect count, verified session context and
  server-returned photo/defect action availability. It derives no readiness,
  status, permission or external result.
- Reused the existing Trial evidence upload editor and `AttachmentField` with
  `accept="image/*"` and `capture="environment"`. Selection remains local,
  cancellation and clear are explicit, and only `Start file transport`
  invokes the unchanged bounded private pending-upload command with the same
  CSRF, optimistic version and actor-bound idempotency boundary.
- Reused `ReviewedScanEntry` against exact cavity references already present
  in the authorized quality workspace. Review and apply remain separate;
  apply changes only the cavity filter and an open editor's exact cavity ID;
  neither step submits a command. The existing defect review/submit command is
  unchanged.
- Kept pending, clean, infected/failed and permission-unavailable File truth
  visible and URL-free. Marked only enumerated Plan, execution, quality,
  comparison and released-summary engineering matrices desktop-only; mobile
  retains blockers, evidence, command bars, conflicts and held external truth
  plus an explicit same-authorized-link desktop handoff.
- Added ten direct English-source translations in both Simplified and
  Traditional Chinese catalogs. No backend route, API contract, Schema,
  permission, business state, dependency, migration, runtime fixture or
  production integration changed.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `live-trial-page.tsx` | live Trial unit regressions; phone/tablet summary, upload and defect command E2E; TypeScript and boundary audit |
| `app.css` | Stylelint, industrial UI audit, responsive overflow/geometry and unchanged fixed-Linux matrix |
| translation CSVs and generated catalog | generation check, `7,467`-source direct trilingual coverage and mixed-language scans |
| `p7-08-mobile-field-actions.spec.ts` | six phone/tablet exact-truth, permission, camera, scan, CSRF/idempotency, accessibility and overflow cases |
| P7-01 assertion repair | three locale planning-truth cases scoped to the intended `#trial-live-plans` list plus complete E2E regression |

## Local Level 1 evidence

- `npm run generate:check`, `npm run typecheck` and full `npm run lint`: PASS;
  format, Stylelint, boundary audit over `87` source files, industrial UI audit
  and i18n audit at `7,467` literal English sources with `100%` direct
  `zh`/`zh-TW` coverage pass.
- Focused Vitest for live Trial and mobile-field primitives: `38/38 PASS`.
- Focused P7-08 browser suite: `6/6 PASS` for phone/tablet three-language
  summary, pending/clean/failed/permission truth, camera cancellation/local
  selection/explicit upload and reviewed scan/no-submit/unchanged defect
  command.
- After diagnostic CI isolated the legacy broad `T0` locator, focused P7-01
  plus P7-08 non-visual browser regression: `13/13 PASS`; targeted Prettier and
  ESLint pass.
- Current-task/controller/reconciliation unit tests: `30/30 PASS`;
  `scripts/verify_current_task.py`, V1.2 reconciliation and
  `git diff --check`: PASS.

## Exact-SHA ordinary CI evidence

- Repository job `95036026662`: PASS; `1,921` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95036026724`: PASS; `59/59` files, `918/918` unit tests,
  `414/414` non-visual E2E, generation/type/lint/build/audit, coverage
  `80.35%` statements, `80.31%` branches, `82.89%` functions and `83.01%`
  lines, `7,467` complete direct trilingual sources and zero vulnerabilities.
- Secret job `95036026676`: PASS; `29` first-parent task commits and `488`
  complete branch commits contain no leak. Artifact `9249464490`, digest
  `sha256:6098cd5f213b0a030a724ca4eb2284b837a8559a24a4c8063b129fe70ff1b02f`.
- Visual job `95036026641`: PASS; unchanged `115/115` fixed-Linux matrix.
  Artifact `9249514548`, digest
  `sha256:845f99b34e678ed27f7409b08f16b7c1db7d3b8f1aa1d881802b8b9ea6d35f3c`.
- Controlled jobs skip as expected because this checkpoint opens no route,
  backend contract, runtime fixture or persisted business truth.

## Diagnostic evidence and repair

Ordinary CI `31893986953` retained `411/414` E2E and failed only the three
locale variants of the P7-01 planning-truth test. Its broad first `T0` query
selected the newly present but desktop-hidden mobile summary before the exact
Plan list. The product truth, all six P7-08 cases and `115/115` visual matrix
passed. Repair commit `290c66f` scopes the legacy assertion to
`#trial-live-plans`; it changes no product behavior, test criterion or expected
truth. Fresh exact-SHA CI `31894667043` proves the complete `414/414` suite.

## Review and rollback

The Task Diff Review found no caller-supplied actor, Project authority,
permission, status, audit identity, raw private locator, automatic submission,
camera decoder, background queue, dependency or external effect. Mobile calls
the same data-source methods as desktop. The corrected label is `Files not in
clean state` because the count truthfully includes every pending, infected or
failed item.

Rollback disables only the independent P7-08 mobile summary, camera-facing
selector, reviewed cavity entry and responsive handoff, then delivers a
reviewed forward repair. It never rewrites a Trial Plan/Round/input, File
Revision, evidence bind, defect/action/verification, conclusion, summary,
receipt or audit record.

This is checkpoint 2 PASS. It is not P7-08 Level 2 and does not replace the
final Phase 7 Level 3 release gate.
