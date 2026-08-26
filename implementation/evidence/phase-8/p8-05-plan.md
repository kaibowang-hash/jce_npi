# P8-05 Plan — Operation-Specific ERPNext Tool Asset Execution

Recorded: `2026-08-24`

Status: `FROZEN — CHECKPOINTS 1–4 ORDINARY PASS; FINAL HELD AT POST-QUERY MAPPED-FIXTURE REMEDIATION`

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

Exact harness checkpoint `154a70058011727b3585f81f3c800aaae77804c0`
passes ordinary CI `32691391426`. Its sole final Level 3 `32692105056` passes
repository, frontend, secret, governed visual and controlled preflight. The
controlled runtime `97329247216` proves the exact retained Master selection,
then stops at the next inherited P6-03 assertion:
`P6-01 retained P6-01 Part cardinality drifted`, still within the Tool Asset
default-disabled probe and before any P8-05 product execution.

P6-07 intentionally creates and retains controlled imported engineering Part
targets for successful-job, retry, replay and reconciliation evidence. P8-01
already selects the original P6-01 Part by exact revised fixture title,
originating Project and current-revision self/version/label truth. The older
P6-03 verifier excluded only its own dedicated Part, so later P6-07 target
Parts remained in the unfiltered uniqueness input. The second bounded harness
remediation reuses the proven P8-01 predicates before `exact_single`; imported
targets remain intact and missing, duplicate, malformed, wrong-Project or
revision-mismatched originals fail constant-safe without row-value leakage.
No product counter, diagnostic activation or external authority changes.

Final run `32694547012` / controlled runtime `97335728724` exposed a defect
in that second verifier remediation itself: initial P6-03 fresh setup failed
before P6-07 because the workspace Part response does not project
`originatingProjectGlobalId`. This is harness regression evidence only and
does not consume a product, diagnostic or final counter.

The corrected stable predicate exactly reuses the full P8-01 containment
chain. It derives linked Part IDs from applicability rows whose
`projectGlobalId` and `toolingMasterGlobalId` match the Project-first context
and selected original Master, then requires the original revised title and
current-revision self/version/label truth before `exact_single`. It works for
the initial projection, which has no Part origin field, and excludes later
P6-07 target Parts without deleting them. Missing, duplicate, malformed,
wrong-edge or revision-mismatched truth remains constant-safe and value-free.

## 19. Retained ERP-projection temporal verifier remediation

Exact stable-Part checkpoint `3181d3b4a023ecd4aae31e16fcf0a84ebdbed483`
passes ordinary CI `32696041807`. Same-cycle final run `32697236054` passes
repository, frontend, secret, governed visual and controlled preflight, while
controlled runtime job `97344193455` stops in the P8-05 default-disabled probe
at the inherited P6-04 unavailable ERP-projection assertion. Fresh P8-05
synthetic execution has already completed at that point.

Execution-order and ownership cross-proof makes the harness root unique. P6
fresh/replay correctly expects unavailable truth before P8-01. P8-01 later
creates and replay-verifies a confirmed read-only ERPNEXT procurement-cost
projection for the exact retained Project and Master. P8-05 synthetic truth
has zero mapping heads and does not write, clear or advance that P8-01
projection. Therefore the later retained probe must verify available truth,
not replay the initial-only unavailable assertion.

The correction uses a closed expected-projection enum. Unspecified P6 fresh
and replay callers remain strict unavailable. Engineering and acceptance
forward the keyword explicitly, and only the P8-05 retained caller selects
available. The available branch requires exact closed outer and nested keys,
read-only ERPNEXT ownership, exact retained Master, confirmed nonempty typed
supplier, rows and summaries, and constant errors without value disclosure.
There is no automatic unavailable-or-available fallback. No product, API,
permission, transaction, Schema, ownership, profile, external contact or Gate
standard changes, and the same-cycle diagnostic, repair and final counters
remain immutable.

## 20. Retained Asset-projection temporal verifier remediation

Exact cost-mode checkpoint `43f442ce9eb6e72b237b013eeedcb869c4271a76`
passes ordinary CI `32699651339`. Same-cycle final Level 3 `32700730677`
passes repository, frontend, secret, governed visual and controlled preflight;
controlled runtime `97353390700` proceeds through the repaired available-cost
predicate and stops at the inherited P6-06 compound acceptance-context check
inside the P8-05 default-disabled probe.

The ordered predicate and ownership proof is unique without inspecting any
business value. Retained Project/Master identity has already passed. The
Administrator permission projection and unavailable business-approval shape
are fixed and unchanged. P8-01 earlier creates and replay-verifies a confirmed
read-only ERPNEXT Asset projection for the exact retained physical Tooling
Set; P8-05 Synthetic execution creates zero mapping heads and cannot mutate
that observation. Thus only the initial-era unavailable Asset projection
equality can be false.

The correction is verifier-only and introduces an independent closed
`ExpectedAssetProjectionMode`. P6 fresh and replay default to `UNAVAILABLE`;
only P8-05 retained explicitly requests both cost and Asset `AVAILABLE`.
Available Asset truth must have exact outer and nested shapes, ERPNEXT
read-only authority, exact Tooling Set, 0/1 mapping cardinality, typed nonempty
confirmed fields and value-free constant failures. Identity, permissions,
business approval and acceptance/request cardinalities retain their exact
checks with no unavailable-or-available fallback. Product, API, permission,
transaction, Schema, ownership, runtime profile and target behavior are
unchanged, and the same-cycle diagnostic, repair and final counters do not
change.

## 21. Tool Asset requester export harness remediation

Exact Asset-projection proof `3e4b57f39267577911fa0d69a9f2d17e2e91ae8b`
passes ordinary CI `32704209380`. Same-cycle final Level 3 `32705616597`
passes every non-runtime lane and controlled preflight. Controlled runtime
`97368465747` crosses retained dual-projection and default-disabled truth, then
stops before the first command at the fixed runtime-actor binding predicate.

The three ordered subpredicates have a unique static result. The captured
Project and retained P6 Tooling Project share the same Document fixture
identity. The worker is a distinct, enabled P8-02 internal NPI API actor. The
requester export alone used the P8-03 Document/Item actor even though the
Tool Asset verifier, profile and permission path require the retained enabled
P6 manufacturing actor. No preceding P5–P8-04 fixture deletes, disables or
rewrites that P6 actor.

The verifier-only harness correction binds the requester environment to the
exact existing P6 actor formula. It adds no fallback and does not accept either
actor: wrong Project, wrong requester, missing/empty worker and requester-equal
worker all remain fixed failures before command access. Product requester and
service-actor enabled/role/session validation and exact profile membership are
unchanged. This modifies no product, user, role, permission, transaction,
Schema, ownership, adapter, target or Gate behavior and consumes no diagnostic,
product-repair or final counter.

## 22. Enabled collection query harness remediation

Exact requester-export checkpoint `aaa433239166e63fcf5420fc2cc003cd0bcd5680`
passes ordinary CI `32708092916`. Same-cycle final Level 3 `32709548912`
passes every non-runtime lane and controlled preflight; controlled runtime
`97380802057` crosses the default-disabled collection and corrected actor
binding, then stops before the first command at the enabled disposable-context
predicate.

The ordered subpredicates have one static harness root. The immediately prior
default-disabled GET proves HTTP success and an exact empty execution
collection, and the intervening server restart/profile activation performs no
Tool Asset execution write. Repository command contexts are intentionally
conditional on an explicit acceptance revision query. The enabled verifier
omitted that query, so its create context is always absent even with the exact
Synthetic profile.

The verifier-only correction URL-encodes the sole retained
`acceptanceRevisionGlobalId` query. HTTP 200, exact empty items, dictionary
create context and exact Synthetic target mode remain four independent,
mandatory predicates; tests prove no POST occurs if any fails. No product,
API, permission, transaction, Schema, ownership, runtime profile, adapter,
external contact or Gate standard changes. Same-cycle counters remain
immutable.

## 23. Command-context response-neutral diagnostic checkpoint

Exact enabled-query checkpoint `bbc787c78601e97c91a54cb5f81216a61fc7e0f3`
passes ordinary CI `32713228802`. Its unchanged final Level 3
`32714624286` passes secret `97393140525`, governed visual `97393140672`,
frontend `97393140721`, repository `97393140797` and controlled preflight
`97396465261`. Controlled runtime `97396526892` crosses the corrected exact
acceptance query but stops at the same compound disposable command-context
boundary before the first Tool Asset command.

Static evidence cannot safely distinguish the four ordered response
predicates or, when the create context is absent, the eight server-side query
and create-build boundaries. No product repair is authorized. An independent
serial command-context cycle therefore starts at diagnostic `0/1`, repair
`0/1`, final `0/1`; all earlier P8-05 and predecessor cycle counters remain
immutable.

The temporary verifier-only activation sends a versioned scope header only on
the exact GET collection route with the sole retained
`acceptanceRevisionGlobalId` query. The parent classifies only status, exact
empty items, create-context shape and exact Synthetic target mode. Only the
create-shape boundary may consult the existing strict mirrored-log reader for
one of eight unique lexical server stages. All output is limited to an
allowlisted code, exception class and validated `HttpResult.trace_id`.
Missing or invalid trace/log evidence remains constant-safe; no HTTP body,
status value, business value, ID, count, actor, exception message or stack is
emitted. The innermost server stage records at most once and rethrows the same
exception, request-local state is restored, and success is response-equivalent.
No write, call order, permission, transaction, API, Schema, ownership,
profile, adapter, target or Gate behavior changes.

