# R1-04 Plan — Shared dense-grid personalization and governed-view foundation

Date: 2026-07-26
Branch: `codex/npi-v1.2-implementation`
Task: `R1-04 — Shared grid sizing personalization views and export foundation`
Requirements: `FR-UX-038`, `UX-007`, `UX-027`, `UX-028`, `UX-035`
Status: `PASS — LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`
Starting synchronized bridge checkpoint:
`3e0721a1b8be8dbd1b618d78a635b74d28cd0178`

## Scope

- Add one repository-owned dense-grid presentation foundation and use it for
  both the live My Work list and the prototype Worklist without introducing a
  new production dependency.
- Support pointer drag resize, double-click auto-fit of the currently rendered
  page, bounded minimum/maximum widths, individual/all-column reset, column
  visibility, a bounded fixed-start column count, safe internal horizontal
  scrolling and an equivalent keyboard resize/reset path.
- Persist the live My Work layout through one fixed authenticated BFF resource.
  The server derives tenant and user from the session and stores layouts by the
  fixed grid, closed saved-view ID and exact table-schema version.
- Add optimistic concurrency and reconciliation. A failed or conflicting save
  retains the last server-confirmed state, reports a traceable error and
  reloads before retry instead of showing an optimistic success.
- Persist only authoritative personal foundations: favorites and recency over
  the existing closed My Work view IDs, plus a default Project selected from
  the current actor's live My Work `projectOptions`.
- Save one personal filter snapshot per closed My Work view using only the
  already-supported Project, priority and bounded search fields. Restoring a
  view replays those fields through the existing server-owned query contract.
- Add persistent, append-only published-grid-view root/revision metadata for a
  Project permission boundary, including name, description, table schema,
  canonical definition/hash, version lineage, publisher evidence and
  rollback-as-a-new-revision metadata.
- Keep the unresolved publisher-authority rule fail-closed. The live
  capability is false with a stable unavailable reason; no production actor
  can publish or roll back until the Class-B decision is approved.
- Expose honest UI seams for shared publication, server-defined sort/group
  behavior, bulk actions and export. Unsupported operations remain visibly
  unavailable with translated reasons and never dispatch fabricated commands.
- Preserve the 1440×900 classic industrial layout: stable Shell and context,
  one page primary action, dense list and 340px properties inspector remain
  visible without document-level scrolling.
- Add direct `zh` and `zh-TW` translations, backend/frontend/component/browser
  tests, runtime migration evidence and affected trilingual visual evidence.

## Non-scope

- No Tooling List ten production views, arbitrary user-authored server filters,
  unrestricted CSV/XLSX export, domain bulk commands, large-data
  virtualization or production-scale performance claim.
- No generic User Defaults, caller-selected preference key, caller-selected
  user, arbitrary grid ID, arbitrary view ID or caller-selected schema API.
- No personal-preference mutation of a published view or its revision history.
- No inference that `System Manager`, Project owner, Project member, RACI,
  transport role or an arbitrary role label is an administrator or Project
  lead for UX-028 publication.
- No active publish/rollback BFF command, authority fixture, default publisher
  binding or historical backfill while the publisher policy is unresolved.
- No change to the accepted R1-03 session-bootstrap preference object or its
  fixed navigation command.
- No activation of `Core.png`, R1-05, R1-07, P5-01, ERPNext/JCE connectivity or
  pending DR-REC behavior.
- No conversion of the other repository-native tables to the new grid in this
  atomic task.

## Repository facts and decisions

1. The live My Work API already owns closed view IDs, Project options, filters
   and stable cursor paging. Those facts remain server-owned and are not
   broadened by personalization.
2. The prototype Worklist's browser `localStorage` is demo state. It may retain
   prototype-only filters/navigation, but it is never read by the live My Work
   preference path and is not migration input.
3. Session bootstrap is a closed accepted R1-03 contract containing only
   `preferences.navigationCollapsed`. R1-04 therefore adds a separate fixed
   `/api/npi/v1/me/preferences/my-work-grid` GET/PUT resource.
4. The personal preference row is keyed from the configured Site tenant,
   authenticated actor, fixed My Work grid ID and fixed table-schema version.
   Its canonical JSON contains only allowlisted view layouts and filter
   snapshots, favorite view IDs, bounded recent view IDs and an accessible
   default Project ID.
5. PUT accepts only the expected preference version, exact schema version,
   one closed view ID, its validated layout, its supported filter snapshot and
   bounded personal metadata. The filter is exactly a nullable accessible
   Project, a closed priority scheme/value pair and a search string capped at
   the existing 140-character query limit. It performs CSRF validation, row
   locking and 409 optimistic-version handling. It cannot name a user, tenant,
   storage key or arbitrary table.
6. Column definitions are code-owned and stable. Unknown/duplicate columns,
   non-finite widths, values outside each column's min/max, invalid order,
   excessive fixed-column counts, unsupported hidden required columns and
   schema mismatches fail closed.
7. The shared dense-grid foundation uses `<colgroup>` and an isolated fixed
   table layout. Fixed-start offsets are calculated from the confirmed visible
   widths; the grid owns its one internal scroll container so the document and
   panel do not acquire competing horizontal scrollbars.
