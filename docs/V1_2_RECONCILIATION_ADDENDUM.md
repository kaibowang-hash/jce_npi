# V1.2 DOCX–Execution Pack Reconciliation Addendum

Status: `ACCEPTED_ADDITIVE_RECONCILIATION`

Date: 2026-07-25
Append-only amendment: 2026-07-27

## 1. Authority and intent

This addendum implements the user-directed reconciliation based on:

- `docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`;
- the repository V1.2 Execution Pack;
- the 2026-07-25 reconciliation report supplied with the instruction to
  proceed; and
- the user-approved 2026-07-26 amended autopilot plan, which adds
  `FR-UX-043` to UX-A3/R1-05 without rewriting prior evidence; and
- `docs/Brand Asset/Brand Asset Instruction.csv` and the exact assets beside
  it, which are the sole authority for brand-asset use.

It is additive. It does not discard completed Phase 4 work, rewrite the
checkpointed P5-01 backend slice, change stable internal identifiers, connect
production ERPNext, or silently decide a Class-B business rule.

The earlier Pack-only execution decision is superseded for requirement
completeness: every original DOCX requirement ID is now retained in the
machine-readable Pack. Existing Pack-only normalized IDs remain valid aliases
or additional requirements.

## 2. Reproduced inventory

Deterministic extraction of the authoritative DOCX requirement annex produces:

| Measure | Count |
|---|---:|
| Unique DOCX requirement IDs | 229 |
| Pre-reconciliation Pack trace IDs | 173 |
| Same IDs in DOCX and pre-reconciliation Pack | 134 |
| DOCX IDs absent from the pre-reconciliation Pack | 95 |
| Pack-only normalized IDs | 39 |
| New clarification IDs in this addendum | 14 |
| Post-reconciliation machine trace IDs | 282 |

The 95 former gaps are `UX-001..036`, `ARCH-001..012`,
`FR-TX-001..018`, `COD-001..022`, and `I18N-001..007`.

Authoritative machine artifacts:

- `implementation/V1_2_DOCX_REQUIREMENTS.csv` — all 229 DOCX rows;
- `implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv` — the accepted
  pre-reconciliation coverage classification and the action taken; every
  listed source path is interpreted at immutable checkpoint
  `930b5a28cb995df12f251994a36f7502525ed94a`;
- `docs/reference/TOOLING_LIST_FIELD_MAPPING.csv` — the exact 43-column
  source-to-target mapping extracted from the DOCX; and
- `implementation/REQUIREMENT_TRACEABILITY.csv` — the union of original DOCX,
  Pack-only normalized, and addendum requirement IDs.

## 3. Product structure retained

The main operating and navigation context is the Engineering Project, but
shared business objects are not copied into Project-owned duplicates:

```text
Engineering Project
├── Charter / team / RACI / WBS / Gates
├── Part Applicabilities
│   └── Part / Part Revision
├── Tooling Requirements
│   └── Tooling Master Applicability
│       ├── Tooling Revision
│       ├── Tooling Set / physical copy
│       │   ├── Cavity Map / Insert applicability
│       │   └── Trial Rounds
│       └── Process Baselines / Capacity Scenarios
├── Design / controlled documents / baselines / EBOM
├── Trial / quality / issues
├── NPI readiness / handover
├── Change impacts
└── Activity / My Work projections
```

Required invariants:

- a shared Tooling Master is referenced through versioned Applicability and is
  not duplicated per Project;
- each physical Tooling Set is independently traceable;
- a Trial Round binds one exact Project execution context and exact Tooling
  Master, Revision, Set, cavity/insert, product, material, parameter and
  evidence versions;
- My Work remains a projection over governed source objects; and
- NPI One and ERP/JCE identities remain separately owned. No display-brand
  change alters system codes, ownership or integration success semantics.

## 4. Reconciled Tooling and import scope

`FR-TX-001..018` are direct requirements, not implementation notes.
Phase 6 must provide:

- distinct Part, Tooling Requirement, Tooling Master, Tooling Revision,
  Tooling Set/Copy and Trial identities;
