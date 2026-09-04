# P6-08 Level 2 Validation — Controlled Tooling List and Object-package Export

Recorded: `2026-08-10T04:36:24Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`68f230fee73b1b6ca95206346d128e1518613d82`

Primary requirement: `UX-007`

Canonical support: `FR-UX-007`, `FR-UX-025`, `FR-UX-030`

## 1. Outcome

P6-08 delivers the frozen minimum complete vertical slice for a controlled
Tooling engineering list and object-package export:

- ten fixed Project-relative views with closed search, sort, group, column and
  stable keyset-paging values;
- actor/Project/view/schema-bound personal preference restoration with
  optimistic conflict and corrupt-preference fallback;
- mutually exclusive explicit-selection and complete-filter export modes with
  exact Master or query snapshot hashes and a maximum of 100 Masters;
- one immutable three-member package (`manifest.json`,
  `tooling-objects.csv`, `README.txt`) with localized human-readable members,
  stable machine keys, exact member/manifest/package hashes and formula
  neutralization;
- single-transaction private Frappe File, package, audit and sealed
  idempotency-receipt persistence, without returning a raw File URL;
- creator-bound, Project-authorized, hash-verified POST download with
  attachment security headers and a fixed one-hour validity boundary; and
- a dense industrial English, Simplified-Chinese and Traditional-Chinese
  selected-Project workspace with ten views, stable paging, selection across
  pages, review-before-export and honest loading/empty/read-only/validation/
  conflict/processing/success/expired/download-failure/replay states.

The package remains an allowlisted NPI engineering object package, not an
arbitrary DocType/report/database dump. It excludes raw workbook values,
external customer/supplier identifiers, custody/repair text, cost, evidence,
ERP/lifecycle truth and private File paths or bytes. Production mapping,
ERPNext contact and Tooling lifecycle authority remain unavailable.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `UX-007` | `TECHNICAL_VERIFIED_FOUNDATION` | Ten Tooling views, personal restoration, dense paging/selection/filter controls and authorized immutable object-package export are live and runtime proven. The generic global editable-grid/bulk-operation interpretation and representative production-scale performance remain outside this bounded Tooling slice. |

The canonical `FR-UX-007`, `FR-UX-025` and `FR-UX-030` dispositions are not
overclaimed: the Tooling-specific fixed views/export complete the accepted
foundation, while unrestricted arbitrary views, global data export and
representative-scale proof remain prohibited or external.

## 3. Ordinary, visual and controlled Gates

Exact-SHA ordinary pull-request CI `31355006189` passed:

- repository `93352955845`: `1,420/1,420` tracked Python tests, `809/809`
  frontend unit tests in `52/52` files, `352/352` non-visual E2E, statements
  `80.07%`, clean generation/type/lint/build, zero-vulnerability complete and
  production audits, and both current-tree/full-branch Gitleaks lanes;
- i18n audit: `5,753` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage; and
- visual `93352955834`: fixed-Linux governed matrix `94/94` PASS.

Ordinary visual artifact `9050369290` has digest
`sha256:6907839620609abb7eb3a128304e759f093d6af50324aa01a1b8ddfceb8f9bdc`.
Ordinary Gitleaks artifact `9050477721` has digest
`sha256:d4c5ecb69580a95c8bda59a639a4e8fdbaaca3f86a72c7add24957f3d5298f00`.

Final unchanged workflow `31355555773` retained the same exact SHA and passed
repository `93354448586`, visual `93354448605` at `94/94`, and controlled
runtime `93354448564`. Runtime artifact `9050565297`,
`p6-tooling-runtime-31355555773`, has digest
`sha256:2b6b91366fff2ba206bec9cfc4784472c1a4659e5eeb9dfbd2802eccbcbff222`.
Its summary records `result=PASS`, exact head SHA, Site `npi.localhost`,
database `npi_one_runtime`, fixed Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1`, cumulative scope
`p5-01-through-p6-08` and predecessor scope `p5-01-through-p6-07`.

Final visual artifact `9050546526` has digest
`sha256:169e49019c28d64d5c79bbb145759617ad7dc42b8aef83a7631dd2d3bac584d2`.
Final Gitleaks artifact `9050637324` has digest
`sha256:843abc3661a89d038c8ae9e44f199fce250b99152a3795857276fbc237908a3f`.

## 4. Controlled truth and negative matrix

The cumulative disposable Site proves all predecessors plus P6-08 using only
visibly synthetic bounded truth. The final export summary records three
guarded DocTypes, ten total views, eight non-empty fixture views, four packages,
three localized packages, formula neutralization, one-hour expiry denial and
zero integration traffic. The retained proof includes:

- exact complete-list, every fixed-view, stable cursor and stale-cursor truth;
- saved/fresh/replayed personal preference, optimistic conflict and immutable
  generic-write/delete denial;
- selection and complete-filter packages with fixed members, deterministic
  order, UTF-8/Unicode/CRLF/BOM behavior, exact hashes and redaction manifest;
- same-process and fresh-process create/download replay without package,
  receipt, audit or byte-cardinality drift;
- guest/external/non-export/other-user/cross-Project/wrong-hash/expired/stale/
  conflict denial and authorization before secondary object resolution;
- independent route disable/recovery without losing retained truth;
- two migrations, private File truth, raw-log sentinel scans, no Outbox/Inbox
  growth, no network/ERP contact and disposable cleanup; and
- cross-process replay confirmation for all three languages: `en`, `zh` and
  `zh-TW`.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Query/view/filter/sort/group domains | ten-view membership, closed values, stable order/cursor, full-result hashes and bounds |
| Preference/package/receipt domains and DocTypes | snapshot/version/hash/immutability, guarded CRUD, additive metadata and migration checks |
| Renderer/private File repository | fixed ZIP members, localized bytes, formula safety, redaction, exact File bytes/name/hash/privacy and rollback |
| Project-first BFF | authorization order, CSRF, replay/conflict, stale/IDOR/expiry/hash denial and no raw URL |
| Data source/workspace/shared grid/i18n | `809/809` unit, `352/352` E2E, direct trilingual audit and `94/94` governed visuals |
| Runtime verifier/workflow | `56/56` focused export regressions, complete Python/ordinary CI, two migrations and cumulative controlled Site |
| Trace/controller/evidence | 282-row uniqueness/evidence reconciliation, YAML parse, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and serial repair analysis

The bounded review covers `d5d6064..68f230f`: `109` files, `14,144`
insertions and `84` deletions across `27` task commits. Every commit belongs to
the frozen four-checkpoint P6-08 slice, a reviewed Linux baseline update or a
serial evidence-proved controlled-runtime repair. No user-owned dirty, Darwin,
local-runtime or untracked file appears in a task commit.

The controlled boundary exposed later runtime paths that mock/unit evidence
could not reach. Repairs remained serial and exact:

1. align the visibly synthetic source fixture and expose only response-neutral
   structural problem/status metadata;
2. provision the disposable cursor-signing precondition and normalize Frappe
   Datetime precision for preference and package snapshot truth;
3. isolate preference validation and package creation only long enough to
   prove their exact failing substages, then close those diagnostics;
4. normalize Frappe text content to authoritative package bytes and retain the
   actual conflict-safe private File name without broadening accepted names;
5. accept both Frappe permission-stage `403` and validation-stage `417` as
   rejected mutations only when the exact protected hash remains unchanged;
   and
6. verify each guarded DocType through its real immutable hash field, using
   `payload_hash` for the command receipt rather than querying a nonexistent
   `snapshot_hash`.

The failed diagnostic/final runs remain recovery evidence only. Each repair
advanced the same controlled path; prior roots did not recur. The final
workflow passed with temporary diagnostics closed. No Requirement, public
route, role/permission, ownership, Schema, transaction, idempotency, audit,
visual matrix, threshold or PASS rule was weakened.

## 7. Security, migration, rollback and limitations

- Project and export authority are checked before Master/package/File
  resolution; creator, hash, expiry, CSRF and actor-bound idempotency are
  revalidated on download.
- Generic Desk writes/deletes, unknown fields/expressions, cross-Project data,
  stale snapshots, altered replay and expired artifacts fail closed.
- Audit and ordinary logs retain structural hashes/counts rather than package
  contents; responses never expose a raw private File URL.
- Migration is additive/idempotent, and the controlled Site passed two
  migrations before the full cumulative lifecycle.
- Before retained use, task commits may be reverted. After retained package,
  File, receipt or audit history, rollback disables the independent P6-08
  routes/workspace and uses a reviewed forward repair; it does not delete or
  rewrite immutable history.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not fail a Gate.
- Production mapping, customer data, representative production-scale
  performance, arbitrary/global export, raw private URLs, ERPNext contact and
  Tooling lifecycle authority remain unavailable.

## 8. Decision and transition

P6-08 passes its Level 2 Task Gate. `UX-007` retains the exact
`TECHNICAL_VERIFIED_FOUNDATION` disposition with the complete P6-08 evidence
set. Because P6-08 closes Phase 6, the cumulative Phase 6 Level 3 release Gate
is recorded separately in `implementation/phase-6-gate.md`.
