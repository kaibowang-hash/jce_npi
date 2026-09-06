# R1-03 Plan — App Shell collapsed navigation, command foundation and contextual quick-create

Date: 2026-07-26
Branch: `codex/npi-v1.2-implementation`
Task: `R1-03 — App Shell collapsed navigation command and contextual quick-create`
Requirements: `FR-UX-039`, `UX-011`, `UX-018`
Status: `COMPLETE — PASS — LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`
Starting synchronized bridge checkpoint:
`07eb5f8b6cf859c406be2aaff3aa218fbf0bf61d`

## Scope

- Add explicit full and icon-only domain-navigation modes to the established
  LaunchFlow App Shell.
- Preserve the active domain, current Project identity and Shell geometry in
  both modes.
- Persist only the explicit navigation-mode choice through the established
  authenticated Frappe session-preference boundary. Store one fixed,
  NPI-owned user-default key and derive the actor exclusively from
  `frappe.session.user`.
- Apply responsive compact navigation independently from the explicit
  preference. A viewport change must not write or replace the saved choice.
- Keep every compact navigation target keyboard reachable, focus-visible,
  accessibly named and backed by a translated focus/hover tooltip.
- Add a keyboard-first command palette for approved existing routes and the
  current authorized Project context. Unsupported Part, live Tooling and live
  Trial targets remain explicit unavailable results rather than fabricated
  object matches.
- Add a Project-context quick-create menu that checks the existing live Project
  learning response and exposes `Create Project learning record` only when the
  server returns `permissions.canCreate: true`.
- Navigate quick-create to the existing governed learning form; that form
  rechecks the same server capability before any command can be submitted.
- Attach a bounded, validated internal return target to command navigation and
  expose a secondary return action without creating a second visual primary
  action.
- Add direct `zh` and `zh-TW` translations, unit/browser/accessibility coverage
  and affected trilingual visual evidence.

## Non-scope

- No unrestricted global search, external index, fuzzy object lookup or
  fabricated Part/Tooling/Trial result.
- No new creation authority, role, permission rule, backend authorization
  model, DocType, migration, event schema or ERPNext connection.
- No generic preference API: the public contract addition is one fixed
  navigation-preference command accepting only `{collapsed: boolean}`.
- No stage-specific Tooling/Trial/Part create action: the current contracts do
  not prove those capabilities.
- No use of `Core.png`, no change to the accepted R1-02 display-brand contexts,
  and no R1-04 or P5-01 product work.
- No browser-local copy of the live navigation preference.

## Repository facts and decisions

1. `frontend/src/app/app-shell.tsx` owns the fixed header, domain navigation,
   route-aware Project context and existing bounded prototype identity search.
2. `frontend/src/api/session.ts` and `frontend/src/i18n/runtime.tsx` already
   enforce an exact, validated, private/no-store Frappe session bootstrap and
   retain its trusted CSRF token for authenticated session commands.
3. Existing browser-local component preferences are unscoped prototypes and
   cannot satisfy the live, per-user persistence requirement. R1-03 therefore
   reuses Frappe v15's `DefaultValue` user-default store through a narrow
   NPI-owned wrapper.
4. The wrapper uses the constant key
   `npi_one_app_shell_navigation_collapsed`, always passes the authenticated
   user explicitly and never accepts a user ID or preference key from the
   browser. Missing or corrupt values resolve safely to expanded navigation
   without mutating data during bootstrap.
5. Session bootstrap gains the exact nested member
   `preferences: {navigationCollapsed: boolean}`. A fixed CSRF-protected
   `PUT /session/preferences/navigation` accepts only
   `{collapsed: boolean}` and returns the confirmed full bootstrap. This is a
   public contract change and triggers the task-level Level 3 gate.
6. The existing Project learning query is a strict BFF read and returns
   `permissions.canCreate`. The governed learning form performs a second
   capability check and requires the authenticated session command context
   before writing.
7. Terminal Projects explicitly allow authorized append-only learning, so the
   Project-level learning action is lifecycle-safe. No Gate-stage-specific
   object creation is inferred.
8. The router has approved Project, Gate, Tooling, Trial, Execution and My Work
   routes but no Part route. The command foundation will expose that absence
   honestly.

## Interaction and state design

- Desktop explicit mode: `full` or `compact`.
- Responsive mode: a media-query-derived compact presentation layered over the
  explicit choice; it is never persisted.
- Preference states: bootstrapping, ready, saving and failed. The UI changes
  only after a validated server response; failure retains the last confirmed
  value, reports that persistence was not confirmed and offers reconciliation
  through a fresh bootstrap before retry.
- Quick-create states: idle, checking, available, unavailable and failed.
  Failed checks expose a safe reference ID and retry; no create item is shown.
- Command palette states: closed/open plus literal-text filtering. `Ctrl+K` or
  `Meta+K` opens it; arrow keys, Home/End, Enter, Escape and a trapped Tab order
  work without a pointer.
- Return targets accept only normalized same-origin approved SPA routes, reject
  protocol-relative/external/nested targets and are re-authorized by the
  destination BFF.
- Compact navigation retains a rectangular active row with the existing
  industrial teal selection strip; icons supplement rather than replace the
  accessible label.

