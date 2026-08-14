# P7-05 Level 2 Validation — Versioned NPI Readiness and Dominant Blockers

Recorded: `2026-08-14T07:01:43Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`418b3aab01c9aebbd0cd0001f58006de9c417f6f`

Primary requirements: `FR-NP-001` through `FR-NP-003` and `FR-NP-006`
through `FR-NP-013`.

## 1. Outcome

P7-05 delivers the frozen NPI-owned readiness slice:

- reusable immutable readiness-template versions with explicit Project-type,
  Customer and NPI-owned industry applicability, plus an independently frozen
  exact Project instance and linear successor history;
- exact category, item, owner, due-date, confirmation, evidence, source,
  applicability, blocking-level and Gate identities without latest-value
  substitution;
- exact same-Project Project, Work Item, released document/baseline, private
  clean File, Tooling capacity-scenario and retained Trial source resolution;
- identity-free `unavailable` truth for formal ERP material/specification,
  quality/NCR, Run-at-rate/production, HR and supplier providers;
- server-derived category and total scores with separately retained incomplete
  P0, failed mandatory quality and required-unavailable-source blockers whose
  dominance cannot be hidden by a high percentage or caller input;
- exact current P0 blockers and one readiness-revision dependency as read-only
  input to the independently governed Gate-review flow; and
- a dense English, Simplified-Chinese and Traditional-Chinese Project
  readiness workspace with immutable history and complete controlled states.

No P7-05 command decides, passes, closes or reopens a Gate; mutates a Work
Item, Project risk, Tooling lifecycle or source record; contacts production
ERPNext; or creates handover, release, external projection or print effects.

## 2. Requirement trace review

| Requirement | Level 2 disposition | Evidence boundary |
| --- | --- | --- |
| `FR-NP-001` | `TECHNICAL_VERIFIED` | Published reusable template versions and independently frozen exact Project instances are runtime proven. |
| `FR-NP-002` | `TECHNICAL_VERIFIED` | Exact category/item/owner/due/status/evidence/blocking/Gate truth and P0 Gate input are proven. |
| `FR-NP-003` | `TECHNICAL_VERIFIED_NPI_CONFIRMATION_FOUNDATION_FORMAL_ERP_MAPPING_HELD` | NPI confirmations and exact evidence are proven; formal ERP material/specification mapping remains held. |
| `FR-NP-006` | `TECHNICAL_VERIFIED_CONTROLLED_REPORT_FOUNDATION_FORMAL_ERP_QUALITY_HELD` | Controlled report and Trial quality evidence plus failed-result blocking are proven; formal ERP quality remains held. |
| `FR-NP-007` | `TECHNICAL_VERIFIED` | Industry deliverables and applicability are governed configuration rather than a global hard-coded automotive rule. |
| `FR-NP-008` | `TECHNICAL_VERIFIED_CAPACITY_SCENARIO_FOUNDATION_RUN_AT_RATE_ACTUAL_HELD` | Exact Tooling capacity-scenario evidence is proven; production Run-at-rate actual remains held. |
| `FR-NP-009` | `TECHNICAL_VERIFIED_TRIAL_ACTION_FOUNDATION_PRODUCTION_RECORD_HELD` | Exact Trial/action evidence and readiness effect are proven; the production small-batch record remains held. |
| `FR-NP-010` | `TECHNICAL_VERIFIED` | Exact released-document and baseline readiness checks are proven. |
| `FR-NP-011` | `TECHNICAL_VERIFIED_CONTROLLED_CONFIRMATION_FOUNDATION_FORMAL_HR_PROJECTION_HELD` | Controlled training/qualification confirmation is proven; formal HR projection remains held. |
| `FR-NP-012` | `TECHNICAL_VERIFIED_NPI_SUPPLIER_FOUNDATION_FORMAL_ERP_AND_RISK_MUTATION_HELD` | NPI supplier evidence, blocker and link foundation are proven; formal ERP supplier truth and automatic risk mutation remain held. |
| `FR-NP-013` | `TECHNICAL_VERIFIED` | Deterministic total/category scores, blocker count and blocker-dominant ready state are proven. |

No aggregate PASS removes or obscures the six scoped holds above.

## 3. Exact-SHA ordinary and controlled Gates

Ordinary pull-request CI `31777229867` passed exact SHA `418b3aa`:

- repository `94695121403`: complete repository verification and
  `1,744/1,744` tracked Python tests PASS;
- frontend `94695122158`: `56/56` files, `881/881` unit tests and `388/388`
  non-visual E2E tests PASS; generation, type, lint and production build are
  clean; `7,003` direct English sources have `100%` `zh`/`zh-TW` coverage;
  aggregate statement/branch/function/line coverage is
  `80.17%/80.16%/82.78%/82.82%`, with zero vulnerabilities;
- visual `94695121693`: the complete `109/109` fixed-Linux governed matrix
  PASS; artifact `9210406077` has upload digest
  `sha256:7bd82310028eace5f7406592b84aca8a3d93f3c1e61e36a82530740e8037fcd6`;
  and
- secret scan `94695121480`: the exact `74`-path task range, current tree and
  complete pull-request branch history PASS with no leaks; artifact
  `9210334347` has upload digest
  `sha256:f6d4df2b88f0b6aa68e0682c80c44f69f6bc9145b18ad76daa3daa44d02a1dc1`.

Optimized exact-SHA controlled Gate `31777985302` then passed the same SHA:

- controlled preflight `94697368669` verified the exact repository, event,
  head SHA and four successful required jobs in ordinary run `31777229867`;
- prior-Gate attestation artifact `9210604110`,
  `prior-gate-attestation-31777985302`, has upload digest
  `sha256:5a58b6dc50b9731e9578d1d33356c3102094121d4b7825d851ca022e196defb0`;
- cumulative runtime `94697448103` passed scope `p5-01-through-p7-05` on
  pinned Frappe commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`;
