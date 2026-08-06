# P5-05 Formal Item/MBOM Publish Request Plan

Recorded: `2026-08-06T09:57:00Z`

Status:
`IN_PROGRESS — REQUIREMENT, OWNERSHIP AND INTEGRATION AUDIT PASS`

Task:
`P5-05 — Formal publish request stub and contract`

Requirement:
`FR-DS-013`

Starting product checkpoint:
`2c0734a4201ac5ee4b53eae913ce01172634da3f`

## 1. Audited repository facts

- P5-04 supplies one exact released NPI-owned EBOM revision, immutable line
  snapshots, exact policy/revision hashes, lifecycle version, release event,
  actor, request and trace history.
- `contracts/npi-api.openapi.yaml` currently exposes a generic
  `CreateExecutionRequest` whose caller selects an operation and supplies an
  open `payload`. It does not bind a released EBOM or prove per-node mapping,
  partial result, authority, replay or no-fake-success truth.
- `apps/npi_integration/npi_integration/reliable.py` and the existing Outbox/
  Inbox DocTypes are Phase 2 message-safety foundations only. They do not
  implement an approved formal Item/MBOM request or an ERPNext adapter.
- `contracts/data-ownership.yaml` keeps formal `item_code`, stock UOM, MBOM,
  routing and manufacturing execution ERPNext-owned. NPI One may send only
  exact released engineering identity/content through an Execution Request.
- No production ERPNext host, credential, Item/BOM customization, submitted-
  BOM mutation rule or approved node-mapping policy exists. These are scoped
  holds, not blockers to strict Mock and sandbox-ready contract work.

The audit therefore rejects rebranding the generic seed or Outbox/Inbox as
P5-05 completion evidence.

## 2. Minimum complete vertical slice

P5-05 will deliver:

1. a separate exact Project-scoped published publish-request policy with
   explicit internal requester bindings, Mock default and no installed
   production authority;
2. one operation-specific `publish_released_ebom_item_mbom` command whose
   browser input selects an exact EBOM/revision and exact optimistic versions,
   not an arbitrary operation or payload;
3. server-resolved immutable request input containing the exact released
   revision/policy/release-event/approval snapshot, complete ordered lines,
   owned-field manifest, actor, request, trace, API version, idempotency key
   hash and canonical payload hash;
4. one durable execution-request aggregate plus exact per-node desired
   Item/MBOM operations, mapping observations and append-only result records;
5. actor-bound replay and changed-payload conflict, independent Project and
   publish authority, CSRF, authorization-before-resolution, optimistic
   root/lifecycle version checks, atomic persistence, audit and route
   disable/recovery;
6. explicit target modes where `mock` is the only enabled Phase 5 mode,
   `sandbox` is contract-ready but unavailable until an approved named
   configuration exists, and `production` is rejected;
7. truth-preserving request/node states and future retry eligibility for
   duplicate, timeout-after-possible-commit, 429, 5xx, business 4xx, partial
   node success, stale mapping, unavailable target, restart and replay; and
8. a dense EBOM publish-request surface with visible source/mode, exact input,
   node mapping/result and unavailable/partial/failure truth, using literal
   English and direct `zh`/`zh-TW` translations.

`validated` means the NPI request and frozen input passed Phase 5 checks. It
does not mean queued, sent, accepted or completed by ERPNext.

## 3. Frozen contract decisions

- Public creation is operation-specific. The generic caller-selected
  `operation + payload` create seed is removed from the accepted browser
  contract; future unrelated operations require their own schemas/routes.
- The top-level operation is `publish_released_ebom_item_mbom`. Server-derived
  node intents are closed values `create_item`,
  `update_item_engineering_fields` or `create_or_update_mbom`; callers cannot
  inject them.
- The exact release/approval snapshot is the EBOM revision, policy reference,
  lifecycle version and release event/confirmation evidence already owned by
  P5-04. P5-05 will not invent a relationship to a Document Baseline when none
  exists.
