# P8-07 Validation — Integration Operations, Replay and Reconciliation

Date: `2026-08-30`

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Verdict: **PASS — BOUNDED TECHNICAL PORTIONS ONLY**

Exact product SHA: `edf89e79cd815cbde60e2940ae9d580479336d75`

## Delivered boundary

P8-07 delivers a Project-scoped operations work center over the five fixed
operation kinds `receive_project_submission`, `publish_item`, `publish_mbom`,
`create_tool_asset` and `update_tool_asset`. It derives logical DLQ truth from
the owning immutable request/attempt/result records, permits only
operation-specific actor-authorized replay or reconciliation intent, retains
target-boundary uncertainty and never turns queued, Mock, timeout, partial or
HTTP acceptance into formal ERP success.

The NPI application remains the owner of engineering-process intent,
idempotency, Inbox/Outbox evidence, attempts, operator actions and immutable
reconciliation observations. ERPNext remains owner of formal Item, MBOM,
Asset, quality, manufacturing and commercial identity/lifecycle/result. No
generic DocType writer, cross-database access or production traffic exists.

## Exact-SHA Gates

- Ordinary CI `33277289693`: repository `99166132533`, frontend
  `99166132617`, secret `99166132618` and visual `99166132648` — PASS.
- Final Level 3 `33277905251`: frontend `99167797638`, visual
  `99167797764`, secret `99167797789`, repository `99167797904`, controlled
  preflight `99168971817` and cumulative runtime `99168998544` — PASS.
- The cumulative runtime completed the P5-through-P8-07 chain, result record,
  artifact upload and cleanup on a fixed disposable Site. All bounded runtime
  diagnostic activations were false.

## Artifacts

- Runtime artifact `9722300941`:
  `sha256:a7835b5e2125780d451335ced76da2521a6527a9d01803492ce268aa37cd0ead`.
- Visual artifact `9722125497`:
  `sha256:ecf51b866b37e5f3d92a174b511124242780ecd60464400841788f54e1e7a5d0`.
- Gitleaks artifact `9722075158`:
  `sha256:1bbea6a7c9da231b3fa951084e62221755336f7388db7b4362a30fea89cc0b34`.

## Acceptance ledger

- Operation authority and ownership: PASS. Exact Project, tenant, actor,
  role, operation, source, request, version, idempotency and trace checks are
  server enforced. P8-02 through P8-06 ownership remains unchanged.
- Logical DLQ and history: PASS. DLQ is a derived classification, never a
  second mutable copy. Requests, attempts, results, action receipts,
  reconciliation observations and audit remain append-only or sealed.
- Replay and reconciliation: PASS. Retryable non-uncertain truth reuses the
  exact immutable source and target idempotency key. Final, partial,
  uncertain, quarantined and conflict truth cannot be redispatched. Operator
  intent alone cannot assert target success.
- Permission/security: PASS. Project containment, operation-specific
  capability, no-database-access operator behavior, redaction, CSRF,
  permission-safe not-found and forged/stale/conflicting request rejection
  pass.
- UI/i18n/accessibility: PASS. Direct English, Simplified Chinese and
  Traditional Chinese loading, empty, permission, read-only, retryable,
  uncertain, conflict and error truth pass unit, E2E and governed visual
  evidence without Desk or browser-to-ERP access.
- Runtime/recovery: PASS. Network-free synthetic evidence covers route
  disable/recovery, cross-process replay, immutable reconciliation history,
  migrations twice, redaction, cleanup and zero production target traffic.

## Requirement allocation and retained holds

- `FR-RP-009`: the bounded operation-center, logical-DLQ, replay and
  reconciliation technical foundation is verified. Production/Sandbox target
  facts, support ownership, monitoring and approved operating policy remain
  held.
- `NFR-INT-001`: the bounded idempotency, timeout/uncertainty, retry, replay,
  reconciliation, audit and recovery foundation is verified. Production
  compatibility and deployment evidence remain held.
- `UX-016`: the existing technical foundation now includes the shared
  Project-scoped execution work center; the status is not promoted to real
  production use or business acceptance.

P8-07F production fact reconciliation, authenticated Sandbox/UAT, precise ERP
fields/methods/roles/service scopes, P8-08/P8-09, M9 controlled UAT and every
user-deferred real-project pilot remain outside this technical completion.
No real pilot, real-user adoption or 80-percent usage claim is made.

## Rollback and recovery

Disable P8-07 routes, operator action capabilities, enqueue and UI exposure
while retaining every request, attempt, result, action receipt, reconciliation
observation and audit record. After a target boundary may have been crossed,
use reviewed forward repair and never delete history, blindly redispatch,
rewrite uncertainty to success or compensate a target automatically.

No unresolved P8-07 technical release blocker remains inside this bounded
foundation. P8-07F is a mandatory compatibility-fact Gate before P8-08, not a
retroactive production acceptance claim.
