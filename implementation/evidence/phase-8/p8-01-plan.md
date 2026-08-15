# P8-01 Plan — Read-only ERP Master and Status Projections

Recorded: `2026-08-16`

Status: `FROZEN — AUDIT PASS; CHECKPOINT 1 AUTHORIZED`

Starting audit/controller checkpoint:
`046dba1c14e8f1f54d8db63ac383fbccc5b4d3d6`

Retained predecessor product checkpoint:
`31114021cf18cf5e32c22902de5150ed2922e7ba`

Primary requirements:

- `INT-001`, `INT-006`, `INT-007` and `INT-010`;
- `FR-PM-010` and `FR-TL-008`; and
- P8-01 projection foundation for `FR-TR-006` and `FR-NP-006`, consumed by
  the separately bounded P8-06 quality-linkage task.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is complete. Exact
audit/controller SHA `046dba1` passes ordinary pull-request CI `31902540587`:
repository `95055380476` proves `1,923` tracked Python tests; frontend
`95055380547` passes the complete unit/E2E, direct-trilingual, coverage,
build/install and zero-vulnerability boundaries; secret scan `95055380583`
passes; and fixed-Linux visual `95055380454` passes the unchanged `119/119`
matrix. Controlled preflight `95056611499` and cumulative runtime
`95056611724` correctly skip because the audit transition changes no product
or runtime truth.

Visual artifact `9251521099` has digest
`sha256:a899c710200b41814e4e7ad4efdf39cda3320461af54b4f58502ac8f1f7d5d34`;
Gitleaks artifact `9251475066` has digest
`sha256:94acc3acc31b6f786b3e91da514df2acc811c7dbcb60350f86f1d7e8119adaf0`.

The repository has reusable read-only consumer contracts but no durable
P8-01 observation boundary:

- `npi_integration.reliable` provides canonical event hashing, an in-memory
  Inbox duplicate/hash-conflict example and an in-memory Outbox state
  machine. It is not a cross-process observation repository or worker.
- `NPI Inbox Message` and `NPI Outbox Message` are guarded support DocTypes
  with minimal payload/state fields. Their controllers contain no signed
  landing, claim, ordering, retry, DLQ, replay or projection behavior.
- `contracts/integration-event.schema.json` contains only EBOM publish and
  Tool Asset request/result events. It has no Customer, Supplier, Item,
  procurement/cost, quality or Asset-status observation event.
- P6-04 already defines a closed ERP-owned Tooling procurement/cost union,
  exact Supplier/source-row/version fields, source-row-derived aggregation
  and an injected read-only reader. With no reader or no exact snapshot it
  returns `erp_projection_unavailable`.
- P6-06 already defines a closed Tool Asset available/unavailable union with
  zero-or-one physical-Set mapping, target version, Asset/location/shot/life/
  maintenance and bounded movement/repair/spare observations. Its workspace
  remains unavailable because no P8 reader is installed.
- Project controls support cost and quality health dimensions but accept no
  authenticated ERP actual projection. Their current health snapshots must
  not be rewritten by P8-01.
- Trial quality/review and NPI Readiness explicitly keep formal Quality
  Inspection/NCR/CAPA unavailable. Readiness already distinguishes failed
  quality from unavailable source truth and can block on either, but P8-01
  must not bypass its exact-source resolver or create a Gate effect.
- Project references can identify an ERP Customer/product/part/order in one
  authorized Project. Tooling Master/Set, Trial Round and Readiness contexts
  provide server-owned NPI scope anchors. There is no approved generic
  Supplier, Item, quality or Asset mapping that a browser may submit.
- `contracts/data-ownership.yaml` declares Customer, formal Item, Tooling
  procurement/cost, Quality Inspection and Tool Asset fields ERP-owned, but
  lacks a Supplier object and still marks Phase 8 connection/reconciliation
  fields unavailable.

P8-01 can proceed without a new business decision only as a normalized,
read-only observation and projection foundation plus bounded existing
consumer activation. It does not invent ERP custom fields, status mappings,
an EAC formula, a quality/Gate rule, an Asset execution result, production
host, service scope or webhook trust policy.

