# Phase 9 Requirement Anchor

Status: `P9-05 PASS — P9-06 DATA EXCHANGE AUDIT AND PLAN ACTIVE`

This anchor is the product-code authorization boundary for Phase 9. It closes no
Phase 9 requirement by itself. P9-00 exact SHA
`065803ae484d885001259de8238ef01d0ad311e4` passes ordinary CI
`33345162833`; only the P9-01 audit/plan boundary is active. Phase 9 product
code remains unauthorized until the applicable atomic plan passes its own Gate.

## Authority and fixed boundaries

- The approved LaunchFlow architecture, data ownership, OpenAPI/event contracts,
  and P8-01 through P8-09 implementations remain the default-correct baseline.
- ERPNext remains authoritative for formal business execution. LaunchFlow remains
  authoritative for NPI engineering process truth. Existing projection, command,
  Inbox/Outbox, idempotency, audit, replay and reconciliation seams are preserved.
- No Phase 9 task may patch Frappe/ERPNext core, introduce browser-direct ERP
  access, cross-database writes, a generic DocType writer, dual-master fields, or
  Mock/HTTP fake success.
- Production ERP compatibility evidence is reused from P8-07F. Any new fact read
  must stay inside its approved read-only, redacted and fail-closed boundary.
- A proven compatibility difference permits only the smallest local and reversible
  adjustment. Absence of a proven difference means `DIRECT_MATCH` / `NO_CHANGE`.
- `FR-CO-003` and `FR-CO-004` external portals remain
  `USER_APPROVED_POST_V1_2_DEFERRED`; their internal collaboration foundations stay
  in V1.2.
- M9-04 and M9-05 real-project pilots remain
  `USER_APPROVED_POST_V1_2_DEFERRED`. Representative non-production UAT remains
  required and must not be reported as a real-project pilot or real-user adoption.

## Audited atomic allocation

| Atomic task | Backlog boundary | Requirement allocation | Authorization boundary |
| --- | --- | --- | --- |
| P9-01 | M8-01 change impact and revalidation | `FR-CH-001` through `FR-CH-010`; `INT-008` | Audit existing change, ERP-number, impact, task, version, evidence and revalidation seams before any code. |
| P9-02 | M8-02 portfolio, KPI and internal collaboration | `FR-SG-008`, `FR-SG-009`, `FR-CO-005`, `FR-CO-007`, `FR-RP-001` through `FR-RP-007`, `INT-014` | Preserve source-labelled Hub/ERP truth, permission filtering and read-only BI direction. |
| P9-03 | M9-01 performance and resilience | `NFR-PER-001`, `NFR-PER-002`, `NFR-AVL-001`, `NFR-SCL-001` | Establish repeatable evidence and bounded targets; do not claim a production SLA without accepted operational facts. |
| P9-04 | M9-02 security hardening | `NFR-SEC-001`, `NFR-SEC-003`, `INT-012` | Apply the approved Entra/Frappe/ERP authority split without replacing the existing server-side permission model. |
| P9-05 | M9-03 historical migration rehearsal | `FR-RP-008`, `NFR-DAT-001` | Non-production preview, validation, provenance, correction and rollback only; no production migration. |
| P9-06 | M9-07 Data Exchange, export and print hardening | `FR-RP-010`, `NFR-COM-001` | Harden existing bounded import/export/print seams; no generic writer or uncontrolled export. |
| P9-07 | M9-06 go-live and rollback rehearsal | `NFR-BCP-001`, `NFR-MNT-001` | Rehearse deployment, restore, rollback and forward-fix with no production mutation in the evidence task. |
| P9-08 | M9-08 full-product controlled UAT and Phase 9 exit | `UX-003` plus the accepted outputs of P9-01 through P9-07 | Run representative non-production golden/fault scenarios for both project types; no real-pilot or 80-percent real-user claim. |

`FR-CO-003` and `FR-CO-004` stay traceable in Phase 9 as deferred external-portal
requirements but authorize no P9 product task. Their retained internal supplier
milestones, observations, customer approval evidence, version locks, permissions,
audit and notifications are covered only where already in V1.2 scope.

## Requirement inventory audited by P9-00

The complete Phase 9 audit set is:

- Stage and collaboration: `FR-SG-008`, `FR-SG-009`, `FR-CO-003`,
  `FR-CO-004`, `FR-CO-005`, `FR-CO-007`.
