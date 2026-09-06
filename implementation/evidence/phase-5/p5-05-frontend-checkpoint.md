# P5-05 Publish-Request Workspace Checkpoint

Recorded: `2026-08-06T13:14:50Z`

Status:
`PASS — FRONTEND CHECKPOINT AND COMPLETE ORDINARY CI`

Requirement: `FR-DS-013`

Starting checkpoint:
`f3018eb94a54fa63cd87e87fb501835510765145`

Product checkpoint:
`358db2045e944d9d3bebb738245938977801028c`

Visual-governance repair:
`82d23595479c023d2dd625ff3d005e9b49c9a831`

Accepted Linux-baseline checkpoint:
`4f4baf97fc0db787decd6c5a5bdcca1c90c2da79`

## Delivered boundary

- Added a closed Project/EBOM-scoped publish-request data source and view
  boundary. List, detail and create responses are validated exactly before
  product state is exposed; an absent live adapter fails closed.
- Integrated a dense publish-request work area into the existing Project EBOM
  workspace. It exposes exact released-revision, release-event, policy,
  immutable-input, request, node, mapping and result truth.
- A publish request can be prepared only from the exact selected released
  revision. The action remains Mock-only, creates no dispatch work, contacts
  no target, returns no formal Item/MBOM identifiers and never reports ERP
  success.
- The create transport requires CSRF, actor-bound idempotency, private
  no-store semantics, exact request/trace identity and immutable replay
  consistency. Command inputs are explicitly allowlisted rather than copied
  from UI state.
- Loading, empty, unauthorized, read-only, validation, conflict, partial,
  manual-intervention, target-unavailable and recovery paths remain visible.
  Retry retains the original actor-bound idempotency identity.
- The selected work context has one visual primary action: draft/unreleased
  EBOM work retains `Create EBOM revision`; an exact released revision makes
  `Prepare publish request` the sole primary action.
- Node-result evidence is keyboard reachable and scrollable, status truth is
  textual and non-color-only, and the three accepted visual cases preserve
  the square, dense, restrained industrial workspace.
- All new user-visible text is literal English source copy with direct
  Simplified and Traditional Chinese translations. The generated catalog has
  `3,759` directly covered sources.

## Requirement -> code -> test -> evidence

| Requirement | Code boundary | Direct proof |
|---|---|---|
| `FR-DS-013` closed Project/EBOM publish-request view | `publish-request-data-source.ts`; `project-ebom-publish-workspace.tsx`; EBOM workspace integration | exact response validators, exact paths, absent-adapter failure and component/unit tests |
| `FR-DS-013` guarded Mock create without fake ERP truth | create form, actor-bound retry and live data source | three-language browser create, request/detail/node truth, unavailable/manual-intervention fixtures and no-target assertions |
| `FR-DS-013` industrial accessible evidence | workspace styles, node-result region and conditional single-primary rule | accessibility assertions, `expectSinglePrimaryAction`, fixed-Linux visual matrix and original-resolution review |

## Changed-files -> affected tests

| Changed boundary | Verification | Result |
|---|---|---|
| closed data-source/runtime adapter | focused data-source and app tests | PASS |
| publish-request workspace and EBOM integration | focused component/unit group | final affected groups `23/23` and `15/15` PASS |
| complete frontend unit regression | complete Vitest suite | `704/704` PASS |
| create, languages and failure states | P5-05 non-visual Playwright | `5/5` PASS |
| backend/API/runtime compatibility | affected P5-04/P5-05 Python group | `47/47` PASS |
| type/lint/build/governance | TypeScript, ESLint/Prettier, style/boundary/UI audits and Vite build | PASS in clean CI |
| localization | literal extraction, placeholders, mixed-language and direct catalogs | `3,759`; direct `100%` zh/zh-TW PASS |
| governed visual evidence | complete fixed-Linux matrix after accepted repairs | `65/65` PASS |
| complete ordinary CI | repository, complete E2E, secret lanes and visual | `PASS` at exact SHA `4f4baf9` |

The local aggregate build's brand-asset guard saw only the pre-existing
user-owned untracked file
`frontend/public/images/npi-one-project-management-sketch.png`. The file is
outside the tracked candidate and the clean CI checkout. It was not removed,
modified or staged.

## Exact-SHA CI isolation and bounded visual repairs

Ordinary CI `31100523170` ran on exact product SHA `358db20`:

- repository job `92612694316` passed complete repository verification,
  non-visual E2E, current-tree Gitleaks and complete branch-history scan; and
- visual job `92612694291` failed `21` of the then-governed `62` cases:
  eighteen durable P0 catalog fingerprints and three P5-04 cases whose
  selected draft context had lost its primary action.

Artifact `8967333151`, digest
`sha256:abe4d11ad602205246bd455b8fa1abff5c487a5e66e06f7332a9b9ab3aec5970`,
provided the exact Linux actuals. Original RGB comparison proved for the
eighteen P0 cases:

- all canvases remained `1440x900`;
- changed pixels were confined to the bottom catalog/status strip, with
  bounding boxes beginning at `y=879` or later; and
- the complete product workspace above `y=879` had exactly zero changed
  pixels in all `18/18` images.

Only those eighteen reviewed CI actuals replaced their matching P0 Linux
baselines. The three P5-04 baselines were not accepted. Instead the product
root was repaired by making the publish action primary only for an exact
released selection and restoring `Create EBOM revision` as the draft-context
primary action. A shared assertion now proves one primary action. The existing
visual workflow was also extended additively with the three P5-05 accepted
language/viewport cases; no prior case, threshold or PASS rule was removed or
weakened.

Repair SHA `82d2359` then ran ordinary CI `31103164950`:

- repository job `92621542292` passed completely;
- visual job `92621542173` passed every pre-existing and repaired case
  (`62/65`) and failed only because the three new P5-05 Linux baselines did
  not yet exist; and
- artifact `8968430517`, digest
  `sha256:1d0623181328bcc2ffe9365cecd0ad43171059942cba90e6c5df6bb0e9992f0a`,
  contained exactly the English `1366x768`, Simplified-Chinese `1440x900`
  at 125%, and Traditional-Chinese `1920x1080` at 150% actuals.

All three actuals were reviewed at original resolution. They preserve the
dense split work area, one primary action, textual Mock/no-contact truth,
square controls, responsive inspector behavior and readable three-language
content. Those exact bytes became the initial P5-05 Linux baselines.

Final ordinary CI `31104305011` retained exact SHA `4f4baf9` and passed:

- repository job `92625383049` in `7m49s`, including complete `verify.sh`,
  complete non-visual E2E, current-tree Gitleaks and complete branch-history
  secret scan;
- visual job `92625383029` in `2m29s`, including the complete governed
  fixed-Linux matrix `65/65`; and
- controlled job `92625384089` correctly skipped for the ordinary pull-request
  event.

Passing visual artifact `8968904285`, size `6,208,110` bytes, has digest
`sha256:aa9d45a0f86b16d10c7046df5cc209dce197d2b9bc9a559e289ffd2db42f6da7`.
Gitleaks artifact `8969071975`, size `6,760` bytes, has digest
`sha256:917aa021fb28360b38145895001c0e9f053b48b04b13c0e1b37f2dc3171dafd4`.

No test, threshold, viewport, scale, language, fixture, Requirement, public
API, permission, Schema, ownership, transaction, idempotency, audit or PASS
criterion was weakened to obtain the exact-SHA PASS.

## Security, ownership, rollback, and next action

- The browser never supplies identity, operation or target credentials.
  Authorization remains server-side and precedes protected resolution; create
  requires CSRF, exact optimistic versions and actor-bound idempotency.
- NPI One owns only the request and immutable engineering evidence. ERPNext
  retains formal Item, stock-UOM, MBOM, routing and execution truth. No target
  system is contacted.
- No raw DocType CRUD, generic operation/payload create, exception leakage,
  production dependency, secret, permission widening or fake success was
  introduced.
- Before retained history, revert these product/evidence commits in a
  disposable environment. After history exists, disable only the P5-05 route,
  preserve all request/node/mapping/result/audit/receipt evidence and use a
  reviewed forward fix. Never delete history or contact ERPNext as rollback.

P5-05 checkpoint 3 is closed. The only next checkpoint is the controlled
disposable-Site verifier: extend the existing P5 document/EBOM lane with exact
P5-05 policy, released input, Mock create/read/replay/conflict, no-fake-success,
route-disable/recovery and cleanup proof. It must pass ordinary CI before one
controlled Gate. P5-05 Level 2 and Phase 5 Level 3 remain open until that
unchanged Gate and the complete `release-gate` review pass.
