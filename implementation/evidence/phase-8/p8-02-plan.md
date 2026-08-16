# P8-02 Plan — Signed Webhook and Inbox Project-Draft Processing

Recorded: `2026-08-16`

Status: `FROZEN — AUDIT PASS; CHECKPOINT 1 AUTHORIZED`

Starting audit/controller checkpoint:
`726115aa58ecaec17a6986cce1b628c760d3ba67`

Retained predecessor product checkpoint:
`b938926293c51c2e3ac1f63adab583c099a5c3ed`

Primary requirements:

- `INT-002`; and
- `FR-PM-002`.

`NFR-INT-001` contributes only the inbound durability/idempotency foundation
needed by this task. Its generic operations, DLQ, operator replay and
reconciliation product claim remains allocated to P8-07.

## 1. Audit decision

The bounded Requirement/domain/existing-capability and security audit passes.
Exact audit/controller SHA `726115a` passes ordinary pull-request CI
`31927559261`: repository `95117362588`, frontend `95117362653`, secret
`95117362609` and unchanged fixed-Linux visual `95117362620` all pass. Visual
artifact `9258338305` has digest
`sha256:1e2e3c5184a8b3acbc51a321a68fc5378e7098fe331ebff859b0322d11d555a9`;
Gitleaks artifact `9258292511` has digest
`sha256:5c76c24a9d494c0afb812e043c66cfc36ac596c8030667ef19c123d5f615e42e`.
Controlled lanes correctly skip because the audit transition changes no
product or runtime behavior.

The repository contains useful foundations but no complete P8-02 boundary:

- `npi_integration.reliable` supplies canonical hashing, an in-memory Inbox
  duplicate/hash-conflict example and Outbox states. It has no raw-body
  authentication, cross-process persistence, claim lease, Project mapping or
  restart recovery.
- `NPI Inbox Message` has only event ID, source, payload/hash, state and replay
  ID. Its controller does not guard insert/update/delete or validate an
  immutable envelope. It has no tenant, source profile, event contract,
  signature evidence, source ordering, claim, result or Project binding.
- No webhook route, HMAC verifier, inbound key/profile configuration, secret
  resolver or inbound scheduler exists in either app.
- The shared integration-event Schema has outbound execution events and seven
  P8-01 read-only observation events, but no submitted Quotation or Sales Order
  project-source event.
- The BFF already maps fixed `/api/npi/v1` routes before Frappe's generic
  router. A narrow guest transport handler can reuse that mechanism while
  replacing session/CSRF authentication with exact HMAC authentication only
  for one fixed route. Generic Frappe methods remain unavailable.
- The Project domain already creates one NPI-owned `draft`, immutable template
  snapshot and ordered Gate shells atomically. Its actor-bound idempotency,
  tenant-scoped business-code reservation, controlled-write guards and audit
  are reusable. The public command is intentionally System-Manager-only and
  is not a webhook endpoint.
- Project creation requires an enabled NPI owner, a published exact Project
  Template version, supported Project type, target SOP date, valid unique
  business code and template-compatible references. ERPNext cannot choose the
  tenant, service actor, owner, template, Project type or permissions.
- `NPI Engineering Project.source_system` correctly remains `NPI_ONE`: the
  Project workflow is NPI-owned even when an ERP source event caused the draft.
  The repository lacks the separate immutable ERP source-document binding
  required by `source_doc` uniqueness and traceability.
- The current reconciliation package has no approved production custom-field,
  naming, owner, template, service-scope, HMAC-key, reverse-proxy or sandbox
  mapping. The technical path can still be proven with a closed server-owned
  profile and disposable synthetic policy without installing production facts.

P8-02 therefore proceeds as a fail-closed, Mock/default-disabled inbound
technical foundation. It proves authenticated durable landing and at-most-one
NPI Project draft on a disposable Site. It does not claim a production ERP
customization, endpoint, credential, business mapping or acceptance.

## 2. Frozen minimum vertical slice

