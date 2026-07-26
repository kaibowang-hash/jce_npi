# Next Action

Status: `R1-03 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-26T05:54:51Z`

Last synchronized product checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 and R1-02 passed their Level 2 Gates. `FR-BR-001` is
  `TECHNICAL_VERIFIED`.
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

`R1-03 — App Shell collapsed navigation command and contextual quick-create`

Requirement IDs:

- `FR-UX-039`
- `UX-011`
- `UX-018`

Use:

- the indexed requirement and coverage rows for `FR-UX-039`, `UX-011` and
  `UX-018`;
- `docs/UX_INTERACTION_SPEC.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- the `industrial-ux` and `frappe-i18n` Skills; and
- the existing App Shell, router, session/preference, capability and i18n
  adapter boundaries.

## R1-03 required behavior

1. Support full and icon-only domain navigation while preserving active state,
   Project context and the established industrial Shell geometry.
2. Persist the explicit collapse preference per current user through an
   existing approved preference boundary; responsive auto-collapse must not
   overwrite the explicit user choice.
3. Keep collapsed navigation keyboard-operable, focus-visible and labelled
   with translated accessible names/tooltips; hover cannot be the only path.
4. Add a Project-context quick-create entry that exposes only actions
   applicable to the current stage and server-proven permission/capability.
5. Add a keyboard-first command/search foundation for existing Project, Part,
   Tooling, Trial and approved common-action routes without fabricating object
   results or creation authority.
6. Preserve context and a deterministic return path across command navigation;
   maintain at most one visual primary action in the active work context.
7. Add literal-English source text, complete direct `zh`/`zh-TW` translations,
   component/browser/accessibility tests and affected trilingual visual
   evidence.

## Prohibited or held behavior

- Do not treat viewport-driven collapse as the user's saved preference.
- Do not expose a create command merely because a route or label exists; use
  authoritative context/capability truth or show an honest unavailable state.
- Do not turn the command foundation into unrestricted global search, external
  indexing, notification delivery or a new backend authorization model.
- Do not disturb the accepted R1-02 asset contexts or activate `Core.png`.
- Do not begin R1-04, resume P5-01, connect ERPNext/JCE or infer any pending
  DR-REC behavior.

## Validation and transition

R1-03 is another shared Shell/i18n task. Start with an explicit plan and
changed-files-to-tests map, then run its affected Level 2 checks. Reuse the
accepted R1-02 evidence without rewriting it. R1-03 does not itself satisfy the
R1 Level 3 bridge Gate; that Gate runs after the accepted shared R1 tasks are
complete.

After R1-03 passes, activate only R1-04. R1-07 remains disabled unless
DR-REC-001 is approved. P5-01 resumes only after the complete R1 shared
Shell/design/i18n Level 3 Gate passes.
