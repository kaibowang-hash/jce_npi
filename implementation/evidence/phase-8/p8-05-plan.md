# P8-05 Plan — Operation-Specific ERPNext Tool Asset Execution

Recorded: `2026-08-24`

Status: `FROZEN — CHECKPOINTS 1–4 ORDINARY PASS; FINAL HELD AT P6-06 PREDECESSOR DIAGNOSTIC`

Audit base and retained P8-04 product checkpoint:
`ca72deceab4b8e899d0da1207883887c9d30077a`

P8-04 final ordinary pull-request CI: `32651139504` (`PASS`)

P8-04 final unchanged Level 3: `32651903846` (`PASS`)

P8-04 closeout and P8-05 audit checkpoint:
`d54b0d71e63fd8a02b294135b5dd879aac16946c`

P8-04 closeout/P8-05 audit ordinary CI: `32654431690` (`PASS`)

P8-05 frozen-plan transition checkpoint:
`937c5d72c29ec189f69ea5b2384eef64847698bf`

P8-05 frozen-plan ordinary CI: `32656436943` (`PASS`)

P8-05 checkpoint 1 final checkpoint:
`db0cb846589816dc55002b8a002914aedced9fb2`

P8-05 checkpoint 1 ordinary CI: `32660953137` (`PASS`)

P8-05 checkpoint 2 final checkpoint:
`d20b4a3bba67ae333e161295fe1155211375f013`

P8-05 checkpoint 2 ordinary CI: `32664440277` (`PASS`)

Primary requirements:

- `INT-005`; and
- `FR-TL-011`, `FR-TL-012`, `FR-TL-013`, `FR-TL-014`, `FR-TL-015`,
  `FR-TL-016`.

`NFR-INT-001` contributes only the durable Outbox, idempotent attempt,
uncertain-result and restart-safety foundation required by this operation.
Generic operations, DLQ, manual retry/replay, corrected-command authority and
reconciliation remain P8-07. P8-06 and P8-08/P8-09 remain inactive.

## 1. Audit decision

The bounded requirement, domain, existing-capability, ownership and security
audit passes. It does not authorize product code until this frozen plan and
task-manifest transition passes exact-SHA ordinary CI.

The repository provides strong predecessors but no executable Tool Asset
boundary:

- Phase 6 defines Tooling Master, one physical Tooling Set, exact Set-to-
  Revision binding, immutable Tooling Revision and append-only acceptance
  evidence. The acceptance revision covers nine evidence categories and
  Project evidence for movement intentions, spares and repairs, but explicitly
  reports business approval as `unavailable`. Evidence completeness is not
  Tooling approval, formal quality approval, Gate approval or ERP approval.
- Phase 6 also retains one `npi.tooling-asset.v1` local Mock preparation under
  the combined operation `create_or_update_tool_asset`. It is fixed to
  `draft` / `validated_mock` / approval `unavailable` / dispatch `prohibited` /
  target result `not_requested`; it creates one local request, audit and sealed
  receipt but no Outbox, attempt, worker, target identifier or formal mapping.
  Those v1 rows remain immutable historical preparation evidence and are not
  relabelled or promoted into P8-05 execution.
- The current v1 future event schemas also use the combined operation and a
  not-yet-supplied `business_approval_evidence_id`. P8-05 must add a versioned
  execution contract with separate create/update operations; it cannot change
  the meaning of old rows or accept a caller-provided approval identity.
- P8-01 already owns the normalized read-only `tool_asset_status` projection
  for one exact Project + physical Tooling Set. An authenticated authoritative
  observation can expose formal Asset ID, mapping/target version, raw Asset
  state, location, shot/life, maintenance and bounded movement/repair/spare
  history. Mock, synthetic, stale, conflicted and unavailable projections stay
  unavailable. P8-05 reuses this reader and does not create a second owner for
  Asset status/location/maintenance truth.
- P8-03 and P8-04 provide reusable patterns for a closed execution profile,
  actor-bound idempotency, atomic request + Outbox + audit, commit-before-
  enqueue, bounded leases, immutable attempts/results, network-free synthetic
  proof, uncertain-after-boundary handling, authenticated result binding and
  compare-and-set mapping. Their operations, profiles, streams and result
  histories remain separate from Tool Asset execution.
- No approved ERPNext Asset method, custom-field mapping, Company, Asset
  Category, Location, naming series, capitalization/depreciation rule,
  maintenance policy, service scope, business-approval source, sandbox host,
  credential or authenticated response fixture exists. These are scoped
  external holds. They block Sandbox/formal activation but do not block a
  default-disabled Mock and disposable network-free technical foundation.

P8-05 therefore delivers only an operation-specific technical execution
foundation. It proves exact physical-Set source binding, separate create/update
authority, immutable expectations, durable execution truth, partial and
uncertain handling, zero-or-one formal mapping protection and read-only
projection consumption without claiming production or Sandbox acceptance.

## 2. Frozen minimum vertical slice

P8-05 delivers exactly this path:

