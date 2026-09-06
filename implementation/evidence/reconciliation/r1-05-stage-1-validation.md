# R1-05 Stage 1 Validation — FR-UX-040 Live My Work Inspector Pane

Result:
`PASS — LEVEL 3 R1-05 STAGE 1 PUBLIC PREFERENCE/SHARED UI CHECKPOINT`

Date: 2026-07-27

Stage 1 starting checkpoint:
`88fca2bd898ca08432c5a5f5eec9f25dc963fc14`

Target requirement:

- `FR-UX-040`: `TECHNICAL_VERIFIED`
- `FR-UX-041`: remains `PLANNED_SHARED_UX_REMEDIATION`
- `FR-UX-043`: remains `PLANNED_SHARED_UX_REMEDIATION`

The exact Stage 1 requirement, implementation, public contract, runtime,
security, browser, accessibility, trilingual visual and rollback evidence
passed the triggered Level 3 Gate. This checkpoint advances only
`FR-UX-040`; it does not advance R1-05 Stage 2 or Stage 3 and does not make
R1-05 as a whole PASS.

## Delivered boundary

- Added one fixed authenticated preference resource for the live My Work
  inspector. The server owns the actor, pane identity, schema version and
  namespaced Frappe User Default key.
- Closed the preference to schema `my-work-inspector-v1`, integer width
  `260..480`, boolean collapse state and a `340px` default. Invalid stored
  state falls back to the default with
  `recoveryReason=stored_preference_invalid`; GET does not repair storage.
- Replaced the live My Work range approximation with a visible vertical
  separator supporting bounded pointer preview, one release commit,
  cancellation/lost-capture recovery, `20px` keyboard adjustment, Home/End
  limits and double-click reset.
- Kept the live pane parent-controlled. Preference loads and saves are bound
  to the active authenticated session generation, writes are serialized, a
  failed save restores the last server-confirmed layout, and retry requires an
  explicit reload.
- Preserved selected work item, filter state, grid scroll and mounted
  inspector content across collapse/expand. When collapse hides focused
  content, focus moves to the visible expand path; failed expansion moves
  focus to the traceable reload action.
- Kept the responsive stacked breakpoint presentation-only. It hides the
  separator without writing a different desktop preference.
- Retained the prior uncontrolled `DockedInspector` compatibility path and its
  existing `320px`/localStorage behavior outside the live My Work slice. Stage
  1 does not claim a product-wide pane migration.
- Added literal English source copy and direct `zh`/`zh-TW` catalog entries for
  pane resize, persistence, recovery and validation states.
- Added no DocType, database table, patch, production dependency, ERPNext
  integration or external connection.

## Changed-files to affected-tests

