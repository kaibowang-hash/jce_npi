# P6-07 Domain, Inspection and Metadata Checkpoint

Recorded: `2026-08-09T05:07:40Z`

Status:
`PASS — LEVEL 1 PASSIVE INSPECTION, IMMUTABLE DOMAIN, CLOSED CONTRACT AND GUARDED METADATA`

Requirements:
`FR-TX-012`, `FR-TX-013`, `FR-TX-014`, `FR-TX-015`, `FR-TX-016`,
`FR-TX-017`, `FR-TX-018` and `UX-016` technical foundation

Exact stable checkpoint:
`00bead7dcb4013a122acd7f41fc5aa1d42ec8856`

Primary product commit:
`3643b6bf076aa35bd055523d9102e91bd7d3139f`

## Delivered boundary

- Moved the reviewed passive XLSX archive/XML inspection behavior into the
  product Tooling module while retaining the execution-Skill entry point as a
  compatibility wrapper. One bounded immutable byte buffer is hashed and
  parsed, closing source replacement between inspection and reading.
- The inspector rejects traversal and Unicode/case-fold member collisions,
  macros, XLM, ActiveX, embedded binaries, encryption, DTD/entities, external
  relationships and limit violations before exposing bounded values. Its
  report retains input size, filename, SHA-256 and the prevalidated member
  manifest without logging confidential cell values.
- Added pure immutable source, inspection, mapping, preview, job, row/field
  result and rollback types. Every successor binds the exact source hash,
  inspection report, mapping revision/hash and predecessor truth. Mapping
  production authority cannot be constructed through the domain foundation.
- Retained typed raw values and hashes, formula errors, mixed units, legacy
  grades, separate `New Tooling` candidates and ambiguous image/relationship
  confirmation truth. A spreadsheet row never becomes a Tooling aggregate by
  inference.
- Added a standard-library deterministic synthetic 43-column workbook builder
  and fixed manifest hashes. No customer workbook, customer value or opaque
  binary fixture is committed.
- Added five guarded additive DocTypes for batch, inspection revision, mapping
  revision, preview revision and a separate actor-bound idempotency receipt.
  Exact source/inspection/mapping lineage is persisted; generic CRUD, delete,
  export and print mutation paths remain denied.
- Added closed OpenAPI component schemas, exact data-ownership rows, receipt
  values and complete direct English/`zh`/`zh-TW` translations. No P6-07
  route, batch row, mapping activation, worker, live SPA or network path is
  active at this checkpoint.

## Deliberately unavailable

- The reviewed 43-column mapping is still a proposal under `DR-REC-007`.
  Production mapping authority is absent and cannot be supplied by a browser,
  migration default or fixture manifest.
- Passive inspection and immutable preview foundations do not authorize a
  Tooling create/update, lifecycle transition, Trial/quality fact, Gate truth
  or ERPNext-owned Asset, location, stock, purchase, manufacturing or cost
  value.
- `DR-REC-008` remains held for destructive downstream rollback. The domain
  permits only an explicit eligibility result and denies changed, pre-existing
  or downstream-used targets.
- No route, repository command, business row, enqueue, Outbox message,
  production ERPNext endpoint, credential or customer workbook is present.

## Local affected and regression evidence

- focused P6-07 inspector/domain/metadata/contract suite: `27/27` PASS;
- complete local Python discovery: `1,312/1,312` PASS, including six
  pre-existing user-owned untracked local-prerequisite tests; clean exact-SHA
  CI below independently proves `1,306/1,306` tracked tests;
- deterministic fixture hashes, all 43 columns, archive/XML safety,
  position-independent region detection, formula/state/grade/unit/image
  ambiguity and exact lineage tests: PASS;
- OpenAPI/data-ownership YAML, all new DocType JSON, Python compilation,
  metadata guards, receipt values, reconciliation and `git diff --check`:
  PASS;
- frontend catalog generation, typecheck, lint, format, style/boundaries,
  industrial UI, build and `777/777` unit tests: PASS in the isolated clean
  frontend tree; and
- i18n audit: `5,246` literal English sources with 100% direct `zh`/`zh-TW`
  coverage and no mixed-language violation.

