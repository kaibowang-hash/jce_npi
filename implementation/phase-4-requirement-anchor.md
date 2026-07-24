# Phase 4 Requirement Anchor — Project, Work Items, and Stage Gates

Status: **ANCHORED — P4-01/P4-02/P4-03 PASS; P4-04 IN PROGRESS AT CHECKPOINT**

Anchor date: 2026-07-22

Controller phase: 4 — Project Work Items and Stage Gates

Compatibility milestone: M3 — Project and stage gates

Starting checkpoint: `711b17d`

## 1. Authority and outcome

This anchor applies the V1.2 continuous-delivery authority to the Phase 4
Project/Gate vertical slice. It is based on `GOAL.md`, `docs/DOMAIN_MODEL.md`,
`docs/DETAILED_REQUIREMENTS.md`, `docs/ARCHITECTURE.md`,
`docs/UX_INTERACTION_SPEC.md`, `implementation/ROADMAP.md`, M3 in
`implementation/backlog.yaml`, the current contracts, and the accepted ADRs.

The bounded demonstrable path is:

> create a project from a versioned template → instantiate G0/G1 → assign the
> team and an action → attach controlled evidence → review a Gate → persist an
> immutable decision snapshot → expose the resulting item in My Work

Phase 4 delivers NPI-owned Project, Team/RACI, WorkItem, Gate, Evidence,
review/snapshot/reopen, internal contextual activity, and live My Work
capability. It does not silently absorb portfolio/KPI, portals, production ERP
creation or cost, external scheduling, or live notification delivery.

## 2. Requirement allocation

### 2.1 Phase 4 delivery scope

| Atomic task | Requirements | Truthful delivery boundary |
|---|---|---|
| P4-01 — Project template and live cockpit | FR-PM-001, FR-PM-003, FR-PM-004 | Versioned generic templates create Project drafts and Gate instances; explicit references and template policies drive validation; the Project cockpit reads the live BFF |
| P4-02 — Team, RACI, WBS, and domain work items | FR-PM-005, FR-PM-006, FR-PM-007, FR-PM-009, FR-CO-002 | Project membership, role assignments, substitute dates, parent/child work, dependencies, plan baseline comparison, critical-task flag, and unified risk/issue/action/decision-request records; no resource optimizer or OpenProject dependency |
| P4-03 — Gate templates and controlled evidence | FR-SG-001, FR-SG-002, FR-SG-004 | Versioned Gate templates, frozen requirements, owners/reviewers/dates, structured version references, private-file revision references, and explicit scan state |
| P4-04 — Review, decision, snapshot, and reopen | FR-SG-003, FR-SG-005, FR-SG-006, FR-SG-007 | Policy-driven review sequences, blockers, safe-default-denied exceptions, immutable snapshots, preserved prior approvals, generic dependency invalidation, and controlled review cycles |
| P4-05 — Live My Work, activity, and Project controls | FR-PM-008, FR-PM-011, FR-PM-012, FR-CO-001, FR-CO-002, FR-CO-006 | Honest health state, policy-driven lifecycle controls, lessons/template feedback, internal comments/activity/attachments, live work projection, and complete `en`/`zh`/`zh-TW` UI/API copy for this phase |

FR-PM-007 is satisfied in Phase 4 through plan-baseline comparison and a
critical-task indicator, both explicitly allowed by its alternative wording.
This phase does not add a Gantt library, OpenProject integration, or complex
resource planning.

FR-CO-006 applies to every Phase 4 screen, API business error, notification
surface rendered by the application, and printable/exportable copy introduced
here. Actual mail transport, live notification delivery, external-user portal
surfaces, and later domain screens remain owned by their delivery phases.

### 2.2 Explicit remapping

| Requirement | Delivery phase | Reason |
|---|---:|---|
| FR-PM-002 | 8 | ERPNext quotation/sales-order triggered draft creation requires integration ownership, source mapping, idempotency, and sandbox facts |
| FR-PM-010 | 8 | Purchase/time/expense/tool actuals are ERP-owned projections and cannot be invented locally |
| FR-SG-008 | 9 | Live reminders, escalation, and notification policy belong to notification/hardening delivery; Phase 4 may create queryable due/overdue work only |
| FR-SG-009 | 9 | Management portfolio bulk view is a portfolio/reporting capability, not the Project/Gate object vertical slice |
| FR-CO-003 | 9 | Supplier portal and external authorization are later external-collaboration scope |
| FR-CO-004 | 9 | Customer portal and externally binding approval are later external-collaboration scope |
| FR-CO-005 | 9 | Mail/in-app delivery, subscriptions, escalation, and mandatory audit notifications require the later notification service |
| FR-CO-007 | 9 | Meeting-minutes templates are a collaboration extension outside the minimum Project/Gate path |

