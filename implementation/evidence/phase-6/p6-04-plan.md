# P6-04 Plan — Manufacturing, Supplier Milestones and ERP Cost Projection

Recorded: `2026-08-08T11:41:29Z`

Starting product checkpoint:
`4ab478259724a8507891f24b33f858ffe9a117a0`

Starting synchronized controller checkpoint:
`ae4bda0dce52e7f26f51c1a36d452bae10c53754`

Starting exact-SHA ordinary CI:
`31255185225` (`PASS`; repository `93097413900`, visual `93097413875`,
controlled runtime `93097414162` correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/CONTRACT/METADATA FOUNDATION NEXT**

Requirements:

- `FR-TL-005`;
- `FR-TL-006`;
- `FR-TL-007`; and
- `FR-TL-008`.

Applicable Skills:

- `repo-discovery`;
- `npi-domain-guard`;
- `frappe-safe-change`;
- `erpnext-integration`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Sources and existing-capability conclusion

The audit used the Phase 6 requirement anchor, M5-04, the four current trace
rows, matching DOCX and Pack requirements, `DOMAIN_MODEL.md`,
`TOOLING_AND_TRIAL.md`, `ERPNEXT_INTEGRATION.md`, the accepted reconciliation
decisions, P6-01 through P6-03 Level 2 evidence, the complete ownership,
OpenAPI and integration-event contracts, the live Tooling repositories and
strict SPA data sources, and the deterministic Tooling prototype.

Repository truth is:

- P6-03 provides immutable Tooling Revision lineage and exact controlled
  Document Revision references. It intentionally does not approve or release
  a Tooling Revision or authorize manufacturing;
- the controlled-document domain can prove one exact revision's released
  state, lifecycle version, release event and release snapshot hash. This is
  reusable design-input evidence, not Tooling lifecycle authority;
- the live Tooling Revision and physical-Set projections correctly return
  `formal_supplier_unavailable` and `erp_projection_unavailable`. No formal
  Supplier, PO, receipt, invoice or actual-cost repository exists;
- `frontend/src/pages/tooling-page.tsx` contains deterministic prototype
  supplier, PO, cost, milestone and release values and in-memory preparation
  dialogs. Those values are visual reference only and cannot be relabelled as
  live P6-04 truth;
- NPI One owns the internal sourcing plan, engineering estimate/budget fact,
  NPI milestone schedule/observation and exact evidence. ERPNext owns the
  formal Supplier, purchasing documents, receipts, invoices and actual cost;
- no supplier identity/authentication policy, supplier portal, production
  ERPNext endpoint/credential, projection adapter or confirmed target result
  is present; and
- `DR-REC-010` still blocks Tooling Requirement/Revision/Set lifecycle states,
  transition commands, manufacturing release authority and formal Gate-ready
  claims. It does not block immutable planning, milestone observations,
  controlled-document release evidence or honest read-only availability.

The safe path is additive and needs no architecture ADR. It must keep internal
planning separate from ERP execution and return explicit unavailable truth
when the read-only ERP projection has no confirmed source observation.

## 2. Scope and truthful completion boundary

P6-04 delivers this minimum complete vertical slice:

> open an authorized Project and Tooling Master -> select one exact immutable
> Tooling Revision -> append an immutable manufacturing-plan revision with an
> internal make/buy/hybrid decision, responsible Project member, engineering
> estimate, budget fact, exact released controlled-document evidence roles and
> an ordered milestone plan -> observe the exact design-document release
> dependency without declaring the Tooling Revision released -> append an
> internal-user-reported milestone progress/evidence observation -> reopen the
> live workspace and inspect the retained plan/observation history together
> with an explicit unavailable or strictly read-only formal Supplier,
> PO/receipt/invoice/actual-cost projection

The slice separates three facts:

1. an NPI-owned internal sourcing and budget plan;
2. NPI-owned milestone schedule/progress/evidence reported by an authorized
   internal Project actor, including milestones whose responsible-party kind
   is `supplier`; and
3. ERPNext-owned formal Supplier/procurement/cost truth, which the SPA can
   never edit and the default production repository cannot invent.

An exact released controlled-document observation proves only that referenced
design or commercial evidence was released. `manufacturingAuthorization`
remains unavailable while the Tooling Revision lifecycle policy and authority
are not approved. The plan does not calculate or claim a G3 pass, funding
approval, PO readiness, supplier acceptance or ERP synchronization success.

Final trace status is evidence-driven. The expected honest boundary is:

- `FR-TL-005`: technically verified foundation for DFM/proposal/quotation/
  budget evidence, make/buy planning and responsible ownership; formal funds,
  PO and G3 readiness remain unavailable;
- `FR-TL-006`: strengthened technically verified foundation through exact
  controlled-document release evidence and a fail-closed Tooling
  manufacturing-authorization capability; formal Tooling lifecycle release
  remains held by `DR-REC-010`;
- `FR-TL-007`: technically verified foundation for milestone schedule,
  observations and exact evidence; external supplier login/update remains
  unavailable; and
- `FR-TL-008`: technically verified foundation for a closed read-only ERP
  projection and deterministic aggregation contract; real adapter sync and
  target-confirmed data remain Phase 8.

## 3. Non-scope and scoped holds

P6-04 does not install or infer:

- Tooling Requirement, Revision or Set lifecycle states, transitions,
  skip/reopen/terminal rules, approval, release or manufacturing authority
  (`DR-REC-010`);
- a G3 Gate policy, Gate pass/readiness calculation, approved funding state,
  approved Tooling solution or PO prerequisite decision;
- a supplier account, supplier Project membership, portal, external upload,
  external signature, notification or supplier-submitted actor claim;
- a formal Supplier master record, supplier edit, PO line mutation, purchase
  execution/change request, receipt, invoice, payment or actual-cost write;
- a production ERPNext connection, endpoint, credential, secret, direct
  database access, Outbox dispatch, Webhook, Inbox row, retry, replay,
  reconciliation or successful target result;
- a formal cost-type vocabulary. Read-only source cost codes remain exact
  ERP business data and are grouped without reinterpretation;
- an ERP Asset, location, movement, shot count, maintenance, acceptance or
  asset execution request (`P6-06` and Phase 8);
- an automatic project-health change, recovery plan, blocker, defect, Trial,
  capacity result or process-baseline transition (`P6-05` and Phase 7);
- a production Tooling-list mapping/import or workbook-derived supplier,
  milestone, budget, PO or cost value (`P6-07`); or
- any business fixture, default plan, default milestone template, production
  policy, mapping, adapter, credential or external mutation.

The existing deterministic prototype remains isolated from live routes. P6-04
must not copy its `K-Tech`, `PO-260144`, cost, completed milestone or released
Revision claims into the live product path.

## 4. Frozen domain design

### 4.1 Immutable manufacturing-plan revisions

`ToolingManufacturingPlanRevision` is an append-only NPI-owned planning
snapshot. It contains:

- stable `planGlobalId`, exact `globalId`, `planVersion`, direct predecessor
  identity/hash and immutable Project/Master scope;
- one exact Tooling Revision identity and snapshot hash. A plan does not alter
  that Revision or become its lifecycle state;
- `sourcingStrategy`: `internal`, `supplier` or `hybrid`. This is an internal
  planning decision, never a formal Supplier assignment;
- one exact current Project-member responsibility snapshot. It records
  responsibility only and grants no approval or command authority;
- optional NPI engineering-estimate and budget values as canonical decimal
  strings with one ISO-style three-letter currency. They are not committed or
  actual ERP cost;
- zero or one exact released controlled Document Revision per evidence role:
  `dfm`, `tooling_proposal`, `quotation` and `budget`. The caller supplies exact
  revision and release preconditions; the server reauthorizes Project scope,
  locks and revalidates current released lifecycle/event/hash truth;
- the server-resolved release observation for every design Document Revision
  already frozen in the exact Tooling Revision. Missing, unreleased, obsolete,
  superseded, cross-Project or hash-mismatched inputs remain explicit blocked
  evidence and cannot be represented as released; and
- a bounded ordered milestone plan plus reason, actor, request, trace and
  snapshot hashes.

Plan succession is direct and exact. A successor increments the plan version,
references the immediate predecessor and its snapshot hash, preserves the
stable plan identity and cannot overwrite earlier evidence, budget or schedule
facts. It may reference a later exact Tooling Revision only by appending the
new complete snapshot.

### 4.2 Milestone plan and observation truth

Each planned milestone has an immutable UUID, one closed category from:

- `design`;
- `material_preparation`;
- `heat_treatment`;
- `machining`;
- `assembly`;
- `trial_preparation`; or
- `delivery`.

It also freezes planned start/finish dates, `internal` or `supplier`
responsibility kind, an exact internal Project-member responsibility only
where applicable, and predecessor milestone UUIDs. The complete milestone
dependency graph must be bounded, same-plan, duplicate-free and acyclic.
Category and responsibility kind are not Tooling lifecycle states.

`ToolingManufacturingMilestoneObservation` appends, but never edits, one exact
plan-revision/milestone observation. It freezes:

- observation version and exact predecessor observation;
- progress percentage, optional actual start/finish, bounded risk/note text
  and the plan/milestone snapshot hashes observed;
- zero or more exact clean private File Revision evidence references with
  roles `progress_evidence`, `technical_evidence` or `delivery_evidence`; and
- the authenticated internal NPI actor, request/trace, time and immutable
  snapshot hash.

An observation whose milestone responsibility kind is `supplier` still has an
internal NPI actor unless a future approved supplier portal authenticates a
different principal. It must never be described as supplier-submitted.
Planned/actual/progress facts remain separate fields; no unapproved Tooling
lifecycle state is derived from them.

### 4.3 Design-release and manufacturing-authorization capabilities

The workspace exposes two separate capabilities:

- `designReleaseEvidence` is `satisfied` only when every exact design Document
  Revision in the selected Tooling Revision resolves to the exact current
  released lifecycle version, release event and release snapshot hash. It is
  `blocked` for an empty set, missing/mismatched reference or any non-released
  lifecycle; and
- `manufacturingAuthorization` remains `unavailable` with
  `tooling_lifecycle_policy_unavailable` until `DR-REC-010` supplies an exact
  Tooling Revision policy and authority.

No P6-04 command accepts either capability, a caller-supplied release state or
an approval flag. Every write re-resolves its exact dependencies.

### 4.4 Formal Supplier and ERP procurement/cost projection

`ToolingProcurementCostProjection` is a closed discriminated read-only union:

- the default `unavailable` branch contains `sourceSystem: ERPNEXT`,
  `editableIn: ERPNEXT`, `state: unavailable` and
  `reasonCode: erp_projection_unavailable`; and
- a future/injected `available` branch requires a target-confirmed observation
  time/version plus exact formal Supplier, PO, receipt, invoice and actual-cost
  source identities. It remains read-only and cannot contain a write
  capability, credential, endpoint or mutable private URL.

Available projection rows retain ERP source IDs, target versions, dates,
currencies, amounts, formal supplier identity and raw source cost-type codes.
The pure projection domain deterministically aggregates actual cost by exact
Tooling Master, formal Supplier and raw ERP cost-type code without inventing a
cost taxonomy or changing source rows. Duplicate source identity/version,
currency mismatch, invalid decimal, missing target confirmation or summary
mismatch fails closed.

The production Frappe repository has no P6-04 ERP adapter and therefore
returns only the unavailable branch. Pure contract/repository tests may inject
a closed read-only reader to prove strict parsing and aggregation; no business
fixture or projection row is installed by migration or controlled runtime.

## 5. Planned additive BFF contract

The closed BFF adds only:

| Path | Purpose |
|---|---|
| `GET /projects/{projectId}/tooling/{toolingMasterId}/manufacturing-plans` | read bounded plan revisions, milestone observations, exact release capabilities and ERP projection truth |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/manufacturing-plans` | append an initial or direct successor immutable plan revision |
| `GET /projects/{projectId}/tooling/{toolingMasterId}/manufacturing-plans/{planRevisionId}` | read one exact authorized immutable plan revision and observations |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/manufacturing-plans/{planRevisionId}/milestones/{milestoneId}/observations` | append one exact internal-user-reported milestone observation and clean evidence snapshot |

Unsafe commands require authenticated session, CSRF, UUID request ID,
actor-bound idempotency and exact optimistic/predecessor/release
preconditions. System Manager is management transport only and does not become
design, funding, supplier or manufacturing approval authority. There is no
Supplier route and no ERP write, dispatch, retry or reconciliation route.

An independent P6-04 fail-closed route switch covers only these four paths and
projection activation. Disabling it leaves P6-01 through P6-03 routes and
retained history untouched.

## 6. Persistence and ownership plan

Checkpoint 1 adds only two guarded DocTypes:

- `NPI Tooling Manufacturing Plan Revision`; and
- `NPI Tooling Manufacturing Milestone Observation`.

Nested evidence, design-release, money and milestone structures are retained
as bounded canonical immutable snapshots with independent UUIDs and exact
hashes. Generic Desk create/update/delete, export, print, share, raw private
URLs and arbitrary JSON mutation remain denied.

The existing `NPI Tooling Command Idempotency` and append-only audit mechanism
are reused with exactly two new operation/target pairs:

- `tooling_manufacturing_plan.create`; and
- `tooling_manufacturing_milestone.observe`.

`contracts/data-ownership.yaml` adds NPI ownership for internal sourcing,
estimate/budget planning, milestone schedule/observation and exact evidence;
controlled-document lifecycle remains owned by the document domain. Formal
Supplier, PO/receipt/invoice/actual cost and formal transaction status remain
ERPNext-owned and read-only. Tooling lifecycle/manufacturing authority remains
`FUTURE_APPROVED_TOOLING_POLICY`.

Migration is additive and idempotent. It creates no plan, milestone,
observation, Supplier, ERP projection, policy, default, backfill, mapping,
adapter, credential or external connection.

## 7. Live Tooling workspace and i18n plan

- The live selected-Master workspace gains a dense manufacturing/supplier
  surface adjacent to the existing Revision/specification surface. It does not
  activate deterministic prototype values.
- A plan tree/table/inspector shows sourcing strategy, exact Tooling Revision,
  estimate/budget, responsibility, evidence coverage, milestone dependency,
  observation lineage and exact hashes.
- Design-release evidence, manufacturing authorization, formal Supplier and
  ERP procurement/cost are separate labelled capability sections. One cannot
  make another appear available.
- Formal Supplier, PO, receipt, invoice and actual cost are read-only. With the
  production reader absent they render explicit unavailable source/reason
  truth and no empty zero, stale fake row, optimistic success or edit action.
- Internal users may append plan/observation records only from server-returned
  capabilities. A supplier-responsible milestone is labelled as internally
  reported; no supplier login or upload affordance is shown.
- One context has at most one primary action. G3 pass, Tooling release,
  manufacturing start, ERP mutation and supplier actions are absent or
  explicitly unavailable, never enabled placeholders.
- Normal, empty, loading, no-permission, read-only, unavailable, validation,
  release-blocked, conflict, processing and retry states are explicit.
  Keyboard, focus, labels and non-color-only state are mandatory.
- Every visible source string is literal English through `t()` with direct,
  complete `zh` and `zh-TW` coverage. Business data, codes, source IDs,
  currency and units use the existing language-exemption boundary only where
  allowed.

## 8. Planned checkpoints

1. **Domain/contract/metadata foundation** — pure immutable plan/milestone/
   observation, release-evidence, read-only ERP projection/aggregation
   invariants, two guarded additive DocTypes, ownership rows, receipt values,
   closed OpenAPI schemas and domain/metadata/contract/security tests; no
   active route or production projection.
2. **Repository/BFF checkpoint** — Project-first bounded reads and narrow
   commands, exact Revision/member/document/release/file containment,
   transaction, idempotency, audit, injected read-only projection boundary,
   independent route switch and API/IDOR/no-ERP-write tests.
3. **Live workspace checkpoint** — strict data source, dense plan/milestone/
   evidence/release/ERP sections, complete trilingual/accessibility/state and
   affected visual tests; deterministic prototype remains isolated.
4. **Controlled runtime and Task Gate** — disposable-Site immutable plan
   successors, milestone dependency/observation/evidence, release dependency,
   explicit ERP unavailability, replay/conflict/rollback/IDOR and independent
   route-disable proof, complete ordinary CI and P6-04 Level 2.

Complete ordinary CI is mandatory before a controlled-Site boundary.
Diagnostics stay closed unless an opaque exact-SHA failure activates one
governed response-neutral diagnostic cycle under standing authority.

## 9. Requirement to code to test to evidence

| Requirement | Planned delivery | Required evidence |
|---|---|---|
| `FR-TL-005` | immutable sourcing/estimate/budget/responsibility plan and exact released DFM/proposal/quotation/budget evidence roles; formal funds/PO and G3 readiness unavailable | plan succession/hash/money/member/evidence coverage, no approval/Gate/ERP claim, UI and runtime; truthful foundation status |
| `FR-TL-006` | exact Tooling Revision and controlled design Document release observation separated from unavailable Tooling manufacturing authorization | exact lifecycle/event/hash, missing/unreleased/mismatch denial, no caller release flag, UI and runtime; retained foundation status |
| `FR-TL-007` | ordered acyclic design/material/heat-treatment/machining/assembly/trial-preparation/delivery milestones plus internal observations and clean evidence | category/order/dependency/progress/evidence/replay/IDOR tests, internal-reporter label, no supplier portal, UI and runtime |
| `FR-TL-008` | closed unavailable/read-only ERP Supplier/PO/receipt/invoice/actual-cost projection and deterministic exact-code aggregation | no write route, unavailable default, injected read-only strictness, target confirmation/duplicate/currency/aggregation tests, UI and controlled unavailable runtime; Phase 8 dependency retained |

Final evidence will be recorded in
`implementation/evidence/phase-6/p6-04-validation.md`.

## 10. Changed-files to affected-tests

| Expected change surface | Minimum direct checks |
|---|---|
| P6-04 pure domain | plan predecessor/hash, sourcing/money/member, evidence roles, milestone graph/observation lineage, design release and ERP read-only aggregation |
| two additive DocTypes and Tooling validation | exact parent/tenant containment, immutable snapshots, denied generic CRUD/delete, receipt values and additive/idempotent migration |
| OpenAPI and data ownership | parse/reference/closed schemas, exact-or-unavailable release and ERP unions, ownership and no fake Supplier/PO/cost/manufacturing success |
| Tooling repository/API/security/BFF | Project-first authorization, exact Master/Revision/member/document/file containment, replay/conflict/audit/rollback/IDOR, injected read-only reader and independent switch |
| Tooling data source and live workspace | strict parser/transport, plan/milestone/release/ERP states, accessibility, no prototype leakage and read-only source truth |
| catalogs/styles | literal English plus direct `zh`/`zh-TW`, terminology/mixed-language, industrial boundary and affected visual matrix |
| runtime verifier/workflow | plan successors, milestone graph/observation/evidence, released/unreleased dependency, explicit ERP unavailable, replay/rollback/IDOR and route disable/recovery |
| controller/evidence | YAML, V1.2 reconciliation, Task Diff Review and `git diff --check` |

## 11. Migration, rollback and exit

Before retained P6-04 rows exist, a disposable environment may restore the
starting product checkpoint and migrate fresh. After retained history exists,
rollback disables only P6-04 routes and projection activation, preserves every
plan revision, milestone, observation, evidence, audit and idempotency receipt,
and uses a reviewed forward repair. It never rewrites a P6-01 Master/
Applicability, P6-02 Set/intake/evidence, P6-03 Tooling Revision/specification/
process-chain/binding, controlled Document lifecycle or external ERP object.

The audit passes. Autopilot may start only checkpoint 1, the pure domain,
closed contract and additive metadata foundation. Repository routes, live SPA
activation, controlled-Site execution and every production ERPNext behavior
remain inactive until their preceding checkpoints pass. P6-05 and later
behavior remains inactive.
