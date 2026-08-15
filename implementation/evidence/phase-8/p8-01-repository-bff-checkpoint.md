# P8-01 Checkpoint 2 — Durable Projection Repository and Read-only BFF

Recorded: `2026-08-16`

Decision: `PASS — CHECKPOINT 2; CHECKPOINT 3 AUTHORIZED`

Implementation and final product checkpoint:
`fd4fc6a7383d43b92cf363cebc08b6c8c7faeb3c`

Ordinary pull-request CI: `31909152423`

## Scope delivered

- Added seven explicit reader seams for Customer, Supplier, formal Item,
  Tooling procurement/cost, Project cost, formal quality status and Tool Asset
  status. Mock remains unavailable and network-free; the frozen sandbox seam
  has no live mapper or transport; disposable synthetic input remains visibly
  non-authoritative.
- Added Project/context-first server scope enumeration and a bounded internal
  refresh of at most `200` Projects under one correlation identity. The caller
  cannot select a target endpoint, DocType, method, credential, version,
  success, freshness or authority.
- Added immutable observation persistence plus an exact locked guarded head.
  Event identity and payload hash are sealed; newer, older, exact duplicate,
  equal-time conflict, unavailable and synthetic results remain distinct.
  Observation, conditional head advance and structural audit commit in one
  guarded transaction, including restart/failure boundaries.
- Added a default-disabled, Project-first read-only collection route at
  `/api/npi/v1/projects/{projectId}/erp-projections`. Authentication and exact
  Project/current-membership authorization precede every optional filter and
  secondary identity. The response is recursively closed, bounded, sorted and
  validated before Frappe serialization; external actors receive the frozen
  redacted shape and never a raw target error or secret.
- Injected only exact confirmed-current typed snapshots into the existing
  Tooling manufacturing cost and acceptance Asset readers. Unavailable,
  stale, synthetic, conflicted, cross-Project, cross-tenant or mismatched-head
  observations cannot become formal cost or Asset truth.
- The checkpoint adds no public webhook/Inbox, target write, retry/DLQ/replay
  operation, scheduler, production host/credential/mapping, Trial Summary/JCE
  Core behavior, Project/Gate/health/readiness/Tooling lifecycle mutation or
  browser-to-ERP call.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| seven reader seams and bounded worker | exact named operation dispatch; Mock/sandbox no-network; synthetic unavailable; bounded Project collection |
| Frappe projection repository | Project-first real/absent IDOR; current membership; redaction; atomic insert/head/audit; duplicate/reorder/conflict/unavailable/restart/lock tests |
| projection API, core BFF and response validator | auth-before-filter; exact route; request ID; closed/bounded/sorted response; read-only/default-disabled behavior |
| Tooling cost and Asset reader injection | exact tenant/Project/head/observation validation; confirmed-current only; existing P6 manufacturing/acceptance regressions |
| OpenAPI and direct translations | route/current-truth/redaction closure; generated catalog symmetry; no raw target error/secret |
| focused Phase 8 tests | repository, API, consumer and runtime-boundary regression with no production literal or transport |

## Local Level 1 and task evidence

- Focused P8 repository/BFF/consumer suite: `34/34 PASS`.
- Full tracked repository verification plus six pre-existing local-only
  prerequisite tests: `1,963/1,963 PASS`; the clean exact-SHA CI count below
  is authoritative for committed code.
- Existing Tooling manufacturing-cost and acceptance-Asset affected suites:
  PASS, including unavailable, typed exact-current and no-lifecycle-mutation
  behavior.
- Frontend generation, type, lint, format, styles, boundary, industrial-UI,
  i18n, unit, coverage and production build checks: PASS. Local unit evidence
  is `59/59` files and `918/918` tests; the direct catalog contains `7,554`
  English sources with complete `zh`/`zh-TW` coverage.
- The final local production-asset audit alone sees the user's pre-existing
  untracked `frontend/public/images/npi-one-project-management-sketch.png`.
  It is outside this checkpoint and was neither modified nor staged. The clean
  exact-SHA CI below is the authoritative asset/brand result.
- Current-task, V1.2 reconciliation, Python compile, generated catalog and
  `git diff --check`: PASS.

## Exact-SHA ordinary CI evidence

- Repository job `95071497748`: PASS; `1,957` tracked Python tests plus
  repository, current-task and V1.2 reconciliation verification.
- Frontend job `95071497747`: PASS; `59/59` files, `918/918` unit tests,
  `421/421` E2E, generation/type/lint/build/audit, `7,554` complete direct
  trilingual sources, zero vulnerabilities and coverage `80.31%` statements,
  `80.16%` branches, `82.81%` functions and `82.96%` lines.
- Secret job `95071497699`: PASS; `27` first-parent task commits and `498`
  complete branch commits contain no leak. Artifact `9253173621`, digest
  `sha256:afe9cb716cd9047034cfa19f2fe9c31eea0cc0e49eedf178b8ece79da50b793d`.
- Visual job `95071497717`: PASS; unchanged `119/119` fixed-Linux matrix.
  Artifact `9253219631`, digest
  `sha256:de0e17de39195f246925b8daf51c41c7e18ec7559033d18093fc1441f85df2e9`.
- Controlled preflight and cumulative runtime skip as expected. Checkpoint 2
  adds no controlled fixture, live mapper, external transport or production
  configuration; the final P8-01 Level 3 checkpoint retains the disposable
  Site, migrate-twice and zero-production-traffic proof.

## Review and rollback

The Task Diff Review found no generic target CRUD, caller-selected target
identity, browser-to-ERP request, production endpoint/credential/data,
cross-database access, raw target error, target-owned mutation, inferred
freshness/EAC/Gate rule or optimistic target success. The route is GET-only
and default-disabled; the worker has no production configuration and performs
no live network request.

Before retained rows exist, rollback may disable the projection route and
reader hooks and remove fresh disposable schema. After any observation/head/
audit history exists, rollback disables only future refresh, route and injected
readers, retains all immutable history and ships a reviewed forward repair. It
never deletes observations, rewrites source identity/version/hash, moves a head
backward, changes unavailable into available or contacts ERPNext.

This is checkpoint 2 PASS. It is not P8-01 Level 2 or Phase 8 Level 3. Only
checkpoint 3 dense direct-trilingual read-only product truth is authorized.