8. Auto-fit measures only the header and currently rendered cells and clamps
   the result. Copy and evidence will not imply that unloaded server rows were
   scanned.
9. Pointer movement previews locally; persistence occurs after the completed
   interaction. Focusable separators expose orientation and min/max/current
   values. Arrow keys resize, Home/End select min/max, Enter auto-fits and a
   visible reset command provides a non-pointer alternative.
10. Published views use a stable root plus immutable append-only revisions.
    Rollback copies a selected historical definition into a new successor
    revision and records `restoredFromVersion`; it never overwrites history or
    silently moves a pointer.
11. Current contracts do not define the UX-028 publisher. Production
    authorization therefore resolves `canPublishSharedView: false` and
    `canRollbackSharedView: false` with
    `publisher_authority_policy_required`. Domain/repository tests may inject
    an explicit authority decision, but no test backdoor or live success path
    is installed.
12. Project-scoped visibility, when the read seam is activated, must reuse the
    existing server-side Project VIEW check. A frontend capability projection
    is presentation data and never substitutes for server authorization.
13. Export remains unavailable. Implementing a real export would require its
    own field-level authorization, data-volume, formula-injection, audit and
    file-delivery contract and is outside this task.

## Class-B publisher-authority hold

The exact meanings of “administrator” and “Project lead” in UX-028 are not
proven by the current capability contracts. Only the dependent publish and
rollback success rule is held.

1. Map `System Manager` to administrator and
   `NPI Engineering Project.owner_user_id` to Project lead. This is small but
   contradicts the current fact that the owner receives VIEW only and would
   convert infrastructure labels into business authority.
2. Add dedicated, versioned `shared_view_administrator` and
   `shared_view_project_lead` authority slots with explicit member bindings,
   validity, audit and fail-closed resolution. **Recommended.** This follows
   the established frozen-authority pattern without reusing an unrelated
   approval meaning.
3. Extend the versioned Project Work policy with a controlled `project_lead`
   role-to-publication capability mapping, requiring an active internal member
   and valid dated assignment. This can reuse existing membership data but
   requires a larger authoritative contract change and more temporal rules.

No option is activated in R1-04. Option 2 is recorded as the recommended later
business decision; absence of a binding continues to deny publication.

## Interaction and state design

- Grid preference states: loading, confirmed, locally previewing, saving,
  conflict-reconciling and failed.
- Schema mismatch or corrupt stored state: discard the unsafe layout, render
  code-owned defaults and return a stable reason without mutating on GET.
- Closed live saved views remain `all`, `today`, `overdue`, `approvals`,
  `blockers`, `waiting` and `integration`.
- Favorite and recent items reference only those IDs. Recent access is bounded
  and deterministic; selecting a view never changes its server-owned meaning.
- Default Project is `null` or one exact current actor Project option. A
  Project lost from live access is cleared in the returned effective
  preference and cannot be written back as accessible.
- A saved filter is explicitly committed with `Save current filters`; search
  keystrokes do not write preferences. Selecting a closed view restores its
  confirmed Project, priority and search snapshot, or the default Project when
  no snapshot exists.
- Grid settings use one compact secondary control. The inspector retains the
  only page-owned primary action.
- Sorting and grouping show their current server-owned policy. Bulk actions,
  export and shared publication are disabled secondary seams with explanatory
  text, not clickable success simulations.
- Fixed columns remain rectangular, inherit selected/hover backgrounds and
  keep text/icon status semantics while the non-fixed columns scroll beneath.

## Risks and controls

| Risk | Control |
|---|---|
| IDOR or cross-user preference writes | Tenant/user derive only from the authenticated session; no caller identity field exists |
| Generic preference storage escapes the product boundary | One fixed route, grid and schema; controlled DocType writes; no generic defaults wrapper |
| A stale tab overwrites a newer layout | Row lock plus expected version and 409 reconciliation |
| Personal settings mutate shared definitions | Separate storage, commands and immutable published-view revisions |
| Role labels accidentally become publication authority | Production authorizer is fail-closed and has no role shortcut |
| Corrupt or obsolete layouts break the table | Strict server/client validation and schema-version fallback to code defaults |
| Resize produces excessive writes | Local pointer preview and one save after a committed interaction |
| Fixed columns overlap or disappear while scrolling | Calculated sticky offsets, bounded fixed prefix and real-browser geometry assertions |
| Auto-fit claims unloaded data | Measure only rendered cells and state that boundary in accessible help/copy |
| Added toolbar controls compete with the primary action | One compact settings entry; unavailable seams remain secondary |
| 1440×900 acquires page-level overflow | One grid scroll owner, constrained work area and explicit viewport geometry checks |
| New DocTypes cannot roll back safely | Additive schema only, no backfill; code rollback leaves inert tables and data intact |

## Expected files