## 2. Frozen minimum vertical slice

P8-01 delivers this one complete technical path:

> enumerate an already authorized Project and exact server-owned NPI scope ->
> select one operation-specific projection reader -> Mock returns explicit
> unavailable while an explicitly configured non-production sandbox reader
> may return one closed ERP-owned observation -> canonicalize and hash the
> minimal allowlisted payload -> append one immutable global observation ->
> atomically compare its exact source ordering against one guarded
> Project/context head -> advance only when provably newer and retain
> duplicate, older, unavailable and conflict truth without overwriting the
> last confirmed observation -> compute server-owned availability and
> freshness without inventing missing target values -> expose only a
> Project-first read-only BFF projection -> feed confirmed exact snapshots to
> the existing Tooling cost/Asset readers and show bounded latest-status truth
> in the dense trilingual product surface -> prove duplicate/reorder/restart,
> migration, route-disable recovery, redaction and zero production traffic on
> a disposable Site

P8-01 owns normalization, immutable observation history, Project/context
heads, ordering, availability/freshness truth, adapter selection/configuration
safety and read-only projection transport. ERPNext continues to own every
projected business field. Existing Project, Tooling, Trial and Readiness
domains continue to own their NPI context and interpretations.

P8-01 creates no target write, formal mapping, execution request/result,
signed webhook, Inbox landing, Project draft, generic ERP query, retry/DLQ/
replay/reconciliation operation, Gate mutation, Readiness mutation, Trial
conclusion change, Tooling lifecycle change, external Trial Summary event or
JCE Core display behavior.

## 3. Closed projection catalog and ownership

Only the following operation-specific kinds are accepted. Unknown kinds fail
closed. Every payload uses exact source codes and remains language-neutral.

| Projection kind | Server-owned NPI scope | Minimal ERP-owned payload | P8-01 consumer |
| --- | --- | --- | --- |
| `customer_master` | exact ERP Customer Project reference | source Customer ID/version, code, display name, enabled/status code | Project projection list; no NPI edit |
| `supplier_master` | exact Tooling Master or procurement context | source Supplier ID/version, code, display name, enabled/status code | Project/Tooling projection list; no portal or master edit |
| `formal_item_master` | exact released/mapped engineering Item context | source Item ID/version, Item Code, Stock UOM, enabled/status code | projection list only until P8-03 owns formal mapping |
| `tooling_procurement_cost` | exact Project + Tooling Master | exact Supplier, PO/receipt/invoice/actual-cost row IDs and versions, posting date, raw cost-type code, currency and amount | existing P6-04 source-row-derived summaries |
| `project_cost` | exact Project | commitment, actual cost, labor-hours and expense source rows/versions by currency | Project projection list; budget and EAC remain separate/held |
| `formal_quality_status` | exact Project plus Trial/Readiness/product context | exact Quality Inspection, NCR or CAPA source ID/version, raw status/result code and observed time | projection list only; P8-06 owns linkage and interpretation |
| `tool_asset_status` | exact Project + physical Tooling Set | zero-or-one formal Asset ID/mapping version, target version, raw Asset/location/shot/life/maintenance and bounded history | existing P6-06 read-only Asset projection |

The contract adds Supplier ownership explicitly and changes only Phase 8
adapter-owned connection/observation fields from future-unavailable to the
new read-only observation owner. It does not transfer Customer, Supplier,
Item, procurement, finance, quality or Asset business ownership to NPI One.

Budget is NPI planning truth and ERP commitment/actual is target truth. P8-01
does not derive forecast-at-completion without an approved versioned formula.
Accordingly `FR-PM-010` remains technically partial after P8-01 if no later
approved EAC policy exists. A quality failure remains an ERP result code; only
P8-06 or an existing versioned NPI policy may interpret it as a specific
blocker. Raw status/result/cost-type codes are retained and displayed as codes
when no approved mapping exists.

## 4. Observation identity, ordering and head rules

