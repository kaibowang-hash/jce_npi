# P5-05 Repository, Permission, Idempotency, Audit, and BFF Checkpoint

Recorded: `2026-08-06T11:44:35Z`

Status:
`PASS — REPOSITORY/API CHECKPOINT AND COMPLETE ORDINARY CI`

Requirement: `FR-DS-013`

Starting checkpoint:
`a76f9c0cac313dabb80d0b31846345b5593c8d35`

Product checkpoint:
`0e3b13d87e4106be7a748db920f57ab43fda2d37`

Evidence repair checkpoint:
`f3018eb94a54fa63cd87e87fb501835510765145`

## Delivered boundary

- Added the Project-authorized Frappe repository and operation-specific
  list/create/detail BFF routes for one Mock
  `publish_released_ebom_item_mbom` request.
- Create authorization is deliberately independent from EBOM release
  authority: the exact published publish-request policy and actor binding are
  proved before the protected released revision is resolved.
- The command then proves the exact EBOM root/revision, released lifecycle,
  release event and immutable policy evidence. Optimistic root/lifecycle
  versions are required; no mutable-latest selector is accepted.
- Actor, tenant, Project, operation, idempotency key and canonical command
  payload bind one receipt. An exact sealed replay returns the immutable
  response; a changed reason or any changed body input fails closed with a
  stable conflict.
- The atomic order is receipt -> request -> nodes -> mapping observations ->
  node results -> audit -> response -> one-way receipt seal. Any non-2xx path
  rolls back the transaction.
- Phase 5 remains Mock-only. Persistence creates no Outbox work, performs no
  network dispatch, returns no formal Item/MBOM identifier and cannot report
  `succeeded`.
- Added an independent literal-true P5-05 route-disable/recovery boundary. It
  does not disable or weaken P5-01 through P5-04.
- All new user-visible messages remain literal English sources with direct
  Simplified and Traditional Chinese translations. The generated catalog has
  `3,685` directly covered sources.

The implementation also corrected two foundation-only internal consistency
defects proved by the repository tests: the command receipt hash is now
distinct from the frozen request payload hash, and the node-result hash uses
the canonical public result rather than persistence-only parent fields. It
also accepts exact fixed-scale released EBOM quantities such as `1.000`.
These changes do not alter the public contract, Schema, ownership, authority,
transaction order, audit content or PASS criteria.

## Requirement -> code -> test -> evidence

| Requirement | Code boundary | Direct proof |
|---|---|---|
| `FR-DS-013` exact released input and separate requester authority | `npi_integration.publish_request.frappe_repository`; `publish_request_api` | authorization-before-resolution, exact policy/actor/release/version and tenant/Project isolation tests |
| `FR-DS-013` safe command and replay truth | actor-bound receipt plus atomic persistence/seal | exact replay, changed-payload conflict, rollback, restart/replay and immutable response tests |
| `FR-DS-013` Mock no-fake-success | domain/repository result projection and operation-specific BFF | no Outbox/network/formal target IDs/`succeeded`; list/create/detail and route recovery tests |

## Changed-files -> affected tests

| Changed boundary | Verification | Result |
|---|---|---|
| repository, policy/release resolution, transaction and replay | `tests.test_phase5_publish_request_repository` | PASS |
| API, CSRF, auth-before-body, BFF and route recovery | `tests.test_phase5_publish_request_api` | PASS |
| domain hash/state/fixed-scale compatibility | complete publish-request domain group | PASS |
| affected publish-request repository/API group | focused final rerun | `11/11` PASS |
| affected P5-04/P5-05 backend group | repository/API/domain/contract/security modules | `48/48` PASS |
| complete tracked Python regression | `python3 -m unittest discover -s tests` | `997/997` PASS |
| complete frontend regression and build | TypeScript, lint, i18n, unit, coverage and Vite bundle | `690/690` PASS; build PASS |
| i18n and generated catalog | literal-source audit and direct catalogs | `3,685`; direct `100%` zh/zh-TW PASS |
| governance and integrity | reconciliation, prototype approval, P0 visual inventory, JSON/Schema and `git diff --check` | PASS |

