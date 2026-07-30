# Next Action

Status: `P5-01 FRONTEND/RUNTIME READY — RESUME AUDIT PASS`

Recovery time: `2026-07-30T14:10:21Z`

Latest synchronized recovery checkpoint:
`ee8730133e8cdd30fc7bff158ab80a252ed14249`

Retained P5-01 checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- The cumulative R1 shared Shell/design/i18n Level 3 exit Gate is `PASS`.
- `R1_SHARED_BRIDGE` is released.
- R1-01 through R1-06 are complete for their executable scope.
- `DR-REC-001` remains pending; conditional R1-07 was not activated or marked
  complete.
- Phase 5 remains `IN_PROGRESS`.
- P5-00 remains `PASS`.
- P5-01 resume audit is `PASS`; P5-01 remains `IN_PROGRESS`, not `PASS`.
- The exact resume-audit checkpoint passed CI `#74`, run `30549749537`.
- P5-02 through P5-05 and Phase 6 remain inactive.
- The current trace contains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Use:

- `implementation/phase-5-requirement-anchor.md`;
- `implementation/evidence/phase-5/p5-01-plan.md`;
- `implementation/evidence/phase-5/p5-01-reconciliation-hold.md`;
- `implementation/evidence/phase-5/p5-01-resume-audit.md`;
- the indexed trace rows and current contracts; and
- `frappe-safe-change`, `npi-domain-guard`, `industrial-ux` and
  `frappe-i18n` Skills.

## First incomplete action

Implement the smallest unfinished P5-01 frontend/runtime vertical slice:

1. add one strict document data-source module with closed list/detail/
   capability/command response parsers and view models;
2. expose the existing live BFF through a dense Project Design/Documents tab,
   preserving Project context and showing identity, policy, revision, exact
   file/hash/scan, relationships, lock history, source/editability and
   external/CAD unavailable truth;
3. support normal, empty, loading, no-permission, read-only, validation,
   conflict, processing, retryable, final and provider-unavailable states
   without a raw private URL or fake success;
4. replace the prototype-only dirty route assumption with real workspace dirty
   registration covering App navigation, Project-tab changes, history and
   `beforeunload`, with cancel restoring focus and preserving input;
5. add direct literal-English/`zh`/`zh-TW` copy and affected unit/component/
   accessibility/browser/visual tests; and
6. prepare the additive/idempotent DocType metadata synchronization and
   controlled Frappe runtime lane before the Level 2 Task Gate.

## Retained passing checkpoint evidence

- P5-01 focused domain/repository/API/metadata/controller/contract:
  `63/63`.
- Binary response/failure matrix: `15/15`.
- Affected foundation/BFF/API regressions: `107/107`.
- Nine DocType JSON and OpenAPI/data-ownership/controller metadata checks.
- Direct catalogs at the checkpoint and generated-catalog freshness.
- Exact 55-file retained inventory and no production policy, external
  identity, scanner/viewer, CAD/PDM or ERPNext activation.

These results were impact-reviewed against current shared code and retained in
`implementation/evidence/phase-5/p5-01-resume-audit.md`. Do not repeat
unrelated complete R1 Gates.

## Prohibited or held behavior

- Do not restart the already retained pure domain/backend slice.
- Do not install production document types, prefixes, numbering or revision
  policy.
- Do not infer release/review authority from Project ownership, RACI,
  `System Manager` or the transport role.
- Do not expose a raw private URL or fabricate upload, scanner, preview,
  connector or external-sharing success.
- Do not weaken tenant/Project/object authorization, CSRF, idempotency,
  optimistic version, audit or immutable revision truth.
- Do not start P5-02 review/release, P5-03 baseline, P5-04 EBOM or P5-05
  publish request behavior.
- Do not connect production ERPNext/JCE/CAD/PDM or sign external UAT.

## Transition

Complete the controlled metadata/runtime plus live Project Design/Documents
workspace slice, trilingual/accessibility/error states and affected exact
visuals. Finish the P5-01 Level 2 Task Gate before activating P5-02.