### 4.1 Immutable global observation

Each observation freezes:

- NPI observation UUID and schema version;
- source event/refresh UUID and operation-specific event type/version;
- `ERPNEXT` source and `NPI_ONE` target technical codes;
- adapter mode (`mock`, `sandbox` or disposable `synthetic` proof), adapter
  contract version and non-secret source-environment code;
- source object type/ID, opaque source version and exact source modified time;
- canonical allowlisted payload and SHA-256 hash;
- server receive time, trace/correlation identity and sensitivity class;
- server-resolved tenant, Project, scope kind/UUID and projection kind; and
- final application disposition: `applied_current`, `unavailable_current`,
  `superseded`, `duplicate_exact`, `conflicted` or `synthetic_retained`.

The browser cannot create an observation or supply tenant, Project, NPI
scope, source identity/version/time, payload, hash, adapter mode, freshness,
application disposition or authority. The internal reader result is parsed by
the exact projection-kind contract before any row or audit is written.

### 4.2 Project/context head

One guarded head exists for exact tenant + Project + scope kind/UUID +
projection kind + source object identity. It holds the last confirmed current
observation, latest refresh/unavailable observation, optimistic version and
freshness-policy reference. It is a read model, not an editable copy of ERP
business fields.

The worker locks the exact head before comparison. A newer source modified
time may advance it. An older time is retained as `superseded`. Equal source
time advances only for an exact same source version and payload replay, which
is a duplicate and produces no new business effect. Equal time with a
different source version or hash is `conflicted` and never advances. Opaque
source versions are never compared lexically or numerically unless a future
operation-specific contract explicitly declares that ordering mode.

The same source event ID plus the same payload hash replays its exact result.
The same event ID with a different hash is a visible conflict. A process
restart after observation insert but before head update re-enters the same
locked comparison and cannot create a second logical effect. Observation and
head/audit changes occur in one transaction where possible; controlled crash
tests prove deterministic recovery at each boundary.

### 4.3 Availability and freshness

Availability and freshness are separate:

- `available` requires one authenticated, confirmed sandbox observation that
  remains the exact current head;
- `unavailable` includes no mapping, no configured provider, rejected
  configuration, source unavailable or no confirmed observation;
- `synthetic` is visibly non-authoritative test truth and is never converted
  to an available formal projection for a business consumer;
- `fresh`, `stale` and `unknown` are server-derived from the exact observation
  and a versioned operation-specific maximum-age policy; and
- no installed freshness policy yields `unknown`, never an invented fresh
  claim. An unavailable refresh preserves the last confirmed snapshot only as
  last-known truth and cannot hide the unavailable/stale state.

P8-01 installs no production freshness thresholds. Disposable runtime may
install an explicitly synthetic policy solely for deterministic boundary
proof and removes it with the Site.

## 5. Event and adapter boundary

The event Schema adds seven operation-specific ERP observation types matching
the catalog. Each uses a closed version-1 payload and requires target system,
payload hash, service actor, exact source object/version/modified time and
server-correlation data. Defining these events does not activate P8-02's
public webhook endpoint or trust an unsigned caller.

The adapter registry exposes seven named read methods, not `read_doc`, SQL,
caller-selected URLs or arbitrary DocType CRUD. Queries contain only the
server-resolved source identity and NPI context necessary for that operation.

- `mock` is the default. It performs no network call and returns explicit
  provider unavailable. It emits no formal ID, target version or `available`
  state.
- A deterministic fake exists only in tests/disposable runtime. Its records
  carry `synthetic_retained`, non-formal IDs and non-authoritative output;
  business consumers continue to see unavailable.
- `sandbox` requires explicit enablement, HTTPS, an exact operation allowlist,
  a separately supplied secret reference, a non-production environment
  attestation and an allowlisted hostname. Empty, loopback ambiguity, IP
  literal, redirect, user-info, insecure scheme, known production host and
  any fallback host are rejected before transport.
