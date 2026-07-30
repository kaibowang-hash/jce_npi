# Next Action

Status:
`BLOCKED_EXTERNAL — P5-01 CHECKOUT HTTP 500; AUTHORIZED ROUND EXHAUSTED`

Recovery time: `2026-07-30T19:18:48Z`

Latest complete CI recovery checkpoint:
`7aa14edbdd2e484784cee6a8ec52adef4f6bf328`

Retained P5-01 checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- The cumulative R1 shared Shell/design/i18n Level 3 exit Gate is `PASS`.
- `R1_SHARED_BRIDGE` is released.
- R1-01 through R1-06 are complete for their executable scope.
- `DR-REC-001` remains pending; conditional R1-07 was not activated or marked
  complete.
- Phase 5 remains `IN_PROGRESS`.
- P5-00 remains `PASS`.
- P5-01 resume audit, frontend, direct trilingual, unit, browser, visual and
  static runtime checks pass; P5-01 remains incomplete and is
  `BLOCKED_EXTERNAL` at the controlled-Site checkout boundary, not `PASS`.
- The frontend/runtime/security checkpoint passed complete CI `#79`, run
  `30560612349`, including `285/285` non-visual browser cases, fixed-Linux
  visuals and both current-tree and complete PR-history secret scans.
- The manual-lane checkpoint passed the same complete normal CI as `#80`, run
  `30561689283`.
- Manual run `30562284484` failed before Bench/Site/Compose/database work
  because strict npm policy rejected an unnecessary Yarn global install; no
  controlled runtime result is claimed from that run.
- The bounded Yarn repair passed complete normal CI `#81`, run
  `30562550109`.
- Manual run `30563106063` installed both exact Python packages and confirmed
  exact Yarn, then failed a silent CLI version-rendering comparison before
  initialization; no controlled runtime result is claimed from that run.
- The distribution-metadata repair passed complete normal CI `#82`, run
  `30563401058`.
- Manual run `30564025523` passed tool/Bench/database guards and created only
  the fresh Site, then failed before NPI app installation because the pinned
  Bench registry lacked a terminal newline. Its containers, volumes and
  network were removed; no controlled document runtime result is claimed.
- The app-registry repair passed normal run `30564533440`, including the
  complete repository, browser, visual and both secret lanes.
- Manual run `30565065165` installed both NPI apps on the fresh guarded Site
  and completed both migrations, then the verifier failed closed because its
  schema fixture required obsolete `response_payload` metadata instead of the
  existing sealed `response_snapshot` and `response_sealed` pair. Cleanup
  removed the runner-local containers, volumes and network; no controlled
  document runtime result is claimed.
- The schema-inventory repair passed normal run `30565607707`, including the
  complete repository, `285/285` browser, fixed-Linux visual and both secret
  lanes.
- Manual run `30566120000` passed both migrations and the corrected schema
  fixture, then Project creation returned HTTP `422` because the synthetic
  fixture supplied non-email owner `Administrator`. Cleanup removed the
  runner-local containers, volumes and network.
- The fifth failed round remains preserved as a truthful historical Hard
  Blocker.
- The user-authorized extra repair is complete at `a2d98e2`. Affected
  runtime/verifier tests pass `91/91`, complete tracked Python tests pass
  `774/774`, and normal CI run `30569830739` passed on the exact SHA.
- Manual run `30570343315` proved the owner lifecycle and advanced through
  Project, Document Policy root and draft creation. Policy publication then
  returned HTTP `500` at the first P5 Frappe `Datetime` persistence boundary.
  Cleanup removed the ephemeral runtime resources.
- The code-backed shared root is canonical ISO `T`/`Z` API text being assigned
  directly to Frappe database `Datetime` fields. The bounded solution must
  separate canonical timestamp truth from Frappe storage formatting across
  all affected P5 Document controllers and add sanitized failure diagnostics.
- The user supplied the exact additional bounded authorization on 2026-07-31
  local time. It permits only the shared Frappe Datetime persistence repair,
  sanitized diagnostics, affected checks, normal CI and one unchanged
  controlled-Site dispatch.
