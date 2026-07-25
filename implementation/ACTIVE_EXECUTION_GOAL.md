# Active Execution Goal

Updated: `2026-07-25T09:09:22Z`

- Mode: `NPI One V1.2 AUTOPILOT CONTINUOUS DELIVERY`
- Final target: `IMPLEMENTATION_COMPLETE` or a true Hard Blocker defined by
  `implementation/AUTOPILOT_CONTROLLER.md`
- Current work: execute `P4-05 — Live My Work, activity, and Project controls`
  from the passing P4-04 Level 3 checkpoint; P4-01 through P4-04 are complete
- Automatic transition: enabled after each passing atomic task and Phase Gate
- Stop-after-P4-04: disabled
- P4-05 and later phases: automatically continue after each applicable Gate
- Source of truth: `AGENTS.md`, `GOAL.md`,
  `implementation/AUTOPILOT_CONTROLLER.md`,
  `implementation/PHASE_STATUS.yaml`, `implementation/NEXT_ACTION.md`,
  `implementation/LAST_RUN.md`, Requirement Anchors, Requirement Traceability,
  the Execution Pack, and accepted ADRs
- Compact/recovery rule: reread this file,
  `implementation/AUTOPILOT_CONTROLLER.md`,
  `implementation/NEXT_ACTION.md`, and `implementation/LAST_RUN.md` before
  replanning after context compaction, session recovery, tool interruption,
  long-running validation, automatic replanning, or agent handoff
- Chat memory: non-authoritative
- Permanent requirements: unchanged

Historical thread-local stop, pause, handoff, and “P4-05 forbidden” boundaries
are retained as history but have status
`SUPERSEDED_BY_LATEST_USER_AUTOPILOT_AUTHORIZATION`. P4-04 has now passed all
applicable Gates, so P4-05 is active without another prompt.

This file records execution intent and recovery behavior only. It does not add,
remove, reinterpret, or replace a product requirement, contract, accepted ADR,
quality criterion, security boundary, data-ownership rule, or Phase Gate.
