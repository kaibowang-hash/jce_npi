# P4-04 Implementation Boundary — Review, Decision, Snapshot, and Reopen

Status: **IN PROGRESS — live implementation checkpoint retained; Task Gate not passed**

Recorded: 2026-07-24

Starting checkpoint: `0fd4762a01fd10fe6851df07ead1c5e4e7a42473`

Atomic task: `P4-04 — Review, decision, snapshot, and reopen`

Requirement allocation: `FR-SG-003`, `FR-SG-005`, `FR-SG-006`,
`FR-SG-007`, with the current Phase 4 contribution to `FR-CO-006`

## 0. Bounded takeover/thread-migration checkpoint

The bounded takeover accepted the current domain/implementation foundation as
`DOMAIN_FOUNDATION_ACCEPTED`; this is not a P4-04 Task `PASS`. The final repair
batch preserves the Gate's latest immutable decision lineage across successor
cycles, closes historical event and exception schema-version forms without
guessing missing exact references, schedules File-delete dependency evaluation
after commit, and keeps transport admission distinct from business authority.

Current affected evidence passes 123 Gate Review Python tests, 46 shared
backend boundary tests, 11 Gate Evidence/Gate Shell tests, 116 frontend tests,
72 current Gate browser cases, 23 exact Review Room visuals, and complete
direct `zh`/`zh-TW` coverage for 1742 literal English sources. P4-03 reconciled
to `EVIDENCE_CONFIRMED` without repeating its full Level 3.

Migration/idempotence, the final focused and complete runtime, coverage/build/
audit, Task Diff/security/trace review, Level 2, and the single triggered Level
3 remain pending. The current focused runtime did not execute because the
stopped controlled MariaDB container could not be restored past a stale Docker
OCI task. Resume from
`implementation/evidence/phase-4/p4-04-takeover-review.md` and
`implementation/NEXT_ACTION.md`; do not start P4-05.

## 0.1 Historical final CLI-to-Cloud handoff checkpoint

The final recoverable handoff retains the current P4-04 implementation:
the review/exception/decision/reopen domain, versioned synthetic policy,
controlled immutable history, live Frappe repository, sealed actor-bound
idempotency receipts, fixed aggregate locks, strict BFF/OpenAPI surface,
dependency hooks, focused live runtime, and a live trilingual industrial
Review Room. Directly affected Level 1 tests, receipt/requires-review E2E, and
three normal-state exact visual baselines pass.

The implementation remains an unfinished atomic task, not an accepted vertical
slice. Its complete state-specific E2E/visual matrix, module coverage/build/
audit lane, migration/runtime compatibility reruns, Level 2 Task Gate, and the
contract/Schema/authentication/permission/shared-catalog-triggered Level 3
remain pending. P4-04 and Phase 4 stay `IN_PROGRESS`; P4-05 is not activated.

The generated plan originally overreached by requiring automatic creation of
an impact Domain WorkItem. Authoritative `FR-SG-007` requires invalidation and
re-review. P4-05 owns work/lifecycle projection. P4-04 therefore records exact
dependency events, creates a successor cycle, denies downstream use, and keeps
the legacy action reference nullable without creating a new DWI.

The Frappe-compatible catalog now contains `1740` literal English sources with
complete direct `zh` and `zh-TW` coverage. No fallback-English acceptance is
claimed.

Resume only from `p4-04-cloud-checkpoint.md` and the durable recovery files.
Do not repeat the committed P4-03 Full Release Gate or the passing P4-04 Level
1 lanes merely for handoff. Complete the missing P4-04 acceptance matrix, then
run Level 2 and one triggered Level 3 boundary.

## 1. Repository facts

- P4-03 provides an exact immutable Gate Template reference, a one-time frozen
  Project requirement snapshot, append-only exact WBS/private File Revision
  evidence, live scan truth, and a strict URL-free evidence workspace.
- Requirement owners/reviewers, Project RACI, the Project owner, and System
  Manager administration do not by themselves confer Gate approval authority.
- At task start, the OpenAPI `/review` and `:decide` definitions were Phase 3
  placeholders. This checkpoint replaces them with closed P4-04 contracts and
  a strict live repository/API protocol with focused runtime evidence.
- The accepted live Gate route now renders the P4-04 Review Room; `/demo/...`
  remains an explicit in-memory prototype and is not runtime evidence.
- Project-scoped Domain Work Items already carry exact Project, stage, policy,
  owner, blocking, terminal-state, optimistic-version, and audit identity.
  They can therefore serve as Gate blockers. P4-04 does not create another
  work item for dependency invalidation; P4-05 owns work projection.
