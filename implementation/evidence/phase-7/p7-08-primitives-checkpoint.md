# P7-08 Checkpoint 1 — Reviewed Field Primitives

Recorded: `2026-08-15`

Decision: `PASS — CHECKPOINT 1; CHECKPOINT 2 AUTHORIZED`

Product checkpoint:
`300bc167fbe2912a5a7fac7e31c86f025521749e`

Ordinary pull-request CI: `31891796533`

## Scope delivered

- Added one local reviewed scan-entry primitive. It accepts only bounded text
  supplied by a device, keyboard wedge or manual entry; trims surrounding
  whitespace; rejects empty, overlong and control-character input; and
  exact-matches only the reference values supplied by the already-authorized
  workspace.
- Kept review and apply as separate operator actions. Review displays the exact
  business label and identifier without invoking the caller. Apply rechecks
  the current authorized reference set, invokes only the local callback and
  states explicitly that no command was submitted. Changing input invalidates
  prior review.
- Added explicit empty/unknown/ambiguous/unavailable/applied truth, translated
  accessible labels/status, one-primary-action presentation and `44px` field
  touch targets at the existing tablet breakpoint.
- Added a mobile-only same-authorized-workspace handoff stating that complex
  engineering tables remain on desktop. Added the reciprocal
  `desktop-engineering-only` responsive policy without applying it to a live
  page in this checkpoint.
- Added direct Simplified and Traditional Chinese translations and regenerated
  the Frappe-backed frontend catalog. No backend route, Schema, permission,
  business state, persisted row or runtime fixture changed.

## Changed-files to affected-checks map

| Changed paths | Affected checks |
|---|---|
| `frontend/src/components/mobile-field-actions.tsx` | five focused unit cases; TypeScript; ESLint; industrial UI/boundary audits |
| `frontend/tests/unit/mobile-field-actions.test.tsx` | exact match, separate apply/no automatic callback, invalidation, fail-closed values, unavailable state and direct `zh`/`zh-TW` copy |
| `frontend/src/styles/app.css` | Stylelint; industrial UI audit; unchanged fixed-Linux visual matrix |
| both Frappe translation CSVs and generated catalog | generation check; i18n extraction/coverage; mixed-language source audit |

## Local Level 1 evidence

- `npm exec vitest -- run tests/unit/mobile-field-actions.test.tsx`:
  `5/5 PASS`.
- `npm run typecheck`: PASS.
- `npm run lint`: PASS, including Stylelint, boundary audit, industrial UI
  audit and i18n audit at `7,457` literal English sources with `100%` direct
  `zh`/`zh-TW` coverage.
- `npm run generate:check`: PASS.
- `python3 scripts/verify_current_task.py`: PASS with only allowlisted task
  paths after commit.
- controller/reconciliation unit tests: `30/30 PASS`.
- `python3 scripts/verify_v1_2_reconciliation.py`: PASS.
- `git diff --check`: PASS.

## Exact-SHA ordinary CI evidence

- Repository job `95029057330`: PASS; `1,921` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95029057344`: PASS; `59/59` files, `918/918` unit tests,
  `408/408` non-visual E2E, generation/type/lint/build/audit, coverage
  `80.35%` statements, `80.28%` branches, `82.94%` functions and `83.02%`
  lines, `7,457` complete direct trilingual sources and zero vulnerabilities.
- Secret job `95029057296`: PASS; `28` first-parent task commits and `485`
  complete branch commits contain no leak. Artifact `9248733354`, digest
  `sha256:50089cf62f05bb1279079634a7845bba9a68a04d388ac8d969c891ee3c63e5f1`.
- Visual job `95029057308`: PASS; unchanged `115/115` fixed-Linux matrix.
  Artifact `9248783301`, digest
  `sha256:8c9e1354c6348e521a58b5b15bffc93f3ffa16ccfa1b7ae99bf6e0c7a27ca11d`.
- Controlled preflight/runtime skip as expected because this checkpoint opens
  no route, backend contract, runtime fixture or persisted truth.

## Review and rollback

The Task Diff Review found no caller-supplied actor/tenant/permission, network
request, automatic submission, camera decoder, dependency, private locator or
business transition. Exact reference values remain identifier/business-data
language exemptions only; all surrounding UI is direct trilingual copy.

Before any live integration, rollback is removal of the independent component,
styles, tests and translations. After later use, disable only the P7-08 mobile
entry surfaces and deliver a reviewed forward repair; do not rewrite any Trial,
Gate, File Revision, evidence, defect, receipt or audit history.

This is checkpoint 1 PASS. It is not P7-08 Level 2 and does not replace the
final Phase 7 Level 3 release gate.
