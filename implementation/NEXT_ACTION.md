# Next Action

Status: `R1-05 STAGE 2 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-27T11:08:13Z`

Last synchronized bridge checkpoint:
`88fca2bd898ca08432c5a5f5eec9f25dc963fc14`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 and R1-02 passed their Level 2 Gates. R1-03 passed its triggered
  `LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`; R1-04 passed its
  `LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`. R1-05 Stage 1 passed its
  `LEVEL 3 R1-05 STAGE 1 PUBLIC PREFERENCE/SHARED UI CHECKPOINT`.
- `FR-UX-040` is `TECHNICAL_VERIFIED`. `FR-UX-041` and `FR-UX-043` remain
  `PLANNED_SHARED_UX_REMEDIATION`.
- The current typed trace contains 282 unique IDs: 173 `PACK_CANONICAL`, 95
  `DOCX_RECONCILED`, and 14 `ADDENDUM_DIRECT`. The added `FR-UX-043` row is an
  append-only correction; historical R1-01 and earlier Gate evidence retain
  their original 281-row counts.
- R1 is an inserted bridge, not a new controller Phase.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; its external UAT is unsigned.
- Phase 4 remains `PASS` and its historical evidence is unchanged.
- Phase 5 remains `IN_PROGRESS`.
- R1-05 remains `IN_PROGRESS`: Stage 1 is `PASS`, Stage 2 is `READY` and is
  the only active next slice, and Stage 3 remains planned/inactive.
- P5-01 remains `IN_PROGRESS_CHECKPOINTED` at the retained backend boundary;
  it is not the active product task and is not `PASS`.
- R1-06, R1-07, P5-02 and Phase 6 remain inactive.

## Current task

Execute only:

`R1-05 Stage 2 — FR-UX-041 field and attachment truth primitives`

Requirement IDs:

- `FR-UX-041`

Use:

- the indexed requirement and coverage rows for those three IDs;
- `docs/UX_INTERACTION_SPEC.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- the `industrial-ux` and `frappe-i18n` Skills; and
- the passing Stage 1 inspector checkpoint;
- the existing controlled document/private-file, exact File Revision,
  scanner-state, confidentiality and permission boundaries; and
- the existing i18n and industrial form foundations.

## Stage 2 required behavior

1. Add reusable presentation primitives for required/optional,
   editable/read-only/conditional,
   source, lock reason, validation, unit, exact version and effectivity.
2. Model attachment states truthfully: local selection, actual transport,
   registration, scanner processing, registered-clean, infected/failed and
   retryable failure. Do not simulate percentages or provider state.
3. Support clearing a local selection. Do not invent detach, delete or
   replacement semantics for a registered immutable revision.
4. Consume the existing URL-free controlled-document/File Revision DTOs only
   where a proven integration surface exists. Display exact revision, hash,
   privacy/confidentiality, permission and capability truth; never expose a
   raw private URL as authorization.
5. Keep transport injected into the primitive. Do not widen the current
   `System Manager` document authority, resume held P5-01 frontend work or
   turn the retained revision command into a generic upload service.
6. Cover normal, loading, empty, read-only, denied, failed, conflict,
   processing and retry/recovery states where they apply.
7. Add literal-English source text, complete direct `zh`/`zh-TW`
   translations, component/browser/accessibility tests and affected
   trilingual visual evidence.

## Prohibited or held behavior

- Do not reopen or widen the passing Stage 1 preference contract.
- Do not fabricate upload progress, scanner, preview, confidentiality,
  permission or success state.
- Do not install production document/file classification, retention, sharing,
  upload, scanner, viewer or external-retrieval policy.
- Do not expose a raw private URL as a stable business link or access grant.
- Do not begin Stage 3 `FR-UX-043` icon-action work.
- Do not disturb R1-04 personal/shared-view separation or activate its held
  publisher authority, export or bulk business commands.
- Do not begin R1-06 or R1-07, resume P5-01, activate `Core.png`, connect
  ERPNext/JCE/CAD/PDM or infer any pending DR-REC behavior.

## Validation and transition

Start from the accepted R1-05 staged plan and a Stage 2
changed-files-to-tests map. Run the affected Level 2 Task Gate and escalate to
Level 3 only for public contract/schema/authentication/permission, shared
design/i18n or reliably unbounded cross-domain changes. Reuse accepted R1-01
through R1-04 and R1-05 Stage 1 evidence without rewriting historical Phase
3/4 evidence.

After Stage 2 passes, activate only R1-05 Stage 3. R1-05 remains
`IN_PROGRESS` until Stage 3 also passes; only then may R1-06 activate. R1-07
remains disabled unless DR-REC-001 is approved. P5-01 resumes only after
R1-06 and the complete R1 shared Shell/design/i18n Level 3 Gate pass.
