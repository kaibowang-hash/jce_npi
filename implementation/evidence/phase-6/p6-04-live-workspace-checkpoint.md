# P6-04 Live Manufacturing Workspace Checkpoint

Recorded: `2026-08-08T15:26:12Z`

Status:
`PASS — LEVEL 1 LIVE WORKSPACE, I18N, ACCESSIBILITY AND VISUAL EVIDENCE`

Requirements:
`FR-TL-005`, `FR-TL-006`, `FR-TL-007`, `FR-TL-008`

Exact stable checkpoint:
`039b7f19d5614352dd7bace45bc297cb8f3128d6`

Primary product checkpoint:
`9346f1baad56e149f923a5478ea2c3c8184b5bf7`

## Delivered boundary

- Added a strict manufacturing data source for exactly the four frozen P6-04
  Project-first routes. Success responses are parsed into the closed plan,
  observation, release-capability and ERP-projection unions before protected
  data reaches the page.
- Added a dense selected-Tooling-Master manufacturing workspace with separate
  plan identity/history, sourcing and responsibility, milestone/observation,
  exact evidence, design-release, manufacturing-authorization and ERPNext
  procurement/actual-cost sections.
- Exposed plan and observation commands only when the server returns the exact
  capability. CSRF, actor-bound request identity, predecessor/hash
  preconditions, explicit processing, validation, conflict and retry behavior
  remain in the strict transport boundary.
- Rendered the formal Supplier, PO, receipt, invoice and actual-cost projection
  read-only. The production reader remains absent, so the live product shows
  the exact ERPNext-unavailable state and offers no edit, dispatch, retry or
  optimistic success action.
- Kept design-document release evidence distinct from Tooling manufacturing
  authorization. `DR-REC-010` still makes manufacturing authorization
  unavailable; the workspace does not add a release, G3, funding, PO-ready or
  start-manufacturing command.
- Labelled supplier-responsible progress as internally reported. No supplier
  identity, portal, login, upload, signature or supplier-submitted claim was
  introduced.
- Added direct literal English source coverage and complete `zh`/`zh-TW`
  translations, keyboard/accessibility assertions, normal and non-normal
  component cases, five non-visual browser cases and three fixed-Linux visual
  cases.

## Failure and repair history

The first exact product run `31262228727` at `9346f1b` did not pass and was
not represented as a checkpoint:

- all `752` frontend unit tests passed, but statement coverage was `79.59%`
  against the unchanged `80%` threshold; and
- the visual job reported `29` expected baseline differences: `26` existing
  Tooling/P0 screenshots changed because the live Tooling surface and catalog
  fingerprint legitimately changed, and the three new P6-04 Linux baselines
  did not yet exist.

Coverage repair `a88f717` added only missing success, read-only, unavailable,
evidence and retry assertions. It did not lower a threshold or exclude code.
Candidate run `31262944445` then passed all `756` unit tests and repository
verification, while visual remained red solely to produce reviewed Linux
candidates.

The first small artifact path omitted the Playwright spec-derived P6-04 result
directory. Behavior-neutral CI checkpoint `30dc020` corrected only that
temporary artifact path. Candidate run `31263363616` passed repository job
`93117479077`; visual job `93117479098` failed only the same expected baseline
set. Artifact `9023448917`, digest
`sha256:6e34b7740636819e7ae50d8fd8df18e351da01a4b42302db0aad098bd34aa885`,
contained exactly `29` actual and `29` diff images.

All three new English, Simplified Chinese and Traditional Chinese manufacturing
screens and representative inherited Tooling/P0 screens were inspected at
original resolution. The accepted baselines preserve the industrial App Shell,
square dense sections, one primary action, explicit text-plus-shape states,
read-only ERP boundary and language purity. The `29` reviewed candidates were
copied exactly; no tolerance, assertion, test, language or governed case was
removed. Stable checkpoint `039b7f1` also removed the temporary candidate
artifact step.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `frontend/src/api/tooling-manufacturing-contract.ts` | strict route, response-union, command-envelope, invalid-success and safe-error tests in `tooling-manufacturing-contract.test.ts` |
| `frontend/src/pages/tooling-manufacturing-workspace.tsx` and live Tooling composition | plan/observation commands, exact capability separation, normal/empty/loading/no-permission/read-only/unavailable/validation/conflict/processing/retry and accessibility cases in `tooling-manufacturing-workspace.test.tsx` |
| catalogs and industrial CSS | complete i18n audit, mixed-language checks, component browser assertions and the three direct P6-04 visuals |
| shared Tooling/P0 screenshots | artifact-proved Linux actual/diff review and final complete zero-tolerance `82/82` governed matrix |
| CI visual evidence paths | workflow verification plus final successful artifact upload; the temporary failed-candidate path was removed |

## Exact-SHA ordinary CI

Ordinary CI `31263974510` passed exact stable checkpoint `039b7f1`:

- repository job `93119021722`: PASS — `1,208` tracked Python tests, `756`
  frontend unit tests, `326` non-visual E2E, `4,641` literal English sources at
  `100%` direct `zh`/`zh-TW`, statement coverage `80.03%`, zero dependency
  vulnerabilities and both current/history secret lanes;
- visual job `93119021805`: PASS — `82/82` fixed-Linux governed cases,
  including the three direct P6-04 screens;
- controlled runtime job `93119022181`: correctly skipped because checkpoint
  4 was not active at this SHA;
- visual artifact `9023617316`, digest
  `sha256:1e47a7454bff0f3566ade380c06ec898dcf347c3c0fe3a57b2a6b75e5084975f`;
  and
- Gitleaks artifact `9023685070`, digest
  `sha256:cf4c19c0074eb36814d1c8b88c43d001bfd5ef1943a14727aa7b4d4c451dbc42`.

## Review, rollback and next checkpoint

No deterministic prototype value, formal Supplier row, ERP endpoint,
credential, adapter, write, successful target result, supplier action or
production lifecycle policy entered the live route. Rollback disables only
`npi_p6_04_routes_disabled` and removes the live composition while preserving
every retained immutable plan, observation, evidence, audit and receipt. It
does not rewrite P6-01 through P6-03 history, controlled Document lifecycle or
any ERPNext object.

Checkpoint 3 is PASS. P6-04 remains in progress. Autopilot next implements
only checkpoint 4: the cumulative disposable-Site verifier and controlled
workflow for immutable plan successors, milestone dependencies and
observations, exact released/unreleased evidence, explicit ERP unavailability,
replay/conflict/rollback/IDOR and independent P6-04 route disable/recovery,
followed by complete ordinary CI and the P6-04 Level 2 Task Gate.
