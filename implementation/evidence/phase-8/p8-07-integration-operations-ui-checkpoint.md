# P8-07 Checkpoint 3 — Live Integration Operations Workspace

Status: **LEVEL 1/2 CANDIDATE — AWAITING EXACT-SHA ORDINARY CI**

Date: 2026-08-29

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Checkpoint-2 Gate: `f7cf7c7ea490c10acfc044aaef236945e5118f01` /
ordinary CI `33187660221` (**PASS**)

## Scope delivered

- Replaces only the in-memory `/execution` prototype with the canonical live
  `/projects/{projectId}/integration-operations` workspace; a missing Project
  fails closed before transport.
- Adds one strict data source for Project-first collection, logical-DLQ,
  detail, replay and reconciliation-request routes. Unknown, foreign,
  malformed or internally inconsistent response truth is rejected.
- Presents a dense worklist and docked inspector covering loading, empty,
  permission, read-only, queued, processing, succeeded, retryable,
  failed-final, uncertain, partial, conflict, quarantined, unavailable,
  command-in-flight, command-conflict and error states.
- Shows exactly one operation-specific action when the server capability and
  current state permit it: replay for exact retryable pre-boundary truth or a
  reconciliation request for uncertain/partial truth. Final and observe-only
  states never receive a mutation action.
- Keeps Impact Review local to command confirmation, submits only the frozen
  expected raw state/version, and never turns HTTP acceptance, queued,
  synthetic or operator intent into formal ERPNext success.
- Integrates Project shell navigation, context display and refresh while
  retaining the legacy route only as an explicit Project-context-required
  compatibility boundary.

## Safety, UX and localization evidence

- Collection permissions hide identities and suppress detail calls when view
  authority is absent; permission-safe `404`, read-only and session-unavailable
  states disclose no payload or target body.
- Keyboard row selection, stable focus, translated accessible names/tooltips,
  non-color-only state icons/shapes and a focusable attempts region are
  covered by unit/E2E evidence.
- English, Simplified Chinese and Traditional Chinese use the repository
  translation chain. `DLQ` is rendered as translated logical-failure-queue
  language rather than leaking an unapproved abbreviation.
- The fixed Linux visual matrix contains three source-driven baselines:
  `1366×768 @100%` English, `1440×900 @125%` Simplified Chinese and
  `1920×1080 @150%` Traditional Chinese. Axe, mixed-language, document-overflow
  and industrial square/density/style assertions pass.
- Snapshot SHA-256 values are:
  `d7a2c0e0927fb8975c66cfcc37d635ac9164b96310471c0fdf921e98c7a33935`,
  `0298baf8604dd350f5a2aa72297482d4bdcbc6e5ccbcb3b9cbba5ce2e7a45a01`
  and `75992e96479e5e077a78bf8f3880259421e40f4ef77f0e2b924571da56c2f414`.

## Verification status

The checkpoint-3 Level 1/2 candidate passes:

- `67/67` focused data-source, page, shell and router unit tests;
- the complete frontend suite at `1084/1084`, with `80.24%` statements,
  `80.08%` branches, `82.71%` functions and `82.84%` lines coverage;
- `34/34` P8-07 backend tests, `7/7` focused security tests and `38/38`
  current-task/reconciliation tests plus both independent verification
  scripts;
- `3/3` affected non-visual E2E cases and `3/3` governed trilingual visual
  cases in the pinned Linux browser environment used by CI; and
- translation generation and `100%` direct Simplified/Traditional Chinese
  coverage, type checking, full lint/format/style/boundary/UI checks, build,
  brand and install-script guards, production and full npm audit, Python
  compile, governed shell syntax and `git diff --check`.

The candidate still requires an exact task manifest, commit and exact-SHA
ordinary CI PASS before this checkpoint can activate checkpoint 4.

## Holds

Checkpoint 3 adds no backend route, permission, Schema, worker, adapter,
target call or production profile. Checkpoint 4 disposable runtime/migration
proof and Level 3 remain inactive. Production ERPNext/JCE contact and the
queued fact check remain prohibited/not effective; P8-08, P8-09 and deferred
external portals remain inactive.