## 24. Command-context STATUS reader harness remediation

Exact diagnostic checkpoint `940f792543db8c5aae5539a5adabc1f11f14d6c9`
passes ordinary CI `32719211351`. Its sole controlled diagnostic run
`32720631772` passes preflight `97411097423`; controlled runtime
`97411186933` returns the safe parent tuple
`P805_TOOL_ASSET_CONTEXT_STATUS / RuntimeError /
trace-c9c0846a767a5981b43b83212f43a5b8`.

The tuple proves only a non-success response on the exact scoped GET. It does
not exclude an already-written safe server record because the parent reader
was invoked only for create-shape. Static order also cannot make an existing
create-stage record the HTTP failure root: create-stage exceptions are
intentionally recorded and caught before later response construction. Product
repair therefore remains prohibited.

The bounded same-cycle harness remediation lets STATUS and CREATE_SHAPE, and
only those two parent predicates, consult the existing strict mirrored-log
reader. A valid exact-trace allowlisted tuple wins. Missing, duplicate,
divergent, wrong-trace, disallowed or malformed evidence yields no server
attribution and falls back to the directly proven parent STATUS tuple; a
missing or invalid `HttpResult.trace_id` remains constant-safe without reading
logs. ITEMS and TARGET_MODE never read logs. No body, status value, business
value, ID, count, actor, exception message or stack is read or emitted. This
changes no product/server diagnostic stage, response, permission, write,
transaction, Schema, ownership, adapter, target or Gate behavior. The cycle
remains diagnostic `1/1`, repair `0/1`, final `0/1`; the harness correction
does not reopen or consume a product counter.

## 25. Command-context STATUS-stage diagnostic subcycle

STATUS-reader remediation exact SHA
`3412feb1d00ceb81f6102541bb51175ce973e14b` passes ordinary CI
`32722130405`: frontend `97415589215`, governed visual `97415589078`,
repository `97415589218` and secret `97415589327` all pass. The historical
command-context parent cycle remains immutable at diagnostic `1/1`, repair
`0/1`, final `0/1`; its valid parent STATUS tuple is not reclassified as a
harness failure and its dispatch is not reopened.

An independent `command-context-status-stage` subcycle starts at diagnostic
`0/1`, repair `0/1`, final `0/1`. It changes no activation, scope, allowlist,
reader, product or test code. Its sole diagnostic target is the exact scoped
GET under the repaired STATUS-or-CREATE_SHAPE reader. A valid mirrored server
tuple takes precedence over the parent predicate. If the strict reader returns
`None`, the result remains the parent STATUS tuple and authorizes no repair.

A server tuple proves only the first safe record produced inside that exact
request. Because CREATE-stage exceptions are deliberately recorded before the
existing list projection catches them, a CREATE-stage tuple is not by itself
proof that the same exception caused the HTTP status. Any tuple must undergo
ordered symbol-level cross-proof before a product repair is authorized. No
body, status value, business value, identifier, count, actor, exception
message or stack may be inspected or emitted.

## 26. Command-context HTTP-boundary diagnostic subcycle

Durable status-stage SHA `a7a74ac19e8a57092a27a4c6d9bb8cfc69db2172`
passes ordinary CI `32723750666`. The sole controlled diagnostic
`32724859319`, runtime `97423819933`, yields only
`P805_TOOL_ASSET_CONTEXT_STATUS / RuntimeError /
trace-73d2232109735af5a2bae6b434ee3c6e`; its strict mirrored reader returns no
trusted server tuple. The status-stage cycle is therefore immutable at
diagnostic `1/1`, repair `0/1`, final `0/1`, and no product repair is allowed.

The missing tuple leaves pre-handler/scope-log activation and the previously
unstaged API/repository read boundaries non-unique. A new independent
`command-context-http-boundary` subcycle starts at diagnostic `0/1`, repair
`0/1`, final `0/1`. Fixed parent codes distinguish only authorization,
not-found, other client, server and other response classes; they never expose
the actual status. Every non-success class uses the existing exact-trace
strict mirrored reader, where a valid server tuple wins and `None` retains the
parent class.

Each new server code wraps exactly one lexical query-context, repository read
or response-construction boundary. The same versioned exact GET/query scope,
innermost one-record state, same-exception propagation and finally restoration
apply. No response body, status value, business value, identifier, count,
actor, exception message or stack is inspected or emitted. Product writes,
call order, permission, transaction, API contracts, Schema, ownership,
profile, adapter, target and Gate behavior remain unchanged.

## 27. Command-context HTTP-boundary product repair

HTTP-boundary checkpoint `b38f3cf9f419c82b3552bdd5fd4dd58e5c182632`
passes ordinary CI `32727690270`. Its sole controlled diagnostic run
`32729074121`, runtime job `97437071555`, yields the unique safe tuple
`P805_TOOL_ASSET_CONTEXT_REQUEST_FIELDS / RequestValidationFailed /
trace-606876fcd3af5fe2bd258f8c8a8c94df`.

The stage contains one expression: the collection wrapper's unexpected-field
check. Pinned Frappe calls the whitelisted method from the complete
`form_dict`; its named query parameter is therefore both bound to the handler
argument and still visible to the shared field checker. The wrapper passed an
empty allowed set even though `acceptanceRevisionGlobalId` is its sole public
query field. BFF route parameters are held separately, the existing transport
field remains excluded by the shared helper, and the verifier already proves
an exact GET path with exactly that one URL-encoded query. The root is thus the
product wrapper's endpoint-specific normalization, not a verifier query,
route, header or authorization defect.

Repair `1/1` supplies the exact collection-only allowed set. The detail route
still supplies an empty set; unknown or additional business fields still
raise `RequestValidationFailed`; shared transport and security logic is not
relaxed. The diagnostic activation returns to `False`, while the strict
response-neutral mechanisms remain dormant. There is no API contract,
permission, Project-first authorization, transaction, Schema, ownership,
repository, adapter, target or Gate change. This cycle is now diagnostic
`1/1`, repair `1/1`, final `0/1`, pending exact-SHA ordinary and unchanged
final proof.

## 28. Post-query command-context diagnostic cycle

Repair exact SHA `9b36a2684e5ea20910ffdc6924177225f922abc2`
passes ordinary `32732876172`. Its sole unchanged final Level 3
`32734371042` passes repository `97453615222`, secret `97453615511`, governed
visual `97453615563`, frontend `97453615727` and controlled preflight
`97457924524`. Controlled runtime `97458015326` reaches only the constant-safe
parent boundary `P8-05 disposable command context is unavailable`.

The HTTP-boundary cycle is now immutable at diagnostic `1/1`, repair `1/1`,
final `1/1`. The repaired request-field predicate and exact verifier query are
excluded, but the fixed parent message cannot uniquely separate non-success,
items, create-context shape or target-profile failure. The repository,
projection and response boundaries after request-field normalization also
remain possible without an exact-trace server tuple. Product repair is
therefore prohibited.

An independent `post-query-command-context` cycle opens at diagnostic `0/1`,
repair `0/1`, final `0/1`. The historical activation stays `False`; one new
verifier activation is `True` and is selected only while the historical flag
is exactly false. It reuses the versioned exact GET/query scope, four ordered
parent predicates, fixed concrete HTTP class codes, all 31 unique server codes
and the strict mirrored-log reader. Success emits nothing; missing or invalid
trace is constant-safe; rejected log evidence cannot become attribution.
No response body, status value, business value, identifier, count, actor,
exception message or stack is inspected or emitted. Product/server code,
response, write order, permissions, transactions, Schema, ownership,
profiles, adapters, targets and Gate rules are unchanged.

## 29. Post-query mapped-fixture harness remediation

Post-query checkpoint `7dce210c95733a0f4a51ff3cca291fa4cb2a7c0d`
passes ordinary CI `32737660292`. Its sole controlled diagnostic run
`32739332564`, runtime job `97469915487`, returns the exact safe tuple
`P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING / ToolAssetExecutionStateConflict /
trace-187f44c7c5c3566080ea091825bb2b63`.

The unique stage calls the ordered mapping-expectation guard. The retained
physical Set already has the exact P8-01 authoritative read-only ERP Asset
projection and has no P8-05 mapping head before the first command. Therefore
create must reject existing observed mapping truth and update must reject the
missing P8-05 head. The collection intentionally catches both guarded
operations and returns `commandContexts: null`; this is the frozen product
contract, not a product failure.

The post-query cycle is immutable at diagnostic `1/1`, repair `0/1`, final
`0/1`. A bounded verifier-only remediation first proves the retained mapped
Set returns status 200, exact empty request items, the exact disposable
Synthetic profile and null command contexts, with an unchanged count-only
P8-05 execution-state snapshot and zero POST. It then constructs a distinct
disposable Master, customer-owned physical Set, Revision binding and
Acceptance through existing P6 APIs. That new Master has neither inherited
P8-01 Asset projection nor a fabricated P8-05 mapping head, so only
`create_tool_asset` may be projected and the original Synthetic worker,
terminal replay, zero formal ID and zero mapping-head proof executes there.