- `frontend/src/ui-adapters/dense-grid.tsx`
- `frontend/src/api/grid-preferences-data-source.ts`
- `frontend/src/components/live-my-worklist.tsx`
- `frontend/src/components/worklist.tsx`
- `frontend/src/domain/view-models.ts`
- `frontend/src/styles/app.css`
- `frontend/tests/unit/dense-grid.test.tsx`
- `frontend/tests/unit/grid-preferences-data-source.test.ts`
- affected Worklist/My Work unit tests
- `frontend/tests/e2e/r1-04-grid.spec.ts`
- `apps/npi_core/npi_core/grid_personalization/`
- `apps/npi_core/npi_core/grid_personalization_api.py`
- `apps/npi_core/npi_core/bff.py`
- three additive grid-personalization DocType directories
- `contracts/npi-api.openapi.yaml`
- backend domain, controller, repository, API and contract tests
- `scripts/verify_frappe_runtime.py`
- `apps/npi_core/npi_core/translations/zh.csv`
- `apps/npi_core/npi_core/translations/zh-TW.csv`
- generated catalogs and R1-04 trace/evidence/controller files

The list may contract if an existing safe boundary is reused. It may not expand
into a generic preference service, real export, bulk business command,
production publisher policy or unrelated table migration without a new scope
and ambiguity review.

## Changed-files to affected-tests

| Changed boundary | Affected checks |
|---|---|
| Shared dense-grid component and isolated CSS | new dense-grid unit tests; Worklist and live My Work units; `r1-04-grid.spec.ts`; axe; real geometry |
| Live My Work personalization integration | live list/data-source units; existing `p4-05-live.spec.ts`; view/filter/cursor/error/stale/selection regressions |
| Prototype Worklist adapter integration | existing grouping/filter/sort/column/selection/paging tests; explicit prototype/live state-isolation case |
| Fixed preference BFF, repository and DocType | domain/repository/API/controller/contract tests; guest, CSRF, closed fields, IDOR, schema, layout/filter bounds, Project access, 409 and cross-user cases |
| Published root/revision foundation | immutable-history, name/description/permission/version/hash/audit and rollback-successor tests; fail-closed live authority tests |
| BFF/OpenAPI/runtime surface | router method/path tests, OpenAPI-source agreement, migration/runtime verifier and generic-CRUD denial |
| Literal English copy and Frappe catalogs | catalog generation/check, i18n lint, direct zh/zh-TW coverage and mixed-language scans |
| Shared source/style/schema change | Python/frontend full tests and coverage, type/lint/format/style/boundary/security scans, two fresh migrations and `git diff --check` |

## Validation plan

1. Level 1 after each implementation batch:
   - changed-file format/lint/type checks;
   - targeted backend/frontend unit tests;
   - targeted English/zh/zh-TW browser cases;
   - `git diff --check`.
2. R1-04 Level 2 Task Gate:
   - complete grid-personalization backend and frontend module tests;
   - API/permission/controller/OpenAPI tests, including actor derivation,
     closed input, CSRF, cross-user isolation, version conflict and authority
     denial;
   - affected My Work/Worklist E2E, accessibility and exact-zero trilingual
     visual cases at 1440×900, plus 125%/150% internal-scroll checks;
   - pointer drag, rendered-page auto-fit, min/max, reset, fixed scroll,
     keyboard separator and remount persistence evidence;
   - i18n coverage/mixed-language scans, exact requirement traces, migration,
     rollback and Task Diff Review.
3. R1-04 Level 3 Release Gate, triggered by additive DocTypes, public BFF,
   shared UI infrastructure and translation changes:
   - full `make verify`, controlled Frappe runtime verification and
     OpenAPI/source/runtime agreement;
   - two clean migrations plus generic DocType CRUD denial;
   - full non-visual browser suite and a clean no-update exact-zero visual
     matrix rerun after any accepted baseline creation;
   - security, accessibility, trilingual, rollback/recovery, traceability and
     independent code/UX review using the `release-gate` skill.
4. This task-level Level 3 does not replace the cumulative R1 shared
   Shell/design/i18n Level 3 bridge Gate after R1-06.

## Trace target

- `FR-UX-038`: `TECHNICAL_VERIFIED` when every column interaction,
  authenticated persistence and fixed-scroll requirement passes.
- `UX-007`: `TECHNICAL_VERIFIED_FOUNDATION`; grid fundamentals and honest
  seams are proven while Tooling production views, real domain bulk/export
  and server-scale virtualization remain held.
- `UX-027`: `TECHNICAL_VERIFIED_FOUNDATION`; personal layout, favorite, recent,
  saved-filter and accessible default-Project settings are proven over current
  live facts.
- `UX-028`: `TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD`; versioned,
  permission-bounded, audited immutable history and rollback semantics are
  proven while the exact publisher policy remains Class-B.
- `UX-035`: `TECHNICAL_VERIFIED_FOUNDATION`; the affected 1440×900 dense
  worklist is proven, while cumulative all-domain density remains the R1 bridge
  Gate.

## Migration and rollback

The change is additive: synchronize the three new DocTypes, run two clean
migrations and verify no backfill or destructive patch exists. Rollback
reverts the single R1-04 commit and removes the BFF/UI integration. The additive
tables and any personal/published-view rows remain inert and recoverable; no
destructive cleanup is required. If a later deployment reapplies R1-04, the
same schema-version and canonical validation can read the retained rows.
