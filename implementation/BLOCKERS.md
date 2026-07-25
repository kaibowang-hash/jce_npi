# Blockers

## Active hard blockers

None.

## Active execution hold

`P5-01` is `IN_PROGRESS — V1_2_RECONCILIATION_HOLD`.

The user directed a recoverable pause before the machine-executable Pack is
reconciled with the authoritative V1.2 DOCX. This hold:

- does not cancel V1.2 or change any product requirement;
- is not an `AUTOPILOT_CONTROLLER.md` Hard Blocker;
- does not permit P5-01 to be marked `PASS`;
- prevents another P5-01 sub-slice, P5-02, or Phase 6 from starting; and
- resumes first with a reconciliation comparison against the checkpoint
  evidence in
  `implementation/evidence/phase-5/p5-01-reconciliation-hold.md`.

## Current P5-01 scope

Phase 4 and P4-05 passed their complete triggered Level 3 Full Release Gate.
`P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
EBOM` is `PASS`. `P5-01 — Document and design revision` remains incomplete
under the current reconciliation hold and is governed by
`implementation/phase-5-requirement-anchor.md`,
`implementation/ACTIVE_EXECUTION_GOAL.md`, and
`implementation/NEXT_ACTION.md`.

The retained checkpoint contains the bounded Controlled Document/Document
Revision/private File Revision backend slice, Project-scoped
confidentiality/download audit, locks, capability-truth preview/download
fallback, and the connector-unavailable seam. No further P5-01 implementation
may begin while this hold is active. On resume, P5-01 must not invent
production document numbering, classification, retention, scanner/viewer,
sharing, revision or CAD/PDM rules; review/release/baseline/EBOM/formal
publish remain P5-02 through P5-05. Production ERPNext/CAD/PDM access and
external file retrieval remain prohibited or fail closed.

The open production Project-health formula, threshold, lifecycle authority,
completion-prerequisite, notification-delivery and external-collaboration facts
remain scoped activation holds. Their generic versioned/fail-closed Phase 4
foundation is complete; no missing rule is inferred and no external delivery
is represented as operational.

Phase 3 named business UAT and sanitized-data provenance remain externally
unsigned. They are not a global blocker and cannot be signed by Codex.

## Open external acceptance and reconciliation inputs

`implementation/REQUIRED_INPUTS.md` is the single complete request for external
material. Its open Phase 3 UAT/sanitized-data items keep final business
acceptance at `TECHNICAL_PASS_PENDING_UAT`; its ERPNext facts pause only work
that would otherwise guess existing customization, numbering, state, field
ownership, mapping, sandbox behavior or a real-data result. These are partial
dependencies, not a global Hard Blocker. Production ERPNext credentials and
activation remain prohibited and are not requested.

## Scoped Phase 4 rule holds

Phase 4 `P4-00` reconciled the controller/M3 Project-and-Gate boundary with Pack
trace rows that also mention portfolio, external collaboration, notifications,
ERP-owned cost, ERP-triggered creation, or external scheduling. The affected
requirements are explicitly remapped without losing their original acceptance.
Production project numbering/source rules, template/skip/duration content,
RACI-to-approval mapping, per-kind Domain WorkItem lifecycle, health/cost
thresholds, Gate waiver/invalidation authority, and project lifecycle approvals
remain Class-B holds until authoritative facts exist. Only those ambiguous
rules are held.
The temporal policy for disabled members' historical or future
role/substitution relations is also held. P4-02 permits only a
non-expansive finite end date on an existing membership identity; it does not
invent a broader retention or revocation rule.
Generic/versioned NPI-owned Project/Gate infrastructure, explicit synthetic
fixtures, contracts, automated tests, localization, UI and documentation can
continue.

P4-03 deliberately did not install production Gate condition/skip/duration
content, RACI-to-approval mapping, evidence-eligibility expansion,
scanner/provider policy, P0 pass policy, waiver authority, or automatic
invalidation rules. These remain scoped Class-B holds. The passing P4-04 slice
uses only a versioned synthetic policy and safe-default-denied behavior; P4-05
must preserve that boundary.

## Resolved checkpoints

- Phase 1.1 fresh target-container validation passed on 2026-07-21 after repair
  round 4.
- The first Phase 3 gate candidate had passing visual, localization, runtime,
  permission, migration and test evidence, but independent review correctly
  returned it for error, CSRF, and privacy repair before a final decision.
- Phase 3 repair round 1 closed error/trace/retry, CSRF, unexpected
  ProblemDetails, telemetry route, transaction and request-locale atomicity
  defects. Independent final review returned technical `PASS` on 2026-07-22;
  Phase 3 is `TECHNICAL_PASS_PENDING_UAT` and Phase 4 is active.
- The P4-02 checkpoint review found a forgeable unsigned Domain WorkItem cursor
  and positional backend translation placeholders. The checkpoint now signs
  every cursor field with a Site-bound domain-separated HMAC, fails closed when
  secure signing is unavailable, rejects forged/tampered/cross-Site cursors,
  uses named placeholders, and statically rejects positional translation
  placeholders. Focused tests and the repaired real Frappe runtime passed.
- Final P4-02 review also found configuration auto-provision, API
  validation-order, related-object tenant, and disabled-member closure gaps.
  The final repair reads only an existing Site key, authorizes before cursor
  validation, checks Project plus tenant on tenant-bearing references, and
  permits only non-expansive end-dating of an existing disabled membership.
  Sixty-three affected Python tests and a fresh Frappe runtime passed.
- The earlier Cloud browser restriction is closed for P4-02. Its complete
  eight-case browser spec, supplemental shards, forced and clean exact
  147-case visual runs, six original-resolution trilingual reviews, and
  independent release review passed on 2026-07-23. P4-02 is `PASS`; P4-03 is
  complete.
- P4-03's independent versioned Gate Template, frozen Project requirement
  snapshots, exact append-only WBS/private File Revision evidence, live scan
  truth, URL-free BFF, and trilingual live workspace passed the triggered Level
  3 gate on 2026-07-24. The final evidence includes additive/idempotent
  migrations, complete P4-01/P4-02/P4-03 runtime, 153 non-visual browser cases,
  159 forced and clean exact visual cases, original-resolution review, and
  independent security/trace/release review.
- P4-04's missing-repository, history-retention, long-text, closure-drift,
  Docker-runtime, npm-vulnerability, install-policy, localization, browser,
  and visual-baseline findings are resolved. Its complete evidence includes
  417 Python tests, 337 frontend tests, two migrations, all six live runtime
  lanes, 1,746 direct trilingual sources, 204 non-visual browser cases, forced
  and clean 170-case exact visual matrices, zero npm vulnerabilities, and
  independent release review. P4-04 is `PASS`; that Gate activated P4-05.
- P4-05's derived-assignment failure semantics, keyboard bubbling, 409 reload,
  proposal-truth, time-zone copy and shared-catalog visual findings are
  resolved. Its complete evidence includes 587 Python tests, 492 frontend
  tests, 2,221 direct trilingual sources, additive/idempotent Site
  synchronization, complete cumulative runtime, 227 non-visual browser cases,
  forced and clean 188-case exact visual matrices, and independent review.
  P4-05 and Phase 4 are `PASS`; that Gate activated P5-00.
- P5-00 allocated all fourteen Phase 5 design/document requirements to the
  Pack's five M4 tasks, froze file/document/baseline/EBOM/ERP ownership,
  retained external-sharing, preview, CAD/PDM and ERP execution holds, and
  activated only P5-01 without changing Schema or runtime behavior.