| Changed files / boundary | Required affected tests and checks | Current evidence |
|---|---|---|
| `apps/npi_core/npi_core/inspector_preferences/__init__.py`; `domain.py` | `tests.test_r1_05_inspector_preferences_domain`; API round-trip and corrupt-storage cases in `tests.test_r1_05_inspector_preferences_api`; exact schema checks in `tests.test_r1_05_inspector_preferences_contract` | Included in focused backend `28/28 PASS` |
| `apps/npi_core/npi_core/inspector_preferences/frappe_repository.py`; `inspector_preferences_api.py` | Actor-bound read/write, internal-user denial, CSRF, exact fields/types/bounds, confirmed write, corrupt read fallback, storage failure/rollback, duplicate-row repair and fixed User lifecycle scope in `tests.test_r1_05_inspector_preferences_api`; controlled local Frappe runtime in `scripts/verify_frappe_runtime.py` | Focused backend `28/28 PASS`; `make frappe-runtime-verify` PASS; final residual inspector `DefaultValue` rows `0` |
| `apps/npi_core/npi_core/bff.py` | Fixed GET/PUT route mapping, request-ID requirement, direct/BFF route-disable behavior in `tests.test_r1_05_inspector_preferences_api`, `tests.test_r1_05_inspector_preferences_contract`, `tests.test_phase4_project_controls_runtime_verifier` and the live disabled/recovered Project Controls runtime lane | Static/unit checks PASS; all `18` controlled routes passed disabled and recovered live probes |
| `contracts/npi-api.openapi.yaml` | YAML parse plus exact path, methods, closed request/response fields, constants, integer bounds and response headers in `tests.test_r1_05_inspector_preferences_contract` | Included in `28/28 PASS` |
| `frontend/src/api/my-work-inspector-preferences-data-source.ts` | `frontend/tests/unit/my-work-inspector-preferences-data-source.test.ts`; session/queue integration in `my-work-inspector-personalization.test.tsx`; exact HTTP transport in `frontend/tests/e2e/r1-05-panes.spec.ts` | Focused frontend unit set `48/48 PASS`; focused behavior `5/5 PASS`; complete behavior `256/256 PASS` |
| `frontend/src/components/my-work-inspector-personalization.ts` | `frontend/tests/unit/my-work-inspector-personalization.test.tsx`; injected live integration in `live-my-worklist.test.tsx`; actor switch, stale completion, FIFO saves, rollback and reload in R1-05 browser cases | Focused unit and behavior sets PASS; failure/reload and actor-generation cases passed |
| `frontend/src/ui-adapters/resizable-pane.tsx` | `frontend/tests/unit/resizable-pane-separator.test.tsx`; controlled integration in `primitives-and-objects.test.tsx`; pointer/keyboard/reset/cancellation cases in `frontend/tests/e2e/r1-05-panes.spec.ts` | Focused unit and behavior sets PASS, including stale-controlled-value and capture-loss regressions |
| `frontend/src/components/live-my-worklist.tsx`; `object-components.tsx`; `primitives.tsx`; `styles/app.css` | `frontend/tests/unit/live-my-worklist.test.tsx`; `frontend/tests/unit/primitives-and-objects.test.tsx`; focused R1-05 accessibility/geometry/browser cases; affected P4-05 live My Work and R1-04 grid regression suites; TypeScript, ESLint, Stylelint, boundary and industrial-UI checks | Focused units `48/48 PASS`; complete frontend units `577/577 PASS`; behavior `256/256 PASS`; clean visual matrix `210/210 PASS` |
| `apps/npi_core/npi_core/translations/zh.csv`; `zh-TW.csv`; `frontend/src/generated/catalogs.ts` | Generated-catalog freshness, direct locale coverage, placeholder/terminology validation, mixed-language scan and affected English/Simplified Chinese/Traditional Chinese browser profiles | `2,671` English sources with complete direct `zh`/`zh-TW` coverage; i18n checks and clean trilingual visual matrix PASS |
| `frontend/tests/e2e/p4-05-live.spec.ts`; `frontend/tests/e2e/r1-04-grid.spec.ts` | Existing live My Work and grid suites now install the fixed inspector preference route and exercise the separator-compatible inspector path without changing their original business contracts | Affected repair replay `11/11 PASS`; final single-worker complete behavior matrix `256/256 PASS` |
| `frontend/tests/e2e/r1-05-panes.spec.ts`; three exact snapshot files under `frontend/tests/e2e/r1-05-panes.spec.ts-snapshots/` | Five non-visual cases for persistence/recovery/failure/focus/responsive behavior and three exact trilingual profiles: English `1366×768 @100%`, Simplified Chinese `1440×900 @125%`, Traditional Chinese `1920×1080 @150%` | Focused behavior `5/5 PASS`; focused exact visual `3/3 PASS`; all three images passed original-resolution review |
| `scripts/verify_frappe_runtime.py` | `tests.test_r1_05_inspector_preferences_contract`, `tests.test_local_frappe_runtime_safety`, affected localization/grid contract tests and the controlled local Frappe runtime with disposable internal/external actors | Focused contract checks and complete `make frappe-runtime-verify` PASS; disposable inspector actor removed with `0` residual preference rows |
| `scripts/verify_project_controls_runtime.py`; `tests/test_phase4_project_controls_runtime_verifier.py` | Static runtime-verifier contract plus live BFF/direct GET/PUT disable and recovery probes; CSRF must be present on PUT even without an idempotency key | Static verifier, direct header smoke and all `18` disabled/recovered route probes PASS |
| `implementation/REQUIREMENT_TRACEABILITY.csv`; `scripts/reconcile_v1_2_traceability.py`; `scripts/verify_v1_2_reconciliation.py`; `tests/test_v1_2_reconciliation.py`; this validation file | Generator freshness, exact `FR-UX-040` evidence set, validation-file existence, complete reconciliation verifier, and proof that `FR-UX-041`/`FR-UX-043` remain planned | Generator freshness PASS; reconciliation unit tests `12/12 PASS`; independent verifier PASS |
| Generated coverage, Playwright result/report and screenshot artifacts under `implementation/evidence/` | Hash/freshness review, exact terminal status, failed-test set, visual review and historical-evidence preservation | Canonical Stage 1 terminal artifact retained; historical Phase 3/4/5 evidence restored byte-for-byte in the task diff |