No product, API, permission, approval, transaction, Schema, ownership,
projection, mapping CAS, adapter, target or Gate rule changes. Missing,
duplicate, reused or tampered fixture identity remains fail-closed. The
temporary post-query diagnostic activation is `False`; dormant mechanisms
remain response-neutral. This remediation consumes no product repair.

## 30. Tooling Revision capability temporal verifier remediation

Exact verifier checkpoint `8bd6c886021f38fba57a8a1a96969b20e666c558`
passes ordinary CI `32744873147`. Its sole unchanged Level 3 run
`32748023307` passes repository `97498086283`, secret scan `97498086637`,
governed visual `97498086710`, frontend `97498086761` and controlled preflight
`97502370255`. Controlled runtime `97502584172` reaches the fixed verifier
boundary `P6-01 downstream unavailable truth drifted`.

The ordered workspace predicates prove status, top-level shape, Project
identity and permission truth before the downstream equality. Four downstream
entries remain statically unavailable. The only temporal entry is Tooling
Revision: P6 fresh and its P6-01 recovered/replay caller intentionally disable
the revision route, whereas the P6-03-through-P8 retained timeline enables it
and projects the closed available capability. The P8-05 disposable fixture
therefore reused a P6-fresh-only expectation; this is not product pollution.

A closed `ExpectedToolingRevisionCapabilityMode` keeps `UNAVAILABLE` as the
P6 default and permits only the three P8-05 disposable workspace assertions
to select `AVAILABLE`. Both branches lock all five downstream keys. The four
unchanged unavailable entries retain exact state/reason pairs; the available
revision branch requires exact keys, state, reason and a non-negative integer
count. Invalid modes, extra keys, booleans, negative counts and mismatched
states or reasons fail closed. There is no OR fallback.

The P8-05 disabled probe and retained mapped read passed. Only the disposable
Master command completed before the assertion; later disposable fixture
construction and the Tool Asset request/Outbox/worker proof did not run. The
post-query cycle remains immutable at diagnostic `1/1`, product repair `0/1`,
final `1/1`. This verifier-only correction does not change product, API,
permission, transaction, Schema, ownership, adapter, target or Gate behavior.

## 31. Post-revision-capability final cycle

Verifier-only remediation SHA
`93f2eb426285d9659036beee8542b8355956c899` passes exact ordinary CI
`32752050312`: frontend `97511036074`, secret scan `97511036317`, governed
visual `97511036345` and repository `97511036955` are successful. Ordinary
controlled jobs are correctly skipped.

The post-query cycle is immutable at diagnostic `1/1`, product repair `0/1`,
final `1/1`; its final run `32748023307` and runtime job `97502584172` remain
consumed evidence. The temporal verifier correction does not reopen that
cycle. A distinct `post-revision-capability` cycle begins at diagnostic `0/1`,
product repair `0/1`, final `0/1`, with all diagnostics still false and no
product, runtime, test, API, permission, transaction, Schema, ownership,
adapter, target or Gate change.

The durable checkpoint must first pass one exact-SHA ordinary CI. The new
cycle then permits exactly one unchanged `gate_mode=level_3` dispatch reusing
that ordinary run ID. Level 2 shortcuts, reruns and other workflows are not
allowed. Local/origin equality, diagnostics-off state, task/index cleanliness
and unrelated-change preservation are mandatory preconditions.

PASS requires all ordinary-equivalent jobs, the complete governed visual
matrix, controlled preflight and the cumulative P5-through-P8-05 disposable
runtime. The runtime must cross all three revision-capability assertions and
complete the distinct disposable Set/Acceptance, Tool Asset request and
Outbox worker, terminal replay, zero formal Asset identity, zero mapping head
and network-free Synthetic evidence. FAIL freezes final `1/1`; only the first
safe boundary may be inspected, and any new opaque root requires another
independent bounded cycle.

## 32. Disposable Engineering Part verifier correction

The sole post-revision-capability Level 3 run `32756343623` passes repository
`97524674080`, governed visual `97524674245`, secret scan `97524674303`,
frontend `97524674365` and controlled preflight `97528227277`. Controlled
runtime job `97528344980` stops at the fixed P6-01 boundary for the disposable
customer-owned Tooling Requirement POST. No response status, body, business
identifier, exception message or stack was inspected.

Static provenance proves the verifier supplied the retained P6 Tooling
Revision identity as `targetPartRevisionGlobalId`. The Requirement repository
requires a current `NPI Engineering Part Revision` belonging to the exact
Project before any write; the later Applicability requires that same Part
Revision. The retained `engineeringRevisionId` remains the established
Acceptance evidence input and is not a Part Revision. This is the unique
verifier fixture root, not a product, API or permission failure.

The post-revision-capability cycle is immutable at diagnostic `0/1`, product
repair `0/1`, final `1/1`. The bounded verifier correction resolves the
existing strict current Engineering Part context before the first disposable
write, requires a valid UUID distinct from the retained Tooling Revision, and
uses exactly that Part Revision for both Requirement and Applicability. A
missing, malformed or reused context fails before Master, Requirement,
Applicability, Set, Acceptance or worker writes. Retained Acceptance semantics
remain unchanged.

This consumes no product repair and changes no product, API, contract,
permission, transaction, Schema, ownership, adapter, target, diagnostic or
Gate behavior. A later durable checkpoint must open any further final cycle;
this correction does not rerun or reopen the consumed final dispatch.

## 33. Post-requirement-part-revision final cycle

Verifier-only correction SHA
`9aac7bd0184a3c08e2c5e1d0577467bac6cec265` passes exact ordinary CI
`32760161981`: repository `97536861375`, frontend `97536861638`, governed
visual `97536861679` and secret scan `97536861710` pass. The ordinary
controlled preflight and runtime jobs are correctly skipped.

The `post-revision-capability` cycle is immutable at diagnostic `0/1`, product
repair `0/1`, final `1/1`; run `32756343623` and runtime job `97528344980`
remain consumed evidence. The successful verifier correction does not reopen
or reclassify that cycle. A distinct `post-requirement-part-revision` cycle
begins at diagnostic `0/1`, product repair `0/1`, final `0/1`. All diagnostics
remain false and this durable state transition changes no runtime, test,
product, API, permission, transaction, Schema, ownership, adapter or target.

The new cycle permits exactly one diagnostics-off unchanged
`gate_mode=level_3` dispatch reusing ordinary `32760161981`. Level 2 shortcuts,
reruns and other workflows are forbidden. Local/origin exact-SHA equality,
all-diagnostics-false state, clean task paths/index and preservation of
unrelated changes are required preconditions.

PASS requires every ordinary-equivalent job, the complete governed visual
matrix, controlled preflight and cumulative P5-through-P8-05 runtime. The
runtime must cross the corrected disposable Requirement and Applicability and
then complete the physical Set, exact Revision binding, Acceptance, Tool Asset
request, atomic Outbox, leased worker, terminal replay, zero formal Asset IDs
and zero mapping head. A failure consumes final `1/1`; only its first safe
boundary may be read, without rerun or guessed repair.

## 34. Tool Asset create-response diagnostic cycle

Durable checkpoint `29957d7226130c69dd14ec6314af5ff122b8f415`
passes exact ordinary CI `32762106318`. Its sole unchanged Level 3 run
`32763677243` passes repository, frontend, secret scan, governed visual and
controlled preflight. Controlled runtime job `97551595519` stops at the fixed
parent boundary `P8-05 Synthetic command did not create one queued request`.
The corrected Requirement and Applicability, disposable physical Set, exact
Revision binding, Acceptance and create command context all completed first.

The parent predicate is ordered but compound: non-201 response, non-object
body, missing request shape, non-queued request state, noncanonical request
identity and noncanonical Outbox identity remain distinct possible first
boundaries. The POST repeats authentication, CSRF, Project containment,
approval/profile/source/mapping validation, atomic request/Outbox/guard/audit/
receipt writes, commit and response serialization. Static evidence cannot
select one product root. The `post-requirement-part-revision` cycle is therefore
immutable at diagnostic `0/1`, product repair `0/1`, final `1/1`; no repair or
rerun is authorized from that parent failure.

A distinct `tool-asset-create-response` cycle begins at diagnostic `0/1`,
product repair `0/1`, final `0/1`. Only its exact synthetic create POST sends
the versioned diagnostic scope, and the temporary verifier activation is
`True`; every historical diagnostic activation remains `False`. Six ordered
parent codes use only the shared validated `HttpResult.trace_id`. Unique API
and repository stages record at most one innermost three-key safe record and
rethrow the same exception. The strict mirrored-log reader accepts only the
exact trace and allowlist; a trusted server tuple wins, otherwise the fixed
parent tuple is retained.

The checkpoint does not inspect or emit response status values, bodies,
business values, identifiers, counts, actor, hashes, profiles, exception
messages or stacks. The enqueue-after-commit recovery catch remains outside
stage instrumentation. Success emits nothing; missing/invalid trace and
invalid/duplicate/mismatched log evidence fail closed. No response, write
value/order, permission, transaction, API, Schema, ownership, worker, adapter,
target or Gate behavior changes.