P8-02 delivers exactly this path:

> receive one fixed TLS-terminated POST -> enforce content type, encoding and
> 256 KiB raw-body bound -> resolve a server-owned non-production source
> profile by exact signing-key ID -> validate request UUID, Unix timestamp,
> key validity and the five-minute replay window -> compare HMAC-SHA256 over
> the exact method/path/key/timestamp/request/raw-body signing input -> parse a
> duplicate-key-free closed version-1 event and verify its canonical payload
> hash -> server-resolve tenant and freeze the exact intake-policy snapshot ->
> atomically land one immutable Inbox receipt and update one locked source
> stream's highest-received version before commit -> acknowledge only after
> commit and enqueue only after commit -> claim the Inbox with a bounded lease
> outside the request -> lock the exact source stream and reject older/equal-
> conflict truth -> validate the configured internal service actor, Project
> owner and published template -> reuse the existing Project instantiation
> service to create one NPI-owned draft and Gate shells -> bind the exact ERP
> source document to that Project and seal Inbox disposition/audits in the
> same transaction -> safely replay duplicates or expired claims without a
> second Project

The webhook request never creates a Project, loads a Project template, creates
Gate shells or performs other long business work. A successful HTTP response
means only that the receipt is durably accepted or is an exact duplicate. It
does not mean that the worker has run or that a Project is submitted,
approved, active or target-confirmed.

No outbound network request exists in this task. No browser calls the webhook.
No production ERPNext/JCE endpoint, credential, data or traffic is installed
or contacted.

## 3. Fixed transport and signature contract

The only public ingress is:

`POST /api/npi/v1/integration/erpnext/project-source-events`

No caller-selected method, path, DocType, endpoint, tenant, operation or
handler is accepted. `OPTIONS` has no integration authority. Generic
`/api/method` invocation repeats the handler's exact route and signature
checks and cannot bypass them.

The route accepts only:

- `Content-Type: application/json` with an optional exact UTF-8 charset;
- absent or `identity` content encoding;
- a body of at least two bytes and at most `262144` bytes;
- `X-Request-ID`: one canonical UUID;
- `X-NPI-Key-ID`: one exact configured identifier;
- `X-NPI-Timestamp`: unsigned decimal Unix seconds; and
- `X-NPI-Signature`: `v1=` followed by 64 lowercase hexadecimal characters.

The version-1 signing input is the UTF-8 prefix
`npi-webhook-v1\nPOST\n/api/npi/v1/integration/erpnext/project-source-events\n`
followed by the exact key ID, timestamp and request ID, each terminated by one
newline, followed by the exact unmodified raw body bytes. Verification uses
HMAC-SHA256 and constant-time comparison. No decoded/re-encoded JSON,
form-dict value or caller-provided payload hash substitutes for the raw bytes.

The signed timestamp must be within an inclusive `300` second window of the
server clock. A sender retry after that window re-signs the same immutable
event with a new request timestamp; Inbox idempotency still returns the first
logical receipt. Key validity is checked at the signed timestamp. Overlapping
old/new keys in one profile provide rotation; an unknown, inactive, expired or
not-yet-valid key produces the same generic authentication failure as a bad
signature.

TLS is a server deployment fact, not a caller header. The handler requires a
secure request or an explicit server-owned trusted-TLS-termination setting in
the closed source profile. The disposable runtime may set that flag only on
its synthetic local profile. No `X-Forwarded-Proto` supplied by the sender is
accepted as authority.

## 4. Source profile, key and policy ownership

P8-02 installs no source profile, key, secret, mapping or default row. Missing
configuration disables the route with explicit unavailable truth.

One immutable parsed profile version contains only server-owned metadata:

- profile ID/version, `ERPNEXT` source and `NPI_ONE` target;
- exact Site tenant matching `npi_tenant_id`;
- non-production environment code and attestation, enabled flag and trusted
  TLS-termination fact;
- the two allowed event types;
- one internal service-actor user ID;
- one or more key descriptors with key ID, validity interval and opaque secret
  reference; and
