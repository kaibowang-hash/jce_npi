# P8-01 Checkpoint 1 — Projection Domains, Contracts and Guarded Metadata

Recorded: `2026-08-16`

Decision: `PASS — CHECKPOINT 1; CHECKPOINT 2 AUTHORIZED`

Implementation commit:
`4e4308aedac96c10a498c2b599055c2ecd2ce21a`

Final checkpoint:
`6d88175582ac09fdc3ef542f1443e5213cb9a6d6`

Ordinary pull-request CI: `31905949549`

## Scope delivered

- Added an exact seven-kind pure projection catalog for Customer, Supplier,
  formal Item, Tooling procurement/cost, Project cost, formal quality status
  and Tool Asset status. Each kind owns one closed value normalizer, allowed
  server-owned scope and operation-specific event/source-object type.
- Added canonical payload hashing and explicit availability, freshness and
  application dispositions. Source ordering uses exact modified time only;
  opaque versions are never compared lexically. Newer, older, exact duplicate,
  equal-time conflict and same-event hash-conflict outcomes are distinct. No
  freshness policy returns `unknown`.
- Added fail-closed adapter configuration. Mock is disabled and network-free;
  synthetic proof is disposable and non-authoritative; sandbox requires an
  immutable exact operation/hostname allowlist, HTTPS origin, explicit
  non-production attestation and a separate bounded secret reference. IP,
  localhost, production/live labels, user info, redirects, invalid origins and
  fallback hosts are rejected. No transport or network client is implemented.
- Extended the integration-event Schema with seven closed version-1
  observation payloads and exact service/source/target/correlation/hash
  constraints. Added only reusable OpenAPI read schemas—no projection route—
  and corrected Supplier plus observation/head ownership without transferring
  any ERP business field to NPI One.
- Added guarded `NPI ERP Projection Observation` and
  `NPI ERP Projection Head` support DocTypes. Observation history is
  append-only; head stream identity is immutable, guarded writes advance the
  optimistic version by exactly one, and current/refresh pointers must resolve
  to the exact observation stream. Business roles cannot create, write,
  delete, export, print or email either record.
- Added direct Simplified and Traditional Chinese translations and regenerated
  the Frappe-backed React catalog. This checkpoint activates no repository
  writer, route, scheduler, fixture/default row, business mutation, webhook,
  target execution or external call.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `npi_integration/projections/domain.py` | all seven closed shapes; exact/type/size rejection; hash; ordering/disposition; availability/freshness tests |
| `npi_integration/projections/config.py` | Mock/synthetic no-network truth; immutable allowlists; HTTPS/host/environment/secret/redirect/production rejection |
| integration event, OpenAPI and ownership contracts | seven event/kind/scope/value mappings; exact envelope; closed read schemas; no route; ERP-owned business truth |
| observation/head DocTypes and controllers | exact fields/links; narrow internal flags; append-only/delete denial; stream/snapshot/hash/version guards; no generic CRUD |
| both Frappe translation CSVs and generated catalog | generation check; direct `zh`/`zh-TW` symmetry and coverage; mixed-language scan |
| focused Phase 8 tests | checkpoint-1 no-route/repository/scheduler/network/fixture assertion and complete contract regression |

## Local Level 1 and task evidence

- Focused Phase 8 domain/contract/metadata tests: `17/17 PASS`.
- Current-task plus reconciliation affected suite: `49/49 PASS`;
  `scripts/verify_current_task.py`, trace reconciliation and generated-state
  verification pass.
- Repository verification passes locally. The dirty development worktree also
  contains six pre-existing untracked local-prerequisite tests, so its local
  count is `1,946`; the clean exact-SHA CI count below is the authoritative
  tracked count.
- Exact Node `24.18.0`/npm `11.16.0` catalog generation check and i18n audit:
  PASS at `7,552` literal English sources with `100%` direct `zh`/`zh-TW`
  coverage.
- JSON, YAML, Python compilation and `git diff --check`: PASS. The final scoped
  review confirms no generic `read_doc`/SQL/write helper, request library,
  scheduler registration, BFF route, fixture row or production endpoint.

## Exact-SHA ordinary CI evidence

- Repository job `95063650353`: PASS; `1,940` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95063650577`: PASS; `59/59` files, `918/918` unit tests,
  `421/421` E2E, generation/type/lint/build/audit, `7,552` complete direct
  trilingual sources, zero vulnerabilities and coverage `80.33%` statements,
  `80.18%` branches, `82.81%` functions and `82.98%` lines.
- Secret job `95063650349`: PASS; `27` first-parent task commits and `496`
  complete branch commits contain no leak. Artifact `9252339236`, digest
  `sha256:fc27bac3e8065516e539f7d8746e4ff7bfb5a2f0a7d552113baaad95df9762f7`.
- Visual job `95063650319`: PASS; unchanged `119/119` fixed-Linux matrix.
  Artifact `9252381948`, digest
  `sha256:996165540f1bba9e503dab7f1203521dbe8576a514097ae9ea7767aec8f20d5b`.
- Controlled preflight and cumulative runtime skip as expected because the
  checkpoint opens no route, repository worker, runtime fixture, persisted
  business row or external transport.

## Diagnostic evidence and repair

Initial implementation SHA `4e4308a` passed repository, secret and unchanged
`119/119` visual jobs in ordinary CI `31905640883`; frontend correctly stopped
at `generate:check` because the two updated Frappe CSV catalogs had not yet
regenerated the React catalog. The same review also found that `ERP` is not an
approved retained Latin token in Chinese UI text. Final checkpoint `6d88175`
expands that term to `企业资源计划`/`企業資源規劃` and regenerates the catalog.
Fresh complete CI `31905949549` passes without changing product behavior,
acceptance criteria or checkpoint boundaries.

## Review and rollback

The Task Diff Review found no caller-selected endpoint/DocType, browser input,
target credential, raw response/error body, production literal, generic CRUD,
business-field owner transfer, lexical source-version ordering, inferred
freshness, EAC formula, quality-to-Gate interpretation or target success.
Synthetic truth remains visibly non-authoritative and Mock cannot become
available.

Before retained rows exist, rollback may remove the two additive support
DocTypes on a disposable Site and return to the P8-00 product boundary. After
history exists, rollback disables only future checkpoint-2/3 routes and worker
activation, retains every observation/head/audit record and ships a reviewed
forward repair. It never deletes history, rewrites a source version/hash,
moves a head backward or contacts ERPNext.

This is checkpoint 1 PASS. It is not P8-01 Level 2 and does not replace the
final P8-01 Level 3 release gate.
