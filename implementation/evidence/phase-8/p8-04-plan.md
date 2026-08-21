# P8-04 Plan — Operation-Specific ERPNext MBOM Publish Execution

Recorded: `2026-08-21`

Status: `FROZEN — CHECKPOINT 1 AWAITS EXACT-SHA ORDINARY CI`

Audit base and retained P8-03 product checkpoint:
`c11d97cc4e26cd3961d7927608eb2510f6411269`

P8-03 final ordinary pull-request CI: `32479492064` (`PASS`)

P8-03 final unchanged Level 3: `32480568505` (`PASS`)

Primary requirements:

- `INT-004`; and
- the MBOM portion of `FR-DS-013`.

`NFR-INT-001` contributes only the durable Outbox, idempotent attempt,
uncertain-result and restart-safety foundation required by this operation.
Generic operations, DLQ, manual retry/replay, corrected-command authority and
reconciliation remain allocated to P8-07. P8-05 through P8-09 remain inactive.

## 1. Audit decision

The bounded requirement, domain, existing-capability, ownership and security
audit passes. P8-03 is sealed at exact product SHA `c11d97c`; its Item request,
Outbox, attempt, result and authoritative mapping history are immutable input
evidence, not MBOM command state.

The repository provides useful foundations but no executable MBOM boundary:

- Phase 5 freezes one Project-scoped, Mock-only combined
  `publish_released_ebom_item_mbom` request over an exact released EBOM,
  release event, approval evidence, canonical lines and per-line hashes. It
  intentionally creates no Outbox, attempt, target identifier or success.
  Its nodes and mapping/result rows remain immutable historical source
  evidence; P8-04 will not promote, relabel or mutate them.
- The released EBOM is a bounded acyclic graph of stable line keys. Each line
  freezes its UUID, parent, engineering identity, quantity, engineering UOM,
  alternates, effectivity and controlled attributes. A line with direct
  children is an assembly source node; a leaf is a component-only source node.
  Every node still participates in exact source and Item-mapping readiness.
- P8-03 creates one authoritative Item mapping stream per tenant + Project +
  exact case-preserved engineering identity. Only an authenticated Sandbox
  observation can advance its head. Mock, synthetic, legacy, conflict and
  absent heads are not valid MBOM prerequisites.
- P8-03 Item commands do not authorize MBOM execution. Item requesters,
  profiles, stream guards, operation, idempotency and target effects remain
  separate. P8-04 consumes only locked current Item mapping observations.
- Phase 5's future combined event/OpenAPI vocabulary is not observed target
  truth and lacks the P8 request/profile/attempt/authenticity/uncertainty
  boundary. It is retained for historical compatibility, not promoted into
  execution. P8-04 requires additive MBOM-only contracts.
- The shared `NPI Outbox Message` has a guarded version-1 Item branch and
  Item-specific Link fields. P8-04 may add a separate guarded MBOM envelope
  branch and MBOM-specific references, but it cannot broaden or reinterpret
  Item or legacy rows.
- There is no MBOM execution request, immutable node snapshot, MBOM attempt,
  aggregate/per-node result, current formal BOM mapping head or observation.
  These must be additive and operation-specific.
- No approved ERPNext BOM method, company/factory context, engineering-to-
  stock UOM conversion, alternate/effectivity projection, routing, naming,
  draft successor rule, submitted-BOM update rule, endpoint, credential or
  authenticated Sandbox response exists. These facts hold real Sandbox and
  production activation, but do not block a fail-closed Mock/default-disabled,
  adapter-ready technical foundation.

P8-04 therefore delivers an MBOM-only technical execution foundation. It
proves immutable released topology, exact authoritative Item prerequisites,
operation-specific command/Outbox/attempt/result truth, per-node partial and
uncertain outcomes, submitted-BOM immutability and restart safety on a
disposable Site using only Mock and network-free synthetic adapters. It
installs no target profile or adapter and claims no formal BOM mapping without
an authenticated authoritative Sandbox result.

## 2. Frozen minimum vertical slice

P8-04 delivers exactly this path:

