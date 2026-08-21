# P8-04 Plan — Operation-Specific ERPNext MBOM Publish Execution

Recorded: `2026-08-21`

Status: `FROZEN — AUDIT-PLAN AND CHECKPOINTS 1–3 EXACT-SHA ORDINARY CI PASS; CHECKPOINT 4 IMPLEMENTED; AWAITS EXACT-SHA ORDINARY CI`

Frozen plan/task-manifest checkpoint:
`171a183009b10eb4c1d8f7135b635ca1537afd27`

Frozen plan ordinary pull-request CI:
`32487934051` (`PASS`)

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

The exact frozen plan/task-manifest SHA `171a183` passes ordinary CI
`32487934051`: secret `96788603341`, repository `96788603559`, frontend
`96788603635` and unchanged fixed-Linux visual `96788603482` pass; controlled
lanes correctly skip. Checkpoints 1–3 subsequently pass their own exact-SHA
ordinary CI and are sealed by the checkpoint evidence recorded below.
Checkpoint 4 is implemented locally and awaits its exact-SHA ordinary CI;
final Level 3 remains closed until that ordinary run passes.

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
after each exact-SHA ordinary CI and affected Gate passes. The frozen plan
transition passes ordinary CI `32487934051`, so checkpoint 1 is active.
Checkpoint 1 is behavior-free domain/contract/metadata work; checkpoint 2
remains inactive until the exact checkpoint 1 product SHA ordinary CI passes.
P8-04 remains in progress until the final Level 3 Gate passes, and no
checkpoint authorizes production ERPNext/JCE contact.

The first checkpoint 1 product candidate at
`7afeee28620ba7f487cbe8bdbf3a56dd4b033744` reached ordinary CI
`32493590200`: repository `96806707492`, frontend `96806707616` and visual
`96806707939` passed, while secret-history job `96806708013` found only the
synthetic `detached-signature-v1` string in a configuration test fixture. The
fixture was unrelated to that test's production-label, IP-literal and generic-
operation assertions and was replaced with the already governed
`hmac-sha256-v1` test value. This is a secret-history fixture remediation, not
a product, credential, contract, permission or Gate repair. Checkpoint 2 stays
inactive until the amended exact SHA passes a new ordinary CI.

The amended exact checkpoint 1 SHA
`97cdfbb843aeac422c71f57434a4a39f22c1954a` passes ordinary CI
`32495121120`: repository `96811612041`, frontend `96811612188`, secret
`96811612042` and unchanged `123/123` visual `96811611815` pass; controlled
lanes correctly skip. Complete checkpoint evidence is
`implementation/evidence/phase-8/p8-04-domain-metadata-checkpoint.md`.

Checkpoint 2 is now active only for fixed Project-first list/detail/create,
exact Phase 5 release/topology plus current P8-03 Item and MBOM expectation-set
resolution, server permission/profile resolution, actor-bound idempotency and
atomic request + nodes + schema-version-2 Outbox + audit, with response and
enqueue strictly after commit. Worker, adapter, attempts, result/mapping
execution and UI remain inactive until their later checkpoints.

The first checkpoint 2 candidate
`d993028560a91aa86895bb9bf028833e4c73d0fa` reached ordinary CI
`32499141551`. Repository job `96824538360` passed `2,221/2,221` Python tests
and reconciliation, then the direct-SQL zero-match scanner self-triggered on a
negative test's combination literal; frontend `96824538278`, secret
`96824538096` and unchanged visual `96824538211` all passed. The product
repository has no direct SQL. The bounded harness remediation replaces only
that literal with an AST Call-chain assertion, changes no scanner/ignore,
product, permission, transaction, threshold or Gate truth, and checkpoint 3
remains inactive until a new exact-SHA ordinary CI passes.

The response-neutral remediation exact SHA
`197a59f9ecf41daa486e84d75ac6007af38fa423` passes ordinary CI
`32500465488`: repository `96828715143` passes `2,221` tracked Python tests;
frontend `96828715126` passes `1,018` unit, `444` E2E and `8,108` direct
trilingual sources; secret `96828715130` finds no leak; unchanged `123/123`
visual `96828715029` passes. Checkpoint 2 is sealed in
`p8-04-command-outbox-checkpoint.md`.

