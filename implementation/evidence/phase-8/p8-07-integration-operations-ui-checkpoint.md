# P8-07 Checkpoint 3 — Live Integration Operations Workspace

Status: **CHECKPOINT 3 PASS — EXACT-SHA ORDINARY CI PASS**

Date: 2026-08-29

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Checkpoint-2 Gate: `f7cf7c7ea490c10acfc044aaef236945e5118f01` /
ordinary CI `33187660221` (**PASS**)

## Scope delivered

- Adds the canonical live `/projects/{projectId}/integration-operations`
  workspace while retaining `/execution` as the explicitly in-memory
  prototype. The live workspace has no missing-Project or tenant-wide
  transport fallback.
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
- Integrates Project command-palette navigation plus exact live-page rail
  context and refresh while retaining the legacy prototype route and its
  existing visible navigation/evidence contract. Unrelated live workspaces
  keep the prior disabled rail item, avoiding a global shell-baseline change.

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

- `69/69` focused data-source, live page, prototype page, shell and router unit
  tests;
- the complete frontend suite at `1086/1086`, with `80.19%` statements,
  `80.00%` branches, `82.60%` functions and `82.80%` lines coverage;
- `34/34` P8-07 backend tests, `7/7` focused security tests and `38/38`
  current-task/reconciliation tests plus both independent verification
  scripts;
- complete non-visual E2E at `458/458` and the exact CI-governed Linux visual
  matrix at `135/135`, including all three P8-07 language/viewports; and
- translation generation and `100%` direct Simplified/Traditional Chinese
  coverage, type checking, full lint/format/style/boundary/UI checks, build,
  brand and install-script guards, production and full npm audit, Python
  compile, governed shell syntax and `git diff --check`.

Stable exact SHA `758bb222a1477474af50fc6b84d5d2c56e379adc`
passes ordinary CI `33204451677`: repository `98961818348`, frontend
`98961818460`, secret `98961818358` and governed visual `98961818084` are all
`SUCCESS`; controlled lanes correctly skip. Checkpoint 4 is therefore active
only for the frozen cumulative disposable runtime and final Gate.

### Same-cycle branch-history scan remediation

Initial exact candidate
`a5bc713d3cac8eb82b511a6aa73dc2262aa58dc6` entered ordinary CI
`33197139118`. Repository job `98937051995` passed, and secret-scan job
`98937052033` passed both current-task verification and the standard Gitleaks
action. Its additional full pull-request-history scan then classified one
synthetic test-only reconciliation idempotency value at
`frontend/tests/unit/integration-operations-data-source.test.ts:146` as a
generic API key and exited `2`; the redacted report identified no production
credential or product-path value.

The same-cycle repair constructs that fixed test value from low-risk literal
segments and adds only the exact historical finding fingerprint to
`.gitleaksignore`. It does not change product code, scanner configuration,
rules, history coverage, exit code or threshold. The replacement candidate
must pass a new exact-SHA ordinary CI; evidence from the failed run cannot
activate checkpoint 4.

Replacement SHA `da7e80a4225d984e9129a6816818fdbb0b4366a0` entered
ordinary CI `33197642272`. Full-history secret scan job `98938823857` passed,
closing the original classification. Repository job `98938824087` then
failed at the independent fail-closed verifier because the newly reviewed
fingerprint was not yet mirrored in its exact allowlist. The follow-up adds
that same immutable fingerprint to the verifier and its negative contract
test; it does not broaden the accepted shape or permit any second finding.

### Same-cycle route and selection compatibility remediation

Verifier-repair SHA `aee201fed52726ea490313003c67e3cdd1d803fc`
entered ordinary CI `33198074871`. Repository job `98940316657` and the full
branch-history secret job `98940316917` passed. Visual job `98940316932`
failed because checkpoint 3 had changed the visible Execution navigation and
replaced the existing `/execution` prototype across the durable P0 matrix;
the three new P8-07 Project-scoped visual cases themselves passed. Frontend
job `98940317013` passed `451/458`; six failures were the same legacy
`/execution` contract, while one P8-07 case exposed that selecting the already
selected logical-DLQ row reset loaded detail to `loading` without changing the
effect dependency, leaving its guarded action disabled.

The bounded repair keeps the new Project-scoped route, data source and action
contracts unchanged. It restores the existing in-memory prototype at
`/execution`, preserves its visible navigation and direct translations,
keeps Project-scoped navigation in the command palette plus the live page's
exact current rail item, and isolates the prototype in a separate page
module. The live worklist now treats selecting the already selected row as a
no-op, preserving the loaded exact detail and its server-authorized action.
The unit contract locks this behavior and the E2E command test waits for the
detail-backed capability before acting.

Affected non-visual E2E passes `67/67`. A clean Debian Bookworm x64-compatible
Node `24.18.0`/Chromium run compares, without updating, all `18` durable P0
screens plus all `3` P8-07 screens and passes `21/21`; no visual baseline is
changed. The final same-cycle Level 1/2 run additionally passes focused units
`69/69`, full frontend unit/coverage `1086/1086`, complete non-visual E2E
`458/458`, the exact CI-governed visual matrix `135/135`, and repository
verification `2606/2606`. The required fresh exact-SHA ordinary CI completed at
`758bb222a` / `33204451677`, activating checkpoint 4 without expanding scope.

## Holds

Checkpoint 3 adds no backend route, permission, Schema, worker, adapter,
target call or production profile. Checkpoint 4 disposable runtime/migration
proof and Level 3 are the only active scope. Production ERPNext/JCE contact and
the queued fact check remain prohibited/not effective; P8-08, P8-09 and
deferred external portals remain inactive.
