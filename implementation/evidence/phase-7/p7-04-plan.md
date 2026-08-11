# P7-04 Plan — Round Comparison, Conclusion, Quality and Approval References

Recorded: `2026-08-11`

Status: `FROZEN — CHECKPOINT 1 AUTHORIZED`

Starting controller checkpoint:
`1c0e8fdd73901c59ce920ff73fa5eea962be70c0`

Retained product checkpoint:
`102de35b9cff4b7303e0e2f17d2bbb146795fc3d`

Primary requirements:

- `FR-TR-005`;
- `FR-TR-006`;
- `FR-TR-007`; and
- `FR-TR-008`.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is technically
complete. Exact controller SHA `1c0e8fd` passes ordinary PR CI
`31460976409`: repository `93684251780`, secret scan `93684251722`,
fixed-Linux visual `93684251718` at the retained `103/103` matrix and
frontend/E2E `93684251739` in `10m44s`. P7-04 may proceed without a new
business decision only within the frozen boundary below.

P7-01 through P7-03 provide immutable Round identities/lifecycle events,
input-lock revisions, manual Trial Actual parameter revisions, Sample Batches,
clean private evidence, cavity dimensions, one stable cross-Round defect
timeline, exact target Rounds and independent verification. They provide no
comparison snapshot, conclusion, review-reference aggregate, conclusion
policy, formal ERP quality projection or customer-signature authority.

The existing Round state vocabulary already names `analysis`, `submitted`,
`approved` and `rejected`, but live validation and lifecycle commands stop at
`running`. Those enum values do not grant transition or conclusion authority.
P7-04 therefore adds versioned policy-bound lifecycle behavior and keeps Round
lifecycle, conclusion and external effects as three distinct facts.

The current Trial Actual has generic parameter/environment/resource readings,
not dedicated governed cycle-time or input/good/scrap yield fields. P7-04 may
compare an exact locked parameter only when its definition explicitly
represents such a metric. Otherwise cycle/yield is `unavailable`; zero,
free-text inference and latest-value substitution are prohibited.

## 2. Frozen outcome

P7-04 delivers one minimum complete vertical slice:

> open one exact running Trial Round -> begin policy-authorized analysis ->
> select at least two exact same-Project/same-Plan Rounds -> freeze one
> deterministic comparison snapshot over exact input-lock, Actual, cavity and
> defect revision tuples -> attach distinct controlled internal-quality,
> internal-sample, customer-evidence and deviation/waiver references to exact
> product, Tooling and clean File revisions without claiming approval -> show
> server-derived critical blockers and explicitly unavailable formal ERP
> quality/cycle/yield/external effects -> submit one immutable conclusion
> snapshot against the exact policy/comparison/reference hashes -> record an
> exact policy-bound approve or reject decision -> reopen by immutable
> successor and audit rather than overwrite -> reopen the dense trilingual
> Trial workspace and reconstruct the same comparison and one-page summary
> input without a latest lookup

P7-04 owns NPI Round-comparison, conclusion-snapshot and controlled reference
truth only. It creates no ERPNext Quality Inspection/NCR/report result, Gate or
Tooling transition, Work Item, customer signature, readiness decision,
Released Trial Summary, external event or production output.

## 3. Domain invariants

### 3.1 Exact immutable comparison

- `TrialRoundComparisonSnapshot` has a UUID and immutable canonical snapshot.
  It is scoped to one exact Project and Trial Plan and contains at least two
  distinct exact Round IDs/versions/hashes including the target Round.
- Each selected Round binds its exact current Round lifecycle version/hash,
  input-lock revision/hash, Trial Actual revision/hash, cavity-result tips and
  hashes, and stable defect tips/hashes at capture time. Optional conclusion or
  review-reference tips are bound only when present. Replay resolves those
  exact tuples and never replaces one with the current tip.
- Input differences use deterministic `added / removed / changed / same` rows
  over stable semantic keys and exact source identities. A changed display
  label does not become identity.
