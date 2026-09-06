# R1-05 Plan — Resizable panes, field attachment, and icon action primitives

Date: 2026-07-27
Branch: `codex/npi-v1.2-implementation`
Task:
`R1-05 — Resizable panes, field attachment, and icon action primitives`
Requirements: `FR-UX-040`, `FR-UX-041`, `FR-UX-043`
Status: `PASS — STAGES 0–3 PASS; R1-06 READY`
Starting synchronized bridge checkpoint:
`fb92884a2d3a1a4b3dd90e8e30a013c457701e7f`

## Delivery sequence

R1-05 is split into bounded stages so the newly discovered requirement is
machine-traceable before any product change and so a held document command or
business policy cannot leak into shared UX work.

### Stage 0 — append-only FR-UX-043 requirement re-anchor

- Add `FR-UX-043` as P0, Phase 5, `ADDENDUM_DIRECT`, self-canonical and
  `PLANNED_SHARED_UX_REMEDIATION`.
- Allocate it to R1-05/UX-A3 and update the current trace from 281 to 282 rows:
  173 `PACK_CANONICAL`, 95 `DOCX_RECONCILED`, 14 `ADDENDUM_DIRECT`.
- Update the addendum, specifications, controller, applicable
  `industrial-ux` Skill, final Definition of Done, generator, verifier,
  focused tests and this plan.
- Preserve the historical 281-row R1-01 checkpoint, all earlier validation
  counts and every Phase 3/4/P5/R1 Gate conclusion.
- Commit and push this planning/tooling checkpoint independently before
  product code.

Stage 0 changes no React/Frappe runtime, public API, schema, permission,
translation catalog, production dependency or external integration behavior.

### Stage 1 — FR-UX-040 live pane vertical slice

- Start with the live My Work context inspector, where a sustained-work
  inspector and real selection/filter context already exist.
- Replace the range-control approximation with a visible boundary separator
  supporting bounded pointer drag, keyboard adjustment, double-click reset and
  integrated collapse/expand.
- Preserve selected work item, Project/filter state, scroll and focus. If
  collapse hides the focused control, focus moves to the visible expand path.
- Keep responsive stacking presentation-only; it must not overwrite a
  deliberate desktop preference.
- Persist only a fixed, actor-bound, validated inspector preference through an
  authenticated boundary. No caller-selected actor, key or arbitrary pane ID
  is accepted.
- Reuse the confirmed-write and recovery patterns from R1-04 and the pointer/
  keyboard separator behavior from the shared DenseGrid.

Any public session/API contract or stored schema change triggers Level 3 for
this stage.

### Stage 2 — FR-UX-041 field and attachment truth primitives

- Add reusable presentation primitives for requiredness, editability, source,
  lock reason, validation, unit, exact version and effectivity.
- Model attachment states truthfully: local selection, actual transport,
  registration, scanner processing, registered-clean, infected/failed and
  retryable failure. No simulated percentage or fabricated provider state is
  allowed.
- Support clearing a local selection. Do not invent detach/delete/replacement
  semantics for a registered immutable revision.
- Consume the existing URL-free controlled-document/File Revision DTOs when a
  proven integration surface is available. Display exact revision, hash,
  privacy/confidentiality, permission and capability truth; never expose a raw
  private URL as authorization.
- Keep transport injected into the primitive. R1-05 does not widen the current
  `System Manager` document authority, resume the held P5-01 frontend or turn
  the retained revision command into a generic upload service.

### Stage 3 — FR-UX-043 bounded icon-action foundation

- Extend only the existing repository-owned local icon adapter for the
  secondary actions required by the R1-05 pane/field/attachment surfaces.
- Permit icon-first treatment only for familiar, low-risk, context-clear
  secondary actions.
- Give every icon-only action a literal-English source label, direct `zh` and
  `zh-TW` translations, accessible name/tooltip, keyboard path, visible focus,
  disabled state and non-hover discovery path.
- Keep high-risk, irreversible, ambiguous and primary actions visibly
  labelled. Color or icon shape is never the only state/meaning signal.
- Siemens iX Classic remains the sole primary visual baseline. GitHub may
  inform compact overflow/inline/sidebar micro-interactions only; no GitHub
  branding, direct vendor icon import or unapproved Primer/Octicons dependency
  is introduced.

## Scope

- One complete R1-05 vertical path proving a real resizable sustained-work
  inspector with truthful persisted state.
- Shared field and attachment presentation contracts whose displayed states
  are derived from server or actual client transport truth.
- A closed local icon-action adapter used only on the affected R1-05 surfaces.
- Literal-English source copy, complete direct Simplified/Traditional Chinese
  coverage, keyboard/focus/accessibility behavior and affected trilingual
  browser/visual evidence.
- Explicit normal, loading, empty, read-only, denied, failed, conflict,
  processing and recovery states where applicable.

