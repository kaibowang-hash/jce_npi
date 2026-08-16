# P8-03 Plan — Operation-Specific ERPNext Item Publish Execution

Recorded: `2026-08-16`

Status: `FROZEN — AUDIT PASS; CHECKPOINT 1 AWAITS EXACT-SHA ORDINARY CI`

Starting audit/controller checkpoint:
`97cba0924a98c36d7302d863a8e88733926df167`

Retained predecessor product checkpoint:
`260ed2ef865180f33edfca0e8fe1daf4a0a4e771`

Primary requirements:

- `INT-003`; and
- the Item portion of `FR-DS-013`.

`NFR-INT-001` contributes only the durable Outbox, idempotent attempt and
restart-safety foundation needed by this operation. Generic operations, DLQ,
manual replay, corrected-command authorization and reconciliation remain
allocated to P8-07. MBOM execution remains P8-04.

## 1. Audit decision

The bounded requirement, domain, existing-capability, ownership and security
audit passes. The P8-03 audit transition at exact SHA `97cba09` passes
ordinary pull-request CI `31946640640`: repository `95163586941`, frontend
`95163586879`, secret `95163586822` and unchanged `119/119` fixed-Linux visual
`95163586888` all pass. Controlled lanes correctly skip because that
transition and this audit add no product or runtime behavior.

The repository has valuable release and integration foundations, but it does
not yet have an executable Item boundary:

- Phase 5 freezes one immutable, Project-scoped, Mock-only combined
  `publish_released_ebom_item_mbom` request over an exact released EBOM,
  release event, approval evidence, revision snapshot and per-line hashes. Its
  controllers intentionally forbid non-Mock target mode, dispatch, attempts,
  target identifiers and success. Those records are retained source evidence,
  not execution rows, and P8-03 will not rewrite or broaden their history.
- An EBOM line has a stable line UUID and an opaque `engineering_item_id`.
  Only line UUID/key uniqueness is enforced; the same engineering identity may
  occur on several BOM lines. Quantity, hierarchy, alternates and effectivity
  are MBOM facts, not Item-master fields. One line occurrence therefore cannot
  silently become the formal Item identity or payload.
- The Phase 5 publish policy is Project-scoped and authorizes creation of the
  combined Mock evidence. It does not authorize a target write or provide a
  Sandbox endpoint. An execution profile must be separate, server-owned,
  immutable in each request and absent by default.
- The Phase 6 `NPI Engineering Part` and document-baseline domains have no
  audited structural link to an EBOM `engineering_item_id` and no replacement
  Item-release authority. P8-03 cannot invent such a relationship. Its only
  accepted source is the exact released EBOM evidence already frozen in a
  valid Phase 5 publish request and its exact nodes.
- `NPI Outbox Message` is a minimal Phase 2 support projection. It lacks a
  guarded versioned envelope, tenant/Project/operation/request binding, claim
  lease, attempt provenance and uncertain result. It can be strengthened
  additively for version-1 operation messages; legacy rows are never promoted
  to authenticated/executable work.
- There is no Item execution request, command idempotency record, attempt,
  result observation or current mapping head. Existing Phase 5 per-node
  mapping/result records are immutable Mock validation evidence and cannot be
  reused as mutable execution state.
- P8-01 proves a strict Mock/synthetic/Sandbox configuration shape and
  non-production host/secret allowlisting; P8-02 proves transactionally landed
  messages, bounded claims, restart recovery, server actor resolution and safe
  diagnostics. P8-03 may reuse those patterns, not their operation data.
- Existing event/OpenAPI contracts describe the combined future Item+MBOM
  operation. P8-03 requires new Item-only contracts and must not relabel those
  old events as observed execution.
- No approved production Item naming series, Item Group, stock UOM mapping,
  engineering-field mapping, target method, service scope, endpoint,
  credential or sanitized Sandbox response exists. This holds production
  activation and real-Sandbox confirmation, but does not block a fail-closed
  Mock/default-disabled, adapter-ready technical foundation.

P8-03 therefore delivers an Item-only technical execution foundation. It
proves immutable command/outbox/attempt/result truth and restart safety on a
disposable Site with Mock and network-free synthetic adapters. It exposes a
strict non-production Sandbox adapter seam, but installs no adapter/profile,
does not contact any target, and does not claim a formal Item mapping without
an authenticated authoritative Sandbox result.

