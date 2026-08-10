# P7-01 Plan — Trial Plan and Round Identity/Lifecycle Foundation

Recorded: `2026-08-10T05:26:23Z`

Starting synchronized controller checkpoint:
`4865e0a6e0e3946f21b847b79675ebeaa828e2b2`

Starting exact-SHA ordinary CI:
`31358008296` (`PASS`; repository `93361224683`, fixed-Linux visual
`93361224744` at `94/94`, controlled runtime correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/CONTRACT/METADATA
FOUNDATION NEXT**

Primary requirement: `FR-TR-001`

Applicable Skills:

- `repo-discovery`;
- `npi-domain-guard`;
- `frappe-safe-change`;
- `frappe-i18n`; and
- `industrial-ux` for the later live workspace checkpoint.

## 1. Sources and existing-capability conclusion

The audit used the Phase 7 anchor, `FR-TR-001`, M6-01, the accepted Trial
sections in `docs/DOMAIN_MODEL.md` and `docs/TOOLING_AND_TRIAL.md`, Project
authorization/work-item patterns, Tooling Master/Revision/Set containment,
the current ownership/OpenAPI contracts and the deterministic Trial SPA.

Repository truth is:

- there is no Trial Plan, Trial Plan Revision, Trial Round, Trial lifecycle
  event, repository, BFF implementation, guarded metadata or durable audit;
- `frontend/src/pages/trial-page.tsx` is intentionally in-memory and persists
  neither its local photo nor its prepared action/reason;
- `/tooling/{toolingId}/trials`, `/trials/{trialId}/workspace` and
  `/trials/{trialId}:submit` in the OpenAPI document are unimplemented early
  placeholders: they omit Project-first containment, collapse Plan into Round,
  accept locked inputs before P7-02 and expose P7-04 conclusion behavior;
- the coarse `TrialRound` ownership row correctly separates NPI and formal ERP
  quality ownership but does not define Plan, revision, lifecycle-event,
  work-link or command-receipt identities;
- Project authorization, current Project membership, immutable Tooling
  identities, Domain Work Items, actor-bound idempotency, audit, request
  security, route switches and stable problem envelopes are reusable
  mechanisms, not inherited Trial authority; and
- no production machine/person/material calendar, availability reader,
  reservation authority/policy or ERP resource adapter exists.

The placeholder contract has no live consumer and conflicts with the accepted
Phase 7 anchor. Replacing it with closed Project-first Plan/Round schemas is a
correction within the approved architecture, not an architecture change or a
new ADR. No production API is removed because no handler is installed.

## 2. Scope and truthful completion boundary

P7-01 delivers this minimum vertical slice:

> open one authorized Project -> create one immutable versioned Trial Plan
> against an exact authorized Tooling Master -> record objectives, purpose,
> planned time, proposed machine/material resources, exact responsible Project
> members, sample quantity and measurement-plan intent -> append one successor
> Plan revision without rewriting history -> create one distinct planned Trial
> Round bound to an exact Plan revision -> generate one or more governed Domain
> Work Item actions with immutable Trial links -> reopen the Project Trial
> workspace and observe Plan/Round/version/task/audit truth

P7-01 proves distinct identities, planned-state lifecycle truth, Plan revision
history, task generation and honest resource-planning status. It does not
claim a proposed machine/material reference is available or reserved. Exact
input locks, physical Set/cavity context, actual parameters, samples/evidence,
defects, conclusion, approval, readiness and external quality remain later P7
tasks.

At its Level 2 Gate, `FR-TR-001` may advance only to
`TECHNICAL_VERIFIED_FOUNDATION_RESOURCE_RESERVATION_HELD` unless a separately
approved and tested reservation policy/reader exists. This is truthful partial
completion, not a global blocker.

## 3. Frozen identities and invariants

### 3.1 Trial Plan and immutable revisions

- `TrialPlan` is one stable UUID inside one tenant and Project. It is neither a
  Trial Round nor a Tooling lifecycle record.
- Every change creates a new immutable `TrialPlanRevision` with exact integer
  version, predecessor ID/hash, reason, actor/time/request/trace and canonical
  snapshot/hash. The latest projection is derived under exact uniqueness; no
  old revision is overwritten.
- A Plan binds one authorized Project and one Tooling Master. P7-01 does not
  invent a released Tooling Revision, physical Set or input lock; those remain
  explicit unavailable dependencies for P7-02.
- Purpose is one controlled source value from the accepted specification:
  `first_trial`, `tooling_change_verification`, `design_verification`,
  `material_color_verification`, `capability_study`, `customer_sample` or
  `other` with a required bounded objective.
- Planned start/end are aware UTC instants with start before end. Sample
  quantity is a positive planning value, not a created Sample Batch.
- Responsible people are exact current enabled internal Project members with
  retained member version and user identity. Free-text people do not grant
  access or command authority.
- Machine/material entries are immutable proposals with source/key/label and
  optional quantity/unit provenance. Their server-owned booking state is
  `unavailable`; no caller availability, conflict-free or reserved flag exists.
- Measurement-plan intent may reference an exact authorized clean controlled
  document revision when available, or remain an explicit bounded description.
  It is not the P7-02 locked inspection input.

### 3.2 Trial Round planned identity

- `TrialRound` has its own immutable UUID and references one exact Plan
  revision ID/hash. Later Plan revisions never move an existing Round.
- Its integer sequence is allocated under one locked Project/Plan scope. The
  server suggests `T0`, `T1`, ...; an optional controlled label must remain
  unique inside that exact Plan and cannot become a global identity.
- P7-01 creates only state `planned`. The accepted lifecycle remains
  `planned -> prepared -> running -> analysis -> submitted ->
  approved/rejected/cancelled`, but P7-02 owns prepare/running input truth and
  P7-04 owns conclusion/submission/approval truth. P7-01 installs no command
  that jumps into those states.
- Planned cancellation, if activated after contract tests, requires exact
  optimistic version, non-empty reason, System Manager technical authority and
  an immutable lifecycle event. It deletes nothing and grants no Gate/Tooling/
  quality effect. Otherwise cancellation remains inactive until P7-04.
- Every lifecycle change is an immutable `TrialRoundLifecycleEvent`; the root
  is only the current guarded projection. State/version/event drift fails
  closed.
- Cloning, input inheritance and unresolved-defect carry-forward are held until
  their exact P7-02/P7-03 source snapshots exist. P7-01 never aliases mutable
  values from the prototype or prior Round.

### 3.3 Task generation without a second task truth

- Generated actions remain the existing governed `NPI Domain Work Item`, using
  the exact current published Project Work policy and action lifecycle.
- A separate immutable `TrialPlanWorkLink` binds the exact Plan revision/Round
  to each same-Project Work Item. The Trial domain does not create a competing
  task state or encode a Trial ID in title/detail text.
- One narrow command validates all owners/context/policy first and creates the
  Work Items plus links in one transaction with one actor-bound receipt and
  audit summary. Partial task generation is prohibited.
- Existing Project Work authority and lifecycle are preserved. A Trial viewer
  does not gain Work Item administration, and a Work Item alone does not grant
  Project or Trial access.

## 4. Authorization, concurrency and audit

- Route/method/CSRF and Project view/administration run before resolving a
  Plan, Round, Tooling Master, member, document or Work Item identity.
- Current enabled same-tenant internal Project owner/member and System Manager
  may view the Project Trial projection. Guest, Website/external, cross-tenant,
  unrelated, duplicate/ambiguous or expired memberships fail indistinguishably.
- Until an approved Trial responsibility policy exists, only same-tenant
  System Manager may create/revise Plans, create Rounds or generate actions.
  This is a fail-closed technical boundary, not a production role decision.
- Each command uses exact predecessor/version/hash where applicable, a closed
  canonical payload, actor-bound idempotency-key hash, one transaction,
  append-only audit and a sealed replay response. Same key/different payload
  conflicts; replay returns the exact original response.
- Collection bounds are explicit. The browser cannot submit tenant, actor,
  sequence, current state, booking state, snapshot hash, audit data, source
  ownership or lifecycle event identity.
- A dedicated independent Trial route switch defaults closed when configured.
  Disabling it never disables Project, Tooling, controlled-print or other
  routes.

## 5. Corrected closed BFF contract

The checkpoint replaces the unimplemented placeholder paths with:

| Method and path | P7-01 purpose |
|---|---|
| `GET /projects/{projectId}/trials` | bounded Project Trial planning projection, exact latest Plan revisions, planned Rounds, work links, capabilities and unavailable later sections |
| `GET /projects/{projectId}/trial-plans/{trialPlanId}` | one authorized Plan revision history and exact linked Rounds/actions |
| `POST /projects/{projectId}/trial-plans` | create a stable Plan and immutable initial revision |
| `POST /projects/{projectId}/trial-plans/{trialPlanId}/revisions` | append one exact successor Plan revision |
| `POST /projects/{projectId}/trial-plans/{trialPlanId}/rounds` | create one distinct planned Round against the exact Plan revision |
| `POST /projects/{projectId}/trial-plans/{trialPlanId}/actions:generate` | atomically create governed Domain Work Item actions and immutable Trial links |

P7-01 exposes no `submit`, `prepare`, `start`, actual-value, defect, conclusion,
approval, Gate, ERP quality or resource-confirmation command. Later tasks add
their paths only after their own domain audits.

All schemas are closed, bounded and use stable keys. The error family includes
`TRIAL_UNAVAILABLE`, `TRIAL_ROUTES_DISABLED`, `TRIAL_REFERENCE_UNAVAILABLE`,
`TRIAL_VERSION_CONFLICT`, `TRIAL_LABEL_CONFLICT` and
`TRIAL_IDEMPOTENCY_CONFLICT` plus existing authentication, CSRF, validation,
method, internal and service-unavailable envelopes.

## 6. Persistence and ownership plan

Checkpoint 1 adds only:

- `NPI Trial Plan Revision` — immutable Plan versions;
- `NPI Trial Round` — guarded current identity/planned-state projection;
- `NPI Trial Round Lifecycle Event` — immutable state/event history;
- `NPI Trial Plan Work Link` — immutable Plan/Round-to-Domain-Work relation;
  and
- `NPI Trial Command Idempotency` — actor/Project/operation/payload identity
  and sealed response.

UUID identity, same-tenant Project/Tooling parent checks, no rename/delete,
System Manager/NPI API create-only DocPerms, controller flags, canonical
snapshots, exact hashes and denied generic CRUD are mandatory. Metadata creates
no business row, policy, resource, task, fixture, external mapping or adapter.

`contracts/data-ownership.yaml` gains exact Plan Revision, Round, lifecycle
event, work-link and receipt rows. NPI One owns planning/lifecycle truth;
Project Work owns action state; ERPNext owns formal machine/material/resource,
quality and production truth. Resource proposals remain NPI intent and target
availability/reservation remains unavailable.

## 7. Checkpoints

1. **Domain/contract/additive metadata** — pure Plan/Round/work-link/receipt
   invariants, five guarded DocTypes, corrected closed OpenAPI and exact
   ownership/security tests; no route, business row, UI or runtime fixture.
2. **Repository/BFF** — Project-first reads and create/revise/create-round/
   generate-actions commands, Tooling/member/document/Work containment,
   transaction/idempotency/audit, route switch and API tests.
3. **Live Trial planning workspace** — strict data source and dense trilingual
   Plan/Round/action projection with honest resource-booking and later-section
   unavailability; state/accessibility/affected visual evidence.
4. **Controlled runtime and Level 2** — disposable-Site Plan successor, Round,
   action/link, replay/conflict/rollback/IDOR/route recovery/migrations and no
   ERP/network/Outbox proof, then trace reconciliation and Task Diff Review.

Complete ordinary CI passes before every controlled-Site boundary. Temporary
diagnostics remain closed unless an opaque exact-SHA failure enters the
controller's serial response-neutral proof protocol.

## 8. Requirement-to-code-to-evidence map

| FR-TR-001 clause | Planned P7-01 truth | Required evidence |
|---|---|---|
| objective, purpose and Rounds | immutable Plan revisions plus distinct planned Round UUID/sequence/label | non-collapse, revision, predecessor/hash, label collision and replay tests |
| date and Tooling | UTC interval and exact authorized Project/Tooling Master | parent/version/cross-Project/IDOR tests |
| machine, material and personnel | proposed resource references plus exact Project-member snapshots; booking explicitly unavailable | no caller reservation state, member expiry and no fake external truth tests |
| sample quantity and measurement plan | positive planning quantity and exact controlled-document reference or bounded intent | no Sample Batch/lock claim, document permission/hash and validation tests |
| generate tasks | existing Domain Work Item actions plus immutable Trial links in one transaction | exact work policy, owner, atomicity, link, replay/conflict and My Work projection tests |
| reserve resources | explicit unsupported/unavailable capability until approved policy/reader | no adapter/network/ERP/Outbox, no reserved/success state and trace-hold assertion |

## 9. Changed-files to affected-tests

| Expected surface | Minimum direct checks |
|---|---|
| `apps/npi_core/npi_core/trial/**` | domain/hash/version/sequence/lifecycle/work-link tests and focused compilation |
| five Trial DocTypes and validation flag | metadata/controller parent/immutability/generic CRUD/delete tests and additive Site migration |
| OpenAPI and data ownership | parse/reference/closed-schema/Project-first/no-placeholder/ownership assertions |
| request security, BFF and Trial API | method/CSRF/route-switch/permission/IDOR/error/idempotency/audit transaction tests |
| Project Work and Tooling references | current Project/member/work-policy/Master/document containment regressions |
| Trial data source/router/page | parser/transport/state/component/type/lint/prototype-isolation tests |
| visible text/catalogs/styles | literal English, direct `zh`/`zh-TW`, mixed-language, accessibility and affected governed visuals |
| controlled runtime/workflow | two migrations, Plan successor, Round/action/link/replay/conflict, rollback, IDOR, independent route recovery, zero integration traffic and cleanup |
| trace/evidence/controller | `FR-TR-001` truthful foundation status, evidence existence, Task Diff and `git diff --check` |

## 10. Migration, rollback and exit

The migration is additive and idempotent. It performs no backfill from the
prototype, Tooling status, spreadsheets, Project schedule, ERPNext or free-text
identifiers.

Before retained Trial history, a disposable environment may restore checkpoint
`4865e0a` and migrate fresh. After retained history, rollback disables only the
independent Trial route/workspace and deploys a reviewed forward fix while
preserving every Plan revision, Round/event, Work Item/link, receipt and audit.
It never deletes a Round, rewrites a predecessor or marks a proposal reserved.

This audit passes. Standing authority activates only checkpoint 1 domain,
contract and additive metadata. No live route, product row, SPA behavior,
resource reservation, lifecycle transition beyond pure planned-state rules,
quality/Gate command, ERPNext contact or later P7 behavior is active.
