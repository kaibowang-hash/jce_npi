# Phase 3 Business UAT Script and Unsigned Result Record

Status: **PENDING BUSINESS REVIEW — NOT SIGNED BY CODEX**
Prepared: 2026-07-22
Scope: Phase 3 industrial SPA and localization prototype only

Execution readiness: **READY FROM THE RELEASE-GATED PHASE 3 CHECKPOINT**. The
technical browser and visual reruns are complete, but no business-reviewer
walkthrough or signature is recorded.

## Preconditions

1. Run the application from the final reviewed Phase 3 checkpoint with
   prototype data visibly identified. Do not connect a production ERPNext
   system.
2. Use a 1366×768 or 1920×1080 desktop browser. Repeat the Trial field step on
   a 768×1024 tablet or equivalent device.
3. Complete every flow in English (`en`), Simplified Chinese (`zh`) and
   Traditional Chinese (`zh-TW`). Refresh once after each language change.
4. Record confusion, wrong context, hidden impact, language mixing, accidental
   action or inability to finish as a finding. Severity is Severe, Major or
   Minor. Any open Severe finding prevents acceptance.

## Review roles

| Role | Required reviewer | Focus |
|---|---|---|
| Project Management | Name and signature required | Work ownership, project context and Gate decisions |
| Engineering / Tooling | Name and signature required | Tooling revisions, Trial inheritance and field usability |
| Quality | Name and signature required | Evidence, formal-quality blockers and decision safety |

## Six walkthroughs

### UAT-03-01 — My Work to blocking Gate evidence

Reviewer: Project Management
Start: `/work`

1. Locate the overdue T1 flash-defect item and explain why it is assigned.
2. Open its next action and verify the same project/Gate context is retained.
3. Identify the missing evidence and the traceable blocker.

Expected: the user reaches G5 without DocType/Desk navigation, understands the
assignment, and sees no approval or completion claim.

### UAT-03-02 — Project Cockpit corrective action

Reviewer: Project Management
Start: `/projects/PJ-26018`

1. Identify the active lifecycle position, major blocker and accountable role.
2. Prepare the corrective action.
3. Confirm that the result says a prototype command was prepared and nothing
   was saved.

Expected: project, Gate, Tooling, Trial, NPI and ERPNext context is readable
without leaving the cockpit; no fake persistence occurs.

### UAT-03-03 — Tooling design release impact

Reviewer: Engineering / Tooling
Start: `/tooling/TL-26018-01`

1. Review the current immutable design and dependent Trial/milestone context.
2. Open the design release impact review, enter a reason and prepare it.
3. Verify Revision C remains unchanged and no release is claimed.

Expected: the reviewer understands affected objects before confirmation and
can cancel with keyboard focus returning to the trigger.

### UAT-03-04 — Inherited Trial and round comparison

Reviewer: Engineering / Tooling
Start: `/tooling/TL-26018-01`

1. Create T1 from T0.
2. Verify locked input versions and inheritance are explicit.
3. Open Round comparison and inspect the result.
4. On the tablet, locate the localized photo action and primary conclusion
   command without horizontal document scrolling.

Expected: no copied value is presented as a new approved baseline; the field
layout and photo action remain operable.

### UAT-03-05 — Tooling acceptance to ERP execution

Reviewer: Engineering / Tooling
Start: `/tooling/TL-26018-01`

1. Review tooling acceptance impact and prepare the acceptance command.
2. Verify that ERPNext asset execution explicitly has not started.
3. Open the execution panel and locate the formal-write status.

Expected: NPI preparation, queueing and ERPNext completion are visually and
semantically distinct; the prototype never claims an asset was created.

### UAT-03-06 — Formal quality failure blocks G6

Reviewer: Quality
Start: `/projects/PJ-26018`

1. Open G6 from the Project Gate track.
2. Identify the failed ERPNext quality result and explain its source.
3. Verify readiness percentage cannot override the blocker.
4. Open the decision impact review without submitting a formal decision.

Expected: formal quality failure is non-bypassable, non-colour-only and
traceable; the review does not fabricate a saved decision.

## Per-locale and usability record

| Flow | en result | zh result | zh-TW result | Duration | Context switches | Findings |
|---|---|---|---|---:|---:|---|
| UAT-03-01 | Pending | Pending | Pending |  |  |  |
| UAT-03-02 | Pending | Pending | Pending |  |  |  |
| UAT-03-03 | Pending | Pending | Pending |  |  |  |
| UAT-03-04 | Pending | Pending | Pending |  |  |  |
| UAT-03-05 | Pending | Pending | Pending |  |  |  |
| UAT-03-06 | Pending | Pending | Pending |  |  |  |

## Finding log

| ID | Flow / locale | Severity | Observation | Owner | Resolution evidence | Status |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## Sign-off

| Role | Reviewer | Result | Date | Signature / approved record |
|---|---|---|---|---|
| Project Management |  | Pending |  |  |
| Engineering / Tooling |  | Pending |  |  |
| Quality |  | Pending |  |  |

Business acceptance is complete only when all three named reviewers sign, all
18 locale/flow passes are recorded, and no Severe finding remains open. The
release-gated technical checkpoint does not supply those signatures; until
they are complete, the truthful Phase 3 acceptance state is
`TECHNICAL_PASS_PENDING_UAT`.
