# PA-01 Production Login Entry Validation

Status: **LOCAL TASK GATE PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-03 (Asia/Bangkok)

## Authorization and scope

The user explicitly authorized production-readiness development after the V1.2
technical implementation. This first atomic task changes only the initial
browser authentication boundary:

- an unauthenticated production session bootstrap redirects to the existing
  Frappe login route;
- the login request carries a same-site `redirect-to` value so successful
  Frappe/Entra authentication returns to the original LaunchFlow route;
- development/prototype fallback behavior and every authenticated session
  response remain unchanged.

This task does not add a password form, identity provider, user-management UI,
role editor, ERP service actor, production adapter, credential, migration or
production write. Entra remains the authentication/MFA authority, Frappe owns
the LaunchFlow session, and ERPNext remains authoritative for approved internal
user/role/scope projections.

## Acceptance and fault truth

| Condition | Result |
|---|---|
| Production bootstrap returns a valid `401` Problem Details response | Browser navigates to `/login?redirect-to=...` |
| Original route contains query or fragment state | It is encoded inside the same-site return value |
| A synthetic or malformed pathname starts with `//` | Return target is reduced to `/`; no cross-origin target is emitted |
| Browser is already on `/login` | No redirect loop is created |
| Bootstrap times out, is unreachable or returns an invalid response | Existing fail-closed unavailable state and retry remain active |
| Development or explicitly approved prototype mode is active | Existing prototype localization fallback remains active |
| Authenticated bootstrap succeeds | Existing user, CSRF, locale and navigation-preference initialization is unchanged |

The route name and parameter are bound to the repository-pinned Frappe v15
implementation in `frappe/www/login.py`, including Frappe's server-side redirect
sanitization. No browser-direct ERPNext request is introduced.

## Changed files to affected checks

| Changed file | Affected behavior | Evidence |
|---|---|---|
| `frontend/src/i18n/runtime.tsx` | Initial production session bootstrap and login navigation | focused Vitest plus production-build browser probe |
| `frontend/tests/unit/i18n.test.tsx` | Same-site return URL, open-redirect guard and exact 401 redirect | 25/25 focused tests; included in 1,142/1,142 frontend tests |

There is no user-visible copy, styling, schema, backend, permission, database or
migration change. Therefore no translation catalog or visual baseline changes.

## Verification

Verification used an isolated detached worktree at base `cb314e45` so the
user's unrelated dirty documentation, local screenshots and untracked public
asset were neither staged nor modified.

- Focused frontend test: `25/25` PASS.
- Backend session/localization contract: `42/42` PASS, including Guest `401`.
- Full repository verification: `2,989/2,989` Python tests PASS; security scans,
  prototype governance, P0 visual governance and V1.2 reconciliation PASS.
- Full frontend verification with exact Node `v24.18.0` and npm `11.16.0`:
  `1,142/1,142` tests PASS; statements `80.07%`, branches `79.50%`, functions
  `82.11%`, lines `82.66%`; typecheck, ESLint, Prettier, Stylelint, boundaries,
  industrial UI audit, three-language coverage, production build, asset budget,
  brand audit, install-script allowlist and both npm audits PASS.
- Production-build Chromium probe: a governed Guest `401` changed
  `/projects/PJ-26018?tab=gates` to the Frappe login route with the exact encoded
  same-site return target; PASS.
- `git diff --check`: PASS for the task files.

The current shared worktree's aggregate `npm run verify` still sees the user's
pre-existing untracked `frontend/public/images/npi-one-project-management-sketch.png`
and correctly rejects it as an unapproved production static asset. The isolated
task Gate proves this task without deleting or accepting that unrelated asset.

## Release-gate decision

**PASS for the PA-01 code checkpoint.** The change is local, reversible,
same-origin, fail-closed, migration-free and uses the already approved
Frappe/Entra session boundary. No rendered UI changed, so new trilingual visual
snapshots are not applicable. This PASS does not authorize deployment or imply
that Entra, users, ERP permissions or ERP production adapters are configured.

## Rollback and next atomic tasks

Rollback removes only the login URL helper, the initial-bootstrap redirect
branch and their tests. No database or external-state rollback is needed.

The next production-readiness tasks remain separate:

1. configure and prove the Entra Social Login Key, disable unintended local
   signup/login paths and retain one recoverable administrator path;
2. activate the existing default-disabled P9-04 authorization projection only
   after the stable identity map, approved roles/scopes, service actor and
   Sandbox/UAT evidence exist;
3. activate ERP integration one operation family at a time with an independent
   ERPNext custom app, operation-specific APIs/events, least privilege,
   idempotency, retry, reconciliation, monitoring and rollback evidence.

Missing production values must be configured privately on the target Site and
must never be committed to Git.
