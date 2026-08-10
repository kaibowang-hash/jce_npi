# P7-03 Plan — Cavity Results, Defect Lineage, Actions and Verification

Recorded: `2026-08-11`

Status: `FROZEN — CHECKPOINT 1 PASS; CHECKPOINT 2 AUTHORIZED`

Starting controller checkpoint:
`135d083bcb4e620c571fa3d4737cae54e7a8be2a`

Retained product checkpoint:
`3a267196d11921ba1111a0774f5f85bd8647ed9f`

Primary requirements:

- `FR-TR-004`;
- `FR-TR-009`; and
- retained `FR-TL-009` / `FR-TL-010` foundations.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is technically
complete. P7-03 may proceed after the starting controller checkpoint passes
ordinary CI, without a new business decision, only if it preserves the single
logical NPI defect identity and every scoped external hold below.

P7-02 provides exact Project, Trial Round, input-lock, Tooling Revision,
physical Set, cavity, Sample Batch, manual Actual and clean private evidence
truth. It does not contain a `CavityResult`, defect, exact action target Round,
independent verification attempt or Pareto projection.

P6-05 provides one live NPI-owned `ToolingDefectRevision` aggregate with a
stable defect identity, immutable successors, exact Tooling Revision/cavity,
severity, root cause, responsible Project member, embedded actions and clean
private evidence. It deliberately exposes Trial context as unavailable and
stores only a target-Round planning label. Its `verified` action state requires
evidence but does not prove an independent verifier, exact verification Round
or cavity result. Creating a second unrelated Trial defect would violate the
single-object ownership rule.

The accepted design therefore evolves the same stable `defectGlobalId` into a
Trial-bound successor stream. A new `NPI Trial Defect Revision` may start a new
Trial defect or succeed the exact current `NPI Tooling Defect Revision`; after
the first Trial successor, the earlier Tooling command cannot append a fork.
Reads union both immutable stores into one ordered defect timeline. There is
one logical defect, not a synchronized copy.

## 2. Frozen outcome

P7-03 delivers one minimum complete vertical slice:

> open one exact running Trial Round -> append one exact cavity-result revision
> for an exact Sample Batch/cavity with immutable dimensional observations ->
> create or continue one stable NPI defect against the exact Round/input lock/
> Tooling Revision/Set/cavity/Sample and clean Trial evidence -> assign
> containment/corrective/preventive actions to exact Project members and exact
> target Rounds -> observe the same defect in a later exact Round without
> rewriting the first observation -> append an independent verification attempt
> against the exact action, target Round, cavity result and evidence -> require
> a separate explicit successor to close or reopen the defect -> reopen the
> Trial workspace and filter exact cavity lineage plus server-derived Round/
> cavity/category/severity Pareto truth

P7-03 owns NPI collaboration defect, action-target, cavity-result and
verification truth only. It creates no ERPNext NCR or Quality Inspection,
does not mutate a Gate or Tooling lifecycle, does not submit a Trial conclusion
and does not claim full P7-04 Round comparison or approval authority.

## 3. Domain invariants

### 3.1 Cavity result revision

- `TrialCavityResultRevision` has one stable result UUID and immutable
  successors. It binds exact Project, running Trial Round, input-lock revision,
  Sample Batch revision, Tooling Revision/Set and one defined cavity UUID.
- A family/multi-cavity result cannot use free text, cavity count or array
  position as identity. The cavity must exist in the exact lock and Sample
  Batch; the exact Part/cavity mapping is server-resolved.
- Every dimensional observation has a stable characteristic key, label, unit,
  nominal/lower/upper definition, explicit `measured` or `not_measured` state,
  exact numeric value only when measured, source, observed time and actor.
  Missing data never becomes zero or a passing result.
- A correction appends a successor under exact version/predecessor/hash and a
  non-empty reason. It never overwrites the earlier measurement or silently
  adopts a later Sample, cavity, definition or evidence reference.
- Measurement-report evidence references only exact clean P7-02 Trial Evidence
  identities already contained by the same Round/Sample. No raw File URL or
  caller-supplied scan/privacy/hash truth is accepted.

### 3.2 Single defect identity and immutable Round observations

- `TrialDefectRevision` continues one stable `defectGlobalId`. Its predecessor
  is either absent for a new defect, the exact current P6-05 Tooling defect
  revision, or the exact current Trial defect revision. Cross-store version,
  predecessor and snapshot-hash checks prevent forks.
- The first Trial-bound revision freezes exact Project, running observation
  Round, input lock, Tooling Master/Revision/Set, optional Sample Batch and one
  exact cavity UUID. Location is structured bounded text in addition to cavity
  identity, never a replacement for it.
