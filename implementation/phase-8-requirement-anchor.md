# Phase 8 Requirement Anchor — ERPNext Reliable Integration

Status: **IN PROGRESS — P8-04 AUDIT PASS; CHECKPOINT 1 AWAITS EXACT-SHA ORDINARY CI**

Anchor date: 2026-08-16

Controller phase: 8 — ERPNext Integration and Execution Requests

Retained predecessor product checkpoint:
`31114021cf18cf5e32c22902de5150ed2922e7ba`

Validated anchor/controller checkpoint:
`1da93f4d21dd434c99cfdc778ac1e63c4668d114`

Validation evidence:
`implementation/evidence/phase-8/p8-00-validation.md` — ordinary CI
`31901621310` PASS

## 1. Authority and bounded outcome

This anchor allocates M7-01 through M7-09 under the repository's fixed system
boundary:

> NPI One browser -> NPI One BFF/domain API -> durable NPI integration
> boundary -> operation-specific Mock or explicitly configured sandbox adapter
> -> observed target result/projection

ERPNext remains the formal manufacturing and commercial execution system.
NPI One never writes its database, never lets the browser call ERPNext and
never treats a queued/accepted request, network response or timeout as target
success. `NPI_ONE` and `ERPNEXT` remain stable technical system codes. The
approved display text `JCE Core` and exact `docs/Brand Asset/Core.png` are
presentation facts only and are activated solely by P8-09.

Phase 8 delivers Mock-default and sandbox-ready contracts, adapters,
projections, operation lifecycle, replay/reconciliation and operational truth.
Production ERPNext endpoints, credentials, data and network contact remain
prohibited. Missing production facts do not block Mock, contract, local
disposable-Site or safe sandbox-adapter work.

## 2. Requirement allocation and atomic order

| Atomic task | Compatibility task | Primary requirements | Truthful delivery boundary |
|---|---|---|---|
| P8-01 — read-only master and status projections | M7-01 | INT-001, INT-006, INT-007, INT-010; FR-PM-010, FR-TL-008, FR-TR-006, FR-NP-006 | Versioned ERP-owned Customer/Supplier/Item/procurement/cost/quality/Asset-status observations with source version, staleness and unavailable truth; no NPI edit or inferred target value |
| P8-02 — signed webhook and Inbox processing | M7-02 | INT-002, FR-PM-002; inbound foundations for INT-001/006/007; NFR-INT-001 | Verify signature and replay window before durable Inbox landing; deduplicate exact event identity/hash; process asynchronously; create at most one Project draft from one exact submitted source document; no long business work in the webhook request |
| P8-03 — Item publish execution | M7-03 | INT-003; Item portion of FR-DS-013 | Separate operation-specific Item request with exact released source/hash, expected target version, actor/trace/idempotency and observed target Item mapping; Mock cannot report a formal Item code |
| P8-04 — MBOM publish execution | M7-04 | INT-004; MBOM portion of FR-DS-013 | Operation-specific MBOM request/result over exact released EBOM nodes and observed Item mappings; preserve per-node partial/uncertain truth and never overwrite a submitted BOM |
| P8-05 — Tool Asset execution | M7-05 | INT-005; FR-TL-011, FR-TL-012, FR-TL-013, FR-TL-014, FR-TL-015, FR-TL-016 | One physical Tooling Set per zero-or-one formal Asset mapping, operation-specific create/update request and read-only observed Asset/location/maintenance result; NPI acceptance evidence is not ERP approval |
| P8-06 — quality linkage | M7-06 | INT-007; FR-TR-006, FR-NP-006 | Read-only formal Quality Inspection/NCR/CAPA references and explicit request/result linkage where an approved sandbox operation exists; ERP result remains authoritative and a failed/unavailable result cannot be presented as pass |
| P8-07 — operations, DLQ, replay and reconciliation | M7-07 | FR-RP-009, UX-016, NFR-INT-001 | Project/operation-scoped job center over durable Outbox/Inbox/execution attempts, classified retry/final/uncertain states, DLQ, actor-authorized replay and reconciliation; operators need no database access and cannot mutate business truth through a generic API |
| P8-08 — Released Trial Summary projection boundary | M7-08 | FR-INT-015 | Reuse the exact immutable NPI summary source and prepare a read-only adapter seam with explicit unavailable state. Exact event name, payload version, redaction, consumer mapping and external receipt remain held by DR-REC-009 and are not invented |
| P8-09 — approved JCE Core display adapter | M7-09 | FR-BR-002 | Present approved `JCE Core` text and exact `Core.png` only in ERP/JCE display contexts; keep `ERPNEXT` and all API/event/schema codes stable; no substitute or redrawn mark |