- Parameter rows align exact definitions/keys and compatible units, preserve
  measured versus `not_measured`, values, target windows and sources, and emit
  an explicit unit mismatch instead of computing an unsafe delta.
- Dimension rows align defined cavity UUID plus characteristic key and retain
  exact value/unit/nominal/limits/comparison state. Missing values remain
  `not_measured`; family/multi-cavity results are not collapsed.
- Defect rows align stable `defectGlobalId` and exact Round observations into
  `new / continued / resolved / reopened` with action/verification lineage.
  Counts and trends are server-derived and textual; color is never the sole
  signal.
- Cycle time and yield are compared only from exact governed definitions. When
  the exact source does not exist, the snapshot and UI say `unavailable`.

### 3.2 Controlled review references are not approvals

- `TrialReviewReferenceRevision` is an immutable successor stream for one
  stable reference UUID and one bounded kind: NPI controlled quality report,
  internal sample review evidence, customer evidence, or deviation/waiver
  evidence.
- Every revision binds the exact Project, Round, comparison snapshot, product/
  Part revision, Tooling Master/Revision/physical Set and clean private File
  Revision identities/hashes required by its kind, plus effectivity start/end
  when applicable. A filename, raw File URL or caller-selected clean state is
  not authority.
- Reference lifecycle and evidence presence are distinct from approval. Exact
  approver, customer, signature, decision and effectivity authority must come
  from the frozen policy/provider; when absent they remain `unavailable` and
  conclusion submission fails closed if the policy requires them.
- ERPNext formal Quality Inspection/NCR/report identity, result and latest
  status remain an independent read-only projection. Phase 8 has not supplied
  the adapter, so P7-04 exposes `unavailable`, stores no caller-supplied formal
  status and performs no network call or external mutation.

### 3.3 Policy-bound lifecycle and immutable conclusion

- `TrialConclusionPolicyVersion` is an exact Project/Plan-scoped immutable
  policy with published version/hash, permitted conclusion/lifecycle
  transitions, required source/reference kinds, blocker rules and authority
  bindings. Metadata installs no default production policy or authority row.
- Round lifecycle transitions are explicit and versioned. P7-04 may add only
  `running -> analysis -> submitted -> approved|rejected`, plus controlled
  `submitted|approved|rejected -> analysis` reopen. Existing cancellation
  remains a separate lifecycle command. The `cancelled` conclusion code does
  not silently cancel a Round.
- `TrialConclusionRevision` has one stable conclusion UUID and immutable
  submitted/decision/reopen successors. A submitted revision freezes the
  exact Round/lifecycle, policy, comparison, input, Actual, Sample, cavity,
  defect/action/verification, review-reference and evidence hashes plus the
  accepted conclusion code, reason, proposed next work and proposed Gate/NPI
  effect.
- Server-derived critical blockers include missing exact current input/Actual,
  required `not_measured` parameters/dimensions, missing required cavity
  results, blocking/open defects, required actions without successful exact
  verification, and policy-required missing/unavailable references. Out-of-
  specification observations block only under the exact policy/conclusion
  rule; severity or color alone never invents a business rule.
- The browser cannot submit readiness, suppress blockers or select a latest
  source. Submission requires exact optimistic versions/hashes and fails
  closed without a published policy and exact eligible authority bindings.
- A decision appends an immutable successor. Reopen appends a new lifecycle
  event and conclusion successor with reason/audit; it never deletes or edits
  the submitted/decided snapshot and never copies prior approval as current.
- Proposed next task/Round and Gate/NPI effect remain snapshot content only.
  No external command runs until a separately authorized exact policy and
  target capability exist.

### 3.4 One-page summary input

- P7-04 produces one immutable, localized-neutral summary-input projection
  referencing the exact comparison and conclusion snapshots: Round/input
  changes, parameters, explicitly unavailable cycle/yield, cavity dimensions,
  defect/action/verification trends, Samples, quality/approval-reference
  states, conclusion, blockers and proposed next effects.
