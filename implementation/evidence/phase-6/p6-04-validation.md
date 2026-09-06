# P6-04 Level 2 Validation — Manufacturing, Supplier Milestones and ERP Cost Projection

Recorded: `2026-08-08T16:40:58Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`5ca13abdbbbe08493ee54e9627849cfb0afdec01`

Requirements:
`FR-TL-005..008`

## 1. Outcome

P6-04 delivers the frozen minimum complete vertical slice:

- immutable NPI-owned manufacturing-plan successors for one exact Tooling
  Revision, with internal make/buy/hybrid planning, engineering estimate,
  budget fact, responsible internal Project member and ordered milestones;
- exact released controlled-document dependency evidence without treating
  that evidence as Tooling approval, release or manufacturing authority;
- append-only internal-user milestone observations with exact immutable File
  Revision evidence, including supplier-responsible milestones that remain
  explicitly reported by an internal actor; and
- a closed read-only ERP procurement/cost projection whose production reader
  is absent and whose exact outward truth is `unavailable`.

Project-first authorization, System Manager management transport, current
internal membership, actor-bound sealed replay, exact predecessor/current
version conflicts, one transaction, append-only audit and the independent
fail-closed P6-04 route switch are live. The dense trilingual workspace keeps
plan, milestone, evidence, design release, manufacturing authorization and
ERP truth visibly separate.

No formal Supplier, supplier account/portal, production ERPNext endpoint or
credential, ERP write, Outbox dispatch, successful target identifier, actual
cost or Tooling lifecycle transition was installed. `DR-REC-010` continues to
hold exact Tooling approval/release/manufacturing authority.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TL-005` | `TECHNICAL_VERIFIED_FOUNDATION` | Internal sourcing, engineering estimate, budget and released proposal/quotation evidence are immutable and live; formal funding, PO and G3 readiness remain unavailable. |
| `FR-TL-006` | `TECHNICAL_VERIFIED_FOUNDATION` | Exact Tooling Revision lineage plus released controlled design evidence are live; Tooling approval/release/manufacturing authority remains held by `DR-REC-010`. |
| `FR-TL-007` | `TECHNICAL_VERIFIED_FOUNDATION` | Ordered milestone plans and append-only internal observations/evidence are live; supplier login, portal and supplier-authored updates remain unavailable. |
| `FR-TL-008` | `TECHNICAL_VERIFIED_FOUNDATION` | The closed read-only projection and unavailable default are live; real ERPNext adapter observations, procurement execution and actual cost remain Phase 8. |

`implementation/REQUIREMENT_TRACEABILITY.csv` is updated to these exact
results and cites the product, tests, controlled verifier and this report.

## 3. Ordinary and controlled Gates

Exact-SHA ordinary CI `31266800163` passed checkpoint `5ca13ab` before the
final Site dispatch:

- repository `93126150493`: `1,214/1,214` tracked Python tests, `756/756`
  frontend unit tests, `326/326` non-visual E2E, statements coverage `80.03%`,
  zero-vulnerability audits, current-tree Gitleaks and complete PR-history
  Gitleaks PASS;
- i18n audit: `4,641` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- visual `93126150510`: fixed-Linux governed matrix `82/82` PASS; and
- controlled `93126150893`: correctly skipped.

The final workflow `31267181068` retained exact SHA `5ca13ab`:

- repository `93127118034`: PASS;
- visual `93127118025`: PASS, `82/82`;
- controlled runtime `93127118037`: PASS, including pinned tools, disposable
  Site, two migrations, cumulative P5/P6 predecessors, fresh P6-04 runtime,
  cross-process replay, independent P6-01/P6-02/P6-03/P6-04 route disable/
  recovery and cleanup; and
- runtime artifact `9024542728`, `p6-tooling-runtime-31267181068`, GitHub
  digest
  `sha256:c6214438b19d025b1e32b0c308913b1b393bba62e3eba742d4b67282554130c2`.

The final visual artifact is `9024528394`, digest
`sha256:4be921ad1381e67783a4390b62c5cb15141df443ab550d8ab6e45274970b43db`.
The final current-tree Gitleaks artifact is `9024598560`, digest
`sha256:27f86de63a4473a66141afd89aef4b763481fced5efc1dbf0f8beb8516984ae1`.
The preceding ordinary-CI visual artifact is `9024424604`, digest
`sha256:81ed21fd6853a1833bdd1fabc14928840921025cbaf7bf19e4bb8ed12245c73a`;
its Gitleaks artifact is `9024492810`, digest
`sha256:3f91748f7ec8ecb9667b1ea53afc12991a0f1e94342a26f8ba2feefbbc7c599e`.

