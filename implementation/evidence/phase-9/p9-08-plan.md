# P9-08 — Controlled Full-Product UAT and Phase 9 Exit Plan

Recorded: `2026-09-03`

Status: `GOVERNANCE — EXACT-SHA ORDINARY CI REQUIRED`

Requirement: `UX-003`, with accepted P9-01 through P9-07 outputs

## Accepted predecessor

P9-07 is accepted at exact SHA
`d911c2bcecb228cee0f4830c868e0d0fdf35d3e2`. Ordinary CI
`33730217862` and diagnostics-off Level 3 `33730710124` pass every required
lane. Controlled runtime job `100571300835` proves the fixed synthetic
backup/restore/forward-fix rehearsal and cleanup with `productionContact=false`.
Artifact `9884231883` has GitHub digest
`sha256:2d4fdb0d1f5293a20d0c4feecf663011712da857f168088a15abe731a25c1ef2`;
its bounded result has checksum
`sha256:9c6b501e20ceeec9abd728f8165b02b05682ebb34e86e4dda010245515bffb93`.
The P9-07 release-gate result is PASS.

## Purpose and truth boundary

This task closes the technical, representative non-production UAT for the two
accepted product paths. It does not run the deferred M9-04 or M9-05 real
pilots, observe production users or measure adoption. The result must be named
`controlled non-production technical UAT`; it must never be reported as a real
pilot, real-project proof or 80-percent real-user usage.

The approved LaunchFlow architecture, object ownership, OpenAPI/event
contracts and accepted P9-01 through P9-07 product are the correct baseline.
The task is evidence-first. It may make no product change unless a fixed
controlled scenario produces a concrete, reproducible incompatibility. Any
such repair must be the smallest local reversible change and must retain the
existing domain, permission, version, idempotency, audit and failure-truth
contracts.

## Fixed UX-003 measure

The denominator is every in-scope, frequent, user-initiated development
activity in the two controlled scenario manifests. A numerator activity must
start from My Work or execute inside the same Project route and one of its
governed Project, Gate, Tooling, Trial, Change, Reporting, Data Exchange or
Integration Operations child workspaces. The ratio is
`qualifying activities / in-scope activities`; it must be at least `0.80` for
each scenario and overall.

Background workers, notifications, administrators, configuration, support,
ERP-owned purchasing/manufacturing/finance execution and production ERP Desk
steps are not LaunchFlow end-user development activities and are excluded from
both numerator and denominator. This exclusion cannot turn a failed or missing
LaunchFlow user activity into a pass. Each included activity must bind a route
or UI entry, expected truthful state, and executable existing or new evidence.

## Controlled scenarios

### AT-01 — Customer-owned mold

Golden flow: Project intake; ownership and inspection; material variance and
customer confirmation; controlled evidence/baseline; Gate review; Tooling
revision and Set truth; T0/T1 planning and execution; Trial quality and review;
Tooling acceptance; ERP Tool Asset request/projection; G6/G7 and operations
visibility.

Fault flow: a major intake variance blocks Trial/acceptance; stale or
unauthorized commands remain rejected; failed, partial, uncertain or
timeout-after-commit ERP execution is shown as unresolved operation truth and
is never displayed as handed off.

### AT-02 — New tooling

Golden flow: Project and customer input; DFM and controlled design baseline;
EBOM; Tooling requirement/specification/budget/supplier; design release;
manufacturing milestones; T0 through Tn comparison; customer approval evidence;
readiness; Item/MBOM/Tool Asset requests and production-handover projections.

Fault flow: a changed design revision cannot silently replace the released
baseline; stale/duplicate publication stays version-locked and idempotent;
ERP purchase/cost remains read-only; failed, partial, uncertain, conflict or
stale integration truth remains visible with trace and recovery action.

## Evidence matrix

The machine-readable manifest must cover these accepted families without
copying their implementations: Project and My Work; roles and permissions;
controlled documents, baselines and EBOM; Gate evidence and exceptions;
Tooling requirements, revisions, Sets, manufacturing, acceptance, import and
export; Trial planning, execution, quality, review, readiness and released
summary; ERP read-only projections, signed Inbox, Item/MBOM/Tool Asset/formal
quality execution, operations/retry/replay/reconciliation views and display
identity; Engineering Change; reporting/collaboration; notifications; data
exchange; security; recovery.

Every manifest activity must provide its scenario, stable activity ID,
Project-context classification, accepted requirement or task anchor, evidence
file and executable test selector. The verifier fails closed on an unknown key,
duplicate ID, absent evidence, missing selector, missing golden/fault class,
ratio below 0.80, production/real-pilot claim, unapproved route class or a
required evidence family with no activity.

No new screenshot is required unless the consolidated browser proof exposes a
new UI state. Existing exact three-language and governed visual matrices remain
the visual and localization evidence; P9-08 must run their full final Level 3
rather than regenerate baselines.

## Final production ERPNext compatibility reconciliation

Phase 9 and release closeout remain blocked until a complete production
ERPNext-to-LaunchFlow compatibility reconciliation is refreshed. This is a
read-only evidence Gate, not a production pilot or modification task. It must:

1. reuse `ERPNEXT_PRODUCTION_FACT_INVENTORY` and the accepted P8-07F facts;
2. use SSH alias `JCE-Core` only under the standing fixed BatchMode,
   strict-host-key, no-TTY/no-forwarding, bounded-output operation allowlist;
3. prefer version, installed-app, tracked-worktree mtime/hash and exact missing
   metadata deltas; never repeat a full read without evidence of drift;
4. compare all ERP-related P8-01 through P8-09 and later Phase 9 dependencies;
5. classify each dependency as still matching, production drift,
   LaunchFlow drift, both drift or unverified, with sanitized provenance,
   checksum, owner, impact and minimal remediation;
6. stop on allowlist, shape, permission, version or sensitive-value drift and
   make no SQL, console, file, database, service, permission, scheduler,
   migration, replay or other production write.

An unresolved or unverified actual ERP dependency blocks Phase 9 PASS,
`IMPLEMENTATION_COMPLETE` and production-ready. A proved conflict creates a
separate minimal decision or adjustment task; it is not silently repaired in
this UAT task.

## Validation and rollout

1. Commit only this governance transition and predecessor evidence, then pass
   exact-SHA ordinary CI.
2. Add the fixed manifest, fail-closed verifier, focused unit tests and the
   smallest consolidated browser proof. Reuse accepted tests; do not duplicate
   feature implementations.
3. Run Level 1 and full P9-08 Level 2, review the task diff and update UX-003
   traceability with the exact technical-UAT wording.
4. Commit and push one implementation checkpoint and require exact-SHA
   ordinary CI PASS.
5. Run the bounded final production read-only reconciliation and commit only
   sanitized evidence. If it proves drift, stop only the affected release
   decision and record the exact gap.
6. Run one final diagnostics-off Level 3 and the release-gate review. Only a
   complete PASS may close P9-08 and Phase 9.

Rollback removes only the new manifest, verifier, consolidated test and P9-08
evidence. It does not roll back accepted P9-01 through P9-07 product history or
change any production system. The read-only reconciliation has no production
state to reverse.