The local aggregate frontend verifier encountered only the pre-existing
user-owned untracked file
`frontend/public/images/npi-one-project-management-sketch.png`; the clean
tracked CI checkout excludes it. No user-owned local file was removed,
modified or staged.

## Exact-SHA CI isolation and Hard Blocker repair

Ordinary CI `31096833679` ran on exact product SHA `0e3b13d`:

- repository job `92600762979` passed complete repository verification,
  non-visual browser tests, current-tree Gitleaks and complete branch-history
  secret scan;
- controlled runtime `92600763678` correctly skipped for the ordinary pull
  request event; and
- visual job `92600763013` passed `44/62` and failed only the exact eighteen
  durable P0 normal 1440x900 English/Simplified-Chinese/Traditional-Chinese
  cases.

Failure artifact `8965851155`, digest
`sha256:376df330173e04037cb267a06c359f8e8965f1e949b7bda7c13b4086fc8cb1ba`,
provided all eighteen Linux actuals. Original RGB pixel comparison proves:

- all `18/18` canvases are exactly `1440x900`;
- every difference box is either `(496, 882, 614, 892)` or
  `(559, 882, 677, 892)`;
- each image changes only `694..696` pixels; and
- the complete product workspace above `y=879` has exactly zero changed
  pixels.

The unique root is therefore the deterministic bottom-status-bar catalog
fingerprint changing after the two approved translated sources were added,
not a product workspace, layout, language or behavior regression. The repair
copies only the eighteen reviewed CI actuals over their corresponding tracked
fixed-Linux baselines. Every source/target pair matches byte-for-byte. No
test, threshold, matrix, viewport, scale, language, fixture, product code or
PASS criterion changes.

Repair SHA `f3018eb94a54fa63cd87e87fb501835510765145` then passed complete
unchanged ordinary CI `31097900948`:

- repository `92604192980` passed in `7m44s`, including complete `verify.sh`,
  non-visual E2E and both secret lanes;
- visual `92604192993` passed the complete unchanged governed matrix in
  `2m30s`;
- passing visual artifact `8966265204`, size `5,760,772` bytes, has digest
  `sha256:cdb7c178c2ce75cc2ee39e3289e3e3f9b9cfdd2f3da001471585bc735249472a`;
  and
- Gitleaks artifact `8966407608`, size `6,760` bytes, has digest
  `sha256:67e119b59f974100b1362cecf44e86282f228aa5981a3a867da6c2691940bb00`.

This exact-SHA PASS resolves the visual Hard Blocker and closes P5-05
checkpoint 2. It does not claim the frontend workspace, controlled-Site
runtime, P5-05 Level 2 or the Phase 5 Level 3 Gate.

## Security, ownership, rollback, and next action

- Project authorization precedes protected object resolution; create also
  requires internal NPI API role, CSRF and the separately published exact
  requester policy binding. Browser identity is never trusted.
- NPI One owns the request and immutable evidence history only. ERPNext still
  owns formal Item/MBOM identifiers and manufacturing truth; no target system
  is contacted.
- No raw SQL, `ignore_permissions`, core patch, cross-database access, manual
  commit, secret, exception leakage, permission widening or production
  dependency was introduced.
- Before retained request history, revert the product/evidence checkpoints in
  a disposable environment. After history exists, disable only the P5-05
  route, preserve request/node/mapping/result/audit/receipt history and ship a
  reviewed forward fix. Never delete history or contact ERPNext as rollback.

The next and only active checkpoint is the EBOM publish-request workspace:
closed data/view contracts, dense industrial list/detail truth, one guarded
Mock create action, complete error/partial/unavailable states, direct
English/zh/zh-TW coverage, accessibility, browser and exact visual evidence.
Controlled-Site runtime and Phase 5 release gates remain inactive until that
frontend checkpoint passes complete ordinary CI.
