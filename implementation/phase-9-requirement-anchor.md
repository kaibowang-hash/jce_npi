# Phase 9 Requirement Anchor

Status: `P9-00 PASS — P9-01 FACT-DELTA GOVERNANCE ACTIVE`

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
