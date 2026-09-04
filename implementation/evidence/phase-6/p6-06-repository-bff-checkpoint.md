# P6-06 Repository and BFF Checkpoint

Recorded: `2026-08-09T00:28:41Z`

Status:
`PASS — LEVEL 1 PROJECT-FIRST REPOSITORY, BFF AND MOCK-ONLY REQUEST BOUNDARY`

Requirements:
`FR-TL-011`, `FR-TL-012`, `FR-TL-013`, `FR-TL-014`, `FR-TL-015`,
`FR-TL-016`

Exact stable product checkpoint:
`257ab50b70d2b47816989991d466fd3f99e1f231`

Primary product commit:
`24bf114cb87ac4da42bfddf6c731ca0ebc188551`

## Delivered boundary

- Activated exactly five independently guarded P6-06 routes: the combined
  acceptance/Asset context, immutable acceptance-evidence append, bounded
  Tool Asset request collection, exact request detail and physical-Set-scoped
  Mock request preparation.
- Every read authorizes the Project and exact Tooling Master before resolving
  contained identities. Missing and cross-Project objects remain one
  indistinguishable not-found result after Project authorization.
- Acceptance append re-resolves the exact Master, physical Set and snapshot,
  immutable Set-to-Revision binding, Tooling Revision/version/hash, Project
  member and clean private File Revision evidence. It preserves one contiguous
  immutable evidence chain per exact Tooling context.
- Tool Asset preparation accepts only fixed operation
  `create_or_update_tool_asset` and target mode `mock`. The server derives the
  exact request input from the physical Set, binding, Tooling Revision and one
  immutable acceptance revision; the browser cannot submit a generic target
  payload.
- Commands require authentication, CSRF, internal System Manager management
  transport and actor-bound idempotency. Acceptance/request row, append-only
  audit and sealed receipt share one transaction; replay, conflict and
  rollback retain exact truth.
- The request remains formal `draft`, input `validated_mock`, business
  approval `unavailable`, dispatch `prohibited` and target result
  `not_requested`. No route can claim that Tooling is accepted or an ERP Asset
  exists.
- ERP projection is strict read-only `unavailable`, owned/editable in ERPNext,
  with cardinality `zero_or_one_per_physical_set`. No formal Asset ID, target
  mapping, location, life, movement, maintenance, repair, spare, inventory or
  cost observation is fabricated.

## Security and negative proof

- `npi_p6_06_routes_disabled` is an independent default-closed switch. Missing
  or non-false configuration disables only the five P6-06 routes; safe sibling
  Tooling routes retain their own switches.
- API and repository tests cover guest/authenticated transport, CSRF, System
  Manager command authority, Project/Master authorization, IDOR, exact body
  closure, File/Set/binding/Revision containment, replay, idempotency conflict,
  version conflict, rollback and route recovery.
- The implementation creates no Outbox/Inbox row and exposes no endpoint,
  credential, adapter, worker, Webhook, retry/replay queue or network client.
  Tests assert zero network calls, zero target identifiers and zero formal
  mapping rows.
- Business approval remains unavailable because P6-06 has no approved
  acceptance policy, live Trial/official quality decision or Tooling
  acceptance authority. Evidence completeness is not approval.