> authorize one Project before every secondary identity -> resolve one exact
> Tooling Master and physical Tooling Set -> lock its exact current Set-to-
> Revision binding, Tooling Revision and acceptance-evidence revision -> retain
> acceptance evidence separately from unavailable business approval -> lock
> the current Tool Asset mapping and exact P8-01 Asset projection expectation ->
> derive either create or update from the fixed route and locked mapping state ->
> resolve one server-owned operation-specific Tool Asset execution profile ->
> create or replay one immutable v2 request with exact source, approval,
> expectation and profile hashes -> atomically append one guarded Tool Asset
> Outbox command and audit -> commit before enqueue -> claim one physical-Set
> stream with a bounded lease -> freeze one immutable attempt before adapter
> entry -> call only the configured closed adapter operation -> classify
> aggregate and bounded owned-field outcomes independently of HTTP acceptance ->
> retain partial, failed and uncertain truth -> advance a zero-or-one mapping
> head only from an authenticated authoritative complete Sandbox result and
> exact compare-and-set -> correlate but never overwrite the existing P8-01
> read-only Asset/status/location/maintenance projection -> expose truthful
> execution and observed Asset truth in the existing Tooling acceptance/asset
> workspace

Create and update are separate commands. P8-05 does not expose a generic
Asset CRUD endpoint, caller-selected target method, movement command,
maintenance command, repair command, spare/inventory command or approval
command.

No production network call, production profile, credential, target row,
cross-database access, Asset submission, depreciation/capitalization action,
movement/maintenance mutation or automatic reconciliation exists in this task.

## 3. Exact source and zero-or-one mapping

The Tool Asset stream key is a canonical SHA-256 over:

- exact Site tenant ID;
- exact NPI Project global ID; and
- exact physical Tooling Set global ID.

The immutable source effect additionally freezes:

- Tooling Master global ID, title and snapshot hash;
- physical Set global ID, physical serial, requirement kind and snapshot hash;
- exact current Set-to-Revision binding global ID and snapshot hash;
- exact Tooling Revision global ID, revision number/label and snapshot hash;
- exact acceptance-evidence revision global ID, stable acceptance identity,
  version, predecessor and snapshot hash;
- the five existing NPI-owned candidate fields manifest: Master title,
  physical serial, Tooling requirement kind, source Tooling revision and
  acceptance-evidence reference;
- current mapping expectation and exact P8-01 projection expectation;
- execution profile ID/version/mode/environment/operation allowlist and hash;
- server-derived actor, service actor, request ID, trace ID, idempotency hash,
  target-effect hash and creation time.

One physical Tooling Set maps to zero or one formal ERP Asset. Tooling Master,
Tooling Requirement quantity and replicated/copy tooling are not mapping
subjects. Every separately created physical copy requires its own Tooling Set
identity and its own zero-or-one stream.

Create requires exact locked `unmapped` expectation: no current authoritative
Tool Asset mapping head and no exact authenticated current P8-01 projection
that identifies an existing formal Asset. Any observed existing mapping,
projection conflict or unknown current state blocks create before Outbox.

Update requires one exact locked current formal mapping: mapping version,
formal Asset ID, opaque target version, authoritative observation identity/hash
and current head hash. The formal Asset ID is server-derived and never accepted
from the browser. Missing, duplicate, stale, synthetic, conflicted or
mismatched mapping/projection truth blocks update before Outbox.

If the operation-specific mapping head and current P8-01 Asset projection both
exist, their physical Set, formal Asset ID and target-version relation must be
compatible under the frozen projection policy. A mismatch is visible conflict;
neither source silently wins and no command is dispatched.

## 4. Separate create/update authority, approval and idempotency

P8-05 v2 freezes exactly two operation codes:

- `create_tool_asset`; and
- `update_tool_asset`.

The legacy `create_or_update_tool_asset` code remains valid only for retained
P6 v1 Mock draft history. It is never accepted by a v2 profile, Outbox worker
or adapter.

Create and update have separate fixed POST routes, profile operation
allowlists, acknowledgement text, payload hashes and idempotency identities.
The browser cannot submit the operation value. The fixed route selects the
operation and the repository proves the corresponding mapping precondition
under lock. One actor/key may replay only the same operation and same complete
payload; the same key across create/update or a changed source/expectation/
profile is a conflict.

Three authorities remain distinct:

1. immutable NPI acceptance evidence — proof of what was reviewed;
2. business approval evidence — a future approved policy/reference required
   for any authoritative Sandbox create/update; and
3. execution authority — current Project operation permission, exact profile
   requester allowlist, service actor and explicit impact acknowledgement.

P8-05 does not invent business approval. Current acceptance evidence keeps
`businessApprovalState=unavailable`. Mock may validate and retain a request
without Outbox. A disposable synthetic fixture may exercise transport under an
explicit test-only authorization marker, but that marker is not business
approval and can never produce a formal Asset ID, mapping or target success.
Sandbox command creation remains blocked until an approved immutable business-
approval contract and exact server-resolved evidence source are supplied.

