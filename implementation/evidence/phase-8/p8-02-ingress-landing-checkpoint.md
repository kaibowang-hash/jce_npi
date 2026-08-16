# P8-02 Checkpoint 2 — Signed Ingress and Durable Landing

Recorded: `2026-08-16`

Decision: `PASS — CHECKPOINT 2; CHECKPOINT 3 AUTHORIZED`

Final product checkpoint:
`4c77c4472a0ea07bc14a2073f0b6c7d3b006b870`

Ordinary pull-request CI: `31932869203`

## Scope delivered

- Added only the fixed
  `POST /api/npi/v1/integration/erpnext/project-source-events` BFF mapping.
  Wrong methods, trailing paths and the generic Frappe method path cannot claim
  the operation; no caller-selected route, tenant or authority is accepted.
- Added a raw request adapter with an early `262144`-byte content-length bound,
  exact JSON media/identity-encoding checks and server-owned TLS truth.
  `X-Forwarded-Proto` is not authority. The server resolves the actual Site
  tenant, and no configured resolver means a closed `503` response.
- Preserved the checkpoint-1 authentication order: canonical signature headers,
  enabled non-production profile, key validity, opaque injected secret and raw
  HMAC verification all pass before the closed business-event parser runs.
  Missing/invalid signature facts stay one generic `401`; only authenticated
  contract failures return `422`.
- Added an atomic Frappe landing repository. One transaction freezes the Inbox
  receipt/raw body/hashes/policy, serializes the exact source stream, retains
  source-version disposition and appends its structural audit. It creates no
  Project, Gate, Work Item, target request or network effect.
- Exact event replays return the original receipt without a second row or job.
  Event-ID hash reuse and equal-version payload conflict return closed `409`
  truth without overwriting the first event; lower/equal events are retained as
  superseded and higher events after Project binding remain received-only.
- The handler commits the landing transaction before staging `202` and calls
  the injected enqueue boundary only after that commit. Commit ambiguity never
  acknowledges or enqueues. One unique-key race is rolled back and reclassified
  against the winner; enqueue failure leaves a durable pending receipt for the
  checkpoint-3 recovery worker.
- Authentication, transport and unexpected failures roll back partial writes,
  append only bounded code/time/size/body-hash/key-ID-hash audit evidence and
  return stable `401/409/413/415/422/503/500` problems. Response, audit and safe
  diagnostics contain no raw body, signature, Authorization, cookie, secret,
  traceback, Site path or database detail.
- Added direct Simplified and Traditional Chinese problem-title translations
  and regenerated the Frappe-backed React catalog. There is no SPA surface or
  governed visual change. No profile, secret, worker implementation, scheduler,
  Project row or production/external endpoint is installed.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `inbound_project/ingress.py` | exact route/media/encoding/body/TLS bounds, profile/key/secret resolution and authentication-before-business-parse tests |
| `inbound_project/frappe_repository.py` | first landing, exact replay, event/source conflict, reorder, source-head lock, failure-audit and no-business-effect tests |
| `inbound_project_api.py` | closed response matrix, rollback, commit-before-ack, enqueue ordering/failure recovery, unique-race retry, redaction and default-disable tests |
| `npi_core/bff.py` | exact POST-only mapping plus trailing/wrong/generic/OPTIONS closure tests |
| both Frappe translation CSVs and generated catalog | generation check, direct `zh`/`zh-TW` symmetry, 100% coverage and mixed-language audit |
| focused Phase 8 tests | checkpoint-1 contract/metadata regression plus checkpoint-2 adapter/repository/API boundary and no Project/Gate/Work Item/network assertions |

## Local Level 1 and task evidence

- Complete affected P8-02 checkpoint-1/2 suite: `38/38 PASS`.
- Full local repository Task Gate: `2,013/2,013 PASS`; six pre-existing
  untracked local-prerequisite tests explain the difference from the clean CI
  count. Development-container, prototype approval, P0 visual governance and
  V1.2 reconciliation verification also pass.
- Exact Node `24.18.0`/npm `11.16.0` generation check, i18n audit, type check
  and focused `23/23` i18n tests pass. The audit reports `7,713` literal
  English sources with `100%` direct `zh`/`zh-TW` coverage.
- Task Diff Review, current-task verification, `git diff --check` and local
  one-commit Gitleaks pass. The exact product commit scans with no leak.
- Repository and test scans confirm no Project/Gate/Work Item/target row,
  outbound client, endpoint, production value, default profile, raw secret or
  active worker implementation was added.

## Exact-SHA ordinary CI evidence

- Repository job `95130229892`: PASS; `2,007` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95130229934`: PASS; `60/60` files, `933/933` unit tests,
  `426/426` E2E, generation/type/lint/build/audit, `7,713` complete direct
  trilingual sources, zero vulnerabilities and coverage `80.36%` statements,
  `80.20%` branches, `83.00%` functions and `82.99%` lines.
- Secret job `95130229918`: PASS; `24` first-parent task commits and `515`
  complete branch commits contain no leak. Artifact `9259797335`, digest
  `sha256:be8eb21923d1e7588e20f43b926a66a7838b6ad66731ad0641c587e215655a35`.
- Visual job `95130229907`: PASS; unchanged `119/119` fixed-Linux matrix.
  Artifact `9259841389`, digest
  `sha256:6f99414ab8f0472e3413dd103c7624b367d83136a4563d676da15642d65a7b86`.
- Controlled preflight and cumulative runtime skip as expected at this
  intermediate checkpoint. Checkpoint 3 owns the worker and cumulative
  disposable-Site runtime before the final Level 3 Gate.

## Review and rollback

The Task Diff Review found no JSON trust before the operation's raw-HMAC
boundary, caller-selected TLS/tenant/profile/policy, decoded-body signing,
signature/secret persistence, generic method authority, uncommitted `202`,
pre-commit enqueue, swallowed commit failure, Inbox overwrite, Project business
work, external request or optimistic target success. Route recovery is the
default: without the exact injected non-production profile and secret resolver,
the endpoint remains unavailable.

Rollback disables only this fixed ingress/enqueue seam and retains every Inbox
body/hash, source head/conflict and audit for reviewed forward repair. It does
not delete, rewrite, rebind, redispatch or contact production ERPNext/JCE.

This is checkpoint 2 PASS. It is not P8-02 completion or Phase 8 Level 3.