The requirement IDs are preserved. Remapping changes only controller
allocation and does not waive the original acceptance criteria.

## 3. Facts frozen before implementation

- `EngineeringProject` is the Project aggregate root. It may hold references
  and read-only projections but never owns ERPNext transaction detail.
- Stable identity uses immutable UUID `global_id`; human `business_code` is not
  a cross-system identity. Every mutable aggregate uses an optimistic version.
- The Project state family remains
  `draft → proposed → active → on_hold → completed/cancelled`. Production
  transition authorities and prerequisites remain policy input, not hard-coded
  guesses.
- `GateInstance` owns the template version, requirement snapshot, evidence
  references, blockers, review records, exceptions, cycles, and immutable
  decision snapshots.
- A Gate snapshot must point to exact object/revision/hash versions. It cannot
  point to “latest,” and a reopen creates a new review cycle rather than
  overwriting prior approval.
- A file revision begins with its real scan state. `pending` or `failed` scan
  state cannot be represented as `clean` and cannot satisfy a requirement that
  explicitly requires trusted clean content.
- Browser traffic stays on same-origin `/api/npi/v1`; commands require
  authentication, Frappe CSRF, project/tenant authorization, idempotency where
  retry can duplicate effects, expected version, audit, and trace identity.
- External principals cannot approve or administer. UI hiding never substitutes
  for the server permission decision.
- Every user-visible source string is literal English and uses the shared
  Frappe-compatible translation chain with complete `zh` and `zh-TW` entries.
- No normal-user accepted path depends on Frappe Desk.

## 4. WorkItem vocabulary boundary

The existing specifications describe two different concepts and they must not
share one ambiguous persistence state machine:

1. **Domain WorkItem** is the persisted NPI object from `DOMAIN_MODEL.md` with
   semantic kinds `risk`, `issue`, `action`, and `decision_request`. Each kind
   retains its own controlled lifecycle while sharing context, owner, due date,
   severity, blocking, relations, and evidence.
2. **My Work item** is a read-only BFF projection that explains work assigned
   to the current user. Its presentation category may be `task`, `approval`,
   `blocker`, `risk`, `issue`, `decision`, or `integration`; it may project a
   Domain WorkItem, Gate assignment, evidence task, or later integration
   operation.

Phase 4 will rename/contract the current broad OpenAPI `WorkItem` view schema as
the My Work projection and define the persisted domain kinds separately. A
projection category is never written back as a domain status or permission.
Mappings must be explicit and tested; unknown source types fail closed rather
than being coerced to `task`.

## 5. Class-B rule holds

The following missing business facts pause only their production rule packages.
They do not block generic/versioned infrastructure, synthetic acceptance
fixtures, contracts, tests, UI, localization, or documentation.

| Held rule | Safe implementation boundary |
|---|---|
| Project numbering and authoritative Customer/Order source | Require an explicit unique `business_code` and typed references in Phase 4. Do not auto-number or claim ERP authority. ERP-triggered creation stays in Phase 8. |
| Production project/Gate template contents, durations, skip conditions, and required references | Implement versioned configurable templates with immutable published versions. Repository tests create clearly synthetic templates; no default production template is installed. |
| RACI role-to-approval mapping and segregation of duties | Store versioned assignment/review policies and enforce explicit policies. Do not infer that a project role grants approval. External users remain denied. |
| Disabled-member role and substitution validity | Permit only an existing membership identity to receive a non-expansive finite end date. Do not invent whether historical roles/substitutions are retained or when future/new relationships must be rejected until the authoritative temporal policy is supplied. |
| Domain WorkItem per-kind lifecycle details | Keep kinds distinct, validate shared invariants, and implement only transitions explicitly covered by the task contract. Do not install one convenience status machine for all kinds. |
| Project health/cost formula and thresholds | Support a versioned rule reference and honest `unassessed`/unavailable dimensions. Red requires reason and recovery plan. Do not fabricate green health or ERP actual cost. |
| Conditional-pass/waiver eligibility and authority | Default deny unless an explicit versioned policy names the exception type, eligible requirement, approver access, reason/risk/expiry/closure fields, and separation constraints. |
| Automatic Gate invalidation dependency matrix | Implement exact version dependencies and a generic invalidation evaluator. No production drawing/tooling/quality/ECN mapping is installed without a versioned policy. Manual controlled reopen remains available to authorized internal users. |
| Pause/cancel/resume/complete approvers and complete-check prerequisites | Implement policy hooks and fail closed when policy is absent. Do not mark projects complete while later file/handover/cost prerequisites are unavailable. |