## 5. Ownership and read-only observed truth

ERPNext owns formal Asset identity, target version, Asset lifecycle/state,
Company/Category/naming, capitalization/depreciation, location, movement,
custody, shot/life count, maintenance, repair execution/history, formal spare
Item/supplier/inventory and target cost.

NPI One owns Tooling development identities, physical Set, revisions,
acceptance evidence, movement/repair/spare Project evidence, execution request,
Outbox, attempt, result observation, audit and read-only mapping/projection
association. No ERP-owned value is editable through NPI One.

An authenticated complete Sandbox create/update result may append one mapping
observation and compare-and-set head for the exact physical Set. The mapping
contains only the exact source/request/attempt/result correlation, formal Asset
ID, mapping version, opaque target version, authenticated response hash,
profile/environment, predecessor head and observation time. It does not become
the owner of Asset state/location/maintenance.

P8-01 remains the only read-only status/location/maintenance projection. P8-05
may display its exact confirmed current value alongside execution truth but
cannot refresh it from the browser, infer missing values, translate raw target
codes into approval, or update it from Mock/synthetic/HTTP acceptance. A later
authenticated observation may show target changes independently of the last
execution request; those facts remain ERP-owned.

NPI movement/loan/return/archive/scrap, spare and repair records are evidence
and intentions only. They never execute an ERP movement, maintenance, stock or
repair transaction in P8-05. Customer-owned repair authorization evidence is
retained but is not target approval or proof of completed repair.

## 6. Execution profile and adapter safety

P8-05 installs no execution profile, endpoint, credential, ERP method or field
mapping. Missing configuration is explicit unavailable. A Tool Asset profile
is separate from Item and MBOM profiles and freezes:

- profile ID/version and exact tenant/Project scope;
- target mode `mock`, `synthetic` or `sandbox`;
- exact allowed operation set (`create_tool_asset` and/or
  `update_tool_asset`) without generic mutation;
- permitted internal requesters and one exact service actor;
- adapter resolver and contract version;
- source-to-target projection policy ID/version/hash;
- explicit non-production environment and hostname allowlist;
- opaque secret reference and response-authentication mode; and
- bounded connect/read timeouts, no redirect and no proxy/production fallback.

Mock is default-disabled and network-free: it has no adapter, operations,
endpoint or secret and creates no Outbox/attempt/mapping. Synthetic is allowed
only in the disposable runtime with an exact test marker and closed in-process
adapter; it emits no formal Asset ID/version and never advances mapping or
P8-01 projection truth.

Sandbox requires an explicitly installed non-production profile, HTTPS exact
host allowlist, operation-specific secret scope, supported response
authentication, exact approved projection policy and business-approval source.
Known production labels, localhost, IP literals, redirects, embedded
credentials, environment fallback and caller-selected resolver/method fail
closed. No Sandbox profile is installed by this task.

## 7. Request, Outbox, attempt, result and mapping truth

P8-05 adds a versioned v2 execution branch without rewriting P6 rows:

- immutable request and exact source/approval/mapping/profile snapshot;
- actor-bound one-way-sealed idempotency receipt;
- one physical-Set stream guard shared by create and update;
- guarded Tool Asset Outbox envelope with operation, target-effect hash,
  request link and immutable payload hash;
- immutable attempt frozen before adapter entry;
- aggregate result plus bounded result entries for the five owned-field
  candidates, without persisting unrestricted target payloads;
- append-only formal mapping observation and compare-and-set head; and
- append-only structural audit.

Business state and Outbox are committed atomically. Enqueue occurs only after
commit. An enqueue failure returns the already committed request and leaves a
recoverable pending Outbox; it does not report a false command rollback.

The worker claims only pending or expired pre-boundary work with a bounded
lease. It freezes request/source/approval/profile/mapping expectations and an
immutable attempt before entering the adapter. A live lease is not reclaimed.
An expired lease may be reclaimed only when no adapter boundary was crossed.
After possible target contact, timeout/crash is `uncertain_after_timeout` and
cannot be blindly redispatched before P8-07 reconciliation.

Result states distinguish at least `synthetic_verified`, `succeeded`,
`partially_applied`, `failed_retryable`, `failed_final`,
`uncertain_after_timeout`, `target_unavailable`, `observed_conflict` and
`not_claimed`. HTTP 2xx or queue acceptance alone never selects success.

Partial results retain every known field outcome and safe target fault code,
but do not advance a formal mapping head. Only one exact authenticated complete
Sandbox result for the claimed attempt, operation, idempotency/effect hash,
source, approval, expected mapping and response contract may append/advance
the mapping. Late or stale success is retained as conflict and cannot overwrite
the current head.

## 8. API, permissions and product surface

Reads remain Project-first and bounded. P8-05 retains the existing acceptance/
Asset context and v1 history and adds a v2 execution request collection/detail
plus two fixed command routes under the exact Project/Master/Set context:

- create route -> `create_tool_asset`; and
- update route -> `update_tool_asset`.

The combined legacy POST remains a P6 Mock preparation endpoint and cannot
emit a v2 command. The BFF exposes no PUT/PATCH/DELETE, retry, replay,
reconcile, movement, repair, maintenance, spare or generic action route.

Authentication occurs before request parsing. Project authorization occurs
before Master/Set/request/mapping/projection lookup. Create/update require
current internal Project operation authority, CSRF, exact profile membership,
explicit impact acknowledgement and server-derived actor/tenant/trace. External
actors and guests cannot create or inspect restricted execution detail.
Identical absent/foreign secondary identities remain non-enumerable.

Checkpoint 4 extends the existing Tooling acceptance/asset workspace rather
than adding a Desk form. It keeps one visible primary action for the currently
valid create or update intent, never both. The action is disabled with a direct
reason for unavailable approval/profile/mapping/permission/readiness.

The inspector separates Tooling source, NPI acceptance evidence, business
approval, execution request/attempt/result, formal mapping and P8-01 observed
Asset truth. It covers loading, empty, unavailable, no-permission, read-only,
conflict, Mock, synthetic, queued, processing, partial, failed, uncertain,
authoritative and stale-observation states. Formal Asset ID/version appears
only for an authenticated authoritative permitted mapping/projection.

All new visible source text is literal English through `t()`, with direct
`zh` and `zh-TW`, controlled terminology, keyboard/focus labels, non-color
status and governed fixed-Linux visual evidence. No UI is active before its
checkpoint.

## 9. Events, audit and response semantics

Contracts add versioned v2 Tool Asset create/update command and observed result
branches. The P6 v1 combined request/result schemas remain exact historical
contracts and cannot be emitted by the v2 worker. Events contain exact request,
source, approval, expectation, profile, operation, idempotency/effect and trace
correlation; no secret, unrestricted payload or exception text is persisted.

Audit records request creation/replay conflict, Outbox append, claim/reclaim,
attempt boundary, classified result, partial/uncertain outcome, mapping CAS or
conflict and safe enqueue failure. Logs and responses expose safe problem codes
and trace IDs, not credentials, raw target bodies, stack traces or business
payloads.

The public request response means only that NPI truth was durably accepted.
Mock means locally validated only. Synthetic means disposable mechanics only.
Only authenticated authoritative complete Sandbox observation can mean target
success, and no such profile/evidence is installed by P8-05.

## 10. Fault matrix

| Fault | Result | Durable truth | Forbidden effect |
| --- | --- | --- | --- |
| Project absent/foreign/unauthorized | unavailable | safe trace | no secondary lookup/leak |
| Master/Set/binding/Revision changed | conflict/final | old source retained | no latest substitution |
| acceptance revision missing/changed | conflict/final | evidence history retained | no guessed acceptance |
| business approval unavailable | blocked for Sandbox | explicit unavailable | no approval inference |
| create with observed mapping | conflict | exact current mapping | no duplicate Asset |
| update without exact mapping/version | conflict/not ready | expectation retained | no caller Asset ID |
| mapping and P8-01 projection disagree | observed conflict | both sources retained | no silent winner |
| profile absent/invalid/production | unavailable/final | safe code | no fallback/network |
| same actor/key/same operation/payload | replay | one request/outbox | no duplicate dispatch |
| same key/different operation/payload | `409` | original + audit | no overwrite |
| Mock request | validated Mock | request/audit only | no Outbox/attempt/mapping |
| synthetic execution | synthetic verified | technical proof | no formal ID/mapping |
| crash before command commit | rollback | no partial rows | no enqueue |
| crash after commit before enqueue | pending recoverable | request/outbox retained | no false rollback |
| live lease | not claimed | current attempt | no concurrent call |
| expired pre-boundary lease | reclaimed | new attempt/audit | no duplicate request |
| crash/timeout after boundary | uncertain | known outcome hashes | no blind redispatch |
| malformed/mismatched 2xx | final/uncertain | safe classification | no status-derived success |
| partial authenticated response | partially applied | bounded field outcomes | no mapping advance |
| rate/5xx before possible commit | retryable | classification | no P8-05 replay control |
| business validation/permission | failed final | safe code/hash | no source rewrite |
| complete authoritative success | succeeded | result + mapping CAS | no Asset-state ownership |
| late success/stale head | observed conflict | result retained | no head overwrite |
| duplicate/reordered status observation | P8-01 rules | immutable observation | no stale projection advance |
| direct support-DocType mutation/delete | denied | immutable history | no support bypass |

## 11. Checkpoints and changed-files-to-tests map

### Checkpoint 1 — pure Tool Asset v2 domains, contracts and metadata

- Add separate create/update operation, exact source/approval/mapping/profile,
  request/state/fault/result/field-result/CAS domains; additive v2 events,
  OpenAPI and ownership contracts; guarded shared Outbox schema-3 Tool Asset branch and
  request/idempotency/stream/attempt/result/field-result/mapping metadata;
  direct translations.