- one exact intake-policy snapshot for each allowed source document type.

Raw HMAC keys are absent from code, Site configuration, DocTypes, events,
audits, responses and logs. A narrow injected secret resolver accepts only the
configured opaque reference and returns bytes in memory. No resolver or
profile means disabled. Profile validation rejects production/live labels,
duplicate key IDs, overlapping identity ambiguity, an external/Guest actor,
unknown event types, raw-secret-shaped configuration and tenant mismatch.

The versioned intake policy server-resolves:

- exact source document type (`Quotation` or `Sales Order`);
- published Project Template global ID/version;
- Project type;
- enabled NPI owner user ID; and
- business-code mode, frozen in P8-02 as `source_document_id`.

The signed source event supplies only exact ERP-owned source identity/version,
title, source-modified time and target-SOP date. The server uses the exact
source document ID as the draft business code only when it already passes the
existing NPI business-code contract and tenant uniqueness. It performs no
silent sanitization, truncation, prefixing or collision rewrite. A production
naming or field mapping that cannot satisfy this closed mode remains a scoped
configuration hold for a later approved policy revision.

No production policy is installed. The cumulative disposable Site creates one
synthetic policy and fake secret resolver, proves behavior, then removes the
Site. The frozen policy snapshot/hash is stored with every accepted Inbox
message so a later configuration change cannot alter an old event's meaning.

## 5. Closed event contract and hashes

Only these event types exist in P8-02:

- `erpnext.quotation.submitted`, version `1`, object type `Quotation`; and
- `erpnext.sales_order.submitted`, version `1`, object type `Sales Order`.

Both require `ERPNEXT` source, `NPI_ONE` target, canonical event UUID, stable
source-stream `global_id`, exact `source_object_id`, positive integer
`object_version`, UTC `occurred_at`, UUID correlation ID, bounded trace ID,
service actor, confidential sensitivity and declared lowercase SHA-256 payload
hash. The closed payload contains only:

- `schema_version: 1`;
- `submission_state: submitted`;
- exact Project title;
- ISO date target SOP; and
- exact UTC source-modified timestamp.

Unexpected/missing keys, duplicate JSON keys, floats, NaN/infinity, invalid
Unicode/UTF-8, invalid dates/timestamps, oversized strings, unknown types or
non-submitted states fail before Inbox acceptance.

P8-02 defines a dependency-free canonical JSON form for closed event hashing:
UTF-8, lexicographically sorted object keys, compact separators, no ASCII
escaping, integers only for numeric values, and no normalization or coercion.
The declared `payload_hash` must match the canonical payload. The server also
stores the SHA-256 of the exact raw body and a canonical full-event hash.

Inbox idempotency uses exact `event_id` plus canonical full-event hash. Same
event/same canonical event is an exact replay even if harmless JSON whitespace
differs; same event/different canonical event is quarantined and returns
conflict. The exact first raw body and its raw hash remain immutable.

## 6. Durable Inbox, source stream and ordering

`NPI Inbox Message` is extended additively. Legacy rows remain readable and
immutable but are never treated as P8-02 authenticated receipts. A version-1
receipt freezes receipt UUID, tenant/profile/policy identity, event envelope,
source key, raw body/hash, canonical event/payload hashes, signing key ID,
signed/received times, trace/correlation/request IDs and initial state.
Mutable processing fields are limited to guarded state, disposition, claim
lease/token, attempt count, safe error code/time and bound Project result.

One new guarded `NPI Project Source Binding` record uses the SHA-256 of exact
tenant + profile + object type + source object ID as its unique name. It holds:

- immutable source identity and profile/tenant scope;
- locked highest-received positive object version, payload hash and Inbox ID;
- explicit stream state (`unbound`, `bound` or `conflicted`);
- bound Project global ID, bound version/hash and policy snapshot/hash; and
- optimistic version and last safe processing metadata.