The first controlled dispatch `32812880293`, runtime job `97695558904`,
produces no allowlisted tuple because the parent verifier stopped at module
load. The controlled shell launches that verifier with `PYTHONPATH=scripts`,
while the checkpoint had introduced a top-level import from the integration
app package. The same invocation reproduces `ModuleNotFoundError` before any
HTTP request, server scope or product code. This is a diagnostic harness
failure within the same cycle; product diagnostic remains `0/1`, repair
remains `0/1`, and no product root is inferred.

The bounded remediation makes the parent verifier app-import-free again. It
owns a frozen literal copy of the response-neutral header, scope and server
allowlist. Unit tests compare that set both to the diagnostics module and to
the diagnostics source AST, while also enforcing one lexical product context
per code. A subprocess regression executes the real controlled parent shape
with `PYTHONPATH=scripts` and `--help`. Server/product diagnostics, activation,
API and transaction behavior are unchanged.

## 35. Tool Asset create HTTP-boundary diagnostic cycle

Harness-remediation SHA `80b16b8507f78d33be8b787ee8ce98362653cffc`
passes exact ordinary CI `32814218905`. Its sole product diagnostic dispatch
`32823780142`, runtime job `97727376777`, returns only the safe parent tuple
`P805_TOOL_ASSET_CREATE_HTTP_STATUS / RuntimeError /
trace-872ec1af140e54528d68f4fc07760c03`; the strict reader finds no trusted
server tuple. No response status value, body, business value, identifier,
count, actor, hash, profile, exception message or stack was inspected.

Static cross-proof uniquely attributes the missing server record to the
diagnostic activation boundary, not to a product root. Pinned Frappe calls the
whitelisted method with `frappe.form_dict`; because the create handler accepts
`**request_fields`, the framework transport field `cmd` is necessarily present
in `command_fields`. The old scope required exactly six business fields and
therefore always disabled its request-local state. The shared request-security
contract already treats only that exact transport field as non-business input
and continues to reject every unknown business field.

The `tool-asset-create-response` cycle is immutable at diagnostic `1/1`,
product repair `0/1`, final `0/1`. Its zero server tuple cannot authorize a
product repair. A distinct `tool-asset-create-http-boundary` cycle starts at
diagnostic `0/1`, product repair `0/1`, final `0/1`. The old verifier activation
is `False`; only the new exact synthetic POST scope is temporarily active.
Activation requires the exact framework command symbol and value plus exactly
the six business fields, exact POST route, empty query, trace and idempotency
header. It neither removes nor changes product input or shared security.

Non-201 responses are classified into fixed authorization, not-found, client,
server or other parent codes without emitting the actual status. Every class
uses the strict exact-trace mirrored reader; one fully valid existing 40-code
server tuple wins, otherwise the fixed parent class remains. Existing
innermost-one-record, same-exception, finally restoration, response
equivalence, zero-extra-write and no-leak contracts remain mandatory. No API,
permission, transaction, Schema, ownership, worker, adapter, target or Gate
behavior changes.

## 37. Tool Asset create pre-handler diagnostic cycle

Exact-SHA ordinary run `32826127517` passed before the sole controlled
diagnostic run `32827536675`. Runtime job `97738829480` produced only
`P805_TOOL_ASSET_CREATE_HTTP_SERVER_CLASS / RuntimeError /
trace-232bf416131b56f6a1d5f85ddd5aaab3`. The API diagnostic context is entered
before `execute_api` resolves the real request trace into `current_trace_id`,
so the absent server tuple uniquely identifies an activation-harness boundary
but does not identify a product root.

Freeze `tool-asset-create-http-boundary` at diagnostic `1/1`, product repair
`0/1`, final `0/1`. Open independent `tool-asset-create-prehandler` at
`0/1`, `0/1`, `0/1`. Only the new exact synthetic POST scope is active. It
strictly validates the real `X-Trace-ID` request header at entry and locks the
later response trace to exact equality; missing, malformed or stale context
cannot activate it. Historical create activations remain false.

The checkpoint reuses the existing 40 unique server stages, five fixed parent
HTTP classes and strict mirrored reader. Trusted server evidence wins;
otherwise the safe parent class remains. No response, input, permission,
transaction, Schema, ownership, worker, adapter, target or Gate behavior is
changed, and output remains limited to code, exception class and exact trace.

## 38. Tool Asset Request reciprocal Outbox Link repair

The sole create-prehandler dispatch `32870596890` passed controlled preflight
job `97876378188`. Runtime job `97876504805` yielded exactly
`P805_TOOL_ASSET_CREATE_REQUEST_INSERT / LinkValidationError /
trace-34f2a48309bb58938b17fc35f6abc160`. The Request metadata has seven Link
fields and no Dynamic Link. Project, disposable Master, physical Set, Tooling
Revision and Acceptance Evidence Revision had already been inserted and
strictly read, while the result Link was empty. The generated Outbox event was
the sole absent Link because the frozen atomic order inserts the Request before
the reciprocal Outbox row. The exact exception class proves the insert stopped
at Frappe's pinned Link-validation boundary rather than a domain predicate.

The product repair consumes this cycle's sole repair allowance. It reuses the
proven Item/MBOM bounded forward-reference seam, scoped only to one dispatched
execution-v2 `NPI Tool Asset Request` carrying a canonical generated Outbox
identity. The previous document flag is restored in `finally`; wrong DocType,
missing flags, Mock/no-Outbox, malformed identity or an insertion exception
fails closed. No fixture or Link is fabricated and no general `ignore_links`
or permission path is opened.

Request, reciprocal Outbox, guard activation, audit and receipt retain their
exact order and one transaction. Metadata, event and payload hashes, API,
permission, ownership, worker, adapter, target and Gate contracts are
unchanged. PREHANDLER activation is false and its response-neutral mechanism
is dormant. Freeze this cycle at diagnostic `1/1`, repair `1/1`, final `0/1`.

## 39. Post-link Tool Asset create diagnostic cycle

Repair SHA `b66d97af946afb9a2f4d936953cd0214e46e51a3` passes exact
ordinary CI `32872788473`. Its sole unchanged diagnostics-off Level 3
`32874043388` passes all non-runtime jobs; controlled runtime job
`97892173555` stops at the same fixed queued-request parent boundary after the
reciprocal Outbox Link repair. The repaired LinkValidationError source is
therefore excluded, but the remaining downstream request, Outbox, guard,
audit, receipt, outcome, commit, problem and response boundaries are not
statically unique.

Freeze `tool-asset-create-prehandler` at diagnostic `1/1`, product repair
`1/1`, final `1/1`. Open a distinct `post-link-tool-asset-create` cycle at
diagnostic `0/1`, product repair `0/1`, final `0/1`. The new verifier activation
alone is `True`; PREHANDLER and all historical diagnostics are `False`.

The bounded checkpoint reuses the proven exact synthetic POST scope, exact
request/response trace correlation, five parent HTTP classes, all 40 unique
server stages and the strict mirrored reader. A trusted server tuple wins;
otherwise the fixed parent code remains. Success emits nothing, and missing or
invalid trace plus malformed, duplicate or mismatched log evidence fails
closed. Output contains only diagnostic code, exception class and exact trace,
never status/body/business values/identifiers/count/actor/hash/profile/message/
stack. Product, server, response, write order, permission, transaction, API,
Schema, ownership, worker, adapter, target and Gate behavior are unchanged.

## 40. Post-link Tool Asset source-hash repair

The sole post-link diagnostic run `32878609864` passes controlled preflight
`97902474357`; runtime job `97902976741` yields exactly
`P805_TOOL_ASSET_CREATE_REQUEST_INSERT / ValidationError /
trace-439587c04656513091543ad4cc160235`. No response status/body, business
value, identifier, count, exception message or stack was read.

Pinned Frappe runs Link validation before `before_insert`, `before_validate`
and controller `validate`. The former reciprocal Link root is therefore
closed. The Tool Asset source domain computes `source_hash` over
`source_payload()`, then appends `sourceStreamKeyHash` and `sourceHash` to the
canonical mapping. The controller's first hash predicate incorrectly hashed
that expanded mapping again. Its generic ValidationError is the unique first
post-Link failure; mandatory, Link and length errors use distinct exception
classes and standard field validation runs later.

The one product repair replaces only that expected value with the already
strictly rebuilt domain source's approved `source_hash`. It does not change
the source payload, persisted hash, approval/mapping/payload hash predicates,
predicate order, immutable truth or later exact physical-Set checks. Nested
and supplied tampering continues to fail before any write.

`POST_LINK_TOOL_ASSET_CREATE_DIAGNOSTICS_ENABLED=False`, and the dormant
mechanism neither sends scope nor reads logs. Freeze the cycle at diagnostic
`1/1`, product repair `1/1`, final `0/1`. No repository write order, response,
API, permission, transaction, Schema, ownership, worker, adapter, target or
Gate contract changes.

## 41. Post-source-hash Tool Asset create diagnostic cycle

