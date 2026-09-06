# P5-01 Projection Validation Repair and Final Gate Hard Blocker

Recorded: `2026-07-31T05:09:49Z`

Task:
`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Result:

`BLOCKED_EXTERNAL — THE AUTHORIZED PROJECTION-VALIDATION REPAIR IS PROVEN,
BUT THE SINGLE FINAL UNCHANGED CONTROLLED-SITE GATE FOUND A NEW POST-CHECKOUT
PDFSTREAM FAILURE`

P5-01 is not `PASS`, none of its seven requirements is promoted, the P5-01
Level 2 Task Gate did not run, and P5-02 remains inactive.

## Bounded authority

The user explicitly authorized one additional bounded P5-01
projection-validation diagnostic round:

1. add a closed validation-substage diagnostic inside `document.save()`;
2. emit only the substage code, validated exception type and exact trace ID;
3. run affected checks and complete normal CI;
4. execute exactly one diagnostic controlled-Site dispatch;
5. repair only the uniquely proven validation substage;
6. rerun affected checks and complete normal CI; and
7. execute exactly one final unchanged controlled-Site Gate.

The authority prohibited any change or weakening of a Requirement, API,
permission, Schema, lock, version, audit, idempotency, transaction order or
PASS criterion.

## Diagnostic checkpoint and normal CI

Diagnostic checkpoint:
`57b431411c130810f5f26109974922a8ae86cb4e`.

The checkout-only scope records exactly one of thirteen closed
projection-validation substage codes plus a validated exception type and the
exact trace ID. It never records the exception message, traceback, request,
cookie or credential. The verifier reads at most the final 64 KiB from two
fixed physical log paths, rejects symlinks and path escape, and accepts only
the exact three-field record for the matching trace.

Removing the diagnostic markers and wrappers produces the same repository
and Controlled Document controller AST as the parent checkpoint. No product
contract, permission, DocType, transaction or persistence behavior changed.

Local diagnostic-checkpoint evidence:

- focused controller/repository/runtime-verifier tests: `43/43 PASS`;
- complete P5 Document module group: `87/87 PASS`;
- complete tracked Python suite: `788/788 PASS`;
- Python compilation and whitespace: `PASS`.

Complete normal CI `#110`, run `30604536515`, passed on the exact checkpoint:

- repository job `91073991057`: complete repository verification, complete
  non-visual E2E, current-tree secret scan and complete PR-history secret scan
  `PASS`;
- visual job `91073991122`: fixed-Linux governed visual matrix `PASS`; and
- controlled runtime job `91073991606`: correctly skipped for the ordinary
  PR event.

## Sole diagnostic dispatch and unique root

The sole diagnostic dispatch was CI `#111`, run `30604964265`, event
`workflow_dispatch`, exact SHA `57b4314`.

- repository job `91075243192`: `PASS`;
- visual job `91075243245`: `PASS`;
- controlled runtime job `91075243225`: diagnostic `FAIL`;
- exact tools, fixed disposable Site/database, both app installations, both
  migrations and bounded cleanup: `PASS`.

The only accepted safe diagnostic was:

- substage: `DOCUMENT_CHECKOUT_PROJECTION_REVISION`;
- exception type: `ValidationError`;
- trace ID: `trace-bc506109a8f95e34b4ec8c4d8c518303`.

The checkout domain operation does not change the revision. Frappe hydrates
empty `Int` columns as `0`, while the existing domain projection normalizes
the same no-revision state to `None`. The revision validator compared the
auxiliary major/minor values before recognizing that both revision IDs were
absent, treated the normalization as a revision change and required an exact
successor with an empty identity. That is the only path in the proven
revision substage consistent with an unchanged empty revision and the
observed `ValidationError`.

## Only proven repair

Repair checkpoint:
`7dc4dc081b669874ab6c10323d774298d45a1c78`.

The repair changes only
`_validate_revision_projection`: when both old and new revision IDs are
absent, it treats the projection as the same empty revision before comparing
auxiliary fields. Existing domain reconstruction and normalization still
clear all auxiliary revision fields, while every non-empty revision continues
through the exact immutable-successor validation.

The repair commit contains exactly:

- the Controlled Document revision-projection validator; and
- one controller regression proving Frappe `Int` zero hydration versus the
  normalized empty projection.

It changes no Requirement, API, permission, Schema, lock, optimistic version,
audit, idempotency, transaction order or Gate standard.

Affected evidence after repair:

- focused controller/repository/runtime-verifier tests: `44/44 PASS`;
- complete P5 Document module group: `88/88 PASS`;
- complete tracked Python suite: `789/789 PASS`;
- Python compilation and whitespace: `PASS`.

Complete normal CI `#112`, run `30605323680`, passed on the exact repair SHA:

- repository job `91076268086`: complete repository verification, complete
  non-visual E2E, current-tree secret scan and complete PR-history secret scan
  `PASS`;
- visual job `91076268080`: fixed-Linux governed visual matrix `PASS`; and
- controlled runtime job `91076268612`: correctly skipped for the ordinary
  PR event.

The workflow, Bench/Site initialization scripts, controlled-runtime shell and
document runtime verifier are byte-for-byte unchanged between the diagnostic
and repair checkpoints.

## Single final unchanged Gate

The single final unchanged controlled-Site Gate was CI `#113`, run
`30605683679`, event `workflow_dispatch`, branch
`codex/npi-v1.2-implementation`, exact SHA `7dc4dc0`.

- repository job `91077318228`: complete repository verification, complete
  non-visual E2E and current-tree secret scan `PASS`; the PR-history scan is
  correctly inapplicable to a manual event;
- visual job `91077318229`: fixed-Linux governed visual matrix `PASS`;
- controlled runtime job `91077318323`: `FAIL`;
- exact tools, fixed disposable Site/database, both app installations, both
  migrations and bounded cleanup: `PASS`; and
- the controlled PASS-result step and artifact were correctly skipped.

The prior revision-substage diagnostic did not recur. The only accepted safe
diagnostic in the final Gate was:

- code: `UNEXPECTED_BFF_EXCEPTION`;
- exception type: `PdfStreamError`;
- trace ID: `trace-5a715a2d1776572ca1eac30bfbafe3f1`.

No raw exception message, traceback, request, cookie or credential was read
into or emitted by the retained evidence.

This is a new post-checkout failure outside the uniquely proven
projection-validation substage. The generic code does not prove which closed
revision/upload transaction boundary raised it. Guessing a product, File,
PDF fixture, revision, audit, idempotency or response repair would exceed the
explicit authority and could weaken controlled-file integrity.

## Hard Blocker and single unblock action

The one diagnostic dispatch and one final unchanged Gate are both exhausted.
The necessary controlled-Site Gate still fails, which is a controller Hard
Blocker. No further repair or dispatch is authorized.

The minimum safe unblock action is:

`Explicitly authorize one additional bounded P5-01 post-checkout
PdfStreamError diagnostic round: add only closed revision/upload transaction
stage codes that emit stage code + validated exception type + exact trace ID,
run affected checks and complete normal CI, execute one diagnostic
controlled-Site dispatch, repair only the uniquely proven stage, rerun
affected checks and complete normal CI, and execute one final unchanged
controlled-Site Gate. Do not change or weaken any Requirement, API,
permission, Schema, file-integrity rule, lock, version, audit, idempotency,
transaction order or PASS criterion.`