Landing performs only bounded transport work. In one transaction it reserves
event identity, inserts or exact-replays the Inbox, locks/creates the source
binding, advances only a higher received version or records an equal-version
hash conflict, appends a safe structural audit and commits. It never loads a
Project template or creates business rows. Only after commit may the route
return `202` and register an after-commit worker enqueue.

Source ordering uses positive `object_version`; timestamps are evidence, not
a lexical fallback. Lower versions are retained as `superseded`. Equal version
and equal payload is source-exact replay. Equal version and different payload
sets the stream to `conflicted` and creates no Project. If a higher version is
already landed when an older worker claims, the older message is superseded
before business work. A higher version received after a Project is bound is
retained as `received_after_creation`; P8-02 never rewrites the Project from a
later commercial event.

## 7. Asynchronous claim and Project creation

The webhook queues a named operation-specific job after commit. A narrow
scheduler recovery entry may requeue only bounded P8-02 `pending` receipts and
expired `processing` leases. It is not a generic replay API, DLQ console or
reconciliation engine.

The worker atomically claims one pending/expired receipt with a random token,
claim time, lease expiry and incremented attempt count. A live unexpired claim
cannot be stolen. Completing a claim requires the same token. A crash before
claim changes nothing; a crash after claim expires and is reclaimed; a crash
during Project transaction rolls back Project, binding, receipt result and
audit together.

After locking the source binding, the worker:

1. revalidates the immutable Inbox snapshot/hash and current source order;
2. revalidates the frozen profile/policy shape without resolving a new policy;
3. resolves the configured service actor as an enabled internal System User
   with `NPI API User`, and constructs its tenant-scoped principal server-side;
4. resolves the configured Project owner as enabled;
5. loads the exact enabled published Project Template version and confirms the
   configured Project type;
6. builds `CreateProjectCommand` with a source-key-derived idempotency hash,
   exact source document ID business code, signed title/target SOP and no
   invented references;
7. invokes the existing `ProjectInstantiationService` and controlled Frappe
   repository, which creates only an NPI-owned draft, template snapshot,
   ordered Gate shells, code reservation, idempotency and Project audit; and
8. binds the exact source document once, marks the Inbox succeeded with
   `project_created` or `project_replayed`, and appends an integration audit in
   the same transaction.

Gate shells are the retained invariant of the existing Project draft
aggregate. P8-02 creates no Gate review, decision, evidence, transition or
Work Item and does not submit/activate the Project.

Distinct event IDs for the same source document serialize on the source
binding. Once bound, they return the exact Project without a second creation.
Actor-bound Project idempotency is derived only from the server source key;
the sender cannot provide or vary it. A business-code collision with another
source, unavailable policy/template/owner, invalid source code or permission
failure is explicit `failed_final` and creates no partial Project.

P8-02 does not add generic manual retry, edit-old-payload, DLQ movement,
operator replay, target reconciliation or cross-operation backoff policy.
Those remain P8-07. Unexpected local failures retain a safe retryable state and
trace ID; only expired-claim recovery is automatically proven here.

## 8. Response, error and audit semantics

A newly landed or exact-replayed authenticated event returns `202` only after
the landing transaction commits. The closed body contains receipt ID, event
ID, current Inbox state, exact-duplicate boolean and request/trace IDs. It
contains no secret, policy body, tenant, Project fields or raw source payload.

Failures are closed machine problems with stable English technical codes:

- `401`: missing/unknown/inactive key, stale/future timestamp or signature
  mismatch, all intentionally indistinguishable;
- `409`: authenticated event-ID hash reuse or source-version hash conflict;
- `413`: raw body too large;
- `415`: unsupported content type or encoding;
- `422`: authenticated malformed/closed-contract failure;
- `503`: route/profile/secret resolver disabled or unavailable; and
- `500`: safe unexpected failure with request/trace IDs only.

Transport errors never expose key existence, secret references, signature
input, expected digest, traceback, raw payload, Site path or database detail.
Authentication failures create no Inbox row. They append a bounded safe audit
identified by server/request UUID with only failure code, received time,
body-size/raw-hash when safely available and a hash of the presented key ID.
No Authorization, cookie, secret, signature or raw body is logged or audited.