## 2. Frozen minimum vertical slice

P8-03 delivers exactly this path:

> authorize one Project before every secondary identity -> resolve one exact
> immutable Phase 5 publish request and selected source node -> revalidate its
> published policy, released EBOM/revision/lifecycle/release evidence and
> hashes -> group every occurrence of the same exact Project-scoped
> `engineering_item_id` -> reject conflicting Item-master content -> derive
> one canonical Item source snapshot/hash and current mapping head under lock
> -> resolve a separate server-owned Item execution profile -> create or
> replay one immutable operation-specific request and command idempotency row
> -> in the same transaction append one version-1 Item Outbox message and
> audit -> commit before enqueue -> claim the exact message with a bounded
> lease -> freeze one immutable attempt before any adapter invocation -> call
> only the configured closed `publish_released_item` adapter -> classify the
> observed response independently of HTTP acceptance -> append an immutable
> result/attempt outcome -> advance a formal mapping head only from an exact
> authenticated authoritative Sandbox success -> retain timeout-after-
> possible-commit as uncertain and prohibit redispatch -> expose request,
> attempt and mapping truth in the existing EBOM publish workspace

One execution request represents one Project-scoped engineering identity, not
one BOM occurrence and not the whole EBOM. The response includes all exact
source occurrence IDs/hashes so every EBOM node can resolve the same retained
Item result without duplicating target work. P8-04 later consumes exact current
Item mappings for MBOM nodes; it never changes this Item request.

No production network call, production profile, target credential, target
row, cross-database access or generic target CRUD exists in this task.

## 3. Source identity, grouping and immutable payload

The Item source stream key is a SHA-256 over this closed canonical identity:

- exact Site tenant ID;
- exact NPI Project global ID; and
- exact case-preserved `engineering_item_id` from the released EBOM.

This is explicitly a Project-scoped engineering identity because the audited
domain provides no approved cross-Project namespace. It does not claim global
part-number equivalence. A later cross-Project master identity would be a
Class-B domain change and requires a separate migration/ADR; P8-03 does not
guess it.

The command accepts only:

- Project ID in the fixed route;
- exact Phase 5 publish-request ID;
- one exact publish-node ID used to select the engineering identity;
- expected current mapping-head version (`0` when no head exists);
- expected request version for a read/command conflict where applicable;
- bounded idempotency key; and
- an explicit acknowledgement of the displayed immutable source/profile
  impact.

The caller cannot supply tenant, actor, operation, target mode, target method,
DocType, endpoint, Item Code, target version, formal success, payload hash,
mapping authority, line content or occurrence membership.

The server loads all nodes in the exact Phase 5 request with the selected
`engineering_item_id`. It derives Item-master content only from:

- `engineeringItemId`;
- engineering description;
- engineering UOM as a source value, never silently as ERP stock UOM; and
- closed engineering attributes.

Hierarchy, parent/line keys, quantity, alternates and effectivity remain exact
source evidence for later MBOM work but are excluded from the Item mutation
payload. If repeated occurrences disagree on description, engineering UOM or
attributes, the command returns `SOURCE_ENGINEERING_ITEM_CONFLICT` and creates
no request/outbox. No arbitrary first occurrence wins.

The immutable request freezes:

- execution API/operation/profile ID, version, mode and profile snapshot hash;
- tenant, Project and source-stream key;
- exact Phase 5 request ID/payload hash and exact publish policy reference;
- exact released EBOM/root/revision/lifecycle/release event IDs, versions and
  hashes plus approval evidence IDs;
- selected node and sorted complete occurrence node/line IDs and hashes;
- canonical Item source snapshot and source hash;
- mapping-head expected version;
- expected target version, which is `null` only for an unmapped create and the
  exact current observed target version for an update;
- server-derived intent (`create_item` or
  `update_item_engineering_fields`);
- actor, request ID, trace ID and actor-bound idempotency-key hash; and
- creation time and initial dispatch disposition.

Any changed released revision, occurrence set, content, mapping version,
target version, profile or actor requires a new request/idempotency key. An old
request remains append-only evidence.

