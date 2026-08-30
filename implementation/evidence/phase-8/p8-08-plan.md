# P8-08 Plan — Released Trial Summary Read-Only Projection Seam

Status: **AUDIT PLAN PASS — CHECKPOINT 1 AWAITS EXACT-SHA ORDINARY CI**

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

Checkpoint-1 product implementation is now authorized only on the exact five
product/test paths frozen below and awaits its own exact-SHA ordinary CI.

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

Eligible new paths are limited to
`apps/npi_integration/npi_integration/released_summary_projection/source.py`
and `tests/test_phase8_released_trial_summary_projection_source.py`, plus the
exact governance/evidence paths.

### Checkpoint 3 — disposable runtime and final Gate

Only after checkpoint 2 exact-SHA ordinary CI passes, extend the existing fixed
disposable, network-free runtime to prove Project containment, exact current
source, stale/conflict/unavailable behavior, cross-process deterministic
hashes, zero rows/writes/network, migration twice and cleanup. Then run the
P8-08 final Level 3. Production ERPNext is not contacted by this Gate.

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