Every successful landing, duplicate, conflict, claim, supersede, Project
creation/replay, expired-claim recovery and terminal failure has a structural
`NPI Audit Event`. Audit append is controlled, immutable and transactionally
aligned with the state it describes.

## 9. Fault matrix

| Fault | HTTP/worker result | Durable truth | Forbidden effect |
| --- | --- | --- | --- |
| route/profile disabled | `503` | safe audit only | no Inbox/Project |
| insecure transport without trusted termination | `401`/closed auth failure | safe audit only | no caller-header bypass |
| unsupported type/encoding or oversized body | `415`/`413` | safe audit only | no unbounded read/log |
| missing/unknown/expired key, stale time, bad signature | generic `401` | safe audit only | no parsing/trust/Inbox |
| signed malformed or unknown event | `422` | safe audit only | no partial Inbox |
| first valid event | `202` after commit | immutable pending Inbox + source head + audit | no Project in request |
| same event/same canonical hash | `202`, duplicate true | original Inbox retained | no second row/job effect |
| same event/different canonical hash | `409` | original receipt plus conflict audit/quarantine truth | no overwrite |
| lower source version | worker succeeded/superseded | receipt retained | no Project if newer already received |
| equal source version/different payload | conflict | source stream conflicted | no Project |
| crash before claim | pending | receipt retained | no loss |
| crash after claim | lease expires/reclaim | attempts/audits retained | no live-claim steal |
| crash during Project transaction | retryable/rollback | no partial Project/binding/result | no orphan code/Gate |
| two events same source concurrently | one locked binding | one exact Project ID | no duplicate Project |
| policy/template/owner unavailable | failed final | safe code/trace retained | no fallback/default |
| Project already bound | replayed/succeeded | exact original Project retained | no rewrite/submission |
| later source version after creation | received-after-creation | later receipt retained | no automatic Project update |

## 10. Checkpoints and changed-files-to-tests map

### Checkpoint 1 — pure signature/event/config domains and guarded metadata

- Add closed canonical JSON/event parsing, raw HMAC signing/verifying, fixed
  replay/key-rotation/profile/policy validation, source ordering and claim
  domains; extend integration-event/OpenAPI/ownership contracts; harden Inbox
  metadata/controller; add the guarded Project Source Binding DocType and
  direct `zh`/`zh-TW` translations.
- Tests: raw-byte signature mutation; method/path/header binding; constant-time
  verifier path; five-minute inclusive edge; old/new overlapping keys;
  unknown/expired/duplicate keys; raw secret/profile/production rejection;
  duplicate JSON keys, floats, extra/missing/type/size/date/UTF-8 boundaries;
  canonical hashes; event/source duplicate/conflict/reorder; metadata insert/
  update/delete guards; legacy-row non-promotion; ownership and translation
  symmetry.
- No route, repository insert, scheduler, worker, Project row, default profile,
  secret or external call is activated. Exact-SHA ordinary CI must pass before
  checkpoint 2.

### Checkpoint 2 — fixed signed ingress and durable landing

- Add the one fixed BFF route, raw request adapter, disabled-by-default profile
  and injected secret resolver, safe problem/audit response, atomic Inbox plus
  source-stream repository, commit-before-acknowledgement and enqueue-after-
  commit behavior.
- Tests: fixed-route/method/generic-method closure; TLS server fact; auth before
  JSON trust; size/content/encoding; every signature/key/replay fault; no
  secret/raw error; first landing, exact replay, event conflict, source reorder
  and equal conflict; transaction rollback; commit ordering; enqueue ordering;
  tenant/profile resolution; route disable/recovery; no Project/Gate/Work Item/
  outbound row or traffic.
- No Project creation runs in the request. Exact-SHA ordinary CI must pass
  before checkpoint 3.

