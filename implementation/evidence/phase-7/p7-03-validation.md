# P7-03 Level 2 Validation — Cavity Defects, Actions and Verification

Recorded: `2026-08-11T05:06:27Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`102de35b9cff4b7303e0e2f17d2bbb146795fc3d`

Primary requirements: `FR-TR-004` and `FR-TR-009`.

Truthful disposition: `TECHNICAL_VERIFIED`.

## 1. Outcome

P7-03 delivers the frozen minimum complete vertical slice for Trial cavity
quality collaboration:

- immutable cavity-result revisions bound to one exact running Round, input
  lock, Sample Batch, Tooling Revision, physical Set and defined cavity;
- one stable NPI defect identity across the P6 Tooling and P7 Trial immutable
  stores, with an exact transactional cross-store tip and no parallel copy;
- append-only observations with category, cavity/location, severity, evidence,
  root cause, containment, corrective/preventive action, responsible Project
  member and exact target Round;
- independent append-only verification attempts against exact actions,
  verification Rounds, cavity results and clean evidence, followed only by an
  explicit defect close or reopen successor;
- server-derived exact Round/cavity/category/severity Pareto counts without
  double-counting a successor revision;
- Project-first reads and commands, actor-bound replay, optimistic conflict,
  one transaction, append-only audit and independent route control; and
- a dense industrial English, Simplified-Chinese and Traditional-Chinese
  quality workspace with exact cavity filtering and complete honest states.

No command creates an ERPNext NCR or Quality Inspection, mutates a Gate or
Tooling lifecycle, closes a Domain Work Item automatically, submits a Trial
conclusion or claims approval, readiness, release or external projection.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
| --- | --- | --- |
| `FR-TR-004` | `TECHNICAL_VERIFIED` | Exact category/location/cavity/severity/evidence/root-cause/responsibility/action/target-Round/verification lineage and server-derived Pareto are live and runtime proven. |
| `FR-TR-009` | `TECHNICAL_VERIFIED` | Exact physical-cavity dimensional/result and defect trace, family/multi-cavity filtering and cross-Round continuation are live and runtime proven. |

The disposition covers NPI-owned collaboration truth only. Formal ERP quality,
NCR, Gate and Tooling lifecycle authority remain separate scoped holds.

## 3. Exact-SHA ordinary and controlled Gates

Ordinary pull-request CI `31459395711` passed exact SHA `102de35`:

- repository `93679724914`: `1,565/1,565` tracked Python tests and complete
  repository verification PASS;
- frontend `93679724949`: `54/54` files, `843/843` unit tests,
  `371/371` non-visual E2E, `6,534` direct trilingual sources, statements
  `80.02%`, zero vulnerabilities and clean generation/type/lint/build checks;
- visual `93679724973`: `103/103` fixed-Linux governed cases PASS;
- secret scan `93679724995`: current-task guard plus current-tree and complete
  branch-history Gitleaks PASS with no leaks;
- visual artifact `9089292279`, upload digest
  `sha256:f533b5bb3d9ac8f8119b8eea027c5b7e4389d326d2929785e1309d4887a39d75`;
  and
- Gitleaks artifact `9089229151`, upload digest
  `sha256:678d5ba022312c030f8f38641d7cdca1023644a4d425a03f85b8f81ff18baad4`.

Optimized exact-SHA controlled Gate `31459974578` then passed the same SHA:

- controlled preflight `93681378431` verified the exact successful prior
  pull-request run, repository, event, SHA and required four jobs;
- cumulative runtime `93681432172` passed in `4m49s` at scope
  `p5-01-through-p7-03` on pinned Frappe commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`;
- runtime artifact `9089512248`, `p7-trial-runtime-31459974578`, contains
  `result=PASS`, upload digest
  `sha256:449dfa0fb3df3f01105dfacdfa890d94e664dfc5eecff73fb2905de499ae9a3a`
  and local content digest
  `sha256:7455a04e3e9f72b55757415965519477c878e1db82649d324f8e15914fc54291`;
  and
