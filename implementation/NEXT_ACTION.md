# Next Action

Status:
`IN_PROGRESS_DIAGNOSTIC — AUTHORIZED POST-CHECKOUT REVISION/UPLOAD STAGES`

Recovery time: `2026-07-31T05:42:15Z`

Latest complete CI recovery checkpoint:
`2d5d57c49ea3a5a0d2828f1a1b745d3f70a9cc23`

Local and remote development-branch SHA:
`2d5d57c49ea3a5a0d2828f1a1b745d3f70a9cc23` (`0 ahead / 0 behind`)

Blocker-checkpoint normal CI:
`30606322575` (`PASS`; controlled runtime correctly skipped on PR event)

Retained P5-01 checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- The cumulative R1 shared Shell/design/i18n Level 3 exit Gate is `PASS`.
- `R1_SHARED_BRIDGE` is released.
- R1-01 through R1-06 are complete for their executable scope.
- `DR-REC-001` remains pending; conditional R1-07 was not activated or marked
  complete.
- Phase 5 remains `IN_PROGRESS`.
- P5-00 remains `PASS`.
- The user authorized the P5-01 recovery plan on 2026-07-31. The controller
  now counts only uniquely proven product roots toward the five-round repair
  budget; environment remediation and behavior-neutral diagnostics remain
  fail-closed but do not consume that budget.
- P5-01 is `IN_PROGRESS_DIAGNOSTIC`. Its seven Requirement rows remain
  incomplete, and P5-02 remains inactive.
- The authorized projection-validation diagnostic checkpoint `57b4314`
  passed complete normal CI `30604536515`. Its sole diagnostic dispatch
  `30604964265` safely proved
  `DOCUMENT_CHECKOUT_PROJECTION_REVISION / ValidationError` with one exact
  trace ID.
- The only proven repair `7dc4dc0` normalizes Frappe's empty-`Int` zero
  hydration only when both revision IDs are absent. Focused `44/44`,
  complete P5 Document `88/88` and complete tracked Python `789/789` checks
  pass, and complete normal CI `30605323680` passed.
- The final controlled-Site runner and verifier were unchanged. The sole
  final Gate `30605683679` matched `7dc4dc0`; repository/E2E/security,
  fixed-Linux visual, setup, both migrations and cleanup passed.
- The controlled job failed later with only the safe
  `UNEXPECTED_BFF_EXCEPTION / PdfStreamError` result and one exact trace ID.
  This is outside the authorized projection-validation repair. The final
  Gate is exhausted, no runtime PASS is claimed, and P5-01 Level 2 did not
  run.
- P5-01 resume audit, frontend, direct trilingual, unit, browser, visual and
  static runtime checks pass. The prior PdfStream authorization hold is
  satisfied; no controlled runtime `PASS` is claimed.
- The frontend/runtime/security checkpoint passed complete CI `#79`, run
  `30560612349`, including `285/285` non-visual browser cases, fixed-Linux
  visuals and both current-tree and complete PR-history secret scans.
- The manual-lane checkpoint passed the same complete normal CI as `#80`, run
  `30561689283`.
- Manual run `30562284484` failed before Bench/Site/Compose/database work
  because strict npm policy rejected an unnecessary Yarn global install; no
  controlled runtime result is claimed from that run.
- The bounded Yarn repair passed complete normal CI `#81`, run
  `30562550109`.
- Manual run `30563106063` installed both exact Python packages and confirmed
  exact Yarn, then failed a silent CLI version-rendering comparison before
  initialization; no controlled runtime result is claimed from that run.
- The distribution-metadata repair passed complete normal CI `#82`, run
  `30563401058`.
- Manual run `30564025523` passed tool/Bench/database guards and created only
  the fresh Site, then failed before NPI app installation because the pinned
  Bench registry lacked a terminal newline. Its containers, volumes and
  network were removed; no controlled document runtime result is claimed.
- The app-registry repair passed normal run `30564533440`, including the
  complete repository, browser, visual and both secret lanes.
- Manual run `30565065165` installed both NPI apps on the fresh guarded Site
  and completed both migrations, then the verifier failed closed because its
  schema fixture required obsolete `response_payload` metadata instead of the
  existing sealed `response_snapshot` and `response_sealed` pair. Cleanup
  removed the runner-local containers, volumes and network; no controlled
  document runtime result is claimed.
- The schema-inventory repair passed normal run `30565607707`, including the
  complete repository, `285/285` browser, fixed-Linux visual and both secret
  lanes.
