# P7-08 Plan — Mobile Field Actions

Recorded: `2026-08-15`

Status: `COMPLETE — LEVEL 2 AND PHASE 7 LEVEL 3 PASS`

Starting controller checkpoint:
`eee737f1eef1937c6a515586850a9ea62e68686a`

Retained predecessor product checkpoint:
`dda9c13a6c3b499347cb96c830de2a034fa61203`

Checkpoint 1 product checkpoint:
`300bc167fbe2912a5a7fac7e31c86f025521749e`

Checkpoint 2 product commit:
`a0a024d45341739fc6441faee876d4876932b2eb`

Checkpoint 2 final checkpoint:
`290c66fe3e2e5c53058b5253b844c6332902f189`

Checkpoint 2 ordinary CI:
`31894667043`

Checkpoint 3 product checkpoint:
`5e8384f968e1b3e147d5810117ea46b252f483da`

Checkpoint 3 final repair checkpoint:
`31114021cf18cf5e32c22902de5150ed2922e7ba`

Checkpoint 3 ordinary CI:
`31898840279`

Final Phase 7 Level 3 workflow:
`31899480493`

Primary requirement: `UX-020`

Reconciled Pack anchors: `FR-UX-016` and `NFR-UX-001`

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is complete. Exact
controller SHA `eee737f` passes ordinary pull-request CI `31889082835`:
repository `95022578841`, frontend `95022578748`, secret scan `95022578755`
and fixed-Linux visual `95022578694` at `115/115` all pass. Controlled jobs
skip as expected because the P7-07 closeout and P7-08 audit activation change
no product or runtime truth.

The V1.2 DOCX requirement is explicit: mobile prioritizes approval, status
updates, photo upload, issue capture and scan entry; complex tables remain on
desktop, and the acceptance example requires phone-based Trial issue capture
and Gate approval. The Pack already requires desktop and field-tablet support,
including view, photo, Trial recording and authorized actions. The Phase 3
prototype proves only local photo selection and in-memory action preparation;
it does not prove a persisted product command.

P7-08 can proceed without a new business decision because it introduces no
role, transition, approval rule, Gate rule, Trial conclusion rule, attachment
policy or external effect. It exposes only existing server-returned
capabilities and existing BFF commands through responsive product layouts.
The same Project-first authorization, authenticated actor, CSRF, optimistic
version/hash, idempotency, audit and validated response contracts remain the
only authority on every viewport.

The audit found the following reusable product truth:

- `frontend/src/pages/live-trial-page.tsx` already loads one authorized
  Project before Plan/Round execution, quality and review data. It already
  submits the same strict BFF commands for private File upload, exact clean
  File Revision binding, cavity results, Trial defects, defect revisions,
  verification, comparison and conclusion actions.
- `frontend/src/api/trial-data-source.ts` validates route UUIDs, closed command
  bodies, CSRF, actor-bound idempotency keys, request/trace identity, replay
  headers and exact response/route containment. The browser cannot supply an
  actor, Project authority, scan result, audit identity or derived success.
- `frontend/src/pages/gate-evidence-page.tsx` already renders only actions
  derived from server permissions and readiness. Start, review, exception,
  Gate decision and reopen actions all use the existing strict Gate BFF
  command coordinator, CSRF, idempotency, conflict/retry and receipt
  reconciliation paths.
- Trial evidence upload already registers a private pending File Revision;
  upload, scan and clean evidence binding are separate. The workspace exposes
  URL-free file identity, scan state and bind availability. A non-clean File
  cannot be bound and no raw private URL is returned or used as authority.
- Trial quality already owns persisted issue capture through exact cavity,
  defect/action and independent-verification commands. No new mobile issue
  aggregate or status transition is needed.
- `AttachmentField` already supports a camera-facing `capture` attribute,
  local/invalid/transport/register/registered/failure/conflict/denied states,
  focus, keyboard and translated accessible labels. The live Trial upload
  editor has not yet reused the photo-facing input.