Checkpoint 3 is now the only active scope: bounded leased recovery, immutable
batch attempts, a closed default-disabled adapter registry, disposable
network-free synthetic proof, aggregate/per-node result truth and exact
authenticated mapping compare-and-set. Its candidate awaits affected checks
and exact-SHA ordinary CI. Checkpoint 4 UI, production/Sandbox activation and
generic operations remain inactive.

Checkpoint 3 candidate `e3e36a0c7adc600a2df012fae8d2d8cb33cc74c4`
reached ordinary CI `32505131927`. Repository job `96843477712` passed
`2,259/2,259` tracked Python tests before the direct-SQL zero-match scanner
self-triggered on the new negative test's combination literal. Frontend
`96843477566`, secret `96843477773` and unchanged visual `96843477762` passed;
controlled lanes skipped. The product contains no direct SQL. The bounded
harness remediation reuses the verified AST Call-chain assertion while
retaining the other negative scans and changes no product, scanner, ignore,
permission, transaction, threshold or Gate truth. Checkpoint 4 remains closed
until a new exact-SHA ordinary CI passes.

The response-neutral remediation exact SHA `93823e35b2dbec2aa48e364e46c9abad350443c5`
passes ordinary CI `32506591419`: repository `96848025053` passes `2,259`
tracked Python tests; frontend `96848024686` passes `1,018` unit, `444` E2E
and `8,108` direct trilingual sources; secret `96848024933` finds no leak;
unchanged visual `96848024903` passes `123/123`. Checkpoint 3 is sealed.
Checkpoint 4 is now the only active scope: the dense direct-trilingual EBOM
MBOM execution inspector, strict request/project/result/current-head
projection, truthful aggregate and per-assembly states, one guarded primary
request action and exactly three affected fixed-Linux visual cases. Retry,
reconcile, submit, browser target access, default/networked profiles and
production ERPNext/JCE remain prohibited.

Checkpoint 4 candidate `a62d5ebaf28ffa4a8fd9482dadce4870e4669e77`
reached ordinary CI `32514627234`. Repository `96873370223` and secret
`96873370244` passed; frontend `96873370008` passed its complete verifier before
`23` E2E failures, and visual `96873370234` reported `116` passing and `7`
failing cases. All `30` failures derive from one legacy Playwright fixture
root: strict P5-05/P8-03 routers rejected the new fixed Project-first MBOM list
GET. The bounded remediation adds only the exact method/path/
`phase5PublishRequestGlobalId` branch with a validated default-disabled empty
list and no formal IDs. Product/UI/baseline behavior and Gate standards are
unchanged; final Level 3 remains closed pending a new exact-SHA ordinary PASS.

The seven existing P5-05/P8-03 fixed-Linux baselines are an explicitly
governed semantic migration because checkpoint 4 intentionally composes the
MBOM inspector into this same released-EBOM workspace and makes the exact MBOM
request the single primary action. Manual industrial/trilingual review retains
the older context and secondary actions, exposes the disabled MBOM reason for
the empty default-disabled legacy fixture, carries no MBOM formal identity and
keeps 125%/150% layouts usable. No product, visual threshold or Darwin baseline
is changed.

Linux/amd64 in the exact ordinary workflow is the sole canonical visual
renderer. All three P8-04 images are normalized to canonical x64 after the
visual-only harness applies one deterministic final scroll anchor; two
consecutive focused `10/10` no-update runs prove zero position drift. All
three P8-04 cases are added to the workflow and visual artifact, raising the
governed cumulative matrix from `123` to `126`.
The cumulative controlled runtime result likewise advances from P8-03 to
`scope=p5-01-through-p8-04` with P8-03 retained as
`predecessor_scope=p5-01-through-p8-03`; the executable shell already runs the
MBOM default-disabled and fresh network-free Synthetic verifier stages.
Canonical Level 1 passes two consecutive focused `10/10` no-update visual
runs, the complete `126/126` visual matrix, `29/29` affected nonvisual browser
cases, the complete `1,046/1,046` frontend unit/coverage/build/audit boundary,
`8,183` direct trilingual sources and `317/317` runtime-verifier tests.