- This projection contains codes, exact values and source identities, not a
  released document or language-rendered production artifact. P7-07 owns the
  immutable Released Trial Summary and controlled output/print behavior.

## 4. Authorization, ownership and transaction boundary

- Existing Project visibility is checked before resolving a Plan, Round,
  policy, comparison source, input, Actual, Sample, cavity, defect, action,
  verification, File, Part, Tooling object or reference.
- Until a production responsibility policy exists, only an enabled same-tenant
  internal System Manager may manage the technical slice. Policy subjects and
  authority bindings are still versioned and validated; this boundary is not a
  production-role decision.
- Every command uses a closed canonical payload, CSRF, exact optimistic
  version/predecessor/hash, actor-bound idempotency, one transaction,
  append-only audit and sealed replay. Same key/different payload fails.
- Comparison capture inserts the immutable snapshot, receipt and audit in one
  transaction. Reference, conclusion submission, decision and reopen each
  insert their exact successor/event/receipt/audit set atomically; failure
  leaves no partial tip or lifecycle advance.
- NPI One owns comparison/conclusion/reference evidence truth. ERPNext retains
  formal quality; existing Project, Gate, Tooling, Trial, File, Sample and
  defect aggregates retain their own truth. No field becomes dual-master.

## 5. Closed BFF boundary

The audit authorizes these paths only after their checkpoint tests:

| Method and path | Purpose |
| --- | --- |
| `GET /projects/{projectId}/trial-rounds/{trialRoundId}/review` | exact sources, comparisons, references, conclusion history, blockers, permissions, summary input and unavailable external projections |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}:begin-analysis` | exact policy-bound `running -> analysis` lifecycle event |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/comparisons` | capture one deterministic exact multi-Round comparison snapshot |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/review-references` | append one exact controlled reference revision without claiming approval |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/conclusions` | submit one immutable conclusion snapshot after server blockers pass |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/conclusions/{conclusionId}:decide` | append one exact policy-bound approve/reject successor |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}:reopen` | append a controlled lifecycle/conclusion reopen successor with reason |

Existing P7-01 through P7-03 paths remain independently switchable. P7-04
exposes no formal ERP quality write, customer-signature, Gate/Tooling/Work Item
mutation, readiness, handover, release, external projection or print route.

## 6. Additive persistence

Checkpoint 1 adds only four guarded DocTypes:

- `NPI Trial Conclusion Policy Version`;
- `NPI Trial Round Comparison Snapshot`;
- `NPI Trial Review Reference Revision`; and
- `NPI Trial Conclusion Revision`.

The existing Trial Round/lifecycle, input-lock, Actual, Sample, evidence,
cavity-result, defect, verification, command-idempotency and audit objects are
reused. New objects use UUID identity, exact parent/version/hash fields,
canonical immutable snapshots/controllers, System Manager/NPI API create-only
DocPerms and denied generic update/delete. Metadata creates no business row,
production policy, authority binding, fixture, ERP adapter or external call.

## 7. Checkpoints

1. **Domain/contract/additive metadata** — pure exact comparison, controlled-
   reference, policy, blocker, immutable conclusion/decision/reopen and summary-
   input invariants; closed OpenAPI/ownership; four guarded DocTypes; receipt
   values, direct translations and focused tests. No route, business row,
   lifecycle transition, UI or runtime fixture.
2. **Repository/BFF/policy boundary** — Project-first review read and exact
   begin-analysis/comparison/reference/conclusion/decision/reopen commands,
   fail-closed published policy/authority, server blockers, actor-bound replay,
   one transaction, append-only audit and an independent default-closed P7-04
   switch. No UI or runtime fixture.
3. **Live comparison/conclusion workspace** — extend the same dense Trial page
   with exact comparison matrix, blockers, reference states, conclusion/history
   and one-page summary-input preview; cover loading, empty, read-only,
   permission, validation, conflict, processing, retry and unavailable ERP/
   cycle/yield/external-effect states in English/`zh`/`zh-TW` plus affected
   fixed-Linux visuals. This is not the P7-07 released export.