- The shell already collapses navigation at `720px`; the prototype matrix
  proves one `768x1024` tablet and one `390x844` phone. Live Trial and Gate
  layouts become one column, but they still expose long desktop engineering
  tables in document order and do not provide a focused field summary,
  reviewed scan entry or deliberate desktop handoff.
- No browser barcode/QR input primitive exists. P7-08 will therefore support
  a device or keyboard-wedge scanner through a normal labelled text input,
  exact-match only against references already present in the authorized
  workspace. Review and apply are separate; neither operation submits a
  command.

This is a frontend-only vertical slice. No DocType, migration, ownership,
OpenAPI, repository, BFF route, permission, runtime fixture or production
integration change is required. The final Phase 7 Level 3 Gate nevertheless
reruns the complete repository, trilingual/visual/security matrix and
cumulative disposable Trial runtime so a lower-level responsive change cannot
replace the Phase boundary.

## 2. Frozen outcome

P7-08 delivers one minimum complete path:

> open an authorized live Trial or Gate workspace on phone/tablet -> see the
> exact current Project/object/version/state, blockers and server-permitted
> actions without desktop-table overflow -> capture or choose one Trial photo
> through the existing bounded private upload command -> keep pending/clean/
> failed scan truth explicit and bind only an exact clean File Revision ->
> scan or enter one exact cavity reference, review the parsed match, explicitly
> apply it to the existing issue form without submitting -> record one Trial
> defect through the unchanged quality command -> review and complete one
> server-authorized Gate action through the unchanged Gate command -> retain
> complex engineering tables on desktop while mobile shows an honest summary,
> all critical blockers/version/authority truth and the same authorized-link
> handoff

Desktop remains the engineering-analysis surface. Mobile is a bounded field
action surface over the same data and commands, not a second application or
authority model.

## 3. Frozen invariants

### 3.1 Same authority on every viewport

- Responsive rendering never creates a permission or capability. Every action
  remains derived from the existing server workspace response and disabled
  when session context, exact permission, lifecycle state or dependency is
  unavailable.
- Mobile calls the identical Trial or Gate data-source method and BFF route as
  desktop. CSRF, Project-first reauthorization, expected versions/hashes,
  actor-bound idempotency, transaction, audit, replay and conflict handling do
  not branch on viewport, user agent, camera or scan input.
- A phone may complete a Gate review or decision only when the same loaded
  action is already permitted for that authenticated actor. P7-08 does not add
  a role, approver, quorum, delegation, signature, outcome or Gate state.
- Layout summaries display exact server facts. They do not compute a new
  readiness, approval, status or external result in the browser.

### 3.2 Photo and private-file boundary

- The field photo input accepts images and may request the environment-facing
  camera through the standard file-input capture hint. Cancellation is an
  unchanged empty/local state and submits nothing.
- Selection remains local until the operator explicitly invokes the existing
  private upload command. The command retains the existing `64 MiB` bounded
  input validation, exact Round optimistic version, CSRF and actor-bound
  idempotency context.
- Upload success means only a private pending File Revision. Pending, clean,
  infected and failed scan states remain visible. Only the existing clean-file
  bind command can create Trial evidence, and it revalidates exact File and
  Round versions on the server.
- Mobile never receives, displays, logs or copies a raw private File URL. An
  audited download continues to use the existing authorized byte route.
- Permission unavailable, session unavailable, conflict, retryable failure and
  unconfirmed result remain explicit; no optimistic success is added.

### 3.3 Reviewed scan entry

- P7-08 scans only a bounded text value supplied by a device/keyboard-wedge
  scanner or manual entry. It does not activate a camera API, native bridge,
  background service, dependency or external decoder.
- The value is trimmed, control-character/length checked and exact-matched only
  against cavity references already returned in the authorized Trial quality
  workspace. Unknown or ambiguous values fail closed.
- `Review scanned value` resolves and displays the exact matched label/value.
  `Use reviewed value` is a separate action that only fills the existing
  cavity filter or open quality editor. Changing the input invalidates the
  prior review.
- Review or apply never creates a defect, changes status, uploads evidence or
  submits any BFF command. The operator must still complete the normal form,
  impact review and authenticated command.

### 3.4 Responsive information boundary

