# P6-08 Repository, BFF and Private Artifact Checkpoint

Recorded: `2026-08-09T21:35:59Z`

Status:
`PASS — PROJECT-FIRST LIST/PREFERENCE, IMMUTABLE PRIVATE PACKAGE AND CREATOR-BOUND DOWNLOAD`

Requirement: `UX-007`, supported by `FR-UX-007`, `FR-UX-025`,
`FR-UX-030`, `NFR-SEC-003` and `NFR-LOC-001`

Exact stable checkpoint:
`ac0a29cc6cd38e87a0e1922abac1e73ea1d969ff`

Product and bounded repair commits:

- `759b4487a45dfa526d0b4577391d9aa37cfd7bc3` — independently
  default-closed Project-first list/preference/export/download BFF, immutable
  private package persistence and direct tests; and
- `ac0a29cc6cd38e87a0e1922abac1e73ea1d969ff` — promote only the eighteen
  reviewed fixed-Linux catalog-footer actuals produced by the added direct
  translations.

## Delivered boundary

- Activated exactly four P6-08 route shapes behind the independent
  `npi_p6_08_routes_disabled` switch: one stable Tooling-list page, one exact
  per-view preference `GET/PUT`, one package-create command and one
  creator-bound package-content `POST`.
- All reads authorize the Project before resolving a Tooling Master, package
  or other secondary identifier. Shared Masters are aggregated only from
  Project-relative Applicability, physical Set, Revision and import-binding
  truth; unrelated Project/customer facts are never returned or packaged.
- Stable server paging retains the complete closed filter, deterministic
  ordering, current row snapshot hashes and complete-result query snapshot.
  Page cursor/page size are not accepted as filtered-export membership.
- Preference persistence is actor/tenant/Project/view/grid-schema bound,
  validates the exact nine-column order and required columns, and applies
  optimistic version plus snapshot preconditions. Duplicate persistence and
  stale writes return explicit conflict truth.
- Export requires current Project `VIEW` plus the separate authenticated
  internal `System Manager` transport authority. Selection revalidates every
  exact Master snapshot; filtered mode recomputes the complete result and
  exact query snapshot; both remain bounded to `1..100` Masters.
- Package creation renders the fixed three-member localized archive and
  persists one immutable private File, package row, audit and actor-bound
  sealed receipt in one transaction. Public responses contain no File ID or
  raw private URL.
- Download is a CSRF-protected POST that reauthorizes the current Project and
  export capability, exact creator, immutable package snapshot, one-hour
  validity and retained File byte count/SHA-256 before returning ZIP bytes
  with attachment-only security headers. Receipt replay reloads the exact
  creator-bound Project package rather than trusting retained response text.
- Frappe Datetime values are normalized to canonical UTC projections before
  immutable comparison, preventing equivalent database text and runtime
  Datetime representations from producing false conflicts.

## Deliberately unavailable

- No P6-08 live SPA action, review dialog, browser download or controlled Site
  runtime is active at checkpoint 2.
- There is no caller-selected DocType, field list, arbitrary expression,
  package member, page-only filtered export or raw File redirect.
- Project visibility alone cannot export. The transport role is not business
  approval, publication, lifecycle or ERP authority.
- No production ERPNext endpoint, credential, Outbox, network call, Tooling
  lifecycle mutation or customer workbook is reachable.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| BFF/request security/errors | exact route registration, independent default-closed switch, authentication, CSRF, strict fields and normalized Problem Details in `test_phase6_tooling_export_api.py` |
| `tooling_export_api.py` | Project-first identity parsing, conservative role/scope authorization, idempotency, JSON/binary response and attachment header tests |
| `export_repository.py` | stable paging/query snapshots, ten live views, shared-Master containment, preference conflicts, selection/filtered stale denial, immutable File/package/audit/receipt transaction, replay, expiry, creator and exact-hash tests |
| OpenAPI | exact four path shapes, closed schemas, role/transaction/audit metadata and URL-free package response in `test_phase6_tooling_export_contract.py` |
| renderer/domain/metadata | full persisted snapshot projection, package creator/expiry manifest truth, exact preference widths, generic CRUD denial and cumulative receipt values |
| translations/generated catalog | `5,647` literal English sources at complete direct `zh`/`zh-TW` coverage |
| fixed-Linux visual baselines | eighteen reviewed catalog-footer actuals promoted byte-for-byte; final complete `91/91` matrix |

