# P9-05 — Historical Migration Rehearsal Audit Plan

Recorded: `2026-09-03`

Status: `AUDIT AND PLAN — PRODUCT CODE HELD PENDING EXACT-SHA ORDINARY CI`

Base checkpoint:
`fa82f3e3dcc7a9474ea51a1356130d5cbc02adee`

## Outcome and boundaries

P9-05 covers only `FR-RP-008` and `NFR-DAT-001`. It adds a controlled,
operation-specific historical migration rehearsal for existing Projects,
Tooling mappings, file indexes and approved NPI-owned reference data. It does
not create a generic DocType writer, redesign current domains, copy an ERP
database, import ERP-owned truth as a second master, or authorize production
migration.

The current LaunchFlow architecture and data ownership remain the baseline.
The task uses one authorized, clean, private File Revision as the immutable
source and accepts only a closed, versioned bundle with a canonical manifest.
All preview and validation can run without mutation. Apply and rollback paths
are additionally gated by an exact non-production Site switch and System
Manager plus server-side object authorization. Production ERPNext and
production LaunchFlow are not contacted.

## Current implementation audit

| Area | Reusable implementation | Proven gap | Minimum P9-05 action |
| --- | --- | --- | --- |
| Source custody | Controlled Document/File Revision already supplies private identity, immutable version/hash, clean scan truth and authorized byte retrieval. | No historical migration bundle schema or manifest binds all source members and row identities. | Add a bounded standard-library bundle reader for one exact File Revision. Freeze member names, byte/row/field limits, UTF-8 CSV rules, manifest schema/version and per-member hashes; reject paths, duplicates, extra members, formulas and malformed rows. |
| Project records | Project creation already validates type, code uniqueness, templates, references, tenant and Project permissions with idempotency and audit. | No batch preview can compare historical rows with existing Projects or preserve stable legacy source keys. | Build a non-mutating create/link/skip/blocked plan through existing Project contracts. Retain source-system/key hash, exact target version/hash and differences; never bypass the normal Project repository. |
| Tooling mappings | Tooling Master/Revision/Applicability and external identities are distinct; P6-07 proves immutable mapping, preview, partial result, correction, reconciliation and guarded rollback mechanics. | P6-07 is a customer Tooling List workflow scoped to one Project and 43 reviewed columns; overloading it would corrupt its contract and cannot cover cross-Project historical mappings. | Add an independent historical mapping row that calls existing Tooling operations and records exact target identity/version. Reuse P6-07 safety patterns and shared primitives only; do not rename or broaden its routes, states or mapping catalog. |
| File index | File and Document APIs preserve Project containment, confidentiality, hash, revision and release truth. | There is no batch operation that validates a historical file index without ingesting arbitrary paths or pretending missing bytes are present. | Accept metadata references only to already registered exact File Revisions. Preview missing, mismatched, forbidden or duplicate entries as blocked; never read a filesystem path, fetch an endpoint or create a fake File. |
| Reference data | Project references and ERP projections already keep source system/object identity and declared ownership. | No closed allowlist defines which historical reference rows may be linked versus which ERP-owned rows must remain unavailable. | Allow only NPI-owned reference/link kinds frozen in the bundle schema. ERP Customer/Supplier/Item/MBOM/cost/quality/Asset facts remain reference-only and must resolve to accepted projections or block. |
| Data quality and correction | Domain validators, canonical hashes, typed Problem Details, idempotency, audit and P6-07 correction artifacts exist. | No cross-file required/unique/enum/reference/version validation or complete difference report exists for historical data. | Produce one immutable preview revision with row/field findings and deterministic summary; create a private allowlisted correction CSV for failed rows; retry only a successor artifact bound to the original manifest and preview. |
| Apply, reconciliation and rollback | Existing repositories use transactions, after-commit jobs, immutable results, reconciliation and exact rollback guards. | No non-production historical rehearsal job proves partial truth, replay, timeout-after-commit, conflict and rollback/forward-fix outcomes. | Add one default-disabled durable rehearsal job. Reauthorize actor/source/preview before apply; keep successful, failed-retryable and failed-final rows explicit; reconcile exact target hashes; remove only unchanged unreferenced batch-created objects and require forward correction otherwise. |
| Administration UX | The independent SPA has an Administration capability surface, shared worklists, tables, inspectors, downloads, errors and trilingual Frappe catalogs. | There is no operator flow for source, validation, preview, difference, apply, correction and rollback evidence. | Add one dense Administration workspace using the BFF only, with a single primary action per state, explicit non-production label, row/field difference table, private correction download, trace IDs and complete English/`zh`/`zh-TW` states. |