- Retain exact hydration and rejection for every P6 v1 combined Mock row.
- Tests: source/hash determinism; physical-Set cardinality; create-unmapped and
  update-exact-version expectations; mapping/projection conflict; acceptance
  evidence versus approval; operation/profile separation; Mock/synthetic/
  Sandbox safety; partial/uncertain aggregation; authenticated mapping CAS;
  metadata guards; legacy/Item/MBOM Outbox regressions; contract/i18n symmetry.
- No route, persistent v2 row, Outbox row, worker, adapter, mapping or UI
  behavior activates. Exact-SHA ordinary CI must pass before checkpoint 2.

### Checkpoint 2 — Project-first create/update commands and atomic Outbox

- Add fixed v2 list/detail/create/update routes, exact Tooling and acceptance
  resolution, locked mapping/P8-01 expectation, Project/profile permission,
  operation-bound idempotency, immutable request, guarded Outbox, stream guard,
  audit, commit-before-response and enqueue-after-commit.
- Tests: route/method/generic closure; tenant/Project/CSRF/IDOR; exact source and
  approval unavailability; create/update mapping preconditions; profile
  separation; replay/cross-operation conflict; atomic rollback and enqueue
  ordering; Mock zero Outbox/attempt/mapping/network; no Tooling/Trial/Gate/
  Project/Asset-projection mutation.
- Exact-SHA ordinary CI must pass before checkpoint 3.

### Checkpoint 3 — leased worker, adapter, result and mapping

- Add bounded pending/expired pre-boundary recovery, immutable attempts, closed
  adapter registry, disposable network-free synthetic proof, aggregate/field
  result classification, uncertainty/no-redispatch and authenticated complete-
  result mapping compare-and-set.
- Tests: live/expired lease; restart before/after boundary; fixed target
  idempotency; create/update manifests; partial/malformed/mismatch/rate/5xx/
  business/timeout; synthetic no formal IDs; authority binding; stale mapping
  conflict; projection mismatch; redaction; zero production traffic and no
  retry/reconcile/movement/maintenance API.
- Extend the cumulative disposable Site only with network-free synthetic proof.
  Exact-SHA ordinary CI must pass before checkpoint 4.

### Checkpoint 4 — trilingual Tool Asset execution inspector

- Extend the existing Tooling acceptance/asset workspace with exact source,
  approval/profile/mapping impact, execution history and read-only P8-01 Asset
  observation; one guarded create-or-update primary action selected by current
  mapping truth.
- Tests: normal/empty/loading/unavailable/no-permission/read-only/conflict/
  Mock/synthetic/queued/processing/partial/failed/uncertain/authoritative/stale;
  ID redaction; CSRF/idempotency; keyboard/focus/non-color state; direct
  English/`zh`/`zh-TW`; mixed-language scan and governed visuals; browser zero
  target access.
- Exact-SHA ordinary CI and affected visuals must pass before final Level 3.

### Final P8-05 Level 3 Gate

- Run complete repository/frontend/security/visual verification and cumulative
  disposable-Site runtime with migrations twice.
- Runtime proves P6 v1 retention, v2 create/update separation, exact physical-
  Set source/cardinality, approval hold, Mock zero dispatch, network-free
  synthetic attempts/results, atomic Outbox, leases/restart, partial/uncertain
  truth, mapping CAS conflict, P8-01 read-only projection separation, direct-
  write guards, zero formal mapping, zero target write, zero production traffic
  and cleanup.
- Use `release-gate` because public API/events/ownership, shared Outbox Schema,
  permissions/transactions and trilingual UI change. P8-06 activates only
  after final exact-SHA ordinary CI and Level 3 pass.

| Changed boundary | Minimum affected evidence |
| --- | --- |
| source/profile/domain | exact Tooling identities/hashes, approval separation, operation/mapping expectations, partial/uncertain, production rejection |
| event/OpenAPI/ownership | closed v2 create/update schemas, v1 preservation, exact ownership, no generic CRUD/secrets/movement/maintenance |
| Outbox/Tool Asset metadata | additive branch, legacy/Item/MBOM non-regression, immutable history, mapping CAS, migration twice |
| Project-first repository/BFF | containment/IDOR/CSRF, exact locks, operation-bound idempotency, atomic request/Outbox/audit, ordering |
| worker/adapter/result | leases/restart, pre-call attempt, no blind redispatch, partial matrix, authority binding, redaction |
| P8-01 projection consumer | exact current/authenticated/unavailable/stale/conflict, no projection ownership or browser refresh |
| frontend/i18n/visual | one contextual action, support states, identifier redaction, trilingual/accessibility/affected visuals |
| final runtime/security/trace | complete suites, disposable runtime, rollback/recovery and requirement reconciliation |

## 12. Expected changed paths

