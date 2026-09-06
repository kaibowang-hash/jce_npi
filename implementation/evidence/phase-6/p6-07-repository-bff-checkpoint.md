# P6-07 Repository, Inspect/Map/Preview BFF Checkpoint

Recorded: `2026-08-09T09:38:02Z`

Status:
`PASS — PROJECT-FIRST SOURCE, INSPECTION, MAPPING PROPOSAL AND IMMUTABLE PREVIEW/CONFIRMATION BFF`

Requirements:
`FR-TX-012`, `FR-TX-013`, `FR-TX-014`, `FR-TX-015`, `FR-TX-016`,
`FR-TX-017`, `FR-TX-018` and `UX-016` technical foundation

Exact stable checkpoint:
`40e142d5f8a38c3ecd2c5da9f5a3326030d37c20`

Primary product commit:
`0cad7ebdadaae06fb270f79747b3fc946350fff4`

## Delivered boundary

- Activated exactly seven Project-first routes behind the independent,
  default-closed `npi_p6_07_routes_disabled` switch: bounded batch collection
  and source registration; exact batch detail; passive inspection; mapping
  proposal; immutable preview; and immutable preview confirmation.
- Source registration accepts only an exact clean private File Revision. The
  repository re-resolves File confidentiality, scan truth, customer and
  Project containment, reads server-owned File bytes and verifies both length
  and SHA-256 before binding the immutable import source.
- Commands require authenticated internal `System Manager` transport, CSRF and
  Project administer scope. All reads and writes begin with the Project and
  reject cross-Project, cross-customer and cross-File identifiers before
  returning child truth.
- Added a versioned mapping catalog and provider boundary. The live provider
  returns production mapping unavailable by default; a browser cannot approve
  or activate a mapping, choose an arbitrary transformation or supply a target
  aggregate payload.
- Persisted immutable source, inspection, mapping proposal, preview and
  confirmation history. Preview confirmation creates an exact successor and
  cannot overwrite or erase earlier evidence.
- Actor-bound idempotency seals the exact operation, Project, batch, expected
  version and payload. Replay returns the sealed receipt; actor, operation or
  payload reuse conflicts.
- Every command executes receipt creation, immutable history append, audit and
  receipt seal in one transaction. Rollback leaves no partial history, audit
  or success receipt.
- OpenAPI commands declare exact roles, transaction boundaries and audit
  operations. Standard logs and audit summaries retain hashes and controlled
  codes only; raw workbook cell values remain confined to authorized detail
  surfaces.

## Deliberately unavailable

- `DR-REC-007` remains open. No production mapping is installed or activatable
  through a route, migration default, workbook, fixture manifest or browser
  decision.
- No worker, queue enqueue, execution job, row mutation, correction artifact,
  retry, reconciliation or rollback command is active at this checkpoint.
- No Tooling Master, Revision, Set, Cavity, Insert, Trial, Gate, quality or
  other target aggregate is created, updated, submitted, cancelled or deleted.
- No customer workbook is committed or read. The deterministic synthetic
  fixture remains the only executable workbook evidence.
- No ERPNext endpoint, credential, network call, Outbox row, Asset mapping or
  ERP-owned location, inventory, maintenance, procurement, manufacturing,
  quality, cost or finance truth is reachable.
- `DR-REC-008` continues to deny destructive downstream rollback. Preview
  confirmation is evidence only and never constitutes execution authority.

## Local affected and regression evidence

- focused P6-07 repository/API/authorization/metadata suite: `31/31` PASS;
- clean exact-product Python discovery: `1,324/1,324` tracked tests PASS;
- strict route-disable, permission, CSRF, Project/customer/File IDOR, clean
  private File rehash/length, replay/conflict/rollback and transaction-order
  tests: PASS;
- production-mapping-unavailable, raw-log-redaction, immutable-successor and
  no-target-mutation/no-network assertions: PASS;
- frontend catalog generation, typecheck, lint, format, style/boundary,
  industrial UI, production build and `777/777` unit tests: PASS;
- i18n audit: `5,274` literal English sources with 100% direct `zh`/`zh-TW`
  coverage and no mixed-language violation;
- frontend coverage: statements `80.20%`, branches `79.08%`, functions
  `82.10%`, lines `82.35%`; and
- non-visual Playwright: `337/337` PASS.