## Frozen bundle and execution boundary

The implementation batch will freeze
`historical-migration-rehearsal.v1` rather than accept caller-selected
DocTypes or fields. One manifest binds exactly four logical row families:
Projects, Tooling mappings, file-index references and approved NPI reference
links. Each row carries a stable source key; target UUIDs are server-resolved
and never trusted from a free-form writer payload.

The bundle parser is bounded before allocation and returns structural codes in
ordinary logs. Raw values are visible only in the exact authorized preview or
private correction artifact. Required, unique, enum, reference, ownership,
target-version and source-hash validation complete before any apply command.
The preview is immutable and non-mutating; an exact manifest/preview hash,
expected version, actor-bound idempotency key and active non-production Site
switch are mandatory for execution.

Apply uses existing operation-specific Project, Tooling and File boundaries.
It never writes an arbitrary DocType or ERP-owned field. Partial work remains
partial. A timeout after commit is resolved by receipt/reconciliation, never
blind redispatch. Correction creates a successor source artifact and retries
only eligible failed rows. Rollback is allowed only for an exact unchanged,
unreferenced object created solely by the rehearsal batch; otherwise the
durable result requires forward correction.

## Single implementation batch after governance PASS

After this audit/plan transition passes exact-SHA ordinary CI, P9-05 proceeds
as one product batch:

1. Freeze the closed bundle/domain contracts, exact routes, permissions,
   DocTypes, allowed paths, synthetic fixtures and output size bounds.
2. Implement bounded source inspection, immutable validation/difference
   preview, private correction artifact and non-production-only durable apply,
   reconciliation and guarded rollback.
3. Add the BFF Administration workspace and complete literal-English,
   Simplified Chinese and Traditional Chinese catalogs without exposing Desk
   or direct DocType CRUD.
4. Extend the disposable-Site verifier with fresh, replay, conflict,
   timeout-after-commit, partial, stale, correction, reconciliation,
   rollback-allowed, rollback-denied, route recovery and cleanup cases.
5. Run affected checks once, one complete Level 2 and one final Level 3.
   Common-root failures are preflighted and repaired together.

## Evidence contract

Final evidence must bind exact commit and CI/Gate IDs; source and manifest
hashes; schema/policy versions and limits; sanitized family/row/finding counts;
preview and difference hashes; actor/idempotency/trace identities; per-row
apply truth; correction/retry lineage; reconciliation results; rollback or
forward-correction decisions; two migrations; route recovery; cleanup and
`productionContact=false`. No real business values, credentials, endpoints or
production records may enter Git or ordinary logs.

## Tests and Gate

- Pure tests cover archive/member/CSV bounds, manifest hashes, required/unique/
  enum/reference/version findings, deterministic differences and malformed
  input failure.
- Repository/API tests cover System Manager and object authorization, IDOR,
  exact source/preview binding, idempotent replay/conflict, transaction order,
  partial results, private correction download and rollback denial.
- Frontend unit/E2E/visual tests cover empty/loading/valid/blocked/partial/
  stale/conflict/retry/rollback states, three languages, keyboard access and
  industrial table/inspector behavior.
- Disposable Frappe runtime uses synthetic non-production data only and proves
  apply/replay/reconciliation/rollback with zero ERP or production traffic.
- P9-05 closes only after an exact-SHA ordinary CI and one diagnostics-off
  Level 3 both pass.

## Rollback

Before product resume, restore exact P9-04 checkpoint
`fa82f3e3dcc7a9474ea51a1356130d5cbc02adee`; the transition changes governance
only. After implementation, disable the rehearsal route first, revert only
the independent P9-05 metadata/domain/API/UI/verifier paths, retain immutable
evidence as invalidated history, and use forward correction for any object
that is changed or referenced. Never obtain rollback by deleting history,
relaxing authorization or enabling a generic writer.