- P8-01 freezes the sandbox protocol/configuration seam but does not implement
  a live ERP field mapper or send a network request while the current ERP
  customization/sandbox reconciliation package is absent. No test may use
  production as a fallback.

Credentials, Authorization headers, cookies, raw responses, full invoices,
bank/tax/contact details, unrestricted Customer/Supplier data and target error
bodies are excluded from payload, persistence, audit, logs and BFF responses.

## 6. Authorization, BFF and consumer boundaries

- Every public query authenticates before parsing optional filters, resolves
  and authorizes the Project before any source ID, Tooling, Trial, Item,
  quality or Asset identity, and revalidates exact tenant/Project containment
  for each returned head.
- The only generic public operation is a bounded read-only Project collection:
  `GET /api/npi/v1/projects/{projectId}/erp-projections`. It may filter by one
  allowlisted projection kind but accepts no external/source object ID.
- Responses are closed, bounded and sorted. They expose projection kind,
  NPI context, availability/freshness, received/observed time, safe source
  version/reference, payload hash and an allowlisted typed value projection.
  They expose `edit: false` and no create/update/delete/refresh action.
- Same-tenant internal Project viewers may read the bounded Project
  collection. External/portal actors receive an explicit unavailable/redacted
  result and no new cost, Supplier, quality or Asset detail authority.
- Existing Tooling manufacturing and acceptance routes remain the detailed
  cost and Asset product surfaces. Their repositories receive injected P8-01
  readers; only a confirmed exact current sandbox observation becomes their
  existing `available` type. Missing, stale-policy-unknown, synthetic,
  conflicted, cross-Project or unavailable truth remains unavailable.
- Project health, Trial comparison/conclusion, Readiness evidence/blockers and
  Gate state are not mutated. P8-06 may later consume exact formal-quality
  observations only through its separately frozen resolver/policy boundary.
- Direct Frappe handlers repeat authentication, Project-first authorization,
  input closure and response validation. The browser never receives adapter
  configuration, secret references or raw target errors and never calls ERP.

## 7. Product and localization boundary

P8-01 adds one dense read-only ERP Projections section to the existing Project
controls workspace and activates only the already designed cost/Asset panels
when their exact confirmed readers are available. It uses the fixed industrial
App Shell, table/inspector layout, square geometry, one small primary context
action at most and text/icon states without a colorful card wall.

The surface covers loading, empty, no permission, internal read-only,
available, last-known-but-unavailable, stale, unknown freshness, synthetic,
conflict and transport failure. It never labels a queued refresh or successful
HTTP call as ERP-confirmed truth. Cost rows show currency and raw source codes;
quality rows distinguish Inspection/NCR/CAPA and never display NPI evidence as
formal approval.

All new user-visible source strings are literal English through the local
Frappe-backed `t()` adapter with direct `zh` and `zh-TW` translations. Mixed
ordinary language, translated enum/contract values and missing-production
fallback are prohibited. Fixed-Linux English/Simplified-Chinese/Traditional-
Chinese evidence covers normal, unavailable/stale and conflict/read-only
states plus Tooling cost/Asset activation.

## 8. Additive metadata and transaction boundary

Checkpoint 1 may add only these guarded support records:

- `NPI ERP Projection Observation`: append-only immutable observation,
  canonical payload/hash, scope and final disposition; and
- `NPI ERP Projection Head`: guarded current/refresh pointers, exact stream
  identity, optimistic version and freshness-policy reference.

Both records deny generic business-role create/write/delete. Only narrow
internal flags used by the P8 projection repository may insert an observation
or advance a head. System Manager support read is retained, but Desk is not a
product path. Scalar identity/version/time/hash fields must exactly match the
replayed canonical JSON snapshot.

The integration repository orders one refresh as: resolve/authorize exact NPI
scope -> validate adapter result -> lock or create exact head -> reserve exact
event/hash identity -> append immutable observation -> conditionally advance
head -> append structural audit -> seal processing result. Any failure rolls
back the complete transaction. It never commits independently, updates an ERP-
owned field, inserts an Inbox/Outbox row or calls a target from a business
transaction.

