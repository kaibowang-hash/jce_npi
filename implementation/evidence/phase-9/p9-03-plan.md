# P9-03 — Performance and Resilience Audit Plan

Recorded: `2026-09-03`

Status: `PASS — EXACT-SHA ORDINARY AND LEVEL 3`

Governance checkpoint:
`c845f93d27d29a692582599e4c5bdcec97693223`; exact-SHA ordinary CI
`33689961261` passed before product implementation began.

Product checkpoint `957d307d26bc93fedb08b03fae25f15d0241e1d7`
passes exact-SHA ordinary CI `33693636192` and diagnostics-off Level 3
`33694055699`, including the cumulative disposable-Site runtime. P9-03 is
complete and P9-04 may proceed under its separate security boundary.

## Outcome and boundaries

P9-03 covers only `NFR-PER-001`, `NFR-PER-002`, `NFR-AVL-001` and
`NFR-SCL-001`. It establishes repeatable, non-production engineering evidence
for the already approved LaunchFlow architecture. It does not promise a
production SLA, replace Frappe deployment topology, redesign a domain, or
introduce a generic cache, queue, search engine, telemetry vendor or storage
provider.

The requirement targets remain engineering acceptance thresholds: the fixed
representative common-request set must record at least 95% of samples within
three seconds, and the fixed metadata-search set must complete within five
seconds. A production monthly availability target remains an IT/business
decision because accepted production topology, monitoring windows and
maintenance exclusions do not exist. Any result is labelled with environment,
fixture scale, warm-up, sample count, clock source, commit and checksum.

No production ERPNext or production LaunchFlow connection is needed. The
accepted P8-07F inventory is reused only as compatibility context; its database
and storage topology remain explicitly unverified. ERP-owned truth, integration
reliability semantics, permissions, idempotency and source labels do not change.

## Current implementation audit

| Area | Reusable implementation | Proven gap | Minimum P9-03 action |
| --- | --- | --- | --- |
| Common request latency | BFF routes use operation-specific handlers, bounded page sizes, deterministic cursors and disposable-Site runtime fixtures. | There is no repeatable server-side sample set or percentile evidence. Existing tests prove correctness, not request latency. | Add one fixed disposable-Site measurement harness with warm-up, bounded samples, monotonic timing, deterministic fixtures and machine-readable percentile evidence. Measure representative bootstrap, My Work, Project cockpit, portfolio and configuration reads without production data. |
| Portfolio and search | P9-02 permission-filters every result and caps Projects at 5,000 and source rows at 1,000. | Portfolio and customer search resolve references and related facts per visible Project, so current correctness bounds do not prove representative-scale latency. | Batch only the already-owned reference, work, Gate and ERP-projection reads needed by the fixed queries; retain authorization-first behavior, output order, bounds and explicit unavailable truth. No new search service or cache. |
| Search and large files | Search terms and pages are bounded; controlled files retain exact private identity, hash and authorization. | No five-second metadata-search evidence exists. Production file storage and large-CAD throughput are unverified, so object-store or streaming capacity cannot be claimed. | Measure the fixed metadata-search families at representative scale. Prove request paths never turn large file bytes into search/report payloads and retain the existing controlled download/upload boundary. Record production large-file throughput and storage as an external activation input, not a synthetic PASS. |
| Frontend payload | Routes are React-lazy and the Vite warning threshold remains visible. | Exact P9-02 ordinary CI emits a 2,519.56 kB / 620.55 kB gzip initial JS chunk and 345.14 kB / 36.56 kB gzip CSS. Both Chinese catalogs are eagerly bundled, and `app.tsx` eagerly imports every live data-source implementation. | Load only the selected locale catalog and route-owned data sources on demand, preserving the Frappe catalog source and existing page contracts. Add a deterministic build-budget verifier against explicit initial and route chunk limits. Do not hide or raise the Vite warning. |
| Resilience and availability | Route switches, typed Problem Details, retry/replay/reconciliation, explicit unavailable states, queue-after-commit controls and disposable recovery/cleanup checks already exist. | There is no consolidated P9 availability/resilience proof, and no accepted production monitoring window supports a 99.5% claim. | Reuse existing switches and fault seams to prove bounded timeout, dependency unavailable, queue failure, recovery, concurrent read and cleanup behavior. Report technical readiness only; retain the production SLA hold. |
| Scalability | Project factory references, versioned templates, three locales, tenant/Site isolation and operation-specific integration seams are already distinct. | The repository has no single evidence set showing these dimensions coexist at representative scale without cross-scope leakage. | Exercise multiple factories, projects, template versions and locales in the fixed non-production fixture, verify stable pagination and isolation, and retain MES/CAD/customer-platform connections as later operation-specific adapters rather than a generic extension layer. |

## Frozen implementation batch

The audit/plan transition passed exact-SHA ordinary CI. P9-03 therefore
proceeds as one product batch rather than a chain of micro-commits:

1. Freeze the exact benchmark fixture, sample counts, percentile calculation,
   build-budget inputs, allowed paths and failure thresholds.
2. Apply only statically proven batching to P9-02 reporting/search reads and
   only route/locale loading changes that reduce the initial frontend payload.
3. Add the disposable-Site latency, fault, recovery and multi-dimension scale
   verifier plus deterministic build-output verification.
4. Run affected checks once, then one complete Level 2 and one final Level 3.
   Failures sharing a root are preflighted and repaired together.

The governance transition exact-SHA ordinary PASS authorizes only this bounded
product candidate. No performance result may weaken a functional, permission,
security, i18n, visual, migration or runtime Gate.

## Evidence contract

The final evidence must include:

- exact commit and CI/Gate identifiers;
- operating system, Python/Node/Frappe versions and disposable-Site marker;
- fixture dimensions without business values;
- warm-up policy, sample count, monotonic clock and deterministic percentile
  method;
- per-operation count, minimum, median, P95, maximum and pass/fail threshold;
- initial and route chunk raw/gzip sizes from a clean production build;
- dependency-failure, timeout, recovery, concurrency and cleanup outcomes;
- explicit separation of technical engineering evidence from production SLA,
  storage throughput and capacity claims.

## Tests and Gate

- Pure tests validate percentile math, sample/fixture bounds, build manifest
  parsing, provenance/checksum and fail-closed malformed evidence.
- Repository and API tests preserve response contracts, permission filtering,
  deterministic pagination, explicit unavailable truth and query batching.
- Frontend tests preserve locale switching, full direct `zh`/`zh-TW` coverage,
  route loading, error states and all existing industrial UX behavior.
- Disposable-Site verification covers normal, empty, representative-scale,
  no-permission, dependency-unavailable, timeout, concurrent, recovery and
  exact-cleanup cases.
- The task closes only after exact-SHA ordinary CI and one diagnostics-off
  Level 3 both pass. Production SLA acceptance remains a separately owned
  release input.

## Rollback

Before product code is released, restore exact P9-02 checkpoint
`36cfe4cec8f31525e836c714236116704be066f3`; the transition changes governance
and evidence only. After implementation, revert only the independently frozen
P9-03 batching/loading/verifier paths, retain the measured evidence as an
invalidated historical record, and deliver a reviewed forward fix. Never
restore performance by relaxing thresholds, authorization, data bounds,
translation coverage or failure truth.