The host Node `24.2.0`/npm `11.3.0` does not match the repository-pinned Node
`24.18.0`/npm `11.16.0`; the pinned GitHub runtime below is the authoritative
full Gate. Isolated clean-tree verification also excluded the user's existing
untracked brand asset. All user-owned files, Darwin snapshots, local evidence
and `implementation/LAST_RUN.md` were preserved and excluded.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| BFF routing and request security | exact seven-route registration, default-closed switch, authentication, CSRF, role and Project-first authorization tests |
| `tooling_import_api.py` and repository | exact File-byte integrity, customer/Project containment, immutable history, one-transaction audit/receipt order, replay/conflict/rollback and no-target-mutation tests |
| mapping catalog and Frappe validation | closed transformations, complete detected-column proposals, production-unavailable provider and exact inspection/mapping/preview lineage tests |
| preview metadata/domain | immutable successor confirmation, predecessor/hash integrity, uniqueness and guarded generic-CRUD tests |
| OpenAPI and translations | route/role/transaction/audit contract assertions plus generated catalog and complete direct trilingual audit |
| governed footer fingerprints | eighteen artifact-reviewed Linux actuals promoted byte-for-byte; complete `88/88` fixed-Linux CI |

## Exact-SHA CI and bounded visual repair

Primary product commit `0cad7ebdadaae06fb270f79747b3fc946350fff4`
ran ordinary CI
[`31305468446`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31305468446).
Repository job `93225017234` passed the complete repository Gate. Visual job
`93225017259` passed `70/88` and failed exactly the eighteen durable P0
screenshots after the additional translated sources changed the status-bar
catalog version from `148ca101b7caed84` to `1790161efddfeb75`.

Artifact `9035832831`, digest
`sha256:ad8a0d66c9a37d7209ccc2a2d69d54c26c0459ee0ae9141e9bd0d2de5223ac6c`,
retains all eighteen actual/diff pairs. Playwright counted `279` differing
pixels for English and `268` for `zh`/`zh-TW`. Exact RGB comparison found zero
changed pixels above `y=860`; visible boxes were confined to the bottom
catalog version at English `x=567..677, y=882..892` and Chinese
`x=504..614, y=882..892`. Threshold-below lower-right antialiasing remained
non-material. No business region, layout, user copy, state, assertion, matrix,
threshold or PASS criterion changed.

Isolated repair `40e142d5f8a38c3ecd2c5da9f5a3326030d37c20`
copied only the eighteen reviewed CI actuals byte-for-byte to their exact
tracked Linux targets. It staged no user-owned or Darwin file.

Final ordinary CI
[`31305920914`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31305920914)
passed exact stable checkpoint `40e142d`:

- repository job `93226181482`: PASS — `1,324/1,324` tracked Python tests,
  `777/777` frontend unit tests, `337/337` non-visual E2E, `5,274` literal
  English sources with 100% direct `zh`/`zh-TW`, statements `80.20%`, zero
  dependency vulnerabilities and both current/history secret lanes;
- visual job `93226181475`: PASS — `88/88` fixed-Linux cases;
- controlled runtime job `93226181903`: correctly skipped;
- visual artifact `9035963363`, digest
  `sha256:d13497b5645fa4a52c90177738d9b9d30191f285f03db17d7be11872db15158f`;
  and
- Gitleaks artifact `9036043177`, digest
  `sha256:6280b3293e2dca80478b90b5acb06ac603829e713de6623d579e687b83354f95`.

## Review, rollback and next checkpoint

Task Diff Review confirms the checkpoint is additive and Project-first. Its
routes fail closed independently, its commands append immutable evidence in
one transaction, and no execution target or external system is mutated.
Rollback is a forward repair: disable the P6-07 route switch while retaining
source, inspection, mapping, preview, confirmation, audit and receipt history.

Checkpoint 2 is PASS. P6-07 remains in progress. Autopilot next implements
only checkpoint 3: after-commit enqueue; resumable bounded worker; immutable
row/field results; exact active synthetic mapping authority outside migrations;
durable status/detail; allowlisted correction artifact; failed-row-only retry;
reconciliation; and strict eligibility/rollback commands. It must prove
partial truth, no duplicate successful mutation, retryable/final failures,
worker reauthorization, rollback only for unchanged batch-created unused
objects, durable denial for changed/downstream-used objects and no ERP contact.
The live SPA, controlled Site, production mapping, customer workbook, ERPNext
contact and destructive downstream rollback remain inactive.
