# P8-06 Validation — Formal Quality Linkage Foundation

Date: `2026-08-28`

Requirements: `INT-007`, `FR-TR-006`, `FR-NP-006`

Verdict: **PASS — BOUNDED TECHNICAL PORTIONS ONLY**

Exact product SHA: `547421a059911df6aeb90bbbf06e837f77a3e5e0`

## Delivered boundary

P8-06 delivers the NPI-owned formal-quality-link foundation over exact,
immutable P8-01 observations. It provides Project-first list/detail/link,
current/drifted/unavailable reconciliation, actor-bound write capability,
immutable revision/head/idempotency/audit history, a read-only Trial/readiness
inspector and one server-capability-gated NPI link action. The runtime proof is
network-free and exercises exact link, replay, conflict, stale and unavailable
truth without contacting an ERP target.

P8-01 remains the sole owner of ERP observation/head ordering and freshness.
P8-06 cannot edit an ERP observation, invent formal quality pass, approval or
Gate/readiness truth, or substitute Mock/Synthetic success for target truth.

## Exact-SHA gates

- Ordinary CI `33131533806`: frontend `98721945574`, repository
  `98721945724`, secret `98721945740`, visual `98721945774` — PASS.
- Final Level 3 `33132296565`: frontend `98724376602`, secret
  `98724376742`, visual `98724376760`, repository `98724376765`, controlled
  preflight `98726515848`, cumulative disposable runtime `98726544430` — PASS.
- Governed visual matrix: `132/132` on pinned native Linux x64 — PASS.
- All 17 bounded runtime diagnostic activations are false in the final
  product SHA; dormant/no-trace/no-cursor/no-reader tests pass.

## Artifacts

- Runtime artifact `9671109131`:
  `sha256:9f20f7e4d8706e6d257460676cfc9edf06c4723d7d8f20a5f8b658bfb521962a`.
- Visual artifact `9670779223`:
  `sha256:1a92751e7f4e917d2b13c1e5eb2e79017ab142f657a86b4d5e3895ae672471c9`.
- Gitleaks artifact `9670710440`:
  `sha256:40128ee7ce2d4ad7ac467780e6d4dd01b194764e19aaa195c21510ef1bacd6ad`.

## Acceptance ledger

- Domain, metadata and ownership: PASS. Additive support records preserve
  zero-row migration behavior and ERP-owned formal identity/lifecycle/result.
- API and schema: PASS. Existing BFF routes, OpenAPI components and exact
  immutable source/head/version locks remain aligned; no generic writer was
  added.
- Permission and security: PASS. Server-side Project/actor/role/source
  capability checks, fail-closed helpers, immutable audit and direct-SQL/
  secret scans pass. Administrator/Guest and out-of-scope authority remain
  rejected.
- Idempotency, replay and conflict: PASS. Same command replays the sealed
  response, competing source/head versions conflict, and uncertain target
  truth is never converted to success or automatically redispatched.
- UI, accessibility and i18n: PASS. English, Simplified Chinese and Traditional
  Chinese loading, empty, permission, read-only, current, drifted, unavailable,
  conflict and error states pass component, E2E and governed visual evidence.
- Integration faults and cleanup: PASS. Disposable runtime proves transaction
  rollback, replay, stale/unavailable results, zero target traffic and cleanup.

## Requirement allocation and retained holds

- `INT-007`: only the formal-quality observation/link/currentness technical
  foundation is verified.
- `FR-TR-006`: only the exact formal-quality reference portion used by Trial
  evidence is verified; the whole requirement is not claimed complete.
- `FR-NP-006`: only the exact formal-quality link portion used by controlled
  reporting is verified; the whole requirement is not claimed complete.

Production and authenticated Sandbox Quality Inspection/NCR/CAPA DocType,
method, field, naming, lifecycle, approval and status/result mappings remain
held. Raw ERP codes have no installed pass/Gate/readiness interpretation.
Production adapters, target traffic, P8-07 operational controls, P8-08/P8-09,
and the `FR-CO-003/004` external portals remain outside this completion.

## Rollback and recovery

Disable the P8-06 route and inspector/link-action exposure while retaining
immutable NPI link, revision, head, idempotency and audit history. Do not delete
history, rewrite P8-01 observations, infer target truth or replay across an
uncertain boundary. Forward repair requires a separately authorized exact
checkpoint and exact-SHA ordinary/controlled evidence.

No unresolved P8-06 technical release blocker remains inside this bounded
foundation. All listed external and policy facts remain explicit scoped holds.
