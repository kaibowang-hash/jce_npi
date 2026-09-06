# P7-01 Repository and BFF Checkpoint

Recorded: `2026-08-10T07:28:04Z`

Status:
`PASS — PROJECT-FIRST PLAN/ROUND COMMANDS, ACTOR-BOUND REPLAY AND GOVERNED ACTION LINKS`

Primary requirement: `FR-TR-001`

Exact stable checkpoint:
`256ea97339b31a9a5fa2d4d6dd0eb92983be11eb`

Product and bounded visual commits:

- `bcdc167` — independently default-closed Project-first Trial repository and
  BFF reads/commands, governed action generation, immutable persistence,
  idempotency/audit and direct tests; and
- `256ea97` — promote only the reviewed fixed-Linux catalog-footer actuals
  produced by the added direct translations.

## Delivered boundary

- Activated exactly the P7-01 Project-first workspace/detail reads and
  create-Plan, append-revision, create-Round and generate-actions command
  shapes behind independent `npi_p7_01_routes_disabled` fail-closed control.
- Every read/command authorizes and locks the Project before resolving a Plan,
  Round, Tooling Master, Project member, controlled document or Work Item.
- Create Plan persists one stable Plan identity and immutable initial revision;
  revise appends one exact successor without rewriting history; create Round
  allocates one distinct planned UUID/sequence and retains the exact Plan
  revision/hash.
- Proposed machine/material resources remain explicit intent with booking state
  `unavailable`. No route accepts or returns a reservation-success claim.
- Commands use closed canonical payloads, actor-bound idempotency, exact
  optimistic predecessor/version checks, one transaction, immutable audit and
  sealed response replay. Same-key/different-payload use fails explicitly.
- Action generation validates the complete batch first, creates existing
  governed Domain Work Items through the Project Work policy, advances the
  Project once and persists immutable Trial links. It creates no competing
  task state and no partial-success receipt.
- Bounded workspace/detail projections reconstruct exact latest revisions,
  planned Rounds and Work links while retaining honest unavailable later
  sections and capabilities.
- Authentication, CSRF, strict-field, request-ID, route-disable, permission,
  IDOR, conflict, replay, rollback and stable Problem Details behavior are
  covered directly.

## Deliberately unavailable

- There is no live Trial SPA composition or controlled-Site Trial runtime at
  this checkpoint.
- There is no prepare/start command, physical input lock, actual parameter,
  Sample Batch, evidence, defect, conclusion, approval, readiness, Gate or
  formal quality mutation.
- There is no availability/calendar reader, reservation authority, production
  ERPNext endpoint, credential, network call, Outbox event or adapter. Missing
  production ERPNext access does not weaken the Mock/Sandbox-ready boundary.
- The route switch remains independently default closed; disabling it does not
  disable Project, Tooling, controlled-print or other domain routes.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| Trial BFF/request security/errors | exact route registration, independent fail-closed switch, authentication, method, CSRF, strict fields, request IDs and stable Problem Details |
| `trial_api.py` | Project-first identity parsing, conservative command authority, closed Plan/revision/Round/action payloads and response envelopes |
| Trial repository | containment, current-member and Tooling/document checks, version/label conflicts, transaction, immutable audit, actor-bound replay, sealed response and reconstruction |
| Project Work repository helper | bounded all-or-nothing action generation under the published policy with one Project advance and immutable Trial links |
| OpenAPI/data ownership/metadata | exact paths and closed schemas, server-owned labels/booking state, ownership and cumulative receipt operation/target values |
| translations/generated catalog | `5,870` literal English sources at complete direct `zh`/`zh-TW` coverage |
| fixed-Linux visual baselines | eighteen reviewed catalog-footer actuals promoted byte-for-byte; complete final `94/94` matrix |

## Local and exact-SHA CI evidence

The checkpoint Level 2 local gate passed:

- complete backend discovery: `1,481/1,481`;
- focused Trial/API/repository/contract/metadata suites, Python compilation,
  YAML parse and V1.2 reconciliation: PASS;
- frontend generation, typecheck, code/style/boundary/UI/i18n lint, Vite build
  and `809/809` unit tests in `52` files: PASS;
- i18n audit: `5,870` English literal sources with 100% direct `zh`/`zh-TW`
  coverage;
- P0 governance: `18/18`; and
- prototype approval checks and `git diff --check`: PASS.

Primary run `31364345007` passed repository job `93379429687`; its visual job
retained eighteen expected catalog-fingerprint candidates. Pixel audit found
zero changed business pixels above `y=860`. Ordinary English/Chinese changes
were confined to the footer digest; one Trial image retained only known
lower-edge one-value antialiasing pixels outside business UI. Commit `256ea97`
copied exactly the reviewed actuals to their fixed-Linux targets.

Final ordinary CI run `31365127408`, attempt 2, passes exact stable checkpoint
`256ea97`:

- repository job `93383559559`: PASS, including full verification, E2E,
  current-tree Gitleaks and complete pull-request history scan;
- visual job `93383558605`: PASS at `94/94`; and
- controlled runtime job `93383558937`: correctly skipped.

The first visual attempt failed only one existing R1-05 150% font-rendering
case after all eighteen P0 cases had passed. Its `1,048` differing pixels were
confined to `x=13..384, y=245..318` in an unchanged business-data text row;
the identical SHA passed the complete `94/94` matrix on the failed-job rerun.
No baseline, component, matrix, assertion, tolerance or PASS rule was changed
for that unrelated rendering flake.

## Review, rollback and next checkpoint

Task Diff Review confirms Project-first authorization, exact immutable
revision/Round identity, actor-bound transactional commands and no resource,
quality, Gate or external authority. Once rows exist, rollback disables the
independent P7-01 routes and live composition through reviewed forward repair;
it never deletes Plan revisions, Rounds, Work links, receipts or audits.

Checkpoint 2 is PASS. P7-01 remains in progress. Autopilot next implements
only checkpoint 3: the strict live data source and dense trilingual Trial
planning workspace with Plan/Round/action projection, honest resource-booking
and later-section unavailability, full state/accessibility behavior and
affected visual evidence. Controlled-Site proof remains checkpoint 4.