> authorize one Project before every secondary identity -> resolve one exact
> immutable Phase 5 released-EBOM publish request -> revalidate its publish
> policy, revision, lifecycle, release event, approval evidence, complete
> topology and hashes -> classify every exact line as assembly or component
> source without changing it -> lock and classify the current Item mapping
> head for every distinct engineering identity -> lock current
> MBOM mapping expectations for every assembly source key -> resolve a
> separate server-owned MBOM execution profile -> create or replay one
> immutable `publish_released_mbom` request with exact source, mapping-set and
> profile hashes -> in the same transaction append one guarded MBOM Outbox
> envelope and audit -> commit before enqueue -> claim the exact message with
> a bounded lease -> freeze one immutable batch attempt before adapter entry ->
> call only the configured closed MBOM adapter -> classify aggregate and every
> node observation independently of HTTP acceptance -> append immutable batch
> and node results -> advance only exact authenticated successful draft-BOM
> mapping heads by compare-and-set -> preserve submitted, partial, failed and
> uncertain truth without overwrite or blind redispatch -> expose the result
> in the existing EBOM publish workspace

One request represents one exact released EBOM revision and its complete
topology. It is not an Item request, a generic ERP payload or a caller-selected
set of nodes. The Item operation remains independently complete and immutable.

No production network call, production profile, target credential, target row,
cross-database access, BOM submission, routing mutation or generic target CRUD
exists in this task.

## 3. Source identity, topology and mapping readiness

The MBOM source stream key is a SHA-256 over this closed identity:

- exact Site tenant ID;
- exact NPI Project global ID; and
- exact NPI EBOM global ID.

The immutable semantic target effect additionally freezes the exact released
revision and complete current mapping expectations, so a new released revision
or changed authoritative observation is a different effect without inventing
a different EBOM stream.

The command accepts only:

- Project ID in the fixed route;
- exact Phase 5 publish-request ID;
- expected exact released-source hash;
- expected Item-mapping-set hash;
- expected MBOM-mapping-set hash;
- bounded actor-scoped idempotency key; and
- explicit acknowledgement of the displayed source/profile/target impact.

The caller cannot supply tenant, actor, operation, target mode, target method,
DocType, endpoint, Item Code, BOM ID, submitted state, target version, node
membership, payload, hash authority, formal success or mapping authority.

The server derives and freezes:

- exact Phase 5 request ID/payload hash and publish-policy reference;
- exact EBOM/root/revision IDs, versions and hashes;
- lifecycle version, release event ID/hash, approval IDs and release time;
- complete canonically ordered line UUID/key/parent/engineering identity,
  quantity, engineering UOM, alternate/effectivity/attribute snapshot and
  line hash;
- an exact edge/topology hash and assembly/component role for every line;
- one locked current authoritative Item mapping expectation per distinct
  engineering identity: stream hash, mapping version, Item Code, target
  version and observation hash;
- one locked MBOM mapping expectation per assembly source key: mapping version,
  formal BOM ID, target version, target submission state and observation hash,
  or exact unmapped-create truth;
- execution profile ID/version/mode/environment/projection-policy snapshot;
- actor, service actor, request ID, trace ID, actor-key hash, target effect hash
  and creation time.

An assembly source key is tenant + Project + EBOM global ID + exact stable line
key. A source line is an assembly when the frozen revision contains at least
one direct child edge; otherwise it is component-only. Nested assemblies are
both a child Item in their parent and an independently mapped assembly BOM.
The contract does not invent routing, operation rows or a target mutation for
component-only leaves.

Every Sandbox-bound line requires a current P8-03 Item mapping head whose
observation is exact, `advanced`, `authoritative_sandbox`, Project/source-bound
and hash-valid. Missing, synthetic, legacy, stale, conflicted, mismatched or
changed Item truth is explicit `not_ready`; Sandbox request creation is
blocked with zero Outbox/attempt. Mock may retain the exact readiness matrix
without dispatch or fabricated codes. Disposable synthetic mode may exercise
only transport mechanics with closed source-derived `synthetic_item_reference`
values under the explicit test marker; those values are never called Item
Codes, never create/alter an Item mapping head and can never authorize a
formal MBOM observation.

