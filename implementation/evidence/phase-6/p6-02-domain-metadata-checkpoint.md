# P6-02 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-07T18:07:22Z`

Status:
`PASS — LEVEL 1 DOMAIN, CLOSED CONTRACT AND GUARDED METADATA`

Requirements:
`FR-TX-003`, `FR-TL-004`

Exact stable checkpoint:
`7b5dda19b2fc080a7dc562abf3f68a0d7a7bddff`

## Delivered boundary

- Added one immutable `ToolingSet` identity per physical Set. No quantity or
  serial-number deduplication collapses two physical copies. Customer-owned
  Sets retain the exact customer reference plus custody responsibility,
  repair-authorization reference and return conditions.
- Added immutable versioned Tooling Intake snapshots with transport/arrival
  provenance, bounded accessories, exactly one observation for each of the
  five required inspection categories and independently identified
  differences tied to their exact accessory or inspection source.
- Added append-only, URL-free Tooling Intake evidence references. Each binds
  one exact intake snapshot to one exact live clean private File Revision and
  snapshots its version, content hashes, name, MIME type and size. Customer-
  confirmation evidence must name the exact retained difference identities.
- Added three guarded additive DocTypes, exact NPI One/ERPNext ownership rows
  and closed OpenAPI schemas. History is immutable and deletion is denied;
  no P6-02 route is active.
- Added literal English source strings and direct `zh`/`zh-TW` coverage. The
  generated catalog contains `4,127` governed sources at 100% direct coverage.

## Deliberately unavailable

- No repository route, BFF command, live Set/intake SPA behavior, controlled-
  Site verifier, business row, policy, fixture/default or external mutation is
  installed by this checkpoint.
- Exact lifecycle states/transitions/authorities remain held by `DR-REC-010`.
  Source Tooling Revision remains P6-03, formal Supplier remains P6-04, and
  ERP location/Asset/state remains P6-06/Phase 8 truth.
- No customer login or signature claim, file upload/release/overwrite/delete,
  raw private URL, adapter, ERPNext endpoint or credential was added.
- This is checkpoint 1, not P6-02 Level 2. `FR-TL-004` and the independent-
  Set foundation of `FR-TX-003` still require repository/BFF, live workspace
  and controlled runtime proof.

## Local affected and regression evidence

- focused P6-02 domain/metadata/contract tests: `30/30` PASS;
- complete tracked Python regression: `1,138/1,138` PASS;
- frontend generation, typecheck, lint, formatting, coverage tests and
  production bundle: PASS;
- i18n audit: PASS, `4,127` literal English sources with direct `100%` `zh`
  and `100%` `zh-TW` coverage;
- OpenAPI, ownership YAML and all three additive DocType JSON files parse;
- compilation, V1.2 reconciliation, prototype approval, P0 visual governance
  and `git diff --check`: PASS.

The workspace-wide local brand command remains intentionally blocked by the
pre-existing untracked user asset
`frontend/public/images/npi-one-project-management-sketch.png`. It was
preserved and excluded from every commit. The clean exact-SHA repository job
passed the same brand guard and every complete verification lane.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/domain.py` | physical identity/non-collapse, customer provenance, five inspections, exact differences, successor intake and URL-free evidence cases in `test_phase6_tooling_domain.py` |
| three guarded DocTypes/controllers | exact fields/options, append-only permissions, denied delete/update, no fake lifecycle/ERP/file URL and additive metadata assertions in `test_phase6_tooling_metadata.py` |
| OpenAPI and ownership rows | closed schemas, inactive-route boundary, browser-owned-field denial and exact NPI/ERP ownership assertions in `test_phase6_tooling_contract.py` |
| translation catalogs/generated catalog | generation, complete i18n audit and fixed-Linux governed visual matrix |
| shared footer fingerprint baselines | exact eighteen P0 fixed-Linux screenshots and P0 visual-governance verifier |

## Exact-SHA ordinary CI and bounded visual proof

Product commit `e659d46361d32650863bedac3567008580ce4289` ran ordinary
CI `31203653903`:

- repository job `92949376253` passed complete repository verification,
  complete non-visual E2E and both current-tree/history Gitleaks lanes;
- controlled runtime job `92949377433` correctly skipped; and
- visual job `92949376152` passed all 55 non-P0 cases and failed only the
  eighteen durable P0 screenshots. Artifact `9003910006`, digest
  `sha256:4c31b017275e9a2ad24285671a39b05ba5961a7ae8de8c8b28c6649e26da3ea5`,
  proved that every delta was confined to the bottom status-bar catalog
  fingerprint changing from `8d880a485a7ba1af` to `220fdc2cf42779bb`.
  Each screenshot differed by only `293` or `297` pixels.

The eighteen exact Linux actuals were synchronized byte-for-byte to only their
matching fixed-Linux baseline targets in isolated repair commit
`7b5dda19b2fc080a7dc562abf3f68a0d7a7bddff`. No product component, layout,
state, assertion, matrix, threshold or PASS rule changed. User-owned Darwin
screenshots and every unrelated dirty/untracked file were not staged.

Final ordinary CI `31204720858` passed at exact stable checkpoint `7b5dda1`:

- repository job `92952842864`: PASS, including complete verification, E2E
  and both secret lanes;
- visual job `92952842802`: PASS, `73/73`;
- controlled runtime job `92952843426`: correctly skipped;
- visual artifact `9004313318`, digest
  `sha256:1cd53e5d0733ac13058d381c7afdaf0fe50d18133100cfd16ab8ae910d1dba6e`;
  and
- Gitleaks artifact `9004474210`, digest
  `sha256:e5266c4199df7bd7afaf6bc694400fca26c457e0d0ce3e19ed2da9b6f6d28f16`.

Local `HEAD`, `origin/codex/npi-v1.2-implementation` and the final run head
were verified at the same exact checkpoint before this evidence update.

## Review, rollback and next checkpoint

This additive foundation creates no business rows and activates no route. If a
later repository/BFF checkpoint is unsafe, its independent switch remains
closed and the additive tables stay dormant. Once real history exists,
rollback is forward-only: preserve every Set UUID, intake version, difference,
File Revision reference, audit and idempotency receipt; never merge Sets,
rewrite intake history or alter referenced files.

Checkpoint 1 is PASS. P6-02 remains in progress. Autopilot next implements
only the Project-first repository/BFF checkpoint: bounded Set queries, three
narrow commands, exact Requirement/customer/File Revision containment,
System Manager-only mutation, actor-bound idempotency, one transaction,
append-only audit, independent fail-closed route switch and exact API/IDOR
tests. The live SPA and controlled-Site boundary remain inactive until that
checkpoint passes affected checks and complete ordinary CI.