### Checkpoint 3 — leased worker and at-most-one Project draft

- Add bounded post-commit enqueue, operation-specific pending/expired-claim
  recovery, source-locking worker, server actor/owner/template resolution,
  existing Project service adapter, atomic source binding/result/audit and safe
  dispositions.
- Tests: pending claim, live lease denial, expired lease recovery, crash at
  claim/Project/binding/audit boundaries, higher-before-older reorder, equal
  conflict, cross-process duplicate event/source concurrency, source-derived
  Project idempotency, policy/template/owner/code failures, one draft plus
  retained Gate shells, source binding, later-version no rewrite and no
  Project submission/Gate review/Work Item/target effect.
- Extend the cumulative controlled runtime and CI lane through P8-02. Exact-SHA
  ordinary CI must pass before the final Level 3 Gate.

### Final P8-02 Level 3 Gate

- Run complete repository/frontend/security/visual verification and cumulative
  disposable-Site runtime with migrations twice.
- Runtime sends signed requests through the fixed route using only a fake
  non-production profile and in-memory/disposable secret resolver; proves
  invalid signature/time/key rotation, durable acknowledgement, duplicate/hash
  conflict, source reorder, crash/lease restart, concurrent source events,
  exactly one Project draft/source binding, route recovery, redaction, zero
  production traffic, zero outbound target write and cleanup.
- Use `release-gate` because public authentication, shared event/OpenAPI,
  additive Schema, Project transaction and integration infrastructure change.
  P8-02 advances to P8-03 only after exact final SHA ordinary CI and Level 3
  both pass.

| Changed boundary | Minimum affected evidence |
| --- | --- |
| signature/profile/policy domain | exact raw signing input, compare path, replay edges, key rotation, production/raw-secret rejection, no fallback |
| event/Schema/ownership | closed two-event JSON Schema/OpenAPI, canonical payload/event hash, exact ERP/NPI ownership and extra/missing/type/size tests |
| Inbox/source metadata | controller guards, immutable envelope/binding, legacy compatibility, migration twice, no generic CRUD/delete |
| route/request adapter | TLS/content/encoding/body bounds, auth before parse, generic-route closure, commit-before-202, enqueue-after-commit, safe errors |
| repository/worker | atomic landing, claim lease/restart, source lock/order/conflict, at-most-one Project, transaction crash and audit tests |
| Project reuse | existing Project domain/repository/API/metadata regressions, draft/template/Gate-shell invariants, actor/owner/tenant/code permission tests |
| i18n/support metadata | literal English plus direct `zh`/`zh-TW`, mixed-language and catalog symmetry; no SPA/visual delta |
| final trace/security/runtime | full repository/frontend/history-secret/unchanged visual matrix, cumulative disposable runtime, release review and Requirement reconciliation |

## 11. Expected changed paths

| Change | Expected paths |
| --- | --- |
| pure inbound project domain/configuration | `apps/npi_integration/npi_integration/inbound_project/**`; focused use of `reliable.py` only if the shared primitive can be strengthened without changing old behavior |
| Inbox and source-binding metadata/controllers | existing `npi_inbox_message/**`; new `npi_project_source_binding/**` |
| fixed route/worker registration | `apps/npi_core/npi_core/bff.py`; `apps/npi_integration/npi_integration/hooks.py`; operation-specific webhook/worker modules |
| Project creation reuse | existing `npi_core.project` modules only for a narrow reusable internal adapter or transaction correction proven necessary by focused tests; no business-rule relaxation |
| contracts and ownership | `contracts/integration-event.schema.json`; `contracts/npi-api.openapi.yaml`; `contracts/data-ownership.yaml` |
| localization | `apps/npi_core/npi_core/translations/zh.csv`; `zh-TW.csv`; generated catalog only if extraction changes it |
| controlled proof | `tests/test_phase8_inbound_project_*.py`; runtime verifier/shell and CI workflow cumulative Phase 8 lane |
| controller/trace/evidence | P8-02 plan/checkpoints/validation and current controller/trace/risk/status files |