## Public contract summary

The additive BFF resource is:

```text
GET /api/npi/v1/me/preferences/my-work-inspector
PUT /api/npi/v1/me/preferences/my-work-inspector
```

Contract invariants:

- Both methods resolve only the authenticated internal Frappe actor. The
  caller cannot send a user, tenant, pane ID, storage key or arbitrary schema.
- GET accepts no business/query fields and does not mutate corrupt storage.
- PUT requires the active session CSRF token and exactly this JSON body:

  ```json
  {
    "schemaVersion": "my-work-inspector-v1",
    "widthPx": 340,
    "collapsed": false
  }
  ```

- `widthPx` is an exact integer from `260` through `480`; `collapsed` is an
  exact boolean; additional or missing fields and unsupported schema versions
  are rejected.
- A successful GET or PUT returns exactly
  `paneId`, `schemaVersion`, `widthPx`, `collapsed` and `recoveryReason`.
  `paneId` is always `my-work-inspector`; `recoveryReason` is either `null` or
  `stored_preference_invalid`. Successful PUT returns a confirmed layout with
  no recovery reason.
- Successful responses require `Cache-Control: private, no-store`,
  `X-Request-ID` and `X-Trace-ID`. Errors remain the established NPI Problem
  Details boundary with stable `400/401/403/422/500/503` behavior as
  applicable.
- The public session bootstrap schema is unchanged. No generic preference
  endpoint, arbitrary pane registry, idempotency-key contract or optimistic
  version field is introduced.

Because this stage adds a public BFF/OpenAPI resource and shared UI/i18n
behavior, it triggers Level 3 validation.

## Security review

- The Frappe methods retain `allow_guest=True` only so the NPI boundary can
  return normalized authentication Problem Details. Both methods authenticate
  inside the handler; guest access returns `401`.
- External/Website users are rejected. The repository receives only the
  authenticated session actor, and the fixed key
  `npi_one_my_work_inspector_layout_v1` is never caller-controlled.
- PUT requires CSRF before persistence. The route-disable switch covers both
  BFF and direct inspector methods and fails closed with the established
  retryable `503` response.
- Input and stored JSON are closed and bounded. Duplicate JSON fields,
  non-finite values, wrong exact types, overlong/deep corrupt input and
  unsupported fields cannot become preference state.
- Persistence replaces every fixed actor/key row in the same request
  transaction, writes the replacement with `parenttype="User"`, invalidates
  the actor cache and reads the value back for exact confirmation. Storage or
  confirmation failure cannot return success and is rolled back by the
  established domain-call boundary.
- The controlled My Work client does not read or write the legacy browser
  localStorage keys. Session generation and abort checks prevent one actor's
  pending load/save completion from becoming another actor's displayed state.
- No permission widening, raw private URL, secret, production credential,
  generic DocType mutation route or external-system connection is added.

## Migration and data review

- Database migration requirement: **none**. There is no new or changed
  DocType, patch, DDL, backfill or destructive transformation.
- A preference row is created lazily only after a valid authenticated PUT,
  using Frappe's existing `DefaultValue` table and one fixed namespaced key.
- GET performs no repair. Missing storage uses the default; invalid storage
  remains recoverable and visible until the actor makes an explicit valid PUT.
- Explicit PUT clears any legacy/duplicate rows for only the fixed actor/key
  and writes one `parenttype="User"` row. The pinned Frappe User delete/rename
  lifecycle therefore owns the replacement row.
- Translation rows and the generated frontend catalog are additive. No package
  or lockfile dependency change is required.
- No production migration or production-data operation was executed.

## Rollback and recovery

- Before retained preference use, revert the bounded Stage 1 code, contract,
  catalog and test change set.
- After retained preferences exist, first use the existing
  `npi_p4_05_routes_disabled` fail-closed switch if the route must be stopped,
  preserve the namespaced `DefaultValue` rows, and deploy a reviewed forward
  correction.
- Reverting the BFF/UI integration leaves any retained preference rows inert
  and recoverable. Do not delete user-default rows as part of rollback; there
  is no schema cleanup to perform.
- Reapplication uses the same fixed key and schema. Corrupt or incompatible
  stored content fails safely to the default and remains explicitly
  repairable by a later valid PUT.
- The responsive stacked layout never writes preference state, so viewport
  changes require no data rollback.

## Level 3 Gate evidence

### Static, unit, coverage, i18n, build and audit

