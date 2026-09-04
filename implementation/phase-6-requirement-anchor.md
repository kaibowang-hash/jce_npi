# Phase 6 Requirement Anchor — Tooling, Capacity, Import, and Export

Status: **ANCHORED — P6-00 LEVEL 2 PASS**

Anchor date: 2026-08-07

Controller phase: 6 — Tooling Domain

Compatibility milestone: M5 — Tooling

Starting checkpoint:
`ce401b87612c946225ef0106fb344cfdcfb21190`

## 1. Authority and bounded outcome

This anchor applies the V1.2 continuous-delivery authority to the reconciled
Tooling scope in `FR-TL-001..018`, `FR-TX-001..020`, `UX-004`, `UX-007` and
`UX-016`. It is based on the current requirement trace, M5 backlog and roadmap,
the accepted reconciliation addendum, Tooling/domain specifications, data
ownership contract, controlled XLSX specification and scoped Decision Requests.

The bounded demonstrable Phase 6 path is:

> register why a Project needs Tooling -> reference or create one logical
> Tooling Master through versioned Applicability -> track every physical Set ->
> define exact Revision/cavity/insert/process/specification structure -> expose
> manufacturing, supplier, defect, process-baseline and capacity truth ->
> freeze acceptance and prepare an honest asset execution request -> ingest a
> 43-column customer workbook through immutable preview/provenance -> export
> only the actor's controlled selection or filtered object package

Phase 6 owns NPI Tooling development, engineering specifications, versions,
physical-set collaboration, customer intake, milestones, defects, process
baselines, capacity scenarios, acceptance evidence and import/export truth. It
does not move formal Supplier, PO, receipt, invoice, actual cost, Asset,
location, shot count, maintenance, inventory, production or finance ownership
from ERPNext.

## 2. Requirement allocation and atomic order

| Atomic task | Compatibility task | Primary requirements | Truthful delivery boundary |
|---|---|---|---|
| P6-01 — Part, Requirement, Master, Applicability and cockpit | M5-01 | FR-TX-001, FR-TX-002, UX-004; FR-TL-001, FR-TL-003 foundation | Distinct stable identities, versioned cross-Project/product/part Applicability and dense live cockpit; no invented Tooling lifecycle command |
| P6-02 — Customer-owned intake and physical Sets | M5-02 | FR-TX-003; FR-TL-004 | Ownership/custody/authorization, intake inspection/difference evidence and one record per physical Set; no asset success claim |
| P6-03 — Revision, specification, cavities, inserts and process chain | M5-03 | FR-TX-004..008; FR-TL-002, FR-TL-003, FR-TL-006 | Immutable versioned specification structure, cavity/part mapping, inserts/changeovers, multi-shot/overmold chain, external IDs and controlled material/color/compliance links |
| P6-04 — Manufacturing, supplier and ERP cost projection | M5-04 | FR-TL-005..008 | Internal make/buy, supplier milestone, design-release dependency and explicit unavailable/read-only ERP procurement/cost projection; no supplier portal or ERP mutation |
| P6-05 — Defects, process baselines, capacity and lifecycle controls | M5-05 | FR-TX-009..011, FR-TX-019, FR-TX-020; FR-TL-009, FR-TL-010 foundation, FR-TL-017, FR-TL-018 | Defect/action truth, Standard/Trial Actual/Approved Baseline separation and versioned Capacity Scenario; exact lifecycle commands and production red semantics remain held |
| P6-06 — Acceptance and asset execution request | M5-06 | FR-TL-011..016 | Immutable acceptance evidence and Mock/sandbox-ready asset request/projection conditions; real asset creation/movement/maintenance/cost remains Phase 8 |
| P6-07 — Specialized Tooling List controlled import | M5-07 | FR-TX-012..018, UX-016 | Eight-step XLSX upload/detect/map/transform/validate/preview/execute/audit flow with partial truth, correction, retry and rollback denial; no production mapping activation |
| P6-08 — Selection/filter and controlled object-package export | M5-08 | UX-007 | Reuse the accepted dense-grid foundation for authorized selection/filter export with exact versions, redaction, audit and language; no arbitrary data dump |

`ANCHORED_P6_XX` means allocated, not implemented or accepted. Later task
evidence must replace the anchored status truthfully.

## 3. Frozen identity and ownership boundaries

### 3.1 Part, Requirement, Master and Applicability

- `Part` and `PartRevision` are NPI engineering identities until formal Item
  mapping; an EBOM line or spreadsheet row is not a substitute Part aggregate.
