# R1-06 Validation — Task Gate

Date: 2026-07-30
Branch: `codex/npi-v1.2-implementation`
Starting synchronized bridge checkpoint:
`373770f988b4cf7707b41a50e96b7a4861d93c3b`
Latest verified implementation checkpoint:
`0b3a7b28bb447edbc165daa95a3e9963f255d832`
Task: `R1-06 — Controlled undo prototype gate and 1440 visual governance`
Requirements: `UX-026`, `UX-030`, `UX-035`, `UX-036`
Result:
`PASS — LEVEL 2 R1-06 TASK GATE; STAGE 2 PRODUCT APPROVAL HOLD RETAINED`

## Final requirement truth

| Requirement | Result | Boundary |
|---|---|---|
| `UX-026` | `PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD` | Closed My Work personal-grid reset/undo prototype proves consequence, recovery and ineligible-action states; no production command or business bulk undo is claimed |
| `UX-030` | `TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD` | Versioned source-bound review manifest and fail-closed backend-entry verifier pass; actual Product Owner approval remains unsigned |
| `UX-035` | `TECHNICAL_VERIFIED_CURRENT_P0_SCOPE` | Exact six-screen × three-language 1440 density and visible-context/work/properties contract passes |
| `UX-036` | `TECHNICAL_VERIFIED_CURRENT_P0_SCOPE` | Exact fixed-Linux 18-image registry plus retained R1-05 comparisons and bounded CI evidence pass |

R1-06 is complete for every currently executable scope. Stage 2 remains a
truthful scoped hold because its explicit Product Owner entry condition has not
been supplied. A technical Gate cannot sign that external decision.

## Completed stages

### Stage 0 — anchor and plan

The task preserved the reconciled requirement meanings, selected only the
current actor's closed My Work grid reset as a bounded low-risk prototype
candidate, kept business bulk capability false and defined the Product Owner
entry condition before implementation.

### Stage 1 — technical prototype and approval governance

Stage 1 passed at implementation checkpoint
`e7f2e3bc7956d5f2192eb1b2b9e5fb3d5dc0c4a2`, finalized by controller
checkpoint `a681c8cf948158b33a78b40a057145f91daf3cc8`.

- Prototype and accessibility/browser cases: `14/14` PASS.
- Approval-verifier tests: `5/5` PASS.
- Real manifest: `PENDING_PRODUCT_OWNER`.
- Exact backend-entry check: expected fail-closed rejection.
- Complete frontend unit suite: `634/634`.
- Complete non-visual browser matrix: `279/279`.
- Canonical hosted evidence: CI `#67`, run `30542155671`, repository job
  `90869267448`, fixed Linux visual job `90869267397`.

Detailed evidence:
`implementation/evidence/reconciliation/r1-06-stage-1-validation.md`.

### Stage 2 — fixed production reset/undo command

Status: `HELD — PENDING_PRODUCT_OWNER`.

The real manifest contains no Product Owner identifier, timestamp, approval
evidence or production undo duration and keeps
`backendImplementationAuthorized = false`. The exact backend-entry verifier
continues to reject it. No API, DocType, migration, audit record, production
mutation or real-command UI was started.

This is not a failed technical Gate and not a global blocker. It is the
specified fail-closed behavior for the one scope dependent on external product
authority.

### Stage 3 — durable additive 1440 governance

Stage 3 passed at fixed-Linux checkpoint
`0b3a7b28bb447edbc165daa95a3e9963f255d832`.

- Affected Python governance lane: `28/28` PASS.
- Exact governed browser case discovery: `18/18`.
- Canonical fixed-Linux lane: `24/24` PASS
  (`18` R1-06 plus retained `6` R1-05).
- Complete Python lane: `762/762`.
- Complete frontend unit lane: `634/634`.
- Complete non-visual browser matrix: `279/279`.
- Direct three-language i18n coverage: `2,782` sources at `100%`.
- Both npm audits: `0` vulnerabilities.
- Original-resolution visual inspection: all `18/18` Linux images.
- Canonical hosted evidence: CI `#70`, run `30544737387`, repository job
  `90877923233`, fixed Linux visual job `90877923386`.

Detailed evidence:
`implementation/evidence/reconciliation/r1-06-stage-3-validation.md`.

## Task Diff Review

### Changed and verified

- one review-only prototype model and My Work demo consumer;
- literal-English prototype copy with direct `zh` and `zh-TW` translations;
- one source-bound pending approval manifest and fail-closed verifier;
- one exact current-P0 visual registry and eighteen additive Linux baselines;
- fixed-digest CI comparison and bounded artifact governance; and
- exact trace/evidence/controller updates.

### Explicitly unchanged

- public API and OpenAPI contracts;
- Frappe controllers, BFF production routes and DocTypes;
- database schema, migrations, patches and retained business data;
- authentication, authorization, CSRF and permission policy;
- data ownership and ERPNext integration;
- production dependencies, design tokens and theme;
- registered revisions, controlled files and formal baselines; and
- every existing 1366/1920/state/zoom/tablet visual baseline.

No TODO, stub, placeholder, static fake-success path, generic undo service,
business bulk mutation, hidden optimistic production success or fabricated
approval was introduced.

## Requirement → code → test → evidence audit

The Stage 1 and Stage 3 validation files contain the exact changed-file to
affected-test mappings. The current trace retains:

- the R1-04 My Work density foundation for `UX-035`;
- the Phase 3 full visual/state/localization foundation for `UX-036`;
- the R1-06 Stage 1 prototype/governance evidence for `UX-026` and `UX-030`;
  and
- the additive R1-06 Stage 3 registry, CI, verifier, screenshot and review
  evidence for `UX-035` and `UX-036`.

The trace remains `282` unique rows:
`173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.
Historical 281-row and earlier accepted Phase/R1 evidence is not rewritten.

## Domain, permission, security, UX and i18n review

- **Domain:** the prototype cannot invent a business bulk command or recovery
  policy; ineligible actions remain visible and forward-recovery oriented.
- **Permission/security:** no production mutation exists. The candidate is
  fixed to a closed current-actor personal preference boundary; manifest
  drift, malformed fields and fabricated authorization fail closed.
- **UX/accessibility:** prototype states and the six current P0 screens retain
  one primary action, visible consequences/recovery, square geometry, dense
  engineering layout, keyboard/focus behavior and non-color-only meaning.
- **i18n:** English remains the only source language; direct `zh` and `zh-TW`
  catalogs are complete. Automated purity checks and original-resolution
  review pass in all three languages.
- **Visual:** eighteen new source-driven Linux baselines are exact and
  reviewed. Unrelated historical renderer drift was neither accepted nor
  normalized.

## Migration, recovery and rollback

There is no production migration or retained business data in R1-06. The
prototype and pending manifest are independently removable. The visual
governance rollback removes only the exact registry/spec/verifier additions
and eighteen R1-06 screenshots, then restores the prior affected CI command.
Earlier accepted evidence and historical screenshots remain intact.

## Task Gate decision and transition

`PASS — LEVEL 2 R1-06 TASK GATE; STAGE 2 PRODUCT APPROVAL HOLD RETAINED`

The unsigned approval holds only Stage 2 and the full production/backend claim
for `UX-026`/`UX-030`. It does not invalidate the completed technical
prototype or current-P0 visual governance and is not a controller Hard
Blocker.

Next:

1. evaluate `DR-REC-001`;
2. if it remains unapproved, skip conditional R1-07 without marking it
   complete; and
3. run the mandatory cumulative R1 shared Shell/design/i18n Level 3 release
   gate before releasing P5-01.
