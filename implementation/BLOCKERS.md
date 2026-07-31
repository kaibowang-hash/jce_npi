# Blockers

Updated: `2026-07-31T07:00:05Z`

## Active hard blockers

None. P5-01 passed its controlled-Site and Level 2 Task Gates; P5-02 is
authorized active.

## Active diagnostic progress

None.

The P5-01 closed diagnostic inventory retained only allowlisted stage code,
validated exception type and exact trace ID. It led to a valid synthetic PDF
fixture and one strict relationship-query parser repair without weakening the
product or Gate. Complete ordinary CI `30610355829` and final unchanged
controlled-Site workflow `30610747931` passed on exact product SHA `5a9cd3d`.

Evidence:
`implementation/evidence/phase-5/p5-01-validation.md`.

## Resolved hard blockers

`P5-01-CONTROLLED-RUNTIME-POST-CHECKOUT-PDFSTREAM-DIAGNOSTIC-LIMIT`

The user-authorized recovery plan satisfies the prior execution-authority
hold. The safe `PdfStreamError` remains unresolved and is now active
diagnostic progress rather than a product `PASS`.

`P5-01-CONTROLLED-RUNTIME-PROJECTION-SUBSTAGE-DIAGNOSTIC-LIMIT`

The user supplied the exact bounded authority on 2026-07-31. Diagnostic
checkpoint `57b4314` and dispatch `30604964265` uniquely proved the revision
validation substage. Repair `7dc4dc0` is locally and normal-CI green and the
prior substage did not recur in the final Gate. The execution-limit blocker
is resolved; the fixed controlled-Site Gate is not. The new downstream
failure is the active Hard Blocker above.

`P5-01-CONTROLLED-RUNTIME-CHECKOUT-STAGE-DIAGNOSTIC-LIMIT`

Checkpoint `e4b284f` and controlled run `30598733723` safely proved
`ValidationError / UNEXPECTED_BFF_EXCEPTION` but not a unique checkout stage.
The user supplied the exact additional bounded authorization on 2026-07-31.
The execution-limit blocker is resolved; the fixed controlled-Site Gate is
not. The active round permits only one allowlisted stage-diagnostic
checkpoint, one controlled-Site diagnostic dispatch, repair of only its
proven stage, affected checks/normal CI and the already authorized final
unchanged Gate. Local focused `28/28`, P5 Document `83/83` and complete
tracked Python `784/784` checks pass. Evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-stage-diagnostic.md`.

Exact checkpoint `954bd0d` passed normal CI `#104`, run `30600587269`.
The sole authorized diagnostic dispatch `30600943765` then proved
`ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE` while fixed setup,
migrations and cleanup passed. The later exact-event binding candidate passed
normal CI but failed its retained final unchanged Gate at the same stage and
was forward-reverted. The remaining projection-validation substage authority
is now the active hard blocker above.

`P5-01-CONTROLLED-RUNTIME-CHECKOUT-DIAGNOSTIC-REPAIR-LIMIT`

The explicitly authorized shared-Datetime repair is complete at
`7aa14edbdd2e484784cee6a8ec52adef4f6bf328`. Normal CI `#98`, run
`30573186630`, passed on that exact SHA. The single authorized manual
controlled-Site run `#99`, `30573778175`, advanced beyond the previously
failing policy publication, created the controlled document and passed its
immediate idempotency replay. The first `:check-out` command then returned
HTTP `500`.

This progression proves that the shared Frappe Datetime persistence repair
closed the prior publication blocker. It also proves that setup, migrations,
schema synchronization, disposable owner, Project, policy publication,
document creation and immediate replay are not the current blocker.

The runtime verifier did not apply its new sanitized failure-detail helper to
the generic document-workspace assertion. The retained log therefore exposes
only HTTP `500`, not the bounded server exception type/message needed to
distinguish lock-event insertion, controlled-document projection save, audit
append or response reconstruction. Guessing among those transaction steps,
or rerunning the Gate without a diagnosis, would violate the fail-closed
evidence rule.

The one authorized dispatch is exhausted and P5-01's necessary controlled
runtime Gate still fails. A further code repair or dispatch requires one new
explicitly bounded authorization for one diagnostic-only dispatch and one
final unchanged Gate after the proven root is fixed. Exact evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-blocker.md`.

The user supplied that exact authorization on 2026-07-31. The execution-limit
blocker is resolved; the fixed controlled-Site Gate is not. The active bounded
round permits only the diagnostic checkpoint, one diagnostic-only dispatch,
repair of the proven root, affected checks/normal CI and one final unchanged
Gate. Local diagnostic tests pass; normal CI and both controlled executions
remain pending.

`P5-01-CONTROLLED-RUNTIME-DATETIME-PERSISTENCE-REPAIR-LIMIT`

The single user-authorized extra repair round passed normal CI and proved the
disposable canonical-email owner correction on the real controlled Site.
Manual run `30570343315` advanced through Project, Document Policy root and
draft creation, then Document Policy publication returned HTTP `500` at the
first P5 Frappe `Datetime` write. The code-backed root is the use of canonical
ISO `T`/`Z` timestamp strings in Frappe database fields whose fixed storage
format is space-separated and timezone-naive. The same helper affects the
downstream P5 Document datetime fields, so a policy-only workaround is unsafe.

The authorized round was exhausted and the necessary Gate still failed.
Historical evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-datetime-blocker.md`.