The last completed full repository `make verify` before the Stage 1
validation evidence reference was added passed with:

- `746` Python tests;
- `577` frontend unit tests;
- `2,671` literal English translation sources with complete direct `zh` and
  `zh-TW` coverage;
- coverage of `85.23%` statements, `83.31%` branches, `89.03%` functions and
  `87.24%` lines;
- TypeScript, ESLint, Prettier, Stylelint, module-boundary, industrial-UI,
  generated-source and prohibited-pattern checks passing;
- production build passing; and
- complete and production-only npm audit lanes passing.

The `746` Python count is retained with its exact pre-trace provenance; it is
not represented as a post-document terminal count. After this validation
document was created, the exact Stage 1 trace checks passed independently:

| Check | Result |
|---|---|
| `python -B -m unittest tests.test_r1_05_inspector_preferences_api tests.test_r1_05_inspector_preferences_domain tests.test_r1_05_inspector_preferences_contract tests.test_phase4_project_controls_runtime_verifier -v` | `PASS — 28/28` |
| `npm --prefix frontend run test:unit -- tests/unit/my-work-inspector-preferences-data-source.test.ts tests/unit/my-work-inspector-personalization.test.tsx tests/unit/resizable-pane-separator.test.tsx tests/unit/live-my-worklist.test.tsx tests/unit/primitives-and-objects.test.tsx` | `PASS — 48/48` |
| Behavioral smoke of `npi_request` with and without an idempotency key | `PASS` — supplied CSRF retained in both paths; no idempotency header synthesized |
| `python scripts/reconcile_v1_2_traceability.py` | `PASS` — generated trace is current |
| `python -B -m unittest tests.test_v1_2_reconciliation -v` | `PASS — 12/12` |
| `python scripts/verify_v1_2_reconciliation.py` | `PASS` |
| `git diff --check` | `PASS` |

The terminal canonical `make verify`, run after the validation and trace
evidence were present, also passed with:

- `747` Python tests;
- `577` frontend unit tests;
- `2,671` literal English translation sources with complete direct `zh` and
  `zh-TW` coverage;
- the same `85.23%` statement, `83.31%` branch, `89.03%` function and `87.24%`
  line coverage;
- all static, type, formatting, style, boundary, generated-source,
  prohibited-pattern and repository-reconciliation lanes passing;
- the production build passing; and
- both complete and production-only npm audit lanes reporting zero
  vulnerabilities.

### Controlled Frappe runtime and security

One complete `make frappe-runtime-verify` command passed. Its Stage 1
coverage proved:

- guest GET/PUT denial, internal/external actor separation and exact
  authenticated-actor binding;
- CSRF rejection and exact closed request/schema/type/bound validation;
- corrupt stored preference fallback without query-side repair;
- confirmed PUT persistence across a fresh authenticated session;
- fixed User lifecycle storage, disposable actor cleanup and `0` residual
  inspector-preference `DefaultValue` rows;
- no optimistic success after storage, confirmation or transaction failure;
- BFF and direct method route-disable behavior for all affected methods; and
- all `18` controlled routes returning their exact disabled and recovered
  contracts.

The runtime used controlled local disposable fixtures. It did not connect to
production ERPNext, change production data or require a database migration.

### Browser behavior

The focused R1-05 behavior run passed `5/5`.

The first complete behavior run passed `253/256`; the remaining three cases
ended in Chromium process crashes. After the affected fixture repair, the
focused replay passed `11/11`. The final complete single-worker replay then
passed `256/256` in `12.0` minutes. No retry waiver, skipped test or lowered
assertion was used.

The terminal behavior evidence covers exact current-actor GET/PUT transport,
bounded pointer and keyboard resize, double-click reset, collapse/expand,
server-invalid recovery, failed-save rollback and reload, focus recovery,
responsive presentation-only stacking, affected P4-05 My Work behavior and
R1-04 grid regression paths.

### Trilingual exact visual matrix

The focused R1-05 exact visual run passed `3/3` for:

- English at `1366×768 @100%`;
- Simplified Chinese at `1440×900 @125%`; and
- Traditional Chinese at `1920×1080 @150%`.

The first complete no-update visual run passed `95/210` and reported `115`
expected mismatches against the pre-Stage-1 baselines. A controlled
single-worker baseline update run passed `210/210` in `8.6` minutes. The final
clean, no-update, single-worker run passed `210/210` in `10.8` minutes at the
unchanged `maxDiffPixelRatio: 0`.

