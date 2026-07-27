# R1-04 Validation — Shared Grid Personalization and Governed-view Foundation

Result: `PASS — LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`

Date: 2026-07-27

Starting synchronized bridge checkpoint:
`3e0721a1b8be8dbd1b618d78a635b74d28cd0178`

Target requirement trace states:

- `FR-UX-038`: `TECHNICAL_VERIFIED`
- `UX-007`: `TECHNICAL_VERIFIED_FOUNDATION`
- `UX-027`: `TECHNICAL_VERIFIED_FOUNDATION`
- `UX-028`: `TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD`
- `UX-035`: `TECHNICAL_VERIFIED_FOUNDATION`

The five target trace rows, their evidence sets and the final task diff passed
the complete triggered Level 3 Gate. R1-04 is accepted at the bounded
foundation states above; no production publisher authority, export, bulk
business command or Tooling production-view claim is implied.

## Delivered boundary

- Added one repository-owned `DenseGrid` foundation and applied it to both the
  live My Work list and the prototype Worklist.
- Added pointer drag resize, rendered-row double-click auto-fit, bounded
  keyboard resize, min/max, individual/all reset, column visibility, bounded
  fixed-start columns and one grid-owned horizontal/vertical scroll surface.
- Kept the rendered table, column offsets, pointer geometry and ARIA values on
  the same exact persisted pixel-width model. When only the required Item and
  Action columns remain, the table stays exactly 420px wide and leaves neutral
  surplus viewport space instead of stretching those columns.
- Added the fixed authenticated
  `GET/PUT /api/npi/v1/me/preferences/my-work-grid` resource. Actor and tenant
  derive only from the Frappe session; the browser cannot select a user,
  tenant, key, grid or arbitrary schema/view.
- Persisted exact per-user/per-view/per-schema layouts, saved filter snapshots,
  favorite/recent closed view IDs and an accessible default Project using
  optimistic versioning and authoritative reload/reconciliation.
- Added strict code-owned schema validation, corrupt/obsolete-storage fallback
  to defaults, a translated recovery warning and controlled repair on the next
  version-zero write.
- Added three additive DocTypes for personal preferences and immutable
  published-view root/revision metadata. Published revisions retain canonical
  definitions, hashes, version lineage, publisher evidence and
  rollback-as-a-new-revision history.
- Kept live shared publication and rollback fail closed with
  `publisher_authority_policy_required`. Export and bulk-action seams remain
  visibly unavailable with stable reasons and dispatch no fabricated command.
- Preserved the classic industrial 1440×900 composition with page identity,
  one primary action, dense worklist, 340px inspector and grid-owned scrolling.
- Kept pointer previews transient and parent-controlled: net-zero release,
  cancellation, lost capture, non-active pointers and failed persistence all
  restore the last confirmed visual and ARIA width without stale local state.
- Serialized preference writes through an immutable FIFO. Adjacent edits for
  the same view may coalesce without losing filter-save intent; cross-view and
  non-adjacent edits remain ordered and derive their expected version from the
  last confirmed response.
- Closed the OpenAPI preference layout to the seven fixed ordered view IDs and
  aligned search validation/truncation with the Python/OpenAPI 140-Unicode-
  code-point contract, including supplementary-plane characters.
- Recursively copied and froze nested publication-authority evidence at both
  decision and revision boundaries. Caller/internal/snapshot mutation, cyclic
  evidence and corrupt lineage now fail or remain immutable without changing
  canonical hashes; repeated non-cyclic aliases remain valid.
- Added literal English source copy, direct Simplified/Traditional Chinese
  catalogs, component/API/runtime/browser/accessibility and trilingual visual
  evidence.

No Tooling ten-view implementation, unrestricted export, domain bulk command,
large-data virtualization, production-scale performance claim, generic user
default endpoint, caller-selected identity/key, active publish/rollback BFF,
production authority fixture, ERPNext/JCE connection, `Core.png` activation,
P5-01 resumption or R1-05 behavior is included.

## UX-028 Class-B authority hold

The current capability and policy contracts do not prove the exact meanings
of “administrator” or “Project lead.” R1-04 therefore proves immutable
published-view storage, Project permission boundary, audit/version lineage and
rollback semantics without installing a live publisher.

The retained options are:

1. Map `System Manager` and Project owner directly. This is rejected as an
   unsafe inference from infrastructure/ownership labels.
2. Add dedicated, versioned `shared_view_administrator` and
   `shared_view_project_lead` authority slots with explicit bindings,
   validity, audit and fail-closed resolution. **Recommended, not activated.**
3. Extend the versioned Project Work policy with an explicit publication
   capability and dated active-member binding.

Only the dependent success rule is held. Reads, personal preferences and the
fail-closed immutable foundation are complete without weakening authority.