Source-hash repair SHA `01e34ddd3e8f3fabbda5f3a980db771a174d27d8`
passes exact ordinary run `32880787908`. Its sole diagnostics-off Level 3
`32882305076` passes every non-runtime job and controlled preflight. Controlled
runtime job `97917870416` stops at the fixed queued-request parent boundary
before the worker is invoked.

Freeze `post-link-tool-asset-create` at diagnostic `1/1`, product repair `1/1`,
final `1/1`. Both the reciprocal Outbox Link and approved source-hash roots are
closed. Static ordering leaves later Request lifecycle, Outbox, guard, audit,
receipt, outcome, commit and response boundaries non-unique, so no guessed
product repair is permitted.

Open independent `post-source-hash-tool-asset-create` at diagnostic `0/1`,
product repair `0/1`, final `0/1`. Only the new verifier activation is true;
POST_LINK and all historical diagnostics are false. The checkpoint reuses the
exact pre-handler POST scope, exact response trace, five fixed HTTP classes,
ordered 201 response-shape checks, all 40 unique server stages and the strict
mirrored reader. A trusted exact-trace server tuple wins; otherwise the fixed
parent code remains. Missing/invalid trace and malformed, duplicate or
mismatched records fail closed.

Diagnostic output is only code, exception class and validated trace. It never
includes response status/body, business values, identifiers, count, actor,
hash, profile, exception message or stack. Product, server, response, write
order, API, permission, transaction, Schema, ownership, worker, adapter,
target and Gate behavior remain unchanged.

## 42. Execution-v2 receipt response identity repair

The sole post-source-hash diagnostic run `32886668058` passes preflight
`97928618343`; controlled runtime `97928721598` returns exactly
`P805_TOOL_ASSET_CREATE_RECEIPT_INSERT / ValidationError /
trace-430d312ef8e2542e9c1b244874b96b6c`.

The repository constructs an execution-v2 sealed receipt only after the exact
Request, reciprocal Outbox, stream guard and audit pass. Its schema, operation,
request parent, actor and canonical hashes come from the same frozen command.
Pinned Frappe lifecycle ordering and the exact exception class exclude
mandatory and Link checks. Unlike the earlier P6 legacy insert/seal save, this
insert has no before-document, so `None` versus database `0` immutable
normalization is not on the failing path.

The first failing controller predicate used the legacy receipt response shape:
top-level `globalId` and `payloadHash`. The execution-v2 response contract uses
top-level `requestGlobalId` plus nested `request.payloadHash`, so the first
legacy identity lookup necessarily failed before response-hash validation.

The sole product repair branches only on the established `_is_execution_v2()`
contract. Execution-v2 strictly validates its top-level request identity,
mapping request body and nested payload hash against the exact parent Request;
legacy retains its original top-level identity and payload hash. Response hash
and canonicalization, immutable fields, one-way seal, capability, API,
transaction and receipt order are unchanged. Missing, wrong or malformed
identity and either payload or response-hash tampering remain ValidationError
with zero write.

POST_SOURCE_HASH activation is false and dormant. Freeze
`post-source-hash-tool-asset-create` at diagnostic `1/1`, product repair `1/1`,
final `0/1`.

## 43. Tool Asset worker-downstream diagnostic cycle

Receipt-repair SHA `a8847cde360f5827fdcdeee8f3d54e0fb843f1b7`
passes exact ordinary CI `32888545597`. Its sole diagnostics-off Level 3
`32889896367` passes secret, repository, visual, frontend and controlled
preflight jobs. Controlled runtime job `97942689801` returns only the fixed
`P8-05 Bench fixture failed` boundary; the failed child output, response body,
business values, identifiers, exception message and stack were not inspected.

The create response contract passed before the child was launched, while the
parent post-worker result and terminal-detail checks were not reached. The
remaining child sequence spans fixture identity, requester session, the full
worker route/claim/profile/boundary/adapter/seal/recovery operation,
post-worker request and field reads, outcome and truth assertions, terminal
replay, recoverable proof and fixture commit. No one product symbol is proven.

Freeze `post-source-hash-tool-asset-create` at diagnostic `1/1`, product
repair `1/1`, final `1/1`. Open independent
`tool-asset-worker-downstream` at `0/1`, `0/1`, `0/1`. The new verifier flag
alone is true; all historical diagnostics remain false.

The checkpoint has seventeen unique `P805_TOOL_ASSET_WORKER_*` lexical stage
codes and fourteen closed return-state/shape codes. `synthetic_verified` is
the only zero-diagnostic success. The exact successful create trace is passed
to the child, safe-log cursors are captured before launch, and each stage
records only code, exception class and validated trace before rethrowing the
same exception. The strict mirrored reader accepts a single record or two
identical handler mirrors as one logical tuple; every missing, duplicate,
divergent, extra-key, invalid-type, wrong-trace or disallowed record fails
closed to the constant parent boundary.

Failed child stderr remains discarded and its temporary stdout is never read;
only a successful child may parse JSON. This is verifier-only recovery
evidence. It changes no product worker, repository, adapter, request, response,
permission, transaction, Schema, ownership, target or Gate behavior.

## 44. Tool Asset worker-downstream request-truth repair

Checkpoint SHA `4cdaad168e44c635fc3ea302e5fd64a32672daf7` passes
ordinary `32893286981`. Controlled run `32894841539`, runtime job
`97955050412`, produced one safe tuple:
`P805_TOOL_ASSET_WORKER_PROCESS_OUTBOX / ValidationError /
trace-4321d8aae6905b94bf50d8ffbaa34c99`.

The create transaction had persisted an immutable executable Request snapshot
at `queued`, optimistic version `1`. During a fresh claim the Attempt insert
and the Outbox `pending -> processing` save are valid and precede the Request
save. The repository then advances the live Request to `processing`, version
`2`. The controller's exact comparison of snapshot state/version to live
state/version made that Request save the unique first failing predicate. The
receipt is not written by the worker, and profile/registry and
adapter/classification failures are caught and converted, so the prior
reciprocal-link, source-hash and receipt roots are excluded.

The repair preserves the immutable create snapshot and hash bit-for-bit:
executable snapshots remain `queued/1`, Mock snapshots remain
`validated_mock/1`. Live state uses the existing one-way transition table and
live optimistic version advances exactly by one. Invalid transitions,
version skips/regressions, snapshot state/version changes and other immutable
tampering remain fail-closed with no recorded write. No API, permission,
capability, transaction, Schema, ownership, worker order, adapter or target
contract changes.

`TOOL_ASSET_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED=False`; dormant verification
does not read safe-log cursors or logs. Freeze this cycle at diagnostic `1/1`,
product repair `1/1`, final `0/1` pending unchanged Level 3.

Level 1 passes Tool Asset `114/114`, P6 tooling `355/355` plus request-domain
`4/4`, Item `146/146`, MBOM `126/126`, and current/reconciliation `33/33`.
Compile, shell syntax, diagnostic-off, exact-eight manifest, unauthorized ninth
path rejection and diff checks also pass. The repair awaits exact-SHA ordinary
CI; no Site or final Gate has been dispatched.

## 45. Post-snapshot Tool Asset worker diagnostic cycle

Request-truth repair SHA `180c1d1fe763a751af9c03f029e2fade38eba500`
passes ordinary `32896971241`. Its unchanged diagnostics-off Level 3
`32898202901` passes visual, frontend, repository, secret scan and controlled
preflight. Controlled runtime job `97969711766` returns only the fixed
`P8-05 Bench fixture failed` boundary; result recording and artifact upload are
skipped and cleanup succeeds. Failed-child stdout/stderr, response data,
business values, identifiers, exception messages and stacks were not read.

The create contract passes before child launch. Deterministic fixture identity,
the explicit requester session and the repaired Request snapshot/live-state
predicate are closed by unchanged inputs and the pinned lifecycle tests. The
outer process context still spans claim commit, profile, boundary, adapter,
classification, seal and recovery, while no parent evidence proves entry into
the later request/field reads, outcome/truth checks, replay, recoverable proof
or fixture commit. A new product repair would therefore be a guess.

Freeze `tool-asset-worker-downstream` at `1/1`, `1/1`, `1/1`. Open independent
`post-snapshot-tool-asset-worker` at `0/1`, `0/1`, `0/1`. Only
`POST_SNAPSHOT_TOOL_ASSET_WORKER_DIAGNOSTICS_ENABLED=True`; the historical
worker and all other diagnostic flags remain false. The checkpoint reuses the
existing seventeen stage and fourteen outcome/shape codes without adding a
code. The exact created trace and pre-child cursors feed the same safe logger
and strict mirrored reader. Missing, duplicate, divergent, wrong-trace,
extra-key, invalid-type or disallowed evidence falls back to the constant.
`synthetic_verified` emits nothing. Failed child stderr remains discarded and
stdout remains unread; successful child JSON is parsed only after zero exit.

This verifier-only checkpoint changes no worker, repository, adapter, API,
permission, transaction, Schema, ownership, target or Gate behavior.

Level 1 passes Tool Asset `114/114`, P6 acceptance/runtime `63/63`, Item
`146/146`, MBOM `126/126`, and current/reconciliation `33/33`. Compile, shell
syntax, exact-five manifest, unauthorized sixth path rejection and diff checks
also pass.

