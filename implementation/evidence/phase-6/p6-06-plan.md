# P6-06 Tooling Acceptance and Asset Request Plan

Recorded: `2026-08-08T22:21:01Z`

Status:
`IN_PROGRESS — REQUIREMENT, DOMAIN AND EXISTING-CAPABILITY AUDIT PASS`

Task:
`P6-06 — Acceptance and asset execution request`

Requirements:
`FR-TL-011..016`

Starting controller checkpoint:
`943d1ea6863ab348afb5bb2f6e0781459d636577`

Starting exact-SHA ordinary CI:
[`31281224456`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31281224456)
(`PASS`; repository `93162778363`, fixed-Linux visual `93162778393`,
controlled runtime correctly skipped)

## 1. Audited repository facts

- P6-01 through P6-05 provide distinct Tooling Requirement, Master, physical
  Set and immutable Revision identities; exact Set-to-Revision binding;
  customer-owned intake evidence; released-document evidence; internal
  manufacturing plans; defect/action evidence; Customer Standard process
  values; and deterministic Capacity Scenario revisions.
- The current Tooling surfaces intentionally return ERP Asset, location,
  lifecycle, Trial, procurement and health projections as `unavailable` when
  no authoritative reader exists. They do not store a zero/default value or
  infer target success.
- `DR-REC-010` still holds exact Tooling Requirement, Revision and Set
  lifecycle states, transitions, skip/reopen/terminal rules and authority.
  The repository therefore has no approved Tooling-acceptance transition,
  acceptance approver policy or business event that can truthfully assert
  `accepted`.
- Phase 7 has not supplied live Trial Round, official quality or Approved
  Process Baseline truth. Those facts may be referenced as explicitly
  unavailable conditions; P6-06 cannot fabricate them from Customer Standard,
  defect severity or a caller flag.
- P5-05 removed the generic caller-selected `operation + payload` browser
  Execution Request seed and replaced it with one operation-specific EBOM
  publish aggregate. The generic route cannot be revived or relabelled for an
  Asset operation.
- The P5-05 publish aggregate, Phase 2 Outbox/Inbox DocTypes and
  `npi_integration.reliable` are reusable reliability patterns, not an
  approved Tool Asset adapter. No Asset request, target mapping, result,
  reconciliation reader or production ERPNext configuration currently
  exists.
- `contracts/data-ownership.yaml` makes formal Asset ID, Asset state,
  physical location, shot count, maintenance, repair/downtime and formal
  spares/inventory ERPNext-owned. NPI One owns immutable Project evidence,
  exact Tooling identities and a formal execution intention only.
- `docs/DOMAIN_MODEL.md` allows ERPNext Asset identifiers to enter a mapping
  only after a successful target-confirmed Execution Request. One physical
  Tooling Set may have zero or one formal Asset mapping; every copied Set is a
  separate physical identity and therefore a separate mapping subject.
- `contracts/integration-event.schema.json` currently defines only the
  operation-specific P5-05 ERP publish command/result payloads. It contains no
  `create_or_update_tool_asset` command/result contract and emits no such
  event.
- No production ERPNext endpoint, credential, Asset customization, mapping,
  location vocabulary, movement workflow, maintenance policy, spare Item
  mapping, repair-cost rule or target idempotency behavior is approved.

The audit therefore rejects all of the following shortcuts:

- treating evidence capture as Tooling acceptance approval;
- showing a locally persisted request as an ERP Asset creation/update;
- assigning a formal Asset ID from the browser or a synthetic fixture;
- reusing Outbox/Inbox rows as proof that an Asset request was queued or sent;
- copying an Asset/location/shot/maintenance value into NPI-owned Tooling
  fields; or
- implementing movement, repair, inventory or cost execution in Phase 6.

## 2. Truthful P6-06 completion boundary

P6-06 will deliver a technical foundation and live no-fake-success workspace:

1. one immutable, versioned Tooling acceptance-evidence revision for an exact
   Project, Master, physical Set and bound Tooling Revision;
2. closed evidence sections for the required technical, quality, cycle/
   capacity, spares/maintenance, documents, warranty/responsibility, cost,
   safety/interface and Asset/location categories;