`ANCHORED_P8_XX` means allocated, not implemented, target-confirmed or
production accepted. Carried Phase 5/6/7 foundations keep their existing
truthful status until their exact Phase 8 slice produces new evidence.

## 3. Interface-catalog boundaries

The complete `INT-001..014` catalog remains traceable, but the Phase 8 task
list does not authorize every optional or later-domain connector:

- `INT-001`, `INT-002`, `INT-003`, `INT-004`, `INT-005`, `INT-006`,
  `INT-007` and `INT-010` are allocated above.
- `INT-008` depends on the Phase 9 Change domain and formal ERP change
  numbering; Phase 8 may reuse transport/Inbox primitives but must not claim a
  bidirectional change integration.
- `INT-009` requires an approved ERP/DMS file consumer, immutable-copy mapping
  and sandbox operation. Existing released NPI files remain authoritative
  NPI copies; no external file publication is inferred.
- `INT-011` requires an approved target summary-field mapping. Phase 8 may
  prove operation mechanics but must not update unspecified ERP fields.
- `INT-012` requires the current identity-platform topology, principal mapping
  and service-account scopes from the external reconciliation package. It is
  not satisfied by inventing OIDC/LDAP/SCIM configuration.
- `INT-013` is optional and no OpenProject provider/ownership decision is
  approved. Hub Gate truth cannot be delegated to an optional task system.
- `INT-014` belongs to the Phase 9 reporting/BI boundary. Any future feed is
  read-only and BI can never write back.

These are scoped holds, not global blockers. The anchor will not silently add
unlisted P8 product tasks or mark held connectors complete.

## 4. Ownership and shared-object invariants

- Customer, Supplier, formal Item code/UOM, MBOM/routing, PO/receipt/invoice,
  inventory/manufacturing, formal Quality Inspection/NCR/CAPA, Asset/location/
  maintenance, production actual cost and finance remain ERPNext-owned.
- NPI One owns Engineering Project collaboration, draft engineering identity,
  EBOM, design/baseline source, Tooling development/acceptance evidence,
  Trial/NPI collaboration and immutable Released Trial Summary source truth.
- A shared object is one logical object with field-level ownership and an
  external reference, not two freely editable copies. No field is dual-master.
- Inbound observations retain target identity, business version/modified time,
  source event, received time, payload hash, projection state and staleness.
  Older or reordered events cannot overwrite newer truth.
- NPI requests retain exact source identity/version/hash. Target mappings and
  success are written only from authenticated observed target results; a
  caller cannot supply them as truth.
- Any ownership change requires a contract update, ADR, migration/rollback
  analysis and approval before code.

## 5. Execution request and result invariants

Every write operation has a separate closed request/result contract and
adapter method. No `write_doc`, generic DocType CRUD or caller-selected target
method is allowed.

Each request includes or derives:

- operation name and contract version;
- exact NPI source object, business version and canonical input hash;
- target system code and explicitly selected `mock` or approved `sandbox`
  mode;
- actor, tenant, Project, request and trace/correlation context resolved on
  the server;
- actor-bound idempotency key/hash and expected target version where known;
- minimum required payload with no secret or unnecessary personal/commercial
  content; and
- immutable approval/source evidence when the operation requires it.

Approval/release and execution remain different facts. A request can be
prepared or queued only after the exact source authority passes, but that does
not make the target operation succeed.

Results use explicit states such as `succeeded`, `failed_retryable`,
`failed_final`, `uncertain_after_timeout` and `target_unavailable`. They retain
target reference/version only when observed, response hash, attempt identity,
failure class/code, retry timing and reconciliation state. Partial node
results remain partial; no aggregate optimistic success masks them.

## 6. Signed webhook, Inbox and projection invariants