## Local and exact-SHA CI evidence

Local affected and regression evidence passed before push:

- direct P6-08 API/contract/domain/metadata/rendering/repository suites:
  `41/41`;
- complete local Python discovery: `1,411/1,411`, including six preserved
  user-owned local-prerequisite tests not tracked by the product commit;
- frontend typecheck and `796/796` unit tests in `50` files;
- OpenAPI YAML parse, generated-catalog check, prohibited-pattern scan and
  `git diff --check`: PASS; and
- i18n audit: `5,647` literal English sources with 100% direct `zh`/`zh-TW`
  coverage.

Primary product commit `759b448` ran ordinary CI `31336374959`:

- repository job `93302794940` passed the complete repository Lane, including
  all `1,405` tracked Python, `796` frontend unit and `343` non-visual E2E
  tests plus both secret lanes;
- visual job `93302794949` passed `73/91` and failed exactly the eighteen
  durable P0 screenshots because the new direct translations changed only the
  status-bar catalog fingerprint from `d37c905dd74e93e4` to
  `1ca4fcaf8b98e6ca`;
- visual artifact `9044488283`, digest
  `sha256:39a4689960087899ff40262a12add50cd1e7895530679c40d2a26d48259d1e16`,
  retained all actual/diff pairs; and
- exact pixel audit found ordinary visible changes confined to English
  `x=559..676, y=882..891` and Chinese `x=496..613, y=882..891`.
  Twenty one-value lower-right antialiasing pixels in one Chinese Trial image
  were below threshold and outside business UI. No source component, layout,
  assertion, matrix, tolerance or PASS rule changed.

Baseline-only commit `ac0a29c` copied exactly those eighteen reviewed CI
actuals to their tracked Linux targets. Final ordinary CI `31336841275`
passes that exact stable checkpoint:

- repository job `93303992048`: PASS in `8m07s` — `1,405/1,405` tracked
  Python tests, `796/796` frontend unit tests in `50` files, `343/343`
  non-visual E2E, statements `80.00%`, `5,647` direct trilingual sources at
  100% `zh`/`zh-TW`, zero dependency vulnerabilities and both current/history
  Gitleaks lanes;
- visual job `93303992034`: PASS in `3m28s` — `91/91` fixed-Linux cases;
- controlled runtime job `93303992327`: correctly skipped;
- visual artifact `9044624626`, digest
  `sha256:33faa7faccab9ca0d541b0a882e6b69fbca9506a84926a1ce466c05fc95a094f`;
  and
- Gitleaks artifact `9044683609`, digest
  `sha256:991266412bed7fbb7b11347df362ffc53fce2b9958b73469f9d85b3fe5fffae3`.

## Review, rollback and next checkpoint

Task Diff Review confirms that every activated route is Project-first and
independently fail closed, every package is fixed-schema/private/immutable,
every command is actor-bound and transactional, and no external or lifecycle
authority was added. After retained preferences/packages/Files/receipts/audits
exist, rollback disables only the P6-08 routes and live composition through a
reviewed forward repair; it never deletes history or exposes a raw File URL.

Checkpoint 2 is PASS. P6-08 remains in progress. Autopilot next implements
only checkpoint 3: a dense trilingual Tooling List section in the selected
Project workspace using the shared DenseGrid and fixed P6-08 data source; ten
views, saved layout/query state, stable paging, accessible selection and
selected-object navigation; plus one secondary Export review/download flow
with exact mode/count/validity/redaction/immutable-version and honest
loading/read-only/error/conflict/processing/success/expiry/replay states. The
controlled Site, production ERPNext and Tooling/lifecycle authority remain
inactive.
