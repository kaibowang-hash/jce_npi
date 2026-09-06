# P6-06 Level 2 Validation — Acceptance and Asset Request Foundation

Recorded: `2026-08-09T03:31:50Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`de7bef7a1cd8894ee350567e2b157dd4b1e52ccb`

Requirements:
`FR-TL-011`, `FR-TL-012`, `FR-TL-013`, `FR-TL-014`, `FR-TL-015`,
`FR-TL-016`

## 1. Outcome

P6-06 delivers the frozen minimum complete vertical slice:

- immutable acceptance-evidence revision chains bound to one exact Project,
  Tooling Master, physical Tooling Set, frozen Set-to-Revision binding and
  Tooling Revision snapshot;
- exactly nine acceptance evidence categories with evidence-presence
  dispositions, without treating category coverage as business approval,
  lifecycle release or formal quality acceptance;
- immutable Project evidence for move/loan/return/archive/scrap intentions,
  critical/wear spare recommendations and repair authorization, quote,
  responsibility, downtime and verification;
- mandatory exact clean private customer-authorization evidence for every
  customer-owned Tooling repair;
- one operation-specific `create_or_update_tool_asset` Mock preparation path
  bound to a physical Set and exact acceptance revision; and
- a separate closed read-only ERP Asset projection whose unavailable state is
  visible and whose future mapping cardinality is exactly zero-or-one per
  physical Set.

The Project-first repository, immutable acceptance append, bounded request
reads, System Manager management commands, actor-bound sealed replay, exact
predecessor conflict, one transaction, append-only audit, IDOR-safe reads and
independent fail-closed P6-06 switch are live. The dense English, Simplified-
Chinese and Traditional-Chinese workspace keeps evidence, business approval,
request input, dispatch, target result and ERP projection visibly separate.

The request remains exactly `draft` / `validated_mock` / `unavailable` /
`prohibited` / `not_requested`. No Outbox, worker, Webhook, endpoint,
credential, network request, target ID, formal mapping, Asset mutation,
location/movement execution, inventory, maintenance, repair transaction or
cost result is created. Production and sandbox ERPNext were not contacted.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TL-011` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable nine-category acceptance evidence and Mock request input are live; business approval, official quality and real Asset execution remain Phase 7/8. |
| `FR-TL-012` | `TECHNICAL_VERIFIED_FOUNDATION` | One physical Tooling Set is the sole zero-or-one mapping subject; formal Asset ID confirmation and reconciliation remain Phase 8. |
| `FR-TL-013` | `TECHNICAL_VERIFIED_FOUNDATION` | The read-only Asset projection is explicitly unavailable; authenticated location, life, maintenance, movement and repair observations remain Phase 8. |
| `FR-TL-014` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable move/loan/return/archive/scrap Project evidence is live; actual Asset movement and approval execution remain Phase 8. |
| `FR-TL-015` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable critical/wear spare recommendations are live; formal Item, supplier mapping and inventory remain ERPNext/Phase 8 truth. |
| `FR-TL-016` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable repair authorization/quote/responsibility/downtime/verification evidence is live and customer-owned authorization is enforced; formal repair cost/history remain Phase 8. |

`implementation/REQUIREMENT_TRACEABILITY.csv` and the reconciliation verifier
are updated to these exact results. No full requirement is mislabeled complete
where its target-confirmed ERPNext behavior remains unavailable.

## 3. Ordinary and controlled Gates

Exact-SHA ordinary CI `31291977009` passed checkpoint `de7bef7` before the
final Site workflow:

- repository `93190608487`: `1,291/1,291` tracked Python tests, `777/777`
  frontend unit tests in `48/48` files, `337/337` non-visual E2E, zero-
  vulnerability package audits and both current-tree/history Gitleaks lanes;
- i18n audit: `5,087` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage; and
- visual `93190608492`: fixed-Linux governed matrix `88/88` PASS.

Final workflow `31292306716` retained the same exact SHA and passed all three
jobs. Repository `93191451402` and visual `93191451404` repeated the complete
repository and unchanged `88/88` visual Gates. Controlled runtime job
`93191451432` passed pinned tools, disposable Site creation, two migrations,
cumulative P5/P6 predecessors, fresh P6-06 runtime, cross-process replay,
independent P6-06 disable/recovery and cleanup.