- Receive only TLS requests at operation-specific endpoints. Resolve the
  configured source without accepting caller-selected tenant or authority.
- Verify supported algorithm, key identifier, HMAC/signature, timestamp,
  bounded replay window and exact raw-body digest before trusting the event.
- Land the minimal envelope and immutable body/hash in a durable Inbox before
  returning success. Invalid signatures, oversized/unknown bodies and hash/
  event-ID reuse conflicts fail closed and are audited without logging secrets.
- Deduplicate by exact event identity plus payload hash. Same identity/same
  payload is safe replay; same identity/different payload is a conflict.
- Process outside the webhook request, resolve ownership and Project scope
  before secondary identifiers, enforce version ordering and retain ignored/
  superseded truth rather than deleting it.
- Reordered or duplicate events, restart after landing, restart during
  processing and cross-process replay must not duplicate business effects.

## 7. Outbox, retry, replay and reconciliation invariants

- Persist business state and Outbox command atomically when an NPI transaction
  authorizes dispatch. A worker claims one immutable attempt; restart cannot
  lose or duplicate the logical operation.
- Retry only classified transient failures: target unavailable, bounded
  timeout without confirmed commit, `429` with policy, and approved `5xx`
  classes. Validation, permission, ownership, version and unsupported-operation
  failures are final until a new corrected request is authorized.
- A timeout after possible target commit is `uncertain_after_timeout`, not
  retryable success. Reconcile by idempotency/external reference before any
  redispatch.
- Backoff, maximum attempts, next retry, DLQ state, alert/owner and last safe
  error summary are explicit and versioned. Logs and UI expose trace IDs, not
  secrets or unrestricted payloads.
- Replay requires current operation/Project authority, impact review and the
  original immutable request identity. It creates an audited attempt, never a
  new business command or edited payload under the old idempotency key.
- Reconciliation compares exact NPI source/request/result and observed target
  identity/version/hash. Differences are visible, classified and assignable;
  repair is forward-only and never a cross-database overwrite.

Required fault cases include duplicate and reordered events, timeout before
and after target commit, `429`, retryable `5xx`, business `4xx`, partial
success, expired/rotated credentials, stale mapping, target unavailable,
worker restart and manual replay.

## 8. Adapter and environment safety

- `mock` is the default and cannot emit formal target identifiers or
  `succeeded` target confirmation.
- `sandbox` requires explicit configuration, allowlisted non-production host,
  operation-specific credentials/scopes and TLS. Configuration rejects known
  production hosts and cannot fall back to production.
- Credentials remain outside code, payloads, audit detail, fixtures and normal
  logs. Secret rotation/expiry is an explicit failure state.
- Tests use deterministic fakes and a disposable local Frappe Site. Any
  sandbox evidence must be separately authorized, sanitized and provenance-
  recorded; absence of a sandbox never justifies production contact.
- The browser calls only `/api/npi/v1` BFF/domain endpoints and never receives
  ERPNext credentials or unrestricted adapter error bodies.

## 9. UX, localization and operational truth

Any end-user or operations UI introduced by Phase 8 must use the industrial
App Shell, dense tables/tree/inspector layout, square geometry, one primary
action and explicit text/icon state. It must cover loading, empty, no-
permission, read-only, validation, queued, processing, retryable, final,
uncertain, partial, reconciled and target-unavailable states without relying
on color alone.

All user-visible source strings remain literal English through the local
Frappe-backed `t()` adapter, with direct `zh` and `zh-TW` translations and no
mixed ordinary language. Technical codes, IDs, hashes, units and allowlisted
terms remain untranslated. Retry/replay/resolve actions require translated
accessible names, keyboard/focus paths and explicit confirmation/impact.

## 10. Existing-capability audit

The repository already contains reusable foundations, not Phase 8 completion:

- `npi_integration.reliable` has pure event/hash, Outbox state and in-memory
  Inbox primitives, but no signed durable webhook, production worker or
  operational projection.
- Phase 5 EBOM publish requests and Phase 6 Tool Asset requests have closed
  domains, guarded DocTypes, Project-first APIs and Mock-only behavior. Mock
  intentionally returns no formal target success or identifier.
