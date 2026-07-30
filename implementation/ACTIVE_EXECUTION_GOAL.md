# Active Execution Goal

Updated: `2026-07-30T10:01:52Z`

- Goal: `NPI One V1.2 — Reconciled Autopilot Continuous Delivery`
- Codex Goal ID: `019fb25f-41fb-7901-9773-c24ebe7e6e34`
- Mode: `R1_SHARED_BRIDGE` within
  `NPI One V1.2 AUTOPILOT CONTINUOUS DELIVERY`
- Final target: `IMPLEMENTATION_COMPLETE` or a true Hard Blocker defined by
  `implementation/AUTOPILOT_CONTROLLER.md`
- Branch: `codex/npi-v1.2-implementation`
- Last synchronized product checkpoint:
  `930b5a28cb995df12f251994a36f7502525ed94a` (`0` ahead / `0` behind before
  the R1-01 task checkpoint)
- Current synchronized Stage 3 starting checkpoint:
  `0b485446ddde66ee0fe0a8ed7459bf191916a020` (`0` ahead / `0` behind at
  recovery); R1-01 through R1-04 are complete bridge tasks, R1-03 passed its
  triggered
  `LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`, and R1-04 passed its
  `LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`; R1-05 Stage 1 is the
  committed predecessor to the passing Stage 2 slice
- Current controller task:
  `R1-05 — Resizable panes, field attachment, and icon action primitives`
  (`IN_PROGRESS`)
- Passing current-task checkpoints:
  `R1-05 Stage 1 — FR-UX-040 live My Work inspector pane`
  (`PASS — LEVEL 3 R1-05 STAGE 1 PUBLIC PREFERENCE/SHARED UI CHECKPOINT`;
  `FR-UX-040` is `TECHNICAL_VERIFIED`), and
  `R1-05 Stage 2 — FR-UX-041 field and attachment truth primitives`
  (`PASS — LEVEL 2 R1-05 STAGE 2 FIELD/ATTACHMENT TRUTH TASK GATE`;
  `FR-UX-041` is `TECHNICAL_VERIFIED`)
- Next and only active slice:
  `R1-05 Stage 3 — FR-UX-043 bounded icon-action foundation`
  (`IMPLEMENTED_LOCAL_VALIDATION_PENDING_LINUX_VISUAL_TASK_GATE`;
  `FR-UX-043` remains `PLANNED_SHARED_UX_REMEDIATION` until its own Gate
  passes)
- Passing reusable Stage 3 checks:
  exact Node `24.18.0` / npm `11.16.0`; generated-source freshness,
  TypeScript, affected ESLint/Stylelint, vendor-boundary, industrial UI and
  i18n audits; `61/61` affected unit tests; `14/14` affected real-browser
  behavior tests; and `6/6` host-platform visual renders. The host-platform
  screenshots are review evidence only and are not substituted for the
  repository's Linux baselines.
- First incomplete action:
  create and push a truthful Stage 3 checkpoint, let existing draft PR `#1`
  run Ubuntu CI, retrieve the exact Linux visual deltas, then complete the
  Level 2 Task Gate. GitHub CLI authentication is stale; the connected GitHub
  app remains available for PR, run and artifact inspection.
- Held product task:
  `P5-01 — Document and design revision`
  (`IN_PROGRESS_CHECKPOINTED`; no P5-01 PASS is claimed)
- Current product Phase:
  `5 — Part Design, Documents, Baselines, and EBOM` (`IN_PROGRESS`)
- Latest complete product Phase:
  `4 — Project Work Items and Stage Gates` (`PASS`)
- External state retained: Phase 3 remains
  `TECHNICAL_PASS_PENDING_UAT`; production rules, ERPNext/JCE/CAD/PDM access,
  and externally owned business decisions remain scoped holds, not a global
  blocker.

## Current authority

- `AGENTS.md` and `implementation/AUTOPILOT_CONTROLLER.md`
- `docs/V1_2_RECONCILIATION_ADDENDUM.md`
- `implementation/V1_2_DOCX_REQUIREMENTS.csv`
- `implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv`
- `implementation/REQUIREMENT_TRACEABILITY.csv`
- `implementation/V1_2_RECONCILIATION_DECISIONS.md`
- the current Requirement Anchors, contracts and accepted ADRs

The current typed trace contains 282 unique IDs: 173 `PACK_CANONICAL`, 95
`DOCX_RECONCILED` and 14 `ADDENDUM_DIRECT`. The 2026-07-27 append-only
correction places `FR-UX-043` in R1-05/UX-A3 without rewriting the historical
281-row R1-01 checkpoint or any earlier Gate evidence.

Brand development has one sole source:
`docs/Brand Asset/Brand Asset Instruction.csv`, the exact five LaunchFlow SVGs
and subsequently supplied `Core.png` beside it. R1-02 uses only the LaunchFlow
assets; `Core.png` is allocated to FR-BR-002/Phase 8/M7-09. No
external/substitute/reconstructed asset is authorized. Stable technical
identifiers remain unchanged.

## Recovery boundary

R1-01 preserved all historical Gate evidence and changed no product runtime,
public API, database schema, event schema, data-ownership contract,
translation allowlist or external integration behavior.

R1-02 implemented the accepted LaunchFlow display-brand boundary. R1-03 added
only the fixed authenticated navigation-preference contract plus collapsed
navigation, command and server-proven Project quick-create foundations. R1-04
added one fixed authenticated My Work grid-preference BFF, three additive
DocTypes, the shared DenseGrid/personal preference behavior and an immutable
published-view root/revision foundation. Personal and published definitions
remain separate; live publication/rollback, export and bulk business commands
remain fail closed. Exact pixel widths, serialized version-confirmed writes,
the seven ordered view schemas and Unicode search limits have final regression
coverage. R1-05 Stage 1 added one fixed actor-bound My Work inspector
preference and a bounded pointer/keyboard/collapse pane boundary. Its public
preference, shared-UI, runtime, accessibility and trilingual evidence passed
the triggered Level 3 checkpoint; it advances only `FR-UX-040`.
Stage 2 added bounded field/attachment truth presentation, a fail-closed
injected transport state machine and URL-free Trial/Gate integrations. Its
unit, browser, accessibility, trilingual, security and independent-review
evidence passed the Level 2 Task Gate; it advances only `FR-UX-041`.
R1-05 remains `IN_PROGRESS`; only Stage 3 is active next, and R1-06 remains
inactive. R1-07 remains scoped to
DR-REC-001. Their cumulative Shell/design/i18n changes must pass the complete
triggered Level 3 bridge Gate before P5-01 product work resumes.

The R1-05 Stage 3 starting boundary is
`0b485446ddde66ee0fe0a8ed7459bf191916a020`. The bounded Stage 3 implementation
introduces no public API, DocType, database migration, authentication or
permission change, production dependency, translation-catalog change or
external integration. Its Linux visual baseline and final Level 2 evidence
remain incomplete, so no Stage 3 or R1-05 PASS is claimed.

On compaction, model switch, tool interruption or handoff, reread this file,
`implementation/PHASE_STATUS.yaml`, `implementation/NEXT_ACTION.md`, and
`implementation/LAST_RUN.md`. Chat memory is non-authoritative. Reuse accepted
Phase 4, P5-00, P5-01 checkpoint, R1-01 through R1-04 and R1-05 Stage 1
and Stage 2 evidence; resume only Stage 3 and do not repeat or rewrite passing
work merely to restore context. Reuse the passing Stage 3 static/unit/browser
evidence above; the first incomplete action is the Linux visual CI checkpoint.
