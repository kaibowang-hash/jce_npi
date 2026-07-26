# Next Action

Status: `R1-04 READY — R1 SHARED BRIDGE`

Recovery time: `2026-07-26T10:30:54Z`

Last synchronized bridge checkpoint:
`07eb5f8b6cf859c406be2aaff3aa218fbf0bf61d`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- R1-01 and R1-02 passed their Level 2 Gates. R1-03 passed its triggered
  `LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`.
- `FR-UX-039` and `UX-011` are `TECHNICAL_VERIFIED`; `UX-018` is
  `TECHNICAL_VERIFIED_FOUNDATION`.
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

`R1-04 — Shared grid sizing personalization views and export foundation`

Requirement IDs:

- `FR-UX-038`
- `UX-007`
- `UX-027`
- `UX-028`
- `UX-035`

Use:

- the indexed requirement and coverage rows for those five IDs;
- `docs/UX_INTERACTION_SPEC.md`;
- `docs/LOCALIZATION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- the `industrial-ux` and `frappe-i18n` Skills; and
- the existing Worklist/live-grid, session preference, API, authorization,
  i18n and industrial table boundaries.

## R1-04 required behavior

1. Establish one shared dense-grid foundation with drag-resized columns,
   double-click auto-fit, bounded minimum/maximum widths, reset, fixed-column
   safe horizontal scrolling and a keyboard alternative.
2. Persist personal column widths and layouts by authenticated user, view and
   table schema version. Personal preferences must not mutate a shared view.
3. Preserve high-density table fundamentals: column selection, fixed columns,
   grouping, filtering, sorting, bulk-action and saved-view/export seams
   without fabricating unsupported domain actions or large-data performance.
4. Provide personal saved-filter/layout foundations for favorites, recent
   access and default Project only where an existing authoritative object or
   preference boundary proves the behavior.
5. Provide a versioned, permissioned and audited published-view foundation.
   A shared view needs a name, description, version and permission boundary,
   and change/rollback history.
6. Preserve the classic industrial layout at 1440×900: object context,
   primary action, dense work list and properties remain visible without
   decorative cards, excess whitespace or competing primary actions.
7. Add literal-English source text, complete direct `zh`/`zh-TW`
   translations, component/browser/accessibility tests and affected
   trilingual visual evidence.

## Class-B boundary

`UX-028` names administrators and Project leads as publishers. If the current
capability/authority contracts do not prove that exact publication authority,
hold only the publisher rule and present 2–3 evidence-backed options. Do not
infer it from a Frappe role, Project membership or UI label, and do not weaken
authorization merely to complete the foundation.

## Prohibited or held behavior

- Do not reuse browser-local prototype state as a live authenticated
  preference.
- Do not create a generic caller-selected preference/user/key API.
- Do not make a shared view mutable through a personal-layout write.
- Do not claim Tooling List's ten production views, unrestricted export,
  server-scale virtualization or domain bulk commands before their owning
  data/contracts exist.
- Do not disturb the accepted R1-02 asset contexts, R1-03 fixed session
  contract or activate `Core.png`.
- Do not begin R1-05, resume P5-01, connect ERPNext/JCE or infer any pending
  DR-REC behavior.

## Validation and transition

Start from an explicit plan and changed-files-to-tests map. Run the affected
Level 2 Task Gate plus any Level 3 trigger introduced by public contract,
schema, permission, shared design/i18n or other cross-domain changes. Reuse the
accepted R1-01/R1-02/R1-03 evidence without rewriting historical Phase 3/4
evidence.

After R1-04 passes, activate only R1-05. R1-07 remains disabled unless
DR-REC-001 is approved. P5-01 resumes only after R1-05, R1-06 and the complete
R1 shared Shell/design/i18n Level 3 Gate pass.