External facts remain requested only through
`implementation/REQUIRED_INPUTS.md`. Production ERPNext access is prohibited.

## 6. P4-01 completed vertical slice

P4-01 passed its bounded technical gate at 2026-07-23T03:21:16Z. It
delivered:

- additive DocTypes/persistence adapters for a versioned Project Template,
  immutable published template version, Engineering Project, and instantiated
  Gate shell;
- framework-independent validation for template versioning, explicit Project
  references, unique business code, stable identity, optimistic concurrency,
  and atomic instantiation;
- a command that creates a Project draft from an explicit published template
  version and a query that returns the live Project Cockpit ViewModel;
- a deterministic test-only template that instantiates G0 and G1, carries
  explicit required-reference rules, and is never installed as a production
  default;
- project/tenant authorization, CSRF, input allowlisting, problem responses,
  trace ID, audit, retry-safe idempotency, and zero partial records on failure;
- the Project page switched from accepted-path fixture data to the live BFF,
  with loading, empty/not-found, no-permission, read-only, validation, conflict,
  retryable/final error, and success states; and
- complete English source, Simplified Chinese, and Traditional Chinese strings
  plus component, contract, permission, runtime, migration, E2E, accessibility,
  and visual evidence.

P4-01 does not propose/activate the Project, assign production RACI, decide a
Gate, claim ERP-created provenance, or report ERP cost.

The completed slice is deliberately narrower than full acceptance of
FR-PM-001, FR-PM-003, and FR-PM-004:

- FR-PM-001 has a generic versioned template, applicable Project types, and
  instantiated Gate shells, but template deliverables, roles, and standard
  duration remain for later slices and approved production policy;
- FR-PM-003 has an explicit tenant-scoped unique business code, owner, target
  SOP, and typed references, but the full production
  customer/product/part/tooling/order completeness rule and submission gate
  remain unimplemented; and
- FR-PM-004 has an exact immutable published-template snapshot, not the Project
  charter fields or immutable G1 charter baseline required for full
  acceptance.

## 7. Acceptance and evidence plan

### Domain and contract

- published template versions are immutable and edits create a new version;
- a Project records the exact template/version used, and later template changes
  do not change instantiated Gates;
- duplicate idempotency keys replay the original result and never create a
  second Project; a key reused with a different payload is rejected;
- business code uniqueness is enforced server-side without using it as
  cross-system identity;
- expected-version mismatch returns a conflict with no partial mutation;
- parent/child cycles and dependency cycles are rejected when P4-02 lands;
- evidence references name exact versions and unsafe scan states remain visible;
- Gate pass is blocked by missing P0 evidence/blockers, and exception paths are
  denied without an explicit policy;
- decisions/snapshots are immutable, and reopen preserves prior cycles; and
- transaction failure leaves no partial Project, Gate, review, audit, or work
  records.

### Permission and security

- guest and unrelated-project access fail;
- tenant mismatch and IDOR attempts fail without leaking object existence;
- view/contribute/approve/administer remain distinct server checks;
- external principals cannot approve/administer;
- CSRF, strict request fields/types, XSS-safe rendering, private-file access,
  audit redaction, and trace behavior are covered; and
- no `ignore_permissions`, direct SQL, raw browser DocType CRUD, core patch,
  production secret, or production ERP endpoint is introduced.

### Runtime, UI, and localization

- real Frappe install/migrate and idempotent migrate rerun pass;
- live BFF contract and permission cases run with disposable normal users;
- Project, Gate, and My Work accepted paths no longer claim fixture persistence;
- all required normal/non-normal states pass in `en`, `zh`, and `zh-TW`;
- keyboard, focus, labels, text-plus-shape status, 125%/150% layouts, and WCAG
  A/AA automation pass; and
- exact visual regeneration/comparison plus representative manual review prove
  the square, neutral, dense industrial baseline.

## 8. Migration and rollback

Phase 4 schema changes are additive. Migrations must be repeatable and cannot
install a production business template or backfill guessed ownership. Feature
exposure remains disabled until its complete vertical slice passes.

Before any retained Phase 4 data exists, rollback can disable the slice and
restore checkpoint `711b17d` on the disposable development Site. Once Project
or Gate history exists, keep the additive tables and immutable snapshots,
disable affected commands/routes, and deploy a reviewed forward fix. Never
uninstall the App or physically delete approval/history records as a production
rollback. ERPNext remains unaffected because Phase 4 creates no ERP write.

## 9. Expected change surface and risks