- versioned cross-project/product/part Applicability;
- independently tracked physical sets, cavity maps, sealed cavities,
  cavity-level results, inserts/changeovers and dual-shot/overmold chains;
- one-to-many external identifiers with source and effectivity;
- controlled material, color, compliance and secondary-process specifications;
- Customer Standard, TP Trial Actual and Approved Process Baseline separation;
- versioned Capacity Scenario inputs and outputs with no hidden constants; and
- the eight-step controlled Tooling List import described in
  `docs/TOOLING_LIST_IMPORT_SPEC.md`.

The imported spreadsheet is evidence and provenance, never the system's
normalized aggregate model.

## 5. Additive clarification requirements

| ID | Priority | Requirement | Acceptance | Decision state |
|---|---|---|---|---|
| FR-UX-038 | P0 | Tables support drag-resized persisted widths, double-click auto-fit, bounded minimum/maximum widths, reset and fixed-column-safe horizontal scrolling. | Width is stored by user, view and table schema version; a keyboard alternative is available. | Accepted |
| FR-UX-039 | P0 | Domain navigation supports full and icon-only collapsed modes without losing Project context. | State persists per user; responsive collapse retains active state, tooltip and keyboard access. | Accepted |
| FR-UX-040 | P0 | Docked panes and sustained-work inspectors resize from the actual boundary and remember layout. | Boundary drag, double-click reset, integrated collapse and keyboard resize are covered by accessibility and visual tests. | Accepted |
| FR-UX-041 | P0 | Fields and attachments expose requiredness, editability, source, lock reason, validation/unit and complete upload/scan/progress/failure truth. | Upload supports clear/remove, drag/drop and picker; registered revision/hash, permission and confidentiality are visible; no raw private URL grants access. | Accepted |
| FR-UX-042 | P0 | My Work may use inline row expansion for quick triage, with drawer/Object Page fallback for sustained work. | Filter, scroll, grouping and selection survive expansion and fallback navigation. | Pending DR-REC-001 |
| FR-UX-043 | P0 | Compact icon-first action affordances use the approved local icon adapter. GitHub interaction patterns may inform micro-interactions, but Siemens remains the only primary design baseline. | Icon-only actions have translated accessible names/tooltips and keyboard/focus/disabled states; high-risk or ambiguous primary actions remain visibly labelled; no GitHub branding, direct vendor icon import or unapproved Primer/Octicons dependency is introduced. | Accepted; source boundary resolved by DR-REC-005 |
| FR-PRN-001 | P0 | Provide a server-side Frappe Print Format registry/mapping by object type, project type, Gate/state, language, effective version and copy control. | Normal users initiate printing through the SPA/BFF and never need Desk. | Accepted foundation; exact forms pending |
| FR-PRN-002 | P0 | Controlled output is rendered from an immutable snapshot with source/version, language, print actor/time, QR/hash, watermark/copy state and audit. | Reprinting the same controlled snapshot is traceable and cannot silently substitute newer live data. | Accepted foundation |
| FR-PRN-003 | P0 | Define controlled domain print-form coverage, permissions and required signatures. | Every enabled form has an owner, signer rule, locale evidence and retention/copy policy. | Pending DR-REC-003/004 |
| FR-INT-015 | P1 | Release an immutable Trial Summary for read-only projection to the quality area of the ERP/JCE system. | The event/contract contains exact Trial inputs, parameters, cavities, issues, conclusions and controlled references; the target cannot edit NPI Trial truth. | Accepted NPI-side readiness only; exact contract/event held by DR-REC-009 |
| FR-BR-001 | P0 | Introduce LaunchFlow display-brand configuration using only the supplied brand package and its CSV usage rules. | User-facing display assets follow the exact light/dark/loading/favicon/footer/source contexts; stable internal names and `/api/npi/v1` do not change. | Accepted |
| FR-BR-002 | P1 | Map the ERP/JCE display identity without changing the stable integration system code. | Display text and icon come from an explicitly supplied approved package; internal `ERPNEXT` identity and ownership remain stable. | Approved `JCE Core` display name and `Core.png` supplied; implementation allocated to Phase 8/M7-09 |
| FR-TX-019 | P0 | Separate Customer Standard/Provided Specification, TP Trial Actual and immutable Approved Process Baseline. | Copying a standard never becomes measured actual; every comparable value has unit, provenance, context and effective version. | Accepted |
| FR-TX-020 | P0 | Calculate delta/variance against a versioned tolerance/rule and display `not_measured`, `within_tolerance`, `outside_tolerance` or `unavailable`. | Difference is not automatically shown as an exception unless the approved policy says so. | Pending DR-REC-002 for red semantics |

