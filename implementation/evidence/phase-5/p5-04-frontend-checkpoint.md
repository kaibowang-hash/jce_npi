# P5-04 Frontend Workspace Checkpoint

Recorded: `2026-08-05T12:47:15Z`

Status:
`PASS — LOCAL LEVEL 1 FRONTEND WORKSPACE; EXACT-SHA CI ROOTS CLASSIFIED; BOUNDED EVIDENCE REPAIR READY`

Task:
`P5-04 — EBOM revision and comparison`

Requirements:

- `FR-DS-011`; and
- `FR-DS-012`.

Starting synchronized checkpoint:
`0ad13b835c622fce9028dadf29d6fe9b2ee755ca` (`0 ahead / 0 behind`)

Pushed frontend candidate:
`85fd03fdc936db03b61985e03caced0e0b68f760` (`0 ahead / 0 behind`)

Reusable predecessor evidence:

- P5-04 Repository/BFF/OpenAPI checkpoint
  `40e7b7036b9f39a8298b6bb44df9749c75337c5e` passed ordinary CI
  `31001529719` and is not reopened;
- controller synchronization checkpoint
  `0ad13b835c622fce9028dadf29d6fe9b2ee755ca` passed ordinary CI
  `31002288210`, repository job `92293780397` and fixed-Linux visual job
  `92293780586`; and
- P5-03 Level 2 and its final unchanged controlled-Site Gate remain sealed
  predecessor evidence.

This is not the P5-04 Level 2 Task Gate. The controlled-Site EBOM proof,
P5-05 and Phase 6 remain inactive until this frontend candidate passes clean
exact-SHA ordinary CI.

## Delivered boundary

- Added one strict Project-scoped EBOM browser data source for list, exact
  detail, first creation, immutable successor creation, submit/review/release
  lifecycle commands and deterministic comparison of two explicit revision
  IDs. Success responses are closed and bounded; Project, EBOM, revision,
  policy, lineage, lifecycle, event, comparison-count and response-header
  truth fail closed.
- Every command sends trusted session CSRF and an actor-bound idempotency key.
  A retryable transport failure reuses the original user-intent key. Request
  bodies are constructed field by field so undeclared caller fields cannot
  leak through structural typing; invalid review decisions or unconfirmed
  release intent are rejected before transport.
- Added the Project `EBOM` workspace with dense structure/revision/line tables,
  a docked exact-revision inspector, append-only lifecycle history, create and
  successor line editors, explicit review/release steps and a typed exact-
  revision comparison table.
- The workspace covers loading, normal, empty, read-only, no-policy,
  source-unavailable, protected/final failure, conflict/retry, processing,
  identical/different comparison and lifecycle capability states without
  optimistic write success.
- Editor rows use a private local key independent of the editable business
  line key, preserving multi-character entry and focus. Dirty navigation
  registers the exact EBOM/revision context, cancel restores focus, and the
  first interactive editor control receives focus.
- Exactly one visual primary action exists in each workspace state. Read-only
  state exposes none; when an editor opens, its submit action replaces the
  toolbar create action as the current primary. Release remains an explicit
  high-risk confirmation.
- Added only literal English source strings and direct Simplified/Traditional
  Chinese Frappe CSV entries. The generated React catalog remains the one
  Frappe-compatible translation chain.
- Added three exact browser visual cases and included P5-04 in the existing
  fixed-Linux governed visual job/artifact inventory. No threshold, viewport,
  language, scale or existing visual case was removed.

No formal ERPNext Item, Item Code, MBOM, routing, inventory, cost, production
execution, cross-database access, production policy, production authority or
optimistic ERP success is introduced. The visible boundary states this
explicitly.

## Review repairs proved during this checkpoint