| Change | Expected paths |
| --- | --- |
| Tool Asset v2 domain/config/repository/worker | existing `apps/npi_integration/npi_integration/tool_asset_request/**` |
| API/BFF/hooks | `apps/npi_core/npi_core/bff.py`; existing `tool_asset_request_api.py`; `hooks.py` |
| guarded Outbox/support metadata | existing `npi_outbox_message/**`, `npi_tool_asset_request/**`, `npi_tool_asset_command_idempotency/**`; new Tool Asset stream/attempt/result/field-result/mapping head/observation DocTypes |
| read-only projection integration | focused existing `projections/**` and P6 acceptance repository only if exact reuse requires it; no new projection owner |
| contracts/ownership | `contracts/integration-event.schema.json`; `contracts/npi-api.openapi.yaml`; `contracts/data-ownership.yaml` |
| translations | direct `zh.csv`, `zh-TW.csv` and generated frontend catalogs |
| frontend | focused Tool Asset data source, existing acceptance/asset workspace/composition/styles and unit/E2E fixtures/snapshots |
| controlled proof | `tests/test_phase8_tool_asset_*.py`; runtime verifier/shell and cumulative Phase 8 workflow lane |
| predecessor regressions | focused P6 acceptance/Tool Asset, P8-01 projection and P8-03/P8-04 Outbox tests |
| controller/evidence | P8-05 plan/checkpoints/validation and current controller/trace/risk/status files |

Any actual ERPNext method/field/category/company/location/naming/depreciation/
maintenance mapping, business-approval policy, default/network profile,
production credential, generic replay/reconciliation, new dependency, core
patch, cross-database access or ownership relaxation reopens the audit instead
of expanding paths.

## 13. Migration, security and rollback

All metadata changes are additive. Existing P6 v1 request/idempotency rows and
their combined operation retain exact validators and remain readable. No patch
rewrites them into v2, creates a business approval, profile, endpoint,
credential, mapping, projection or target row. New support DocTypes deny normal
create/update/delete and use narrow capability scopes.

The disposable Site migrates twice. Runtime checks exact indexes/uniqueness,
controller guards, v1/Item/MBOM compatibility, scheduler idempotence, lease
expiry, cross-process replay and cleanup. No production endpoint/credential
appears in code, Site config, database, environment, process arguments,
artifacts or logs.

Before any adapter boundary, rollback disables v2 Tool Asset routes, enqueue
and worker and retains committed request/idempotency/Outbox/audit rows for
forward migration. After any attempt crosses the boundary, rollback is
forward-only: disable new commands/enqueue/claims; retain every request, event,
lease, attempt, response hash, field/aggregate result, uncertainty, mapping
observation/head and audit; deploy a reviewed repair. Never delete or replay an
uncertain attempt, rewrite partial/failure/Mock/synthetic to success, change a
formal Asset ID, mutate Tooling/acceptance/projection truth, execute movement/
maintenance/repair, or compensate a target automatically.

Because the Gate uses no networked Sandbox, no target compensation is needed.
Future Sandbox activation requires adapter-specific approval, projection,
reconciliation and rollback evidence before use.

## 14. Explicit holds and automatic transition

- Production ERPNext/JCE endpoint, credential, data, adapter, method, traffic,
  customization and Asset create/update/movement/maintenance remain prohibited.
- No default profile/requester/service actor/endpoint/secret/company/category/
  location/naming/depreciation/maintenance/field mapping or sample Asset ID is
  installed.
- Formal Asset mapping/status cannot come from P6 request history, acceptance
  evidence alone, Mock, synthetic, enqueue, HTTP acceptance, timeout or an
  unverified response.
- The exact business-approval source and authenticated Sandbox mapping remain
  scoped external holds, not reasons to weaken the technical foundation.
- P8-07 owns generic operations/DLQ/retry/replay/reconciliation and operator
  overrides. P8-06, P8-08/P8-09 and Phase 9 remain inactive.

Frozen-plan SHA `937c5d72` passes exact-SHA ordinary CI `32656436943`, and
remediated checkpoint 1 SHA `db0cb846` passes ordinary CI `32660953137`.
Standing continuous-delivery authority therefore permits checkpoint 2 only.
Its fixed Project-first list/detail/create/update and atomic request + guarded
Outbox + stream guard + audit implementation now awaits its own exact-SHA
ordinary CI. Checkpoints 3–4 each require the previous exact-SHA ordinary CI.
P8-05 remains in progress until final unchanged Level 3 passes; no checkpoint
authorizes production ERPNext/JCE contact.

Checkpoint 2 exact product SHA `d20b4a3bba67ae333e161295fe1155211375f013`
passes ordinary CI `32664440277` (repository `97255552087`, frontend
`97255551972`, secret `97255552048`, visual `97255552051`; controlled jobs
correctly skipped). Standing authority therefore activates checkpoint 3. The
checkpoint 3 candidate adds only the bounded leased worker, closed operation-
specific adapter registry, network-free disposable synthetic proof, immutable
attempt/field/aggregate result truth and authenticated complete-result mapping
CAS described above. Checkpoint 4 remains closed until checkpoint 3 exact-SHA
ordinary CI passes.

