# P6-05 Level 2 Validation — Defect, Process and Capacity Controls

Recorded: `2026-08-08T22:05:48Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`4e04eb47b1c5f77b9a442b3bef139df61cb83782`

Requirements:
`FR-TX-009..011`, `FR-TX-019`, `FR-TX-020`, `FR-TL-009`, bounded
`FR-TL-010` foundation and `FR-TL-017..018` foundations

## 1. Outcome

P6-05 delivers the frozen minimum complete vertical slice:

- immutable Tooling-defect revision chains with explicit severity, separate
  blocking intent, root-cause state, responsible current Project member,
  action lifecycle, target-round intention and exact clean File Revision
  verification evidence;
- immutable Customer Standard process-profile revisions, while Trial Actual is
  exactly `not_measured` and Approved Process Baseline is exactly
  `unavailable` until Phase 7 supplies their authoritative facts;
- exact rule-versioned comparison truth and the closed textual states
  `not_measured`, `within_tolerance`, `outside_tolerance` and `unavailable`,
  without activating production exception-color semantics; and
- immutable, successor-versioned Capacity Scenarios under published
  `capacity.v1`, with every input and result retained, deterministic server
  recomputation, visible `3600` conversion, `decimal-6-half-even` rounding,
  stable line identities, part/day/month output, assembly output, bottleneck
  and gap.

The Project-first repository, three narrow System Manager management commands,
actor-bound sealed replay, exact predecessor conflicts, one transaction,
append-only audit, IDOR-safe reads and independent fail-closed P6-05 switch are
live. The dense English, Simplified-Chinese and Traditional-Chinese workspace
keeps defect/action/verification, three process layers, capacity and unavailable
health truth visibly separate.

No Trial round, Gate, Domain Work Item, Requirement/Revision/Set lifecycle,
ERPNext, IoT, calibration, health score or maintenance recommendation is
created or mutated. Severity never implies Gate blocking. `DR-REC-002` retains
production exception-color semantics and `DR-REC-010` retains exact Tooling
lifecycle and manufacturing authority.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TL-009` | `TECHNICAL_VERIFIED_FOUNDATION` | Exact immutable defect, action, responsibility, target-round intention and verification truth are live; final Trial/G5/G6 policy integration remains Phase 7. |
| `FR-TL-010` | `TECHNICAL_VERIFIED_FOUNDATION` | Exact future Trial context, target-round references and separated comparison slots are live; Trial rounds and round comparison remain Phase 7. |
| `FR-TL-017` | `TECHNICAL_VERIFIED_FOUNDATION` | A closed unavailable ERP/IoT shot-count/source/calibration projection is live; no count or calibration rule is fabricated. |
| `FR-TL-018` | `TECHNICAL_VERIFIED_FOUNDATION` | A closed unavailable health/maintenance-policy projection is live; no score, threshold or advice is fabricated. |
| `FR-TX-009` | `TECHNICAL_VERIFIED_FOUNDATION` | Customer Standard values are immutable, versioned and live; Trial Actual and Approved Baseline creation remain Phase 7. |
| `FR-TX-010` | `TECHNICAL_VERIFIED` | Complete explicit Capacity Scenario inputs, formula version, provenance, successors and deterministic recomputation are runtime proven without hidden business constants. |
| `FR-TX-011` | `TECHNICAL_VERIFIED` | Part/day/month, assembly, bottleneck and gap outputs are server-derived, versioned and runtime proven after changed inputs. |
| `FR-TX-019` | `TECHNICAL_VERIFIED_FOUNDATION` | Customer Standard, Trial Actual and Approved Baseline are disjoint typed layers; copying Standard never becomes measured or approved truth. |
| `FR-TX-020` | `TECHNICAL_VERIFIED_FOUNDATION` | Exact rule-versioned comparison and all four textual states are implemented; production red semantics remain held by `DR-REC-002`. |

`implementation/REQUIREMENT_TRACEABILITY.csv` and its canonical reconciliation
generator/verifier are updated to these exact results.

## 3. Ordinary and controlled Gates

Exact-SHA ordinary CI `31280290398` passed checkpoint `4e04eb4` before the
final Site workflow. Final workflow `31280296684` retained the same exact SHA
and passed all three jobs:

- repository `93160709198`: `1,251/1,251` tracked Python tests, `768/768`
  frontend unit tests in `46/46` files, `332/332` non-visual E2E, statements
  coverage `80.35%`, zero-vulnerability package audits and current-tree
  Gitleaks PASS;
- i18n audit: `4,901` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- visual `93160709195`: fixed-Linux governed matrix `85/85` PASS; and
- controlled runtime `93160709186`: PASS, including pinned tools, disposable
  Site, two migrations, cumulative P5/P6 predecessors, fresh P6-05 runtime,
  cross-process replay, independent P6-05 disable/recovery and cleanup.