Runtime artifact `9031822151`, `p6-tooling-runtime-31292306716`, has GitHub
digest
`sha256:a55daeaac0dbc29eeab853fd6ca76d74d2b0fd2df60b4722ba134d82af5e2b8b`.
Its retained summary records `result=PASS`, exact head SHA `de7bef7`, Site
`npi.localhost`, database `npi_one_runtime`, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1` and cumulative scope
`p5-01-through-p6-06`.

Ordinary visual artifact `9031715466` has digest
`sha256:7b06b98c72774684f45c28bc98fd121ce96016cbd97c4cd748b89ff04d9fe925`.
Ordinary Gitleaks artifact `9031770982` has digest
`sha256:58625aaf4ba4e68067eefa66d8dfc1c21faa12a7fb988b046ff1e6c7e937f0eb`.

## 4. Controlled truth and negative matrix

The cumulative Site proves:

- two immutable acceptance revisions with exact predecessor, stable context,
  nine-category coverage and changed snapshot hashes;
- customer-owned repair authorization, quote/responsibility/downtime and
  verification evidence while all ERP repair results stay unavailable;
- exact physical-Set-to-frozen-Revision binding, never a latest-Revision or
  Master/quantity shortcut;
- Mock request preparation with no formal Asset ID, mapping, Outbox, network
  or target-success truth;
- same-process and cross-process sealed replay;
- stale successor conflict and transaction rollback without partial business,
  audit or receipt rows;
- Project IDOR denial and generic Desk mutation denial; and
- independent P6-06 route disable/recovery without changing P6-01 through
  P6-05 routes or retained data.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Acceptance/request/projection domains and guarded DocTypes | domain, metadata, contract, additive-migration and controlled-Site suites |
| Repository, BFF, request security and route switch | repository/API suites plus containment, replay, conflicts, rollback, audit and IDOR |
| OpenAPI, ownership and receipt values | closed-schema, exact-ownership and no-fake-approval/ERP assertions |
| Data source, workspace, styles and catalogs | `777/777` unit, `337/337` browser, i18n/UI/boundary audits and `88/88` Linux visuals |
| Runtime verifier/workflow and disposable fixtures | verifier regression, complete ordinary CI and exact-SHA controlled Gate |
| Trace/controller/evidence | 282-row uniqueness, generated-form reconciliation, YAML parse, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and repair analysis

The product review covers `943d1ea..de7bef7`: `95` files, `14,271`
insertions and `84` deletions across the bounded audit, domain/metadata,
repository/BFF, live workspace, reviewed Linux evidence, runtime verifier and
exact tests. Every commit belongs to one planned checkpoint, evidence-only
visual sync or serial evidence-proved runtime repair. No unrelated user dirty
or untracked file appears in a task commit.

The controlled boundary exposed four serial exact roots after ordinary CI
remained green:

1. the verifier selected an engineering Revision rather than first resolving
   the physical Set's frozen binding;
2. the corrected selection still coupled the P6-05 engineering revision to
   the P6-03 physical binding instead of retaining those distinct identities;
3. the bounded request repository passed a supported ordering predicate to a
   helper whose interface did not yet accept it; and
4. the negative verifier expected `400` although the frozen OpenAPI/error
   contract correctly returns `422 VALIDATION_FAILED` for missing customer
   authorization.

Repairs `fafc578`, `459c9f0`, `2dfe79a` and `de7bef7` changed only the exact
binding selection/hydration, bounded helper interface and contract-aligned
verifier expectation. They preserve the Requirement, public route shapes,
authorization, ownership, Schema, transaction, idempotency, audit, visual
thresholds and PASS criteria.

## 7. Security, migration, rollback and limitations

- Project authorization precedes protected Master/Set reads; management
  commands require System Manager transport before exact dependency
  resolution. Ordinary non-privileged reads remain IDOR-safe.
- Generic Desk create/write/delete, cross-Project/tenant references, stale
  successors, caller approval/dispatch/target flags, raw URLs and actor-
  mismatched replay fail closed.
- Migration is additive/idempotent and the controlled Site passed it twice.
- Before retained use, task commits may be reverted. After retained rows,
  rollback disables only P6-06 routes/projections and uses a reviewed forward
  repair; it never deletes or rewrites acceptance/request/audit/receipt truth.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not fail a Gate.
- Business acceptance approval, official Trial/quality truth, Tooling
  lifecycle, formal Asset mapping/creation/update, target dispatch, location,
  movement, maintenance, repair, spares, inventory and cost remain unavailable
  until their authoritative Phase 7/8 boundaries.

## 8. Decision and transition

P6-06 passes its Level 2 Task Gate. Standing transition authority activates
only the bounded P6-07 Requirement/domain/existing-capability audit for
`FR-TX-012..018` and `UX-016`: the controlled Tooling List XLSX import flow.
The reviewed 43-column mapping remains a proposal under `DR-REC-007`; no
production semantic mapping, ERPNext contact or destructive rollback is
authorized.