## Non-scope

- No generic preference service, arbitrary pane registry or caller-selected
  user/tenant/storage key.
- No product-wide pane retrofit in the first slice and no promise that every
  left/tree pane shares one geometry policy.
- No registered-file detach/delete/replacement command, binary deletion,
  mutable revision, raw private URL, permission widening or production
  document/file policy.
- No simulated upload percentage, scanner result, preview, confidentiality,
  authorization or success.
- No new production dependency, GitHub/Primer branding, direct Octicons import
  or Siemens restricted corporate asset.
- No R1-06/R1-07 behavior, held UX-028 publisher authority, held P5-01
  continuation, `Core.png` activation or ERPNext/JCE/CAD/PDM connection.

## Repository facts and bounded choices

1. The current `DockedInspector` uses browser `localStorage` and a range input.
   That state is browser-profile-bound and cannot satisfy actor ownership.
2. The live My Work inspector is the narrowest real sustained-work slice.
   Other consumers remain on a compatibility path until their scope is
   explicitly reviewed.
3. DenseGrid already proves pointer capture, bounded preview, one committed
   write, cancellation, double-click and keyboard separator behavior.
4. R1-03 and R1-04 prove fixed authenticated preference routes,
   server-derived actor identity, strict input validation and confirmed-state
   recovery. R1-05 must reuse those invariants rather than expose generic
   storage.
5. The visual token defines a 340px inspector default, while the current
   component uses 320px and 260–480px bounds. The product stage must reconcile
   default/bounds against the authoritative token and real viewport evidence;
   Stage 0 does not silently choose a new business policy.
6. The retained P5-01 backend distinguishes Controlled Document, Document
   Revision, private File Revision, scanner truth and URL-free capability
   reads. Its revise/upload command is not a generic attachment endpoint.
7. `DR-REC-005` is resolved: existing iX/company adapters are approved;
   Octicons are not.
8. No requirement authorizes making a high-risk or ambiguous primary action
   icon-only.

## Scoped Class-B holds

The following facts are not invented by Stage 0:

- whether the persisted layout is one global context inspector or a closed
  per-workspace preference beyond the initial My Work slice;
- exact width bounds and whether left/tree panes join this task;
- responsive collapse persistence beyond the safe rule that transient
  stacking does not overwrite an explicit desktop preference;
- registered attachment remove/detach/replacement semantics;
- any widening of document revise/upload/preview/download authority;
- production confidentiality labels, MIME/size limits, scanner/viewer
  provider behavior and external-retrieval policy;
- server-owned codes for field source, lock reason, validation, effectivity
  and confidentiality where current contracts do not expose them; and
- a progress transport that reports real byte percentages.

Only the dependent behavior is held. The first safe vertical slice and
truthful unavailable/indeterminate states may proceed without guessing.

## Changed-files to affected-tests

| Changed boundary | Required affected checks |
|---|---|
| Stage 0 addendum/spec/controller text | exact `FR-UX-043` presence, allocation and historical-count review; Markdown/YAML/CSV consistency; `git diff --check` |
| Reconciliation generator and trace CSV | generator `--apply` then clean check; 282 unique rows; 173/95/14 kinds; immutable 173-ID digest |
| Reconciliation verifier/tests | complete `tests.test_v1_2_reconciliation`; standalone verifier; exact R1-05 row/allocation assertion |
| Pane preference contract/runtime | domain/repository/API/controller/OpenAPI tests; actor/tenant/CSRF/closed-input/conflict/corrupt-state/rollback cases; controlled Frappe runtime |
| Resizable pane adapter and My Work integration | pointer/keyboard/double-click/capture-loss tests; selection/filter/scroll/focus preservation; responsive presentation behavior; affected My Work regressions |
| Field/attachment primitives | state-machine and accessibility units; denied/read-only/failure/retry/scanner/revision/hash/privacy truth; existing document contract regressions when consumed |
| Local icon adapter and affected controls | adapter allowlist/import-boundary checks; accessible-name/tooltip/keyboard/focus/disabled/high-risk-label tests |
| Literal English and direct Chinese catalogs | extraction/catalog checks, translation coverage, mixed-language scans and terminology validation |
| Shared UI/API/schema impact | affected trilingual E2E/visual matrix; full repository/runtime/security/migration/recovery Gate when the Level 3 trigger applies |

## Stage 0 validation

1. Regenerate the trace with
   `python scripts/reconcile_v1_2_traceability.py --apply`.
2. Run `python -m unittest tests.test_v1_2_reconciliation -v`.
3. Run `python scripts/verify_v1_2_reconciliation.py`.
4. Run the generator again without `--apply` to prove freshness.
5. Validate `.agents/skills/industrial-ux` with
   `tmp/frappe-bench/env/bin/python -B
   /home/vscode/.codex/skills/.system/skill-creator/scripts/quick_validate.py
   .agents/skills/industrial-ux` and assert the icon/DoD guard text.