The runtime artifact records `result=PASS`, head SHA `5ca13ab`, run
`31267181068`, disposable Site `npi.localhost`, database
`npi_one_runtime`, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1` and cumulative scope
`p5-01-through-p6-04`.

The final P6-04 runtime summary proves two guarded DocTypes, two immutable
plan revisions, two milestone observations and three retained Tooling Revision
rows, while both `erpProjection` and `manufacturingAuthorization` remain
`unavailable`. It also proves exact released dependency evidence, an actual
unreleased-revision rejection, replay, stale conflict, rollback, IDOR denial,
generic mutation denial and independent route disable/recovery.

## 4. Level 2 module and UI checks

- affected verifier/API/team-contract checks: `73/73` PASS;
- complete tracked Python regression in CI: `1,214/1,214` PASS;
- complete frontend unit suite: `44` files and `756/756` PASS;
- complete non-visual browser matrix: `326/326` PASS;
- governed fixed-Linux visual matrix: `82/82` PASS, including exact English,
  Simplified-Chinese and Traditional-Chinese P6-04 cases;
- direct three-language coverage: `4,641/4,641` source strings in both Chinese
  catalogs, with mixed-language scans PASS;
- boundary, industrial UI, accessibility, TypeScript/build, package audits,
  both secret lanes, additive migrations, shell syntax and
  `git diff --check`: PASS.

The local workspace also contained user-owned untracked prerequisite tests,
so local discovery reported `1,220`; the official clean-checkout tracked count
is the CI-proven `1,214` and is the number used for this Gate.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Manufacturing plan/milestone/observation and closed ERP domains plus two guarded DocTypes | domain/metadata/contract suites, additive migrations and controlled Site |
| Repository, BFF, request security and independent route switch | repository/API suites plus controlled containment, replay, conflicts, rollback, audit and IDOR |
| OpenAPI and data ownership | closed schemas, exact ownership and no-fake-Supplier/lifecycle/ERP assertions |
| Data source, workspace, styles and catalogs | `756/756` unit, `326/326` browser, i18n/UI/boundary audits and `82/82` Linux visuals |
| Runtime verifier/workflow and actor fixture | verifier/team-contract regressions, complete ordinary CI and exact-SHA controlled Gate |
| Trace/controller/evidence plus canonical verifier | CSV uniqueness, generated-form reconciliation, YAML parse, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and recovery analysis

The review covers `4ab4782..5ca13ab`: `94` task files across the frozen audit,
domain/metadata, repository/BFF, live workspace, reviewed Linux evidence,
runtime verifier and exact tests (`15,221` insertions, `119` deletions). Every
commit belongs to one planned checkpoint, evidence-only baseline sync or a
serial evidence-proved technical recovery. No unrelated user dirty or
untracked file appears in a task commit.

The controlled boundary exposed two fixture-only roots after complete ordinary
CI remained green:

1. workflow `31265692653` proved that using `Administrator` as the P6-04
   responsible member violated the product's real current-project-membership
   precondition. Repair `f1c260b` creates a namespaced disposable System User,
   grants only the already-required transport roles and adds it through the
   formal Project team command; no product permission was relaxed;
2. workflow `31266455642` then proved the actor creation path reached the
   formal `configure-team` contract, whose `roleAssignments` and
   `raciAssignments` arrays require at least one value. Repair `5ca13ab`
   queries and resubmits the exact retained role/RACI unchanged while adding
   the new member. It changes no authority assignment or product contract.

The final Site passed on the repaired verifier. No Requirement, public API,
permission, Schema intent, ownership, transaction, idempotency, audit, visual
baseline, threshold or PASS criterion was weakened.

## 7. Security, migration, rollback and limitations

- Project authorization precedes protected Master/Revision/plan/evidence
  resolution; mutation remains current-project-member plus internal System
  Manager transport under the held production lifecycle policy.
- Generic Desk create/write/delete, cross-Project/tenant references, stale
  tips, arbitrary evidence roles, raw URLs and actor-mismatched replay fail
  closed.
- Migration is additive/idempotent and the controlled Site passed it twice.
- Before retained use, the task commits may be reverted. After retained rows,
  rollback disables only P6-04 routes/projections and uses a reviewed forward
  repair; it never deletes or rewrites a plan, observation, evidence, audit,
  receipt or any retained P6-01/P6-02/P6-03 object.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not affect any job.
- Exact Tooling lifecycle approval/release/manufacturing authority, formal
  Supplier, supplier portal, ERPNext procurement/receipt/invoice/actual cost,
  adapter connectivity and every external mutation remain unavailable.

## 8. Decision and transition

P6-04 passes its Level 2 Task Gate. The next atomic task is P6-05 only:
`FR-TX-009..011`, `FR-TX-019`, `FR-TX-020`, `FR-TL-009`, the bounded
`FR-TL-010` foundation and `FR-TL-017..018` for defect/action truth, separated
Standard/Trial Actual/Approved Baseline process truth and versioned capacity
scenarios. It begins with a bounded Requirement/domain/existing-capability
audit. Exact Tooling lifecycle commands and production red semantics remain
held; no Trial/ERP execution or unapproved capacity formula may be invented.
