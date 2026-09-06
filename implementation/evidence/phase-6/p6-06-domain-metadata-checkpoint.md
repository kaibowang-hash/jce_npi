# P6-06 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-08T23:33:09Z`

Status:
`PASS — LEVEL 1 DOMAIN, CLOSED CONTRACT AND GUARDED METADATA`

Requirements:
`FR-TL-011`, `FR-TL-012`, `FR-TL-013`, `FR-TL-014`, `FR-TL-015`,
`FR-TL-016` technical foundation

Exact stable checkpoint:
`7ab28bf27ec223d3a0e024e77bd628fed2c0fa9e`

## Delivered boundary

- Added immutable, versioned Tooling acceptance-evidence revisions bound to
  one exact Project, Master, physical Set, Set-to-Revision binding and Tooling
  Revision. Predecessor and snapshot hashes make successor history explicit.
- Added all nine frozen evidence categories with evidence-only dispositions,
  exact clean private File Revision snapshots, optional current Project-member
  responsibility and server-derived coverage. Coverage never becomes business
  approval; the Phase 6 approval projection is always `unavailable`.
- Added immutable NPI-owned move/loan/return/archive/scrap evidence, critical-
  spare/wear recommendations and repair authorization/quote/responsibility/
  downtime/verification evidence. Customer-owned repair evidence requires an
  exact customer-authorization evidence role.
- Added the operation-specific Tool Asset request domain. The only operation is
  `create_or_update_tool_asset`; the only active target mode is `mock`, and
  every request is fixed to `draft`, `validated_mock`, approval `unavailable`,
  dispatch `prohibited` and target result `not_requested`.
- Added a strict unavailable ERP Asset projection and a closed future available
  projection shape. One physical Set is the mapping subject with zero-or-one
  formal Asset mapping; no browser or NPI-owned field can choose an Asset ID.
- Added one guarded append-only acceptance DocType, one guarded append-only
  Tool Asset request DocType, one actor-bound one-way-sealed request receipt,
  the exact acceptance command-receipt pair, closed OpenAPI/ownership/future-
  event schemas and complete direct `zh`/`zh-TW` translations.
- No P6-06 route, repository command, business row, Outbox message, adapter,
  worker, endpoint, credential or live UI is active at this checkpoint.

## Deliberately unavailable

- Checklist coverage is not Tooling acceptance, approval, waiver, Gate truth or
  a Requirement/Revision/Set lifecycle transition. `DR-REC-010` remains held.
- Trial Round, official quality and Approved Process Baseline truth remain
  unavailable until Phase 7; no Customer Standard, defect or capacity record
  substitutes for them.
- A retained local request is not queued, sent or executed. It cannot contain a
  target ID, target success, Outbox identity or formal mapping observation.
- Formal Asset mapping, state, location, movement, shot/life, maintenance,
  repair, supplier, spare Item/inventory and cost truth remain ERPNext-owned
  and unavailable until an authenticated Phase 8 result or reader supplies
  them.
- `sandbox` and `production` target modes, all production/sandbox network
  access and every target-side mutation remain inactive and rejected.

## Local affected evidence

- focused P6-06 domain/metadata/contract and cumulative Tooling metadata
  checks: `42/42` PASS;
- OpenAPI/data-ownership YAML, event JSON Schema, all new DocType JSON and
  Python compilation: PASS;
- catalog generation/check and i18n audit: PASS — `5,012` literal English
  sources with complete direct `zh` and `zh-TW` coverage and no mixed-language
  violation;
- exact acceptance/request hash hydration, successor, category, evidence-role,
  customer-authorization, unavailable-projection and no-fake-success cases:
  PASS; and
- `git diff --check`: PASS.

