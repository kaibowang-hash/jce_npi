# P5-01 Post-Checkout Recovery

Recorded: `2026-07-31T05:42:15Z`

Task:
`P5-01 — Document and design revision`

State:
`IN_PROGRESS_DIAGNOSTIC — AUTHORIZED REVISION/UPLOAD STAGE CHECKPOINT`

## Frozen product path

The active Requirements remain:

- `FR-DS-001`;
- `FR-DS-003`;
- `FR-DS-004`;
- `FR-DS-007`;
- `FR-DS-008`;
- `FR-DS-009`; and
- `FR-DS-014`.

No Requirement, API, permission, Schema, ownership, file-integrity rule, lock,
version, audit, idempotency, transaction order or PASS criterion may change in
this recovery. P5-02 remains inactive until one real controlled-Site PASS and
the P5-01 Level 2 Task Gate.

## Auto Pilot execution guard

Repair-round accounting is now product-root based:

- runner/bootstrap/verifier/fixture-precondition failures are environment
  remediation;
- behavior-neutral closed diagnostics are `IN_PROGRESS_DIAGNOSTIC`; and
- only a uniquely proven implementation root after exact environment, Site,
  App, migration and fixture preconditions begins a product-root repair round.

Neither environment remediation nor diagnostic progress is a Gate PASS.
Five complete product-root repair rounds, a Class B/C decision, a required
contract/permission/Schema/ownership change, or a concrete security/license
risk remains a true stopping condition.

## Closed diagnostic inventory

The existing revision transaction order is unchanged. Unexpected non-domain
exceptions may record exactly one of:

1. `DOCUMENT_REVISION_RECEIPT_INSERT`;
2. `DOCUMENT_REVISION_PRIVATE_FILE_SAVE`;
3. `DOCUMENT_REVISION_FILE_REVISION_INSERT`;
4. `DOCUMENT_REVISION_DOMAIN_APPEND`;
5. `DOCUMENT_REVISION_RECORD_INSERT`;
6. `DOCUMENT_REVISION_FILE_ASSOCIATION_INSERT`;
7. `DOCUMENT_REVISION_PROJECTION_SAVE`;
8. `DOCUMENT_REVISION_AUDIT_APPEND`;
9. `DOCUMENT_REVISION_RESPONSE_BUILD`; or
10. `DOCUMENT_REVISION_RECEIPT_SEAL`.

The retained safe record contains exactly `code`, `exceptionType` and
`traceId`. Raw exception messages, traceback, request data, cookies and
credentials are excluded. Expected `NpiProblem` outcomes are not diagnostic
events, and diagnostic failure cannot replace the original exception.

## Changed files to affected checks

| Boundary | Affected checks |
|---|---|
| Auto Pilot repair classification | controller guard tests, V1.2 reconciliation, YAML and whitespace |
| revision transaction diagnostic wrappers | exact closed inventory/order, expected-domain exclusion, secondary-diagnostic behavior, P5 repository/API/controller regressions |
| safe runtime diagnostic selection | exact trace/schema/type/code, stage-over-generic preference, fixed path/symlink/64-KiB bounds and non-disclosure |
| recovery state/evidence | P5 trace remains incomplete, P5-02 inactive, no Requirement or contract drift |

## Required execution

1. pass affected checks and complete normal CI;
2. execute one controlled-Site diagnostic dispatch on the exact checkpoint;
3. repair only the uniquely proven stage;
4. rerun affected checks and complete normal CI;
5. execute one final unchanged controlled-Site Gate; and
6. only after runtime PASS, execute the complete P5-01 Level 2 Task Gate.

No controlled runtime result is claimed by this diagnostic checkpoint.

## Local diagnostic-checkpoint evidence

- controller/repository/runtime-verifier focused group: `36/36 PASS`;
- complete P5 document, controller, runtime, reconciliation and guard group:
  `109/109 PASS`;
- complete tracked Python suite: `795/795 PASS`;
- complete current workspace Python discovery: `801/801 PASS`;
- baseline-versus-checkpoint `create_revision()` non-diagnostic call sequence:
  identical `61/61`;
- V1.2 reconciliation verifier: `PASS`;
- Python compilation, YAML parsing and whitespace: `PASS`.

The current workspace discovery includes pre-existing untracked local
prerequisite tests. They pass but are not part of this checkpoint. Complete
normal CI remains required before dispatch.