- A defect may continue across Rounds only through a successor. Every historical
  Round/cavity observation remains immutable; updates within a Round and a new
  Round observation are explicit different revision reasons.
- Category, severity, blocking intent, root-cause state/text, responsible
  member, occurrence count and evidence are immutable per revision. Severity
  never automatically sets blocking intent, and blocking intent never mutates
  a Gate.
- Existing P6 defect history remains readable. Once a Trial successor exists,
  the P6 Tooling append command fails closed instead of creating a parallel
  tip. The Tooling and Trial workspaces render the same current logical defect
  with its complete ordered lineage.

### 3.3 Actions, exact target Round and independent verification

- Containment, corrective and preventive actions retain stable action UUIDs,
  detail, exact responsible Project-member snapshot, due date, state and one
  exact target Trial Round ID/version/hash. A display label is never target
  identity.
- New/changed actions exist only in a defect successor. Removing a prior action,
  changing its identity/responsible member/target Round or moving backward in
  state fails closed unless the frozen transition explicitly permits a new
  corrective successor with reason.
- `TrialDefectVerificationRevision` is an immutable attempt bound to the exact
  defect revision, action UUID, target Round, verification Round, cavity result
  revision, verifier Project-member snapshot, `pass` or `fail`, finding,
  observed time and exact clean Trial evidence.
- The verifier must differ from the action's responsible member. A missing or
  same-member verifier, wrong Round/cavity/action, stale defect, unmeasured
  required cavity result or unsafe evidence fails closed.
- A verification attempt never edits an action or closes a defect. A later
  explicit defect successor may mark the action verified and the defect closed
  only against the exact latest successful verification. Failed verification
  keeps closure unavailable and can support an explicit reopened successor.
- Defect close/reopen is NPI collaboration lifecycle only. It creates no NCR,
  Quality Inspection, Gate result, Tooling lifecycle transition, Work Item
  closure or external event.

### 3.4 Derived filtering and Pareto truth

- The server derives Round/cavity/category/severity counts from exact immutable
  defect observations. Updates to the same defect/observation tuple do not
  double-count; explicit occurrence count is preserved.
- The workspace supports exact Round and cavity filtering for family/multi-
  cavity Tooling and shows dimensional lineage, open/closed defects, actions,
  verification attempts and Pareto rows with text labels and counts.
- P7-03 does not claim the full parameter/dimension/defect trend comparison or
  one-page summary assigned to P7-04. It exposes the exact source histories and
  bounded defect Pareto required for that later comparison.

## 4. Authorization, ownership and transaction boundary

- Existing Project visibility is required before resolving a Round, input lock,
  Tooling object, Sample, cavity, defect predecessor, action, member, result,
  evidence or verification.
- Until an approved production Trial-quality responsibility policy exists,
  only an enabled same-tenant internal System Manager may append cavity results,
  defects, actions or verification. Independent verifier business identity is
  still persisted and validated; this is a fail-closed technical boundary, not
  a production-role decision.
- Every command uses a closed canonical payload, CSRF, exact optimistic
  version/predecessor/hash, actor-bound idempotency, one transaction,
  append-only audit and sealed replay. Same key/different payload fails.
- Composite new/continued defect commands insert the exact defect revision and
  its receipt/audit in one transaction. A failure leaves no partial Trial tip,
  Cavity Result, verification, receipt or audit.
- NPI One owns the single logical defect, Trial action-target, cavity-result and
  verification truth. ERPNext retains formal NCR/Quality Inspection and
  production results. Existing Tooling, Trial, File, Project and member
  aggregates retain their own exact truth.

## 5. Closed BFF boundary

The audit authorizes these paths only after their checkpoint tests:

| Method and path | Purpose |
| --- | --- |
| `GET /projects/{projectId}/trial-rounds/{trialRoundId}/quality` | exact cavity-result/defect/action/verification histories, cavity filters, Pareto, permissions and unavailable external effects |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/cavity-results` | create one stable exact-cavity result and initial immutable revision |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/cavity-results/{cavityResultId}/revisions` | append one exact corrected cavity-result successor |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/defects` | create one stable Trial defect or atomically continue the exact current P6 defect into the Trial stream |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/defects/{defectId}/revisions` | append exact Round observation, root-cause/action/target/state successor without forking |
| `POST /projects/{projectId}/trial-rounds/{trialRoundId}/defects/{defectId}/verifications` | append one independent exact verification attempt only |

The existing P6-05 and P7-01/P7-02 paths remain closed and independently
switchable. P7-03 exposes no NCR, Quality Inspection, Gate, Tooling lifecycle,
conclusion, approval, readiness, release, external projection or print command.

## 6. Additive persistence

Checkpoint 1 adds only three guarded DocTypes:

- `NPI Trial Cavity Result Revision`;
- `NPI Trial Defect Revision`; and
- `NPI Trial Defect Verification Revision`.

The existing `NPI Tooling Defect Revision`, Trial Round, input lock, Sample
Batch, Trial Evidence, command-idempotency and audit objects are reused. New
objects use UUID identity, exact parent/version/hash fields, canonical snapshots
and hashes, immutable controllers, System Manager/NPI API create-only DocPerms
and denied generic update/delete. Metadata creates no business row, default
policy, fixture, production mapping, adapter or external call.

## 7. Checkpoints

1. **Domain/contract/additive metadata** — pure Cavity Result, cross-store
   single-defect successor, exact action target and independent-verification
   invariants; closed OpenAPI/ownership; three guarded DocTypes; direct
   translations and focused tests. No live route, business row, UI or runtime
   fixture.
2. **Repository/BFF/single-tip boundary** — Project-first reads and cavity-
   result/defect/verification commands, exact containment, P6-to-P7 single-tip
   enforcement, actor-bound replay, one transaction, append-only audit and an
   independent default-closed P7-03 switch. No UI or runtime fixture.
3. **Live cavity-quality workspace** — strict quality data source and dense
   trilingual cavity-result/defect/action/verification/Pareto work area with
   loading, empty, read-only, permission, validation, conflict, processing,
   retry and unavailable NCR/Gate/Tooling states plus affected Linux visuals.
4. **Controlled runtime and Level 2** — disposable-Site cavity result successor,
   new and continued P6 defect, cross-Round observation, exact action target,
   failed/passed independent verification, explicit close/reopen, same/cross-
   process replay, fork/conflict/rollback/IDOR/route recovery/migrations/
   redaction, no ERP/network/Outbox and cleanup; then trace, diff and Task Gate.

Complete ordinary CI passes before each controlled-Site dispatch. The optimized
`level_2_controlled` path may reuse only the exact successful prior PR Gate
after machine verification. Any unbounded shared-contract, permission or
infrastructure impact escalates to Level 3.

## 8. Requirement acceptance map

| Requirement | P7-03 evidence boundary |
| --- | --- |
| `FR-TR-004` | exact category/location/cavity/severity/evidence/root-cause/responsibility/action/target-Round/independent-verification lineage plus bounded server-derived defect Pareto |
| `FR-TR-009` | exact Sample/cavity dimensional result and defect lineage with family/multi-cavity filtering; full cross-Round dimension trend comparison remains P7-04 |
| `FR-TL-009` foundation | the existing single Tooling defect gains exact Trial successors/actions/verifications without automatic G5/G6 effect |
| `FR-TL-010` foundation | exact Round/Tooling/product/input/parameter/Sample/cavity/defect source histories become available; full Round comparison remains P7-04 |

Expected truthful Task-Gate dispositions are `TECHNICAL_VERIFIED` for
`FR-TR-004` and
`TECHNICAL_VERIFIED_CAVITY_TRACE_FOUNDATION_ROUND_COMPARISON_HELD` for
`FR-TR-009`. `FR-TL-009/010` retain their earlier foundation statuses until
later comparison and separately authorized Gate-policy integration. No
aggregate PASS may hide those holds.

## 9. Changed-files to affected-tests

| Surface | Required evidence |
| --- | --- |
| domains/contracts/ownership | one defect identity, cross-store tip, exact cavity/result/action/verification schemas and no external effect |
| DocTypes/controllers | additive migration, exact projections, cross-parent validation, generic mutation/delete denial and no seeded rows |
| repository/BFF | Project-first IDOR, Round/lock/Sample/cavity/member/evidence containment, fork/stale/hash conflict, actor replay, transaction/audit/rollback and independent switch |
| P6 interoperability | union timeline, P6 append denial after Trial successor, retained P6 histories and no existing snapshot/hash rewrite |
| frontend | unit/state/keyboard/Axe, direct English/zh/zh-TW, mixed-language scan, industrial density and affected P7 visuals |
| runtime | cumulative predecessor, cross-store successor, fresh-process replay, route recovery, migrations, redaction, zero integration traffic and cleanup |
| trace/controller | two primary Requirement rows, two retained foundations, current-task manifest, Task Diff Review and `git diff --check` |

## 10. Rollback

Before retained P7-03 rows, restore the starting checkpoint and migrate a
disposable Site fresh. After retained Cavity Result/defect/verification/
receipt/audit history, disable only the independent P7-03 quality routes and
workspace and deliver a reviewed forward fix. Never delete rows, split the
single defect timeline, re-enable a P6 append fork or rewrite immutable Trial,
Tooling, File, evidence, action or verification snapshots to simulate rollback.