The exact Item and MBOM mapping-set hashes are returned by the read boundary
and acknowledged by the command. The repository rebuilds both under lock;
changed head versions, codes, target versions, observations, node membership
or topology produce a conflict rather than latest-value substitution.

## 4. Command and approval separation

EBOM release approval remains immutable source evidence. It does not itself
authorize an ERPNext write. P8-04 adds a separate MBOM execution command with:

- independent Project operation authority;
- membership in the exact MBOM execution profile requester allowlist;
- explicit acknowledgement of the exact released topology, Item readiness,
  MBOM expectation and profile impact; and
- a separately frozen worker service actor.

P8-03 Item requester membership, confirmation, idempotency key, request state
or terminal success grants no MBOM authority. Conversely, MBOM execution does
not change or approve Item execution. No new multi-user approval workflow is
invented: the exact EBOM release event is the engineering approval evidence,
while the MBOM profile and confirmation are the operation-specific execution
authority.

## 5. Ownership and submitted-BOM boundary

ERPNext owns formal BOM ID, target version, draft/submitted state, routing,
manufacturing operations and formal lifecycle. NPI One owns the released EBOM
source, approval evidence, request, Outbox, attempt, result observation, audit
and read-only association to an observed ERP-owned BOM.

A formal MBOM mapping is an append-only observed association for one assembly
source key. It contains the exact source/revision/topology hash, formal parent
Item Code, formal BOM ID, opaque target version, semantic target submission
state (`editable_draft` or `submitted_immutable`), request/event/attempt/result
identity, adapter profile/environment, authenticated response hash, previous
mapping hash/version and observation time.

Only an authenticated authoritative Sandbox result for the exact claimed
attempt, operation, idempotency key, source hash, Item-mapping set, MBOM
expectation and response contract may append a formal observation. Mock,
synthetic, HTTP 2xx, queue acceptance, timeout, caller echo, unverified body or
partial aggregate status cannot.

P8-04 never submits a BOM. It may model only create-draft or update-draft
intent. A current `submitted_immutable` mapping blocks local update before
dispatch. If the target reports that a previously observed draft became
submitted or its version changed, the exact node is retained as conflict and
no mapping head is overwritten. Creating a successor for a submitted BOM
requires a future approved target policy; P8-04 does not guess it.

Each successful node performs its own locked compare-and-set. A late success
whose expectation is no longer current is retained as `observed_conflict` and
does not advance the head. Formal BOM IDs are never edited in place.

## 6. Execution profile and adapter safety

P8-04 installs no MBOM execution profile, endpoint, credential, method or
business mapping. Missing configuration is explicitly unavailable. The MBOM
profile is separate from the Item profile and freezes:

- profile ID/version and exact tenant/Project scope;
- target mode: `mock`, `synthetic` or `sandbox`;
- only operation `publish_released_mbom`;
- permitted internal requesters and exact service actor;
- fixed adapter resolver and contract version;
- non-production environment attestation;
- immutable projection-policy ID/version/hash for hierarchy, engineering-to-
  stock UOM, alternate/effectivity and target-field interpretation;
- for Sandbox only, exact HTTPS origin/hostname allowlist, opaque secret
  reference, fixed timeouts, no redirects and response-authentication mode.

Modes are truthful:

- `mock`: validates and retains one `validated_mock` request with the exact
  source and Item-readiness matrix, including explicit `not_ready`; no Outbox,
  attempt, node success, Item/BOM ID, mapping or target access.
- `synthetic`: available only under an explicit disposable-test marker and
  injected network-free adapter/projection fixture. It may derive closed
  synthetic Item references from exact line/source hashes solely to exercise
  batch and per-node Outbox/claim/attempt/result mechanics. It ends
  `synthetic_verified`, exposes no formal Item/BOM ID/version and advances no
  Item or MBOM mapping.
- `sandbox`: disabled unless a separately approved exact non-production
  profile, projection policy and adapter exist. No such profile is installed
  or used by P8-04 validation.
- production/live labels, hosts and modes are unsupported and rejected before
  enqueue or adapter resolution.