- runtime artifact `9210730456`, `p7-trial-runtime-31777985302`, records
  `result=PASS`, the exact SHA, Level 2 mode and scope, with upload digest
  `sha256:e018a02bc3005670879822c3ca2ec348136b4f36db50feb7ac7398c395ba4372`;
  and
- disposable MariaDB/Redis containers, volumes and network were removed by
  the successful always-run cleanup step.

Repeated repository/frontend/visual/secret jobs were skipped by the
controlled dispatch only after the fail-closed exact-SHA attestation passed.
This is the P7-05 Level 2 Task Gate. Phase 7, PR and release boundaries still
require the complete Level 3 Gate and `release-gate` review.

## 4. Controlled truth and negative matrix

The cumulative disposable Site proves template create/edit/publish and
immutability, independent Project initialization, exact internal/quality/
external-source successor revisions, score reconstruction and blocker-
dominant Gate input. It also proves:

- sixteen exact internal source kinds and five identity-free offline external
  kinds, including canonical retained Capacity and current Trial-reference
  preparation without unrelated-source substitution;
- same-process and cross-process replay, altered-payload conflict, stale/fork
  denial and transaction rollback without receipt, audit or response drift;
- Project-first guest/external/unrelated/cross-Project IDOR denial and guarded
  generic update/delete denial;
- high score cannot hide an incomplete P0, failed mandatory result or required
  unavailable source, and tampered frozen assignments/evaluations fail closed;
- readiness revision drift changes only read-only Gate input while preserving
  every Gate cycle, decision, event, dependency and authority boundary;
- independent route disable/recovery, additive migrations, clean-log
  sentinel/redaction checks, zero ERP/network/Outbox traffic and zero
  downstream Gate/Work/Tooling/risk mutation; and
- exact retained cardinalities plus complete disposable-resource cleanup.

## 5. Task Diff Review and diagnostic runs

The bounded P7-05 range is
`81b720487cface6ca78a9e77724223e61c766871..418b3aab01c9aebbd0cd0001f58006de9c417f6f`:
`74` files, `28,511` insertions and `105` deletions across `15` task commits.
The exact-SHA current-task guard accepted all `74` committed paths. They belong
to the frozen four checkpoints, direct evidence, generated trilingual
catalogs, reviewed fixed-Linux visuals or evidence-proved controlled-runtime
repairs. User-owned dirty development files, Darwin snapshots and local
Playwright reports are absent from the committed range.

Earlier controlled runs `31773714266` and `31775596713` are diagnostic
failures, not PASS evidence. They respectively exposed retained Capacity
provenance and persisted Project decoding mismatches. Each bounded repair kept
the same Requirement, API, permission, ownership, transaction, idempotency,
audit and PASS rules, ran affected tests, and obtained a new exact-SHA ordinary
CI before redispatch. No test, governed visual, threshold, matrix or Gate
criterion was removed or weakened.

## 6. Security, migration, rollback and limitations

- Authentication precedes parsing; Project authority precedes every protected
  secondary source; mutations enforce CSRF, internal authority, exact hashes,
  predecessor state and actor-bound idempotency.
- Published templates, Project-instance history, command receipts and audits
  are append-only. Unknown fields, altered replay, stale sources, corrupt
  provenance and unsafe Files fail closed.
- Additive/idempotent migrations and the complete cumulative runtime passed on
  a fresh disposable Site.
- Before retained data, rollback may disable the independent P7-05 route,
  workspace and Gate-input switches. After retained history exists, rollback
  is switch disable plus reviewed forward repair; exact history is never
  deleted, edited or renumbered.
- Formal ERP material, quality, production, HR and supplier truth; production
  Run-at-rate/small-batch records; automatic Gate/Work/Tooling/risk mutation;
  handover, release, external projection and production print remain explicit
  scoped holds, not global Hard Blockers.

## 7. Decision and transition

P7-05 passes its Level 2 Task Gate with the eleven truthful per-row
dispositions in section 2. Standing continuous-delivery authority activates
only the bounded P7-06 Requirement/domain/existing-capability audit for
`FR-NP-014` and `FR-NP-015`. Product implementation may begin only after that
audit freezes formal handover and observation-period ownership, immutable
snapshots, acknowledgements, Gate separation, tests and rollback in a
machine-readable task plan. Level 3 remains reserved for the applicable Phase,
PR or release boundary.