- Change: `FR-CH-001`, `FR-CH-002`, `FR-CH-003`, `FR-CH-004`,
  `FR-CH-005`, `FR-CH-006`, `FR-CH-007`, `FR-CH-008`, `FR-CH-009`,
  `FR-CH-010`, `INT-008`.
- Reporting and data movement: `FR-RP-001`, `FR-RP-002`, `FR-RP-003`,
  `FR-RP-004`, `FR-RP-005`, `FR-RP-006`, `FR-RP-007`, `FR-RP-008`,
  `FR-RP-010`, `INT-014`.
- Security and non-functional: `INT-012`, `NFR-SEC-001`, `NFR-SEC-003`,
  `NFR-PER-001`, `NFR-PER-002`, `NFR-AVL-001`, `NFR-BCP-001`,
  `NFR-SCL-001`, `NFR-MNT-001`, `NFR-DAT-001`, `NFR-COM-001`.
- Controlled full-product UAT: `UX-003`.

## Gate and rollback

P9-00 changes governance and trace evidence only. Its Level 2 Gate requires the
current-task verifier, reconciliation generator/verifier, focused governance tests,
repository verification, exact-path manifest check and exact-SHA ordinary CI.
Failure restores the P8-09 final checkpoint
`6235502363e34b1279a0c0e26d8d6aecbbd7811f`; no product or external state needs
rollback. A passing P9-00 may authorize only the P9-01 audit/plan boundary, not
unreviewed product code.

## P9-01 audit result and bounded fact delta

P9-01 audit activation exact SHA
`e6a99666f2f1101bb21ffd4d499728d015c5e98c` passes ordinary CI
`33345969806` in all four lanes. The existing LaunchFlow baseline-impact,
Gate-review, Tooling-revision, Trial-revalidation, audit and integration
mechanics are reusable. They do not create an ERP-owned formal change object.

The accepted P8-07F 27-of-28 relevant-DocType result proves production
`Engineering Change Request` is present and only `Injection Molding Condition`
is absent. Its aggregate checksums do not retain the exact ECR/ECO/ECN fields,
permissions, Workflow/Script and naming metadata needed for an evidence-based
`INT-008` mapping. A separately gated delta may therefore extend only the
existing collector and its focused test to query that exact three-name set and
directly related declarative metadata. It may not read business rows, raw
Scripts, secrets, target methods or unrelated metadata, and may not write or
execute any ERP business action. Product code remains unauthorized until the
sanitized result is accepted and the final P9-01 plan passes exact-SHA ordinary
CI.

## P9-04 approved security boundary and bounded fact delta

P9-03 product checkpoint `957d307d26bc93fedb08b03fae25f15d0241e1d7`
passes ordinary CI `33693636192` and diagnostics-off Level 3 `33694055699`.
P9-04 now applies the approved Entra/Frappe/ERP authority split. Existing
server-side role, tenant, Project, object, file and operation authorization is
retained; the task may neither redesign domains nor make NPI a second editable
permission master.

The accepted P8-07F inventory is reused. A separately exact-SHA ordinary-gated,
fixed collector may read only Role Profile role membership, non-secret Social
Login provider metadata, System User and selected User Permission aggregate
counts, and the self-signup flag. It excludes identities, permission values,
secrets, endpoints and business records. The fact checkpoint makes no product
change and no production mutation. Only a concrete compatibility difference
may authorize a later minimal local adjustment.

The fixed delta completed at `2026-09-03T07:07:46+07:00` with aggregate
checksum `sha256:0919d57016166b07899a3a0648ef975755413027e6e2d29606720308df84afb8`.
Office 365 login and disabled self signup directly match the approved design.
Six standard Role Profiles contain no NPI-specific profile, and the 14 User
Permissions include seven Company rows but zero Project, Customer or Supplier
rows. No accepted source proves an operation-specific NPI authorization
sender. This concrete delta authorizes only one default-disabled, complete,
versioned and hash-bound local projection ingress plus fail-closed principal
resolution. It does not authorize ERPNext mutation, local role administration,
Frappe User role writes or any architecture redesign.

## P9-05 historical migration rehearsal boundary

P9-04 final checkpoint `fa82f3e3dcc7a9474ea51a1356130d5cbc02adee`
passes ordinary CI `33702330209` and diagnostics-off Level 3 `33702723201`;
its `release-gate` result is PASS. P9-05 now audits `FR-RP-008` and
`NFR-DAT-001` only. Product code remains held until the audit/plan transition
passes exact-SHA ordinary CI.