## 9. Checkpoints and changed-files-to-tests map

### Checkpoint 1 — pure projection domains, contracts and guarded metadata

- Add closed seven-kind observation domains, exact ordering/freshness state,
  operation-specific event payloads, ownership corrections, OpenAPI read
  schemas, adapter configuration validation and two guarded additive DocTypes.
- Tests: exact/extra/missing/type/size boundaries; canonical hash; all seven
  owner/field allowlists; newer/older/equal duplicate/equal conflict; unknown
  freshness; Mock no formal truth; sandbox scheme/host/redirect/secret/
  operation rejection; metadata guards; no generic CRUD; no network import or
  production literal; direct translation symmetry.
- No route, repository write, scheduler, business row, UI or external call is
  activated. Exact-SHA ordinary CI must pass before checkpoint 2.

### Checkpoint 2 — durable repository, internal refresh and read-only BFF

- Implement Project/context-first scope enumeration, immutable observation/
  guarded head transaction, exact replay/conflict/restart handling, seven
  named adapter-reader seams, bounded internal refresh worker, Project
  projection collection and injected Tooling cost/Asset readers.
- Tests: auth-before-filter; Project-before-secondary-ID with real/absent IDOR;
  tenant/current-membership/external redaction; exact event replay and hash
  conflict; reordered observation; unavailable refresh preserving visible
  last-known truth; restart at insert/head/audit boundaries; optimistic lock;
  no Project/health/Trial/Readiness/Gate/Tooling lifecycle/ERP mutation;
  Mock/synthetic never available; sandbox configuration fail-closed; bounded
  query and typed consumer parsing.
- The worker has no production configuration and performs no live network
  request. P8-02 webhook/Inbox and P8-07 replay/operations remain inactive.
  Exact-SHA ordinary CI must pass before checkpoint 3.

### Checkpoint 3 — dense live trilingual projection truth

- Add the strict frontend data source and Project projection table/inspector;
  surface confirmed cost/Asset truth only through existing Tooling workspaces.
- Tests: strict closed response; state/freshness combinations; loading/empty/
  denied/read-only/unavailable/stale/unknown/synthetic/conflict/error; no edit
  path; raw-error/secret/source-substitution denial; keyboard/focus/Axe;
  direct English/`zh`/`zh-TW`; mixed-language and governed visuals.
- Exact-SHA ordinary CI passes before the final P8-01 Level 3 Gate.

### Final P8-01 Level 3 Gate

- Run complete repository/frontend/security/visual verification and cumulative
  disposable-Site runtime with migrations twice.
- Runtime proves all seven closed kinds, one confirmed synthetic sandbox-style
  observation path kept visibly non-production, Mock unavailable, cost/Asset
  consumer closure, exact duplicate/reorder/conflict/restart/IDOR/redaction,
  route disable/re-enable, no target write, zero production integration
  traffic, complete cleanup and no retained fixture/default configuration.
- Use the `release-gate` review because shared event/ownership/OpenAPI/Schema/
  integration infrastructure changes are Level 3. P8-01 may advance to P8-02
  only after exact final SHA ordinary CI and Level 3 both pass.

| Changed boundary | Minimum affected evidence |
| --- | --- |
| projection domain/event/ownership | JSON Schema/OpenAPI closure; owner/editability; canonical hash; all-kind payload; ordering/freshness and no inferred value tests |
| adapter configuration | Mock no-network/no-success; sandbox HTTPS/allowlist/production rejection; secret/redaction and no fallback tests |
| DocTypes/repository/worker | controller guards; migrate twice; atomic insert/head/audit; duplicate/reorder/conflict/restart/cross-process tests |
| BFF/permissions | auth-before-input; Project-first IDOR; tenant/current membership; external redaction; bounded response and no generic mutation tests |
| Tooling consumers | P6-04 procurement/cost and P6-06 acceptance/Asset regressions; exact current/unavailable/synthetic/stale/conflict behavior |
| Project product UI/translations | strict data-source/unit/Axe; direct three-language scan; affected E2E and fixed-Linux visuals |
| shared infrastructure/final trace | full repository/frontend/history-secret/visual matrix; cumulative disposable runtime; release review and Requirement reconciliation |