| Root | Repair and proof |
|---|---|
| Browser command fixture remained read-only | The synthetic CSRF token was 29 characters while the session contract requires 32–128. The fixture now supplies a valid non-secret token; all five non-visual command/read cases pass. Product permission logic was not weakened. |
| New Project tab changed keyboard `End` truth | The retained tab test now expects the actual final `EBOM` tab while preserving Arrow, Home and single-tab-stop assertions. |
| Retry created a second business intent | Idempotency keys are allocated once per user submit and captured by the retry closure. A component regression test proves the first and second transport attempts use the same key. |
| Editable `lineKey` was also the React row key | A private local client key now owns render identity. A complete first-create test proves multi-character line input and exact command payload. |
| Request object spread could forward undeclared fields | Every request is rebuilt from its exact allowed fields. A regression test supplies an undeclared formal-MBOM field and proves it is absent from the serialized request. |
| Review/release relied only on TypeScript literal types | Runtime checks now reject an unknown review decision, `confirmed != true`, or a non-exact confirmation intent before any HTTP call. |
| Multiple or read-only primary actions | Toolbar, empty state and editor action prominence now leave exactly one primary in mutable states and zero in read-only state. |

## Requirement → code → test → evidence

| Requirement | Code boundary | Direct proof |
|---|---|---|
| `FR-DS-011` | `frontend/src/api/ebom-data-source.ts`; `frontend/src/pages/project-ebom-workspace.tsx`; Project/App integration; local industrial styles | exact list/detail/command validators; create/successor/lifecycle command units; dense workspace states; first-create/focus/dirty/read-only/confirmation/idempotency tests; trilingual browser and visuals |
| `FR-DS-012` | exact comparison query and typed difference workspace | two distinct explicit revision IDs, closed response counts, invalid/identical identity rejection, typed quantity before/after UI and browser assertions |

## Changed files → affected tests

| Changed boundary | Affected verification | Local result |
|---|---|---|
| EBOM view models, validators and live HTTP data source | `ebom-data-source.test.ts` plus TypeScript/ESLint | PASS |
| Project EBOM workspace, command/focus/dirty/primary-action behavior | `project-ebom-workspace.test.tsx`; Project page/workspace/shell units | PASS |
| Project tab registration and App injection | `project-workspace.test.tsx`; `project-page.test.tsx`; `pages-and-shell.test.tsx`; full unit regression | PASS |
| translations and generated catalog | generation check; full lint/i18n | `3,508` literal English sources; direct `100%` `zh`/`zh-TW` PASS |
| browser behavior | new P5-04 live suite; complete non-visual browser suite | P5-04 `5/5`; complete suite `293/293` PASS before the final isolated data-source/component repairs; final affected P5-04 suite `8/8` PASS |
| visual surface and workflow inventory | exact Darwin P5-04 matrix; fixed-Linux job declaration | local zero-tolerance `3/3` PASS; exact-SHA CI `31006126302` classified `38/62` PASS with 24 reviewed evidence-only baseline deltas |
| complete frontend | full unit, type, lint, generation and Vite production build | `690/690` units and all static/build checks PASS |

The full unit runner emits the retained expected negative-path
`I18nProvider is required` reporter output while all `690/690` assertions
pass. The production bundle retains the existing size warning and completes.
The local display-brand guard is not claimed because user-owned untracked
`frontend/public` assets are intentionally preserved and excluded from this
checkpoint. Clean-run CI `31006126302` supplied the authoritative brand proof
and passed the current-tree secret lane; its complete-history secret lane
isolated only the two reviewed synthetic fixture fingerprints recorded below.

## Exact-SHA CI classification and bounded repair

Ordinary CI `31006126302` ran against exact pushed SHA
`85fd03fdc936db03b61985e03caced0e0b68f760`:

- repository job `92306322154` passed `933/933` tracked Python, `690/690`
  frontend unit, direct `3,508`-source trilingual coverage, production build,
  brand guard, zero-vulnerability audits, complete `293/293` non-visual
  browser and the current-tree no-leak scan;
- that job failed only its final complete PR-history scan after `137` commits
  because `generic-api-key` classified two literal synthetic EBOM business
  keys in commit `85fd03f` as secrets; and
- fixed-Linux visual job `92306322226` passed `38/62` and failed exactly 24
  reviewed images: three new P5-04 images with no predecessor Linux baseline,
  three P5-01 images whose only strong change is the approved additive `EBOM`
  Project tab, and eighteen durable P0 images whose only strong change is the
  generated catalog fingerprint in the bottom status bar.