Credentials are resolved separately into memory and never persist in request,
Outbox, attempt, audit, response or logs. The adapter is batch- and
operation-specific; no browser or generic DocType/method payload reaches it.

## 7. Request, node, Outbox, attempt and result truth

Request states are closed:

- `validated_mock` — local exact-source validation only;
- `queued` — request plus MBOM Outbox committed;
- `processing` — exact claim and immutable attempt retained;
- `synthetic_verified` — disposable non-authoritative proof;
- `partially_succeeded` — authenticated node outcomes differ; every node
  remains visible and no automatic retry is exposed;
- `succeeded` — every targeted assembly node has an authoritative successful
  result and mapping compare-and-set;
- `failed_retryable` — classified safe pre-boundary/target failure retained
  for future P8-07 policy;
- `failed_final` — closed source/profile/permission/business/contract failure;
- `uncertain_after_timeout` — target may have committed and redispatch is
  prohibited; and
- `mapping_conflict` — one or more authenticated observations were retained
  but could not advance their expected head.

Every source line has an immutable request node. Component-only nodes finish
with explicit `component_only` disposition and never claim a BOM mutation.
Assembly node results are closed: queued, processing, synthetic-verified,
succeeded-authoritative, failed-retryable, failed-final,
blocked-item-mapping, blocked-submitted, uncertain-after-timeout or
observed-conflict. Aggregate state is derived from exact node truth; it cannot
erase a partial, blocked, failed or uncertain node.

The MBOM Outbox branch is additive, operation-specific envelope schema version
`2` (the event contract remains version `1`). Its immutable envelope binds
exact request, event, tenant, Project, operation, profile,
released source/topology, Item/MBOM mapping-set expectations, actor, service
actor, trace, request idempotency and target semantic effect. Item version-1
and legacy Outbox rows retain their existing validation and execution rules.

Each adapter invocation gets a new immutable attempt identity and claim token
but the same server-derived semantic target idempotency key. The batch attempt
is persisted before adapter entry and binds a fixed sorted node manifest.
Raw credentials, headers, response bodies, exception messages and stack traces
are never stored.

Initial dispatch and expired-lease recovery are in scope. A worker may reclaim
only a pre-boundary expired claim. Once adapter entry is durable, a crash or
timeout seals uncertainty and prohibits redispatch until P8-07 reconciliation.
A partial response never authorizes retry of failed nodes in P8-04.

## 8. API, permissions and UI

The fixed Project-first BFF routes are:

- `GET /api/npi/v1/projects/{projectId}/mbom-publish-requests`;
- `POST /api/npi/v1/projects/{projectId}/mbom-publish-requests`; and
- `GET /api/npi/v1/projects/{projectId}/mbom-publish-requests/{requestId}`.

Every route validates canonical UUIDs, authenticated session, CSRF for POST,
tenant membership and Project view/execute authority before resolving a Phase
5 request, Item mapping, MBOM mapping or target-derived identifier. Missing,
foreign and unauthorized secondary IDs share the safe unavailable boundary.
List limits, containment and redaction are server-side.

Execution requires Project authority plus exact MBOM-profile requester
membership. The worker uses only the profile's enabled internal service actor.
Support DocTypes are System-Manager read-only and controlled internal writes
use narrow operation-specific capabilities. No Desk CRUD is a product path.

The existing dense EBOM publish workspace gains an MBOM inspector showing the
exact revision/topology hash, assembly/component roles, Item readiness,
expected MBOM version/submission state, profile/mode, aggregate and per-node
states, uncertainty/reconciliation requirement and observed mapping authority.
It shows no formal ID unless the current observation is authoritative and the
viewer is permitted.

There is one primary MBOM request action with exact impact and acknowledgement.
It is disabled with a direct reason for missing Item mappings, no assembly,
missing profile, permission denial, changed hashes, active/uncertain stream,
submitted mapping or stale expectation. No retry/reconcile/submit control is
added. New text is literal English through `t()`/Frappe `_()` with direct `zh`
and `zh-TW`, keyboard/focus/accessibility checks and restrained industrial
status treatment.

## 9. Events, audit and response semantics

The additive MBOM-only events are:

- `npi.mbom_publish_request.ready`, version `1`, NPI One to ERPNext; and
- `erpnext.mbom_publish_result.observed`, version `1`, ERPNext to NPI One.

They bind the exact profile, released source/topology, Item mapping set, MBOM
expectations, request/event/attempt/idempotency identity and closed aggregate/
node result. They contain no generic method/DocType/endpoint, credential,
routing mutation or caller-selected success.

API `201` means only the immutable local request committed; `200` replay means
the same actor/key/payload returned the original. Sandbox `succeeded` requires
every assembly node to pass response authenticity and mapping compare-and-set.
It does not submit a BOM or make NPI One the MBOM master.

Request creation/replay/conflict, Outbox append/claim/recovery, attempt start,
partial/uncertain classification, node observation, mapping advance/conflict
and terminal failure append structural audits in the same transaction as the
state they describe. Audits store only stable codes, IDs, hashes, versions and
trace IDs.

## 10. Fault matrix

| Fault | Result | Durable truth | Forbidden effect |
| --- | --- | --- | --- |
| Project absent/foreign/unauthorized | unavailable | safe trace | no secondary lookup/leak |
| Phase 5 request/release/hash invalid | conflict/final | old source retained | no latest substitution |
| graph invalid/changed | conflict/final | exact old topology | no repaired graph |
| Item head absent/non-authoritative/changed | not ready/conflict | exact readiness | no Sandbox dispatch or guessed Item Code |
| no assembly node | validation failure | source retained | no empty target command |
| MBOM profile absent/invalid/production | unavailable/final | safe code | no fallback/network |
| existing submitted mapping | blocked-submitted | exact observation | no update/successor guess |
| same actor/key/same payload | replay | one request/outbox | no duplicate dispatch |
| same actor/key/different payload | `409` | original + conflict audit | no overwrite |
| Mock request | validated-mock | request/audit only | no Outbox/attempt/mapping |
| synthetic execution | synthetic-verified | batch/node proof | no BOM ID/mapping |
| crash before command commit | rollback | no partial rows | no enqueue |
| crash after commit before enqueue | pending recoverable | request/outbox retained | no lost work |
| live lease | not claimed | existing attempt | no concurrent call |
| expired pre-boundary lease | reclaimed | new attempt/audit | no duplicate request row |
| crash/timeout after boundary | uncertain | all known node truth | no redispatch/success |
| malformed/mismatched 2xx | final/uncertain by boundary | safe hash/code | no status-derived success |
| partial authenticated response | partially-succeeded | each node result | no aggregate fake success |
| rate/5xx before possible commit | retryable | classification | no P8-04 replay control |
| business validation | failed-final | safe target code/hash | no source rewrite |
| target reports submitted/version drift | conflict/blocked | observation retained | no overwrite |
| authoritative current node success | node succeeded | observation + CAS head | no dual-master edit |
| late success/stale MBOM head | observed-conflict | result retained | no head overwrite |
| direct support-DocType mutation/delete | denied | immutable history | no support bypass |

## 11. Checkpoints and changed-files-to-tests map

### Checkpoint 1 — pure MBOM domains, contracts and guarded metadata

- Add exact topology/assembly classification, Item readiness, MBOM expectation,
  request/profile/state/fault/result/CAS domains; additive MBOM-only event,
  OpenAPI and ownership contracts; guarded MBOM Outbox schema-version-2 branch and read-only
  request/node/idempotency/stream/attempt/result/node-result/mapping metadata;
  direct translations.
- Tests: graph/source/hash determinism; assembly/component classification;
  every authoritative Item prerequisite; no-assembly/missing/stale/conflict;
  create/update/submitted MBOM expectations; profile mode/host/secret/
  operation rejection; partial/uncertain aggregates; authenticated authority;
  mapping CAS; direct-write/delete/legacy/Item Outbox regressions; contract and
  translation symmetry.
- No route, persistent command row, Outbox row, worker, adapter, mapping or UI
  behavior activates. Exact-SHA ordinary CI must pass before checkpoint 2.

### Checkpoint 2 — Project-first command and atomic durable Outbox

