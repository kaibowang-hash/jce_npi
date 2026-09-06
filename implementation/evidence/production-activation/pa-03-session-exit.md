# PA-03 Governed Session Exit

Status: **LOCAL TASK GATE PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-03 (Asia/Bangkok)

## Authorization and scope

The user authorized continued production-readiness development and asked for a
usable authenticated product shell. This atomic task adds a governed exit for
the current LaunchFlow/Frappe session:

- the browser calls only the fixed `POST /api/npi/v1/session/logout` BFF;
- the BFF requires an authenticated user, the current Frappe CSRF token and an
  exact empty JSON object;
- the handler delegates to the pinned Frappe v15 `LoginManager.logout()`;
- the live shell shows the actual session user and a trilingual **Sign out**
  action;
- success navigates to `/login`; an absent, malformed, failed or timed-out
  response is treated as an unconfirmed outcome and freezes the in-memory
  command context until a full session reload reconciles it.

This does not implement a password form, global Entra identity-provider logout,
user provisioning, account mutation, ERPNext connection or production secret.
It ends only the current Frappe Site session.

## Pinned framework fact

The repository pins Frappe `version-15` commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`. Its `frappe/auth.py`
`LoginManager.logout()` deletes the current SID, clears Frappe session cookies
and changes the current request to Guest. PA-03 calls that public framework
behavior through the independent NPI app; it does not patch Frappe core.

## Acceptance and fault truth

| Condition | Required result |
|---|---|
| Valid authenticated request and exact `{ "signedOut": true }` private/no-store response | Clear client CSRF state and navigate to `/login` |
| Missing/invalid CSRF, Guest session or non-empty request | Governed non-2xx response; Frappe logout is not called |
| Duplicate click while pending | No duplicate request |
| Network failure, timeout-after-commit, malformed body or missing cache directive | Do not claim success or continued authentication; clear command context and show a reference-bearing unconfirmed-state alert |
| Operator selects **Check session** | Reload the application so bootstrap either restores the authenticated session or routes a confirmed Guest to login |
| Prototype mode | No production session-exit action is offered |

## Changed files to affected checks

| Area | Files | Evidence |
|---|---|---|
| Fixed BFF and Frappe adapter | `apps/npi_core/npi_core/bff.py`, `localization_api.py` | adapter, route, CSRF, Guest, extra-field and runtime tests |
| Closed contract | `contracts/npi-api.openapi.yaml` | contract and reconciliation checks |
| Browser session state | `frontend/src/api/session.ts`, `frontend/src/i18n/runtime.tsx` | client and provider unit tests |
| Industrial shell | `frontend/src/app/app-shell.tsx` | normal, unconfirmed and trilingual App Shell tests |
| Localization | Frappe `zh.csv`, `zh-TW.csv` and generated catalogs | catalog generation and mixed-language audit |
| Runtime probe | `scripts/verify_frappe_runtime.py` | real local Frappe SID/cookie reconciliation |

## Verification evidence

- Exact Node.js `24.18.0` / npm `11.16.0` isolated worktree Gate:
  `scripts/verify.sh` **PASS**.
- Python: **2993/2993 PASS**, including the fixed route, authenticated-user,
  CSRF, exact-empty-request and logout adapter tests.
- Frontend: **1151/1151 PASS**; the focused session/API/App Shell matrix was
  also **105/105 PASS** after the only lint repair.
- Formatting, ESLint, Stylelint, browser boundary and industrial UI audits:
  **PASS**.
- Internationalization: **9329** literal English sources with **100%**
  Simplified Chinese and Traditional Chinese coverage.
- Production build, build budgets, approved brand assets, install-script policy,
  `npm audit` and production-dependency audit: **PASS**, zero known
  vulnerabilities.
- `scripts/verify-frappe-runtime.sh` did not start because the fixed local
  `tmp/frappe-bench` lacks the pinned Frappe application checkout. No runtime
  result is claimed. The verifier changes are covered by the full static and
  unit Gate and remain ready for a disposable local Site or deployment smoke
  validation.

## Rollback

Rollback removes the fixed route, adapter, response schema, browser session-exit
state, shell action, translations and tests. There is no migration, stored
business data or external production state to reverse.