- Breakpoints retain the existing shell contract: field tablet up to `920px`
  uses one-column workspaces; phone up to `720px` uses compact navigation and
  a focused field surface. Desktop/zoom cases remain unchanged.
- Mobile summaries retain Project, Plan/Round or Gate identity, exact current
  version/state, permission availability, blocker counts, conflict/failure
  state, evidence scan truth and held external authority. Color is never the
  only state channel.
- Parameter matrices, locked-reference/source manifests, cavity/dimension
  comparison tables, full review histories, baseline impact matrices and
  controlled-output source tables remain available on desktop. Mobile replaces
  them only with bounded counts/current facts plus an explicit statement to
  continue engineering analysis from the same authorized link on desktop.
- Mobile does not compress a wide engineering table into an unusable control,
  and it does not hide blockers or action authority merely to reduce height.
- Touch targets, keyboard focus, labels, 200% zoom-equivalent layout, reduced
  motion and English/`zh`/`zh-TW` direct translation remain required.

## 4. Checkpoints

### Checkpoint 1 — reviewed field primitives and responsive policy

- Add one local mobile-field component for reviewed exact-reference scan entry
  and an honest desktop-engineering handoff.
- Prove input invalidation, exact-match/unknown behavior, separate review and
  apply, no automatic command, disabled/unavailable states, focus and direct
  trilingual copy through unit tests.
- Add only square, dense, single-primary-action responsive styles. No API,
  metadata, permission or business state changes.
- Run affected unit, type, lint, i18n and diff checks, then exact-SHA ordinary
  CI before checkpoint 2.

### Checkpoint 2 — live Trial field actions

- Add a phone/tablet Trial field summary using already loaded exact workspace
  facts and same-page anchors.
- Reuse the existing attachment primitive for environment-camera photo
  selection while preserving the existing private upload and clean bind
  commands and generic desktop file path.
- Add reviewed cavity scan entry to the existing quality workspace and apply
  only to the filter/open editor. Keep normal defect review/submit unchanged.
- Mark only enumerated engineering tables desktop-only and show mobile counts,
  blockers and deliberate handoff instead.
- Prove camera/file selection, cancellation, pending/clean/failed/permission
  states, scan review/apply/no-submit, issue command CSRF/idempotency and
  phone/tablet accessibility in the focused P7-08 browser suite.

### Checkpoint 3 — live Gate field review and final Phase Gate

- Add a phone/tablet Gate summary with exact Project/Gate/cycle/policy/version,
  readiness blockers, server-permitted action and held authority.
- Reorder only the responsive presentation so the existing inspector action is
  reachable before desktop evidence/history matrices. Keep all action
  construction, impact review, command coordinator, receipt, retry and conflict
  paths unchanged.
- Retain desktop requirements/evidence/history/baseline tables; render bounded
  mobile summaries and explicit desktop handoff for those matrices.
- Prove a phone completes one already-authorized Gate review/decision through
  the exact existing BFF command with CSRF and idempotency, while denied,
  read-only, blocked, conflict and processing states expose no extra action.
- Generate and independently review fixed-Linux English/Simplified Chinese/
  Traditional Chinese phone/tablet visuals plus a desktop complex-table guard.
- Run the Level 2 Task Gate, then the final Phase 7 Level 3 `release-gate`
  review and cumulative disposable Trial runtime before activating P8-00.

## 5. Expected changed files

| Change | Expected paths |
| --- | --- |
| reviewed scan and handoff primitives | `frontend/src/components/mobile-field-actions.tsx`; `frontend/tests/unit/mobile-field-actions.test.tsx` |
| Trial field product surface | `frontend/src/pages/live-trial-page.tsx` and affected Trial tests |
| Gate field product surface | `frontend/src/pages/gate-evidence-page.tsx` and affected Gate tests |
| responsive industrial policy | `frontend/src/styles/app.css` |
| focused browser/visual proof | `frontend/tests/e2e/p7-08-mobile-field-actions.spec.ts`; governed Linux snapshots; `.github/workflows/ci.yml` visual list |
| direct localization | `apps/npi_core/npi_core/translations/zh.csv`; `apps/npi_core/npi_core/translations/zh-TW.csv`; generated catalog |
| controller/trace/evidence | P7-08 controller, trace, risk, Phase Gate and evidence files |