- `ToolingRequirement` records why a Project needs Tooling, including new,
  customer-owned intake, copy/additional set, modification, repair or capacity
  need. It does not become the logical tool or a physical set.
- `ToolingMaster` is the reusable logical identity. A shared tool is referenced
  through versioned/effective `ToolingApplicability`; it is not copied per
  Project, product, model or part.
- `ToolingRevision` is versioned engineering/design/manufacturing truth.
  Release or supersession never silently changes a physical Set.
- Every `ToolingSet` is one physical copy with independent serial/source
  Revision/supplier/custody/location and future Asset mapping. Planned or
  copied quantity never replaces Set records.

### 3.2 Cavity, insert and process structure

- `CavityMap` maps exact cavity identifiers to Part Applicability and preserves
  enabled/sealed state and cavity-level results.
- `InsertApplicability` records the exact insert/changeover version, applicable
  model/part, change time and validation state.
- Dual-shot, two-shot and overmold behavior uses an ordered versioned process
  chain with parent/overmold relationships and machine requirements; blank
  Tooling numbers, remarks or concatenated codes are never authority.
- Customer/SN/KW/TH/supplier identifiers are one-to-many external identities
  with source and effectivity, not alternate primary keys.

### 3.3 Process and capacity truth

- Customer Standard/Provided Specification, TP Trial Actual and immutable
  Approved Process Baseline are three different facts. `not_measured` remains
  honest until an exact Trial context records an actual.
- Values retain unit, source, context, effective version and evidence.
  Comparison uses an exact versioned tolerance/rule and returns only
  `not_measured`, `within_tolerance`, `outside_tolerance` or `unavailable`.
- `DR-REC-002` blocks final production exception-color semantics only. The
  system must not color every nonzero difference as abnormal.
- Capacity Scenario inputs explicitly version available hours, working days,
  OEE, yield, cycle, cavity count, usage and effective physical sets. Outputs
  include part/day/month, assembly units, bottleneck and gap. No hidden 22-hour,
  26-day or similar constant is permitted.

### 3.4 ERPNext boundary

- NPI One owns Tooling development/specification/revision, intake evidence,
  NPI milestones, defects, acceptance snapshot and capacity scenarios.
- ERPNext owns formal Supplier, PO/receipt/invoice, actual cost, Asset ID/state,
  physical location, shot count, maintenance, spares/inventory and execution.
- Phase 6 may expose explicit unavailable/read-only projections and create
  operation-specific Mock/sandbox-ready execution requests. It cannot contact
  production ERPNext or report an Asset/movement/cost result without target
  confirmation. Phase 8 owns the real adapter and reconciliation.

## 4. Lifecycle hold

`DR-REC-010` remains `PENDING_PRODUCT_OWNER`. Requirement, Revision and each
physical Set require separate versioned lifecycle policies; no shared
convenience status is allowed. Until exact states/transitions/skip/reopen/
terminal rules and authorities are approved:

- P6 tasks may create immutable identity/version structures, exact
  Applicability, evidence, drafts, explicit unavailable capabilities and
  synthetic policy tests;
- they may not install production lifecycle defaults or expose formal
  transition commands as accepted behavior; and
- release/manufacturing/acceptance prerequisites must fail closed where an
  exact approved lifecycle policy is required.

This scoped hold does not block identity, provenance, parser, capacity or
read-only capability work.

## 5. Controlled Tooling List boundary

P6-07 must follow the repository `xlsx-tooling-import` Skill and
`docs/TOOLING_LIST_IMPORT_SPEC.md`:

1. upload the exact private File Revision and immutable SHA-256/batch truth;
2. passively inspect archive/sheet/formula/external-link/image facts with
   bounded resources and no macro/formula execution or linked-content fetch;
3. detect headers, data/shared-tool/summary regions without fixed row numbers;
4. apply an exact versioned 43-column mapping while retaining every raw value;
5. validate types, references, duplicates, units, formula errors, embedded
   state, unmapped fields and ambiguous relations;
6. preview create/update/skip/error/confirmation results before execution;
7. execute asynchronously with actor-bound idempotency and explicit per-row,
   per-field partial truth; and
8. retain provenance, correction/retry/reconciliation and policy-bound
   rollback truth.

