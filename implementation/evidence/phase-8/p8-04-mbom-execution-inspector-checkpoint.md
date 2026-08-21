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
| `p8-04-mbom-synthetic-en-1366x768-125-linux.png` | `c8e2801b96538eaf40b5011577ed0e9158ce0c53a586c9a8a6640898035e005e` |
| `p8-04-mbom-partial-zh-1920x1080-150-linux.png` | `2a73fbb89586c83553b8955454f294eaff85445131605fc4b7c8c89bc35efa4a` |
| `p8-04-mbom-authoritative-zh-TW-1920x1080-125-linux.png` | `1819e3878882e2dbf26d1c83e8a6aee9748016dd65d56f1537a0cc6e85a02ee2` |

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

## Ordinary CI legacy-fixture remediation

- Candidate `a62d5ebaf28ffa4a8fd9482dadce4870e4669e77` reached ordinary CI
  `32514627234`. Repository `96873370223` and secret `96873370244` passed;
  frontend `96873370008` passed the full frontend verifier before `23` E2E
  failures, while visual `96873370234` reported `116` pass and `7` failures.
- The `30` failures are derived from one fixture-only root. The existing strict
  P5-05 and P8-03 route fixtures rejected the newly composed fixed MBOM list
  GET before those legacy pages could reach their assertions. No product API,
  UI, permission, transaction, response or visual-baseline defect was shown.
- The remediation admits only `GET` on the exact Project MBOM collection with
  the sole exact `phase5PublishRequestGlobalId` query. It reuses the validated
  MBOM fixture shape in a default-disabled, empty state with no formal IDs;
  every other request remains an unhandled-request failure. The response-
  neutral fixture remediation consumes no product repair round.
- Final Level 3 remains closed until a remediated exact-SHA ordinary CI passes.

The frozen checkpoint deliberately keeps the new MBOM inspector in the
existing released-EBOM workspace and reserves its visible-text request action
as the single primary action. Consequently, the following seven existing
fixed-Linux baselines receive an approved semantic migration; no Darwin image,
product behavior or visual threshold changes:

| Existing governed case | SHA256 |
|---|---|
| `p5-05-publish-request-en-1366x768-100-linux.png` | `1c2a11edbd7a7d137fe29376b873cf7dc1478299cc76ed12f740434ecbf92ee3` |
| `p5-05-publish-request-zh-1440x900-125-linux.png` | `fb28b7e2468ce37ff08c471145bbfb21ba4b4cea2bfe1b5dd289348cf9bd93b7` |
| `p5-05-publish-request-zh-TW-1920x1080-150-linux.png` | `36cf14ad797bffcb550be429e6321b63cb2bbc2887bd3d0626703ff41596eaf0` |
| `p8-03-item-synthetic-en-1366x768-100-linux.png` | `c7b1e71c5c8f0147b0f34424a7e93b713f6b175fadb0a54a12ffc65ff3696a41` |
| `p8-03-item-uncertain-zh-1440x900-125-linux.png` | `8b237ec7b055467d33423228204c641a3a732d09c30a6a6b6d91dad26a300f14` |
| `p8-03-item-authoritative-zh-TW-1920x1080-150-linux.png` | `f6b0f629c7c9de215ea5d3fce250588221ccf29ea5c9ac0481364d8cbe913faf` |
| `p8-03-item-inactive-en-1366x768-100-linux.png` | `024b6d283919d7b33a3722ccf8b9284193dfb300335abc94290a55ae5866d88f` |

Manual review confirms the flat, square, neutral composition; retained EBOM
and Item context; secondary legacy actions; visible disabled MBOM reason; no
MBOM formal identity in the empty fixture; direct `en`/`zh`/`zh-TW` text with
no unapproved mixing; and usable 125%/150% layouts.

Canonical visual evidence is now generated only in the ordinary workflow's
exact Linux/amd64 bookworm, Node `24.18.0`, Playwright `1.61.1` environment.
All three P8-04 baselines are normalized to that canonical renderer after the
visual-only harness applies one deterministic final scroll anchor. Two
consecutive focused `10/10` no-update runs prove zero position drift. The
workflow governs all three P8-04 images, increasing the cumulative visual
matrix from `123` to `126`, and publishes them in the visual artifact.

The remediated canonical Level 1 evidence passes `29/29` affected nonvisual
browser cases and `126/126` governed visual cases. The complete frontend
suite passes `1,046/1,046` unit tests with coverage, production build, brand
audit and both dependency audits; source localization remains `8,183` direct
English literals at `100%` `zh`/`zh-TW` coverage. All `317` runtime-verifier
tests, the focused controller/reconciliation set, current-task verification,
JSON/YAML parsing, changed Python compilation and `git diff --check` pass.

The controlled runtime already executes the MBOM verifier's default-disabled
and network-free fresh Synthetic stages after the retained P8-03 source. Its
job/step/result attestation now records current
`scope=p5-01-through-p8-04` and
`predecessor_scope=p5-01-through-p8-03`; the prior P8-03 scope remains an
explicit predecessor contract rather than being deleted.

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