## 4. Ownership and mapping authority

ERPNext owns formal Item Code, Item master lifecycle/state, stock UOM, Item
Group, naming and target version. NPI One owns engineering source/release,
approval evidence, execution request, Outbox, attempt, result observation,
audit and the read-only association to an observed ERP-owned Item.

A formal mapping is a versioned observation, not an editable field on the
EBOM line or Phase 5 request. It consists of:

- source-stream key and mapping version;
- formal Item Code returned by the target;
- opaque exact target version returned by the target;
- request, Outbox event and attempt IDs;
- adapter profile ID/version and non-production environment code;
- target result snapshot/hash and target observation time;
- previous mapping version/hash when updating; and
- authoritative observation state.

Only a closed Sandbox result received through the configured adapter for the
exact claimed attempt, with matching operation, idempotency key, source hash,
expected target version and response authenticity evidence, may create an
authoritative observation and advance the locked mapping head. HTTP 2xx,
queue acceptance, a response that merely echoes caller input, Mock, synthetic
proof, locally generated Item Code, timeout or an unverified body cannot.

Mapping-head compare-and-set requires the request's exact expected mapping
version and expected target version. A late authoritative result that no
longer matches the locked head is retained as `observed_conflict`; it does not
overwrite the current mapping. Published mappings are never edited to change
an Item Code. A different formal code requires an explicit future superseding
mapping decision, outside P8-03 automatic retry authority.

## 5. Execution profile and adapter safety

P8-03 installs no Item execution profile, endpoint, credential, method or
default business mapping. Missing configuration makes execution explicitly
unavailable. One immutable parsed profile contains only server-owned facts:

- profile ID/version and exact tenant/Project scope;
- target mode: `mock`, `synthetic` or `sandbox`;
- exact operation allowlist containing only `publish_released_item`;
- permitted internal requester users and worker service actor;
- fixed adapter resolver path and contract version;
- non-production environment code/attestation;
- for Sandbox only, exact HTTPS origin hostname allowlist, opaque secret
  reference, fixed timeouts, no redirects and response-authentication mode;
  and
- explicit closed Item field/UOM/naming policy version when required by the
  adapter, never caller-provided defaults.

Validation rejects production/live labels and hosts, IP literals, localhost,
userinfo, path/query/fragment origins, redirects, raw-secret-shaped values,
unknown operations, broad methods/DocTypes, tenant/Project mismatch, external
actors and ambiguous resolvers. Credentials are resolved separately into
memory and never persisted in request, Outbox, attempt, audit, response or log.

Modes are truthful:

- `mock`: validate and retain one request with state `validated_mock`; create
  no Outbox, attempt, mapping or target success and make no network call.
- `synthetic`: allowed only when an explicit disposable-test marker and
  injected network-free adapter are present. It may exercise Outbox/claim/
  attempt/result mechanics, but the terminal state is
  `synthetic_verified`, carries no formal Item Code/target version and cannot
  create or advance a mapping.
- `sandbox`: disabled unless an exact separately approved non-production
  profile and adapter resolver exist. It may enqueue and call only the closed
  operation. No such profile is installed or used by P8-03 validation.
- production: unsupported and rejected in domain/configuration before enqueue
  or adapter resolution.

The repository does not invent an ERPNext whitelisted method without the
missing reconciliation facts. The adapter protocol is closed and
operation-specific; a later approved Sandbox adapter can implement the exact
method/field mapping without altering request, state or ownership contracts.

## 6. Request, Outbox, attempt and result states

Request states are closed:

- `validated_mock` — immutable Mock validation; no dispatch authority;
- `queued` — durable request plus Outbox committed, worker not yet claimed;
- `processing` — exact Outbox claim and attempt are durable;
- `synthetic_verified` — disposable non-authoritative proof completed;
- `succeeded` — authoritative Sandbox target result observed and mapping
  compare-and-set succeeded;
- `failed_retryable` — classified safe pre-commit/target failure retained for
  later P8-07 policy; P8-03 does not expose manual replay;
- `failed_final` — closed source, profile, permission, business validation or
  response-contract failure;