A required production field/naming/owner/template/service-scope choice,
Project lifecycle or Gate-policy change, generic replay/DLQ operation, outbound
target call, new dependency, Frappe/ERPNext core patch or cross-database access
reopens the audit instead of silently expanding these paths.

## 12. Migration, security and rollback

Metadata is additive. Existing Inbox rows receive no fabricated signature,
tenant, source policy, Project binding or authenticated status. New required
truth is enforced by the controlled version-1 controller rather than an unsafe
backfill. No patch creates a profile, key, secret, mapping, user, template,
Project or business value.

The disposable Site migrates twice. Runtime checks exact indexes/uniqueness,
controller guards, legacy-row immutability, scheduler idempotence and cleanup.
No production endpoint or credential appears in configuration, database,
environment, process arguments, artifacts or logs.

Before any retained P8-02 receipt, rollback may return to the exact P8-01
product boundary and remove fresh disposable Schema. After an Inbox/source/
Project/audit record exists, rollback disables the P8-02 route, enqueue and
worker, retains every raw/canonical hash, receipt, claim, conflict, source
binding, Project draft, Gate shell and audit, and deploys a reviewed forward
repair. It never deletes a receipt/Project, edits an old policy snapshot,
unbinds/rebinds a source, resubmits an event or rewrites state to simulated
success.

Because P8-02 has no outbound target call, rollback requires no target
compensation. It still never cross-writes ERPNext or treats a local Project
draft as ERP acceptance.

## 13. Explicit holds and non-scope

- Production ERPNext/JCE endpoint, credential, data, webhook, traffic,
  customization, host, service scope and business mapping remain prohibited.
- No raw secret, production source profile, default intake policy, sample
  business row or fallback owner/template is installed.
- No Project submission/activation, Gate review/decision/evidence/transition,
  Work Item generation, Item/MBOM/Asset/quality execution, Tooling/Trial/
  Readiness mutation or target write occurs.
- P8-07 owns generic operations UI, DLQ, manual replay, corrected payload/new
  command authorization, retry policy and reconciliation. P8-02 exposes no
  generic operator mutation API.
- P8-03/04/05 own Item, MBOM and Tool Asset execution; P8-06 owns formal
  quality linkage; P8-08/09 own the held external summary/JCE display seams.
- Production business-code transformation, Quotation/Sales Order field
  extraction and owner/template policy values remain in the external
  reconciliation package. P8-02 proves only the closed normalized contract
  with a disposable synthetic policy.
- No frontend/product UI or visual change is required. Desk remains
  System-Manager support only; every new support label/error source is English
  with direct Simplified/Traditional Chinese translation where user-visible.

## 14. Automatic transition

Standing continuous-delivery authority permits automatic progression after
each exact-SHA ordinary CI and affected Gate passes. Checkpoint 1 is the only
active product scope after this plan commit passes ordinary CI. No checkpoint
authorizes production ERPNext/JCE contact. P8-02 completes only after its final
Level 3 Gate; only then may the controller activate P8-03.

Checkpoint progress recorded on 2026-08-16: checkpoint 1 passes at exact
product SHA `a040f21d4379d529f9524bbf09c1ac5016fe6881` and ordinary CI
`31930363720`. Checkpoint 2 is now the only active product scope; every later
checkpoint and the final Level 3 boundary remain unchanged.

Checkpoint 2 passes at exact product SHA
`4c77c4472a0ea07bc14a2073f0b6c7d3b006b870` and ordinary CI
`31932869203`. Checkpoint 3 is now the only active product scope; the final
Level 3 boundary remains unchanged and production ERPNext/JCE contact remains
prohibited.

Checkpoint 3 passes at exact final product SHA
`f3f7fba8ed0c59ce958f2ecb7709ea3c5a6b1f39` and ordinary CI
`31935510653`. The final Level 3 Gate is now the only active scope; P8-03 and
production ERPNext/JCE contact remain inactive until that Gate passes.