3. immutable NPI-owned evidence for proposed move/loan/return/archive/scrap
   actions, spare/wear recommendations and repair authorization/quote/
   responsibility/downtime/verification without claiming ERP execution;
4. one operation-specific `create_or_update_tool_asset` request-preparation
   command whose complete input is server-resolved from exact retained Tooling
   and evidence versions;
5. a durable local request aggregate that remains `draft`, has technically
   validated Mock input, shows acceptance authority as `unavailable` and has
   dispatch explicitly `prohibited`;
6. a closed sandbox-ready command/result event shape for future Phase 8 use,
   with no emitted event, Outbox message, worker, endpoint or credential;
7. an explicit default-unavailable ERP Asset projection and strict future
   projection shape for formal mapping, location/state/life/maintenance,
   movement, repair and spares truth; and
8. a dense trilingual Tooling acceptance/Asset workspace that keeps evidence,
   business approval, request preparation, target execution and ERP projection
   as separate visible states.

P6-06 can technically verify the immutable evidence and no-fake-success
foundation of `FR-TL-011..016`. The exact Requirement statuses at Level 2
will remain `TECHNICAL_VERIFIED_FOUNDATION` wherever Phase 7 approval/quality
or Phase 8 ERP execution/projection is still required.

## 3. Frozen domain decisions

### 3.1 Acceptance evidence is not acceptance authority

The aggregate is named `ToolingAcceptanceEvidenceRevision`, not an accepted
Tooling lifecycle state. It is append-only and binds:

- exact Project, Tooling Master and physical Tooling Set identities;
- exact immutable Set snapshot hash and exact Set-to-Tooling-Revision binding;
- exact Tooling Revision identity, revision label, revision number and snapshot
  hash;
- predecessor revision, evidence revision number and canonical snapshot hash;
- recorder, recorded time, request and trace identities; and
- complete typed evidence sections.

Each checklist item records an English business requirement statement,
category, evidence disposition, optional responsible Project member, exact
clean private File Revision references and an optional note. The only closed
dispositions are:

- `evidence_recorded`;
- `evidence_missing`; and
- `not_applicable_asserted`.

These are evidence-presence assertions, not pass/fail, approval, waiver,
Tooling lifecycle or Gate conclusions. The server derives category coverage
from the exact item/evidence set and never converts coverage into acceptance.
At least one item is required for every frozen category so absence remains
visible rather than silently omitted.

`businessApproval` is always the closed unavailable projection
`tooling_acceptance_policy_unavailable` in Phase 6. No caller field can make
it available.

### 3.2 NPI-owned Asset-adjacent evidence

The same immutable revision may contain bounded typed records for:

- `move`, `loan`, `return`, `archive` and `scrap` evidence intentions;
- critical spare and wear-part recommendations;
- repair authorization, quote, responsibility, downtime impact and
  verification evidence.

They are Project evidence only:

- an Asset action record stores intended action, reason, exact evidence and
  optional external approval reference; `executedInErp` is never accepted and
  the response states `erpExecution: unavailable`;
- a spare recommendation stores an NPI recommendation key, description,
  critical/wear classification, recommended minimum quantity and unit, plus
  optional supplier source reference. It never creates an Item or stock level;
- a repair record stores authorization evidence, quote reference/amount,
  responsible Project member, planned downtime impact and verification
  evidence. Customer-owned Sets require customer-authorization evidence; and
- every formal supplier, Item, inventory, movement, repair transaction and
  cost result remains an unavailable ERPNext projection unless a future
  authenticated Phase 8 reader supplies it.

No action evidence changes Set lifecycle, location or custody automatically.

### 3.3 Operation-specific Tool Asset request preparation

The browser command selects only:

- the exact acceptance-evidence revision;
- exact Master/Set/binding/Revision snapshots and optimistic File/evidence
  versions and hashes;
- `targetMode: mock`; and
- the fixed acknowledgement that business approval and ERP execution are not
  being claimed.

The browser cannot supply operation, arbitrary payload, tenant, actor, formal
Asset ID, Asset state, location, shot/life, maintenance, target result or
request state.

The server fixes `operation: create_or_update_tool_asset`, resolves and locks
all input again in one transaction, and stores a canonical request-input hash.
The request has separate truth axes:

