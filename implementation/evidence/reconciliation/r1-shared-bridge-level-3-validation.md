# R1 Shared Bridge Validation — Cumulative Level 3 Exit Gate

Date: 2026-07-30
Branch: `codex/npi-v1.2-implementation`
Starting synchronized product checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`
Final synchronized Gate candidate:
`2ced098362ab99a4750a13e7004a441a7f19b698`
Result:
`PASS — LEVEL 3 R1 SHARED SHELL/DESIGN/I18N EXIT GATE`

## Gate scope and decision

This Gate closes the inserted R1 reconciliation/shared-UX bridge. It reviews
the cumulative R1-01 through R1-06 delivery and every current executable
requirement boundary before releasing the preserved P5-01 checkpoint.

The cumulative branch delta contains `27` commits and `464` changed files:
`43,188` insertions and `1,361` deletions. The large file count includes the
accepted trilingual visual matrices and exact supplied brand assets. It does
not contain a production deployment, production ERPNext connection or
cross-database operation.

The `release-gate` Skill review found no blocker. The scoped external decisions
below remain truthful and do not invalidate the completed technical bridge:

- `UX-028` publisher authority remains held at its verified immutable
  published-view foundation;
- R1-06 Stage 2 remains held until actual Product Owner approval of the
  unchanged prototype revision;
- `FR-UX-042` / conditional R1-07 remains unactivated because
  `DR-REC-001 = PENDING_PRODUCT_OWNER`; and
- Phase 3 business UAT remains externally unsigned.

None is silently relabelled complete. Each blocks only its named dependent
behavior.

## Task and requirement acceptance

| Task | Terminal task Gate | Current requirement truth |
|---|---|---|
| R1-01 | `PASS — LEVEL 2 DOCUMENTATION/TRACE/TOOLING TASK GATE` | Reconciled Pack/DOCX/Addendum inventory, mappings and passive XLSX safety tooling retained |
| R1-02 | `PASS — LEVEL 2 SHARED-SHELL/I18N TASK GATE` | `FR-BR-001 = TECHNICAL_VERIFIED` |
| R1-03 | `PASS — LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE` | `FR-UX-039`, `UX-011` verified; `UX-018` verified foundation |
| R1-04 | `PASS — LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE` | `FR-UX-038` verified; `UX-007/027/035` verified foundations at that checkpoint; `UX-028` authority held |
| R1-05 Stage 1 | `PASS — LEVEL 3 PUBLIC PREFERENCE/SHARED UI CHECKPOINT` | `FR-UX-040 = TECHNICAL_VERIFIED` |
| R1-05 Stages 2–3 | two bounded Level 2 Task Gates | `FR-UX-041`, `FR-UX-043 = TECHNICAL_VERIFIED` |
| R1-06 | `PASS — LEVEL 2 TASK GATE; STAGE 2 PRODUCT APPROVAL HOLD RETAINED` | `UX-026/030` prototype/governance verified with exact approval hold; `UX-035/036` verified for the current P0 registry |

The current exact statuses are:

```text
FR-BR-001  TECHNICAL_VERIFIED
FR-UX-039  TECHNICAL_VERIFIED
UX-011     TECHNICAL_VERIFIED
UX-018     TECHNICAL_VERIFIED_FOUNDATION
FR-UX-038  TECHNICAL_VERIFIED
UX-007     TECHNICAL_VERIFIED_FOUNDATION
UX-027     TECHNICAL_VERIFIED_FOUNDATION
UX-028     TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD
UX-035     TECHNICAL_VERIFIED_CURRENT_P0_SCOPE
FR-UX-040  TECHNICAL_VERIFIED
FR-UX-041  TECHNICAL_VERIFIED
FR-UX-043  TECHNICAL_VERIFIED
UX-026     PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD
UX-030     TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD
UX-036     TECHNICAL_VERIFIED_CURRENT_P0_SCOPE
FR-UX-042  DECISION_REQUIRED_DR_REC_001
```

## Cumulative changed-files → affected-tests audit

| Boundary | Gate coverage |
|---|---|
| Reconciliation, trace, supplied brand package and passive XLSX inspection | R1-01/02 exact package/hash/mapping tests; current standalone reconciliation and generated-artifact verification |
| Shared Shell preference/session command and quick-create | R1-03 public-contract Level 3 API, permission, runtime, browser, trilingual and visual evidence |
| DenseGrid, fixed personal/published view contracts and three additive DocTypes | R1-04 schema Level 3 migrations, controlled runtime, API/permission, browser and complete visual evidence |
| Fixed actor-bound inspector preference and shared pane behavior | R1-05 Stage 1 Level 3 runtime, route-disable/recovery, CSRF/IDOR, unit, browser and 210-case visual evidence |
| Field/attachment truth and icon-action policy | R1-05 Stage 2 Gate/Trial/focused visual and behavior evidence; Stage 3 policy/adapter units and six exact affected Linux comparisons |
| Controlled undo review prototype | R1-06 Stage 1 no-mutation transport, complete state, approval-manifest, trilingual accessibility and browser evidence |
| Current P0 1440 governance and CI/security infrastructure | strict 18-case/file verifier, original-resolution review, fixed Linux 24-case lane, repository verifier and both secret scans |
| Current Task Gate/controller evidence | fresh CI #72 over the exact synchronized candidate plus trace/controller consistency review |

## Fresh canonical repository evidence

GitHub Actions CI `#72`, run `30546528862`, completed `success` for head SHA
`2ced098362ab99a4750a13e7004a441a7f19b698`.