Runtime artifact `9028284028`, `p6-tooling-runtime-31280296684`, has GitHub
digest
`sha256:7efde76303c3cdee8a83e8ba3d28614213a62e1fb988cb7475e8507c196e978a`.
It records `result=PASS`, exact head SHA `4e04eb4`, Site `npi.localhost`,
database `npi_one_runtime`, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1` and cumulative scope
`p5-01-through-p6-05`.

Visual artifact `9028277547` has digest
`sha256:2947a003f67d49a69eb3044a55780ba1d0cdd4768d55ec51041bef7c2c996d0d`.
Gitleaks artifact `9028341579` has digest
`sha256:a85172692c3a604d4fe623dfb420af6f25bde6951a3c72d3eb0055583502558e`.

The fresh runtime summary retains two Tooling-defect revisions, two Customer
Standard profile revisions and two Capacity Scenario revisions. It proves
exact succession, action/evidence/blocking truth, absent Trial Actual and
Approved Baseline, deterministic successor recomputation, stable bottleneck
and gap, replay, stale conflict, rollback, IDOR denial, generic mutation denial
and route recovery without changing predecessor P6 routes.

## 4. Level 2 module and UI checks

- cumulative engineering-controls runtime-verifier regression: `145/145`
  PASS locally before dispatch;
- complete tracked Python regression in CI: `1,251/1,251` PASS;
- complete frontend unit suite: `46` files and `768/768` PASS;
- complete non-visual browser matrix: `332/332` PASS;
- governed fixed-Linux visual matrix: `85/85` PASS, including exact English,
  Simplified-Chinese and Traditional-Chinese P6-05 cases;
- direct three-language coverage: `4,901/4,901` source strings in both Chinese
  catalogs, with mixed-language scans PASS; and
- boundary, industrial UI, accessibility, TypeScript/build, package audits,
  additive migrations, shell syntax, reconciliation and `git diff --check`:
  PASS.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Defect/process/comparison/capacity domains and three guarded DocTypes | domain, metadata, contract, controller, additive-migration and controlled-Site suites |
| Repository, BFF, request security and route switch | repository/API suites plus controlled containment, replay, conflicts, rollback, audit and IDOR |
| OpenAPI, ownership and receipt values | closed-schema, exact-ownership and no-fake-Trial/ERP/IoT assertions |
| Data source, workspace, styles and catalogs | `768/768` unit, `332/332` browser, i18n/UI/boundary audits and `85/85` Linux visuals |
| Runtime verifier/workflow and disposable fixtures | `145/145` verifier regression, complete ordinary CI and exact-SHA controlled Gate |
| Trace/controller/evidence and reconciliation scripts | CSV uniqueness, generated-form reconciliation, YAML parse, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and recovery analysis

The product review covers `e38da24..4e04eb4`: `92` files across the bounded
audit, domain/metadata, repository/BFF, live workspace, reviewed Linux evidence,
runtime verifier and exact tests (`16,499` insertions, `95` deletions). Every
commit belongs to one planned checkpoint, evidence-only visual sync or serial
evidence-proved runtime repair. No unrelated user dirty or untracked file
appears in a task commit.

The controlled boundary exposed four fixture/verifier roots after ordinary CI
remained green:

1. `31278115296` proved the safety guard did not validate literal
   `Administrator`; `7f91a7c` binds the guard while retaining the synthetic
   System Manager actor used for real Project membership;
2. `31278714697` proved the applicability fixture selected a relationship from
   another Project; `42c4a0b` adds the exact Project predicate and behavior
   regression;
3. `31279399638` proved the IDOR fixture incorrectly used a System Manager and
   therefore bypassed Project membership; `ffaf4e7` reuses the existing
   non-privileged internal NPI API fixture user; and
4. `31280060255` proved management commands authorize System Manager before
   protected object resolution, so both missing and inaccessible command
   scopes correctly return the same `403 PERMISSION_DENIED`; `4e04eb4`
   verifies that order while the read path separately proves IDOR-safe `404`.

The final Site passed with every diagnostic activation closed. No Requirement,
public API, permission, Schema intent, ownership, transaction, idempotency,
audit, visual threshold or PASS criterion was weakened.

## 7. Security, migration, rollback and limitations

- Project authorization precedes protected Master reads; management commands
  require System Manager transport before exact Project/dependency resolution.
  The ordinary non-privileged query path remains IDOR-safe.
- Generic Desk create/write/delete, cross-Project/tenant references, stale
  successors, caller-computed capacity results, caller availability flags,
  raw URLs and actor-mismatched replay fail closed.
- Migration is additive/idempotent and the controlled Site passed it twice.
- Before retained use, task commits may be reverted. After retained rows,
  rollback disables only P6-05 routes/projections and uses a reviewed forward
  repair; it never deletes or rewrites a defect, profile, capacity scenario,
  audit, receipt or predecessor Tooling object.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not affect any job.
- Trial rounds/measurements/approved baselines, G5/G6 policy, production
  exception colors, ERPNext/IoT observations, calibration, health scoring and
  maintenance advice remain unavailable.

## 8. Decision and transition

P6-05 passes its Level 2 Task Gate. Standing transition authority activates
only the bounded P6-06 Requirement/domain/existing-capability audit for
`FR-TL-011..016`: immutable Tooling acceptance evidence and Mock/sandbox-ready
ERP asset request/projection conditions. Real ERPNext asset creation/update,
unique formal mapping confirmation, location/movement, maintenance, repair,
spares, inventory and cost execution remain Phase 8 and production ERPNext
must not be contacted.