- `requestState: draft`;
- `inputValidationState: validated_mock`;
- `businessApprovalState: unavailable`;
- `dispatchState: prohibited`; and
- `targetResultState: not_requested`.

It creates no Outbox message and no target mapping/result. `mock` is the only
enabled mode. `sandbox` is contract-ready but unavailable until Phase 8 has an
approved named configuration and approval source; `production` is rejected.

The request is actor-bound and idempotent. An exact replay returns the sealed
response; changed input conflicts. A local request never produces a formal
Asset ID or `succeeded` state.

### 3.4 Formal Asset mapping and projection

The formal mapping subject is one physical Tooling Set, not a Tooling Master,
Requirement, planned quantity or mutable business code.

P6-06 freezes these conditions:

- cardinality is zero-or-one formal Asset mapping per physical Set;
- copied molds are distinct Sets and therefore distinct mapping subjects;
- mapping may be created or changed only from authenticated ERPNext target
  confirmation with exact request/result and prior-observation identity;
- NPI One never chooses an Asset ID, overwrites an ERP mapping or resolves a
  competing target observation; and
- the default live projection is `unavailable` with source `ERPNEXT`,
  editable-in `ERPNEXT` and reason `erp_asset_projection_unavailable`.

The future available projection contract contains exact source observation,
mapping version, formal Asset ID, target version, Asset state, location,
shot/life, maintenance due, bounded movement/repair history and formal spare/
inventory references. It is read-only and cannot be constructed from browser
input.

## 4. Public API and persistence boundary

The accepted browser contract will be Project-first and operation-specific:

- `GET /projects/{projectId}/tooling/{toolingMasterId}/acceptance-assets`;
- `POST /projects/{projectId}/tooling/{toolingMasterId}/acceptance-revisions`;
- `GET /projects/{projectId}/tooling/{toolingMasterId}/asset-requests`;
- `POST /projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/asset-requests`;
  and
- `GET /projects/{projectId}/tooling/{toolingMasterId}/asset-requests/{assetRequestId}`.

The exact OpenAPI implementation may consolidate read results, but it may not
add a generic execution-request create route or caller-selected payload.

Additive persistence is limited to:

- one guarded append-only `NPI Tooling Acceptance Evidence Revision`;
- one guarded append-only `NPI Tool Asset Request` in `npi_integration`; and
- one actor-bound one-way-sealed Tool Asset command-idempotency receipt.

Nested checklist/action/spare/repair values are frozen in canonical closed
snapshots. No migration installs business rows, policy, mapping, endpoint,
credential, ERP fact or production default.

## 5. Integration contract boundary

The event schema may add closed future event types for:

- `npi.tooling_asset_request.ready`; and
- `erpnext.tooling_asset_result.observed`.

The command payload fixes `operation: create_or_update_tool_asset`, exact
request/Tooling/Set/Revision/evidence identity and hashes, and NPI-owned
request fields only. The result payload requires the exact request/input hash,
target idempotency identity, formal Asset mapping observation and explicit
per-operation outcome.

These shapes are sandbox-ready contracts only. P6-06 emits neither event and
creates no Outbox/Inbox row. Phase 8 owns adapter activation, authentication,
retry/replay, Webhook ingestion, mapping reconciliation and target-confirmed
projection persistence.

## 6. Authority, containment and security

- Every read authorizes Project scope before resolving Master/Set/evidence/
  request identifiers and returns one indistinguishable `404` for missing or
  cross-Project contained objects after Project authorization.
- Every command requires authentication, CSRF, System Manager management
  transport, actor-bound idempotency and the independent P6-06 route switch.
  System Manager transport does not become Tooling acceptance authority.
- Exact Master identity/snapshot, Project-contained Set snapshot, immutable
  Set-to-Revision binding, Revision snapshot, Project member, private clean
  File Revision and source-reference invariants are re-resolved on every
  command.
- File evidence exposes stable File Revision identity, hash, name and scan
  state only; it never returns a raw private URL.
- Acceptance revision, Asset request, audit and receipt persistence share one
  transaction. Rollback leaves no partial accepted/request truth.
- All retained records deny update and delete. Reads remain available during
  a forward repair where safe.

## 7. Scope and non-scope

In scope:

- pure acceptance/evidence/action/spare/repair and Asset request/projection
  domains;
- closed OpenAPI, ownership and future event schemas;
- additive guarded metadata and receipt values;
- Project-first repository/BFF commands and reads;
- Mock request preparation with no dispatch or target result;
- dense live acceptance/Asset workspace with all operational states;
- direct English, Simplified Chinese and Traditional Chinese catalogs;
- unit, contract, repository, API, security, browser, visual and controlled-
  Site evidence; and
- Level 2 Task Gate and truthful requirement trace update.

Out of scope:

- Tooling acceptance approval, rejection, waiver, lifecycle transition or
  approver policy;
- creating/updating an ERPNext Asset or choosing a formal Asset ID;
- target-confirmed mapping observation, competing-mapping resolution or
  reconciliation;
- any Asset location/state/movement, shot/life, maintenance, repair, spare,
  inventory, PO, invoice or cost mutation;
- production or sandbox network access, credentials, endpoint, service
  identity, worker, Outbox dispatch, Webhook, retry, replay or DLQ;
- Trial Round, official quality, Approved Process Baseline or Gate mutation;
- customer login, legal electronic signature or supplier portal;
- production checklist template, acceptance tolerance, warranty rule,
  movement workflow, maintenance policy, spare mapping or repair-cost rule;
- P6-07 import, P6-08 export or Phase 7 behavior; and
- any business fixture, production policy, mapping or external mutation from
  migration.

## 8. Requirement outcome plan

| Requirement | P6-06 technical outcome | Retained dependency |
|---|---|---|
| `FR-TL-011` | Immutable complete-category evidence revisions and a Mock-validated draft Asset request input | Business approval/quality source in Phase 7 and real Asset execution in Phase 8 |
| `FR-TL-012` | Physical-Set mapping subject and zero-or-one target-confirmation invariant | Formal Asset ID/mapping result and reconciliation in Phase 8 |
| `FR-TL-013` | Strict read-only available/unavailable projection contract and honest unavailable live state | Authenticated ERP Asset/location/life/maintenance/repair observations in Phase 8 |
| `FR-TL-014` | Immutable Project evidence for move/loan/return/archive/scrap with separate unavailable ERP execution | Actual Asset movement/approval integration in Phase 8 |
| `FR-TL-015` | Immutable critical/wear spare recommendations and explicit unavailable formal Item/stock truth | Formal spares, supplier mapping and inventory in ERPNext/Phase 8 |
| `FR-TL-016` | Immutable repair authorization/quote/responsibility/downtime/verification evidence; customer-owned Set authorization enforced | Formal repair/cost/history projection and any external approval integration in Phase 8 |

## 9. Primary risks and controls

| Risk | Control |
|---|---|
| Evidence revision is displayed as approved acceptance | Separate evidence coverage, business approval, request state, dispatch and target result; business approval remains unavailable |
| Mock request appears to create an Asset | Keep formal request `draft`, input only `validated_mock`, dispatch `prohibited`, target result `not_requested`, no Asset ID/Outbox/network |
| Browser invents a target mapping or ERP fact | Operation-specific closed input; server-resolved Tooling/evidence; formal mapping and projection are reader/result-only |
| Master or planned quantity is mapped instead of a physical Set | Bind every request/mapping condition to one exact Tooling Set; copied molds are independent Sets |
| Missing Trial/quality/approval is inferred from checklist coverage | Preserve explicit unavailable source conditions and never derive approval from coverage, defects or capacity |
| NPI evidence changes ERP movement/repair/stock truth | Keep actions/recommendations/repair records immutable NPI evidence and expose ERP execution/projection separately unavailable |
| Customer-owned repair lacks authorization evidence | Require exact clean private customer-authorization File Revision before retaining a customer-owned repair entry |
| Generic Execution Request reappears | Contract tests forbid generic operation/payload routes and require fixed `create_or_update_tool_asset` |
| Partial persistence creates false request truth | One transaction for evidence/request/audit/receipt and controlled rollback proof |
| Sandbox-ready schema contacts production | No endpoint/credential/Outbox/worker; target modes fail closed; controlled fixtures assert zero network and zero target IDs |

## 10. Expected change surface

Backend and metadata:

- `apps/npi_core/npi_core/tooling/acceptance_domain.py` and bounded repository
  composition;
- `apps/npi_integration/npi_integration/tool_asset_request/` domain and
  Frappe repository;
- operation-specific BFF controllers;
- additive acceptance/request/receipt DocTypes and guarded controllers; and
- independent P6-06 route switch plus controlled-runtime verifier extension.

Contracts:

- closed P6-06 paths/schemas in `contracts/npi-api.openapi.yaml`;
- exact ownership rows in `contracts/data-ownership.yaml`; and
- future no-dispatch command/result shapes in
  `contracts/integration-event.schema.json`.

Frontend and language:

- strict Tooling acceptance/Asset data source and dense selected-Master
  workspace;
- operational loading/empty/denied/read-only/validation/conflict/processing/
  unavailable/failure states; and
- literal-English sources plus direct `zh`/`zh-TW` Frappe CSV translations.

Verification and evidence:

- focused P6-06 domain/metadata/contract/repository/API/security tests;
- no-network/no-Outbox/no-target-ID tests;
- component/E2E/accessibility/trilingual visual cases;
- cumulative disposable-Site verifier; and
- checkpoint/Level-2 controller and trace evidence.

No new production dependency is planned.

## 11. Changed-files to affected-tests plan

| Change boundary | Required affected checks |
|---|---|
| pure acceptance/request/projection domain | category coverage, immutable hashes, customer-authorization rule, physical-Set mapping invariant, no-fake-success and strict hydration tests |
| additive DocTypes/guards/receipts | metadata closure, permission, update/delete denial, install/migrate twice and no-default-row tests |
| OpenAPI/ownership/event schemas | operation-specific closure, fixed states/source ownership, generic-route prohibition and schema validation |
| repository/idempotency/audit | Project-first auth, containment, exact version/hash, clean private files, replay/conflict, rollback, restart and bounded-list tests |
| BFF and route switch | authentication/CSRF/role/IDOR, error mapping, disable/recovery and no-network/no-Outbox tests |
| live workspace | exact request paths, server capabilities, complete states, keyboard/accessibility and no-fake-approval/ERP copy tests |
| translation catalogs | literal extraction, direct `zh`/`zh-TW`, placeholders, terminology and mixed-language scans |
| controlled Site | two migrations, immutable successor evidence, customer repair authorization, Mock draft request, replay/conflict/rollback/IDOR, no target truth and route recovery |
| complete task | module suite, affected E2E/visual/i18n/security, trace/diff review and Level 2 Gate |

## 12. Implementation checkpoints

1. Pure acceptance/request/projection domains, closed contract/ownership/event
   shapes, guarded additive metadata and direct tests. No route or business row.
2. Project-first repositories, BFF routes, actor-bound idempotency/audit,
   Mock request persistence, explicit unavailable projections and security
   tests. No SPA or controlled Site.
3. Dense acceptance/Asset workspace, direct trilingual catalogs,
   accessibility, operational-state E2E and fixed-Linux visual evidence.
4. Cumulative disposable-Site proof, complete ordinary CI and P6-06 Level 2
   Task Gate.

Each checkpoint runs Level 1 affected checks and exact Task Diff Review. P6-06
is complete only after Level 2. Phase 6 Level 3 remains deferred until P6-08
finishes unless a checkpoint crosses another Level 3 trigger.

## 13. Rollback

Before retained acceptance/request rows exist, a disposable environment may
revert the additive checkpoint and migrate fresh. After retained rows exist,
rollback is a reviewed forward fix: disable only P6-06 routes and request
preparation, keep safe reads available, and preserve every immutable evidence
revision, request, audit and idempotency receipt. Never delete or rewrite
history, remove a target mapping, contact ERPNext or alter P6-01 through P6-05
truth.

## 14. Audit conclusion and first implementation action

The audit passes without an ADR because the plan preserves the approved
architecture, field ownership, no-cross-database rule, Frappe v15 translation
chain and Phase 8 integration allocation.

Autopilot may start only checkpoint 1: pure domains, closed contracts and
additive guarded metadata. Repository routes, live SPA, controlled-Site
execution and all business approval/Trial/Gate/ERP behavior remain inactive
until their preceding checkpoints pass.
