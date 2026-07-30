# Active Execution Goal

Updated: `2026-07-30T13:52:00Z`

- Goal: `NPI One V1.2 — Reconciled Autopilot Continuous Delivery`
- Codex Goal ID: `019fb25f-41fb-7901-9773-c24ebe7e6e34`
- Mode: `PHASE_5_CONTINUOUS_DELIVERY`
- Final target: `IMPLEMENTATION_COMPLETE` or a true Hard Blocker defined by
  `implementation/AUTOPILOT_CONTROLLER.md`
- Branch: `codex/npi-v1.2-implementation`
- Latest synchronized recovery checkpoint:
  `c980571b27be66e16f2ac57409f0ef72a986e741`
- Current controller task:
  `P5-01 — Document and design revision`
  (`IN_PROGRESS — RESUME AUDIT PASS; FRONTEND/RUNTIME READY`)
- Current Requirement IDs:
  `FR-DS-001`, `FR-DS-003`, `FR-DS-004`, `FR-DS-007`, `FR-DS-008`,
  `FR-DS-009`, `FR-DS-014`
- Retained P5-01 implementation checkpoint:
  `930b5a28cb995df12f251994a36f7502525ed94a`
- Current product Phase:
  `5 — Part Design, Documents, Baselines, and EBOM` (`IN_PROGRESS`)
- Latest complete product Phase:
  `4 — Project Work Items and Stage Gates` (`PASS`)

## Completed bridge and passing reusable evidence

R1-01 through R1-06 are complete for their executable scope. Conditional R1-07
was not activated because `DR-REC-001` remains pending.

The cumulative exit result is:

`PASS — LEVEL 3 R1 SHARED SHELL/DESIGN/I18N EXIT GATE`

Terminal synchronized evidence:

- CI `#72`, run `30546528862`;
- repository job `90884045344`: `763/763` Python, `634/634` frontend unit,
  `279/279` non-visual browser, `2,782` complete direct trilingual sources,
  both zero-vulnerability audits and both secret scans;
- visual job `90884045367`: exact fixed-Linux `24/24`;
- current visual inventory: `231` cases completely covered by the accepted
  210-case matrix plus every source-affected replacement and `21` additive
  cases; and
- current trace: `282` unique IDs =
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

The pushed recovery checkpoint `c980571b27be66e16f2ac57409f0ef72a986e741`
then passed CI `#73`, run `30548142786`: `764/764` Python, `634/634`
frontend unit, `279/279` non-visual browser, `24/24` fixed-Linux visuals,
complete direct trilingual coverage, both zero-vulnerability audits and both
secret scans. This seals the controller/evidence checkpoint without changing
the original R1 Gate decision.

Complete bridge evidence:
`implementation/evidence/reconciliation/r1-shared-bridge-level-3-validation.md`.

These accepted results are not rerun unless P5-01 changes their source
boundary. Historical Phase 3/4, P5-00, P5-01 checkpoint and R1 evidence remains
append-only.

## Retained and unfinished P5-01 scope

Retained at `930b5a2`:

- controlled document/revision/File Revision identities and domain invariants;
- nine additive controlled DocTypes and guarded controllers;
- Project/tenant/actor-bound repository and command idempotency;
- fixed document BFF/API/OpenAPI/data-ownership contracts;
- confidential audited binary retrieval and URL-free capability truth;
- external/CAD/PDM unavailable seams;
- direct backend/DocType `zh` and `zh-TW` sources; and
- focused backend/contract tests.

Still unfinished:

- additive/idempotent migration and complete controlled Frappe runtime
  evidence;
- live Project Design/Documents frontend, parser/view models and dirty-state
  integration;
- complete P5-01 unit/E2E/accessibility/trilingual/visual evidence;
- exact Requirement → Code → Test → Evidence updates;
- P5-01 Level 2 Task Gate; and
- every later P5 task.

No P5-01 requirement is yet reported complete.

## First incomplete action

The bounded resume audit passed and is recorded at
`implementation/evidence/phase-5/p5-01-resume-audit.md`. It found no retained
product conflict and reran the focused P5-01 suites `63/63`.

Implement the smallest unfinished P5-01 frontend/runtime vertical slice:

1. add strict document list/detail/command data sources, closed response
   parsers and view models over the existing BFF contract;
2. integrate a live Project Design/Documents engineering workspace with dense
   document/revision/file/relationship/lock and capability truth;
3. register real form dirty state with App navigation, browser history,
   Project-tab and `beforeunload` guards;
4. add only the additive/idempotent metadata synchronization and controlled
   runtime proof required by the retained nine DocTypes;
5. add literal-English source copy and direct `zh`/`zh-TW` translations; and
6. run affected Level 1 checks before the complete P5-01 Level 2 Task Gate.

Do not start P5-02, add review/release/baseline/EBOM behavior, enable external
retrieval, claim an Office/CAD viewer or connect ERPNext/JCE/CAD/PDM.

## Scoped holds that remain truthful

- Production document classes, numbering, revision, release authority,
  confidentiality, retention, scanner/viewer and sharing rules remain
  unresolved Class-B inputs.
- R1-06 Stage 2 remains held by its unsigned Product Owner approval.
- R1-07 remains unactivated while `DR-REC-001` is pending.
- Phase 3 named business UAT and sanitized-data provenance remain externally
  unsigned.
- Production ERPNext/JCE/CAD/PDM access remains prohibited.

These hold only their named behavior and are not currently global Hard
Blockers.

## Recovery boundary

The R1 bridge Gate remains complete at
`2ced098362ab99a4750a13e7004a441a7f19b698` and CI `#72`; its pushed recovery
checkpoint is `c980571b27be66e16f2ac57409f0ef72a986e741` with CI `#73`. The
P5-01 retained backend checkpoint remains `930b5a2`, and its resume audit is
`PASS`. The first unfinished action is the frontend/runtime vertical slice,
not reimplementation of the retained domain/backend.

On compaction, model switch, tool interruption or handoff, reread this file,
`implementation/PHASE_STATUS.yaml`, `implementation/NEXT_ACTION.md`,
`implementation/LAST_RUN.md`, `implementation/phase-5-requirement-anchor.md`,
`implementation/evidence/phase-5/p5-01-plan.md` and
`implementation/evidence/phase-5/p5-01-resume-audit.md`. Chat memory is
non-authoritative.