- Production approval, segregation, waiver, deviation, expiry, dependency,
  downstream-action, and disabled-member policies have not been supplied.
  They are scoped Class-B holds, not authority to invent rules.

## 2. Selected minimum vertical slice

P4-04 will implement:

> publish an exact synthetic Gate Review Policy version → explicitly bind
> active internal Project members to its authority slots → start a frozen
> review cycle → complete parallel, sequential, and condition-selected review
> steps → enforce P0/evidence/scan/blocker and exception rules → create a
> server-built immutable decision snapshot → manually reopen or automatically
> invalidate into a new cycle while preserving the prior decision and denying
> guarded downstream use until re-review

No policy is installed by migration or treated as a production default.
Synthetic policies exist only in tests and disposable runtime evidence.

## 3. Versioned review policy

An independent `GateReviewPolicy` aggregate will have a stable UUID/code root
and contiguous immutable published versions. A canonical published snapshot
contains:

- `schemaVersion`;
- exact applicable Gate Template version/hash references;
- bounded review steps;
- an explicit final-decision authority slot;
- an explicit reopen authority slot;
- bounded exception rules; and
- allowlisted dependency evaluators.

Review steps use an allowlisted data-only model:

- each step has a stable key, positive sequence, and assignment slot;
- equal sequence means parallel sign-off;
- a later sequence cannot act until every selected prior-sequence step
  approves;
- activation is either `always` or an allowlisted condition over the frozen
  requirement snapshot, initially `requirement_priority_present`;
- unknown condition kinds, properties, operators, or values fail publication
  and evaluation; and
- no script, expression engine, arbitrary field path, RACI lookup, role lookup,
  or substitution inference is permitted.

At cycle start, the caller explicitly binds every policy authority slot to one
same-Project enabled internal member. The server freezes member UUID, user ID,
display name, policy slot, policy version/hash, and selection result. New
assignments fail closed when membership or internal-user validity is
unavailable. Historical records remain readable if a member later changes.

The synthetic acceptance policy will prove:

1. two technical steps at the same sequence are parallel;
2. a P0-selected quality step is conditionally active at the next sequence;
3. a final decision authority is separate from every review assignment; and
4. reopen and exception authorities are explicit slots.

## 4. Review, exception, and decision invariants

Every submitted review is append-only and records:

- Gate, Project, tenant, cycle, policy version/hash, and review-step identity;
- exact assigned member and authenticated actor;
- outcome, complete opinion, occurrence time, reviewed input hash, and cycle
  object version; and
- audit and trace identity.

A reviewer may act only on their selected current-sequence step. Completing a
requirement review assignment never grants final decision, exception approval,
reopen, administration, or Project access.

Normal `pass` requires all of the following at decision time:

- every selected review step approved;
- no missing required P0 evidence;
- no pending, failed, infected, unavailable, or drifted private-file evidence;
- no same-Project, same-Gate, non-terminal blocking Domain Work Item;
- no input change since the reviewed snapshot; and
- the exact final-decision authority actor.

`reject` creates an immutable decision snapshot and never deletes evidence or
reviews.

`conditional_pass` is denied unless the exact published policy explicitly
defines every used exception kind, eligible requirement key, approval
authority slot, maximum validity, required closure action, and requester/
approver separation. Each exception records kind, requirement, reason, risk,
requester, exact approver, expiry, same-Project non-terminal `action`, opinion,
versions, and timestamps. P0 evidence gaps and unsafe/unavailable file content
are never exception-eligible in the synthetic policy.

Unknown, pending, rejected, expired, self-approved, cross-Project,
cross-tenant, incomplete, or policy-ineligible exceptions cannot support a
conditional pass. A readiness score or review count cannot override any
blocker.

The decision request supplies expected Gate/cycle versions and the last
server-provided input hash only as stale-input preconditions. The server
re-resolves all exact evidence and live scan truth, blockers, reviews,
exceptions, policy, and dependencies and then constructs and hashes the
immutable decision snapshot. The caller cannot supply snapshot content or
claim a successful decision.

## 5. Persistence boundary

The additive persistence model is:

- `NPI Gate Review Policy` — stable administrative root;
- `NPI Gate Review Policy Version` — immutable canonical published version;
- `NPI Gate Review Cycle` — exact policy/assignment/input snapshot, sequence,
  trigger, prior decision reference, state, and optimistic version;
- `NPI Gate Review Record` — one append-only opinion per selected assignment
  and cycle;
- `NPI Gate Review Exception` — exact immutable request fields plus a
  controlled one-way approval/rejection result and optimistic version;
- `NPI Gate Review Event` — append-only exception-decision, reopen, and
  invalidation history with canonical payload/hash; and