## Changed-files to affected-tests

| Changed boundary | Evidence |
|---|---|
| shared DenseGrid component/layout and isolated CSS | DenseGrid exact-width unit tests; Worklist/live-grid units; industrial static guard; required-column-only 420px browser regression; R1-04 E2E geometry, Axe and exact screenshots |
| live My Work personalization integration and generation-scoped reconciliation | hook/data-source/live-grid units; FIFO cross-view and same-view coalescing cases; Unicode code-point bounds; exact current-actor browser transport; save failure, conflict, reload, session-switch and remount cases |
| prototype Worklist DenseGrid adoption | grouping/filter/sort/selection/paging units; unique group accessible-name regression |
| fixed preference BFF, domain, repository and additive DocTypes | grid domain/repository/API/contract tests; guest, CSRF, closed-field, IDOR, schema, filter, Project-access, version and generic-CRUD denial |
| immutable published-view foundation | first/revision/rollback lineage, canonical hash, mutation denial, authority denial and controlled real-Site runtime |
| OpenAPI/BFF/runtime agreement | ordered seven-view and Unicode-bound contract parser tests, two migrations, runtime verifier and source/runtime route agreement |
| literal copy and catalogs | generated-catalog drift, 2,659-source i18n audit, direct `zh`/`zh-TW` coverage and mixed-language browser scans |
| reconciliation/evidence | exact trace-set generator/verifier, evidence-file existence, historical Phase 3/4 preservation and Task Diff review |

## Level 3 Gate evidence

Targeted backend result: `PASS — 42/42`.

Two consecutive additive migrations passed after the final code and visual
baseline state.
The three DocTypes synchronized without a patch, backfill, destructive
transformation or production data operation.

The complete controlled local Frappe runtime then passed. It proved:

- guest GET/PUT denial; CSRF, malformed/extra/missing-field and schema denial;
- cross-user read isolation and exact actor/tenant binding;
- optimistic version conflict and no generic DocType browser mutation;
- corrupt stored-version fallback and controlled version-zero repair;
- three immutable published revisions and rollback as a new successor;
- six controller mutation denials, UTC timestamp coercion and fixture rollback;
- unchanged Project, Project Work, Gate Evidence, Gate Review, Project
  Controls/My Work, route-disable/recovery and cross-process replay lanes.

The disposable Docker runtime was interrupted again during finalization.
Exact inspection found the stopped MariaDB/Redis records and their historical
OCI collision errors, but no live task, shim, `runc` entry, cgroup or exact
stale runtime directory. Both named volumes remained intact. Sequential
exact-ID starts restored MariaDB and Redis to healthy without deleting,
recreating or moving a container or volume.

The first complete runtime retry then correctly detected a stale My Work
projection left by an earlier interrupted fixture run. Its first and second
committed rebuilds had identical `503`-source / `218`-assignment results and
digest, proving deterministic convergence; only the pre-rebuild snapshot
differed. The official Project-controls-only lane then passed on the reconciled
base, followed by a clean complete runtime pass. No database reset, fixture
deletion or product-code waiver was used.

Complete frontend preflight:

- Whole-repository Python/reconciliation tests: `727/727 PASS`.
- Vitest: `549/549 PASS`.
- TypeScript, ESLint, Prettier, Stylelint, module-boundary, industrial-UI,
  generated-source and prohibited-pattern checks: `PASS`.
- i18n extraction: `2,659` literal English sources with `100%` direct `zh` and
  `zh-TW` coverage.
- Coverage: `84.32%` statements, `82.85%` branches, `88.43%` functions and
  `86.32%` lines.
- Production build and exact display-brand/Core guard: `PASS`.
- Reviewed install-script check and complete/production-only npm audits:
  `PASS`, `0` vulnerabilities.

Portable coverage evidence:

```text
implementation/evidence/reconciliation/r1-04/coverage/coverage-summary.json
SHA-256 6c00713fcd43542f7b78a1847ab20cc41778de93745551749ef99c7824f3dd18
```

Focused non-visual browser result after the final UI/accessibility repairs:
`PASS — 7/7`.

Complete non-visual browser result:
`PASS — 251/251` in 11.3 minutes.

The first post-audit complete non-visual replay was interrupted after roughly
205 cases when the development container, MariaDB and Redis all stopped.
Their exact existing instances and named data were restarted without deletion,
recreation or reset. The exact previously crashed all-optional-columns-hidden
scenario then passed `1/1`, followed by the uninterrupted `251/251` run.
The final health check found the development container running and both
preserved services running healthy.

Focused exact visual result from the final terminal run:
`PASS — 6/6` at unchanged `maxDiffPixelRatio: 0`.