The current 43-column CSV is a reviewed proposal, not an approved production
mapping. `DR-REC-007` blocks only production semantic activation.
`DR-REC-008` denies destructive rollback after downstream use; a forward
correction preserves history. A/B/C remains `Legacy Grade`, `New Tooling` is
not a number, `#REF!` never becomes approved capacity, physical Sets do not
collapse to a count and uncertain images require human confirmation.

The existing 531-line passive inspector and adversarial repository tests are
reusable parser-safety foundation only. There is no runtime upload/import API,
mapping engine, preview, batch persistence or execution job to relabel as
P6-07 completion.

## 6. Existing-capability audit

- NPI Core has no Tooling/Part/Applicability/Revision/Set/Cavity/Insert/
  Capacity DocType, repository, BFF route or product runtime.
- `frontend/src/pages/tooling-page.tsx` is a deterministic prototype. Its
  commands explicitly remain in memory, persist no audit and prepare no real
  ERPNext request. It is UX/reference evidence, not a live Tooling slice.
- The existing industrial shell, Object Page, local icon/action adapter,
  DenseGrid personalization, File Revision, audit, idempotency, Project
  authorization, route-switch and Frappe-compatible trilingual chain are
  reusable mechanisms. Reuse does not inherit domain permission or lifecycle
  authority.
- `contracts/data-ownership.yaml` has a correct coarse Tooling split but lacks
  the distinct Requirement/Master/Applicability/Revision/Set/import/capacity
  field rows needed by each product task.
- No production ERPNext endpoint/credential, sanitized customer workbook,
  approved lifecycle policy or production column overlay is present.

## 7. Task verification and Gate order

Each product task uses four checkpoints unless its accepted plan proves a
smaller complete vertical slice:

1. Requirement/domain/existing-capability audit and exact task plan;
2. pure domain/contract/additive metadata;
3. repository/BFF/permission/idempotency/audit and reusable SPA/i18n evidence;
4. controlled disposable-Site runtime, Level 2 Task Gate and transition.

P6-07 additionally requires the XLSX archive/mapping/provenance/partial-result/
correction/retry/rollback matrix. Complete ordinary CI must pass before every
controlled-Site boundary. Diagnostics remain closed except one governed
response-neutral run for a uniquely bounded opaque failure. Phase 6 ends with
a cumulative Level 3 `release-gate` review.

## 8. Changed-files to affected-tests map

| Change boundary | Minimum affected evidence |
|---|---|
| Part/Requirement/Master/Applicability identity | domain identity/non-collapse, Project/tenant authority, exact version and shared-master tests |
| physical Set/customer intake | ownership/custody, per-set identity, inspection/difference evidence, IDOR and retained-file tests |
| Revision/cavity/insert/process/specification | immutable version, cavity/part, sealed cavity, insert/changeover, process-chain and external-ID tests |
| manufacturing/supplier/cost projection | release prerequisite, milestone/evidence, explicit unavailable/read-only ERP and no-fake-success tests |
| process baseline/capacity/defect | fact-layer separation, `not_measured`, exact tolerance, no-hidden-constant, scenario recompute and blocker tests |
| acceptance/asset request | immutable checklist, authority, Mock/sandbox contract, node result, retry/reconciliation and no-formal-ID tests |
| XLSX import | archive safety, regions, 43 columns, raw provenance, images/formulas, preview, partial/replay/correction/rollback tests |
| selection/filter/export | exact selection/filter semantics, permissions/redaction/audit, locale headers and immutable-reference tests |
| every live SPA surface | component/state/accessibility, direct English/zh/zh-TW, mixed-language and affected visual matrix |

## 9. Migration and rollback

- P6 metadata is additive and installs no production policy, workbook mapping,
  external adapter, business fixture or ERPNext identifier.
- Before retained task history, a disposable environment may restore the task
  checkpoint and migrate fresh.
- After retained identity/version/Set/evidence/import/acceptance/audit history,
  rollback disables only the affected task routes/jobs and deploys a reviewed
  forward fix. It never deletes shared Masters, physical Sets, released
  Revisions, source provenance, import results or ERP mappings.
- Import rollback is a separate audited command with exact eligibility.
  Downstream-used data is corrected forward until `DR-REC-008` approves a more
  specific cutoff.

## 10. Automatic transition

P6-00 passes its documentation/trace Task Gate. Standing authority activates
only `P6-01 — Part, Tooling Requirement, Master, Applicability aggregate and
cockpit` within the frozen no-lifecycle-command boundary. P6-02 through P6-08
remain inactive until their predecessor Task Gates pass.
