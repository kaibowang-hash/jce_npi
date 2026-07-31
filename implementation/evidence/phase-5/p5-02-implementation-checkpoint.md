# P5-02 Implementation Checkpoint

Recorded: `2026-07-31T08:55:00Z`

Status:
`IN PROGRESS — IMPLEMENTATION CANDIDATE; CLEAN CI AND CONTROLLED SITE PENDING`

Requirements:

- `FR-DS-002`;
- `FR-DS-005`; and
- `FR-DS-010`.

## Implemented boundary

- Exact Project-scoped, publish-once release-policy selection.
- Closed submit, reject, resubmit, approve, release, supersede and obsolete
  commands with independent business authority.
- Append-only review cycles, electronic confirmations and lifecycle events.
- Guarded lifecycle projection with exact optimistic versions.
- Actor-bound idempotency and immutable transition responses.
- Fresh private-file identity, byte length, SHA-256, MIME and scanner-owned
  `clean` revalidation before release.
- Released Frappe `File` deletion protection.
- Independent `npi_p5_02_routes_disabled` switch that retains P5-01 routes and
  immutable P5-02 history.
- Closed OpenAPI, BFF, browser data-source and dense Project document
  workspace behavior.
- Direct English, Simplified Chinese and Traditional Chinese coverage.

No production reviewer, quorum, delegation, regulated-signature meaning,
scanner provider, retention rule, watermark, replacement policy or ERPNext
execution authority was inferred.

## Changed-files to affected-tests

| Boundary | Evidence at this checkpoint |
|---|---|
| Domain, metadata, controllers, repository, BFF and OpenAPI | Complete Python test discovery: `833/833 PASS`; focused P5 document modules: `67/67 PASS`; compile and shell syntax checks pass |
| Browser data source and workspace | Frontend unit/coverage suite: `660/660 PASS`; ESLint, Prettier, Stylelint, boundary, industrial UI, type and build checks pass |
| i18n | `3055` literal English sources; direct `zh` and `zh-TW` coverage `100%` |
| Browser command and nonnormal truth | Affected P5 document Playwright: `7/7 PASS`; explicit authenticated confirmation, exact command body and immutable review refresh included |
| Trilingual visual | Local original-resolution review cases: `3/3 PASS`; fixed-Linux baselines remain pending |
| Controlled runtime | Verifier static suite: `21/21 PASS`; real two-migration Site dispatch remains pending |
| Requirement trace | Current V1.2 reconciliation verifier passes; requirement rows remain `IN_PROGRESS` until Level 2 completes |

The local aggregate frontend command reached the production build and stopped
only when the existing untracked
`frontend/public/images/npi-one-project-management-sketch.png` was correctly
rejected by the brand asset guard. That user-owned file is not modified,
staged or included in P5-02. The clean remote CI result is the authoritative
ordinary-CI check.

## Controlled runtime candidate

The unchanged controlled document lane now verifies:

1. two consecutive additive migrations;
2. one explicit internal reviewer with `NPI API User` transport access;
3. exact synthetic release-policy publication;
4. missing CSRF and wrong business-authority rejection;
5. submit plus exact cross-request replay;
6. stale lifecycle conflict;
7. reject, immutable prior cycle, resubmit and a new cycle;
8. exact reviewer approval;
9. physical private-file byte tamper causing
   `DOCUMENT_RELEASE_INTEGRITY_BLOCKED`, followed by exact byte restoration;
10. release, retained hash/history and released file projection;
11. Frappe `File` deletion rejection;
12. independent P5-02 route disable and recovery while P5-01 list/detail stay
    available; and
13. cross-process release replay and cleanup.

## Remaining Task Gate work

- Commit and push the bounded implementation candidate without user-owned
  changes.
- Run complete ordinary CI from a clean checkout.
- Capture and commit exact fixed-Linux P5-02 visual baselines, then rerun the
  unchanged zero-tolerance visual job.
- Run one final P5 controlled-Site workflow on the exact candidate.
- Repair only a uniquely proved product root if a Gate fails.
- After all checks pass, update trace, risk, phase status, next action, last
  run and final P5-02 evidence, then commit and push the Level 2 checkpoint.
