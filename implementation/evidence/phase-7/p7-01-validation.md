# P7-01 Level 2 Validation — Trial Plan and Round Foundation

Recorded: `2026-08-10T11:04:13Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`78efa3ec5c584928f510e4b095ead5a36f2fb376`

Primary requirement: `FR-TR-001`

Truthful disposition:
`TECHNICAL_VERIFIED_FOUNDATION_RESOURCE_RESERVATION_HELD`

## 1. Outcome

P7-01 delivers the frozen minimum complete vertical slice for Trial planning:

- one stable Trial Plan identity with immutable successor revisions and exact
  predecessor hashes;
- one distinct planned Trial Round bound to an exact Plan revision, without
  collapsing Plan and Round identities;
- Project-first authorization and exact Tooling Master, current Project member
  and optional controlled-document containment;
- planned objective, purpose, UTC window, proposed machine/material resources,
  responsible members, sample quantity and measurement-plan intent;
- server-owned resource status `unavailable`, with no false availability or
  booking success;
- governed Domain Work Item generation with immutable Trial work links rather
  than a second task lifecycle;
- actor-bound idempotency, optimistic conflict, one-transaction append-only
  history/audit, independent route control and fail-closed generic mutations;
  and
- a dense industrial English, Simplified-Chinese and Traditional-Chinese
  Project Trial workspace with truthful loading, empty, read-only, permission,
  validation, conflict, processing, success and later-capability-held states.

P7-01 does not lock actual Round inputs, create sample/cavity/evidence truth,
record defects or conclusions, approve a Trial, mutate a Gate or Tooling
lifecycle, contact ERPNext, reserve a machine/person/material, publish a
Released Trial Summary or install production print policy. Those authorities
remain assigned to later Phase 7/8 tasks and approved decisions.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TR-001` | `TECHNICAL_VERIFIED_FOUNDATION_RESOURCE_RESERVATION_HELD` | Plan objectives, proposed resources, dates, members, sample quantity, measurement intent, immutable revision/Round truth and task generation are live and runtime proven. Production availability and reservation remain explicitly unavailable because no approved policy, calendar reader or reservation adapter exists. |

This disposition is intentionally narrower than complete functional
acceptance. It neither converts proposed resource references into reservations
nor treats task generation as resource booking.

## 3. Exact-SHA ordinary, visual and controlled Gates

Final unchanged workflow `31380834335` passed exact SHA `78efa3e`:

- repository `93430635765`: `1,485/1,485` tracked Python tests, `822/822`
  frontend unit tests in `54/54` files, `359/359` non-visual E2E, statements
  `80.10%`, clean generation/type/lint/build, zero-vulnerability complete and
  production audits, and current-tree Gitleaks with no leaks;
- i18n audit: `6,001` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- visual `93430635728`: fixed-Linux governed matrix `97/97` PASS, including the
  direct English, Simplified-Chinese and Traditional-Chinese P7-01 cases; and
