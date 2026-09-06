# P5-03 Domain and Metadata Foundation Checkpoint

Recorded: `2026-07-31T20:58:50Z`

Status:
`PASS — LEVEL 1 DOMAIN/METADATA FOUNDATION`

Requirement:
`FR-DS-006`

## Delivered boundary

- Added an independently testable exact baseline domain with deterministic
  canonical hashes for Project-scoped publish-once policy versions, immutable
  baselines and members, explicit Gate dependencies and append-only successor
  impact events.
- Added seven additive guarded DocTypes: baseline policy root/version,
  baseline/member, actor-bound command receipt, Gate dependency and impact
  event.
- Baseline members freeze the exact Document Revision identity/hash,
  lifecycle version, release event/hash and complete P5-02 release/File
  evidence. A later revision cannot replace a retained member.
- Baseline and member history requires the private baseline-command write
  scope. Dependency and impact history requires the separate private system
  scope. Every retained record denies rename, update and delete; normal API
  users have no generic read or mutation path.
- The command receipt binds tenant, Project, actor, operation, hashed
  idempotency key and payload and permits only one unsealed-to-sealed response
  transition.
- A Gate dependency can reference only an exact member of an immutable
  baseline and its exact `release_baseline` evidence reference. An impact
  event can reference only that dependency and an exact direct successor
  revision.
- Updated ownership to separate baseline administration, immutable versioned
  policy, baseline command, rule engine, Gate evidence and existing Gate
  Review resolution.

No production policy, G2/G5/G6/ECN content map, dependency matrix, retention,
replacement, external provider or ERPNext behavior was installed or inferred.
Repository/API/Gate-evidence integration remains inactive until the next
checkpoint.

## Changed-files to affected-tests

| Boundary | Evidence |
|---|---|
| baseline domain and exact hashes | `tests.test_phase5_document_baseline_domain` — `8/8` PASS |
| seven DocTypes, permissions, flags, enums and ownership | `tests.test_phase5_document_baseline_metadata` — `5/5` PASS |
| adjacent P5-01/P5-02 metadata | `tests.test_phase5_document_metadata` plus `tests.test_phase5_document_release_metadata` — `15/15` PASS |
| Python/JSON/static whitespace | changed Python compilation, all seven DocType JSON parses and `git diff --check` PASS |

Combined focused result: `28/28` PASS.

The preceding P5-03 audit/controller checkpoint
`81f12493d01b4112afb59966a845de49230c819d` passed ordinary CI
`30663842514`; both repository and fixed-Linux visual jobs passed. This Level
1 checkpoint does not claim the later P5-03 ordinary CI, controlled-Site Gate
or Level 2 Task Gate.

## Security and invariants review

- No `ignore_permissions`, raw idempotency key, file URL, credential, request
  body, Cookie, traceback or exception text is persisted or exposed.
- No existing Requirement, API, role, Schema, lock, version, audit,
  idempotency, transaction order, Gate Review state or PASS criterion was
  weakened.
- Production baseline authority/content and dependency completeness remain
  fail-closed under `FUTURE_APPROVED_PRODUCT_POLICY` ownership.
- The existing WBS plan baseline is unchanged and is not reused.

## Rollback

Before retained P5-03 history exists, remove the additive foundation and
restore the checkpoint parent. After any P5-03 history exists, preserve it,
disable only the independent future P5-03 routes and use a reviewed forward
fix. P5-01/P5-02 records and ERPNext remain untouched.

## Next stage

Implement only the baseline repository/BFF/OpenAPI slice with authorization
before protected resolution, exact released-input revalidation, actor-bound
replay/conflict behavior, atomic baseline/member/audit/receipt ordering and an
independent fail-closed route switch. Gate attachment, successor impact and UI
remain later bounded P5-03 stages.
