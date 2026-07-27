# Next Action

Status: `R1-05 STAGE 3 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-27T14:00:01Z`

Stage 2 synchronized starting checkpoint:
`749665e5428208f0453832b7f394eddcb6deebca`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 and R1-02 passed their Level 2 Gates. R1-03 passed its triggered
  `LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`; R1-04 passed its
  `LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`. R1-05 Stage 1 passed its
  `LEVEL 3 R1-05 STAGE 1 PUBLIC PREFERENCE/SHARED UI CHECKPOINT`; Stage 2
  passed its `LEVEL 2 R1-05 STAGE 2 FIELD/ATTACHMENT TRUTH TASK GATE`.
- `FR-UX-040` and `FR-UX-041` are `TECHNICAL_VERIFIED`. `FR-UX-043` remains
  `PLANNED_SHARED_UX_REMEDIATION` until its own Gate passes.
- The current typed trace contains 282 unique IDs: 173 `PACK_CANONICAL`, 95
  `DOCX_RECONCILED`, and 14 `ADDENDUM_DIRECT`. The added `FR-UX-043` row is an
  append-only correction; historical R1-01 and earlier Gate evidence retain
  their original 281-row counts.
- R1 is an inserted bridge, not a new controller Phase.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; its external UAT is unsigned.
- Phase 4 remains `PASS` and its historical evidence is unchanged.
- Phase 5 remains `IN_PROGRESS`.
- R1-05 remains `IN_PROGRESS`: Stages 1 and 2 are `PASS`; Stage 3 is `READY`
  and is the only active next slice.
- P5-01 remains `IN_PROGRESS_CHECKPOINTED` at the retained backend boundary;
  it is not the active product task and is not `PASS`.
- R1-06, R1-07, P5-02 and Phase 6 remain inactive.

## Current task

Execute only:

`R1-05 Stage 3 — FR-UX-043 bounded icon-action foundation`

Requirement IDs:

- `FR-UX-043`

Use:

- the indexed requirement and coverage rows for `FR-UX-043`;
- `docs/UX_INTERACTION_SPEC.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- the `industrial-ux` and `frappe-i18n` Skills; and
- the passing Stage 1 inspector and Stage 2 field/attachment checkpoints;
- `implementation/V1_2_RECONCILIATION_DECISIONS.md` and resolved
  `DR-REC-005`;
- the existing repository-owned iX/company icon and `Button` adapters; and
- the existing i18n and industrial action hierarchy.

## Stage 3 required behavior

1. Extend only the existing repository-owned local icon adapter for secondary
   actions required by the R1-05 pane, field and attachment surfaces.
2. Permit icon-first treatment only for familiar, low-risk and context-clear
   secondary actions. Keep the single primary action visibly labelled.
3. Give every icon-only action a literal-English source label, direct `zh` and
   `zh-TW` translations, translated accessible name and tooltip, keyboard
   path, visible focus, disabled state and non-hover discovery path.
4. Keep high-risk, irreversible, ambiguous and primary actions visibly
   labelled. Icon shape or color must never be the only state or meaning cue.
5. Preserve Siemens iX Classic as the sole primary visual baseline. GitHub may
   inform only compact micro-interaction patterns; no GitHub branding, direct
   vendor icon import or unapproved Primer/Octicons dependency is allowed.
6. Cover allowed-icon mapping, unknown-icon failure, accessible name/tooltip,
   focus, keyboard, disabled and high-risk visible-label boundaries in unit,
   browser, accessibility and affected trilingual visual evidence.

## Prohibited or held behavior

- Do not reopen or widen the passing Stage 1 preference contract.
- Do not reopen or widen the passing Stage 2 field/attachment state machine,
  file authority or Trial/Gate integrations.
- Do not fabricate upload progress, scanner, preview, confidentiality,
  permission or success state.
- Do not install production document/file classification, retention, sharing,
  upload, scanner, viewer or external-retrieval policy.
- Do not expose a raw private URL as a stable business link or access grant.
- Do not make a primary, destructive, high-risk or ambiguous action icon-only.
- Do not import GitHub/Primer/Octicons, a direct vendor icon package, Siemens
  restricted assets or a new production dependency.
- Do not disturb R1-04 personal/shared-view separation or activate its held
  publisher authority, export or bulk business commands.
- Do not begin R1-06 or R1-07, resume P5-01, activate `Core.png`, connect
  ERPNext/JCE/CAD/PDM or infer any pending DR-REC behavior.

## Validation and transition

Start from the accepted R1-05 staged plan and a Stage 3
changed-files-to-tests map. Run the affected Level 2 Task Gate and escalate to
Level 3 only for public contract/schema/authentication/permission, shared
design/i18n or reliably unbounded cross-domain changes. Reuse accepted R1-01
through R1-04 and R1-05 Stage 1/Stage 2 evidence without rewriting historical
Phase 3/4 evidence.

After Stage 3 passes, R1-05 may become a completed bridge task and only R1-06
may activate. R1-07 remains disabled unless DR-REC-001 is approved. P5-01
resumes only after R1-06 and the complete R1 shared Shell/design/i18n Level 3
Gate pass.