## 46. Tool Asset process-stage diagnostic cycle

Post-snapshot checkpoint SHA `8376f62ec88e6be439fde49c162f24d67f17a90f`
passes exact ordinary CI `32901049838`. Its sole controlled diagnostic Site
`32902381446`, runtime job `97978983425`, returns exactly
`P805_TOOL_ASSET_WORKER_PROCESS_OUTBOX / TypeError /
trace-217bee3b702e52be8658f9afc089cda3`. Failed-child stdout/stderr, response
data, business values, identifiers, exception messages and stacks were not
read or emitted.

The outer process predicate remains composite. Service-route failures are
caught as not-claimed, while profile, registry, adapter and classification
failures are converted to explicit failed or uncertain results. A raw
`TypeError` can still originate in actor entry, claim reads/rebuild/writes/
return, commits, failure or uncertain result construction, adapter-boundary
writes, terminal sealing/recovery or the response build. The tuple therefore
does not uniquely prove a product repair.

Freeze `post-snapshot-tool-asset-worker` at diagnostic `1/1`, product repair
`0/1`, final `0/1`. Open independent `tool-asset-process-stage` at diagnostic
`0/1`, product repair `0/1`, final `0/1`. Only
`TOOL_ASSET_PROCESS_STAGE_DIAGNOSTICS_ENABLED=True`; the post-snapshot worker
flag and every historical diagnostic activation are false.

The checkpoint adds fifty-two fixed, uniquely placed process codes spanning
actor, claim reads/build/writes/return, commit, failure conversion, boundary,
uncertain/result persistence, terminal seal/recovery and response. The exact
created trace is carried in request-local scope. The innermost failing context
records at most one exact three-key safe tuple, restores prior scope in
`finally`, and rethrows the same exception. Expected caught and recovered
paths emit no record. No write value, order, transaction or catch behavior is
changed.

The parent keeps the established strict mirrored reader and captures cursors
before child launch. Failed-child stderr remains discarded and stdout remains
unread; only a successful child may parse JSON. Product response, permission,
Schema, ownership, adapter, target and Gate behavior remain unchanged.

Level 1 passes Tool Asset `118/118`, P6 tooling `355/355` plus Tool Asset
request-domain `4/4`, Item `146/146`, MBOM `126/126`, and current-task/
reconciliation `33/33`. The fifty-two-code lexical/equality contract, direct
SQL/network and TODO/secret scans, `py_compile`, current/reconciliation
scripts, exact-ten manifest with an unauthorized eleventh path rejected, and
diff hygiene all pass.

## 47. Tool Asset boundary Attempt datetime repair

Process-stage checkpoint SHA `a4f8709cf12629b267f349478a8677c68f751c83`
passes ordinary `32904854534`. Its sole controlled diagnostic Site
`32906055265`, runtime job `97990383427`, yields exactly
`P805_TOOL_ASSET_PROCESS_BOUNDARY_TRANSACTION / TypeError /
trace-dc72892e93f052daa0ad34f7290b0356` without reading failed-child output or
exposing response data, values, identifiers, counts, messages or stacks.

The same claim capability and context manager completed moments earlier.
Boundary profile and current-claim reads passed, while every save and audit has
a more specific inner stage. The first unwrapped call is the Attempt snapshot
rebuild. Claim builds that snapshot from canonical database datetime strings;
Frappe then hydrates the persisted `Datetime` fields to datetime objects.
The boundary rebuild passed the hydrated object directly to standard JSON
canonicalization, which cannot serialize datetime and therefore raised the
observed TypeError before any boundary write.

Product repair `1/1` normalizes only `started_at` and nonempty `finished_at`
through the existing `_db_datetime` helper before hashing. Initial DB strings,
naive hydrated datetimes and aware datetimes resolve to the same canonical DB
text and hash. All other snapshot fields, transaction/capability boundaries,
permission checks and attempt -> Outbox -> audit order remain unchanged;
invalid datetime truth fails closed before a write.

`TOOL_ASSET_PROCESS_STAGE_DIAGNOSTICS_ENABLED=False`; the mechanism remains
dormant and reads no cursor/log. Freeze `tool-asset-process-stage` at
diagnostic `1/1`, product repair `1/1`, final `0/1`.

Level 1 passes Tool Asset `121/121`, P6 tooling `355/355` plus Tool Asset
request-domain `4/4`, Item `146/146`, MBOM `126/126`, and current-task/
reconciliation `33/33`. All-diagnostics-off, direct-SQL/network and
TODO/secret scans, `py_compile`, current/reconciliation scripts, exact-seven
manifest with an unauthorized eighth path rejected, and diff hygiene pass.

## 48. Post-Attempt-snapshot Tool Asset process diagnostic cycle

Attempt datetime repair SHA `722d47d42f61fbee9ad5b8152bb14c4012ad7ee3`
passes exact ordinary CI `32907447942`. Its sole diagnostics-off Level 3
`32908387565`, runtime job `98000359305`, passes create and launches the Bench
worker child, then stops at the fixed `P8-05 Bench fixture failed` boundary.
The result and artifact steps are skipped, cleanup succeeds, and failed-child
stdout/stderr, response data, business values, identifiers, counts, exception
messages and stacks are not read or emitted.

The prior tuple already proved actor entry, the normal claim reads/rebuild/
writes/return and commit, and boundary profile/current-claim reads. The repair
uniquely closes hydrated Attempt datetime canonicalization without changing an
upstream input or branch. The current failure remains non-unique across the
remaining boundary saves/audit/commit, adapter classification, result
persistence, seal/recovery and response build. No product repair is proven.

Freeze `tool-asset-process-stage` at diagnostic `1/1`, product repair `1/1`,
final `1/1`. Open independent
`post-attempt-snapshot-tool-asset-process` at diagnostic `0/1`, product repair
`0/1`, final `0/1`. Only
`POST_ATTEMPT_SNAPSHOT_TOOL_ASSET_PROCESS_DIAGNOSTICS_ENABLED=True`;
`TOOL_ASSET_PROCESS_STAGE_DIAGNOSTICS_ENABLED` and every historical
diagnostic activation are false.

The verifier reuses the exact existing fifty-two process codes and server
lexical contexts, successful create trace, pre-child safe-log cursors,
request-local scope, innermost-one-record behavior, same-exception rethrow and
strict mirrored reader. Failed-child stderr stays discarded and stdout stays
unread; successful zero-exit child output alone may be parsed and emits no
diagnostic. No worker, repository, adapter, API, permission, transaction,
Schema, ownership, target or Gate behavior changes.

Level 1 passes the focused verifier `37/37`, complete Tool Asset
worker/repository/API/security/metadata suite `123/123`, P6 tooling `355/355`
plus Tool Asset request-domain `4/4`, Item `146/146`, MBOM `126/126`, and
shared HTTP/current-task/reconciliation `39/39`. Fifty-two-code
AST/equality/lexical uniqueness, direct-SQL/target-network and weakening-marker
scans, compile and shell syntax, current/reconciliation scripts, exact-five
manifest with an unauthorized sixth path rejected, and diff hygiene pass.

## 49. Post-Attempt-snapshot Result datetime repair

Post-Attempt-snapshot checkpoint SHA
`590b90e16c10056d7da0e9dd54c022e22b54b351` passes exact ordinary CI
`32910964897`. Its sole controlled diagnostic Site `32912119252`, runtime job
`98008349085`, yields exactly
`P805_TOOL_ASSET_PROCESS_SEAL_RESULT_INSERT / OperationalError /
trace-705e1e4f9e395a8282b8f4c5c3f086d1`. Failed-child stdout/stderr, response
data, business values, identifiers, counts, exception messages and stacks were
not read.

The exact inner stage starts only after result lookup, preparation,
transaction entry and Frappe document construction. The prior `SELECT *`
result lookup proves the migrated Result table is addressable. Link,
permission, mandatory and controller predicates execute before `db_insert`
and have distinct fail-closed exception classes. Pinned Frappe v15 serializes
JSON dictionaries but leaves an already-string `Datetime` unchanged. The
Result writer alone passed canonical ISO `observedAt` text ending in `Z`
straight into the MariaDB `Datetime` column, whereas the working Item and MBOM
peers and every other Tool Asset datetime write use the existing canonical
`_db_datetime` boundary. This is the unique first SQL source consistent with
the exact OperationalError.

Product repair `1/1` normalizes only persisted `observed_at` columns through
`_db_datetime` in the Result, Field Result and Mapping Observation snake-case
adapters. Those three rows share the same proven root; their immutable JSON
snapshots retain exact ISO `observedAt` and all canonical hashes remain
bit-for-bit unchanged. Write order, transaction/capability, permission,
metadata, API, ownership, mapping CAS and worker behavior are unchanged;
invalid datetime truth remains fail closed before a write.

`POST_ATTEMPT_SNAPSHOT_TOOL_ASSET_PROCESS_DIAGNOSTICS_ENABLED=False`; the
fifty-two-code mechanism remains dormant and reads no cursor/log. Freeze
`post-attempt-snapshot-tool-asset-process` at diagnostic `1/1`, product repair
`1/1`, final `0/1`.