Expected files include additive `npi_core` DocTypes and domain/API modules,
`npi_core.bff` route registration, strict OpenAPI Project/Gate/My Work schemas,
Project/Gate/My Work data sources and pages, canonical Frappe CSV catalogs,
Phase 4 tests, migration/runtime scripts, traceability, and evidence. No new
production dependency is authorized by this anchor.

Primary risks are guessed business policy, mutable snapshots, IDOR, role/approval
conflation, non-atomic template instantiation, fake file cleanliness, frontend
fixture leakage, bundle growth, and incomplete trilingual states. Each is an
explicit test or release-gate item; the unresolved business policy packages
remain scoped holds rather than silent defaults.

## 10. P4-00 exit decision

**P4-00 PASS.** Phase 4 scope, non-scope, requirement allocation, vocabulary,
Class-B holds, first vertical slice, test evidence, migration, and rollback are
explicit. This decision activated P4-01 under the existing automatic-transition
authority.

## 11. P4-01 exit decision

**P4-01 PASS; P4-02 ACTIVE.** The bounded Project-template and live-cockpit
slice now provides:

- immutable published template versions and an exact template snapshot on each
  Project;
- atomic and retry-safe Project/G0/G1 creation with stable UUID identity,
  tenant-scoped business-code reservation, optimistic concurrency, audit, and
  idempotency replay/conflict handling;
- strict Project create/cockpit BFF contracts with CSRF, trace identity, and
  IDOR-safe owner/System Manager authorization;
- an explicit per-Site `npi_tenant_id` trust boundary that fails closed when
  configuration is absent or invalid and rejects tenant mismatch;
- a live industrial Project cockpit with reproducible loading, empty/not-found,
  no-permission, read-only, validation, conflict, retryable/final-error, and
  success behavior;
- 738 direct entries in each Frappe-compatible `zh` and `zh-TW` catalog for the
  shared literal-English source set; and
- exact visual baseline regeneration and comparison across all 141 cases. The
  global rebaseline was required because the shared catalog hash and shell copy
  are rendered outside the new live Project cases as well.

The command, runtime, permission, coverage, localization, visual, migration,
rollback, and remaining-scope evidence is recorded in
`implementation/evidence/phase-4/p4-01-validation.md`.

No production Project template, role mapping, reference-completeness policy, or
G1 charter baseline was installed. FR-PM-001, FR-PM-003, and FR-PM-004 remain
truthfully traced as foundation/partial rather than complete; FR-CO-006 remains
partial with P4-05 still responsible for the rest of the Phase 4 language
surfaces.

## 12. P4-02 completed boundary

P4-02 now owns Project membership and dated substitutes, explicit RACI
assignments without implicit approval authority, WBS parent/dependency/date/
milestone/progress behavior with cycle rejection, plan-baseline comparison and
critical-task indication, and distinct persisted
`risk`/`issue`/`action`/`decision_request` lifecycles with
project/stage/owner/overdue queries.

It does not add a resource optimizer, OpenProject dependency, guessed
production role-to-approval defaults, live notification delivery, or the full
My Work projection assigned to P4-05.

## 13. P4-02 exit decision

**P4-02 PASS; P4-03 ACTIVE.** The bounded Team, RACI, WBS, baseline, and
Domain WorkItem slice now provides:

- explicit Project membership, dated role and substitute assignments, and RACI
  without implying Gate approval authority;
- parent/child WBS, dependencies, owners, planned/actual dates, milestones,
  state, progress, graph-cycle rejection, immutable plan baselines, comparison,
  and explicit critical-task indication;
- distinct persisted `risk`, `issue`, `action`, and `decision_request` kinds
  with strict Project, stage, owner, and overdue queries;
- authorization-before-cursor-validation, an existing read-only Site key for
  signed cursors, fail-closed 503 behavior without configuration mutation, and
  Project-plus-tenant validation for every tenant-bearing identity/reference;
- a live Team/Plan/Work Items Project workspace with direct English-source,
  `zh`, and `zh-TW` coverage; and
- current exact visual evidence across all 147 cases because the rendered
  catalog version changed globally.

The cumulative Task Gate passed 63 directly affected Python tests, a fresh
real Frappe runtime, the complete eight-case P4-02 browser spec, supplemental
browser shards, forced and clean 147-case visual runs, six original-resolution
trilingual reviews, Task Diff/trace review, and independent release review.
Complete evidence is recorded in
`implementation/evidence/phase-4/p4-02-validation.md`.

