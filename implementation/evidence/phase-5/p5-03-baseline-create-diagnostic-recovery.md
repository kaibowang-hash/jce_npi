# P5-03 Baseline-Create Diagnostic Recovery Checkpoint

Recorded: `2026-08-02T19:11:28Z`

Status:
`IN_PROGRESS_DIAGNOSTIC — NO P5-03 PASS`

Requirement:
`FR-DS-006`

Recovered base HEAD:
`a1d84294641cb0b8cf71002c3d3557cb6b485ce7`

Complete ordinary CI:
`30761151383` (`PASS`)

Diagnostic-only controlled-Site run:
`30761455482` (`FAIL`, diagnostic evidence only)

Accepted safe diagnostic tuple:

- stage code: `P503_VERIFIER_POST_WORKSPACE_BASELINE_CREATE`
- verified exception type: `RuntimeError`
- exact trace ID: `trace-f9c9295e07be5bec93aa8b6b05cc2c30`

P5-03 final unchanged controlled-Site Gate:
`NOT EXECUTED`

## Recovery conclusion

The accepted tuple proves only that the controlled verifier reached the
post-workspace baseline-create phase. It does not uniquely distinguish a
server-side baseline-create substage, so it authorizes no product repair and
cannot support a Gate `PASS`.

The current workspace contains unrelated tracked and untracked user changes.
This checkpoint modifies only controller/evidence files. In particular, the
existing dirty `implementation/LAST_RUN.md` is protected and is not staged,
overwritten or incorporated into this checkpoint.

## Product-root accounting

`implementation/evidence/phase-5/p5-03-plan.md` records four completed genuine
product-root repairs before this controlled sequence. The closed
baseline-workspace diagnostic uniquely proved an incorrect Project field
mapping. Repair `2b067c1cbd0977d843780d386bfc882b80615b33` corrected only
that mapping and advanced the same unchanged Gate to the new baseline-create
failure. Under `implementation/AUTOPILOT_CONTROLLER.md`, that is the fifth
completed product-root repair.

The user's current authorization is one additional, strictly bounded P5-03
repair exception for the current `baseline-create` root only. It does not
modify the controller's global five-round rule. Behavior-neutral diagnostic
narrowing remains `IN_PROGRESS_DIAGNOSTIC` and consumes no product-root round.

## Authorized diagnostic boundary

The existing behavior may be wrapped with closed diagnostics at only these
stages:

- command context;
- input parse;
- Project lock;
- membership authority;
- policy load;
- idempotency replay;
- member resolve;
- domain build;
- receipt insert;
- baseline insert;
- member insert;
- audit append;
- response build;
- receipt seal;
- client HTTP;
- response shape; and
- response contract.

Diagnostic output is limited to an allowlisted stage code, a validated
exception type and the exact trace ID. Exception text, traceback, request,
response, Cookie, credentials, business data and storage paths are forbidden.
Requirement, API, permission, Schema, ownership, locks, versions, audit,
idempotency, transaction order and PASS criteria remain frozen.

## Dispatch and repair limits

- Newly authorized diagnostic-only controlled-Site dispatches: `2` maximum.
- Dispatches used under this new authority: `0`.
- Before every dispatch: affected tests and complete ordinary CI must pass.
- Diagnostic convergence itself does not consume a product-root repair.
- A repair is permitted only after one unique server root is proved and
  cross-validated against `FR-DS-006`, the Requirement anchor, OpenAPI, true
  DocType fields, permissions and transaction invariants.
- After that one repair: rerun affected tests, complete ordinary CI and one
  final unchanged controlled-Site Gate with diagnostic activation closed.
- If two dispatches cannot uniquely prove a root, or the required change is a
  business-rule, API, permission, Schema, ownership or transaction-order
  change, stop and record one blocker without guessing.

## Next action

Implement and test the behavior-neutral closed diagnostic ladder. Do not
resume Gate-evidence/dependency work, P5-04, P5-05 or Phase 6 until the current
P5-03 baseline-create root is closed by the authorized sequence.