Level 1 passes focused repository/runtime `48/48`, complete Tool Asset
`124/124`, P6 tooling `355/355` plus Tool Asset request-domain `4/4`, Item
`146/146`, MBOM `126/126`, and current-task/reconciliation `33/33`.
All-diagnostics-off, direct-SQL/target-network/submit-BOM scans, compile,
current/reconciliation scripts, exact-seven manifest with an unauthorized
eighth path rejected, and diff hygiene pass.

## 50. Post-Result-datetime Tool Asset process diagnostic cycle

Result datetime repair SHA
`398cd326339f2dae146380be239940d7f00dc35e` passes exact ordinary CI
`32913836338`. Its sole diagnostics-off Level 3 `32914798761` passes secret,
repository, frontend, governed visual and controlled preflight jobs. Controlled
runtime job `98019105211` initializes the pinned Bench and disposable Site,
then stops at the fixed cumulative P5-through-P8-05 runtime step. Result and
runtime-artifact steps are skipped and cleanup succeeds. Failed-child
stdout/stderr, response data, business values, identifiers, counts, exception
messages and stacks were not read.

The repair closes the exact ISO-`Z` Datetime boundary for Result, Field Result
and Mapping Observation, as well as the earlier hydrated Attempt datetime
root. The diagnostics-off cumulative boundary cannot prove this run entered
the Tool Asset child, and, if it did, remaining Result SQL constraints, Field
Result/Mapping persistence, Attempt/Request/Outbox/Guard/Audit saves, commits,
recovery, outcome and response contexts remain non-unique. No next product
repair is proven.

Freeze `post-attempt-snapshot-tool-asset-process` at diagnostic `1/1`, product
repair `1/1`, final `1/1`. Open independent
`post-result-datetime-tool-asset-process` at diagnostic `0/1`, product repair
`0/1`, final `0/1`. Only
`POST_RESULT_DATETIME_TOOL_ASSET_PROCESS_DIAGNOSTICS_ENABLED=True`; every
historical activation is false.

The verifier reuses the exact fifty-two existing process codes, successful
create trace, pre-child log cursors, request-local scope, innermost-one-record
behavior, same-exception rethrow and strict mirrored reader. Failed-child
stderr remains discarded and stdout unread; successful zero-exit output alone
may be parsed and emits no diagnostic. No product worker, repository,
diagnostics, API, permission, transaction, Schema, ownership, adapter, target
or Gate behavior changes.

Level 1 passes focused runtime verifier `38/38`, complete Tool Asset `125/125`,
P6 Tooling `355/355`, Tool Asset request-domain `4/4`, Item `146/146`, MBOM
`126/126`, and current-task/reconciliation `33/33`. Exact-52 code equality and
unique lexical contexts, strict shared-reader and failed-child-output contracts,
Python compile, shell syntax, direct-SQL/target-network/submit/TODO scans,
current/reconciliation scripts and diff hygiene pass. Runtime verifiers expose
twenty-nine diagnostic flags: only the new post-Result-datetime flag is true.
The post-commit manifest accepts exactly the five authorized paths and rejects
an unauthorized sixth path. Product code remains unchanged.

### Post-Result-datetime diagnostic result and repair 1/1

Checkpoint SHA `fdff0c0c9caf5cefe8ce3794e2ddf5cd7b504419` passes exact
ordinary CI `32917091959`. The single controlled diagnostic run `32918081992`,
runtime job `98025953304`, yields only the strict tuple
`P805_TOOL_ASSET_PROCESS_SEAL_OUTBOX_SAVE / ValidationError /
trace-668631acc1b252ff98c23d16fe27082d`. Preflight, pinned Bench, disposable
Site and cleanup pass. Failed-child output, response/business values,
identifiers, counts, exception messages and stacks remain unread.

The source is unique. Synthetic execution classifies every valid field as
`synthetic_verified`, aggregates the request to the same state, and
`_outbox_state()` preserves it. Result, Field, Mapping, Attempt and Request
writes completed before the Outbox save. At that save the v3 controller's
ordered first failing predicate is `processing -> synthetic_verified`, because
both `_TOOL_ASSET_STATES` and the DocType Select metadata omitted this already
contracted terminal state. The later terminal-state shape check would reject
the same state independently. No other controller predicate can be the first
source.

Repair only the shared additive Outbox v3 state allowlist and Select option so
`processing -> synthetic_verified` is terminal. Pinned controller lifecycle
tests require complete claim history and a result reference, and continue to
reject pending-to-synthetic, an unrelated state and a missing result. No
payload/hash, permission, transaction, ownership, API, adapter, mapping, claim,
lease, replay or write-order behavior changes. Freeze the independent cycle at
diagnostic `1/1`, product repair `1/1`, final `0/1`; set
`POST_RESULT_DATETIME_TOOL_ASSET_PROCESS_DIAGNOSTICS_ENABLED=False` and retain
the diagnostic mechanism dormant.

Level 1 passes focused controller/runtime `47/47`, complete Tool Asset
`126/126`, P6 Tooling `355/355`, request-domain `4/4`, Item `146/146`, MBOM
`126/126`, and current-task/reconciliation `33/33`. All twenty-nine runtime
diagnostic flags are false. JSON metadata parse, exact real-controller
lifecycle, Python compile, shell syntax, direct-SQL/target-network/submit/TODO
scans, current/reconciliation scripts and diff hygiene pass. The exact-eight
post-commit manifest passes and rejects an unauthorized ninth path.

## 51. Post-synthetic-Outbox Tool Asset process diagnostic cycle

Synthetic Outbox repair SHA
`f117cf422ac2e6cdf2c55382689c7d95280182e5` passes exact ordinary CI
`32919368662`. Its sole diagnostics-off Level 3 `32920304450` passes secret,
repository, frontend, governed visual and controlled preflight. Controlled
runtime job `98034836197` passes pinned Bench and disposable Site setup, then
stops at the cumulative P5-through-P8-05 runtime step. Result and runtime
artifact steps skip and cleanup succeeds. Failed-child stdout/stderr,
response/business values, identifiers, counts, exception messages and stacks
were not read.

The synthetic Outbox terminal transition and metadata defect is closed. The
ordinary lanes, controlled preflight and Bench/Site setup also pass. The
remaining diagnostics-off boundary neither proves Tool Asset child entry nor
distinguishes the exact process stages, worker postconditions, replay and
recoverability checks, parent outcome, terminal projection or later retained
runtime checks. A further product repair would be a guess and is prohibited.

Freeze `post-result-datetime-tool-asset-process` at diagnostic `1/1`, product
repair `1/1`, final `1/1`. Open independent
`post-synthetic-outbox-tool-asset-process` at diagnostic `0/1`, product repair
`0/1`, final `0/1`. Only
`POST_SYNTHETIC_OUTBOX_TOOL_ASSET_PROCESS_DIAGNOSTICS_ENABLED=True`; all
historical activations are false.

The verifier reuses the exact fifty-two existing process codes, successful
create trace, pre-child log cursors, request-local scope, strict mirrored
reader, innermost-one-record, same-exception/finally, failed-child-output-unread
and success-zero contracts. Product worker, repository, diagnostics, API,
permission, transaction, Schema, ownership, adapter, target and Gate behavior
have zero diff.

Level 1 passes focused runtime verifier `39/39`, complete Tool Asset `127/127`,
P6 Tooling plus request-domain `359/359`, Item `146/146`, MBOM `126/126`, and
current-task/reconciliation `33/33`. Exact-52 code equality and unique lexical
contexts, strict shared reader, failed-child stdout/stderr unread,
same-exception/scope, Python compile, verifier executable, shell syntax,
JSON/YAML parse, security-negative/TODO scans, current/reconciliation and diff
hygiene pass. Runtime verifiers expose thirty diagnostic flags and only the new
post-synthetic-Outbox flag is true. The exact-five post-commit manifest passes
and rejects an unauthorized sixth path; product/frontend/contracts have zero
diff.

## 52. Post-synthetic-Outbox Tool Asset worker-parent diagnostic cycle

Checkpoint SHA `ebd5384a7c1875171b8e103764a721e768c269c5` passes exact
ordinary CI `32922315867` with repository `98038152844`, governed visual
`98038152937`, frontend `98038152950` and secret scan `98038152959` all
successful. The sole controlled run `32923258310` passes preflight
`98040916983`; runtime job `98040974787` reaches the Tool Asset
`exercise_worker` child, which returns nonzero. The strict exact-52 mirrored
reader returns no tuple. Failed-child stdout/stderr, response and business
values, identifiers, counts, exception messages and stacks remain unread.

This zero tuple is fail-closed evidence. The parent emits its generic Bench
fixture failure only after a nonzero `exercise_worker` child return, excluding
all earlier cumulative phases, Tool Asset create and child dispatch. The
process-only activation cannot record the existing seventeen fixture stages
or fourteen outcome/shape classifiers. It therefore cannot distinguish a
non-success process return from a post-process fixture assertion, and no
product repair is justified.

