# P6-01 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-07T10:55:32Z`

Status:
`PASS — LEVEL 1 DOMAIN, CLOSED CONTRACT AND GUARDED METADATA`

Requirements:
`FR-TX-001`, `FR-TX-002`, `UX-004`, `FR-TL-001`, `FR-TL-003`

Exact stable checkpoint:
`62c063e43bb582e270b6e5adf326382c70f2b393`

## Delivered boundary

- Added distinct pure domain values for Engineering Part, immutable exact Part
  Revision, Project-scoped Tooling Requirement, logical Tooling Master and
  immutable versioned/effective Tooling Applicability. None collapses a
  Requirement, Master, Revision, physical Set, Trial or ERPNext object into a
  convenience Tooling row.
- Added exact predecessor/current-revision, canonical snapshot/hash, stable
  relationship identity and half-open effectivity invariants. A shared Master
  is reused through separate Applicability relationships rather than cloned.
- Added six additive guarded DocTypes for Part, Part Revision, Requirement,
  Master, Applicability and actor-bound command idempotency. History is
  append-only/read-only, deletion is denied, and command receipts can only
  seal forward.
- Added exact NPI One/ERPNext ownership rows and closed OpenAPI schemas. The
  schemas reuse the existing typed Project source vocabulary and expose a
  bounded `ToolingProjectCockpit` with plural Masters; no route is active.
- Added literal English source strings and direct `zh`/`zh-TW` coverage. The
  generated React catalog contains `3,985` governed sources at 100% coverage.

## Deliberately unavailable

- No live repository, BFF route, Tooling SPA data source, business fixture,
  policy, default, numbering rule or normal-user generic Desk mutation is
  installed by this checkpoint.
- No production lifecycle state or command is inferred. Exact transitions and
  authorities remain scoped by `DR-REC-010`.
- No physical Set, Tooling Revision, cavity, Trial, supplier/PO/cost,
  acceptance, Asset, capacity, workbook mapping/import, adapter, ERPNext
  endpoint, credential or external mutation was added.
- The checkpoint does not claim P6-01 Level 2 or technical verification of the
  five requirements; repository/BFF, live cockpit and controlled runtime
  checkpoints remain required.

## Local affected and regression evidence

- focused P6-01 domain tests: `9/9` PASS;
- focused P6-01 metadata/controller tests: `7/7` PASS;
- focused P6-01 contract/ownership tests: `5/5` PASS;
- combined affected tests: `21/21` PASS;
- complete tracked Python regression: `1,106/1,106` PASS;
- generated catalog check and i18n audit: PASS, `3,985` literal English
  sources, direct `100%` `zh` and `100%` `zh-TW`;
- OpenAPI, ownership YAML and all six additive DocType JSON files parse;
- compilation, V1.2 reconciliation, prototype approval, P0 visual governance,
  prohibited-pattern and `git diff --check` checks: PASS.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/domain.py` | identity, exact revision, relationship, version/effectivity, canonical-hash and non-collapse cases in `test_phase6_tooling_domain.py` |
| six guarded DocTypes and `frappe_validation.py` | additive JSON, flags, immutability/delete/idempotency/date validation and translation coverage in `test_phase6_tooling_metadata.py` |
| OpenAPI and ownership rows | closed schemas, plural Master projection, exact source vocabulary and NPI/ERP ownership assertions in `test_phase6_tooling_contract.py` |
| translation catalogs/generated catalog | catalog generation, full i18n audit and fixed-Linux visual matrix |
| shared footer fingerprint baselines | exact eighteen governed P0 fixed-Linux screenshots and P0 visual-governance verifier |

## Exact-SHA ordinary CI and bounded visual proof

Product commit `73c8a7a4d3342b663f1650839209a2726d38c443` ran ordinary
CI `31170493815`:

- repository job `92840992551` passed complete repository verification,
  complete non-visual E2E and both current-tree/history Gitleaks lanes;
- controlled runtime job `92840993051` correctly skipped; and
- visual job `92840992439` passed all 50 non-P0 cases and failed only the
  eighteen durable P0 screenshots. Artifact `8990825369`, digest
  `sha256:e9926ae4ab30a6e1b91ef3c1b02f7ecfa945a15decd41fe621a5fee20eca8ae2`,
  proved that every delta was confined to the bottom status-bar catalog
  fingerprint changing from `fd8d72a35779b6ea` to `05fc637e0c1286cb`.

The eighteen exact Linux actuals were synchronized byte-for-byte to only their
matching fixed-Linux baseline targets in isolated repair commit
`62c063e43bb582e270b6e5adf326382c70f2b393`. No product component, layout,
state, assertion, matrix, threshold or PASS rule changed. User-owned Darwin
screenshots were not staged or modified.

Final ordinary CI `31171293330` passed at exact stable checkpoint `62c063e`:

- repository job `92843457513`: PASS, including complete verification, E2E
  and both secret lanes;
- visual job `92843457422`: PASS, `68/68`;
- controlled runtime job `92843458095`: correctly skipped;
- visual artifact `8991126144`, digest
  `sha256:f163ed7b82018fe3ad807f3e90409a89214b5fd83d86f65b56e979cf422e9b81`;
  and
- Gitleaks artifact `8991255329`, digest
  `sha256:a01d17fab0e96a899451c7c9e423229aeba9b63b261374ad80a5f31979fa89fe`.

Local `HEAD`, `origin/codex/npi-v1.2-implementation` and the final run head
were verified at the same exact checkpoint before this evidence update.

## Review, rollback and next checkpoint

This additive foundation creates no business rows and activates no route. If a
later repository/BFF checkpoint is unsafe, its route switch remains closed and
the additive tables stay dormant. Code may be restored before retained data;
once real rows exist, rollback is forward-only through compatibility and no
destructive table removal is permitted.

Checkpoint 1 is PASS. P6-01 remains in progress. Autopilot next implements only
the Project-first authorized repository/BFF checkpoint: bounded queries and
narrow commands, same-tenant/reference/effectivity validation, actor-bound
idempotency, one transaction, append-only audit, independent route switch and
exact API/security tests. The live SPA and controlled-Site boundary remain
inactive until that checkpoint passes affected tests and complete ordinary CI.