4. **Controlled runtime and Level 2** — disposable-Site exact multi-Round
   comparison, unavailable sources, reference revision, policy blockers,
   submit/approve/reject/reopen history, same/cross-process replay, stale/fork/
   conflict/rollback/IDOR/route recovery/migrations/redaction, no ERP/network/
   Outbox or Gate/Tooling effect and cleanup; then trace, Task Diff Review and
   Task Gate.

Complete ordinary CI passes before each controlled-Site dispatch. The optimized
`level_2_controlled` path may reuse only the exact successful prior PR Gate
after machine verification. Repair loops run affected checks first and batch
failures with one root; no test, threshold, matrix or PASS criterion is
removed. Any unbounded shared-contract, permission or infrastructure impact
escalates to Level 3.

## 8. Requirement acceptance map

| Requirement | P7-04 truthful evidence boundary |
| --- | --- |
| `FR-TR-005` | immutable NPI conclusion/reopen and proposed next effects; automatic next-task/Gate mutation remains policy-held |
| `FR-TR-006` | NPI controlled quality-reference foundation and explicit unavailable formal ERP projection; latest ERP status remains Phase 8-held |
| `FR-TR-007` | version-locked internal/customer/deviation evidence reference foundation; evidence is not approval and customer/signature authority remains held |
| `FR-TR-008` | exact parameter/dimension/defect comparison and immutable one-page summary input; released export/output remains P7-07-held |

Expected truthful Task-Gate dispositions are
`TECHNICAL_VERIFIED_FOUNDATION_GATE_EFFECT_POLICY_HELD` for `FR-TR-005`,
`TECHNICAL_VERIFIED_NPI_REFERENCE_FOUNDATION_FORMAL_ERP_PROJECTION_HELD` for
`FR-TR-006`,
`TECHNICAL_VERIFIED_INTERNAL_REFERENCE_FOUNDATION_CUSTOMER_AUTHORITY_HELD` for
`FR-TR-007`, and
`TECHNICAL_VERIFIED_COMPARISON_FOUNDATION_SUMMARY_OUTPUT_HELD` for
`FR-TR-008`. No aggregate PASS may hide those holds.

## 9. Changed-files to affected-tests

| Surface | Required evidence |
| --- | --- |
| domains/contracts/ownership | exact source tuples, deterministic comparison, policy/blockers, distinct evidence/approval/external truth and no downstream mutation |
| DocTypes/controllers | additive migration, immutable projections, exact containment, generic update/delete denial and no seeded rows/policy |
| repository/BFF | Project-first IDOR, stale/version/hash/fork conflict, policy/authority/blockers, actor replay, transaction/audit/rollback and independent switch |
| retained P7 interoperability | exact Round/input/Actual/Sample/cavity/defect tips, lifecycle/conclusion separation, no retained snapshot rewrite and no latest substitution |
| frontend | unit/state/keyboard/Axe, direct English/zh/zh-TW, mixed-language scan, industrial density and affected P7 visuals |
| runtime | cumulative predecessor, exact replay/reconstruction, unavailable ERP/cycle/yield truth, route recovery, migrations, redaction, zero traffic/effects and cleanup |
| trace/controller | four Requirement rows, current-task manifest, Task Diff Review and `git diff --check` |

## 10. Rollback

Before retained P7-04 rows, restore the starting checkpoint and migrate a
disposable Site fresh. After retained comparison/reference/conclusion/
lifecycle/receipt/audit history, disable only the independent P7-04 review
routes and workspace and deliver a reviewed forward repair. Never delete a
row, rewrite an exact source tuple, substitute a current tip, erase a decision
or approval hold, infer formal ERP/customer/Gate/Tooling truth, or edit
immutable Trial/File/Tooling/defect history to simulate rollback.
