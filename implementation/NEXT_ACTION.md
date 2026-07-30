# Next Action

Status:
`P5-01 FRONTEND/BROWSER/STATIC RUNTIME PASS — CONTROLLED SITE PENDING`

Recovery time: `2026-07-30T17:17:57Z`

Latest complete CI recovery checkpoint:
`5dfb99df923ed112ea4eae2ea1b8019ec723d953`

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
  static runtime checks pass; P5-01 remains `IN_PROGRESS`, not `PASS`.
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

Push and validate the bounded document verifier schema-inventory repair, then
redispatch `.github/workflows/ci.yml` on the development branch. It must keep
the exact tool pins, initialize a fresh runner-local fixed disposable Frappe
Site without touching retained local volumes, append each NPI app as its own
registry line, then run:

`bash scripts/verify-frappe-runtime.sh --document-only`

The terminal result must prove:

1. the exact fixed Site/database/user safety guards;
2. two additive/idempotent migrations and exact nine-DocType metadata;
3. one fresh synthetic policy/Project/document/lock/revision/private file
   round trip with server-observed hash and scanner state;
4. exact CSRF, version, idempotency, replay, audit, Guest and IDOR behavior;
5. route-disable/recovery and second-process replay; and
6. bounded cleanup with no production or external connection.

If runtime repair changes source, rerun its affected checks. Then complete the
Task Diff/domain/permission/security/UX/i18n review and P5-01 Level 2 Task
Gate. P5-02 remains inactive until this passes.

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