Repository job `90884045344` passed:

- Node `24.18.0`, npm `11.16.0`, Python `3.11.15`;
- clean `npm ci --strict-allow-scripts`, `380` packages audited and
  `0` vulnerabilities;
- development-container/toolchain, generated-source, formatting, static,
  type, style, industrial-UI, boundary, prohibited-pattern and reconciliation
  checks;
- complete Python lane: `763/763` PASS;
- complete frontend unit lane: `634/634` across `30/30` files;
- frontend coverage: statements `85.46%`, branches `83.63%`, functions
  `89.01%`, lines `87.53%`;
- i18n audit: `2,782` literal English sources with `100%` direct `zh` and
  `zh-TW` coverage;
- production build and exact supplied-brand/display guards;
- complete and production-only npm audits: `0` vulnerabilities;
- complete non-visual browser matrix: `279/279` PASS in `4.3m`;
- action secret scan: `22` commits / `6.32 MB`, no leaks; and
- complete branch secret scan: `58` commits / `11.89 MB`, no leaks.

The three Gitleaks exclusions remain limited to the exact previously reviewed
synthetic fingerprints and are guarded by the repository verifier. No new
finding or broad path/rule exclusion exists.

## API, permission, runtime and migration evidence

R1-03 and R1-04 each passed their triggered public-contract/schema Level 3
Gate. R1-05 Stage 1 is the last R1 change to production backend behavior. Its
complete controlled `make frappe-runtime-verify` evidence passed:

- guest denial and internal/external actor separation;
- exact authenticated-actor and tenant binding;
- CSRF and closed input/schema/type/bound enforcement;
- corrupt stored-state fail-closed recovery without read-side repair;
- confirmed persistence across a fresh session;
- no optimistic success after storage, confirmation or transaction failure;
- all `18` controlled routes in disabled and recovered states; and
- disposable actor cleanup with `0` residual inspector preference rows.

The diff from that Level 3 checkpoint
`749665e5428208f0453832b7f394eddcb6deebca` to the final candidate changes
only:

```text
apps/npi_core/npi_core/translations/zh.csv
apps/npi_core/npi_core/translations/zh-TW.csv
```

within `apps/npi_core`. It changes no backend Python, BFF, OpenAPI/contract,
DocType, patch, migration, runtime verifier, dependency manifest or lockfile.
Therefore the controlled runtime, API/schema agreement, permission and
migration results remain directly reusable. Fresh CI #72 still executes every
current Python contract, domain, repository, permission, migration-metadata
and verifier test.

R1-04's two additive/idempotent migrations and complete controlled runtime
passed after its final code. R1-05 Stage 1 required no database migration.
R1-05 Stage 2/3 and R1-06 introduce no production backend schema or retained
business data. No destructive migration, backfill, production data operation
or migration waiver exists.

## Complete browser, localization and visual evidence

The fresh `279/279` non-visual matrix covers all current deterministic states,
current-actor transports, error/conflict/retry/final truth, keyboard/focus,
axe WCAG A/AA, engineering layout, language purity, URL locale persistence and
tablet/phone flows.

The current `@visual` inventory lists exactly `231` tests in `11` files. Its
complete zero-tolerance evidence is cumulative and source-mapped:

1. R1-05 Stage 1 accepted a clean independent `210/210` complete matrix after
   the public shared-pane change.
2. R1-05 Stage 2 then reran the affected Gate `23/23` and Trial `24/24`
   matrices, reviewed and replaced the nineteen existing Trial images affected
   by the new field/attachment truth, and added three focused images.
3. R1-05 Stage 3 reran the six pane/attachment cases after icon-action adoption
   in the fixed Linux renderer.
4. R1-06 Stage 1 reviewed all three prototype languages at original
   1440×900 resolution; the review-only route is not part of the production
   visual registry.
5. R1-06 Stage 3 added the exact eighteen current-P0 1440×900 cases and CI
   #72 reran them together with the six retained R1-05 cases: `24/24` PASS in
   `31.3s`.

Thus the current inventory is the accepted 210-case set, with every
source-affected historical case replaced by its later zero-diff evidence,
plus the three new attachment and eighteen new P0 cases:
`210 + 3 + 18 = 231`.

