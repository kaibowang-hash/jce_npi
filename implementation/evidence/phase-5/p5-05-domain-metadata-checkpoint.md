# P5-05 Domain, Contract, and Metadata Checkpoint

Recorded: `2026-08-06T10:46:00Z`

Status:
`IN_PROGRESS — EXACT CATALOG-FINGERPRINT VISUAL REPAIR CANDIDATE`

Requirement: `FR-DS-013`

Starting checkpoint:
`15e41f5e7c1c680bf4d7507aa2517ff08f1c41b2`

Product checkpoint:
`258277cc018a9e8b72cccb921b94e84b3dd0cb59`

## Scope delivered

- Added a pure closed `publish_released_ebom_item_mbom` domain that binds an
  exact released EBOM revision, exact release event and policy evidence,
  actor/request/trace/idempotency identity, deterministic payload hashes and
  exact ordered request nodes.
- Added closed Mock validation truth. Phase 5 can finish only at `validated`
  or `manual_intervention`; it cannot dispatch, report `succeeded`, or expose
  formal Item/MBOM identifiers.
- Added the required ten no-network fault classifications for duplicate,
  payload conflict, timeout after possible commit, rate limit, target 5xx,
  business validation, partial node success, stale mapping, unavailable target
  and restart/replay. Retry and reconciliation facts are descriptive only and
  cannot dispatch in Phase 5.
- Replaced the accepted generic browser-selected `operation + payload` seed
  with Project/released-EBOM-scoped list/create/detail OpenAPI routes and a
  closed create schema. Added only future sandbox event identities; no endpoint,
  credential, production mode or network behavior was added.
- Added seven additive guarded DocTypes for publish policy/version, request,
  node, mapping observation, node result and actor-bound command idempotency.
  Request history is append-only, denied deletes are audited, formal target
  identifiers remain read-only observations and no default business records
  are installed.
- Added direct `zh` and `zh-TW` translations for every new literal source and
  regenerated the deterministic React catalog from the Frappe v15 CSV source.

Production ERPNext access, Outbox dispatch, automatic retry/replay, webhook
consumption, reconciliation jobs and formal Item/MBOM mutation remain
prohibited and deferred to Phase 8.

## Changed-files to affected-tests

| Change boundary | Affected verification |
|---|---|
| publish request domain and fault taxonomy | `tests.test_phase5_publish_request_domain` |
| OpenAPI, ownership and future event vocabulary | `tests.test_phase5_publish_request_contract`; JSON and YAML parse |
| additive DocTypes and guarded validation helpers | `tests.test_phase5_publish_request_metadata`; Python compilation |
| exact predecessor EBOM relationship | complete P5-04 EBOM API/contract/controller/domain/metadata/repository/security modules |
| literal English and direct Chinese catalogs | `npm run lint:i18n`; `npm run generate:check` |
| public contract/Schema/shared catalog checkpoint | complete ordinary CI repository, E2E, secret and fixed-Linux visual jobs |

## Local Level 1 results

| Check | Result |
|---|---|
| new P5-05 domain/contract/metadata | `PASS — 22/22` |
| P5-04 EBOM predecessor plus P5-05 affected modules | `PASS — 72/72` |
| Python compilation | `PASS` |
| integration event and seven DocType JSON parse | `PASS` |
| OpenAPI and ownership YAML parse | `PASS` |
| V1.2 reconciliation verifier | `PASS` |
| i18n audit | `PASS — 3,683 literal English sources; direct 100% zh/zh-TW` |
| generated catalog check | `PASS` |
| `git diff --check` | `PASS` |

## Exact-SHA ordinary CI classification

Ordinary CI `31093873820` ran on exact product SHA `258277c`:

- repository job `92591063338` passed complete `verify.sh`, complete non-visual
  E2E, current-tree Gitleaks and complete branch-history secret scan;
- controlled P5 runtime job `92591063842` correctly skipped for the ordinary
  pull-request event; and
- fixed-Linux visual job `92591063141` passed `44/62` and failed exactly the
  eighteen durable P0 normal-state cases.

Visual artifact `8964668073` has GitHub digest
`sha256:ff008bedb4d189ca33ff17a404ecea5a48f47f02163d381fe0cd746400f599a0`.
Original-resolution review and exact pixel comparison prove:

- every one of the eighteen diffs is confined to the fixed bottom status bar
  at `y=879..899`; the product workspace has zero changed pixels;
- the only visible content change is the deterministic catalog fingerprint,
  from `b4eead0d9711948` to `da1371bd0cacf5c2` after the approved catalog grew
  from 3,508 to 3,683 complete sources; and
- all other forty-four governed Linux cases passed unchanged.

The bounded evidence repair copies only those eighteen exact CI `actual.png`
files over their corresponding tracked `*-linux.png` baselines. Every copied
file was compared byte-for-byte with its source. No test, threshold, matrix,
layout, source string, translation, product code or PASS criterion changes.
The repaired candidate must pass complete ordinary CI before this checkpoint
is closed and before repository/BFF implementation begins.

## Rollback

Revert the P5-05 product checkpoint and the eighteen catalog-fingerprint
baselines before retained publish-request history exists. After history exists,
disable the P5-05 route and dispatch capability through a reviewed forward fix
while preserving every request, node, mapping observation, result, audit and
idempotency receipt. Never contact or mutate ERPNext as rollback.
