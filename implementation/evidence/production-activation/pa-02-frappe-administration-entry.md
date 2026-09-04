# PA-02 Frappe Administration Entry

Status: **LOCAL TASK GATE PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-03 (Asia/Bangkok)

## Authorization and scope

The user authorized production-readiness development and specifically asked how
administrators will manage users, permissions and backend configuration. This
atomic task connects the LaunchFlow shell to the already approved Frappe
administration boundary:

- the authenticated session bootstrap reports whether the current Frappe user
  has the exact `System Manager` role;
- only that role receives an **Administration** action in the LaunchFlow header;
- the action opens the same-site Frappe Desk at `/app` for administration.

This task does not create a second user directory, custom role editor, password
flow, permission bypass, ERPNext browser connection or production credential.
Frappe remains the LaunchFlow session and administration authority. ERPNext
remains authoritative for approved internal identities, roles and service
scopes that enter LaunchFlow through the existing default-disabled P9-04
authorization projection.

## Acceptance and permission truth

| Condition                                                               | Result                                                                                  |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Authenticated user has the exact `System Manager` role                  | Bootstrap returns `isSystemManager: true`; the header offers **Administration**         |
| Authenticated user lacks that role                                      | Bootstrap returns `isSystemManager: false`; no Frappe administration action is rendered |
| A legacy deployment omits the additive flag during a rolling deployment | Frontend treats it as false and does not reveal the action                              |
| The flag has an invalid type or the bootstrap has an unknown shape      | Bootstrap validation fails closed                                                       |
| Administrator activates the action                                      | Browser navigates to same-site `/app`; Frappe re-enforces Desk and DocType permissions  |

The flag controls discoverability only. It is not an authorization boundary;
Frappe continues to enforce the actual Desk, User, Role and configuration
permissions on every request.

## Changed files to affected checks

| Changed file                                              | Affected behavior                                  | Planned evidence                        |
| --------------------------------------------------------- | -------------------------------------------------- | --------------------------------------- |
| `apps/npi_core/npi_core/localization_api.py`              | Current-session role projection                    | focused Python adapter tests            |
| `contracts/npi-api.openapi.yaml`                          | Additive session-bootstrap capability contract     | contract test and full reconciliation   |
| `frontend/src/api/session.ts`                             | Typed bootstrap capability                         | TypeScript check                        |
| `frontend/src/i18n/runtime.tsx`                           | Exact-shape validation and safe legacy fallback    | focused Vitest                          |
| `frontend/src/app/app-shell.tsx`                          | System Manager-only same-site Desk entry           | focused Vitest and trilingual UI checks |
| `apps/npi_core/npi_core/translations/zh.csv`, `zh-TW.csv` | Simplified and Traditional Chinese accessible name | catalog generation and i18n scan        |
| related tests and generated catalogs                      | Regression and translation coverage                | focused and task-level verification     |

## Verification

Verification used an isolated detached worktree at base `f1361930`; the user's
unrelated dirty documentation, screenshots, local-development files and
untracked public asset were neither staged nor modified.

- Focused Frappe session/localization adapter and contract tests: `43/43` PASS,
  including positive and negative `System Manager` role cases.
- Focused frontend localization and App Shell tests: PASS. The final
  reproducible role-gated matrix covers English, Simplified Chinese and
  Traditional Chinese; the App Shell file completed `36/36` focused tests.
- Full repository verification on the product patch: `2,990/2,990` Python tests
  PASS; development configuration, security scans, prototype governance, P0
  visual governance and V1.2 reconciliation PASS.
- Exact final frontend verification with Node `v24.18.0` and npm `11.16.0`:
  `1,146/1,146` tests PASS; statements `80.08%`, branches `79.51%`, functions
  `82.11%`, lines `82.66%`; generated-catalog check, typecheck, ESLint,
  Prettier, Stylelint, boundaries, industrial UI audit, production build,
  asset budgets, brand audit and install-script allowlist PASS.
- Localization audit: `9,323` literal English sources with `100%` Simplified
  and Traditional Chinese coverage; PASS.
- Dependency audit: no unreviewed install scripts and zero reported production
  or development vulnerabilities; PASS.
- `git diff --check`: PASS for the task files.

The first isolated attempt reused the shared `node_modules` tree and therefore
failed closed at the npm install-script provenance check. A clean
`npm ci --ignore-scripts` from the unchanged lockfile removed that environmental
ambiguity; the exact clean verification above then passed without changing any
dependency, lockfile, allowlist or CI configuration.

## Release-gate decision

**PASS for the PA-02 code checkpoint.** The change is additive, same-origin,
role-restricted for discoverability, migration-free and reversible. Frappe
remains the enforcing authorization boundary. The reproducible trilingual
System Manager fixture exercises the only newly rendered state, so unrelated
visual baselines are unchanged. This PASS does not authorize deployment or
imply that Entra, production users, ERP authorization projection or ERP
operation adapters are configured.

## Rollback

Rollback removes the additive bootstrap property, header action, translations
and tests. No migration, database rollback or external-state change is needed.

## Deferred boundaries

Safe sign-out is intentionally a separate atomic task because it must represent
timeout-after-commit truth and CSRF handling without claiming the session still
exists or has ended when the result is indeterminate. Entra configuration,
production user provisioning and ERPNext authorization/integration activation
also remain separate gated tasks; this checkpoint does not configure or enable
them.