- Add fixed list/detail/create routes, exact Phase 5 released-source and locked
  Item/MBOM mapping-set resolution, Project/profile permission, actor-bound
  idempotency, immutable request/nodes, guarded MBOM Outbox, stream guard,
  structural audit, commit-before-response and enqueue-after-commit.
- Tests: route/method/generic closure; tenant/Project/CSRF/IDOR; source graph/
  hash and Item-authority validation; mapping-set conflict/submitted block;
  profile separation; replay/payload conflict; stream active/retained truth;
  rollback/enqueue ordering; Mock zero Outbox/attempt/mapping/network; no Item,
  EBOM, Gate, Project, Work Item, Tooling or Trial mutation.
- Exact-SHA ordinary CI must pass before checkpoint 3.

### Checkpoint 3 — leased batch worker, adapter and per-node observations

- Add bounded pending/expired pre-boundary recovery, immutable batch attempts,
  closed adapter registry, disposable network-free synthetic proof, aggregate/
  node result classification, uncertainty/no redispatch and authoritative
  per-assembly mapping compare-and-set with submitted-BOM protection.
- Tests: live/expired lease; restart before/after boundary; fixed target
  idempotency; exact node manifest; partial/malformed/mismatch/rate/5xx/
  business/timeout; synthetic no IDs; authenticated result binding; submitted
  drift; per-node stale mapping conflict; transaction ambiguity; redaction;
  bounded recovery; zero production traffic and no retry/reconcile API.
- Extend the cumulative disposable Site only with network-free synthetic proof.
  Exact-SHA ordinary CI must pass before checkpoint 4.

### Checkpoint 4 — trilingual MBOM execution inspector

- Extend the existing EBOM publish workspace with bounded MBOM list/detail/
  create data, topology/readiness/expected-version impact, aggregate/per-node
  truth, permissions and disabled reasons; one guarded primary action.
- Tests: normal/empty/loading/unavailable/no-permission/read-only/conflict/
  processing/Mock/synthetic/partial/failed/uncertain/submitted/authoritative
  states; identifier redaction; idempotency/CSRF; keyboard/focus/labels/
  non-color status; direct English/`zh`/`zh-TW`; mixed-language scan and three
  fixed visual cases; no target access from browser.
- Exact-SHA ordinary CI and affected visuals must pass before final Level 3.

### Final P8-04 Level 3 Gate

- Run complete repository/frontend/security/visual verification and cumulative
  disposable-Site runtime with migrations twice.
- Runtime proves default-disable, Mock zero dispatch and explicit not-ready,
  exact topology, synthetic-reference isolation, batch/node partial and uncertainty, leases/restart,
  submitted guard, direct-write guards, redaction, stable replay, zero formal
  MBOM mapping, zero target write, zero production traffic and cleanup.
- Use `release-gate` because public API/events/ownership, shared Outbox Schema,
  permissions/transactions and trilingual UI change. P8-05 activates only
  after final exact-SHA ordinary CI and Level 3 pass.

| Changed boundary | Minimum affected evidence |
| --- | --- |
| source/profile/domain | topology/hash, roles, Item readiness, MBOM expectation/submitted, state/fault/partial/uncertain, production rejection |
| event/OpenAPI/ownership | closed MBOM-only schemas, exact ownership, no generic CRUD/secrets/routing/submission, extra/missing/type tests |
| Outbox/MBOM metadata | additive branch, Item/legacy non-regression, immutable history, per-node results, CAS, migration twice |
| Project-first repository/BFF | containment/IDOR/CSRF, exact source and mapping-set locks, atomic request/idempotency/outbox/audit, ordering |
| worker/adapter/result | leases/restart, pre-call attempt, no blind redispatch, partial matrix, authority binding, submitted protection, redaction |
| frontend/i18n/visual | support states, identifier redaction, one action, trilingual/accessibility/affected visuals |
| final runtime/security/trace | complete suites, disposable runtime, rollback/recovery and requirement reconciliation |

## 12. Expected changed paths

