# P8-08 Plan — Released Trial Summary Read-Only Projection Seam

Status: **CHECKPOINT 3 IMPLEMENTED — AWAITS EXACT-SHA ORDINARY CI**

Audit date: 2026-08-30

Audit base: `216ac60480d4af2456b1649626ca23131f886048`

Predecessor product checkpoint:
`edf89e79cd815cbde60e2940ae9d580479336d75`

Requirement: `FR-INT-015`

P8-07F evidence base: diagnostics-off checkpoint `d8aba50580ffd7a0ca3fca0493cf49f84a6a1e8c`, ordinary CI `33317964484`, final Level 3 `33318628754`, governance closeout `216ac60480d4af2456b1649626ca23131f886048` and ordinary CI `33320025714`.

Product-code authorization: **false until this plan's exact-SHA ordinary CI passes and a separate checkpoint-1 controller transition is committed**.

Audit-plan checkpoint: `d560fdf218f415a14b6cf5bef0baa436da4725cc`

Audit-plan ordinary CI: `33320787112` (**PASS**) — frontend
`99282270348`, visual `99282270267`, repository `99282270365` and secret
`99282270388`; controlled lanes correctly skipped.

Checkpoint-1 product paths remain conditional on the separate activation
commit's exact-SHA ordinary PASS.

Checkpoint-1 activation: `c7571d1b5057cc353ade46aa83537fc853698fa7`

Checkpoint-1 activation ordinary CI: `33321510831` (**PASS**) — secret
`99284179932`, frontend `99284180072`, visual `99284180080` and repository
`99284180157`; controlled lanes correctly skipped.

Checkpoint-1 product implementation was limited to the exact five product/test
paths frozen below and has passed its own exact-SHA ordinary CI.

Checkpoint-1 product: `495141f9650d71b9ae2c8f7cf8a8904e0242c210`

Checkpoint-1 product ordinary CI: `33322318251` (**PASS**) — secret
`99286336195`, frontend `99286336260`, repository `99286336272` and visual
`99286336293`; controlled lanes correctly skipped.

Checkpoint-2 activation: `1d8b13c99362c375e8ea1424840e91e8ab48a23d`

Checkpoint-2 activation ordinary CI: `33323078013` (**PASS**) — secret
`99288353208`, repository `99288353284`, frontend `99288353388` and visual
`99288353423`; controlled lanes correctly skipped.

Checkpoint-2 implementation resolves only an exact current P7-07 source
through the Project + Trial Round-first repository boundary. It returns
unavailable for a permission-safe missing workspace, fails closed on stale,
foreign, duplicate, malformed or hash-drifted truth, and emits only the exact
immutable descriptor. It adds no route, row, event, queue or network.

Checkpoint-2 product: `3a9ab61cd83bb13dae8b9ac40a687b2b83bb6f25`

Checkpoint-2 product ordinary CI: `33323869238` (**PASS**) — frontend
`99290465347`, governed visual `99290465499`, repository `99290465500` and
secret `99290465597`; controlled lanes correctly skipped.

Checkpoint-3 activation: `5175efc9a3968d7e39d8021c147cc25a6f8b5d5c`

Checkpoint-3 activation ordinary CI: `33324672403` (**PASS**) — repository
`99292592936`, secret `99292593013`, governed visual `99292593027` and
frontend `99292593047`; controlled lanes correctly skipped.

Checkpoint-3 implementation extends only the existing P7-07 fixed disposable
runtime and one focused test. It resolves the exact current Project + Trial
Round source, revalidates all immutable hashes, reports the held external
projection as unavailable in fresh and replay-only processes, and brackets the
read with the existing retained persistence digest to prove zero writes.

## 1. Audit conclusion

P7-07 already provides the exact NPI-owned immutable source required by
P8-08. Its retained summary, presentation projection and redaction manifest
use the fixed schemas `npi.released_trial_summary.v1`,
`npi.released_trial_summary.presentation.v1` and
`npi.released_trial_summary.redaction.v1`. The source retains exact Project,
Trial Round, conclusion, source revisions and hashes; its existing public view
truthfully reports `externalProjection: unavailable`.

P8-07F found no concrete incompatibility with that design. The accepted
production facts identify `Mold Trial Report` only as a future read-only source
or corroboration candidate and classify the compatibility outcome as
`CONFIG_OR_MAPPING_ONLY` with `NO_CHANGE`. They do not approve an external
event, consumer method, target field mapping, receipt or production profile.

P8-08 therefore does not redesign or duplicate P7-07. It adds a small internal
read-only integration seam that resolves one exact current immutable summary
and returns an explicit unavailable external-projection result while the
external contract is held. It creates no event, Outbox row, API route, target
call, ERP write or formal external success.

## 2. Frozen ownership and compatibility result