- cumulative controlled Site `93430635851`: PASS through
  `p5-01-through-p7-01` on pinned Frappe commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`.

Visual artifact `9059903977` has digest
`sha256:887a23d8d14717899475638cf85f2d3106adfd5c4cd7d8f103a8613cab146b9a`.
Gitleaks artifact `9060085481` has digest
`sha256:a68a427ff280aeed61bd901955b12a57c57f6fabb187b4456e7fe296d313c71c`.
Runtime artifact `9059935812`, `p7-trial-runtime-31380834335`, has digest
`sha256:b7e00cbbd0622961517b22ea690f372aafb7748f81542cb6c67fd7090a74632f`.
It records `result=PASS`, exact head SHA, fixed disposable Site/database,
runtime marker `npi-one-local-runtime-disposable-v1`, scope
`p5-01-through-p7-01` and predecessor scope `p5-01-through-p6-08`.

The branch-history Gitleaks step is correctly skipped for a manual
`workflow_dispatch`; current-tree Gitleaks passed. Earlier pull-request runs
already exercise the separate branch-history lane, and Delivery Pipeline
Optimization must retain both trigger-appropriate secret-scan boundaries.

## 4. Controlled truth and negative matrix

The disposable Site summary records five guarded Trial DocTypes, two immutable
Plan revisions, one distinct planned Round, one governed action link,
`resourceReservation=unavailable`, synchronized metadata, verified rollback,
cross-process replay readiness and zero integration traffic. The cumulative
proof also covers:

- initial Plan create and exact successor revision without rewriting history;
- Round creation against the exact retained Plan revision and immutable
  generated Work Item linkage;
- same-process replay, same-key/different-payload conflict and fresh-process
  replay without row, receipt, audit or response drift;
- guest/external/unrelated/cross-Project/object-substitution denial and
  authorization before secondary Trial/Tooling/member/document resolution;
- generic update/delete denial, transaction rollback and retained hashes;
- independent Trial route disable/recovery while predecessor routes remain
  available;
- two migrations, raw-log sentinel/redaction checks, no network/ERP contact,
  no Outbox/Inbox growth and disposable cleanup; and
- exact replay after route recovery.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Plan/Revision/Round/Work-link domains | immutable successors, exact hashes, planned-only lifecycle, closed resources, task links and bounds |
| OpenAPI/ownership/DocTypes/controllers | Project-first schemas, five guarded additive objects, direct translations, no generic mutation or external authority |
| Repository/BFF/routes | authorization order, containment, CSRF, replay/conflict/rollback/IDOR, transaction/audit/seal order and independent switch |
| Trial data source/workspace/Shell/i18n | `822/822` unit, `359/359` E2E, direct trilingual audit and `97/97` governed visuals |
| Runtime verifier/workflow | focused Trial verifier regressions, full repository Gate, two migrations and cumulative disposable Site |
| Trace/controller/evidence | 282-row uniqueness/evidence reconciliation, YAML parse, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and serial runtime repairs

The bounded review covers `4865e0a..78efa3e`: `150` files, `15,246`
insertions and `238` deletions across `17` task commits. Every commit belongs to
the frozen four-checkpoint P7-01 slice, a reviewed fixed-Linux baseline update,
the user-ordered post-P7-01 pipeline hold, or an evidence-proved controlled-
runtime repair. No user-owned dirty, Darwin, local-report or untracked file is
included.

The controlled boundary reached persistence behavior that unit fakes had not
previously represented. Repairs remained serial and exact:

1. a response-neutral diagnostic identified first Plan reconstruction at
   `planSnapshot`;
2. repository reads now normalize Frappe JSON Text values before domain
   reconstruction, and the fake persistence seam serializes snapshots like
   Frappe rather than hiding the boundary; and
3. the revision verifier removes server-owned `toolingMasterGlobalId` from the
   closed successor payload after the real handler correctly rejected it.

Failed runs `31377825847`, `31379615766` and `31380269675` remain diagnostic
evidence only. Each advanced the same controlled path, previous roots did not
recur, and final run `31380834335` passed with only safe structural diagnostics
retained. No Requirement, route, role, permission, Schema, transaction,
idempotency, audit, visual matrix, threshold or PASS rule was weakened.

## 7. Security, migration, rollback and limitations

- Project authority precedes Plan, Round, Tooling, member, document and Work
  Item resolution; actor, CSRF, exact predecessor and idempotency are
  revalidated for every command.
- Machine/material references are bounded proposals and always expose booking
  truth as unavailable. No caller field can claim availability or reservation.
- Generic Desk writes/deletes, unknown fields, cross-Project identities,
  altered replays and stale predecessors fail closed.
- Migration is additive/idempotent and the controlled Site passed two
  migrations before the cumulative lifecycle.
- Before retained use, task commits may be reverted. After retained Plan,
  Round, link, receipt or audit history, rollback disables the independent
  P7-01 routes/workspace and uses a reviewed forward repair; it does not delete
  or rewrite immutable history.
- GitHub runner warnings show four actions targeting deprecated Node.js 20 and
  being forced onto Node.js 24. They did not fail P7-01, but they are an
  explicit input to the separately ordered Delivery Pipeline Optimization
  task.

## 8. Decision and ordered transition

P7-01 passes its Level 2 Task Gate. `FR-TR-001` advances only to
`TECHNICAL_VERIFIED_FOUNDATION_RESOURCE_RESERVATION_HELD` with this complete
evidence set.

Per the user's `2026-08-10` directive, P7-02 and every later Phase 7 product
task remain paused. The next active atomic task is the independent
`Delivery Pipeline Optimization` audit and implementation. It must preserve
all product/Gate invariants and pass a complete Level 3 Gate before P7-02 may
resume.
