# Next Action

Status: `R1-02 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-25T21:47:16Z`

Last synchronized product checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 passed its Level 2 documentation/trace/tooling Gate.
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

`R1-02 — LaunchFlow display brand adapter and exact supplied assets`

Primary Requirement ID:

- `FR-BR-001`

Use:

- `docs/Brand Asset/Brand Asset Instruction.csv`;
- the exact five SVGs beside that CSV;
- `docs/decisions/ADR-012-launchflow-display-brand.md`;
- `docs/UX_INTERACTION_SPEC.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- the `industrial-ux` and `frappe-i18n` Skills; and
- the existing local UI/icon/i18n adapter boundaries.

## R1-02 required behavior

1. Add one local display-brand adapter; do not scatter asset-path decisions.
2. Use the white wordmark on the existing dark application header and the
   standard wordmark only on light backgrounds.
3. Use the square LaunchFlow icon for favicon and compact platform/source
   identity with translated accessible names.
4. Use `Loading.svg` only for blank entry/start/full-surface loading, not
   routine inline loading.
5. Use `Company LOGO.svg` only in the persistent website footer on a
   contrast-safe neutral light surface.
6. Preserve stable `NPI_ONE`, `ERPNEXT`, `/api/npi/v1`, package, DocType and
   database identities.
7. Add literal-English source text and complete direct `zh`/`zh-TW` coverage;
   no mixed-language release fallback.
8. Add affected component/browser/visual/accessibility tests and exact asset
   scope assertions.

## Prohibited or held behavior

- Do not redraw, recolor, crop or replace a supplied asset.
- Do not infer component colors from logo colors or change industrial
  teal/neutral tokens.
- Do not use Company LOGO as the product, source or ERP/JCE mark.
- Do not invent, search for or substitute an ERP/JCE asset or legal display
  identity; `FR-BR-002` remains held by DR-REC-006.
- Do not rename internal identifiers, connect ERPNext/JCE, resume P5-01, or
  begin another R1 task early.

## Validation and transition

R1-02 is a shared Shell/i18n task. Run affected Level 2 checks and retain the
changed-files-to-tests map. R1-02 does not itself satisfy the R1 Level 3 bridge
Gate; that Gate runs after the accepted shared R1 tasks are complete.

After R1-02 passes, activate only R1-03. R1-07 remains disabled unless
DR-REC-001 is approved. P5-01 resumes only after the complete R1 shared
Shell/design/i18n Level 3 Gate passes.