## 15. Checkpoint 2 implementation candidate evidence

Checkpoint 2 implements the frozen Project-first command boundary and awaits
its own exact-SHA ordinary CI:

- fixed GET collection/detail plus fixed POST `:create` / `:update` BFF and
  domain API routes preserve exact Project, Tooling Master, physical Set and
  request route parameters; wrong methods, generic collection writes,
  detail writes, retry, reconcile and suffix variants fail as not found;
- Project authorization precedes secondary identity and command-body parsing;
  execution reads exclude external principals and command writes require the
  internal `NPI API User` role, CSRF and exact current Project membership;
- the repository locks the exact Master, physical Set, Set-to-Revision
  binding, Tooling Revision and acceptance revision, then requires an exact
  create-unmapped or update-current mapping plus P8-01 projection expectation;
- acceptance evidence remains separate from unavailable business approval.
  No Sandbox command can proceed without the missing approved authority, and
  the profile resolver is default-off and fails closed when ambiguous;
- one actor- and operation-bound transaction writes the immutable request,
  guarded schema-3 Outbox when dispatch is explicitly allowed, physical-Set
  stream guard, audit and sealed idempotency receipt. Commit precedes response,
  enqueue follows commit, exact replay returns committed truth without enqueue,
  enqueue failure retains the pending Outbox and emits one safe diagnostic,
  and commit failure rolls back without reporting success; and
- Mock persists only local request/audit/receipt truth with no Outbox, enqueue,
  worker, adapter, target identifier, formal mapping, network or target effect.

Changed-files to affected-tests evidence:

- BFF/API/problems/OpenAPI -> fixed-route behavior, route parameters,
  Project-first IDOR, role/CSRF, closed input, replay/status and stable problem
  tests;
- repository/capability helper -> exact five-parent locking, create/update
  mapping and projection expectations, profile/approval holds, atomic write
  order, cross-operation idempotency, datetime parsing and exact
  `ignore_permissions` capability tests;
- translations/generated catalog -> literal-English extraction, direct
  no-header `zh` / `zh-TW` symmetry, generated-catalog equality and mixed-
  language audit; and
- predecessor security -> retained P6 combined Mock behavior and exact BFF
  routes, all Item/MBOM suites, and the global seven-call capability allowlist
  with no additional permission bypass.

Final Level 1 results are `431/431 PASS`: Tool Asset `46/46`, P6 acceptance
`35/35`, retained P6 Tool Asset domain `4/4`, Item `146/146`, MBOM `126/126`
and current-task/reconciliation/localization `74/74`. Generated catalog and
TypeScript checks pass; i18n audits `8,293` literal English sources with
`100%` direct `zh` / `zh-TW` coverage. Focused Python compilation, JSON/YAML/
CSV parsing, exact no-direct-SQL/network/target-call checks, controller
verification, reconciliation and `git diff --check` pass. Post-commit manifest
simulation accepts exactly `29` task paths and no thirtieth task path.

Checkpoint 3 exact product SHA
`17406118f2a771644c90ca00272a247f40b1b5b7` passes ordinary CI
`32667224305` (secret `97262446040`, frontend `97262445982`, visual
`97262446007`, repository `97262446049`; controlled jobs correctly skipped).
Standing authority therefore activates checkpoint 4. The candidate adds only
the strict read-only execution detail projection and the compact trilingual
Tool Asset execution inspector in the existing acceptance/Asset workspace.
Formal Asset identity remains withheld unless authenticated authoritative
Sandbox result, exact current mapping head and fresh permitted P8-01
projection all agree. Final unchanged Level 3 remains closed until checkpoint
4 exact-SHA ordinary CI passes. The scoped ERPNext field/approval/Sandbox facts
remain held, and no code, test or evidence claims production or formal Asset
acceptance.

## 16. Checkpoint 4 pre-commit evidence

The checkpoint 4 candidate implements only the strict Tool Asset detail read
projection and the compact trilingual execution inspector described above.
Affected backend/controller suites pass `409/409`, focused frontend tests pass
`21/21`, complete frontend unit tests pass `1,060/1,060`, and the complete
non-visual browser suite passes `454/454`. The final strict P6 and P8-05 browser
fixtures independently pass `22/22` and `4/4`.

The six affected Bookworm/x64 baselines pass no-update twice consecutively,
and a clean serial run passes the complete governed visual matrix `129/129`.
The P6-06 images are an approved semantic composition migration caused by the
frozen always-present inspector; the old acceptance/Mock context remains
visible, the disabled reason is direct, and no formal Asset identifier is
introduced. The P8-05 authoritative case alone shows the controlled fake ID
after exact permission/current-mapping/fresh-projection agreement; synthetic
and partial cases remain redacted. No tolerance, threshold, Darwin baseline,
command, worker, adapter or target behavior changed.