- Outbox/Inbox DocTypes exist as guarded foundations; their exact Frappe
  repositories, worker claiming, signature landing, retries, DLQ/replay and
  reconciliation are not yet live as a complete product boundary.
- Phase 5/6/7 screens expose ERP-owned values as read-only or unavailable.
  They do not prove authenticated source observations.
- The immutable Released Trial Summary exists on the NPI side. No exact
  external event/projection contract is approved under `DR-REC-009`.
- LaunchFlow display branding is complete. `Core.png` is supplied and approved
  only for the future JCE Core display adapter; internal `ERPNEXT` is unchanged.

## 11. Task verification order

Every P8 product task begins with a bounded requirement/domain/existing-
capability audit and freezes its exact operation, owner, source/result states,
adapter mode, fault matrix, paths, tests, migration and rollback before code.
Unless that audit proves a smaller slice, delivery uses:

1. pure domains, closed contract/event Schema, ownership and guarded additive
   metadata without live dispatch;
2. durable Project/operation-first repository, Inbox/Outbox/execution worker,
   signed/idempotent boundaries and atomic audit/receipt;
3. operation-specific Mock and explicitly bounded sandbox adapter plus fault
   injection and reconciliation proof;
4. dense direct-trilingual SPA/operations truth where required; and
5. cumulative disposable-Site runtime and exact-SHA Level 2 Task Gate.

Ordinary CI passes before every controlled runtime. Contract/Schema,
authentication/permission, shared integration infrastructure or other
cross-domain changes escalate to Level 3 under `implementation/QUALITY_GATE.md`.
Phase 8 ends with a complete Level 3 `release-gate`.

## 12. Changed-files to affected-tests map

| Change boundary | Minimum affected evidence |
|---|---|
| ownership/projection models | owner/editability, source version/order/staleness, no caller target truth, unavailable/IDOR/redaction tests |
| signed webhook/Inbox | raw-body signature, replay window, key rotation, duplicate/hash conflict, durable landing-before-success, restart/reorder tests |
| execution request/Outbox worker | exact source/hash/version, approval-execution separation, atomic Outbox, claim/restart/idempotency and no generic mutation tests |
| operation adapter | Mock no-success boundary; sandbox host rejection; timeout-after-commit, 429/5xx/4xx/partial/credential/stale-map faults and contract tests |
| replay/reconciliation | current authority, immutable payload, audited attempt, target compare/difference/forward-repair and no cross-db-write tests |
| BFF/permissions | tenant/Project/operation resolution order, CSRF, actor-bound idempotency, restricted diagnostics and error trace tests |
| operations/product UI | unit/state/accessibility, direct English/zh/zh-TW, mixed-language scan, fixed-Linux visuals and no color-only/optimistic success |
| JCE Core display | exact approved bytes/hash/usage, stable `ERPNEXT` code, light/dark/scale/accessibility and three-locale screenshots |
| migration/runtime | additive/idempotent migrate twice, worker/restart/replay, zero production traffic, cleanup and forward rollback |

## 13. Migration and rollback

Phase 8 metadata must be additive and install no production endpoint,
credential, mapping or sample business truth. Before retained integration
history, disposable environments may return to the task checkpoint. After
Inbox/Outbox/request/attempt/result/projection/reconciliation/audit history is
retained, rollback disables the affected endpoint/worker/adapter/UI route and
deploys a reviewed forward repair. It never deletes messages, changes an old
payload/hash/result or rewrites target observation to simulate success.

If an external call may have committed, rollback first marks the operation
uncertain and reconciles the target; it never blindly redispatches or performs
an unapproved compensating mutation.

## 14. Scoped holds and non-scope

- Production ERPNext/JCE, real credentials, production data, cross-database
  access, core patches and generic DocType writes are prohibited.
- The external ERP reconciliation bundle remains open. Exact custom fields,
  naming, states, target versions, service scopes and sandbox operations cannot
  be guessed.
- `DR-REC-009` holds the exact Trial Summary event/consumer contract.
- `INT-008/009/011/012/013/014` remain limited as stated in section 3 until
  their domain, provider, mapping or owner decision exists.
- No Phase 8 request may mutate Gate, Project, Work Item, Tooling, Trial or NPI
  state merely because a target message was queued or observed.

## 15. Automatic transition