The accepted set contains `117` reviewed tracked baseline replacements and
three new R1-05 images. Original-resolution review confirmed the new
separator, status, recovery and collapsed states, the single industrial
primary-action hierarchy, keyboard focus visibility, translated accessible
names, dense geometry and absence of document overflow or mixed-language UI.

Three of the `117` tracked replacements are a reviewed renderer-only delta:

- `frontend/tests/e2e/visual-matrix.spec.ts-snapshots/locale-gate-zh-1366x768-100-linux.png`;
- `frontend/tests/e2e/visual-matrix.spec.ts-snapshots/locale-trial-zh-1366x768-100-linux.png`; and
- `frontend/tests/e2e/visual-matrix.spec.ts-snapshots/locale-trial-zh-TW-1366x768-100-linux.png`.

Each image changes exactly four pixels at `(1352,747)`, `(1353,747)`,
`(1352,748)` and `(1353,748)`, on the native fixture-state select's upper-right
edge. In the two Simplified Chinese images the RGBA transitions are:

```text
(144,154,158,255) -> (143,154,159,255)
(228,232,233,255) -> (229,231,233,255)
(216,220,222,255) -> (215,219,220,255)
(145,155,159,255) -> (144,154,159,255)
```

The Traditional Chinese image contains the exact reverse transitions. The
run used Playwright `1.61.1` and Chromium Headless Shell `149.0.7827.55`
revision `1228`. An independent no-update single-worker `210/210` replay
reproduced the accepted set. The twelve pixels change no text, geometry,
meaning, interaction or UX state.

### Independent audits

Final independent review results:

- source/API/security: `0 blocker / 0 major / 0 minor`;
- Frappe User-default lifecycle and CSRF helper:
  `0 blocker / 0 major / 0 minor`;
- UX/i18n/accessibility: `0 blocker / 0 major / 0 minor`; and
- complete visual diff: `0 blocker / 0 major / 0 minor`.

The initial source audit had identified stale controlled-value restoration on
Escape/lost capture and pointer release, a missing PUT allowance on the
route-disable handler, an unbounded corrupt-storage recursion edge and missing
live inspector route-disable probes. Those issues were repaired and
independently re-reviewed. The follow-up audit also confirmed
`clear_user_default` plus
`add_user_default(..., parenttype="User")` lifecycle semantics and the
non-idempotent PUT CSRF header path.

## Canonical artifacts and historical preservation

The terminal coverage artifact is:

```text
implementation/evidence/reconciliation/r1-05/stage-1/coverage/coverage-summary.json
SHA-256 c05bb103bb7a0cd0ed12243a64789627995134eb203cf5f4f99da0c22fc2e2dc
```

The terminal Playwright artifact is:

```text
implementation/evidence/reconciliation/r1-05/stage-1/playwright-results/.last-run.json
SHA-256 91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903
```

It records `status: passed` and an empty failed-test set. As with earlier task
evidence, the compact artifact does not encode the `5/5`, `256/256`,
`3/3` or `210/210` terminal counts; those direct terminal results are recorded
above.

The three new exact R1-05 baselines are:

```text
f351b3336a376e945321a58d2cf3a8d20119e61a60414199e97a0913c9f6185d  r1-05-inspector-en-1366x768-100-linux.png
72ac41dcd27eb93d211f235912ec2533be41f07c6494d0d44cb5a856798a5591  r1-05-inspector-zh-1440x900-125-linux.png
18b099df27df5b8122c3d30d84383b50f24cce48d131e8e77221bd56b6759fc0  r1-05-inspector-zh-TW-1920x1080-150-linux.png
```

The historical Phase 3, Phase 4 and Phase 5 evidence directories were
restored; the final scoped diff contains no change under those directories.
The current reconciliation remains `282` unique rows with the unchanged
`173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT` distribution.
Only `FR-UX-040` advances, and its exact generated evidence set passed;
`FR-UX-041` and `FR-UX-043` remain planned.

## Final Gate and transition decision

R1-05 Stage 1 passes the triggered task-level Level 3 public
preference/shared-UI checkpoint. Its migration, security, recovery, rollback,
accessibility, trilingual and original-resolution evidence has no unresolved
finding.

R1-05 as a whole is not PASS. Automatic continuation activates only Stage 2,
the `FR-UX-041` field/attachment truth-primitives slice. Stage 3
(`FR-UX-043`) remains planned until the Stage 2 Gate, and no R1-06, R1-07,
held P5-01 or external-integration work is activated by this checkpoint.
