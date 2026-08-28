# P8-07 Production Fact Documentation Governance Transition

Date: `2026-08-28`

Status: **TRANSITION PENDING EXACT-SHA ORDINARY CI**

## Authority boundary

The user requested a future production read-only ERPNext fact check and an
ERPNext customization requirements document. This request is recorded as
`QUEUED_NOT_EFFECTIVE`. Current `AGENTS.md` and the autopilot controller still
prohibit production ERPNext contact. This transition performs no SSH command,
connector use, endpoint probe, credential use, request, response read, replay,
reconciliation or other production action.

P8-07 remains audit-only for `FR-RP-009`, `UX-016` and `NFR-INT-001`.
`product_code_authorized` remains false. Requirement IDs, trace statuses,
contracts, product code and external state are unchanged.

The task-diff base is the accepted P8-06 closeout/P8-07 activation checkpoint
`d39b24e4169d6116ab0721440b1f7dc01b599c96`, whose ordinary CI
`33134622237` passed. The predecessor product checkpoint remains
`547421a059911df6aeb90bbbf06e837f77a3e5e0`; advancing the governance base
does not rewrite or supersede the product checkpoint.

## Exact transition paths

1. `implementation/ACTIVE_EXECUTION_GOAL.md`
2. `implementation/AUTOPILOT_CONTROLLER.md`
3. `implementation/BLOCKERS.md`
4. `implementation/CURRENT_TASK.json`
5. `implementation/DECISION_LOG.md`
6. `implementation/NEXT_ACTION.md`
7. `implementation/PHASE_STATUS.yaml`
8. `implementation/RISK_REGISTER.md`
9. `implementation/evidence/phase-8/p8-07-production-fact-governance-transition.md`
10. `tests/test_current_task_verifier.py`

## Frozen future documentation manifest

Only after this transition passes exact-SHA ordinary CI may the next atomic
task modify the exact twenty paths in `implementation/CURRENT_TASK.json`.
That task may create `docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md` as a
facts/status/acceptance matrix, preserve `implementation/REQUIRED_INPUTS.md`
as the sole external-input request, update the specification index,
repository facts, roadmap, quality Gate, controller state and exact trace
evidence, and strengthen the current/reconciliation verifiers and tests.

The document must not invent endpoint, credential, field, schema, workflow,
status, identity, count or business value. Production facts remain
`EXTERNAL_EVIDENCE_REQUIRED`; connection remains
`PROHIBITED_PENDING_RULE_CHANGE_AND_GATE`.

## Future connection prerequisites

This transition does not satisfy any prerequisite below. A later connection
would require a separately approved higher-priority `AGENTS.md`/controller
rule change, exact read-only command allowlist, least-privilege principal,
strict host-key verification, non-interactive bounded execution, timeouts,
redaction and secret exclusion, no writes or side-effect methods, provenance
and checksums, and its own release Gate. Any mismatch must fail closed.

## Validation contract

- Changed paths are exactly the ten transition paths above; no product,
  contract, workflow or trace-status diff exists.
- The future allowed-path manifest contains exactly twenty literal paths and
  no wildcard, app, frontend or contract path.
- Current-task and reconciliation checks, JSON/YAML/CSV parsing and diff
  checks pass.
- The exact-ten task manifest accepts this transition and an unauthorized
  eleventh path is rejected.