- Every EBOM line receives a stable request-node identity and an immutable
  input hash. Mapping state, target identifiers and result history are
  distinct from engineering content and never rewrite the EBOM.
- Mock validation cannot populate a formal Item Code/MBOM ID or any
  `succeeded` state. A formal target identifier is accepted only from a future
  authenticated target result at the Phase 8 adapter boundary.
- Request acceptance and target execution remain distinct. No Outbox message
  is created in Phase 5, because dispatch is not authorized.
- Partial success is represented at node level; aggregate state is derived.
  Safe retry eligibility is descriptive only in Phase 5 and cannot dispatch.
- Production schemes/hosts, loopback/private-link exceptions, credentials and
  service identities are neither persisted in browser-visible records nor
  accepted by this task.

These decisions preserve the existing Requirement, architecture and ownership
contracts; no ADR is required.

## 4. Scope and non-scope

In scope:

- operation-specific domain/OpenAPI/event contract;
- additive publish policy, request, input node, mapping observation, result,
  audit and idempotency persistence;
- Mock validation and sandbox-ready configuration shape;
- BFF read/create paths and exact Project EBOM workspace presentation;
- deterministic adapter-outcome classification and no-contact fault fixtures;
- tests, migration/runtime verifier, trilingual/visual evidence and controller
  trace updates.

Out of scope:

- any production or sandbox network request;
- ERPNext credentials, secrets, service account or endpoint activation;
- creating/updating an actual Item, BOM, routing, stock UOM or submitted BOM;
- automatic retry, worker scheduling, webhook consumption, replay execution,
  DLQ or reconciliation jobs;
- production field mapping, conversion, company/factory/tax context or Item/
  BOM custom-field decisions; and
- changing EBOM, Item or MBOM ownership.

Real adapter execution, retry/replay, inbound confirmation and reconciliation
remain Phase 8.

## 5. Assumptions and scoped holds

- Synthetic fixtures may publish a separate policy with fixed internal users
  and visibly synthetic namespaces. No fixture is a production default.
- Engineering Item ID, description, hierarchy, quantity, engineering UOM,
  alternates, effectivity and bounded attributes may be frozen as NPI-owned
  request input. They are not asserted to be formal ERP values.
- Missing formal Item mapping, stock UOM, MBOM ID or routing is visible node
  truth. It does not block Mock validation unless the selected closed
  operation specifically requires an immutable existing mapping.
- Exact production Item/BOM field maps, endpoint/version rules, submitted-BOM
  restrictions, retry schedule and reconciliation ownership remain Class-B
  holds recorded in `implementation/REQUIRED_INPUTS.md`.

## 6. Primary risks and controls

| Risk | Control |
|---|---|
| Generic payload lets a browser invent ERP writes | Replace accepted create seed with a closed EBOM publish command and server-derived node intents |
| Request acceptance is shown as ERP success | Mock ends at `validated`; target IDs and success are forbidden; source/mode/state remain visible |
| Mutable/latest EBOM input drifts | Resolve one exact released revision, policy hash, lifecycle version and release event under lock; store canonical input/payload hashes |
| Release authority silently grants publish authority | Separate published publish-request policy and exact internal requester binding |
| Duplicate or changed replay creates divergent requests | Actor + operation + idempotency identity with immutable payload hash and sealed response replay |
| Partial result is collapsed into success/failure | Persist per-node mapping/result history and derive aggregate state without hiding failed/uncertain nodes |
| Timeout after commit is retried unsafely | Model `uncertain_after_timeout`; future retry requires target idempotency/reconciliation and is disabled in Phase 5 |
| Stale mapping silently overwrites ERP identity | Immutable mapping observation/version; conflict/stale states fail closed and never choose a winner |
| Sandbox-ready code reaches production | Named configuration only, production target rejection, no credential field in public/API records and no Phase 5 dispatch |
| Transaction failure leaves partial request truth | Freeze receipt -> request -> nodes -> mapping/result -> audit -> response -> receipt-seal order and prove rollback |