## 10. Expected changed paths

| Change | Expected paths |
| --- | --- |
| pure integration projection domain/configuration | `apps/npi_integration/npi_integration/projections/**` |
| guarded metadata/controllers | `apps/npi_integration/npi_integration/npi_integration/doctype/npi_erp_projection_observation/**`; `.../npi_erp_projection_head/**` |
| internal worker/reader/API registration | `apps/npi_integration/npi_integration/hooks.py`; projection repository/worker/API modules |
| closed contracts and ownership | `contracts/integration-event.schema.json`; `contracts/data-ownership.yaml`; `contracts/npi-api.openapi.yaml` |
| bounded existing consumers/BFF | `apps/npi_core/npi_core/bff.py`; Project controls and Tooling repository/API modules only as required by the frozen reader boundary |
| live product/data source | existing Project controls and Tooling frontend modules, focused tests and `frontend/src/styles/app.css` |
| localization | `apps/npi_core/npi_core/translations/zh.csv`; `zh-TW.csv`; generated translation catalog |
| controlled proof | focused `tests/test_phase8_projection_*.py`; frontend unit/E2E/visual proof; runtime verifier and exact governed snapshots |
| controller/trace/evidence | P8-01 plan/checkpoints/validation and current controller/trace/risk/status files |

A required change to authentication, Project membership, existing Tooling
business ownership, Trial/Readiness/Gate policy, generic Inbox/Outbox/replay or
target execution reopens the audit instead of silently expanding these paths.

## 11. Migration, security and rollback

Metadata is additive and creates no default observation, head, provider,
freshness policy, host, credential, mapping or business value. The disposable
Site migrates twice. No patch backfills historical ERP truth or marks an NPI
reference confirmed.

Before retained observation history, rollback may return to the exact P8-00
product boundary plus this audit evidence and remove fresh disposable schema.
After any observation/head/audit history exists, rollback disables only the
P8-01 refresh worker, Project projection route and injected readers, retains
all observations/conflicts/heads/audits and deploys a reviewed forward repair.
It never deletes an observation, rewrites a source version/hash, moves a head
backward, changes unavailable to available or compensates in ERPNext.

Route disable must make product consumers explicitly unavailable, not retain
an unlabeled cached value. If any future external call may have occurred,
disable transport first, preserve the attempt as uncertain and defer target
reconciliation to the approved operation boundary; never redispatch during
rollback.

## 12. Explicit holds and non-scope

- Production ERPNext/JCE endpoint, credential, data, traffic, webhook,
  reconciliation, mutation or compensating transaction remains prohibited.
- Current ERP custom fields, DocType status/value mappings, service scopes,
  sandbox host and credentials remain external holds. P8-01 proves the seam
  and synthetic/disposable mechanics without guessing them.
- No production freshness threshold, cost-type translation, EAC formula,
  quality-failure-to-Gate rule, CAPA workflow or formal Item/Asset mapping is
  installed.
- P8-02 owns signature/replay-window verification, durable public Inbox
  landing and exact submitted-source Project draft behavior.
- P8-03/04/05 own Item, MBOM and Tool Asset execution; P8-06 owns formal
  quality linkage/interpretation; P8-07 owns operations/DLQ/replay/
  reconciliation; P8-08 owns the held Trial Summary projection seam; P8-09
  owns approved JCE Core presentation.
- `INT-008/009/011/012/013/014`, `DR-REC-009`, production UAT and external
  reconciliation facts retain their existing scoped holds.

## 13. Automatic transition

The audit passes and authorizes only checkpoint 1. Standing continuous-
delivery authority permits automatic progression after each exact-SHA
ordinary CI and affected Gate passes. P8-01 completes only after the final
Level 3 Gate. Only then may the controller activate P8-02. No checkpoint
authorizes production ERPNext contact.
