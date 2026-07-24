# Next Action

Status: `CHECKPOINT — P4-04 PLANNED; IMPLEMENTATION NOT STARTED`

First incomplete phase: `3 — React App Shell Siemens UI and i18n Foundation`.

Phase 3 status: `TECHNICAL_PASS_PENDING_UAT` — **not** `PASS`.

## First pending task — external validation

Complete `FR-UX-031` business UAT with named Project Management,
Engineering/Tooling, and Quality reviewers using provenance-backed sanitized
data, then record signatures, findings, timings, context switches, and closure
of every Severe finding. This task is environment/business specific and cannot
be completed or signed by Codex. It remains the first incomplete requirement.

`implementation/phase-3-gate.md` nevertheless records the exact Pack-approved
continuation state: the technical release gate is `PASS`, the phase remains
`TECHNICAL_PASS_PENDING_UAT`, the external inputs are not a global blocker, and
Phase 4 is explicitly activated for independent NPI-owned domain work. Therefore
Phase 4 may continue without changing Phase 3 to `PASS` or concealing its UAT
obligation.

## Current implementation checkpoint

- Required development branch:
  `codex/npi-v1.2-implementation`.
- Current controller phase:
  `4 — Project Work Items and Stage Gates` (`IN_PROGRESS`).
- Completed atomic tasks:
  `P4-01`, `P4-02`, and `P4-03`.
- Latest completed atomic task:
  `P4-03 — Gate templates and controlled evidence`, committed at
  `0fd4762a01fd10fe6851df07ead1c5e4e7a42473`.
- Current unfinished atomic task:
  `P4-04 — Review, decision, snapshot, and reopen`.

P4-04 has completed only its read-only repository/specification inventory and
the implementation boundary in
`implementation/evidence/phase-4/p4-04-plan.md`. Its parallel implementation
agents were stopped before producing shared-file changes, and the incomplete
local transport-role draft was removed. No P4-04 product, contract, Schema,
permission, backend, frontend, translation, runtime, test, or visual change is
part of this checkpoint. P4-04 is **not implemented, not validated, and not
PASS**.

P4-04 owns `FR-SG-003`, `FR-SG-005`, `FR-SG-006`, and `FR-SG-007` within a
synthetic, versioned, safe-default-denied Gate review/decision slice. It must
preserve P4-03's immutable requirement/evidence history, separate assignment
from authority, create server-owned immutable decisions, preserve every prior
approval, and create controlled new cycles for reopen/invalidation.

Do not implement P4-05 live My Work/activity/notification delivery, production
template contents, guessed RACI-to-approval mappings, production waiver or
invalidation rules, normal-user file routes, production scanner/DMS behavior,
production ERPNext access, or any held production mapping in P4-04.

## Passed evidence — do not repeat for handoff

The committed P4-03 Level 3 evidence remains valid and must not be rerun merely
to resume in Codex Cloud:

- `make verify`: 276 Python and 237 frontend tests plus static/type/lint/style/
  boundary/UI/i18n, coverage, build, and zero npm audit findings;
- direct post-aggregate authorization repair: 20 affected tests;
- two successful additive/idempotent Site migrations;
- complete P4-01/P4-02/P4-03 runtime, including P4-03 run
  `2e070c8599694beabb6f5cf679a8c54b`;
- 153/153 non-visual browser cases;
- 159/159 forced and clean exact visual cases;
- trilingual original-resolution review; and
- independent security, traceability, Task Diff, and release-gate review.

These checks become applicable again only when later P4-04 changes actually
affect them or at P4-04's final required boundary. They are not a substitute
for any P4-04 test.

## Exact Codex Cloud resume steps

1. Open the repository on
   `codex/npi-v1.2-implementation`; fetch origin and verify the local HEAD is
   exactly `origin/codex/npi-v1.2-implementation` with a clean worktree.
2. Read `AGENTS.md`, `implementation/AUTOPILOT_CONTROLLER.md`,
   `implementation/PHASE_STATUS.yaml`, this file,
   `implementation/LAST_RUN.md`, `implementation/BLOCKERS.md`,
   `implementation/REQUIREMENT_TRACEABILITY.csv`, the Phase 4 anchor, and
   `implementation/evidence/phase-4/p4-04-plan.md`.
3. Confirm P4-03 remains the latest completed task and P4-04 has no product
   implementation. Do not reinterpret the plan as acceptance evidence.
4. Resume only P4-04 from Section 3 of its plan: first define the additive
   review-policy/persistence/transport-permission boundary and its direct
   tests; then add strict API/BFF, invalidation/impact-action/guard, and the live
   trilingual review room as one vertical slice.
5. Use Level 1 directly affected checks during repair. Because P4-04 changes
   public OpenAPI, DocType Schema, authorization/permission, and an accepted
   live route, run its applicable Level 3 exactly once after the complete slice
   stabilizes; after a localized repair rerun only affected checks plus any
   incomplete Gate lane.
6. Update durable P4-04 evidence and traceability truthfully. Do not activate
   P4-05 until P4-04 has a passing Gate and a pushed checkpoint.

## Still pending

- All P4-04 implementation and validation: domain, DocTypes, migration,
  transport permission, repository, API/BFF, contract/ownership, source-change
  invalidation, impact action/downstream guard, frontend, direct Chinese
  catalogs, unit/API/permission/runtime/E2E/accessibility/visual evidence,
  Task Diff review, trace review, and the applicable final Level 3.
- Phase 3 `FR-UX-031` named business UAT and provenance-backed sanitized-data
  review; it remains `TECHNICAL_PASS_PENDING_UAT`.
- Authoritative production approval/RACI, exception/waiver, disabled-member,
  dependency/downstream, scanner/DMS, and ERPNext mapping inputs.

Production ERPNext remains prohibited. No unfinished item above may be marked
PASS merely to complete a checkpoint.