- `uncertain_after_timeout` — target may have committed; reconciliation is
  required and redispatch is prohibited; and
- `mapping_conflict` — authoritative result retained but current mapping head
  did not match the request's exact expectation.

Outbox version-1 Item rows use `pending`, `processing`, `succeeded`,
`failed_retryable`, `failed_final` or `uncertain`. Mutable fields are limited
to guarded lease, attempt count, safe error/disposition and terminal result
references. The immutable envelope binds exact request, event, tenant,
Project, operation, profile, source/mapping versions, payload/hash, actor,
trace and idempotency.

Each adapter invocation gets a new immutable attempt number and random claim
token but the same immutable target idempotency key derived server-side from
the request ID and source hash. An attempt records start/finish time, request
snapshot/hash, configured timeouts, transport disposition, safe target status,
response/body hash, result classification, reconciliation requirement and
safe error code. Raw credentials, authorization headers, arbitrary response
bodies and tracebacks are never stored.

P8-03 proves only initial dispatch and expired-lease recovery. A recovered
worker first reloads durable request/attempt truth. It may resume local
finalization of a fully retained response, but it never sends a second target
request after an attempt reached the adapter boundary unless an exact future
reconciliation decision authorizes it. P8-07 owns that decision and operator
surface.

## 7. API, permissions and UI

The fixed Project-first BFF routes are:

- `GET /api/npi/v1/projects/{projectId}/item-publish-requests` with bounded
  exact source filters;
- `POST /api/npi/v1/projects/{projectId}/item-publish-requests`; and
- `GET /api/npi/v1/projects/{projectId}/item-publish-requests/{requestId}`.

No generic Frappe method/DocType route is a product API. Every route validates
canonical UUIDs, authentic session, CSRF for POST, tenant membership and
Project view/execute authority before loading publish request/node, mapping or
target-derived identifiers. Missing, foreign and unauthorized secondary IDs
return the same internal unavailable response. List bounds, exact containment
and response redaction are server-side.

Execution requires both Project operation authority and membership in the
exact frozen Item execution profile requester list. Worker authority is an
enabled internal service actor from the profile, resolved server-side. Browser
roles, hidden controls or caller-supplied actor/tenant never substitute for
server checks. Support DocTypes remain System-Manager read-only and all writes
use narrow controlled scopes; direct create/update/delete is denied.

The existing dense EBOM publish workspace gains an Item execution inspector
for the selected Phase 5 request/node. It shows exact source identity/hash,
occurrence count, intent, expected mapping/target version, profile/mode,
request state, attempt history, uncertainty/reconciliation requirement and
observed mapping authority. It never labels queued/processing/HTTP accepted/
synthetic/Mock as success and never displays a formal Item Code unless the
server response says the current mapping is authoritative and the user may
view it.

The one primary action is an explicit Item publish request with impact summary
and acknowledgement. It is disabled with a direct reason for Mock validation,
missing profile, permission denial, conflict, in-flight request, uncertain
state or stale mapping expectation. No retry/reconcile button is added. All
new source copy is literal English through `t()`/Frappe `_()` with complete
direct `zh` and `zh-TW` translations, keyboard/focus/accessibility coverage
and restrained industrial status treatment.

## 8. Events, audit and response semantics

The additive event contracts are Item-only:

- `npi.item_publish_request.ready`, version `1`, NPI One to ERPNext; and
- `erpnext.item_publish_result.observed`, version `1`, ERPNext to NPI One.

The request event contains only the frozen operation/profile/source/mapping
contract required by the adapter. The result event/observation binds the exact
request/event/attempt/idempotency/source hash and carries the closed
classification plus authenticated target result fields. Neither event contains
MBOM nodes/IDs, a generic DocType/method/endpoint, secrets, target credentials
or caller-selected success.

An API `201` means the immutable local request was committed; `200` on replay
means the same actor/idempotency/payload returned the original request. It does
not mean target acceptance or Item success. A Sandbox `succeeded` state means
only that an authoritative result passed the complete contract and mapping
compare-and-set. It does not make NPI One the Item master.