- prior-Gate attestation artifact `9089425791` binds successful run
  `31459395711`, with upload digest
  `sha256:c9c8e93b5201bf993be9864cec37ec0480abe41484e7df9b376ddc4a0816b237`
  and local content digest
  `sha256:e17c29eb7263a9713e5fd9a6c08b5157f1cb7e2d2af3aad2c65f737c70bd2bed`.

The controlled dispatch intentionally skipped repeated repository/frontend/
visual/secret jobs only after its fail-closed exact-SHA preflight accepted the
complete prior PR Gate. This is the P7-03 Level 2 Task Gate; the Phase 7 final
Level 3 Gate remains mandatory at the Phase boundary.

## 4. Controlled truth and negative matrix

The disposable Site proves cavity-result succession, a new Trial defect, a
continued P6 Tooling defect, exact cross-Round action target, failed and passed
independent verification, explicit close/reopen and exact Pareto truth. It also
proves:

- retained cross-Round evidence is validated against its immutable predecessor
  while every newly supplied reference remains bound to the current Round and
  Sample context;
- pure dates and datetimes are normalized only at the JSON receipt boundary,
  preserving typed domain validation and deterministic replay;
- same-process replay, same-key/different-payload conflict and cross-process
  replay without row, receipt, audit or response drift;
- one exact cross-store defect tip, fork/stale-predecessor denial and rollback
  without partial P6/P7 history;
- guest/external/unrelated/cross-Project/member/Round/cavity/File substitution
  denial and authorization before secondary object resolution;
- generic update/delete denial, additive migrations and immutable history;
- independent P7-03 route disable/recovery while predecessor Trial and Tooling
  routes remain available;
- raw-log sentinel/redaction checks, zero ERP/network/Outbox traffic and
  disposable cleanup; and
- explicit unavailable formal NCR, Quality Inspection, Gate and Tooling
  lifecycle effects without optimistic success.

## 5. Task Diff Review

The bounded P7-03 review range is
`135d083bcb4e620c571fa3d4737cae54e7a8be2a..102de35b9cff4b7303e0e2f17d2bbb146795fc3d`:
`70` files, `16,032` insertions and `491` deletions across `20` task commits.
Every committed path is inside the frozen P7-03 manifest and belongs to the
four checkpoints, direct evidence, generated trilingual catalogs, reviewed
Linux visuals or an evidence-proved runtime repair. No user-owned dirty file,
Darwin snapshot, local report or untracked development prerequisite is in the
range.

The serial controlled-runtime failures advanced to later boundaries and did
not recur after repair. The final repairs normalize typed date values only for
receipts and preserve predecessor-bound evidence across Rounds while keeping
new evidence current-Round-bound. No Requirement, public API, permission,
Schema ownership, transaction, idempotency, audit, test, visual threshold or
PASS criterion was weakened.

## 6. Security, migration, rollback and limitations

- Project authority precedes Round, input, Sample, Tooling, Set, cavity,
  member, defect, action, verification and File resolution; actor, CSRF,
  predecessor/hash and idempotency are checked for every command.
- Generic Desk writes/deletes, unknown fields, altered replays, stale tips,
  unsafe Files and cross-context identities fail closed.
- Migration is additive/idempotent and the controlled Site passed cumulative
  migrations before and after the complete quality lifecycle.
- After retained history, rollback disables independent P7-03 routes and the
  workspace and uses reviewed forward repair; it never deletes, rewrites or
  forks immutable cavity, defect, action, verification, receipt or audit truth.
- Formal ERPNext quality/NCR, Gate/Tooling lifecycle, Trial conclusion,
  approval, readiness, release, external projection and production print
  remain scoped holds, not global Hard Blockers.

## 7. Decision and transition

P7-03 passes its Level 2 Task Gate. `FR-TR-004` and `FR-TR-009` advance only
to `TECHNICAL_VERIFIED` for the NPI-owned boundary above. Standing continuous-
delivery authority activates P7-04 only at the bounded Requirement/domain/
existing-capability audit. Product implementation may begin only after that
audit freezes the exact Round comparison, immutable conclusion, formal-quality
unavailable/read-only projection, controlled approval references, summary
input, tests and rollback in a machine-readable task plan.