- `NPI Gate Decision Snapshot` — one immutable server-built decision snapshot
  per completed cycle.

`NPI Gate Shell` receives only controlled review state, current cycle, and
latest decision references. Its P4-03 template/requirement snapshots remain
immutable. All review writes use a narrow command flag, Gate/Project row locks,
expected versions, actor-bound idempotency, audit, and transaction rollback.
A dedicated non-Desk transport role grants only the framework create/write
capabilities needed by the command path; its controller flags and exact policy
assignment still deny generic CRUD and never confer approval authority.
Generic create/update/delete/rename of controlled history remains denied.

## 6. Reopen and dependency invalidation

Manual reopen:

- requires the exact policy reopen authority and a complete reason;
- references the prior immutable decision snapshot;
- appends a reopen event;
- creates cycle `n + 1` with a newly frozen current input snapshot;
- resets review progress without copying approvals; and
- never changes the old decision, reviews, exceptions, or snapshot.

The initial allowlisted dependency evaluator is `gate_input_snapshot`. It
re-resolves P4-03 exact WBS/File identities, versions, hashes, live file
identity/scan state, and current Gate blockers. It is invoked after controlled
evidence attachment and from narrow WBS/File source-change hooks; the browser
cannot submit or forge dependency deltas. Unknown dependency types fail
closed.

When a decided cycle's exact input changes, one transaction:

1. preserves the old decision and snapshot;
2. appends an exact old/new hash invalidation event;
3. creates review cycle `n + 1` with trigger `dependency_change`;
4. marks the Gate as requiring review; and
5. denies downstream use until a new current decision exists.

Repeated evaluation of the same change is idempotent and creates no duplicate
cycle or event. It does not require or create a Domain WorkItem. The event and
workspace retain a nullable legacy action reference so historical data created
under an older contract remains readable.

A reusable server-side downstream guard accepts only a current non-invalidated
decision snapshot. P4-04 tests the guard and exposes its result in the Gate
workspace. P4-05 may project invalidation into live My Work, but P4-04 does not
implement that work projection, notification, activity feed, or escalation.

## 7. BFF/API boundary

The strict same-origin surface will retain P4-03 `/evidence` and replace the
prototype review contract with closed schemas for:

- `GET /projects/{projectId}/gates/{gateId}/review`;
- `POST /projects/{projectId}/gates/{gateId}:start-review`;
- `POST /projects/{projectId}/gates/{gateId}/review-cycles/{cycleId}/reviews`;
- `POST /projects/{projectId}/gates/{gateId}/review-cycles/{cycleId}/exceptions`;
- `POST /projects/{projectId}/gates/{gateId}/review-cycles/{cycleId}/exceptions/{exceptionId}:decide`;
- `POST /projects/{projectId}/gates/{gateId}:decide`;
- `POST /projects/{projectId}/gates/{gateId}:reopen`.

Every command has authentication, Frappe CSRF, request/trace ID, actor-bound
idempotency, exact expected versions, closed field allowlists, explicit
permission metadata, documented 4xx/5xx responses, and a Gate-root transaction.
Authorization occurs before protected Gate/cycle/event/source resolution.
Unavailable, unauthorized, cross-tenant, and mismatched Project/Gate identities
use the same 404 representation.

## 8. Live industrial review room

The existing live Gate URL remains:

`/projects/{projectUuid}/gates/{gateUuid}`

It will render a strict review workspace response that embeds the P4-03
evidence model rather than loading two independently timed versions:

- left: frozen requirements/evidence plus selected parallel/sequential review
  steps;
- center: exact selected evidence, blockers, changed dependencies, and prior
  immutable decision detail; and
- right docked inspector: current assignment, allowed action, exception
  status, cycle/version, downstream guard, and decision history.

The server, not the UI, determines `canReview`, `canDecide`,
`canRequestException`, `canApproveException`, and `canReopen`. The object header
shows at most one visual primary action for the current actor/state. High-risk
decision, exception, and reopen commands use a focused review step with impact,
versions, irreversibility, failure handling, and audit summary. No optimistic
success is shown.

The accepted live path covers loading, no active cycle, selected review,
sequential wait, P0/scan/blocker/input-change denial, read-only, decided,
reopened/invalidated, conflict, validation, no-permission/not-found,
retryable/final error, and processing prevention. The `/demo/...` prototype
remains explicitly separate.

All new user-visible source copy is literal English through `t()` or Frappe
`_()`, with complete direct `zh` and `zh-TW` catalogs. Codes are exhaustively
mapped to literal copy. User names, opinions, filenames, identifiers, and other
business data remain escaped data, not translation keys.