All pre-existing user-owned development files, Darwin screenshots, local
evidence and `implementation/LAST_RUN.md` were preserved and excluded from the
checkpoint commits.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/acceptance_domain.py` | complete-category evidence, disposition/evidence-role rules, immutable successor hashes, customer-owned repair authorization, NPI-only Asset-adjacent evidence and strict unavailable/future ERP projections in `test_phase6_tooling_acceptance_domain.py` |
| `tool_asset_request/domain.py` | closed resolved input, physical-Set mapping subject, fixed request truth axes, hash hydration, no target ID/Outbox/success and distinct Set inputs in `test_phase6_tool_asset_request_domain.py` |
| three guarded DocTypes/controllers and receipt values | exact fields/options, append-only and one-way-sealed guards, generic CRUD/delete/export/print denial, and cumulative operation/target whitelists in `test_phase6_tooling_acceptance_metadata.py` plus existing Tooling metadata suites |
| OpenAPI, ownership and future event schema | closed operation-specific request/projection shapes, ERP ownership, no generic execution route, no active P6-06 path and no emitted Asset event in `test_phase6_tooling_acceptance_contract.py` |
| translation catalogs/generated catalog | generation plus `5,012` literal English sources at complete direct `zh`/`zh-TW` coverage and mixed-language audit |
| governed footer fingerprints | exact eighteen reviewed CI actuals copied byte-for-byte to only their Linux baseline targets and complete `85/85` fixed-Linux CI |

## Exact-SHA CI and bounded repair history

Product commit `43e187f38662baae23d606246fbacbef273c6bd4` first ran ordinary
CI `31282919775`. Its failures were cumulative-gate integration defects rather
than domain failures: two older exact receipt assertions needed the new closed
operation/target pair, and the new Select values needed direct translations.
Repair `a3cd86401f2441a8a446612601bff17a668f89f5` corrected only those
expectations/catalog rows.

CI `31283028492` then passed all `1,271` Python tests and isolated one unused
translation left by removal of a nonexistent Set-binding version field. Repair
`a491b8311e84b3ce0c7a4937f0207b2b3f9e13a5` removed that obsolete source and
regenerated the governed frontend catalog. CI `31283136214` next isolated only
Latin `ID`/`ERP` tokens in the new Chinese translations plus the expected
eighteen shared footer fingerprints. Repair
`34bfb17a4e737c0e12ef14a57c22c9fe96fe1910` closed the mixed-language audit
without changing a domain or contract.

At exact SHA `34bfb17`, ordinary CI `31283358898` passed repository job
`93168103152` completely and visual job `93168103126` passed `67/85`, failing
only the eighteen durable P0 screenshots. Artifact `9029108774`, digest
`sha256:1ef926b2b3147ee692adda7b99a67abe5fc878756d1ffa3f3d74e1973a6d8c2f`,
retains every actual/diff pair. Exact RGB comparison against the tracked
baselines proved all deltas confined to the bottom catalog fingerprint:
English half-open box `x=559..676, y=882..892`; Simplified and Traditional
Chinese `x=496..613, y=882..892`. Each image changed only `799` or `800` RGB
pixels; full diff inspection found no business-region component, layout, copy
or state change.

Isolated repair `7ab28bf27ec223d3a0e024e77bd628fed2c0fa9e` copied only those
eighteen reviewed CI actuals byte-for-byte to their exact Linux targets. It
changed no component, state, assertion, matrix, threshold or PASS rule and
staged no user-owned or Darwin file.

Final ordinary CI `31283811647` passed exact stable checkpoint `7ab28bf`:

- repository job `93169231333`: PASS — `1,271/1,271` tracked Python tests,
  `768/768` frontend unit tests, `332/332` non-visual E2E, `5,012` literal
  English sources with 100% direct `zh`/`zh-TW`, statements `80.35%`, zero
  dependency vulnerabilities and both current/history secret lanes;
- visual job `93169231300`: PASS — `85/85` fixed-Linux cases;
- controlled runtime job `93169231539`: correctly skipped;
- visual artifact `9029232932`, digest
  `sha256:4755a3e8be2a8517a80a2fb3d49f78c7a02ce780784a3f9e32c9ae6eab206d60`;
  and
- Gitleaks artifact `9029295848`, digest
  `sha256:12d9a502d37fa9a8cfb81f7ae163355d07be70aaf1e6a01c68d99586665fcada`.

## Review, rollback and next checkpoint

The checkpoint is additive, creates no business rows and activates no route.
Before retained rows exist, a disposable environment may restore the starting
checkpoint and migrate fresh. After retained history exists, rollback disables
only later P6-06 routes/request preparation and uses a reviewed forward repair
while preserving every immutable evidence revision, request, audit and receipt.
It never deletes history, contacts ERPNext or alters Tooling/Trial/Gate truth.

Checkpoint 1 is PASS. P6-06 remains in progress. Autopilot next implements only
checkpoint 2: Project-first bounded acceptance/request reads; immutable
acceptance append and Mock request preparation; exact Project/Master/Set/
binding/Revision/member/File/evidence containment; System Manager management
transport; actor-bound idempotency; one transaction; append-only audit; strict
unavailable ERP projections; independent fail-closed routes; and API,
permission, IDOR, replay, conflict, rollback, no-Outbox, no-network and no-
target-ID tests. The live SPA and controlled Site remain inactive until that
checkpoint passes affected checks and complete ordinary CI.
