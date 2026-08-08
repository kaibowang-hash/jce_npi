# P6-03 Level 2 Validation — Tooling Revisions, Specifications, Cavities, Inserts and Process Chain

Recorded: `2026-08-08T11:23:47Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`4ab478259724a8507891f24b33f858ffe9a117a0`

Requirements:
`FR-TX-004..008`, `FR-TL-002`, `FR-TL-003`, `FR-TL-006`

## 1. Outcome

P6-03 delivers the frozen minimum complete vertical slice:

- immutable Tooling Revision successors with closed unit-bearing engineering
  specifications and exact controlled Document Revision provenance;
- exact cavity-to-current-Applicability/Part mapping, versioned inserts and
  independently identified customer/SN/KW/TH/supplier-reference provenance;
- one immutable controlled material/color/compliance specification for an
  exact current Part Revision;
- immutable ordered primary/second-shot/overmold process-chain successors with
  exact Part and Tooling Revision references; and
- one append-only initial physical-Set source-Revision binding without
  rewriting the retained P6-02 Set snapshot.

Project-first authorization, System Manager-only mutation, actor-bound sealed
replay, exact predecessor/current-version conflicts, one transaction,
append-only audit and the independent fail-closed P6-03 route switch are live.
The dense trilingual workspace exposes exact Revision/specification/cavity/
insert/process-chain/binding truth and honest unavailable lifecycle, Supplier,
ERP Asset/location/execution, combined-Trial and automatic-impact capabilities.

`DR-REC-010` still holds exact Tooling Requirement/Revision/Set lifecycle
states, transitions, design approval/release and manufacturing/Trial authority.
Production workbook mapping, supplier portal, ERPNext endpoint/credential and
every external mutation remain absent.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TX-004` | `TECHNICAL_VERIFIED_FOUNDATION` | Exact cavity UUID/identifier, enabled/sealed structure and current Applicability/Part mapping are live; cavity Trial, defect and capacity results remain Phase 7/P6-05. |
| `FR-TX-005` | `TECHNICAL_VERIFIED_FOUNDATION` | Ordered primary/second-shot/overmold structure, parent relation and exact machine/Part/Tooling references are live; combined Trial remains Phase 7. |
| `FR-TX-006` | `TECHNICAL_VERIFIED` | Insert/changeover identity, model applicability, immutable version, duration and evidence-bound validation state are structured, queryable and runtime-proven. |
| `FR-TX-007` | `TECHNICAL_VERIFIED_FOUNDATION` | One-to-many Part and Tooling external identities retain source, raw value and effectivity; production workbook splitting/import remains P6-07. |
| `FR-TX-008` | `TECHNICAL_VERIFIED_FOUNDATION` | Controlled material/grade/color/compliance/secondary-process facts bind to an exact immutable Part Revision; automatic impact action remains Phase 9. |
| `FR-TL-002` | `TECHNICAL_VERIFIED_FOUNDATION` | The closed core unit-bearing Tooling specification is live; unapproved mold-type extensions remain explicitly unavailable. |
| `FR-TL-003` | `TECHNICAL_VERIFIED_FOUNDATION` | Multi-Project/Master/Part Applicability now includes exact cavity mapping; Trial and quality results remain Phase 7. |
| `FR-TL-006` | `TECHNICAL_VERIFIED_FOUNDATION` | Immutable Tooling Revision lineage and controlled design-document provenance are live; approval/release commands remain held by `DR-REC-010`. |

`implementation/REQUIREMENT_TRACEABILITY.csv` is updated to these exact
results and cites the product, tests, controlled verifier and this report.

## 3. Ordinary and controlled Gates

Diagnostics-closed ordinary CI `31254281586` passed exact SHA `4ab4782`
before the final Site dispatch:

- repository `93095213074`: `1,177/1,177` tracked Python tests, `744/744`
  frontend unit tests, `321/321` non-visual E2E, statements coverage `80.07%`,
  zero-vulnerability audits, current-tree Gitleaks and complete PR-history
  Gitleaks PASS;
- visual `93095213086`: fixed-Linux governed matrix `79/79` PASS; and
- controlled `93095213506`: correctly skipped.

The final diagnostics-closed workflow `31254642262` retained the exact same
SHA:

- repository `93096129318`: PASS;
- visual `93096129329`: PASS, `79/79`;
- controlled runtime `93096129310`: PASS, including pinned tools, disposable
  Site, two migrations, cumulative P5/P6 predecessors, fresh P6-03 runtime,
  cross-process replay, independent P6-01/P6-02/P6-03 route disable/recovery
  and cleanup; and
- runtime artifact `9021059611`, `p6-tooling-runtime-31254642262`, GitHub
  digest
  `sha256:aa0b3c80f38ae7ac6acbe16245e5baf6e176c470c15bf7a435dae231afee52bc`.

The final visual artifact is `9021054263`, digest
`sha256:5eb17241fa267ce39c37ab709d0865702560b526bf83851970255bb46b91b1d6`.
The final Gitleaks artifact is `9021114730`, digest
`sha256:bfe7dc41bd8e49e7aacc4fe8ac3313536199de526c3b38ea0573b812483b57d9`.
The preceding ordinary-CI visual artifact is `9020948710`, digest
`sha256:d14aeacd78aa14af22745eb246b5bf15fb7506b7158cc0f6deceb9f944d0c4ee`;
its Gitleaks artifact is `9021018709`, digest
`sha256:709b68e0f39820ddf2e225b0d05f0c7c87557e3c9f83e57d1076efbb37b80291`.