## 7. Expected change surface

Backend and metadata:

- `apps/npi_integration/npi_integration/publish_request/` domain, Frappe
  validation and repository modules;
- `apps/npi_integration/npi_integration/publish_request_api.py`;
- additive NPI Integration DocTypes for policy/version, request, node,
  mapping observation, result and command idempotency;
- the existing NPI Core request-security/BFF route adapters only where needed
  to expose the NPI Integration controller through `/api/npi/v1`.

Contracts:

- operation-specific P5-05 paths and closed schemas in
  `contracts/npi-api.openapi.yaml`;
- publish-request/mapping/result ownership rows in
  `contracts/data-ownership.yaml`;
- versioned event payload definitions only for the future dispatch/result
  identities needed by the sandbox-ready boundary.

Frontend and language:

- the existing EBOM data source/workspace and focused tests;
- literal-English sources plus direct `apps/npi_core/npi_core/translations/
  zh.csv` and `zh-TW.csv` entries;
- focused browser, accessibility and exact trilingual visual cases.

Verification/evidence:

- focused P5-05 domain/metadata/repository/API/contract/security/runtime tests;
- a no-network fault-classification suite;
- controlled disposable-Site verifier extension;
- Phase 5 evidence/controller/trace files.

No production dependency is planned.

## 8. Changed-files to affected-tests plan

| Change boundary | Required affected checks |
|---|---|
| publish-request domain and fault taxonomy | deterministic hash/state/aggregate/partial/uncertain/stale-mapping tests for every required fault case |
| additive DocTypes and guards | JSON metadata, immutable/delete/update guards, install/migrate twice and rollback tests |
| repository/idempotency/audit | exact release resolution, authorization, replay/conflict, concurrent winner, transaction rollback and restart/replay tests |
| BFF/OpenAPI/ownership/event contract | schema closure, headers/status, CSRF, IDOR, version and no-service-secret/no-open-payload scans |
| EBOM publish UI | data-source/component tests, loading/empty/no-permission/read-only/validation/conflict/processing/partial/unavailable/failure states |
| catalogs | literal extraction, `zh`/`zh-TW` direct coverage, placeholder, terminology and mixed-language scans |
| runtime verifier | two migrations, exact released input, Mock no-fake-success, replay/conflict, route disable/recovery and cleanup |
| complete task | current-module suite, affected E2E/visual/i18n/security, trace/diff review and Level 2 Gate |

## 9. Implementation checkpoints

1. Domain, closed operation-specific contract and additive metadata.
2. Repository, permission/idempotency/audit, BFF and Mock persistence.
3. EBOM publish-request workspace, i18n and browser/visual evidence.
4. Controlled-Site runtime, Level 2 Task Gate and Phase 5 Level 3 Gate.

Each checkpoint runs Level 1 affected checks and exact diff review. P5-05 is
complete only after Level 2. Because P5-05 ends Phase 5 and changes public
contract/Schema/integration infrastructure, the final accepted candidate also
runs the complete Phase 5 Level 3 `release-gate` after one controlled-Site
PASS.

## 10. Rollback

Before retained request history exists, a disposable environment may revert
the P5-05 product checkpoint and migrate fresh. After retained request,
mapping or result history exists, rollback is a reviewed forward fix: disable
only the P5-05 route and all dispatch capability, keep reads available where
safe, and preserve every request, input, mapping observation, result, audit
and idempotency receipt. Never delete/rewrite history or touch ERPNext.

## 11. First implementation action

Add and test the pure operation-specific request/fault domain plus closed
OpenAPI and ownership vocabulary. Do not create a route, persistent record or
UI until the exact state, hash, mapping and Mock no-fake-success invariants
pass their affected tests.
