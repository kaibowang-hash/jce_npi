# Active Execution Goal

Updated: `2026-07-25T18:21:56Z`

- Goal: `NPI One V1.2 — Autopilot Continuous Delivery`
- Codex Goal ID: `019f97ce-d6ad-74f2-8f14-68f2d0d5e962`
- Mode: `NPI One V1.2 AUTOPILOT CONTINUOUS DELIVERY`
- Final target: `IMPLEMENTATION_COMPLETE` or a true Hard Blocker defined by
  `implementation/AUTOPILOT_CONTROLLER.md`
- Branch: `codex/npi-v1.2-implementation`
- Last confirmed remote checkpoint before this release commit:
  `028d551d4e02ad5700b165c21409e14b647babf0` (`0` ahead / `0` behind at
  P5-00 recovery)
- Current release checkpoint: P5-00 anchor/trace/recovery changes in this
  commit;
  confirm and record the exact remote SHA immediately after push
- Current Phase: `5 — Part Design, Documents, Baselines, and EBOM`
  (`IN_PROGRESS`)
- Current atomic task:
  `P5-01 — Document and design revision`
- Completed scope: Phase 4 P4-01 through P4-05 and the Phase 4 Gate are
  `PASS`; Phase 5 controller task P5-00 is `PASS`
- Current accepted P4-05 evidence: 587 Python tests; 492 frontend tests;
  2,221 literal English sources with complete direct `zh`/`zh-TW`; additive
  and idempotent Site synchronization; complete cumulative Frappe runtime;
  227/227 non-visual Playwright; forced and clean 188/188 zero-tolerance
  visuals; original-resolution trilingual and independent release reviews
- Reusable prior evidence: every accepted P4-01 through P4-04 task report;
  P4-05/Phase 4 Level 3 evidence; and the P5-00 documentation/trace Gate;
  do not repeat them merely to restore context
- External state retained: Phase 3 remains
  `TECHNICAL_PASS_PENDING_UAT`; production rule packages and ERPNext facts
  remain scoped holds, not a global blocker
- First incomplete action: create
  `implementation/evidence/phase-5/p5-01-plan.md`, set only the P5-01
  traceability rows to `IN_PROGRESS_P5_01`, inventory the existing private
  File Revision and Project/BFF/UI foundations, then implement the bounded
  Controlled Document/Document Revision vertical slice from
  `implementation/phase-5-requirement-anchor.md`
- Automatic transition: enabled after each passing atomic task and Phase Gate
- Source of truth: `AGENTS.md`, `GOAL.md`,
  `implementation/AUTOPILOT_CONTROLLER.md`,
  `implementation/PHASE_STATUS.yaml`, `implementation/NEXT_ACTION.md`,
  `implementation/LAST_RUN.md`, Requirement Anchors, Requirement Traceability,
  the Execution Pack, contracts, and accepted ADRs
- Compact/recovery rule: reread this file,
  `implementation/PHASE_STATUS.yaml`, `implementation/NEXT_ACTION.md`, and
  `implementation/LAST_RUN.md` before replanning after compaction, model
  switch, tool interruption, automatic replanning, or agent handoff
- Chat memory: non-authoritative
- Permanent product, architecture, domain, permission, UI, i18n, ownership and
  quality requirements: unchanged

Historical thread-local stop, pause, handoff, and single-Phase boundaries
remain history with status
`SUPERSEDED_BY_LATEST_USER_AUTOPILOT_AUTHORIZATION`.

P5-00 passed as a documentation/trace-only controller task. P5-01 is the only
active Phase 5 product task. Review/release, baselines, EBOM and formal publish
requests remain P5-02 through P5-05 and must not begin early.

This file records execution intent and recovery behavior only. It does not add,
remove, reinterpret, or replace a product requirement, contract, accepted ADR,
quality criterion, security boundary, data-ownership rule, or Phase Gate.