Every request creation/replay/conflict, Outbox append/claim/recovery, attempt
start/classification, uncertain outcome, authoritative observation, mapping
advance/conflict and final failure creates a structural `NPI Audit Event` in
the same transaction as the state it describes. Audits contain stable codes,
IDs, hashes, versions and trace IDs, never raw secret/headers/body or private
stack details.

## 9. Fault matrix

| Fault | Request/worker result | Durable truth | Forbidden effect |
| --- | --- | --- | --- |
| Project absent/foreign/unauthorized | unavailable | safe trace only | no secondary lookup/leak |
| exact Phase 5 request/node unavailable or hash-invalid | `422`/failed final | safe source error/audit | no repaired/guessed source |
| repeated identity has divergent Item fields | `SOURCE_ENGINEERING_ITEM_CONFLICT` | conflict evidence | no arbitrary occurrence chosen |
| release/approval no longer exact | conflict/final | exact old evidence retained | no latest-source substitution |
| profile absent/invalid/production | unavailable/final | safe profile code | no fallback/network |
| Mock request | `validated_mock` | immutable request/audit | no Outbox/attempt/code/success |
| same actor/key/same payload | replay original | one request/outbox | no duplicate dispatch |
| same actor/key/different payload | `409` | original plus conflict audit | no overwrite/new outbox |
| stale mapping-head expectation | `409` | current head retained | no old-target update |
| first synthetic request | queued then `synthetic_verified` | request/outbox/attempt/result | no formal Item mapping/code |
| crash before command commit | rollback | no partial rows | no enqueue |
| crash after commit before enqueue | pending recoverable Outbox | request retained | no lost request |
| live Outbox lease | not claimed | current attempt retained | no concurrent call |
| expired lease before adapter boundary | reclaimed | incremented attempt/audit | no duplicate request row |
| crash/timeout after adapter boundary | `uncertain_after_timeout` | attempt/hash/reconcile-required | no redispatch or success |
| HTTP 2xx with malformed/mismatched body | failed final/uncertain by boundary | safe response hash/code | no mapping from status alone |
| rate limit/5xx before possible commit | failed retryable | retry classification retained | no P8-03 manual replay |
| target business validation | failed final | safe target code/hash | no local source rewrite |
| authoritative success/current expectation | succeeded | observation + advanced mapping head | no dual-master edit |
| authoritative late result/stale head | mapping conflict | result retained | no head overwrite |
| commit error while sealing result | uncertain/recover from retained attempt | claim/result evidence retained | no optimistic success |
| direct DocType mutation/delete | denied | immutable history retained | no support-path bypass |

## 10. Checkpoints and changed-files-to-tests map

### Checkpoint 1 — pure Item execution domains, contracts and guarded metadata

- Add closed source grouping/hash, operation/profile configuration, request,
  mapping, attempt/result, fault classification and claim domains; add
  Item-only event/OpenAPI/ownership contracts; harden version-1 Outbox metadata
  and add guarded Item request/idempotency/attempt/result/mapping head/
  observation DocTypes with direct translations.
- Tests: exact/duplicate/divergent occurrence grouping; Item-versus-MBOM field
  boundary; request/source/profile/idempotency hashes; create/update target
  version rules; state/fault matrix; Mock/synthetic/Sandbox/production config;
  host/secret/redirect/operation rejection; authoritative versus synthetic
  result; mapping compare-and-set; metadata insert/update/delete guards;
  legacy Outbox non-promotion; Schema/OpenAPI/ownership and translation
  symmetry.
- No BFF route, repository request row, Outbox row, worker, adapter call,
  mapping or UI behavior is activated. Exact-SHA ordinary CI must pass before
  checkpoint 2.

### Checkpoint 2 — Project-first command and atomic durable Outbox

- Add fixed list/detail/create BFF routes, server Project/source/profile/
  permission resolution, occurrence grouping, current mapping lock,
  actor-bound command idempotency, immutable request, version-1 Item Outbox,
  structural audit, commit-before-response and enqueue-after-commit.
- Mock creates only `validated_mock`; synthetic/Sandbox modes may enqueue only
  after their exact profile validates. No adapter is invoked in the request.