I18n audits cover `8,341` literal English sources with complete direct `zh` and
`zh-TW` catalogs. Current-task/reconciliation, compilation, JSON/YAML/Frappe-
CSV parsing, frontend static/a11y/boundary checks, zero-vulnerability audit and
`git diff --check` pass. Post-commit manifest simulation accepts exactly `32`
authorized task paths and rejects any thirty-third path. Exact image hashes and
the full changed-files-to-tests mapping are retained in
`p8-05-execution-inspector-checkpoint.md`. The checkpoint still awaits its own
exact-SHA ordinary CI before final unchanged Level 3 can start.

## 17. Final runtime predecessor diagnostic cycle

Checkpoint 4 exact SHA `3d35d6860e63478bc12fde9a0426d0ea00c8b31e`
passes ordinary CI `32680231720`. The sole final dispatch `32682520429`
passes all non-runtime lanes and controlled preflight, but controlled runtime
job `97303507677` receives an opaque HTTP 500 at the P6-06 predecessor Mock
Asset-create POST before any P8-03 through P8-05 runtime stage. That final
allowance is immutable `1/1` and proves no product root.

Standing serial recovery opens a distinct P6-06 predecessor Asset-create
cycle at diagnostic `0/1`, repair `0/1`, final `0/1`. The bounded checkpoint
temporarily activates only the exact synthetic POST/key scope and records one
allowlisted lexical stage, exception class and exact validated trace. It
changes no response, permission, transaction, ownership, Schema, worker,
adapter or target behavior and discloses no status, body, business value,
identity, hash, actor, message or stack. Product repair remains prohibited
until one tuple uniquely proves a root.

Diagnostic dispatch `32686039575` / controlled job `97311234126` reached the
safe mirrored reader, but the new parent verifier destructured its established
`(exception_type, code, trace)` return contract as `(code, exception_type,
trace)`. It therefore rendered the two labels in reverse. This is a bounded
verifier harness failure, not product evidence: predecessor-cycle diagnostic,
repair and final counters remain `0/1`, `0/1`, `0/1`.

The response-neutral remediation corrects only that parent tuple unpacking and
locks single/mirrored success plus duplicate, divergent, wrong-trace, invalid-
type and extra-key fail-closed behavior. Server diagnostic code, API,
repository, response, permission, transaction and product behavior are
unchanged. A new diagnostic dispatch is prohibited until this checkpoint
passes affected Level 1 and exact-SHA ordinary CI.

The corrected diagnostic dispatch `32687547589` / controlled job
`97315303938` emitted exactly
`P805_P606_ASSET_RECEIPT_SEAL / PermissionError /
trace-094ac4bd2cf15cac884914224d752ba1`. Static execution-order and pinned
Frappe v15 storage cross-proof uniquely locate the first failure in the shared
receipt controller's new raw immutable comparison: a legacy P6 receipt omits
the additive Int `schema_version`, so the same in-memory document retains
`None` while Frappe persists and reloads database truth as `0`. The seal save
therefore compared `None` with `0` and raised before any sealed-response
predicate. The legacy write flag remains active around insert, request, audit
and seal; permissions, links and the P8-05 execution capability are not the
root.

The predecessor cycle is now diagnostic `1/1`, uniquely proved product repair
`1/1`, final `0/1`. The bounded repair treats only `None` and `0` as the same
legacy storage representation for immutable `schema_version`; nonzero changes,
all other raw immutable fields, the one-way seal, validation ordering,
capability and transaction boundaries remain unchanged. The temporary parent
activation is closed. Diagnostic run `32686039575` remains immutable harness
failure evidence and consumes no product counter.

## 18. Final retained-Master verifier remediation

Exact repair SHA `735992c1971c258089ab596ed20663606908f1f7`
passes ordinary CI `32688638775`. Final Level 3 run `32689595411` passes
repository, frontend, secret, governed visual and controlled preflight, then
controlled runtime job `97322480056` stops in the Tool Asset default-disabled
probe at the fixed `P6-01 P6-03 Master cardinality drifted` verifier boundary.
The P8-05 fresh command and worker have not run at that point.

Cross-proof identifies a verifier-fixture compatibility defect. P6-08
intentionally creates and retains a second formula-neutralization Tooling
Master for export route recovery, replay and package evidence. P8-01 already
selects the original retained Master by its exact synthetic title and
originating Project, while the older P6-03 `project_context` still applied
`exact_single` to the complete unfiltered Master collection. Tool Asset
product code only reads and locks the exact Master and physical Set and cannot
be the source of the additional retained row.

The bounded harness remediation makes the P6-03 verifier select that exact
original fixture title plus `originatingProjectGlobalId` before applying the
same fail-closed uniqueness check. The P6-08 Master remains retained; missing,
duplicate, malformed or wrong-Project original rows remain constant-safe and
no row value is emitted. This changes no product, API, permission,
transaction, Schema, ownership, runtime profile or target behavior and does
not consume a product repair counter. A new exact-SHA ordinary CI is required
before the predecessor cycle's sole final unchanged Level 3 may resume.
