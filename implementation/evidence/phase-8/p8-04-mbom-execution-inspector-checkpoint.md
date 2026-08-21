# P8-04 Checkpoint 4 — MBOM Execution Inspector

Recorded: `2026-08-22`

Status: `IMPLEMENTED — AWAITING EXACT-SHA ORDINARY CI`

## Scope and truth boundary

- Extends the existing Phase 5 released-EBOM workspace with one dense,
  direct-trilingual MBOM execution inspector for the exact selected Phase 5
  publish request. It does not add a generic operations screen or a second App
  Shell.
- The fixed Project-first list query is scoped by
  `phase5PublishRequestGlobalId`; list and detail projections revalidate tenant,
  Project, request, source/topology/mapping hashes, node manifest, attempt,
  aggregate Result, per-node Result and current mapping-head evidence. Missing,
  detached, duplicate or inconsistent evidence fails closed.
- A formal BOM ID and target version are rendered only from a current mapping
  that matches an authenticated `authoritative_sandbox` node result and only
  after Project/view authorization. Mock, synthetic, failed, conflict,
  uncertain and unauthenticated truth cannot carry formal identity. Partial
  truth remains per-node: an authoritative successful node may show its exact
  current mapping while sibling failure remains explicit; no aggregate success
  is invented.
- The one visible-text primary action opens Impact Review and sends only the
  exact Phase 5 request ID, four expected hashes and the literal governed
  acknowledgement through the NPI BFF. CSRF, actor-bound idempotency replay,
  request/trace echo and private-no-store remain required. The browser has no
  ERPNext/JCE endpoint, credential, target payload, retry, reconcile or submit
  path.

## Industrial UX and localization

- The inspector preserves the classic light App Shell, flat square borders,
  neutral dense evidence grid, compact four-column engineering table,
  non-color status shape/icon/text and stable right-side EBOM inspector. It
  adds no card wall, gradient, large radius, shadow or decorative asset.
- Covered states are loading, empty, unavailable, no permission, read-only,
  Mock, queued, processing, synthetic, partial, retryable/final failure,
  conflict, uncertainty, submitted immutability and authoritative Sandbox
  observation. Primary action eligibility is fail-closed for missing session,
  permission, profile, context, readiness, immutable/active/uncertain truth or
  submitted expectation.
- Every new source string is a literal English `t()` source with direct Frappe
  CSV entries for `zh` and `zh-TW`. The Frappe v15 no-header catalogs and
  generated catalog remain synchronized; retained `EBOM`, `MBOM`, `BOM`,
  `ERPNext`, `ID`, `CSRF`, hashes and business identifiers follow the governed
  terminology rules.
- Keyboard activation/focus return, Impact Review acknowledgement, WCAG axe,
  non-color status, single-primary, industrial computed-style, overflow and
  mixed-language checks are part of the browser cases.

## Fixed-Linux visual evidence

Only these three checkpoint baselines are governed; no Darwin baseline is in
task scope:

| Case | SHA256 |
|---|---|
| `p8-04-mbom-synthetic-en-1366x768-125-linux.png` | `202ba76fcf5a7e9803f9e23e71eb9f84cc161db5521ff3c32f954da50d35365e` |
| `p8-04-mbom-partial-zh-1920x1080-150-linux.png` | `5c2f34bd06af6abe2c5e3b2911203b3d99a866ac087a8772cbbf073650e6086c` |
| `p8-04-mbom-authoritative-zh-TW-1920x1080-125-linux.png` | `db8070026d683516a1cf661ca4f3a6d8de370325803a7254883187781718d506` |

The three baselines pass exact zero-diff Linux verification. They show
synthetic no-formal truth, mixed authoritative/failed partial truth and two
current authoritative formal BOM identities respectively. In the `zh` 150%
case, the narrow inspector stacks Impact Review vertically without truncating
the primary action, and the horizontally governed table position exposes the
complete per-assembly outcome phrase rather than an icon-only fragment.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| Frappe MBOM read repository, BFF handler and OpenAPI | exact Phase 5 list containment, strict request/node/attempt/result/current-head integrity, IDOR/permission and no-write repository/API/contract tests |
| MBOM frontend data source | exact fixed routes/query, private trace/request contract, CSRF/idempotent command, detached evidence, aggregate mismatch, redacted no-view and no-formal synthetic validation tests |
| EBOM workspace composition and styles | complete state matrix, one primary action, Impact Review, no retry/reconcile/submit, keyboard/focus, non-color and industrial density checks |
| translations and generated catalog | Frappe CSV parsing, literal extraction, direct `zh`/`zh-TW` coverage, terminology and mixed-language audit |
| P8-04 browser fixture/E2E and three Linux images | trilingual state, zero target access, exact command headers/body, submitted guard, axe/overflow/single-primary/style and exact visual comparison |
| controller and checkpoint evidence | checkpoint 3 exact SHA/CI/jobs/artifact digests, checkpoint 4-only authority and retained production/Sandbox/P8-07/P8-05..09 holds |

## Pre-commit Level 1 evidence

- MBOM repository/API/domain/contract/config/metadata/security/adapter/worker/runtime:
  `88/88`; complete P8-03 Item publish regression: `146/146`; complete affected
  Phase 5 regression: `363/363`.
- Frontend MBOM data-source and workspace focus: `64/64`; complete frontend unit
  suite: `1,046/1,046`; browser behavior for `en`, `zh` and `zh-TW`: `6/6`.
- The three governed Linux visual cases pass exact zero-diff comparison after
  axe, overflow, single-primary, industrial-style and mixed-language checks.
  Their SHA256 values are the fixed values recorded above; no Darwin image is
  checkpoint evidence.
- TypeScript typecheck, ESLint, Prettier, Stylelint, frontend boundary/UI
  audits, generated artifact check and Frappe i18n audit pass. The i18n audit
  covers `8,183` literal English sources with `100%` direct `zh`/`zh-TW`
  coverage.
- Current-task and V1.2 reconciliation verifiers, controller/foundation tests
  (`47/47`), changed Python compilation and `git diff --check` pass. No
  production ERPNext/JCE endpoint, credential or request was used.

## Rollback

Remove the MBOM inspector/data source and disable its request action while
retaining every Phase 5 release, MBOM request, node, idempotency row, Outbox
event, attempt, aggregate/node result, uncertainty, observation, current
mapping head and audit. The read projection and UI may be rolled back without
target compensation. Never delete or rewrite observed truth, blindly
redispatch a crossed boundary, change a formal BOM identity, submit/overwrite a
BOM or contact production ERPNext/JCE.

This checkpoint is not P8-04 Level 2 or Level 3. Exact-SHA ordinary CI must
pass before final Level 3 becomes the only active scope.