The runtime artifact records `result=PASS`, head SHA `4ab4782`, run
`31254642262`, disposable Site `npi.localhost`, database
`npi_one_runtime`, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1` and cumulative scope
`p5-01-through-p6-03`.

The final P6-03 runtime summary proves:

- four additive DocTypes, two immutable Tooling Revision tips and two ordered
  process-chain revisions;
- one exact controlled Part specification and one exact initial Set-source
  binding;
- exact cavity, insert, model, external-identity and source-hash truth;
- replay, predecessor/current-version conflict, rollback and IDOR denial; and
- diagnostics closed plus independent P6-03 disable/recovery without weakening
  the retained cumulative P5/P6-01/P6-02 truth.

## 4. Level 2 module and UI checks

- focused diagnostics-closure verifier checks: `16/16` PASS;
- complete clean-tree Python regression: `1,177/1,177` PASS;
- complete frontend unit suite: `42` files and `744/744` PASS;
- complete non-visual browser matrix: `321/321` PASS;
- governed fixed-Linux visual matrix: `79/79` PASS, including exact English,
  Simplified-Chinese and Traditional-Chinese P6-03 cases;
- i18n audit: `4,419` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- boundary, industrial UI, display-brand, TypeScript/build, package install,
  zero-vulnerability audit and both secret lanes: PASS; and
- migrations, shell syntax and `git diff --check`: PASS.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Revision/specification/cavity/insert/process-chain/binding domain and four guarded DocTypes | domain/metadata/contract suites, additive migrations and controlled Site |
| repository, BFF, request security and route switch | repository/API suites plus controlled containment, replay, conflicts, rollback, audit and IDOR |
| OpenAPI and data ownership | closed schemas, exact ownership and no-fake-lifecycle/Supplier/ERP assertions |
| Tooling data source, workspace, styles and catalogs | `744/744` unit, `321/321` browser, i18n/UI/boundary audits and `79/79` Linux visual matrix |
| runtime verifier/workflow | affected verifier suites, complete ordinary CI and exact-SHA diagnostics-closed controlled Gate |
| DateTime and runtime-fixture repairs | direct regressions, full Python, complete ordinary CI and cumulative Site proof |
| trace/controller/evidence plus canonical generator/verifier | CSV uniqueness, YAML parse, generated-form equality, V1.2 reconciliation, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and recovery analysis

The review covers `36e2b9b..4ab4782`: `90` task files across the frozen plan,
domain/metadata, repository/BFF, live workspace, governed Linux evidence,
runtime verifier and exact tests (`15,404` insertions, `166` deletions).
Every commit belongs to one planned checkpoint, evidence-only baseline sync or
a serial evidence-proved technical recovery. No unrelated user dirty or
untracked file appears in a task commit.

The controlled boundary exposed only serial, later-stage roots:

1. verifier projections initially selected a top-level rather than nested Part
   Revision, used a non-Project model reference and queried a non-governed
   cockpit path; each fixture repair added a direct regression;
2. command effectivity dates required canonical date-only values rather than
   the verifier's timestamp text;
3. the first opaque server failure was narrowed by one response-neutral generic
   diagnostic and then one revision-create substage diagnostic to
   `P603_REVISION_INSERT / OperationalError`;
4. comparison with working P6-01 controllers proved all four P6-03 DocTypes
   passed ISO `...Z` timestamps directly to MariaDB `Datetime` fields. Repair
   `05a27b8` uses the existing validated Frappe UTC DateTime conversion at all
   four boundaries and adds cross-controller regression coverage;
5. the next Site passed all fresh P6-03 behavior and exposed only a stale
   recovered-route count in the cumulative P6-01 probe. Repair `ff32f0b`
   asserts the exact retained cumulative totals rather than weakening them to
   inequalities; and
6. checkpoint `4ab4782` closes P6-03 diagnostic activation before the final
   unchanged Gate.

Controlled run `31253914746` proved the repairs and full runtime path while the
diagnostic request header was still enabled. It was therefore retained as
recovery evidence, not accepted as the final Gate. Only workflow
`31254642262` combines the same successful behavior with diagnostics closed.

No Requirement, public API semantics, permission, Schema intent, ownership,
transaction, idempotency, audit, visual baseline, threshold or PASS criterion
was weakened.

## 7. Security, migration, rollback and limitations

- Project authorization precedes protected Master/Revision/Part/
  Applicability/Set/process-chain resolution; mutation remains same-tenant
  internal System Manager-only pending approved lifecycle policy.
- Generic Desk create/write/delete, cross-Project/tenant references, stale
  tips, arbitrary specification keys/source systems, raw URLs and unsealed
  replay fail closed.
- Migration is additive/idempotent and the controlled Site passed it twice.
- Before retained use, the task commits may be reverted. After retained rows,
  rollback disables only P6-03 routes/projections and uses a reviewed forward
  repair; it never deletes or rewrites a Revision, controlled Part
  specification, process-chain revision, Set binding, audit, receipt or any
  retained P6-01/P6-02 object.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not affect any job.
- Exact lifecycle approval/release, formal Supplier, ERPNext procurement/cost/
  Asset/location, combined Trial, automatic impact and production import
  behavior remain unavailable and must not be inferred from this PASS.

## 8. Decision and transition

P6-03 passes its Level 2 Task Gate. The next atomic task is P6-04 only:
`FR-TL-005..008` for internal make/buy, supplier milestones, design-release
dependency and an explicit unavailable/read-only ERP procurement/cost
projection. It begins with a bounded Requirement/domain/existing-capability
audit. No supplier portal, production lifecycle rule, ERP mutation, endpoint,
credential or target-system success may be invented.