| Change | Expected paths |
| --- | --- |
| pure MBOM domain/config | new `apps/npi_integration/npi_integration/mbom_publish/**` |
| API/repository/worker hooks | `apps/npi_core/npi_core/bff.py`; new `mbom_publish_api.py`; `hooks.py` |
| guarded Outbox/MBOM metadata | existing `npi_outbox_message/**`; new `npi_mbom_publish_request/**`, `npi_mbom_publish_node/**`, `npi_mbom_publish_command_idempotency/**`, `npi_mbom_publish_stream_guard/**`, `npi_mbom_publish_attempt/**`, `npi_mbom_publish_result/**`, `npi_mbom_publish_node_result/**`, `npi_mbom_mapping_head/**`, `npi_mbom_mapping_observation/**` |
| contracts/ownership | `contracts/integration-event.schema.json`; `contracts/npi-api.openapi.yaml`; `contracts/data-ownership.yaml` |
| translations | direct `zh.csv`, `zh-TW.csv` and generated frontend catalogs |
| frontend | focused MBOM data source, existing EBOM publish workspace/composition/styles and unit/E2E fixtures/snapshots |
| controlled proof | `tests/test_phase8_mbom_publish_*.py`; runtime verifier/shell and cumulative Phase 8 workflow lane |
| controller/evidence | P8-04 plan/checkpoints/validation and current controller/trace/risk/status files |

An actual ERPNext method/field/UOM/alternate/effectivity/routing mapping,
submitted-BOM successor rule, default/network profile, production credential,
generic replay/reconciliation, new dependency, core patch, cross-database
access or ownership relaxation reopens the audit instead of expanding paths.

## 13. Migration, security and rollback

All metadata changes are additive. Existing Phase 5, legacy Outbox and P8-03
Item rows retain exact validators and are never promoted to MBOM execution.
No patch creates a profile, endpoint, credential, Item/BOM mapping or target
row. New support DocTypes deny normal create/update/delete and use narrow
capability scopes.

The disposable Site migrates twice. Runtime checks exact indexes/uniqueness,
controller guards, Item/legacy compatibility, scheduler idempotence, claim
expiry, cross-process replay and cleanup. No production endpoint/credential
appears in code, Site config, database, environment, process arguments,
artifacts or logs.

Before any adapter boundary, rollback disables MBOM routes/enqueue/worker and
retains committed request/node/idempotency/outbox/audit rows for forward
migration. After any attempt crosses the boundary, rollback is forward-only:
disable new command/enqueue/claim; retain every request, node, event, lease,
attempt, response hash, aggregate/node result, uncertainty, mapping
observation/head and audit; deploy a reviewed repair. Never delete/requeue an
uncertain attempt, rewrite partial/failure/Mock/synthetic to success, change a
formal BOM ID, mutate released source, submit/overwrite a BOM or compensate a
target automatically.

Because the Gate uses no networked Sandbox, no target compensation is needed.
Any future Sandbox activation must add adapter-specific projection,
reconciliation and rollback evidence before use.

## 14. Explicit holds and automatic transition

- Production ERPNext/JCE endpoint, credential, data, adapter, method, traffic,
  customization and BOM creation/update/submission remain prohibited.
- No default profile, requester, service actor, endpoint, secret, company,
  factory, UOM/field/alternate/effectivity/routing mapping, naming policy,
  sample mapping or fallback is installed.
- Formal Item/MBOM mapping cannot come from Phase 5, Mock, synthetic, enqueue,
  HTTP acceptance, timeout or an unverified response.
- Submitted-BOM successor/version policy and actual Sandbox mapping remain
  scoped external holds, not reasons to weaken the technical foundation.
- P8-07 owns generic operations/DLQ/retry/replay/reconciliation and operator
  overrides. P8-05 through P8-09 and Phase 9 remain inactive.

Standing continuous-delivery authority permits automatic progression only
after each exact-SHA ordinary CI and affected Gate passes. This frozen plan
transition activates checkpoint 1 only after its own ordinary CI passes.
Checkpoint 1 is behavior-free domain/contract/metadata work; checkpoint 2
cannot begin early. P8-04 remains in progress until the final Level 3 Gate
passes, and no checkpoint authorizes production ERPNext/JCE contact.