P8-00 is documentation/trace work only and passes its exact-SHA ordinary CI
and Level 2 validation. The bounded P8-01 requirement/domain/existing-
capability audit also passes at exact controller SHA `046dba1` and ordinary CI
`31902540587`; its frozen plan is
`implementation/evidence/phase-8/p8-01-plan.md`. P8-01 checkpoint 1 passes at
exact final checkpoint `6d88175` and ordinary CI `31905949549`; complete
evidence is
`implementation/evidence/phase-8/p8-01-domain-metadata-checkpoint.md`.
P8-01 checkpoint 2 passes at exact product checkpoint `fd4fc6a` and ordinary
CI `31909152423`; complete evidence is
`implementation/evidence/phase-8/p8-01-repository-bff-checkpoint.md`.
P8-01 checkpoint 3 passes at exact final checkpoint `71bd18a` and ordinary CI
`31913915708`; complete evidence is
`implementation/evidence/phase-8/p8-01-product-ui-checkpoint.md`. P8-01 then
passes ordinary CI `31925662056` and exact-SHA Level 3 `31926087732` at final
product checkpoint `b938926`. The cumulative disposable Site proves seven
kinds/heads, twenty-five immutable observations, migrations twice, exact
replay/order/conflict/restart/IDOR/redaction/route recovery, Tooling consumer
closure, zero target write/production traffic and cleanup. Complete evidence
is `implementation/evidence/phase-8/p8-01-validation.md`.

Starting P8-02 audit/controller SHA `726115a` passes ordinary CI
`31927559261`. The bounded audit freezes exact raw-body HMAC, the five-minute
replay window and key rotation, closed Quotation/Sales Order submit events,
default-disabled non-production source profiles, durable landing before
acknowledgement, immutable event/hash and source-version conflict, leased
asynchronous processing/restart/reorder, server-owned intake mapping and
at-most-one Project draft in
`implementation/evidence/phase-8/p8-02-plan.md`.

P8-02 checkpoint 1 passes at exact product SHA `a040f21` and ordinary CI
`31930363720`. It proves exact raw-byte HMAC input and constant-time compare,
inclusive five-minute replay/key-rotation rules, two duplicate-key-free closed
events and canonical hashes, fail-closed non-production profile/policy, source
order/claim domains, immutable Inbox/source-binding metadata, direct
trilingual coverage and no route, row, worker, Project, secret or network
effect. Complete evidence is
`implementation/evidence/phase-8/p8-02-domain-metadata-checkpoint.md`.

P8-02 checkpoint 2 passes at exact product SHA `4c77c44` and ordinary CI
`31932869203`. It proves the fixed POST-only route, raw request bounds, TLS
server fact, default-disabled injected profile/secret boundary,
authentication-before-business-parse, atomic Inbox/source/audit landing,
commit-before-`202`, enqueue-after-commit, exact replay/conflict/order truth,
safe rollback/redaction and no Project/Gate/Work Item/network effect. Complete
evidence is
`implementation/evidence/phase-8/p8-02-ingress-landing-checkpoint.md`.

P8-02 checkpoint 3 passes at exact final product SHA `f3f7fba` and ordinary CI
`31935510653`. It proves bounded pending/expired claims, live-lease denial,
source locking/order/conflict, server actor/owner/template authority,
source-derived idempotency, existing Project draft aggregate reuse and atomic
binding/result/audit. Complete evidence is
`implementation/evidence/phase-8/p8-02-worker-project-checkpoint.md`.

P8-02 then passes ordinary CI `31944345420` and exact-SHA Level 3
`31944941030` at final product checkpoint `260ed2e`. The cumulative disposable
Site proves signed-route disable/recovery, bad/stale/key-rotation
authentication, durable acknowledgement, duplicate/conflict/reorder/
concurrency, claim restart, exactly one draft/binding/two Gate shells,
later-version no rewrite, stable cross-process replay, migrations twice,
redaction, zero target write/production traffic and cleanup. Complete evidence
is `implementation/evidence/phase-8/p8-02-validation.md`.