## Risks and controls

| Risk | Control |
|---|---|
| One user changes another user's preference | Actor comes only from `authenticated_user()` and the server uses one constant preference key |
| Generic user-default access bypasses permissions | No client-selected key/user; the NPI wrapper exposes one boolean command only |
| Stored value is missing or corrupt | Bootstrap resolves it to expanded navigation without a read-side mutation |
| Save fails or response is inconsistent | Keep the last confirmed mode, clear unsafe session command state and reconcile before retry |
| Responsive collapse overwrites the user's desktop choice | CSS/media state is separate; only an explicit toggle invokes the persistence adapter |
| A route label is mistaken for create authority | Quick-create item exists only after the validated live BFF capability returns true |
| Prototype routes are mistaken for live results | Prototype targets remain explicitly labelled; live contexts show unavailable states for unproven domains |
| Command return parameter becomes an open redirect | Strict same-origin route allowlist, length/control-character checks and nested-return rejection |
| Collapsed labels become hover-only | `aria-label`, `aria-describedby`, focus-triggered tooltip and keyboard tests |
| Shared Shell change regresses dense layouts or translations | Affected unit/E2E/three-language/zoom visuals now; cumulative full matrix remains mandatory at the R1 Level 3 bridge |
| Added toolbar controls create competing primary actions | Shell controls remain secondary/ghost; page-owned primary action is unchanged |

## Expected files

- `frontend/src/app/app-shell.tsx`
- `frontend/src/app/command-palette.tsx`
- `frontend/src/app/router.ts`
- `frontend/src/app/app.tsx`
- `frontend/src/api/session.ts`
- `frontend/src/i18n/runtime.tsx`
- `frontend/src/ui-adapters/npi-ui.tsx`
- `frontend/src/pages/project-governance-workspace.tsx`
- `frontend/src/styles/app.css`
- `apps/npi_core/npi_core/localization_api.py`
- `apps/npi_core/npi_core/bff.py`
- `contracts/npi-api.openapi.yaml`
- `tests/test_phase3_localization.py`
- `scripts/verify_frappe_runtime.py`
- `frontend/tests/unit/pages-and-shell.test.tsx`
- `frontend/tests/unit/router.test.tsx`
- `frontend/tests/unit/i18n.test.tsx`
- `frontend/tests/unit/project-governance-workspace.test.tsx`
- `frontend/tests/e2e/r1-03-shell.spec.ts`
- `apps/npi_core/npi_core/translations/zh.csv`
- `apps/npi_core/npi_core/translations/zh-TW.csv`
- generated catalogs and R1-03 trace/evidence/controller files

The file list may contract where an existing boundary can be reused directly.
It may not expand into a generic preference surface or a new authorization
model without a new ambiguity review.

## Changed-files to affected-tests

| Changed boundary | Affected checks |
|---|---|
| App Shell, command palette, navigation CSS and icons | `pages-and-shell.test.tsx`; `r1-03-shell.spec.ts`; affected Shell visual cases; axe |
| Session bootstrap, fixed preference PUT and Frappe user-default wrapper | `test_phase3_localization.py`; `i18n.test.tsx`; OpenAPI checks; `verify_frappe_runtime.py`; responsive persistence browser cases |
| Router return-target validation | `router.test.tsx`; command navigation/return E2E |
| Project learning focus handoff | `project-governance-workspace.test.tsx`; live capability quick-create E2E |
| Literal English copy and Frappe catalogs | catalog generation/check, `verify-i18n.mjs`, three-language mixed-language scans and screenshots |
| Shared source/style change | TypeScript, ESLint, Prettier, Stylelint, UI/boundary scans, `git diff --check` |

## Validation plan

1. Level 1 after each implementation batch:
   - changed-file format/lint/type checks;
   - targeted unit tests;
   - targeted English/zh/zh-TW browser cases;
   - `git diff --check`.
2. R1-03 Level 2 Task Gate:
   - complete frontend module verification and coverage thresholds;
   - affected non-visual E2E and accessibility cases;
   - exact-zero affected trilingual visual snapshots at 1366×768 and
     1920×1080, including 125%/150% and responsive compact presentation;
   - i18n literal-source, placeholder, missing-translation and mixed-language
     checks;
   - strict current-requirement trace review and Task Diff Review;
   - explicit confirmation that only the fixed session-preference contract
     changed and no schema/migration/permission model changed.
3. R1-03 Level 3 Release Gate, triggered by the public session contract:
   - full repository verification, controlled Frappe runtime verification and
     OpenAPI/source/runtime agreement;
   - full three-language, accessibility and visual matrices;
   - migration `N/A`, security, rollback/recovery and traceability review using
     the `release-gate` skill.
4. This task-level Level 3 does not replace the cumulative R1 Level 3 bridge
   Gate. The complete
   shared Shell/design/i18n matrix remains required after R1-06.

## Rollback

Revert the single R1-03 commit. The change introduces no schema migration.
Existing namespaced `DefaultValue` rows are harmless and ignored once the
endpoint/bootstrap member is removed, so rollback requires no destructive
cleanup. Existing R1-02 assets and evidence remain unchanged.