- Manual run `30566120000` passed both migrations and the corrected schema
  fixture, then Project creation returned HTTP `422` because the synthetic
  fixture supplied non-email owner `Administrator`. Cleanup removed the
  runner-local containers, volumes and network.
- The fifth failed round remains preserved as a truthful historical Hard
  Blocker.
- The user-authorized extra repair is complete at `a2d98e2`. Affected
  runtime/verifier tests pass `91/91`, complete tracked Python tests pass
  `774/774`, and normal CI run `30569830739` passed on the exact SHA.
- Manual run `30570343315` proved the owner lifecycle and advanced through
  Project, Document Policy root and draft creation. Policy publication then
  returned HTTP `500` at the first P5 Frappe `Datetime` persistence boundary.
  Cleanup removed the ephemeral runtime resources.
- The code-backed shared root is canonical ISO `T`/`Z` API text being assigned
  directly to Frappe database `Datetime` fields. The bounded solution must
  separate canonical timestamp truth from Frappe storage formatting across
  all affected P5 Document controllers and add sanitized failure diagnostics.
- The user supplied the exact additional bounded authorization on 2026-07-31
  local time. It permits only the shared Frappe Datetime persistence repair,
  sanitized diagnostics, affected checks, normal CI and one unchanged
  controlled-Site dispatch.
- Datetime repair candidate `7aa14ed` passed normal CI `#98`, run
  `30573186630`. Its one authorized controlled dispatch `#99`, run
  `30573778175`, passed the formerly failing policy publication, controlled
  document creation and immediate idempotency replay, then returned HTTP
  `500` on the first document `:check-out`.
- The verifier's sanitized detail helper covered policy operations but not
  the generic document-workspace assertion. The retained evidence therefore
  cannot uniquely attribute the checkout failure inside the four-step
  persistence/response boundary. The one authorized dispatch is exhausted.
- The user explicitly authorized one additional bounded round limited to the
  document-workspace diagnostic, one diagnostic-only controlled-Site run,
  repair of only the proven checkout root, affected checks/normal CI and one
  final unchanged controlled-Site Gate.
- The diagnostic checkpoint carries the exact deterministic trace identity,
  applies the shared failure boundary to every document workspace result and
  accepts only the existing exact `code / exceptionType / traceId` BFF record
  from one of two fixed physical Bench log paths. It reads no more than the
  final 64 KiB and never emits raw traceback, exception message, request,
  cookie or credential data.
- Focused `15/15` and complete tracked Python `781/781` checks pass locally.
  No product/domain/API/permission/transaction/DocType change is present.
- Exact diagnostic checkpoint `e4b284f` passed complete normal CI `#101`, run
  `30598406263`.
- The sole authorized diagnostic dispatch `#102`, run `30598733723`, matched
  the exact SHA and passed tools, fixed Site/database guards, both app
  installations, both migrations and cleanup. Checkout returned
  `ValidationError / UNEXPECTED_BFF_EXCEPTION`.
- The safe record has no checkout stage code. `ValidationError` remains
  possible at the command-receipt exact-parent check, immutable lock-event
  validation, controlled-document exact lock projection and final receipt
  seal. The result therefore does not authorize choosing one for repair.
- The user supplied the exact additional bounded authorization on 2026-07-31.
  The active checkpoint adds six closed stage codes, preserves the exact
  three-field safe record, ignores business `NpiProblem` outcomes and never
  emits raw exception text, traceback, request, cookie or credential data.
- Focused checkout/repository/verifier tests pass `28/28`; the complete P5
  Document module group passes `83/83`; complete tracked Python passes
  `784/784`; compilation and whitespace checks pass.
- Exact stage-diagnostic checkpoint `954bd0d` passed complete normal CI
  `#104`, run `30600587269`.
- The sole authorized stage-diagnostic dispatch `30600943765` matched that
  SHA, passed exact setup, both migrations and cleanup, and safely proved
  `ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`. Its safe record was
  accepted only after exact request-trace equality; no trace value or raw
  server detail was echoed.
- The bounded repair changes only that proven projection-save boundary. It
  binds the save to the exact immutable acquisition-event name returned by
  the successful insert and retains the controller's database-backed exact
  tenant/Project/Document/lock/event/holder/expiry validation. Invalid
  bindings fail closed and temporary state is restored.
- Focused repair tests pass `41/41`; the complete P5 Document module group
  passes `85/85`; complete tracked Python passes `786/786`; compilation and
  whitespace checks pass.
- Exact repair checkpoint `b2d7ca9` passed complete normal CI run
  `30601670711`.
- The retained final unchanged controlled-Site Gate `30601980685` matched the
  exact repair SHA, passed fixed setup, both migrations and cleanup, but
  returned the same safe
  `ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`.