| Truth | Owner | P8-08 treatment |
|---|---|---|
| Released Trial Summary identity, version, source manifest, presentation and redaction hashes | NPI One P7-07 | reuse exactly; never copy into a second mutable domain |
| Trial/Project containment and summary-currentness | NPI One P7-07 repository | recheck Project first and require the exact current summary revision |
| external event name/version, routing, payload and consumer mapping | held by `DR-REC-009` | unavailable; do not invent or serialize an event |
| accepted external receipt/reference | future approved consumer | unavailable; no NPI assertion or synthetic receipt |
| production `Mold Trial Report` mapping | ERPNext configuration/approved custom app | future mapping/Sandbox task only; `NO_CHANGE` in P8-08 |

Compatibility is `DIRECT_MATCH` for the existing immutable NPI source and
`CONFIG_OR_MAPPING_ONLY` for the future production source mapping. No
LaunchFlow or ERPNext product adjustment is evidenced by P8-07F.

## 3. Internal seam contract

The seam is internal Python code under `npi_integration`; it is not a public
OpenAPI or event contract. It accepts only server-owned exact source values:

- Project global ID;
- Released Trial Summary global ID and positive summary version;
- immutable summary snapshot hash;
- presentation projection schema and hash;
- redaction manifest schema and hash; and
- current request trace identity.

It never accepts a caller-selected target, endpoint, method, event name,
payload version, field list, desired status or receipt. It exposes two separate
truths:

1. exact NPI source resolution: current, unavailable or conflict; and
2. external projection: always unavailable until a separately approved exact
   contract/profile exists.

An exact source may be available while external projection remains
unavailable. The seam must never collapse those states into success.

## 4. Security and failure behavior

- authorize the Project before resolving any secondary summary identifier;
- use only the existing P7-07 repository/permission boundary for persisted
  source reads;
- require exact current revision, version, schema and hashes;
- reject stale, foreign, malformed, duplicate or ambiguous source truth;
- reject URLs, private locators, credentials, tokens, provider payloads and
  unapproved external fields at the pure boundary;
- preserve request trace and hashes without logging source content;
- perform no network, DNS, queue, Outbox, Inbox, File or generic DocType write;
- return explicit unavailable truth for missing profile/contract/consumer;
  and
- never treat Mock, Synthetic, HTTP acceptance or absence of an error as
  formal external projection success.

Permission-safe not-found, unavailable and conflict remain distinct internal
fault classes but disclose no foreign Project or summary identity.

## 5. Checkpoints

### Checkpoint 1 — pure source descriptor and unavailable adapter seam

After this plan's exact-SHA ordinary CI and a separate activation transition:

- add `npi_integration.released_summary_projection` pure domain/config/reader
  interfaces;
- validate the exact P7-07 schema/version/hash tuple;
- model source resolution separately from external projection availability;
- implement only the default-disabled/unavailable adapter result; and
- prove no URL, credential, provider payload, target selector, event name or
  success fabrication is accepted.

No Frappe row, route, hook, event, contract file, network call or existing
P7-07 behavior changes in checkpoint 1.

Frozen eligible paths for checkpoint 1 are:

- `apps/npi_integration/npi_integration/released_summary_projection/__init__.py`
- `apps/npi_integration/npi_integration/released_summary_projection/config.py`
- `apps/npi_integration/npi_integration/released_summary_projection/domain.py`
- `apps/npi_integration/npi_integration/released_summary_projection/readers.py`
- `tests/test_phase8_released_trial_summary_projection_domain.py`
- this plan and the exact controller/current-task evidence paths named by the
  activation manifest.

### Checkpoint 2 — exact P7-07 source adapter

Only after checkpoint 1 exact-SHA ordinary CI passes:

- add a Project-first adapter over the existing P7-07 repository;
- resolve one exact current summary revision without copying the domain;
- revalidate summary/presentation/redaction schemas and hashes;
- preserve unavailable/conflict behavior and source-content redaction; and
- keep the external projection state unavailable with zero target traffic.

No public route is required. Any later need for a new local API must be proved
and frozen as a separate checkpoint; the audit does not authorize one.

The existing P7-07 repository exposes only the exact Project-first
`summary_workspace(project_id, round_id)` boundary. A secondary summary
revision cannot safely replace Trial Round in that call. Checkpoint 2 therefore
also makes the minimal factual update to the already-created reader Protocol so
that its inputs are Project, Trial Round and summary revision, in that order.
This is not a new domain or route.

Eligible product/test paths are limited to:

- `apps/npi_integration/npi_integration/released_summary_projection/readers.py`
- `apps/npi_integration/npi_integration/released_summary_projection/source.py`
- `tests/test_phase8_released_trial_summary_projection_source.py`
- the exact governance/evidence paths.

### Checkpoint 3 — disposable runtime and final Gate

Only after checkpoint 2 exact-SHA ordinary CI passes, extend the existing fixed
disposable, network-free runtime to prove Project containment, exact current
source, stale/conflict/unavailable behavior, cross-process deterministic
hashes, zero rows/writes/network, migration twice and cleanup. Then run the
P8-08 final Level 3. Production ERPNext is not contacted by this Gate.