Freeze `post-synthetic-outbox-tool-asset-process` at diagnostic `1/1`, product
repair `0/1`, final `0/1`. Open independent
`post-synthetic-outbox-tool-asset-worker-parent` at `0/1,0/1,0/1`. Only
`POST_SYNTHETIC_OUTBOX_TOOL_ASSET_WORKER_PARENT_DIAGNOSTICS_ENABLED=True`;
the prior process activation and all historical flags are false. Reuse the
exact thirty-one existing worker stage/outcome codes, created trace,
pre-child cursors, strict mirrored reader, same-exception/finally,
failed-child-output-unread and success-zero contracts. Product, server,
frontend, contracts, transaction and worker order remain unchanged.

Level 1 passes focused verifier `40/40`, complete Tool Asset `128/128`, P6
Tooling `355/355` plus request-domain `4/4`, Item `146/146`, MBOM `126/126`,
and current-task/reconciliation `33/33`. Exact-31 equality and lexical
coverage, strict shared-reader behavior, failed-child stdout/stderr unread,
success-zero, compile, executable, shell, JSON/YAML, security-negative/TODO,
current/reconciliation and diff checks pass. Runtime verifiers expose
thirty-one diagnostic flags and only the worker-parent flag is true. The
exact-five manifest passes and rejects an unauthorized sixth path.

### Worker-parent result and synthetic terminal replay repair

Checkpoint SHA `a5840dcba90d7d06fefb6da84d134c0b6d571c31` passes exact ordinary
`32924661379`. Controlled run `32925635182`, runtime job `98047912734`, yields
the sole allowlisted tuple `P805_TOOL_ASSET_WORKER_TERMINAL_REPLAY /
RuntimeError / trace-d603365eaca85769bee5c61299eb8a49`; failed-child and
prohibited content remain unread.

The completed first process and intervening request/field assertions prove
the persisted terminal value is `synthetic_verified`. Replay enters the same
repository, whose private terminal set omits only this already-contracted
state. The terminal branch is skipped and the next active-state predicate is
therefore the unique first source. Add only `synthetic_verified` to that set.
The existing `_require_terminal_truth` request/result/guard checks remain
mandatory before replay returns not-claimed; no redispatch or write occurs.

Freeze this cycle at `1/1,1/1,0/1`. Disable the worker-parent activation and
keep every runtime diagnostic dormant. No Schema, API, permission,
transaction, ownership, adapter, mapping or worker-order behavior changes.

Level 1 passes complete Tool Asset `131/131`, P6 Tooling `355/355` plus
request-domain `4/4`, Item `146/146`, MBOM `126/126`, and
current-task/reconciliation `33/33`. Real terminal claim/truth failure,
write-free public replay, zero redispatch, compile, executable, shell,
JSON/YAML, security-negative, current/reconciliation and diff checks pass.
All thirty-one runtime diagnostic flags are false. The exact-eight manifest
passes and rejects an unauthorized ninth path.

## 53. Ordinary P8-01 loading harness remediation

Synthetic-terminal replay repair SHA
`5c2e7b252fc9259c9ba772eef005ce685e78beed` reaches exact ordinary CI
`32926690741`. Repository `98050949937`, secret scan `98050949942` and
governed visual `98050949808` pass. Frontend `98050949978` passes 453 of 454
E2E cases and fails only the existing P8-01 loading-state observation. The
exact-eight repair contains no frontend path.

The failure has one harness source. The projection route released its mock
after a fixed 450 ms; that wall-clock interval starts at interception and can
expire before a loaded CI worker mounts the React loading surface. The test
then cannot observe a state whose response has already completed. Existing
governed loading peers instead use an explicit unresolved Promise, proving
the intended deterministic contract.

The bounded same-cycle remediation holds the unchanged projection response
until the existing loading label is visible, releases the response in
`finally`, and then requires the unchanged loaded heading and formal value.
It does not change product code, route matching, response data, assertions,
timeouts or retries. CURRENT_TASK authorizes only this exact E2E path and its
focused check. The worker-parent cycle remains `1/1,1/1,0/1`; all diagnostic
activations remain false.

Level 1 passes focused formatting, lint and TypeScript plus five consecutive
single-worker runs of all five nonvisual P8-01 cases (`25/25`). The exact
loading case passes in every run. Current-task/reconciliation units pass
`33/33`; scripts, JSON/YAML parse, diff hygiene and exact-five manifest pass,
and an unauthorized sixth path is rejected. Product, visual baselines,
timeouts and diagnostic activations are unchanged.

## 54. Release-gate Tool Asset terminology remediation

The release review found that the eight new P8-05 visible Tool Asset strings
used `工装资产` / `工裝資產`, while the established catalog used
`模具资产` / `模具資產`. Repository priority resolves this without a new
business decision: V1.2 DOCX rows `FR-TL-011`, `FR-TL-012`, `FR-TL-013` and
`INT-005` explicitly name `模具资产`, and the P8-05 base checkpoint already
contains thirty-four Tool Asset translations per Chinese locale using that
term. No authoritative source defines a distinct `工装资产` concept.

The remediation therefore adds the exact Tool Asset term to the controlled
terminology list, harmonizes only the eight affected P8-05 translations in
each Chinese catalog, regenerates the React catalog, strengthens the
terminology regression and updates only the affected canonical zh and zh-TW
P8-05 baselines plus the two P6-06 composition baselines that render the same
inspector. English sources, product behavior, API contracts, the English
baseline and all execution diagnostics remain unchanged.

The first clean full-matrix proof exposed one separate P5-04 harness ordering
race. The route-level Suspense fallback can be detached while `ProjectPage`
still renders its independent cockpit-loading surface, so the first English
case could assert the EBOM tab before the exact cockpit response completed;
the following zh and zh-TW cases passed. The bounded test-only repair awaits
the GET response for the exact Project cockpit path with an empty query and
requires HTTP 200 before asserting the tab. It does not change timeouts,
retries, fixtures, product behavior or any P5-04 baseline.

The final governed remediation contains exactly sixteen paths: the fourteen
approved terminology/catalog/test/evidence/baseline paths, the P5-04 exact
cockpit-response gate, and the P6-03 locale expectation that exercises the
same inspector. Manual review confirms the four image updates are text-only;
the two P8-05 and two P6-06 Chinese images retain geometry, old context and
formal-ID boundaries. Those four pass twice no-update (`4/4` each), the
P5-04 gate passes twice across en/zh/zh-TW (`3/3` each), and the final clean
Bookworm/amd64 workers-one governed matrix passes `129/129`.

P5-04 nonvisual passes `5/5`; P6/P8-05 nonvisual passes `26/26`; full
frontend coverage passes `1,060/1,060`. Generate, type, lint, format, style,
boundary, UI, build, clean brand and zero-vulnerability audits pass. I18n
covers `8,341` literal English sources with complete direct zh/zh-TW
coverage; the Frappe localization/current/reconciliation group passes
`75/75`, verifier scripts pass, forbidden alternation and diagnostic-enabled
scans are zero, and diff hygiene passes. Exact-sixteen post-commit simulation
accepts the governed set and rejects an unauthorized seventeenth path.

## Final release-gate closeout

P8-05 passes at exact product SHA
`f9c358018823f3af20aca38efb53f8fcbd13d406`. Ordinary CI `32937395289`
passes repository, frontend, secret and governed visual lanes. Final Level 3
`32938622250` passes the same exact SHA with repository `98084790776`,
frontend `98084790857`, secret `98084790876`, visual `98084790917`,
controlled preflight `98087726984` and cumulative runtime `98087768879`.
The governed visual matrix is `129/129`; the controlled runtime scope is
`p5-01-through-p8-05` with predecessor `p5-01-through-p8-04`.

Runtime artifact `9596248305` has SHA-256
`11554463405c3165891e23bbd522e9c6093ef00f95d34d221d182efebfea8c41`;
visual artifact `9595833757` has SHA-256
`0a9712c3bf082a52a59ac04344a6e1ba2837ae831bf15994745b8950a06dd9b8`;
Gitleaks artifact `9595725822` has SHA-256
`25e68fa800f44f5927120e472245707ee1abb5e6fc6b453d165a4fdbd7de5f58`.
All diagnostics are dormant.

The authoritative terminology chain now uses only `模具资产` / `模具資產`
for Tool Asset; user-visible/generated sources contain no forbidden
alternation, and all four affected Chinese canonical images are text-only
updates inside the passing `129/129` matrix. Complete evidence is
`implementation/evidence/phase-8/p8-05-validation.md`.

Only the bounded technical portions of `INT-005` and `FR-TL-011..016` are
verified. Production/Sandbox execution, current ERPNext Asset method and field
mapping, location/maintenance rules, business approval and formal production
mapping remain held. P8-06 starts audit-only; no P8-06 product code, route,
writer, worker, adapter, UI or target network is authorized.

The first governed closeout commit
`c3b445b1b89d6d994766515540f6f8467bde15f3` reached ordinary CI
`32942302400`. Repository, frontend and visual passed; secret job
`98095619359` alone failed on the `generic-api-key` lexical classification of
the `final_secret_artifact_sha256` evidence key in `PHASE_STATUS.yaml`. The
value is the already governed Gitleaks artifact SHA-256, not a credential.
The same-cycle history-clean remediation renames only that key to
`final_gitleaks_artifact_sha256`, preserves the value bit-for-bit, adds no
allowlist, changes no scanner rule and consumes no product repair. The failed
ordinary run is not rerun or reused for a controlled workflow.