- This disproves the exact acquisition-event selector hypothesis. The failed
  repair is forward-reverted in the blocker checkpoint.
- P5-02 through P5-05 and Phase 6 remain inactive.
- The current trace contains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Use:

- `implementation/phase-5-requirement-anchor.md`;
- `implementation/evidence/phase-5/p5-01-plan.md`;
- `implementation/evidence/phase-5/p5-01-reconciliation-hold.md`;
- `implementation/evidence/phase-5/p5-01-resume-audit.md`;
- the indexed trace rows and current contracts; and
- `frappe-safe-change`, `npi-domain-guard`, `industrial-ux` and
  `frappe-i18n` Skills.

## First incomplete action

The frontend/runtime-ready checkpoint is recorded at
`implementation/evidence/phase-5/p5-01-frontend-runtime-checkpoint.md`.

The authorized projection-validation diagnostic and its uniquely proven
revision-substage repair are complete. Complete normal CI passes. The single
final unchanged Gate advanced beyond that prior failure and then emitted only
the safe `UNEXPECTED_BFF_EXCEPTION / PdfStreamError` result. It does not
identify a unique revision/upload transaction stage, and the final Gate is
exhausted.

The user has authorized the first incomplete action. Add one closed
revision/upload diagnostic inventory covering receipt insertion, private File
save, File Revision insertion, domain append, Document Revision insertion,
revision/file association, document projection save, audit append, response
build and receipt seal. Emit only stage code, validated exception type and
exact trace ID. Run affected checks and complete normal CI before one
controlled-Site diagnostic dispatch.

After that dispatch, repair only the uniquely proven stage. Rerun affected
checks and complete normal CI, then execute one final unchanged controlled-Site
Gate. Do not change or weaken any Requirement, API, permission, Schema,
file-integrity rule, lock, version, audit, idempotency, transaction order or
PASS criterion.

The terminal result must prove:

1. the exact fixed Site/database/user safety guards;
2. two additive/idempotent migrations and exact nine-DocType metadata;
3. one fresh synthetic policy/Project/document/lock/revision/private file
   round trip with server-observed hash and scanner state;
4. exact CSRF, version, idempotency, replay, audit, Guest and IDOR behavior;
5. route-disable/recovery and second-process replay; and
6. bounded cleanup with no production or external connection.

Only a real PASS may resume the Task Diff/domain/permission/security/UX/i18n
review and P5-01 Level 2 Task Gate. P5-02 remains inactive. Active evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-projection-validation-blocker.md`.

## Retained passing checkpoint evidence

- P5-01 focused domain/repository/API/metadata/controller/contract:
  `63/63`.
- Binary response/failure matrix: `15/15`.
- Affected foundation/BFF/API regressions: `107/107`.
- Nine DocType JSON and OpenAPI/data-ownership/controller metadata checks.
- Direct catalogs at the checkpoint and generated-catalog freshness.
- Exact 55-file retained inventory and no production policy, external
  identity, scanner/viewer, CAD/PDM or ERPNext activation.
- Frontend/runtime-ready candidate:
  `658/658` complete frontend unit, `6/6` P5 browser, `3/3` exact trilingual
  visual, `2,860` complete direct sources, production build, `68/68` P5
  Python/static verifier and `85/85` shared runtime regressions.

These results were impact-reviewed against current shared code and retained in
`implementation/evidence/phase-5/p5-01-resume-audit.md`. Do not repeat
unrelated complete R1 Gates.

## Prohibited or held behavior

- Do not restart the already retained pure domain/backend slice.
- Do not install production document types, prefixes, numbering or revision
  policy.
- Do not infer release/review authority from Project ownership, RACI,
  `System Manager` or the transport role.
- Do not expose a raw private URL or fabricate upload, scanner, preview,
  connector or external-sharing success.
- Do not weaken tenant/Project/object authorization, CSRF, idempotency,
  optimistic version, audit or immutable revision truth.
- Do not start P5-02 review/release, P5-03 baseline, P5-04 EBOM or P5-05
  publish request behavior.
- Do not connect production ERPNext/JCE/CAD/PDM or sign external UAT.

## Transition

The recovery authority is active. Continue the safe diagnostic and uniquely
proven repair inside the remaining product-root budget. Stop only for a real
Class B/C boundary, a required contract/permission/Schema/ownership change, a
concrete security/license risk, or five complete product-root repair rounds.
After one real controlled-Site PASS, complete the final affected reviews and
P5-01 Level 2 Task Gate before activating P5-02.