The user supplied that exact additional bounded authorization on 2026-07-31
local time. The blocker is resolved only as an execution-limit decision; the
runtime defect remains in repair and no Gate PASS is claimed.

`P5-01-CONTROLLED-RUNTIME-REPAIR-LIMIT`

The five-round limit was a real controller Hard Blocker and remains preserved
in `implementation/evidence/phase-5/p5-01-controlled-runtime-blocker.md`.
The user explicitly authorized exactly one additional bounded repair round on
2026-07-31 local time. The known disposable-owner correction passed local
checks, normal CI and its real controlled-Site path through Project creation.
That historical repair-limit blocker is resolved by the authorization, while
the new downstream Datetime persistence blocker above is active. Evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-extra-repair.md`.

## Active execution hold

None.

## Historical and scoped execution holds

`P5-01_CONTROLLED_RUNTIME_PROJECTION_SUBSTAGE_DIAGNOSTIC_LIMIT`

The cumulative R1 shared Shell/design/i18n Level 3 exit Gate passed on
2026-07-30 at synchronized candidate
`2ced098362ab99a4750a13e7004a441a7f19b698` and CI `#72`; pushed recovery
checkpoint `c980571b27be66e16f2ac57409f0ef72a986e741` passed CI `#73`.
`R1_SHARED_BRIDGE` is released. Complete evidence:
`implementation/evidence/reconciliation/r1-shared-bridge-level-3-validation.md`.

P5-01 remains at its retained backend checkpoint as incomplete and
`IN_PROGRESS`; this does not mark P5-01 `PASS`, activate P5-02 or permit scope
beyond the current Phase 5 anchor. Its bounded
reconciliation/current-shared-boundary audit passed and retained the
implementation without product correction. Complete evidence:
`implementation/evidence/phase-5/p5-01-resume-audit.md`.

R1-06 Stage 1 passed its technical prototype/governance Gate at
`e7f2e3bc7956d5f2192eb1b2b9e5fb3d5dc0c4a2` and CI `#67`. Stage 3 passed at
`0b3a7b28bb447edbc165daa95a3e9963f255d832` and CI `#70`: the complete
repository/non-visual lanes and the exact `24/24` fixed-Linux visual lane
passed. Actual Product Owner approval is still required before the dependent
Stage 2 public reset/undo command may begin. That approval remains pending and
is a scoped `UX-030` entry gate, not an overall Hard Blocker. No technical
fixture, screenshot, Codex review or automated test may sign the approval.

R1-04's `UX-028` publisher authority remains a scoped Class-B hold, not a
global blocker. The immutable published-view root/revision, hash, lineage and
rollback-as-new-revision foundation passed, but no live publish/rollback route
or actor mapping exists until the exact “administrator” and “Project lead”
authority policy is approved. Personal preferences, R1-05 and other
independent bridge work continue without inferring that policy.

The append-only `FR-UX-043` trace correction is not a blocker and does not
change any historical Gate. `DR-REC-005` resolved its source boundary to the
existing local iX/company icon adapter. R1-05 implemented and verified only
bounded icon-first secondary actions; GitHub branding, direct vendor imports,
unapproved Primer/Octicons dependencies and icon-only high-risk/ambiguous
primary actions remain prohibited.

## Current P5-01 scope

Phase 4 and P4-05 passed their complete triggered Level 3 Full Release Gate.
`P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
EBOM` is `PASS`. `P5-01 — Document and design revision` remains incomplete
and is resumed at its retained checkpoint under
`implementation/phase-5-requirement-anchor.md`,
`implementation/ACTIVE_EXECUTION_GOAL.md`, and
`implementation/NEXT_ACTION.md`.