- Tests: route/method/generic closure; Project/tenant/actor/CSRF/IDOR; exact
  release/policy/node/hash validation; duplicate/divergent occurrences;
  stale mapping/profile/target version; exact replay/payload conflict;
  transaction rollback; commit/enqueue ordering; Mock zero Outbox/attempt/
  mapping/network; no MBOM/Gate/Project/Work Item/Tooling/Trial mutation.
- Exact-SHA ordinary CI must pass before checkpoint 3.

### Checkpoint 3 — leased worker, closed adapter and observed result/mapping

- Add bounded pending/expired-claim recovery, immutable pre-call attempt,
  closed adapter registry, default-disable/Mock and disposable network-free
  synthetic adapters, Sandbox-ready injected adapter seam, result classifier,
  atomic terminal result/audit and authoritative mapping compare-and-set.
- Tests: pending/live/expired lease; crash before/after adapter boundary;
  restart without blind redispatch; exact target idempotency; timeout uncertain;
  2xx malformed/mismatch; rate/5xx/business faults; synthetic no formal code;
  authoritative result authenticity/binding; stale mapping conflict;
  transaction/commit ambiguity; secret/body/error redaction; bounded recovery;
  zero production host/traffic and no generic retry/reconcile API.
- Extend the cumulative disposable-Site runtime through command/Outbox/worker/
  restart using only explicit network-free synthetic proof. Exact-SHA ordinary
  CI must pass before checkpoint 4.

### Checkpoint 4 — trilingual EBOM Item execution workspace

- Extend the existing Phase 5 EBOM publish workspace/data source with bounded
  Item execution list/detail/create behavior, source/profile/expected-version
  impact, request/attempt/uncertain/mapping truth, permissions and disabled
  reasons. Keep one primary action and no retry/reconcile control.
- Tests: normal/empty/loading/unavailable/no-permission/read-only/conflict/
  processing/Mock/synthetic/failed/uncertain/succeeded-authoritative states;
  formal-code redaction; optimistic/idempotency/CSRF command; keyboard/focus/
  labels/non-color status; English/`zh`/`zh-TW` direct translations and mixed-
  language scans; three fixed visual cases; no target access from browser.
- Exact-SHA ordinary CI and affected visual evidence must pass before the final
  Level 3 Gate.

### Final P8-03 Level 3 Gate

- Run complete repository/frontend/security/visual verification and cumulative
  disposable-Site runtime with migrations twice.
- Runtime proves default-disable, Mock zero dispatch, synthetic request/
  Outbox/claim/attempt/result, duplicate/conflict, stale mapping, crash/restart,
  timeout uncertainty/no redispatch, direct-write guards, redaction, stable
  cross-process replay, zero formal mapping, zero target write, zero production
  traffic and cleanup. Because no approved Sandbox exists, it does not claim an
  authoritative mapping or production readiness.
- Use `release-gate` because public API/event/OpenAPI/ownership, shared Outbox
  Schema, permission/transaction infrastructure and trilingual UI change.
  P8-03 advances to P8-04 only after exact final SHA ordinary CI and Level 3
  both pass.

| Changed boundary | Minimum affected evidence |
| --- | --- |
| source/request/profile domain | grouping/conflict, exact hashes, Item/MBOM separation, expected mapping/target versions, mode/production rejection |
| event/OpenAPI/ownership | closed Item-only schemas, no generic CRUD/MBOM/secrets, exact ERP/NPI field ownership and extra/missing/type tests |
| Outbox/Item metadata | version-1/legacy guards, immutable envelopes/history, mapping CAS, migration twice, no direct write/delete |
| Project-first repository/BFF | containment/IDOR/CSRF/permission, exact source/profile resolution, atomic request/idempotency/outbox/audit, commit/enqueue ordering |
| worker/adapter/result | leases/restart, pre-call attempt, no blind redispatch, classifier matrix, authority binding, redaction and zero production traffic |
| frontend/i18n/visual | all support states, formal-code redaction, one primary action, direct trilingual coverage, accessibility and affected visual matrix |
| final trace/security/runtime | complete repository/frontend/history-secret/visual, cumulative disposable runtime, release review and Requirement reconciliation |

## 11. Expected changed paths