The governed checkpoint 4 exact SHA
`4e9c8d6577e503087ec137a6b1144858c21e38fb` passes ordinary CI
`32523149643`: repository `96899549039`, frontend `96899549122`, secret
`96899549195` and canonical `126/126` visual job `96899549250` pass. The first
unchanged final Level 3 dispatch `32524439660` retains successful visual
`96903389857`, frontend `96903390151`, repository `96903390207`, secret
`96903390224` and controlled preflight `96906520757`, but controlled runtime
job `96906588035` stops in the first fresh Synthetic MBOM create response at
the existing composite verifier boundary. The observable evidence cannot
distinguish response status, response shape, queued state, request identity or
Outbox identity and therefore proves no product repair root.

This completed final dispatch is immutable historical evidence. A new opaque
P8-04 create-response narrowing cycle starts at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`; the prior dispatch remains consumed and no product
repair is counted. Its response-neutral checkpoint is parent-verifier only:
the existing shared `HttpResult.trace_id` may expose exactly one fixed
`P804_CREATE_*` response predicate with fixed `RuntimeError` type and an exact
validated `trace-[a-f0-9]{32}` correlation. It never reads or emits response
status/body, identifiers, business values, hashes, actor, target, exception
message or stack. Missing/invalid trace and disabled activation retain the
original constant; success emits no diagnostic. The activation is temporary
for the one bounded diagnostic dispatch and must be closed after tuple
recovery. API, repository, permission, transaction, Schema, response and Gate
behavior remain unchanged.

The first server-checkpoint candidate `43bf869891bf99f62f0cfbddeb56b42bd6b2a9af`
reached ordinary CI `32529961407`. Frontend `96919848835`, repository
`96919848850` and visual `96919848904` passed. Secret job `96919848666` alone
self-triggered the branch-history `generic-api-key` rule on the negative
runtime-verifier fixture value paired with the `idempotency_key` test key. The
fixture is not a credential and only proves that a non-exact synthetic
idempotency value fails closed; replacing it with the lower-entropy literal
`wrong` preserves that contract. This is a history-clean test-harness
remediation and consumes no diagnostic or product repair round.

The parent-verifier diagnostic checkpoint exact SHA
`f1c59bb6000a37a5427522c559130112eb560adb` passes ordinary CI
`32526910040`: frontend `96910769884`, canonical visual `96910769942`,
repository `96910769972` and secret `96910770018` pass. Its only controlled
diagnostic dispatch `32528181842`, preflight `96914641053` and runtime job
`96914756808` returns exactly one tuple:
`P804_CREATE_RESPONSE_STATUS / RuntimeError /
trace-4928b75518d75155a4fe459cb419dc98`. This proves only that the first fresh
Synthetic POST did not return the required create status; it exposes no actual
status, body, identifier or product symbol. The parent response cycle is now
immutable at `diagnostic 1/1`, `repair 0/1`, `final 0/1`.

A separate server-narrowing cycle starts at `diagnostic 0/1`, `repair 0/1`,
`final 0/1`; product repair remains unconsumed. Only the exact runtime
Synthetic POST may send the independent `p804-mbom-create-v1` diagnostic
scope. The server records at most the innermost allowlisted `P804_CREATE_*`
context, actual exception class and exact request trace, restores request flags
and rethrows the same exception. The parent accepts only one exact three-key
logical record, including identical dual-handler mirrors, through the existing
strict bounded log reader. Missing, duplicate, divergent, wrong-trace,
disallowed, malformed, oversized, symlink or out-of-root evidence returns the
unchanged constant. Enqueue is deliberately outside the diagnostic because
its existing post-commit failure contract still returns the committed queued
request. No response, permission, transaction, API, Schema or Gate behavior is
changed.

The history-clean server checkpoint exact SHA
`a35aae1b63becb39e6185babc001e7fb90d0a35c` passes ordinary CI
`32531248862`: frontend `96923519086`, canonical visual `96923518724`,
repository `96923519012` and secret `96923519013` pass. Its one controlled
diagnostic dispatch `32532396488` passes preflight `96926841397`; runtime job
`96926902427` returns exactly one tuple:
`P804_CREATE_REQUEST_INSERT / ValidationError /
trace-7b774b6d5f8f5df6853b4b5917f645d1`.

The exact pinned Frappe 15.115.4 insert path proves the unique first failure.
`NPI MBOM Publish Request.item_readiness_snapshot` is a JSON field, but the
repository supplied its snapshot as a Python list. Frappe `db_insert()` calls
`get_valid_dict()`, whose non-Table list predicate raises `ValidationError`
before its JSON-dict serialization branch. The preceding `source_snapshot`
dict is valid; `mbom_expectation_snapshot` is the later instance of the same
representation defect and has not yet executed. The bounded product repair
serializes only those two arrays through the existing canonical JSON helper.
It changes no source snapshot, field order, response, permission, transaction,
Schema, adapter or target behavior. The parent response cycle remains
immutable at `diagnostic 1/1`, `repair 0/1`, `final 0/1`; the server cycle is
now `diagnostic 1/1`, `repair 1/1`, `final 0/1`. Both parent and server
diagnostic activations are closed; the response-neutral mechanism remains
dormant for regression coverage.

The product-repair candidate `fde8505b478eb83f6e74ff6a9d8197246e79029e`
reached ordinary CI `32533729907`. Visual `96930635920` passes the governed
`126`-case matrix and secret `96930636093` passes. Repository job
`96930636035` runs `2,277` tests with one deterministic error in the new
pinned-Frappe simulation: full-suite import order reuses a minimal fake
`frappe` module without a `ValidationError` attribute. The test-only repair
uses its own private `PinnedValidationError`, preserving the exact list
rejection predicate without depending on shared fake-module state.

Frontend `96930636054` passes the full verifier and `449/450` E2E. Its only
failure is the pre-existing P8-01 loading-state test missing a transient
spinner before navigation completed. The exact six-path repair diff contains
no frontend path; every P8-04 E2E case passes. No timeout, retry, baseline,
product or Gate standard changes. This run is a test-harness failure and does
not consume another diagnostic or product repair round.

The deterministic test-harness repair exact SHA
`8ffd881f81fd26731c41edea545689ed6e0d4917` reached ordinary CI
`32534726775`. Attempt 1 passed repository `96933374457`, frontend
`96933374441` and secret `96933374248`; visual `96933374410` alone observed a
pre-existing R1-05 loading-position transient. The one authorized same-run,
failed-job-only attempt 2 passed repository `96936025915`, frontend
`96936009997`, secret `96936009966` and the canonical `126/126` visual job
`96936008811`. Visual artifact `9465410732` has SHA-256
`3fbbf0e47e7f10edffe3202b1744179d1039d3a3a1faccb7e76ce4e5deec06c6`.

The one unchanged final Level 3 dispatch `32536066784` retains successful
secret `96937128093`, repository `96937128315`, frontend `96937128212`,
canonical `126/126` visual `96937128296` and controlled preflight
`96939235660`. Controlled runtime `96939285384` stops at the existing first
Synthetic POST composite verifier boundary after the request-array repair.
No safe tuple, result artifact or retained Site log distinguishes the ordered
status, response-shape, queued-state, request-identity and Outbox-identity
predicates. Static code inspection therefore proves no new product symbol.
The historical server/create cycle is immutable at `diagnostic 1/1`,
`repair 1/1`, `final 1/1`.

An independent post-array-create downstream cycle starts at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`. Its verifier-only checkpoint temporarily activates
the existing exact `p804-mbom-create-v1` Synthetic POST scope and strict
mirrored-log reader. The existing 29-code `P804_CREATE_*` allowlist, shared
validated `HttpResult.trace_id`, one logical safe record and constant fallback
remain unchanged. It changes no server, product, API, permission, transaction,
Schema or Gate behavior and consumes no product repair. The activation must be
closed after the single bounded tuple is recovered.