The retained checkpoint at `930b5a2` contains the bounded Controlled
Document/Document Revision/private File Revision backend slice, Project-scoped
confidentiality/download audit, locks, capability-truth preview/download
fallback, and the connector-unavailable seam. The resume audit is now `PASS`,
and the frontend/browser/static-runtime slice is recorded at
`implementation/evidence/phase-5/p5-01-frontend-runtime-checkpoint.md`.
The final controlled-Site command could not start because this host has no
Docker CLI/daemon/Compose and no fixed repository Bench. It failed before
migration or fixture writes. This remains a scoped local environment gap, not
a global Hard Blocker. A manual-only CI job now provides the same pinned,
guarded, fixed disposable Site on a fresh ephemeral runner without touching
retained local volumes or any production endpoint. P5-01 remains
`IN_PROGRESS` and P5-02 inactive until its real
two-migration/fresh/replay/route-recovery result passes. P5-01 must not invent
production document numbering, classification, retention, scanner/viewer,
sharing, revision or CAD/PDM rules;
review/release/baseline/EBOM/formal publish remain P5-02 through P5-05.
Production ERPNext/CAD/PDM access and external file retrieval remain
prohibited or fail closed.

Manual dispatch `30562284484` failed before Bench/Site/Compose/database work
because npm 11 rejected Yarn's package preinstall script. This is a bounded
CI setup defect, not an external or global Hard Blocker. The repair removes
the unnecessary global install and requires the already present runner Yarn,
the installed Bench and uv to equal all exact repository pins before
initialization.

Manual dispatch `30563106063` then installed both exact Python packages and
confirmed exact Yarn, but a silent CLI presentation-string comparison
returned nonzero before initialization. This remains a bounded CI setup
defect, not a Hard Blocker or runtime result. The second repair uses exact
installed distribution metadata for Bench/uv and retains exact Yarn
verification before any stateful command.

Manual dispatch `30564025523` then passed exact tool/Bench setup, Docker and
the live database identity guard and created only the fresh disposable Site.
It failed before NPI app installation because pinned Bench emitted
`sites/apps.txt` without a terminal newline, causing the first app append to
form `frappenpi_core`. Cleanup removed the runner-local containers, volumes
and network. This is a bounded bootstrap defect, not a Hard Blocker or
document runtime result; the repair only restores the missing line boundary
and rejects a missing app registry.

The line-boundary repair passed normal CI run `30564533440`. Manual dispatch
`30565065165` then passed the exact setup, installed both apps on the fresh
guarded Site and completed both migrations. The document verifier failed
closed at its first schema fixture because that fixture still named obsolete
`response_payload` metadata instead of the existing sealed
`response_snapshot` and `response_sealed` contract. Cleanup removed the
runner-local containers, volumes and network. This is a bounded verifier
inventory defect, not a Hard Blocker or controlled runtime PASS.

R1-02 used only the five supplied LaunchFlow SVGs in their governed contexts
and passed its exact-scope asset guard. The subsequently supplied `Core.png`
and approved `JCE Core` display name resolve DR-REC-006 but remain allocated to
FR-BR-002/Phase 8/M7-09; they must not be activated by the remaining R1 tasks
or P5-01, or replaced by the Company LOGO, a reconstructed mark or an external
search.

DR-REC-001..010 in
`implementation/V1_2_RECONCILIATION_DECISIONS.md` pause only their named
dependent behavior. Exact Tooling lifecycle commands, production spreadsheet
semantics/destructive rollback, controlled form signature/copy rules and the
Released Trial Summary event remain unapproved.

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
- R1-04 passed its triggered Level 3 grid-personalization/schema Gate on
  2026-07-27. The final evidence includes 727 Python tests, 549 frontend tests,
  two additive/idempotent migrations, the complete controlled Frappe runtime,
  251 non-visual browser cases, a clean 207-case exact visual matrix, a fresh
  13-case task run, complete trilingual coverage and independent code,
  security, UX, accessibility and visual review. Only the explicit UX-028
  publisher-authority decision remains held; R1-05 is active.
- R1-05 Stage 1 passed its triggered Level 3 public preference/shared-UI
  checkpoint on 2026-07-27 from starting boundary
  `88fca2bd898ca08432c5a5f5eec9f25dc963fc14`. Its final evidence records a
  terminal canonical full Gate at 747 Python tests, 577 frontend unit tests
  and 2,671 complete direct trilingual sources, plus 256 non-visual browser
  cases, a clean 210-case exact visual matrix, all 18 controlled routes
  disabled/recovered, zero residual inspector `DefaultValue` rows and
  independent audits with zero findings. This closes only `FR-UX-040`; R1-05
  Stage 2 was activated without an active Hard Blocker.
- R1-05 Stage 2 passed its bounded Level 2 field/attachment truth Gate on
  2026-07-27 from starting boundary
  `749665e5428208f0453832b7f394eddcb6deebca`. Its final evidence records 614
  frontend unit tests, 2,735 complete direct trilingual sources, focused
  browser `12/12`, affected page `20/20`, Gate visual `23/23`, Trial visual
  `24/24`, zero dependency vulnerabilities and an independent post-repair
  PASS. This closes only `FR-UX-041`; Stage 3 is the sole next task and there
  is no active Hard Blocker.