| Change | Expected paths |
| --- | --- |
| pure Item execution domain/configuration | new `apps/npi_integration/npi_integration/item_publish/**`; focused shared reliable primitive only if backward-compatible |
| shared Outbox and Item metadata/controllers | existing `npi_outbox_message/**`; new `npi_item_publish_request/**`, `npi_item_publish_command_idempotency/**`, `npi_item_publish_attempt/**`, `npi_item_publish_result/**`, `npi_item_mapping_head/**`, `npi_item_mapping_observation/**` |
| Project-first API/repository/worker hooks | `apps/npi_core/npi_core/bff.py`; operation-specific API/worker modules; `apps/npi_integration/npi_integration/hooks.py` |
| contracts and ownership | `contracts/integration-event.schema.json`; `contracts/npi-api.openapi.yaml`; `contracts/data-ownership.yaml` |
| localization | `apps/npi_core/npi_core/translations/zh.csv`; `zh-TW.csv`; generated frontend catalogs after extraction |
| frontend workspace | focused publish-request data source/workspace/styles/app composition and their unit/E2E fixtures/tests/snapshots |
| controlled proof | `tests/test_phase8_item_publish_*.py`; runtime verifier/shell and CI workflow cumulative Phase 8 lane |
| controller/trace/evidence | P8-03 plan/checkpoints/validation and current controller/trace/risk/status files |

A required global engineering identity, production Item naming/UOM/field
mapping, actual target method, production/Sandbox credential activation, MBOM
payload, generic retry/replay/reconciliation, new dependency, core patch,
cross-database access or ownership relaxation reopens the audit instead of
silently expanding these paths.

## 12. Migration, security and rollback

All metadata changes are additive. Legacy Outbox rows remain readable support
history but receive no fabricated tenant, Project, profile, source, claim,
attempt, authenticated or executable state. Version-1 validation applies only
to controlled Item rows. No patch creates a profile, endpoint, credential,
mapping, target ID or business row.

The disposable Site migrates twice. Runtime checks exact indexes/uniqueness,
controller guards, legacy compatibility, scheduler idempotence, claim expiry,
cross-process replay and cleanup. No production endpoint/credential appears in
code, Site config, database, environment, process arguments, artifacts or logs.

Before an Item Outbox message crosses an adapter boundary, rollback may disable
the routes/enqueue/worker and remove fresh disposable Schema while retaining
any committed request/idempotency/outbox/audit rows for forward migration.
After any attempt crosses the adapter boundary, rollback is forward-only:
disable new command/enqueue/claim, retain every request, event, claim, attempt,
response hash, result, uncertainty, mapping observation/head and audit, and
deploy a reviewed repair. It never deletes/requeues an uncertain attempt,
rewrites failed/Mock/synthetic state to success, changes an Item Code, edits the
released source or performs compensating target mutation.

Because the P8-03 Gate uses no networked Sandbox, its rollback requires no
target compensation. Any future Sandbox activation must add adapter-specific
reconciliation and rollback evidence before use.

## 13. Explicit holds and non-scope

- Production ERPNext/JCE endpoint, credential, data, adapter, method, traffic,
  customization, Item creation/update, naming/UOM/field mapping and acceptance
  remain prohibited.
- No default execution profile, requester, service actor, endpoint, secret,
  Item Group, stock UOM, naming series, sample mapping or fallback is installed.
- No MBOM/routing, Tool Asset, formal quality, Project/Gate/Work Item, Tooling,
  Trial, readiness, released source or Phase 5 history mutation occurs.
- No global/cross-Project engineering-part identity is claimed. The mapping
  stream is explicitly tenant + Project + exact engineering identity.
- P8-07 owns generic operations/DLQ/manual retry/replay/reconciliation,
  corrected commands, cross-operation backoff and operator overrides. P8-03
  adds no such UI/API.
- P8-04 through P8-09 remain inactive. A synthetic result is technical evidence
  only and never a formal Item mapping, ERP acceptance or production UAT.

## 14. Automatic transition

Standing continuous-delivery authority permits automatic progression after
each exact-SHA ordinary CI and affected Gate passes. Checkpoint 1 becomes the
only active product scope only after the commit freezing this plan and task
manifest passes ordinary CI. No checkpoint authorizes production ERPNext/JCE
contact. P8-03 completes only after its final Level 3 Gate; only then may the
controller activate P8-04.
