# P8-02 Checkpoint 1 — Signed Event Domains and Guarded Metadata

Recorded: `2026-08-16`

Decision: `PASS — CHECKPOINT 1; CHECKPOINT 2 AUTHORIZED`

Final product checkpoint:
`a040f21d4379d529f9524bbf09c1ac5016fe6881`

Ordinary pull-request CI: `31930363720`

## Scope delivered

- Added dependency-free canonical JSON and the exact two version-1 submitted
  source events: ERPNext Quotation and Sales Order to NPI One. Duplicate keys,
  floats, non-finite values, invalid UTF-8/Unicode, unexpected or missing keys,
  noncanonical UUIDs, invalid exact-second UTC timestamps/dates, nonpositive
  source versions and payload-hash drift fail closed.
- Added fixed `POST /api/npi/v1/integration/erpnext/project-source-events`
  signing input that binds method, path, key ID, Unix timestamp, canonical
  request UUID and the exact raw body. HMAC-SHA256 comparison is constant-time;
  the replay window is inclusive at 300 seconds.
- Added immutable non-production source-profile, rotating-key and intake-policy
  domains. Distinct overlapping key IDs are allowed; unknown/expired keys,
  production/live/unknown environments, raw-secret-shaped configuration,
  Guest/Administrator actors, incomplete event/policy coverage and missing
  injected secret resolution fail closed. No profile, key, policy or secret is
  installed.
- Added explicit event-identity, source-order and bounded claim-lease domains.
  Exact duplicate, hash conflict, advance, superseded and received-after-
  creation outcomes are distinct and source order uses only positive versions.
- Extended the shared integration-event Schema, OpenAPI and ownership contract
  with the closed HMAC-only intake contract and one-way ERP/NPI responsibility.
  The OpenAPI operation is declarative only in this checkpoint; no BFF route is
  active.
- Hardened the existing Inbox additively while preserving required legacy
  fields and its historical System-Manager read permission shape. Version-1
  receipts freeze event, raw body, payload, source key, profile/policy,
  signature and receipt hashes; legacy rows remain readable but cannot be
  promoted or changed.
- Added guarded `NPI Project Source Binding` support metadata with one hashed
  tenant/profile/type/source identity, positive highest source head, optional
  immutable bound Project result and exactly advancing optimistic version.
  Generic creation/write/delete remains denied without narrow service flags.
- Added direct Simplified and Traditional Chinese translations and regenerated
  the Frappe-backed React catalog. No frontend surface or visual baseline
  changed.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `inbound_project/domain.py` | closed parser/event hashes, exact event shapes, source identity/order and claim lease tests |
| `inbound_project/signature.py` and `config.py` | raw-byte mutation, method/path/header binding, replay edges, constant-time comparison, rotating keys and production/raw-secret rejection |
| shared event/OpenAPI/ownership contracts | exact two-event/system/actor/payload mapping, HMAC-only route contract, one-way ownership and never-persist secret assertions |
| Inbox and source-binding DocTypes/controllers | additive legacy compatibility, immutable snapshots/hashes, source-key identity, narrow write flags, delete denial and no generic CRUD |
| both Frappe translation CSVs and generated catalog | generation check, direct `zh`/`zh-TW` symmetry, 100% coverage and mixed-language audit |
| focused Phase 8 tests | no route/repository/scheduler/network/fixture activation and P8-01 projection regression coverage |

## Local Level 1 and task evidence

- Focused P8-02 plus affected P8-01 projection-contract tests: `25/25 PASS`.
- Full local repository Task Gate: `1,996/1,996 PASS`; six pre-existing
  untracked local-prerequisite tests explain the difference from the clean CI
  count. Development-container, prototype approval, P0 visual governance and
  V1.2 reconciliation verification also pass.
- Exact Node `24.18.0`/npm `11.16.0` generation check, i18n audit and type
  check pass. The audit reports `7,706` literal English sources with `100%`
  direct `zh`/`zh-TW` coverage; focused i18n tests pass `23/23`.
- JSON and YAML parsing, Python compilation, current-task verification,
  reconciliation, local one-commit Gitleaks and `git diff --check`: PASS.
- Task Diff Review confirms no route implementation, repository insert,
  scheduler registration, worker, Project creation, default profile, secret,
  request library, external host or network call.

## Exact-SHA ordinary CI evidence

- Repository job `95124090677`: PASS; `1,990` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95124090661`: PASS; `60/60` files, `933/933` unit tests,
  `426/426` E2E, generation/type/lint/build/audit, `7,706` complete direct
  trilingual sources, zero vulnerabilities and coverage `80.36%` statements,
  `80.20%` branches, `83.00%` functions and `82.99%` lines.
- Secret job `95124090655`: PASS; `25` first-parent task commits and `513`
  complete branch commits contain no leak. Artifact `9259085371`, digest
  `sha256:8d335ed28fe3d7ea5fd123d4c5d4eb67618d27bfeab1f7fd6afedd0f66d8f3fd`.
- Visual job `95124090840`: PASS; unchanged `119/119` fixed-Linux matrix.
  Artifact `9259127166`, digest
  `sha256:eb93d1bb1f036c187d206a801fcf443e79159ecbc066286cb68b1387ece5ebe1`.
- Controlled preflight and cumulative runtime skip as expected because this
  checkpoint activates no route, repository, worker, fixture, business row or
  external transport.

## Review and rollback

The Task Diff Review found no caller-selected tenant, authority, owner,
template, Project type, business-code transform, target identity, success or
secret reference in the signed event. It found no decoded-body signing,
nonconstant signature comparison, production fallback, generic DocType API,
legacy-row promotion, dual field ownership, target write or optimistic Project
success.

Before retained rows exist, rollback may remove the additive P8-02 metadata on
a disposable Site and return to the P8-01 boundary. After retained receipts or
bindings exist, rollback disables only future ingress/enqueue/worker behavior,
retains every raw/canonical hash, receipt, claim, conflict, source binding,
Project draft, Gate shell and audit, and uses a reviewed forward repair. It
never deletes or rebinds history and never contacts production ERPNext/JCE.

This is checkpoint 1 PASS. It is not P8-02 completion or Phase 8 Level 3.