The host Node `24.2.0`/npm `11.3.0` cannot satisfy the repository-pinned Node
`24.18.0`/npm `11.16.0` install-script verifier. The clean pinned GitHub
runtime below is the authoritative full gate. The ordinary local frontend
tree also contains the user's pre-existing untracked
`frontend/public/images/npi-one-project-management-sketch.png`; isolated
verification proved it is unrelated. All user-owned files, Darwin snapshots,
local evidence and `implementation/LAST_RUN.md` were preserved and excluded.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/xlsx_inspector.py` and Skill wrapper | bounded immutable source bytes, member collision/traversal, unsafe feature rejection, XML/archive limits and confidential-value boundary in the passive-inspector suites |
| `tooling/xlsx_fixture.py` and manifest | deterministic 43-column inserted/deleted-title fixtures, visibly synthetic provenance and fixed content hashes in `test_phase6_tooling_import_domain.py` |
| `tooling/import_domain.py` | exact source/inspection/mapping binding, raw hashes, formula/state/grade/unit/image findings, immutable preview/job/result truth and strict rollback eligibility in `test_phase6_tooling_import_domain.py` |
| guarded DocTypes/controllers and receipt values | exact fields/options/lineage, append-only and one-way-sealed guards, forbidden defaults and cumulative operation/target whitelists in `test_phase6_tooling_import_metadata.py` |
| OpenAPI and data ownership | closed no-route schemas, NPI/ERP ownership and absent production authority/no-target-mutation assertions in the P6-07 contract tests |
| translation catalogs/generated catalog | generation plus `5,246` literal English sources at complete direct `zh`/`zh-TW` coverage and mixed-language audit |
| governed footer fingerprints | only eighteen reviewed CI actuals copied byte-for-byte to their exact Linux targets; complete `88/88` fixed-Linux CI |

## Exact-SHA CI and bounded visual repair

Primary product commit `3643b6bf076aa35bd055523d9102e91bd7d3139f`
ran ordinary CI `31295089150`. Repository job `93198776956` passed the complete
repository gate. Visual job `93198776937` passed `70/88` and failed exactly
the eighteen durable P0 screenshots after the additional translated sources
changed only the bottom status-bar catalog digest.

Artifact `9032713648`, digest
`sha256:f7ba8e1a6bab641b1dd7eb906365abaf4d8f1ddf1c804f6c3bf52a8ffd39cfd4`,
retains all eighteen actual/diff pairs. Playwright counted `296` differing
pixels for English and `300` for `zh`/`zh-TW`. Full-size inspection found the
visible difference only in the catalog digest: English box
`x=560..677, y=882..892`; Chinese box `x=496..614, y=882..892`. Trial images
also retained threshold-below edge antialiasing at the extreme lower right;
expected, actual and diff inspection found no business-region component,
layout, copy or state regression.

Isolated repair `00bead7dcb4013a122acd7f41fc5aa1d42ec8856` copied only those
eighteen reviewed CI actuals byte-for-byte to their exact tracked Linux
targets. It changed no component, state, assertion, test case, matrix,
threshold, tolerance or PASS rule and staged no user-owned or Darwin file.

Final ordinary CI `31295649693` passed exact stable checkpoint `00bead7`:

- repository job `93200203795`: PASS — `1,306/1,306` tracked Python tests,
  `777/777` frontend unit tests, `337/337` non-visual E2E, `5,246` literal
  English sources with 100% direct `zh`/`zh-TW`, statements `80.20%`, zero
  dependency vulnerabilities and both current/history secret lanes;
- visual job `93200203763`: PASS — `88/88` fixed-Linux cases;
- controlled runtime job `93200204062`: correctly skipped;
- visual artifact `9032884209`, digest
  `sha256:324a332decd3212116a001d3d1de771830eea44fbef679d5d595664bb0fe968e`;
  and
- Gitleaks artifact `9032933838`, digest
  `sha256:6ae8a79f23c05078d1ea173b87d68361b462317dcc1bb8c5d12e5a9fd0196564`.

## Review, rollback and next checkpoint

Task Diff Review confirms the checkpoint is additive, creates no business row
and activates no route. Rollback is a reviewed forward repair: keep immutable
inspection/mapping/preview history and disable only later P6-07 routes or
workers. Never delete retained truth, contact ERPNext, activate a production
mapping or alter P6-01 through P6-06 aggregates.

Checkpoint 1 is PASS. P6-07 remains in progress. Autopilot next implements
only checkpoint 2: independently default-closed Project-first batch/detail,
inspect, mapping-proposal and immutable preview/confirmation routes; exact
File/customer/Project authorization; production mapping unavailable by
default; one-transaction append, audit and actor-bound idempotency; and exact
permission, IDOR, replay, conflict, rollback, raw-log-redaction and no-target-
mutation tests. Worker execution, live SPA, controlled Site, customer workbook,
production mapping, ERPNext contact and destructive rollback remain inactive.