The earlier R1-05 diagnostic fixed-renderer run that reported unrelated
historical package/font drift remains a diagnostic failure, not PASS evidence.
Those unrelated accepted baselines were not bulk rewritten. This follows the
repository's changed-files → affected-tests strategy and the explicit R1-06
prohibition on normalizing renderer-only drift. Every product source change
after the 210-case Gate is covered by a later exact affected comparison and
original-resolution review.

CI #72 visual job `90884045367` passed in:

`mcr.microsoft.com/devcontainers/python:1-3.11-bookworm@sha256:b726eb94f42fcddb10056835f2c474c9f9e12e717ba2b2d2f9a8b1d78feeb68b`

Artifact:

- `r1-06-linux-visual-evidence`, ID `8760986155`, size `3,725,947` bytes,
  digest
  `sha256:fd58861f26629f35dbe1c4914922884ab3134711102ba9ad5114699d5fadd750`,
  expires 2026-08-29.

The final original-resolution reviews report no single-primary, radius,
color-wall, gradient, glass, shadow, density, clipping, mixed-language or
non-color-only status blocker. Literal English remains the only source
language; generated catalogs reuse the Frappe-compatible CSV source and all
three languages pass current purity checks.

## Security, ownership and integration review

- No Frappe/ERPNext core patch, direct cross-database query/write or dual-master
  field was introduced.
- Fixed browser commands derive actor/tenant from the trusted session and
  expose no caller-selected generic preference, publish, export, bulk or undo
  authority.
- Public mutations retain CSRF, permission, optimistic version and
  confirmation truth; uncertain writes reconcile and never display optimistic
  success.
- Field attachments expose no raw private URL, fabricate no scanner/upload
  state and cannot mutate a registered revision.
- Icon-only actions are restricted to familiar, low-risk, context-clear
  secondary actions with translated name/tooltip, keyboard/focus/disabled
  paths and repository-owned icon mapping.
- The undo route is a review-only no-mutation prototype. The unsigned manifest
  blocks the production backend entry point.
- No production ERPNext, JCE Core, CAD/PDM or external integration was
  activated. Integration-fault evidence is not applicable to this shared-UX
  bridge; existing mocks and fail-closed unavailable states remain intact.
- CI #72 used only the repository-scoped read-only GitHub token and retained
  the exact secret-scan artifacts.

Security artifact:

- `gitleaks-results.sarif`, ID `8761142614`, size `6,760` bytes, digest
  `sha256:574b5a225face8b03790291ea97353500196a77d343ba08830bf6781488f189e`,
  expires 2026-10-28.

## Traceability, evidence and independent review

Current trace verification passes:

- `282/282` unique IDs;
- `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`;
- exact original Pack-ID digest and historical checkpoint preservation;
- exact R1 task evidence sets and current status boundaries;
- generated-artifact freshness; and
- no rewritten historical 281-row Gate evidence.

Independent cumulative review result:

- requirements/scope/Decision Requests: `0 blocker / 0 major / 0 minor`;
- domain/API/schema/ownership: `0 blocker / 0 major / 0 minor`;
- permission/security/privacy: `0 blocker / 0 major / 0 minor`;
- migration/rollback/recovery: `0 blocker / 0 major / 0 minor`;
- UX/accessibility/i18n/visual: `0 blocker / 0 major / 0 minor`; and
- evidence/controller/recovery integrity: `0 blocker / 0 major / 0 minor`.

The controller-only follow-up checkpoint corrected the recovery summary before
the final CI run; it changed no product, requirement status or acceptance
criterion. User-owned local-development changes and host-generated Darwin
screenshots/reports remain outside this Gate and were not staged.

## Rollback and recovery

R1 rollback remains task-bound:

- planning/trace and display-brand adapters are reversible without retained
  business data;
- personal preferences retain actor-bound confirmed-state recovery and route
  disable;
- immutable published-view revisions are preserved; rollback creates a new
  successor rather than rewriting history;
- additive R1-04 schema remains forward-compatible and is not destructively
  removed after retained records;
- Stage 2 field/attachment and Stage 3 icon/prototype/visual additions are
  removable presentation/test layers with no production file or undo command;
  and
- production recovery uses the already tested exact route-disable controls and
  a reviewed forward fix, never database reset or history deletion.

P5-01's pre-R1 checkpoint at `930b5a2` remains preserved. Releasing the R1 hold
resumes that task; it does not mark P5-01 complete or activate P5-02.

## Final release decision

`PASS — LEVEL 3 R1 SHARED SHELL/DESIGN/I18N EXIT GATE`

The R1 bridge may be marked `PASS`. Release `R1_SHARED_BRIDGE`, preserve every
scoped external-decision hold, and resume only P5-01 from its retained
checkpoint and current Phase 5 requirement anchor.