The six full-page profiles cover English, Simplified Chinese and Traditional
Chinese at 1440×900, English at 1366×768, Simplified Chinese at 1920×1080 and
125%, and Traditional Chinese at 1366×768 and 150%. The zoomed profiles prove
grid-owned horizontal overflow and no document overflow. Three additional
exact header snapshots prove rendered LaunchFlow pixels in every 1440 locale.
The 150% capture resets and asserts the actual `#main-content` scroll owner, so
the logo, H1 and page identity remain visible.

Independent focused code/security review:
`PASS — 0 unresolved blocker / 0 unresolved major / 0 unresolved minor`.
The review first identified two major issues—the stretched all-hidden layout
and overwriteable pending preference write—and two minor contract edges—the
open ordered-view schema and UTF-16/code-point mismatch. The exact-width,
FIFO/coalescing, ordered OpenAPI and Unicode repairs above were independently
re-reviewed with no remaining finding.

Independent focused UX/i18n/accessibility review:
`PASS — 0 blocker / 0 major / 0 minor`.

The existing complete visual matrix was first run without updates. Its
`113/207` mismatches were reviewed before acceptance:

- `99` were confined to the generated catalog hash in the bottom status bar;
- `14` were exactly the in-scope DenseGrid/Worklist surfaces: three live
  My Work profiles, three locale Worklists, five Work geometry profiles and
  three rendered Work states; and
- English, Simplified Chinese, Traditional Chinese, compact, 125% and 150%
  samples preserved controls, inspector context, translations, status truth
  and grid-owned scrolling.

One controlled update run passed `207/207` in 7.2 minutes. The task retains
exactly `113` reviewed replacement baselines and nine new R1-04 images.
Thirteen pixel-identical re-encodings and four sub-threshold 1–10-pixel
update-all artifacts were restored to their exact prior bytes. A separate
final clean no-update full visual run passed `207/207` in 6.6 minutes.

The subsequent exact-width audit repair was then tested against that accepted
set without updates. `205/207` passed; the only two mismatches were the
expected wide Work geometry and read-only Work state, each changing exactly
19,785 pixels (`0.01` ratio). Original-resolution review confirmed that the
new pixels preserve the exact persisted column widths and leave neutral
surplus viewport space, while status, inspector, context and scroll ownership
remain unchanged. Only those two baselines were updated in a scoped `2/2`
run. The final clean no-update complete visual matrix then passed `207/207` in
7.3 minutes at unchanged zero tolerance.

Independent complete visual-diff review:
`PASS — 0 blocker / 0 major / 0 minor`.

The final post-repair focused browser run passed all `13/13` R1-04 cases
(seven non-visual and six exact visual) in 1.0 minute. Terminal artifact:

```text
implementation/evidence/reconciliation/r1-04/playwright-results/.last-run.json
SHA-256 91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903
```

The final dot reporter intentionally retained no HTML report.
`.last-run.json` records only the passing terminal status and failed-test ID
set; it does not encode the `13/13`, `251/251` or `207/207` counts. Those
direct terminal summaries are recorded above and are not inferred from the
artifact hash.

## Final Gate and transition decision

- The five R1-04 trace rows were generated at their exact target states.
  Focused reconciliation passed `10/10`; the complete trace/source/evidence
  verifier passed.
- Final scoped `make verify` passed in the approved Node 24.18.0/npm 11.16.0
  devcontainer: `727` Python tests, `549` frontend tests, generation, type,
  lint, format, style, boundaries, industrial UI, i18n, coverage, production
  build, display-brand/Core guard, install-script review, both zero-finding
  npm audits and V1.2 reconciliation.
- The final Task Diff, prohibited-pattern, no-diagnostic-artifact and
  historical Phase 3/4 byte-preservation checks passed. The two
  `allow_guest=True` Frappe transport decorators are intentional so the NPI
  Problem Details boundary can return stable authentication errors; both
  handlers authenticate internally, and unit/runtime evidence proves guest
  GET/PUT return `401`.
- Security, rollback, recovery, migration, accessibility, trilingual and
  original-resolution reviews passed with no actionable finding.
- The `release-gate` Skill decision is `PASS` for this task-level Level 3
  boundary. This does not replace the cumulative R1 shared
  Shell/design/i18n Level 3 bridge Gate after R1-06.

Automatic continuation activates only R1-05. R1-06 and the cumulative bridge
Gate remain ahead; R1-07 remains conditional on DR-REC-001, and P5-01 remains
`IN_PROGRESS_CHECKPOINTED`.

Rollback remains non-destructive: revert the single R1-04 commit and remove
the BFF/UI integration. The three additive tables and any rows remain inert
and recoverable; no destructive cleanup is required. Reapplication reuses the
same schema-version and canonical validators.