- Datetime repair candidate `7aa14ed` passed normal CI `#98`, run
  `30573186630`. Its one authorized controlled dispatch `#99`, run
  `30573778175`, passed the formerly failing policy publication, controlled
  document creation and immediate idempotency replay, then returned HTTP
  `500` on the first document `:check-out`.
- The verifier's sanitized detail helper covered policy operations but not
  the generic document-workspace assertion. The retained evidence therefore
  cannot uniquely attribute the checkout failure inside the four-step
  persistence/response boundary. The one authorized dispatch is exhausted.
- P5-02 through P5-05 and Phase 6 remain inactive.
- The current trace contains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Use:

- `implementation/phase-5-requirement-anchor.md`;
- `implementation/evidence/phase-5/p5-01-plan.md`;
- `implementation/evidence/phase-5/p5-01-reconciliation-hold.md`;
- `implementation/evidence/phase-5/p5-01-resume-audit.md`;
- the indexed trace rows and current contracts; and
- `frappe-safe-change`, `npi-domain-guard`, `industrial-ux` and
  `frappe-i18n` Skills.

## First incomplete action

The frontend/runtime-ready checkpoint is recorded at
`implementation/evidence/phase-5/p5-01-frontend-runtime-checkpoint.md`.

The shared-Datetime repair and its one authorized dispatch are complete. Do
not change product code or dispatch the Gate again under the exhausted
authorization.

The single unblock action is explicit user authorization for one further
bounded repair round limited to:

1. extending the already reviewed sanitized exception type/message helper to
   the document-workspace command boundary;
2. one diagnostic-only controlled-Site dispatch to identify the exact
   checkout transaction root;
3. fixing only that proven root, with affected tests and complete normal CI;
   and
4. one final unchanged
   `bash scripts/verify-frappe-runtime.sh --document-only` dispatch.

The terminal result must prove:

1. the exact fixed Site/database/user safety guards;
2. two additive/idempotent migrations and exact nine-DocType metadata;
3. one fresh synthetic policy/Project/document/lock/revision/private file
   round trip with server-observed hash and scanner state;
4. exact CSRF, version, idempotency, replay, audit, Guest and IDOR behavior;
5. route-disable/recovery and second-process replay; and
6. bounded cleanup with no production or external connection.

Only a real PASS may resume the Task Diff/domain/permission/security/UX/i18n
review and P5-01 Level 2 Task Gate. P5-02 remains inactive. Evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-blocker.md`.

## Retained passing checkpoint evidence

- P5-01 focused domain/repository/API/metadata/controller/contract:
  `63/63`.
- Binary response/failure matrix: `15/15`.
- Affected foundation/BFF/API regressions: `107/107`.
- Nine DocType JSON and OpenAPI/data-ownership/controller metadata checks.
- Direct catalogs at the checkpoint and generated-catalog freshness.
- Exact 55-file retained inventory and no production policy, external
  identity, scanner/viewer, CAD/PDM or ERPNext activation.
- Frontend/runtime-ready candidate:
  `658/658` complete frontend unit, `6/6` P5 browser, `3/3` exact trilingual
  visual, `2,860` complete direct sources, production build, `68/68` P5
  Python/static verifier and `85/85` shared runtime regressions.

These results were impact-reviewed against current shared code and retained in
`implementation/evidence/phase-5/p5-01-resume-audit.md`. Do not repeat
unrelated complete R1 Gates.

## Prohibited or held behavior

- Do not restart the already retained pure domain/backend slice.
- Do not install production document types, prefixes, numbering or revision
  policy.
- Do not infer release/review authority from Project ownership, RACI,
  `System Manager` or the transport role.
- Do not expose a raw private URL or fabricate upload, scanner, preview,
  connector or external-sharing success.
- Do not weaken tenant/Project/object authorization, CSRF, idempotency,
  optimistic version, audit or immutable revision truth.
- Do not start P5-02 review/release, P5-03 baseline, P5-04 EBOM or P5-05
  publish request behavior.
- Do not connect production ERPNext/JCE/CAD/PDM or sign external UAT.

## Transition

Complete only the controlled-Site proof and final affected reviews. Finish the
P5-01 Level 2 Task Gate before activating P5-02.
