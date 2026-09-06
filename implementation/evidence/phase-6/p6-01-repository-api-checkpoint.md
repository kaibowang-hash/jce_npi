# P6-01 Repository and BFF Checkpoint

Recorded: `2026-08-07T11:55:19Z`

Status:
`PASS — LEVEL 1 AUTHORIZED REPOSITORY AND CLOSED BFF`

Requirements:
`FR-TX-001`, `FR-TX-002`, `UX-004`, `FR-TL-001`, `FR-TL-003`

Exact stable checkpoint:
`4215bbe392c72010ffd036348647c745d37cbc84`

## Delivered boundary

- Added Project-first authorized, bounded Project cockpit and exact Master
  projections. A protected Master, Part Revision, Requirement or
  Applicability identity is never resolved before Project authorization.
- Added the seven frozen closed paths: two private/no-store GET projections
  and five narrow POST commands for Part plus initial Revision, successor Part
  Revision, Requirement, logical Master and immutable Applicability.
- Mutation remains same-tenant internal `System Manager` only until an
  approved Tooling authority policy exists. The repository reauthorizes and
  locks the exact Project before resolving command targets.
- Commands bind idempotency to tenant, Project, actor, operation, key and
  canonical payload; safe replay verifies a sealed target and response hash.
  Receipt, object/projection, append-only audit, response and seal stay in one
  Frappe request transaction, with every non-2xx path rolled back.
- Applicability creation requires one same-tenant Master, the exact current
  Part Revision, exact unique Project references, a direct predecessor for
  successors, stable normalized relationship identity and non-overlapping
  half-open effectivity.
- Added an independent fail-closed `npi_p6_01_routes_disabled` switch. Missing
  configuration is disabled; no Site or production default was enabled.

## Deliberately unavailable

- No live SPA data source or Tooling workspace activation is delivered by
  this checkpoint. The existing prototype remains isolated until checkpoint
  3 passes its state, accessibility, trilingual and visual evidence.
- No production lifecycle, numbering, ownership/custody, Tooling Revision,
  physical Set, cavity, Trial, copy policy, workbook mapping, adapter, signer,
  external QR/render service, ERPNext endpoint, credential or external
  mutation was installed.
- Downstream lifecycle, revision, physical Set, Trial and ERP truth remains
  explicitly `unavailable`; the API does not return invented lifecycle,
  set-count, Asset, shot-count or ERP authority.
- This is not P6-01 Level 2. Disposable-Site runtime and the final Task Gate
  remain checkpoint 4 after the live cockpit passes ordinary CI.

## Local affected and regression evidence

- focused domain/metadata/contract/repository/API suite: `35/35` PASS;
- complete local Python regression: `1,120/1,120` PASS;
- generated catalog and i18n audit: PASS, `3,987` literal English sources,
  direct `100%` `zh` and `100%` `zh-TW` coverage;
- OpenAPI YAML, additive DocType JSON, compilation, V1.2 reconciliation,
  prototype approval, Dev Container registry configuration, P0 visual
  governance, prohibited-pattern and `git diff --check`: PASS;
- the local host lacks installed frontend `tsc`; the fixed-toolchain ordinary
  CI below passed the complete frontend type/lint/unit/build/audit path.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/frappe_repository.py` | Project-first scope, bounded queries, atomic order, exact predecessor/reference/effectivity, replay integrity and unavailable projection assertions in `test_phase6_tooling_repository.py` |
| `tooling_api.py`, `bff.py`, request security and errors | handler/method/CSRF/admin/IDOR/unavailable/closed-field/replay/rollback/route-switch cases in `test_phase6_tooling_api.py` |
| Part projection controller and Tooling domain errors | exact initial-pointer versioning, title-through-revision and successor conflict regressions in Tooling metadata/domain suites |
| OpenAPI and generated translations | seven-path/closed-schema/forbidden-server-truth contract assertions plus complete catalog/i18n audit |
| shared footer catalog fingerprint | exact eighteen fixed-Linux P0 baselines from the failed exact-SHA artifact, followed by `68/68` final visual PASS |

## Exact-SHA ordinary CI and bounded visual proof

Product commit `96fdd844b88e603857540361e18aec64e358f127` ran ordinary
CI `31174458472`:

- repository job `92853267311` passed complete repository verification,
  complete non-visual E2E and both current-tree/history Gitleaks lanes;
- controlled runtime job `92853267998` correctly skipped; and
- visual job `92853267409` passed all 50 non-P0 cases and failed only the
  eighteen durable P0 screenshots. Artifact `8992324656`, digest
  `sha256:e697467a89b314a6ed31ba2dc5275628c15de4d62a8362b7b17e4142cfa66691`,
  proved the changes were confined to the bottom status-bar catalog
  fingerprint changing from `05fc637e0c1286cb` to `088d4637dea1703c`.

The eighteen exact Linux actuals were synchronized byte-for-byte to only their
matching tracked fixed-Linux targets in isolated repair commit
`4215bbe392c72010ffd036348647c745d37cbc84`. No product component, layout,
state, assertion, matrix, threshold or PASS rule changed. User-owned Darwin
screenshots were not staged or modified.

Final ordinary CI `31175388717` passed at exact stable checkpoint `4215bbe`:

- repository job `92856145644`: PASS, including complete verification, E2E
  and both secret lanes;
- visual job `92856145467`: PASS, `68/68`;
- controlled runtime job `92856146245`: correctly skipped;
- visual artifact `8992669663`, digest
  `sha256:6e0a0c711e8dd19f2962581f529faf2fcf1faa9c66bf06db01a6b4b54ade1831`;
  and
- Gitleaks artifact `8992813445`, digest
  `sha256:c50fd6f6a0fc1279b8abb5c8842b82a0f3522342362742c9b7b440a173c6709e`.

## Review, rollback and next checkpoint

Checkpoint 2 is PASS. The independent route switch remains closed by default,
so rollback disables Tooling routes and preserves every additive Part,
Revision, Requirement, Master, Applicability, audit and receipt row. Once rows
exist, repair is forward-only; no table removal, history rewrite or Master
merge is permitted.

Autopilot next implements only P6-01 checkpoint 3: the server-backed dense
Tooling cockpit, honest downstream unavailable states, capability-driven
actions, complete English/`zh`/`zh-TW`, accessibility and affected visual
matrix. A controlled Site still must not be dispatched until that live
checkpoint passes affected checks and complete ordinary CI.
