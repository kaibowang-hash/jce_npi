# P8-03 Checkpoint 1 — Item Publish Domains, Contracts and Guarded Metadata

Recorded: `2026-08-16`

Decision: `PASS — CHECKPOINT 1; CHECKPOINT 2 AUTHORIZED`

Final product checkpoint:
`1c1faa771ef8a129467fa4376edbcede12a9ecbb`

Ordinary pull-request CI: `31950411271`

## Scope delivered

- Added dependency-free Item-only source grouping over one exact tenant,
  Project and case-preserved engineering identity. All repeated released EBOM
  occurrences are retained in deterministic order; divergent description,
  engineering UOM or attributes fail closed, and MBOM quantity, hierarchy,
  alternates and effectivity never enter the Item-master payload.
- Added immutable released-source, execution-profile reference, mapping
  expectation, request, adapter-observation, fault-classification, mapping-CAS
  and claim-lease domains. Mock cannot emit an Outbox event, synthetic proof is
  non-authoritative, and only an authenticated authoritative Sandbox success
  with exact formal identity/version can advance a mapping.
- Added strict no-default Mock, disposable network-free synthetic and
  non-production Sandbox configuration shapes. Sandbox configuration requires
  an exact HTTPS origin/hostname allowlist, opaque secret reference, closed
  operation, response-authentication mode, bounded timeouts and scoped tenant,
  Project, requester and service actor. Production/live hosts, IP literals,
  localhost, redirects, raw network authority and broad actors fail closed.
- Added closed Item-only request/result event schemas, OpenAPI data schemas and
  split field ownership. No Item route is activated and no caller controls an
  endpoint, method, DocType, credential, formal Item code or success truth.
- Hardened the shared Outbox additively for guarded version-1 Item envelopes
  while preserving legacy permission and field compatibility. Legacy rows
  cannot be promoted. Item envelopes bind request, tenant, Project, profile,
  source/mapping versions, actor, trace and idempotency; terminal history is
  frozen and a crossed adapter boundary cannot return to pending.
- Added six read-only support DocTypes for request, actor-bound command
  idempotency, attempt, result, mapping observation and mapping head. Narrow
  internal flags guard all writes, append-only records deny update/delete, and
  mapping heads require exact authoritative observations with version-by-one
  advancement.
- Added direct Simplified and Traditional Chinese translations and regenerated
  the Frappe-backed React catalog. No frontend route, workspace, style or
  visual baseline changed.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `item_publish/domain.py` | occurrence grouping/conflict, canonical identities/hashes, create/update expectation, authoritative mapping, fault matrix and lease tests |
| `item_publish/config.py` | exact Mock/synthetic/Sandbox shape, scoped actors, operation/host/origin/secret/auth/timeout validation and production rejection |
| event/OpenAPI/ownership contracts | closed Item-only fields, no MBOM/transport authority, authenticated formal identity and one-way ERP/NPI ownership tests |
| Outbox and six support DocTypes/controllers | legacy non-promotion, read-only permissions, narrow write flags, immutable/one-way history, terminal freeze and formal-mapping authority tests |
| both Frappe translation CSVs and generated catalog | generation check, direct `zh`/`zh-TW` symmetry, 100% coverage and mixed-language audit |
| focused Phase 8 tests | no BFF route, repository, worker, adapter, scheduler, network, fixture or business-row activation |

## Local Level 1 and task evidence

- Focused P8-03 domain/configuration/metadata/contract tests: `27/27 PASS`;
  affected Phase 2 metadata/foundation regression set: `42/42 PASS` including
  the focused tests.
- Full local repository Task Gate: `2,054/2,054 PASS`; six pre-existing
  untracked local-prerequisite tests explain the difference from the clean CI
  count. Development-container, prototype approval, P0 visual governance and
  V1.2 reconciliation verification also pass.
- Exact Node `24.18.0`/npm `11.16.0` generation check, i18n audit and type
  check pass. The audit reports `7,872` literal English sources with `100%`
  direct `zh`/`zh-TW` coverage.
- JSON/YAML parsing, current-task verification, reconciliation, staged and
  exact-commit Gitleaks and `git diff --check`: PASS.
- Task Diff Review confirms no BFF route, repository request/Outbox insert,
  worker, adapter registry/call, scheduler, default profile, target host,
  credential, formal mapping, generic retry/replay or production traffic.

## Exact-SHA ordinary CI evidence

- Repository job `95172902059`: PASS; `2,048` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95172902078`: PASS; `60/60` files, `933/933` unit tests,
  `426/426` E2E, generation/type/lint/build/audit, `7,872` complete direct
  trilingual sources, zero vulnerabilities and coverage `80.36%` statements,
  `80.20%` branches, `83.00%` functions and `82.99%` lines.
- Secret job `95172902103`: PASS; `25` first-parent task commits and `527`
  complete branch commits contain no leak. Artifact `9264480505`, digest
  `sha256:7c0d8b2dc8f3acb1850b73add27193bb4be1cbae70d213919c91f833f5aa33ef`.
- Visual job `95172902112`: PASS; unchanged `119/119` fixed-Linux matrix.
  Artifact `9264530147`, digest
  `sha256:3a56bbad5c4d6a89d24c64d6c49b9d2b108e7301b396db2859d1fa2688d193a9`.
- Controlled preflight and cumulative runtime skip as expected because this
  checkpoint activates no route, repository row, worker, adapter, fixture,
  business row or external transport.

## Review and rollback

The Task Diff Review found no first-occurrence-wins grouping, cross-Project
identity, caller-selected target/method/authority, MBOM field leakage, Mock or
synthetic formal mapping, optimistic HTTP success, legacy Outbox promotion,
terminal history rewrite, adapter-boundary requeue, raw secret, generic CRUD,
production fallback or target call.

Before retained rows exist, rollback may remove the additive checkpoint-1
metadata on a disposable Site and return to the P8-02 boundary. After retained
request/Outbox/attempt/result/mapping history exists in later checkpoints,
rollback disables new routes/enqueue/claims, retains all immutable evidence
and uses reviewed forward repair. It never deletes or requeues uncertain
history, rewrites Mock/synthetic/failure to success, changes a formal Item code,
mutates released source or contacts production ERPNext/JCE.

This is checkpoint 1 PASS. It is not P8-03 completion or Phase 8 Level 3.