`FR-PM-005`, `FR-PM-006`, `FR-PM-007`, and `FR-CO-002` remain truthful
foundations because their production assignment, template/bulk-scheduling,
planned-versus-actual, and unified My Work acceptance remains later scope.
`FR-PM-009` is technically verified only for its bounded Project-domain
acceptance. P4-03 is activated under the existing automatic-transition
authority; the complete Level 3 gate remains required at the later Phase/PR
boundary.

## 14. P4-03 completed boundary

P4-03 owns an independent versioned Gate Template aggregate, exact optional
bindings from new Project Template versions, one-time frozen Project Gate
requirement assignments, append-only exact WBS/File Revision evidence, and the
live trilingual Gate evidence workspace.

It does not add Gate review or approval authority, P0 normal-pass policy,
conditional pass, waiver, decision snapshots, reopen/invalidation behavior,
normal-user upload/download, production template contents, future evidence
resolvers, live notifications, or production ERPNext/scanner integration.

## 15. P4-03 exit decision

**P4-03 PASS; P4-04 ACTIVE.** The bounded Gate Template and controlled-evidence
slice now provides:

- deterministic, contiguous, immutable published Gate Template versions with
  applicable Project types, ordered requirement definitions, exact hashes, and
  historical reads after root disablement;
- legacy-compatible optional Gate Template references on Project Template
  Gate definitions without rewriting historical P4-01 snapshots;
- retry-safe one-time freezing of the exact Gate Template reference, explicit
  Gate due date, requirement owner/reviewer identities, dates, evidence kinds,
  actor, time, audit, and immutable snapshot;
- append-only exact same-Project/same-tenant WBS and private File Revision
  evidence with source version/hash checks, actor-bound idempotency, optimistic
  concurrency, and rollback;
- private File identity revalidation, real scanner-owned state, same-content
  cross-Project denial, and URL-free BFF metadata;
- authorization before protected-object resolution, including denial for an
  external Website User whose identity equals the stored Project owner; and
- a live industrial Gate evidence workspace with direct `en`, `zh`, and
  `zh-TW` normal/non-normal coverage.

The cumulative Level 3 gate passed the 276-Python/237-frontend aggregate before
the final two-file authorization-order repair, 20 directly affected tests
after that repair, two successful Site migrations, the complete P4-01/P4-02/
P4-03 real runtime, 153 non-visual browser cases, forced and clean exact
159-case visual matrices, trilingual original-resolution review, security,
Task Diff/trace, and independent release review. Complete evidence is recorded
in `implementation/evidence/phase-4/p4-03-validation.md`.

`FR-SG-001`, `FR-SG-002`, and `FR-SG-004` remain technically verified
foundations because production condition/skip policy, P0 normal-pass blocking,
future evidence resolvers, and decision-time snapshots remain P4-04 or later
scope. `FR-CO-006` remains a foundation until later external-user,
notification, email, print, and delivery surfaces exist. P4-04 is activated
under the existing automatic-transition authority. Phase 3 remains
`TECHNICAL_PASS_PENDING_UAT`.

## 16. P4-04 CLI-to-Cloud handoff checkpoint

P4-04 now retains a live but unaccepted implementation checkpoint: the
review/decision/exception/reopen domain and repository, controlled persistence,
strict BFF/OpenAPI/receipt surfaces, dependency invalidation hooks, focused
Frappe runtime, strict trilingual Review Room, reconstructable immutable audit,
and directly affected Level 1 tests.

The generated P4-04 plan is corrected to the authoritative `FR-SG-007` scope.
Dependency change preserves the prior decision, records exact
`invalidated`/`refreshed` events, creates a successor review cycle, and denies
downstream use. It does not automatically create an impact Domain WorkItem;
P4-05 owns work/lifecycle projection. The nullable action reference remains
only for backward-compatible reads.

`FR-SG-003`, `FR-SG-005`, `FR-SG-006`, and `FR-SG-007` remain
`IN_PROGRESS_P4_04`. Passing Level 1 evidence includes 116 Gate Review Python
tests, the focused live Frappe runtime, 93 frontend parser/Review Room tests,
four affected E2E cases, complete 1740-entry direct Chinese catalogs, and three
forced/clean exact trilingual normal-state visuals.

This evidence does not pass the atomic task. The complete P4-04 state-specific
E2E/visual matrix, coverage/build/audit, migration/runtime compatibility,
Task Diff/security/trace review, Level 2 Task Gate, and triggered Level 3
remain pending. Resume only P4-04 from
`implementation/evidence/phase-4/p4-04-cloud-checkpoint.md`; P4-05 is not
activated. The prior P4-03 Level 3 evidence remains valid and must not be
rerun solely to reconstruct this handoff.