## 9. Security, migration, and recovery

- Guest and external principals cannot review, decide, approve exceptions,
  reopen, or administer, even if their ID equals the
  Project owner or an old assignment.
- The dedicated `NPI API User` transport role has no Desk access and is not an
  approval role. It only lets an already-authorized BFF command pass Frappe's
  framework write check; direct DocType writes still fail at the controller.
- Project view authorization does not imply an approval action.
- Exact assigned authority and current enabled internal membership are checked
  for every action; System Manager has no approval bypass unless explicitly
  assigned by the exact policy snapshot.
- P4-03 File evidence remains private and URL-free; decision-time reads repeat
  the live identity/privacy/scan checks.
- New DocTypes and Gate fields are additive and nullable/defaulted for existing
  P4-01/P4-03 records. Legacy Gates remain `not_started` and cannot review
  without an explicit exact policy/cycle.
- Before retained P4-04 history exists, the prior checkpoint may be restored.
  After retained review/decision history exists, rollback disables new routes,
  keeps additive tables and immutable records, denies downstream use, and
  deploys a reviewed forward fix. It never deletes decisions or approvals.
- No production ERPNext endpoint, credential, database, scanner, DMS, default
  policy, or customer data is used.

## 10. Changed-files → affected-tests plan

| Planned surface | Direct tests |
|---|---|
| Review policy domain and controllers | policy unit tests; publication/immutability/sequence/condition/controller tests |
| Review cycle, events, decision snapshot, Gate state controllers | domain/state tests; metadata/history/generic-CRUD guards |
| Frappe review repository and evidence invalidation hook | repository tests; Project/tenant/authority/P0/scan/blocker/exception/reopen/invalidation/idempotency/rollback tests |
| Strict review API, BFF routes, OpenAPI, and ownership | API/controller tests; contract/ownership/request-security tests |
| Real Frappe schema and behavior | focused P4-04 runtime verifier; P4-01/P4-02/P4-03 compatibility runtime |
| Review data source, ViewModel, page, route/shell | strict parser/request unit tests; page/component/accessibility tests |
| Live review flow and trilingual industrial UI | affected Gate live E2E, three-locale/zoom visual cases, mixed-language scan |
| Controller and traceability records | YAML/CSV parsing, requirement-status review, `git diff --check` |

## 11. Validation strategy

Public OpenAPI, DocType Schema, authorization, permission, and accepted live
Gate changes trigger one Level 3 boundary after the complete slice stabilizes.
During implementation and repair, only Level 1 changed-file checks and directly
affected unit/component/API/runtime/browser cases run. Related failures are
batched by root cause. The complete Level 3 is not restarted after every
repair; only the directly affected checks and any incomplete final Gate lane
are rerun before the final evidence decision.

## 12. Explicit non-scope and Class-B holds

P4-04 does not deliver:

- production Gate contents, condition/skip/duration rules, approval maps,
  segregation rules, waiver/deviation eligibility, expiry rules, reopen reason
  taxonomy, or dependency/downstream matrices;
- disabled-member substitution or delegation policy;
- Document Revision, Trial, Quality Inspection, Customer Approval, external
  link, drawing, Tooling, Quality, or ECN live resolvers;
- live My Work, generic activity/comments, mail, in-app notification,
  reminder, escalation, portfolio, or Project health/lifecycle controls;
- normal-user file upload/download;
- production scanner/DMS or ERPNext access; or
- a claim that synthetic fixtures are production policy.

Missing production policy remains recorded in `BLOCKERS.md`,
`REQUIRED_INPUTS.md`, and the Phase 4 anchor. The executable path fails closed
instead of treating the hold as an empty success.

## 13. Truthful acceptance target

- `FR-SG-003` may reach `TECHNICAL_VERIFIED_FOUNDATION` for the versioned
  parallel/sequential/conditional mechanism, not production approval mapping.
- `FR-SG-005` may reach `TECHNICAL_VERIFIED_FOUNDATION` for blockers and
  explicit synthetic exceptions, not production waiver authority.
- `FR-SG-006` may reach `TECHNICAL_VERIFIED` for immutable decisions and
  preserved-cycle reopen semantics.
- `FR-SG-007` may reach `TECHNICAL_VERIFIED_FOUNDATION` for exact-input
  invalidation, successor review cycle, and guard, not a P4-04 impact
  WorkItem or the production drawing/Tooling/Quality/ECN matrix.
- `FR-CO-006` remains a foundation until later notification, email, print,
  external-user, and delivery surfaces exist.

Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; no P4-04 fixture or technical
evidence substitutes for the named external business UAT.
