# P9-03 Performance and Resilience Validation

## Decision

P9-03 retains the approved LaunchFlow architecture and makes only three local,
reversible changes: batch existing authorized reporting reads, defer route-owned
data sources and full locale catalogs, and enforce repeatable non-production
performance budgets. It adds no cache, search service, queue, telemetry vendor,
production connection, domain abstraction or production SLA.

## Frozen evidence method

- Runtime environment: the existing disposable local Frappe Site created and
  destroyed by `scripts/verify-frappe-runtime.sh`; production systems are never
  contacted.
- Runtime clock: `perf_counter_ns`; two warmups followed by twenty recorded
  samples for each operation; P95 is nearest-rank.
- Thresholds: common Project portfolio, KPI availability and configuration
  reads are at most 3,000 ms P95; bounded metadata search is at most 5,000 ms
  P95.
- Provenance: the runtime emits only environment label, fixed method/counts,
  timings, thresholds and a checksum of top-level response keys. It emits no
  credential, identity, business value or endpoint.
- Frontend method: the clean production build identifies entry assets from
  `dist/index.html`, measures raw bytes and deterministic level-9 gzip bytes,
  and fails closed on an initial, route-lazy or selected-locale-catalog budget
  violation. Locale catalogs are classified separately and capped at 700,000
  raw / 180,000 gzip bytes; the route cap stays 500,000 / 110,000 bytes.

## Local implementation evidence

| Concern | Before | P9-03 result | Bound |
| --- | ---: | ---: | --- |
| Initial JavaScript | 2,519.56 kB / 620.55 kB gzip | 804,996 / 196,501 deterministic-gzip bytes | 850,000 / 220,000 bytes |
| Initial CSS | 345.14 kB / 36.56 kB gzip | 345,141 / 35,942 deterministic-gzip bytes | 380,000 / 42,000 bytes |
| Largest lazy route | not isolated | 445,556 / 95,616 deterministic-gzip bytes | 500,000 / 110,000 bytes |
| Largest selected-locale catalog | both full catalogs were in the initial chunk | 639,991 / 166,359 deterministic-gzip bytes | 700,000 / 180,000 bytes |
| Portfolio database reads | grows by Project | five bounded reads independent of selected Project count | fixed-query regression |
| Customer metadata search references | one Project document read per visible Project | one bounded child-reference query | permission-filtered parent set |

The generated catalog version remains in the entry bundle, while full `zh` and
`zh-TW` catalogs are separate modules loaded only for the selected development
fallback locale. The production session catalog remains authoritative. A tiny
generated startup catalog contains only the two loading/brand strings required
to prevent a mixed-language transient. Live Project, Gate, Work, Tooling,
Tooling Import, Trial and Execution data sources are instantiated only with
their lazy route; Shell-owned Project controls, reporting and collaboration
sources remain shared.

## Correctness, resilience and scale

- Batch reads begin with the unchanged tenant/owner/member-visible Project set.
  Every child, work, Gate, ERP projection and search result is rejected if its
  Project key escapes that set. Existing deterministic cursor ordering and
  stale/partial/unavailable ERP truth remain unchanged.
- Portfolio enrichment happens only for the selected page. Result caps remain
  explicit and excess rows fail closed.
- The cumulative disposable-Site sequence retains disabled-route failure,
  cross-process idempotent replay, route restart/recovery, dependency failure,
  explicit error truth, redaction and exact cleanup. P9-03 adds measurements to
  that same functional sequence rather than a synthetic success path.
- Multi-factory filtering continues through typed Project references;
  multi-template ownership remains on the existing immutable Project template
  snapshot; `en`, `zh` and `zh-TW` use the same source keys and selected-locale
  loading. Future MES/CAD/customer adapters remain operation-specific and are
  not implemented by this task.

## Held facts

The 3-second and 5-second results are engineering acceptance evidence only.
Production database, file/object storage, worker topology, capacity, monitoring
window and maintenance exclusions remain unverified. Therefore P9-03 makes no
large-CAD throughput claim and does not accept or claim the suggested 99.5%
production availability target. Those facts remain an IT/business decision and
release input.

## Verification checkpoint

Governance transition `c845f93d27d29a692582599e4c5bdcec97693223`
passed exact-SHA ordinary CI `33689961261` in repository, secret, frontend,
both E2E shards, governed visual and frontend aggregate lanes. The product
candidate's local Level 2 passes `2,891/2,891` repository tests,
`1,117/1,117` frontend units with 80.07% statement coverage, `463/463`
nonvisual E2E, generation, type checking, lint, 8,982-source complete
`zh`/`zh-TW` coverage, build budgets and reconciliation/diff checks. The host's
npm 11.3 cannot execute the repository-pinned npm 11.16 `approve-scripts`
command, so the clean exact-SHA CI frontend lane remains the authoritative
install-script and audit proof. The product candidate must pass exact-SHA
ordinary CI and one diagnostics-off Level 3 including the cumulative disposable
runtime before P9-03 can close. Until then this file is candidate evidence, not
a release PASS.

## Rollback

Revert the reporting batch adapter, lazy route wrappers, split catalog generator
and build/runtime budget verifiers as one P9-03 product commit. No database
migration, external state or production data requires rollback. Preserve this
record as invalidated history and use a reviewed forward fix if a later clean
build or disposable runtime differs.