- No Trial, Gate, lifecycle, ERPNext, Asset, stock, purchase, maintenance or
  cost mutation was added.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/acceptance_repository.py` and Tooling repository composition | bounded Project-first context, immutable chain, exact Set/binding/Revision/member/File containment, audit/receipt/transaction order, replay/conflict/rollback and IDOR in `test_phase6_tooling_acceptance_repository.py` |
| `tool_asset_request/frappe_repository.py` and operation-specific controller | exact Mock request hydration, fixed operation/state axes, physical-Set mapping subject, detail/list containment, sealed replay, no target truth and rollback in `test_phase6_tool_asset_request_repository.py` and `test_phase6_tooling_acceptance_api.py` |
| `tooling_api.py`, `tool_asset_request_api.py`, `bff.py`, request security and errors | five exact routes, Project-first authorization, strict request fields, authentication/CSRF/role behavior, independent fail-closed switch and sibling-route recovery in `test_phase6_tooling_acceptance_api.py` |
| guarded acceptance metadata and receipt uniqueness | immutable insert-only rows, unique version key, exact operation/target pairs and no default business row in `test_phase6_tooling_acceptance_metadata.py` |
| direct translations and generated catalogs | literal source extraction, 100% direct `zh`/`zh-TW`, placeholders and mixed-language scans in the complete repository gate |
| complete checkpoint | exact-SHA repository, `332` non-visual browser cases, `85` fixed-Linux visuals, dependency audit and both secret lanes in CI below |

## Local affected and regression evidence

- focused P6-06 repository/API/contract/metadata suite: `44/44` PASS;
- complete local Python discovery: `1,288/1,288` PASS, including six
  pre-existing user-owned untracked prerequisite tests; clean CI below proves
  the `1,282` tracked repository tests independently;
- frontend typecheck, lint, i18n, `768/768` unit tests, build and compilation:
  PASS;
- direct translation audit: `5,013` literal English sources with 100% direct
  `zh` and `zh-TW` coverage;
- dependency audit: zero vulnerabilities;
- P0 visual-governance structure: all eighteen fixed-Linux baselines present;
- V1.2 reconciliation, prototype-approval scan, prohibited-pattern scan,
  Python compilation and `git diff --check`: PASS; and
- local `scripts/verify.sh` could not start under host Node `24.2.0`/npm
  `11.3.0` because the repository pins Node `24.18.0`/npm `11.16.0`.
  Complete clean pinned-runtime CI below is the authoritative full gate. A
  separate local display-brand scan also sees the user's pre-existing
  untracked `frontend/public/images/npi-one-project-management-sketch.png`;
  it is outside this checkpoint and was neither changed nor staged.

## Visual catalog repair

Initial exact product CI `31285554375` passed repository job `93173561115`,
including complete E2E and both secret lanes, and failed only visual job
`93173561067`. Artifact `9029709948`, digest
`sha256:682d1a610eff601bb93775114d57c4793372a988af5792cd73a51f19fa8da361`,
retained all eighteen actual/diff pairs. Each existing P0 case differed only
in the durable bottom status-bar catalog digest introduced by the new direct
translations: `271` pixels for English and `242` for `zh`/`zh-TW`.

Repair commit `257ab50` copied only those eighteen reviewed Linux actuals to
their exact tracked targets. It changed no component, source copy, assertion,
case, matrix, threshold, tolerance or PASS rule. The user's untracked Darwin
snapshots were not staged or modified.

## Exact-SHA ordinary CI

Ordinary CI `31285929039` passed exact stable checkpoint `257ab50`:

- repository job `93174630031`: PASS — `1,282` tracked Python tests,
  `768` frontend unit tests, `332` non-visual E2E, `5,013` literal English
  sources with 100% direct `zh`/`zh-TW`, statements `80.35%`, zero dependency
  vulnerabilities and both current/history secret lanes;
- visual job `93174629999`: PASS — `85/85` fixed-Linux governed cases at
  exact-zero-difference;
- controlled runtime job `93174630243`: correctly skipped because checkpoint
  3 live SPA and checkpoint 4 disposable-Site proof are not active;
- visual artifact `9029830642`, digest
  `sha256:5e6145bd753d28784713888694fcd696ee600154a8d3ebad83f4075961334226`;
  and
- Gitleaks artifact `9029883853`, digest
  `sha256:162115cf98f74a06bc75f1e5f51a32e787e12b88fa776b31a65d1b9817ee7f2e`.

## Review, rollback and next checkpoint

Task Diff Review confirms the checkpoint is limited to the approved
repository/BFF/security boundary plus the isolated catalog-digest baseline
repair. Rollback is a reviewed forward fix: disable only P6-06 routes and
request preparation while preserving every immutable acceptance/request row,
audit and receipt. Never delete history, contact ERPNext or alter P6-01 through
P6-05 truth.

Checkpoint 2 is PASS. P6-06 remains in progress. Autopilot next implements
only checkpoint 3: a strict acceptance/Asset data-source contract and dense
selected-Master live workspace; complete loading, empty, denied, read-only,
validation, conflict, processing, unavailable and failure/retry states; direct
English/`zh`/`zh-TW`; keyboard/accessibility checks; operational E2E and
fixed-Linux visual evidence. Controlled Site, formal approval, lifecycle,
Trial/Gate and all real ERPNext/Asset execution remain inactive.