The P8-03 audit passes after transition checkpoint `97cba09` ordinary CI
`31946640640`; its frozen plan/task manifest at exact SHA `bf5e022` then
passes ordinary CI `31947838578`. The boundary is frozen in
`implementation/evidence/phase-8/p8-03-plan.md`. It preserves Phase 5 as
immutable combined Mock evidence and defines a separate Item-only operation
over one tenant + Project + exact engineering identity. All released
occurrences must agree on Item-master fields; MBOM facts remain excluded. The
request freezes exact source/profile/mapping/target versions and separates
approval, request, Outbox, attempt, transport, result observation and mapping
head. Mock and disposable synthetic proof have no formal code/mapping;
authoritative mapping requires an authenticated non-production Sandbox result
and exact compare-and-set. Timeout after the adapter boundary is uncertain and
cannot redispatch before future P8-07 reconciliation.

Checkpoint 1 passes at exact product SHA `1c1faa7` and ordinary CI
`31950411271`: `2,048` tracked Python tests, `933/933` frontend unit,
`426/426` E2E, `7,872` direct trilingual sources, complete history secret scan
and unchanged `119/119` visual matrix pass; controlled lanes correctly skip.
Complete evidence is
`implementation/evidence/phase-8/p8-03-domain-metadata-checkpoint.md`.

Checkpoint 2 passes at exact final product SHA `6e11a86` and ordinary CI
`31953799677`: `2,069` tracked Python tests, `933/933` frontend unit,
`426/426` E2E, `7,879` direct trilingual sources, complete history secret scan
and unchanged `119/119` visual matrix pass; controlled lanes correctly skip.
Complete evidence is
`implementation/evidence/phase-8/p8-03-command-outbox-checkpoint.md`.

Checkpoint 3 passes at exact product SHA `1a2c5be` and ordinary CI
`31956908978`: `2,094` tracked Python tests, `933/933` frontend unit,
`426/426` E2E, `7,879` direct trilingual sources, complete history secret scan
and unchanged `119/119` visual matrix pass; controlled lanes correctly skip.
Complete evidence is
`implementation/evidence/phase-8/p8-03-worker-adapter-result-checkpoint.md`.

Checkpoint 4 passes at exact product SHA
`5dbce209ea818a3ae929feb6decd40491175df5a` and ordinary CI `32376188274`:
repository `96448042317`, frontend `96448041734`, secret/Gitleaks
`96448041487` and visual `96448041169` pass at `122/122`; controlled lanes
correctly skip. Complete evidence is
`implementation/evidence/phase-8/p8-03-item-inspector-checkpoint.md`.

P8-03 then passes ordinary CI `32479492064` and final unchanged Level 3
`32480568505` at exact product checkpoint `c11d97c`. The cumulative Site proves
migrations twice, route and Project-first permission truth, request/Outbox/
attempt/result/mapping separation, stream conflicts, uncertain no-redispatch,
cross-process replay, strict legacy read-only/non-claimable behavior, zero Mock
mapping, zero production traffic and cleanup. Complete evidence is
`implementation/evidence/phase-8/p8-03-validation.md`.

`INT-003` is technically verified for the Item execution foundation while
production/Sandbox mapping remains held. Only the Item portion of `FR-DS-013`
is technically verified; MBOM and production/Sandbox mapping remain held, so
the whole requirement is not complete.

The bounded P8-04 audit passes and is frozen in
`implementation/evidence/phase-8/p8-04-plan.md`. It defines a separate
`publish_released_mbom` command over one exact released EBOM topology, requires
current exact authenticated P8-03 Item mappings for every Sandbox-bound node, classifies
direct-parent lines as assembly sources and leaves as component-only, freezes
Item/MBOM mapping-set expectations, preserves per-node partial/uncertain truth
and never submits or overwrites a submitted BOM.

Standing authority activates checkpoint 1 only after this frozen plan/task-
manifest exact SHA passes ordinary CI. Checkpoint 1 is pure domain, contract,
guarded Outbox/metadata, translations and focused tests; no route, persistent
command row, Outbox row, worker, adapter, mapping, UI or target effect is
active. Actual ERPNext method/field/UOM/alternate/effectivity/routing mapping,
submitted-BOM successor policy and Sandbox/production activation remain held.
`NFR-INT-001` full operations/DLQ/manual replay/reconciliation remains P8-07.
P8-05 through P8-09 and production ERPNext/JCE remain inactive.