6. Parse repository YAML safely, verify 282 unique trace rows and the exact
   173/95/14 distribution, and scan all current-count references.
7. Run `git diff --check`, confirm no product-code path changed and prove
   historical Phase 3/4 evidence directories are untouched.
8. Obtain an independent requirement/trace/commit-scope audit.

Product implementation begins only after Stage 0 is committed and pushed.
Each later stage runs Level 1 repair checks, an R1-05 Level 2 Task Gate, and
Level 3 whenever public contract/schema/authentication/permission, shared
design/i18n or reliably unbounded cross-domain behavior changes.

## Stage 1 validation and Stage 2-only transition

Stage 1 evidence:
[R1-05 Stage 1 Validation — FR-UX-040 Live My Work Inspector Pane](r1-05-stage-1-validation.md).

Result: `PASS — FR-UX-040 TECHNICAL_VERIFIED; STAGE 2 READY`.

The fixed current-actor My Work inspector preference, bounded separator,
confirmed-write recovery, presentation-only responsive stacking, focus
recovery, trilingual UI and triggered Level 3 boundary passed their required
contract, runtime, unit, browser, accessibility, i18n and zero-tolerance
visual checks. The linked validation is the evidence source for exact commands,
counts, artifacts, reviewed renderer deltas and independent reviews.

This transition makes only Stage 2 and `FR-UX-041` ready as the next
implementation stage. Stage 3 and `FR-UX-043` remain planned and are not
activated by the Stage 1 PASS. It does not resume held P5-01 work or widen any
document, attachment, ERPNext or production authority.

## Stage 2 validation and Stage 3-only transition

Stage 2 starting synchronized checkpoint:
`749665e5428208f0453832b7f394eddcb6deebca`.

Stage 2 evidence:
[R1-05 Stage 2 Validation — FR-UX-041 Field and Attachment Truth](r1-05-stage-2-validation.md).

Result:
`PASS — LEVEL 2 R1-05 STAGE 2 FIELD/ATTACHMENT TRUTH TASK GATE`.

The reusable field/attachment truth contracts, fail-closed injected transport
workflow, visible async file identity, URL-free registered File Revision
presentation, local-only Trial integration, read-only Gate integration,
trilingual UI, accessibility and exact affected visual evidence passed their
bounded Level 2 Gate. The linked validation is the evidence source for exact
commands, counts, coverage, artifacts, security/rollback review and the
independent post-repair PASS.

`FR-UX-040` and `FR-UX-041` are `TECHNICAL_VERIFIED`. This transition
activates only Stage 3 and `FR-UX-043`; `FR-UX-043` remains
`PLANNED_SHARED_UX_REMEDIATION` until its own Gate passes. R1-05 as a whole
remains `IN_PROGRESS`. R1-06 is not activated, R1-07 remains disabled under
DR-REC-001, P5-01 remains held, and no document/file permission, registered
revision mutation, production upload/scanner policy or external integration
is widened.

## Stage 3 validation and R1-06-only transition

Stage 3 starting synchronized checkpoint:
`0b485446ddde66ee0fe0a8ed7459bf191916a020`.

Stage 3 evidence:
[R1-05 Stage 3 Validation — FR-UX-043 Bounded Icon Actions](r1-05-stage-3-validation.md).

Result:
`PASS — LEVEL 2 R1-05 STAGE 3 ICON-ACTION TASK GATE`.

The closed local action policy, fail-closed Siemens iX icon mapping, translated
accessible tooltip/name behavior, keyboard/focus/disabled boundaries, visible
primary/high-risk/ambiguous actions, vendor-import bans and affected
trilingual Linux visuals passed. The CI repairs required to execute the
repository, visual, metadata and secret-scan lanes are recorded in the linked
evidence; no test or acceptance threshold was reduced.

`FR-UX-040`, `FR-UX-041` and `FR-UX-043` are
`TECHNICAL_VERIFIED`, and R1-05 is complete. This transition activates only
R1-06. R1-07 remains disabled under DR-REC-001; P5-01 remains held until R1-06
and the cumulative R1 shared Shell/design/i18n Level 3 Gate pass.

## Rollback

- Stage 0 is an independent planning/tooling commit. Before product adoption,
  reverting that one commit restores the prior current trace; it never edits
  historical evidence.
- Pane preference schema/records, if introduced later, are additive. Before
  retained user state, roll back code/migrations to the pre-stage checkpoint.
  After retained state, disable the fixed route, preserve records and deploy a
  reviewed forward correction.
- Field/attachment primitives are presentation-only until connected to an
  approved command. Removing them must not delete controlled document/File
  Revision history.
- Local icon mappings are additive and reversible; no vendor dependency or
  brand asset migration is permitted.