## 6. Brand boundary

The supplied folder contains five usage-governed LaunchFlow SVGs:

- `Company LOGO.svg` — website footer only;
- `Loading.svg` — blank entry/start/loading page;
- `LaunchFlow Icon.svg` — favicon and visual platform/source identity;
- `LaunchFlow-logo_Standard.svg` — light backgrounds; and
- `LaunchFlow-logo_White.svg` — dark backgrounds.

The assets are consumed unchanged through a display-brand adapter. Alternative
logos, reconstructed marks, colors inferred from unrelated sources, GitHub
marks, Siemens marks and placeholder JCE Core icons are prohibited. Colors
inside the unchanged SVGs are a narrow brand-mark exception and do not retheme
the industrial teal/neutral UI. Accessible names remain translated text even
where the visible source identity uses the LaunchFlow icon.

The subsequently supplied `Core.png` and CSV usage rule approve the `JCE Core`
display identity. They resolve DR-REC-006 but remain allocated to Phase 8/M7-09;
R1-02 does not activate them, and the stable `ERPNEXT` system code remains
unchanged.

## 7. Delivery sequence

1. Pass the documentation/trace reconciliation task; no product code.
2. Implement the accepted shared UX primitives and LaunchFlow display-brand
   adapter with targeted Phase 3/4 regressions. Pending decisions remain
   disabled.
3. Compare the retained P5-01 backend/domain/contract checkpoint with this
   addendum and apply only necessary corrections.
4. Resume and complete the P5-01 frontend/runtime/i18n slice and Level 2 gate.
5. Complete Phase 5, including the bounded controlled-print foundation.
6. Execute the expanded Phase 6 Tooling/domain/capacity/import/export plan.
7. Deliver Trial/NPI and immutable Released Trial Summary in Phase 7.
8. Deliver NPI-side Mock/sandbox-ready ERP/JCE contracts and adapters in
   Phase 8; never claim production execution.
9. Harden generic Data Exchange, reporting/export, operations, migration and
   final reconciliation in Phase 9.

Pending Class-B decisions pause only their dependent acceptance. They do not
authorize guessed defaults and do not block unrelated NPI-owned work.

## 8. Compatibility with completed and checkpointed work

- Phase 4 P4-01 through P4-05 and their accepted Level 3 evidence remain valid.
- P5-00 remains valid as the original Phase 5 anchor; this addendum extends its
  requirement index without re-running the historical gate.
- The P5-01 backend/domain/DocType/repository/BFF/API checkpoint remains
  retained. It is not P5-01 `PASS`.
- No current P5-01 identity, ownership or file-security invariant conflicts
  with this addendum.
- Shared UX/brand remediation must finish before broad Phase 6/7 screen
  generation, limiting visual-baseline churn.

## 9. Reconciliation acceptance

This addendum passes only when:

- the DOCX extraction contains exactly 229 unique requirements;
- the Tooling mapping contains exactly 43 unique source columns;
- the coverage matrix reproduces the accepted category counts;
- all 229 DOCX IDs and all 14 clarification IDs are present in the 282-ID
  trace union;
- backlog, roadmap, acceptance, decisions, risks, deviations and required
  inputs agree with the scoped delivery sequence;
- the `xlsx-tooling-import` skill validates; and
- no product runtime, API, database schema, event schema or external
  integration behavior is changed by this task; the data-ownership contract
  is clarified additively for future Phase 6 implementation.
