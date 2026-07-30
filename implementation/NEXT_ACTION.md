# Next Action

Status: `R1-06 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-30T11:35:38Z`

R1-05 Stage 3 synchronized implementation checkpoint:
`a2b533691ab7f223c1f51b8113fb2b9251aa82a4`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 and R1-02 passed their Level 2 Gates. R1-03 and R1-04 passed their
  triggered task-level Level 3 Gates.
- R1-05 is complete:
  - Stage 1 / `FR-UX-040`: `TECHNICAL_VERIFIED`;
  - Stage 2 / `FR-UX-041`: `TECHNICAL_VERIFIED`; and
  - Stage 3 / `FR-UX-043`: `TECHNICAL_VERIFIED`.
- The current trace contains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.
- R1 remains an inserted bridge, not a controller Phase.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; its external UAT is unsigned.
- Phase 4 remains `PASS`; Phase 5 remains `IN_PROGRESS`.
- P5-01 remains `IN_PROGRESS_CHECKPOINTED` at the retained backend boundary.
- R1-06 is the only next bridge task.
- R1-07 remains disabled unless `DR-REC-001` is approved.
- P5-01 resumes only after R1-06 and the cumulative R1 shared
  Shell/design/i18n Level 3 Gate pass.

## Current task

Plan and execute only:

`R1-06 — Controlled undo prototype gate and 1440 visual governance`

Requirement IDs:

- `UX-026`
- `UX-030`
- `UX-035`
- `UX-036`

Use:

- the indexed requirement and coverage rows for those IDs;
- `docs/UX_INTERACTION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `implementation/V1_2_RECONCILIATION_DECISIONS.md`;
- the `industrial-ux`, `frappe-i18n` and `release-gate` Skills; and
- the accepted R1-03 through R1-05 shared Shell/design/i18n evidence.

## First incomplete action

Create the R1-06 Requirement Anchor and atomic delivery plan before product
code. The plan must:

1. preserve the exact DOCX meanings and existing canonical mappings for
   `UX-026`, `UX-030`, `UX-035` and `UX-036`;
2. identify one genuinely low-risk reversible action eligible for a timed undo
   contract and explicitly list ineligible actions;
3. define the prototype-before-business-implementation Gate without
   representing fixtures or technical validation as business UAT;
4. define the additive `1440×900` English/Simplified/Traditional P0 visual
   matrix alongside, not instead of, accepted `1366×768` and `1920×1080`
   evidence;
5. replace the temporary R1-05 affected-visual CI scope with durable,
   fail-closed R1-06 visual governance; and
6. map changed files to affected tests, Level 1/2 checks and the mandatory
   cumulative R1 Level 3 exit Gate.

## Prohibited or held behavior

- Do not invent undo semantics for approval, release, baseline, registered
  revision, delete, external execution or any irreversible/high-risk command.
- Do not use an optimistic toast as proof that an undo or business command
  succeeded.
- Do not rewrite unrelated historical visual baselines merely to normalize
  current renderer drift.
- Do not sign Phase 3 business UAT or treat technical prototype evidence as
  representative-user acceptance.
- Do not reopen passing R1-03/R1-04/R1-05 contracts unless the R1-06 impact
  analysis proves a direct requirement.
- Do not begin R1-07, resume P5-01, activate `Core.png`, connect
  ERPNext/JCE/CAD/PDM or infer any pending Decision Request.

## Transition

After R1-06 passes its task Gate, evaluate `DR-REC-001`. If it remains
unapproved, skip R1-07 as conditional and run the complete R1 shared
Shell/design/i18n Level 3 exit Gate. Only a passing exit Gate releases the
P5-01 hold.