Visual artifact `8930443639`, digest
`sha256:9c8dc4b9d3354e77ebb0718829ba00d6bbe93b0283cf58e6000d3e752f35da5b`,
was reviewed at original resolution. Its 24 actuals are accepted byte for byte
only for their corresponding Linux baselines. All 24 copied baseline files
match the artifact actuals exactly; no visual threshold, viewport, language,
scale, state or case was changed. The three P5-04 Linux SHA-256 values are:

- English: `28837931db00caea741d01d2377649939c5ba4aa6339c0b51c57966144335b6b`;
- Simplified Chinese: `bfdff2f16fa473458011ff7fea3db471295989f5299313e5b49cf5ccb6376aa6`;
- Traditional Chinese: `d740d4b76db3b660c13738c3f8be9973fc2f4f5de668c51e9e4fda212e381f5f`.

The history-scan repair adds only the two exact immutable fingerprints to the
already strict reviewed allowlist and its fail-closed verifier/test inventory.
Current fixture code now keeps the same visible synthetic values separate from
the `engineeringBomKey` field assignment so a future commit does not recreate
the lexical false positive. Focused workspace tests passed `8/8`; the strict
allowlist verifier tests passed `21/21`; the network-backed verifier passed.
The local wrapper could not run because this macOS environment lacks the
unversioned `python` executable expected by the CI runner; this is an
environment presentation difference, and the unchanged exact-SHA CI remains
mandatory.

## Visual, accessibility and language review

The final unchanged local P5-04 browser/visual run passed `8/8`, including
Axe WCAG A/AA, no document overflow, industrial computed-style checks and
mixed-language scans. Original-resolution images were inspected at:

- English `1366×768@100%`, SHA-256
  `034ce6ed52d2ff86c9e28b9d28d019a4920cdc8af1698eb5afb50197c62f5217`;
- Simplified Chinese `1440×900@125%`, SHA-256
  `d47cc8ad0d01cd08d8093305c4c158ae402206f827ffa8ffb26cd88eb72259e4`;
- Traditional Chinese `1920×1080@150%`, SHA-256
  `2b21b3b44bbcdee8a078f927ff17c2910a37993d7bf2566fbe68227c25126f72`.

The surface is square, flat, high-density and single-accent; uses stable
toolbar/list/revision/line/inspector regions; shows state with text and shape;
contains no decorative card wall, gradient, glass, large-radius treatment or
Desk form. Business descriptions, synthetic identities, email addresses,
hashes and engineering units remain explicitly scoped business-data,
identifier or unit exemptions.

## Permission, security, domain and rollback review

- The UI consumes server capability truth but never grants authority. Writes
  remain protected by authenticated session context, Project scope, CSRF,
  exact policy/snapshot/version inputs and server-side authorization.
- Queries send no CSRF or idempotency header. Commands cannot supply actor,
  tenant, formal Item/MBOM identity or lifecycle result; non-2xx results
  remain visible and traceable.
- NPI One owns only working EBOM revisions and their lifecycle. ERPNext keeps
  formal Item, stock UOM, MBOM, routing and execution ownership.
- No raw SQL, `ignore_permissions`, core patch, production endpoint, secret,
  raw exception text, fake success, TODO/stub/placeholder implementation or
  new dependency was introduced.
- `R-059` remains the scoped production-policy hold. `R-060` remains open
  until clean frontend CI and controlled-Site/Level 2 proof. No new Decision
  Request, ADR or Hard Blocker is required.
- Before retained P5-04 history exists, this frontend slice can be reverted.
  After retained history exists, disable only the existing P5-04 route switch,
  preserve immutable history and deploy a reviewed forward repair.

## First incomplete action

Create and push one bounded CI-evidence repair checkpoint containing only the
24 reviewed Linux baselines, two exact historical synthetic fingerprints,
their strict verifier/test inventory, the lexical fixture hardening and
synchronized evidence/controller files. Then require complete unchanged
ordinary CI on that exact SHA. Do not activate controlled runtime, P5-05 or
Phase 6 before that clean run passes.
