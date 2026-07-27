# Next Action

Status: `R1-05 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-27T06:44:34Z`

Last synchronized bridge checkpoint:
`3e0721a1b8be8dbd1b618d78a635b74d28cd0178`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 and R1-02 passed their Level 2 Gates. R1-03 passed its triggered
  `LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`; R1-04 passed its
  `LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`.
- R1-04 trace states are:
  - `FR-UX-038`: `TECHNICAL_VERIFIED`;
  - `UX-007`: `TECHNICAL_VERIFIED_FOUNDATION`;
  - `UX-027`: `TECHNICAL_VERIFIED_FOUNDATION`;
  - `UX-028`: `TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD`; and
  - `UX-035`: `TECHNICAL_VERIFIED_FOUNDATION`.
- `FR-UX-040` and `FR-UX-041` remain
  `PLANNED_SHARED_UX_REMEDIATION`; R1-05 has not yet claimed implementation.
- The current typed trace contains 281 unique IDs: 173 `PACK_CANONICAL`, 95
  `DOCX_RECONCILED`, and 13 `ADDENDUM_DIRECT`.
- R1 is an inserted bridge, not a new controller Phase.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; its external UAT is unsigned.
- Phase 4 remains `PASS` and its historical evidence is unchanged.
- Phase 5 remains `IN_PROGRESS`.
- P5-01 remains `IN_PROGRESS_CHECKPOINTED` at the retained backend boundary;
  it is not the active product task and is not `PASS`.
- P5-02 and Phase 6 remain inactive.

## Current task

Execute only:

`R1-05 — Resizable panes and field attachment primitives`

Requirement IDs:

- `FR-UX-040`
- `FR-UX-041`

Use:

- the indexed requirement and coverage rows for those two IDs;
- `docs/UX_INTERACTION_SPEC.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- the `industrial-ux` and `frappe-i18n` Skills; and
- the existing docked inspector, authenticated preference, controlled
  document/private-file, exact File Revision, scanner-state, confidentiality,
  permission, i18n and industrial form boundaries.

## R1-05 required behavior

1. Resize docked panes and sustained-work inspectors from the actual visible
   boundary, with bounded pointer drag, double-click reset, integrated
   collapse and an equivalent keyboard path.
2. Remember only an authenticated user's validated pane layout through a
   fixed, actor-bound preference boundary. Preserve authoritative
   Project/object selection, filters, scroll and focus across resize and
   collapse.
3. Keep sustained-work inspectors docked. A temporary drawer may not replace
   the stable engineering workspace or hide object context.
4. Expose field truth for required/optional, editable/read-only/conditional,
   source, lock reason, validation, unit, exact version and effectivity.
5. Expose attachment clear/remove, drag/drop and picker paths with explicit
   type/size guidance, progress, scanner-owned state and visible failure.
6. After registration, expose exact revision/hash, permission and
   confidentiality truth. A raw private URL is never authorization.
7. Add literal-English source text, complete direct `zh`/`zh-TW`
   translations, component/browser/accessibility tests and affected
   trilingual visual evidence.

## Prohibited or held behavior

- Do not create a generic caller-selected preference, user or key API.
- Do not fabricate upload progress, scanner, preview, confidentiality,
  permission or success state.
- Do not install production document/file classification, retention, sharing,
  upload, scanner, viewer or external-retrieval policy.
- Do not use a drawer as the primary sustained-work inspector.
- Do not expose a raw private URL as a stable business link or access grant.
- Do not disturb R1-04 personal/shared-view separation or activate its held
  publisher authority, export or bulk business commands.
- Do not begin R1-06 or R1-07, resume P5-01, activate `Core.png`, connect
  ERPNext/JCE/CAD/PDM or infer any pending DR-REC behavior.

## Validation and transition

Start from an explicit R1-05 plan and changed-files-to-tests map. Run the
affected Level 2 Task Gate and escalate to Level 3 only for public
contract/schema/authentication/permission, shared design/i18n or reliably
unbounded cross-domain changes. Reuse accepted R1-01 through R1-04 evidence
without rewriting historical Phase 3/4 evidence.

After R1-05 passes, activate only R1-06. R1-07 remains disabled unless
DR-REC-001 is approved. P5-01 resumes only after R1-06 and the complete R1
shared Shell/design/i18n Level 3 Gate pass.
