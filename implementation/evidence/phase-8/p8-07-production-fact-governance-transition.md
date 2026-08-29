# P8-07 Production Fact Documentation Governance Transition

Date: `2026-08-28`

Status: **TRANSITION PASS; DOCUMENTATION BASELINE CANDIDATE**

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

The transition itself is accepted at exact SHA
`74aa849dce34374521119b09eb2d59e8c2be0445`; ordinary CI `33136143519`
passes repository `98736441843`, visual `98736441983`, frontend
`98736441999` and secret `98736442002`. Controlled lanes correctly skip.

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

## Documentation baseline candidate

The subsequent exact-20 task creates
`docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md`, links it only to the frozen
integration-hold evidence set and leaves every requirement status unchanged.
It records the five explicit classifications and the independent evidence
axis, keeps `implementation/REQUIRED_INPUTS.md` as the sole external request,
and preserves P8-07 audit-only/product-code-false state. Its changed-files to
checks map is the current/reconciliation scripts and their two unit modules;
product, contract, workflow and external-state diffs remain zero.

Level 1 candidate verification on `2026-08-28` passes:

- current-task, canonical reconcile and reconciliation verifier;
- `37/37` focused current/reconciliation unit tests;
- JSON, YAML and strict CSV parsing, Python compile and diff hygiene;
- the document classification/section/security scan and exact 18-ID
  integration-hold evidence set with all `282` trace statuses unchanged;
- exact twenty changed paths accepted, unauthorized path twenty-one rejected;
- zero app, frontend, contract or workflow diff and no production connection,
  endpoint, credential, secret, response or business value collected.

The documentation candidate still requires its own exact-SHA ordinary CI.
That CI does not authorize production fact collection or P8-07 product code.

## 2026-08-29 user authorization supersession

The earlier `QUEUED_NOT_EFFECTIVE` state is superseded only through the new
two-Gate sequence documented in `p8-07f-production-fact-reconciliation-plan.md`.
P8-07 has now passed Level 3, but the current `P8-07F-GOVERNANCE` transition
still performs zero production contact. Standing read-only authority becomes
effective only after this transition's exact-SHA ordinary CI and Level 3 PASS
and a separate controller activation of `P8-07F-FACTS`.

The purpose is compatibility reconciliation and minimal adjustment. Existing
LaunchFlow architecture, ownership, contracts and P8-01 through P8-09 design
are the default-correct baseline; no redesign/refactor/rebuild is authorized.
The SSH transport/operation allowlist, redaction/provenance/checksum, stop
conditions, persistent delta-first usage and final full reconciliation Gate
are frozen in the P8-07F plan. P8-08 remains closed until the facts task and
its Gate pass.

## 2026-08-30 transition exact-SHA Gate

The superseding P8-07F governance transition is accepted at exact SHA
`d919d695972260fa86d5df7fa60033e6adb62f49`. Ordinary CI `33279778063`
passes repository `99172860297`, frontend `99172860137`, secret
`99172860343` and governed visual `99172860279`. Level 3 `33280319184`
passes repository `99174278508`, frontend `99174278534`, secret
`99174278422`, visual `99174278532`, controlled preflight `99175743503` and
cumulative runtime `99175763495`. No SSH, connector, Site or production fact
operation occurred in the transition.

The controller may now activate only `P8-07F-FACTS`. Its first commit freezes
the exact task manifest and a repository-governed collector. The first
production read still requires that activation commit's exact-SHA ordinary CI
to pass. P8-08, product changes and production mutation remain inactive.