Checkpoint 3 must reuse the existing P7-07 runtime already invoked by the
cumulative Frappe verification. It does not add a route, workflow lane or
external process. Eligible product/test paths are limited to:

- `scripts/verify_released_trial_summary_runtime.py`
- `tests/test_phase8_released_trial_summary_projection_runtime.py`
- the exact governance/evidence paths.

## 6. Migration, rollback and activation

P8-08 adds no DocType, patch, fixture or stored row. Migration is therefore
none; the runtime must prove the app remains migration-safe. Rollback removes
or disables only the internal seam. P7-07 immutable summaries, controlled
outputs, Project/Trial truth and all accepted production facts remain
untouched. No external compensation is required because no target boundary is
crossed.

Production activation is outside P8-08. It requires the held `DR-REC-009`
business/contract decision, exact service identity and permission, approved
mapping/profile, Sandbox/UAT and a separate atomic task. The standing P8-07F
read-only authority may refresh facts when needed but is never write or
activation authority.

## 7. Verification map

| Changed area | Required evidence |
|---|---|
| pure domain/config/readers | exact schemas/versions/hashes, current/unavailable/conflict separation, default unavailable, malformed/stale/foreign rejection |
| security/redaction | forbidden keys/values, URL/private locator, credential/token/provider-payload rejection, trace/hash-only diagnostics, zero target selector |
| P7-07 adapter | Project-first permission-safe lookup, exact current revision, no copied mutable truth, no write/network/queue |
| runtime | disposable Site, migration twice, retained source resolution, zero new row, zero network, cleanup |
| governance | exact changed-file manifest, `FR-INT-015` trace, `DR-REC-009` hold, P8-09 inactive, user dirty worktree preserved |

Each checkpoint runs focused tests, complete affected P7-07/P8 integration
regressions, current-task/reconciliation checks, compile/shell/diff/security
scans and exact manifest rejection. The final checkpoint additionally runs the
full ordinary CI and sole applicable Level 3.

## 8. Explicit non-scope

- changing P7-07 summary schemas, ownership, repository, API or UI;
- inventing an external event/payload/consumer/receipt under `DR-REC-009`;
- creating an Outbox/Inbox, target worker, generic adapter or target command;
- reading or writing production ERPNext, including `Mold Trial Report` rows;
- browser-direct ERP access, cross-database access or dual-master fields;
- claiming Sandbox/UAT, production acceptance, real pilot or external success;
- P8-09 display identity; and
- redesign, refactor, rename, generalized abstraction or nearby optimization.

## 9. Checkpoint-3 Level 3 migrated-legacy diagnostic

Checkpoint-3 product `fc43c4aa5b876d98e9123977c6d5441ac088632a`
passes exact-SHA ordinary CI `33325513567` in all four lanes. Its sole Level 3
`33326192285` passes repository `99296625210`, frontend `99296625273`, governed
visual `99296625299`, secret `99296625349` and controlled preflight
`99298323642`. Runtime `99298356336` passes the fixed Bench/Site setup and the
P8-08 Released Trial Summary boundary, then fails only at the later fixed Item
publish migrated-legacy outer label.

No raw or child output, response content, business value, identity, message or
stack was read. This does not evidence a P8-08 product failure or an Item
publish repair. Open one product-zero diagnostic at `0/1,0/1,0/1` by enabling
only the existing collection-fallback exact-39 code/type/trace mechanism. Its
exact-SHA ordinary CI must pass before one Level 2 controlled run. Success
emits zero tuple; a failure may emit only one strict safe tuple. P8-09 remains
inactive and production ERPNext remains untouched.

## 10. Reconciliation-response bounded diagnostic

The product-zero exact-39 checkpoint
`51e071f01b830f680f5aaeb97460fe32b2969bab` passes ordinary CI
`33327421787`. Its sole controlled run `33328132993` passes preflight
`99301811297` and returns only the strict safe tuple
`P803_LEGACY_FULL_RECONCILIATION_CONTRACT / RuntimeError /
trace-13dcf4b038055bed9842636978c24021` from runtime `99301844242`.
No raw or child output, response content, business value, identity, message or
stack was read.

This proves the same run passed legacy collection, detail, public/redaction and
binding checks. The parent tuple does not distinguish the six value-free
problem-response predicates from an inner create-server exception, so no
product repair is evidenced. Freeze that cycle at diagnostic `1/1`, repair
`0/1`, final `0/1` and open one independent product-zero response diagnostic.

The new activation reuses the existing exact-three safe record and strict
reader. Its exact 67-code set is the 24 ordered outer stages, three collection
fallbacks, twelve legacy-query server stages, six ordered reconciliation
response predicates and twenty-two create-server stages. The create server
tuple wins; otherwise the response classifier records only status, body-status,
body-code, media-type, trace or forbidden-envelope stage. It never records the
actual response status, code, body, trace contents, message or stack. Exact-SHA
ordinary PASS is required before one Level 2 controlled run. P8-08 product,
contracts and persistence remain unchanged; P8-09 and production contact stay
closed.