No backend Python, DocType JSON, hook, patch, OpenAPI or ownership file is
expected. Discovery of a required server contract change pauses that dependent
part and reopens the audit rather than silently expanding P7-08.

## 6. Changed-files to affected-tests map

| Changed boundary | Minimum affected evidence |
| --- | --- |
| mobile field component | component unit tests; typecheck; eslint/prettier/stylelint; i18n extraction and direct-catalog checks |
| Trial integration | live Trial unit tests; P7-02 execution and P7-03 quality regressions; P7-08 phone/tablet camera, scan and persisted-defect flow; no raw URL/mixed-language/axe/overflow checks |
| Gate integration | Gate page/data-source unit regressions; P7-08 phone authorized action plus blocked/read-only/conflict states; same CSRF/idempotency/receipt assertions |
| responsive CSS/shared translations | affected English/`zh`/`zh-TW` Trial and Gate visuals first; complete fixed-Linux matrix at Level 3 |
| CI visual enrollment | current-task verifier, workflow/static governance and exact fixed-Linux P7-08 visual count |
| final trace transition | reconciliation generator/verifier tests, current-task verifier, Task Diff Review and complete Level 3 trace |

## 7. Migration, security and rollback

- Migration impact is `NONE`: P7-08 adds no schema, data row, patch, hook,
  route, worker or dependency. Existing Trial/Gate runtime migrations must
  still pass twice in the final cumulative disposable Site.
- Security impact is presentation-only but authority-sensitive. Tests must
  prove identical paths/headers/bodies, no caller actor/authority, no raw File
  URL, no automatic scan command, explicit denied/read-only/conflict truth and
  unchanged Project containment.
- Before any P7-08 product commit, rollback is the exact P7-07 product
  checkpoint plus this audit/controller evidence.
- After deployment, disable only the independent mobile field presentation and
  deliver a reviewed forward repair. Do not delete, rewrite or renumber any
  existing Project, Gate, Trial, issue, File Revision, evidence, receipt,
  audit, conclusion, summary or controlled-output history.
- Desktop Trial/Gate workspaces and every existing BFF command remain the
  recovery path; no database downgrade or external compensation is required.

## 8. Explicit non-scope and holds

- No mobile-only role, permission, status, approval, Gate decision, Trial
  conclusion, evidence policy, file route, audit rule or external effect.
- No camera barcode/QR decoding, automatic submission, offline cache/sync,
  service worker queue, native app, background upload, device management,
  push notification or biometric/signature semantics.
- No generic DocType CRUD, Frappe Desk product path, Frappe/ERPNext core patch,
  production ERPNext access, Outbox/Inbox, formal NCR/Quality Inspection,
  customer signature, production reservation or Phase 8 integration.
- Existing business UAT and representative-data holds remain truthful. P7-08
  may reach `TECHNICAL_VERIFIED`; it does not sign the Phase 3 business UAT on
  behalf of Project, Engineering/Tooling or Quality representatives.

## 9. Automatic transition

The audit passes and authorizes only checkpoint 1. Standing continuous-
delivery authority permits automatic progression after each exact-SHA ordinary
CI and affected Gate passes. P7-08 completes only after Level 2 and the final
Phase 7 Level 3 `release-gate` both pass. Only then may the controller activate
`P8-00`; production ERPNext remains prohibited.

## 10. Completion record

Checkpoint 3, the Level 2 Task Gate and the final Phase 7 Level 3 Gate passed
at exact final product SHA `31114021cf18cf5e32c22902de5150ed2922e7ba`.
The complete ordinary, fixed-Linux visual, security, trace, cumulative
disposable-Site and release-review evidence is recorded in
`implementation/evidence/phase-7/p7-08-validation.md` and
`implementation/phase-7-gate.md`. This completion changes no backend route,
Schema, permission, ownership, dependency, migration or external adapter and
does not authorize production ERPNext contact.