The approved implementation direction is one closed, operation-specific,
non-production historical migration rehearsal. It reuses controlled File
Revision custody, existing Project/Tooling/File operation boundaries and the
proven P6-07 preview/correction/reconciliation/rollback patterns without
renaming or widening P6-07. It may add a separate versioned bundle, immutable
difference preview, private correction artifact and default-disabled durable
rehearsal job. It must not accept arbitrary DocTypes or fields, copy a database,
create a generic importer, import ERP-owned truth as a second master or run a
production migration.

No new production ERPNext fact is needed. Production ERPNext and LaunchFlow
must not be contacted by this transition or its controlled evidence. The
M9-04/M9-05 real-project pilots remain post-V1.2; synthetic non-production UAT
must never be described as real-project or real-user adoption.

P9-05 governance SHA `4d54fbef67cb9111618ded2ae2abd0cc47942167`
passes exact-SHA ordinary CI `33704386277`. The authorized implementation keeps
the audited direction unchanged: one closed five-member ZIP bundle, immutable
preview and hashes, operation-specific System Manager BFF commands, durable
partial results, private correction artifacts, reconciliation and logical
binding rollback. Execution is independently default-disabled and limited to an
explicitly enabled non-production Site. The worker reauthorizes the exact actor,
File Revision, bytes, preview and manifest before processing. No target object is
deleted by rollback, and no production or ERP connection is used.

The final candidate at exact SHA
`22cc20294f37a21a64b00d6d6f2975e2988880f8` passes ordinary CI
`33712753404` and diagnostics-off Level 3 `33713119419`, including cumulative
disposable-Site runtime `100517575541` with `productionContact=false`.
`release-gate` is PASS and P9-05 is complete. Neither its controlled synthetic
evidence nor completion is a real-project pilot.

## P9-06 Data Exchange, export, print and retention boundary

P9-06 covers `FR-RP-010` and `NFR-COM-001` only. The audited baseline already
contains five correct specialized capabilities: P6-07 controlled Tooling XLSX
import, P6-08 Tooling List export, P5-06 controlled print, P9-02 fixed portfolio
and KPI reporting, and P9-05 historical rehearsal. They remain independent and
must not be renamed, widened or routed through a generic importer, exporter,
DocType writer, query dispatcher or print engine.

The minimal additive slice is one fixed Data Exchange capability catalog and
two server-owned versioned report datasets, `project_portfolio.v1` and
`kpi_trends.v1`. Published operation-specific profiles allowlist dataset,
columns, language, structural redaction and a closed CSV/XLSX/controlled-PDF
package. Creation requires server-side permission, CSRF, exact profile version
and hash, actor-bound idempotency and bounded deterministic generation. Every
artifact is private, immutable, hashed and audited. Spreadsheet cells are
formula-neutralized. The PDF is controlled report output only; browser/device
print, numbered copies, production forms and signers remain held by
`DR-REC-003` and `DR-REC-004`.

The retention foundation is explicit rather than inferred. A published policy
version declares one closed tenant-default, exact-customer-reference or
exact-regulation-reference scope, effectivity interval, category years for
project, quality, change, file, Data Exchange export and controlled print, and
an exact hash. No production default or policy precedence is seeded. An
append-only archive record binds one exact selected policy version to one
allowlisted source kind, identifier, optimistic version, source hash and
immutable snapshot/reference. It never deletes, rewrites, purges or
automatically disposes source truth; legal-hold precedence and physical
disposition require a future approved policy decision.

This audit uses repository and already accepted P8-07F facts only. P9-06 has no
fresh production ERP dependency and must not contact production ERPNext or
LaunchFlow. The transition changes governance/evidence only. Product code is
held until the transition passes exact-SHA ordinary CI, after which the frozen
slice is delivered as one batch, one Level 2 and one final diagnostics-off
Level 3.

Governance SHA `ff34547d9cb4ffd441b3203cf92d37571230bb44` passes exact-SHA
ordinary CI `33714911502` on attempt 2; its first attempt was only an existing
P6-08 loading-state browser race and no product code changed. The authorized
single batch now implements the fixed catalog, two report adapters, immutable
five-member package, explicit policy versions and append-only archive records.
Local Level 2 passes `2970` repository tests and `1140` frontend tests with
`9322` English sources at complete direct `zh`/`zh-TW` coverage. The candidate
remains incomplete until one exact-SHA ordinary CI and one diagnostics-off
Level 3 pass at the same commit. P9-07 remains gated, and production ERPNext
and LaunchFlow remain untouched.
