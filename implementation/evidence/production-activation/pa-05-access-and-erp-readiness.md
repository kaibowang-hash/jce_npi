# PA-05 Access and ERPNext Activation Readiness

Status: **LOCAL LEVEL 3 PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-04 (Asia/Bangkok)

## Outcome

The System Manager-only `/administration` workspace now reports the current
LaunchFlow Site's non-secret access and ERPNext activation truth. It does not
present an empty configuration catalog as a ready production system.

The bounded server classification covers:

- exact Microsoft Entra/Office 365 Social Login enablement without reading a
  client ID or secret;
- global and provider-level self-signup denial;
- the independent P9-04 authorization ingress and enforcement switches;
- the closed role allowlist and projection validity-window policy shape;
- the approved ERPNext ownership of enabled users, NPI roles and scopes;
- the same-Site Frappe `/app` support administration path;
- explicit incomplete states for idempotent local User provisioning, the
  operation-specific ERPNext authorization sender and ERPNext business
  adapters.

The last three states are deliberately not inferred from HTTP availability or
operator laptop configuration. The existing authorization projection rejects a
target that is not already an enabled Frappe System User, so user provisioning
is a proved production-activation gap rather than an assumed capability.

## Safety and non-scope

- No production LaunchFlow or ERPNext Site was contacted or modified.
- No user, role, permission, Social Login Key, Site switch or adapter was
  created, edited or enabled.
- No credential, endpoint, provider metadata value, identity or business row is
  returned or committed.
- The page remains read-only and available only after the existing internal
  System Manager check. It adds no generic DocType or field writer.
- Entra remains authentication/MFA authority, Frappe remains session authority,
  and ERPNext remains editable user/role/scope authority. LaunchFlow does not
  add a permission-management UI.

## Changed files to affected checks

| Area | Files | Evidence |
|---|---|---|
| Server observation | `reporting/frappe_repository.py` | System Manager denial, exact enabled/disabled/configured classification, provider signup override and non-secret field selection |
| API contract | `contracts/npi-api.openapi.yaml`, `reporting-data-source.ts` | closed activation object, exact enums/constants and malformed response rejection |
| Administration UI | `portfolio-page.tsx` | compact authority/state/action table and same-Site Frappe support link |
| Internationalization | Frappe CSVs, terminology allowlist and generated catalogs | complete English/Simplified/Traditional sources with retained product names only |
| Operator procedure | `docs/GO_LIVE_AND_RECOVERY_RUNBOOK.md` | ownership, activation order, stop boundary and rollback |
| Browser proof | `production-activation-readiness.spec.ts` plus three Linux baselines | production environment truth, incomplete-state truth, support link, accessibility, overflow and mixed-language checks |

## Verification evidence

- Focused Python reporting API, repository, runtime-verifier, contract and
  domain tests: **34/34
  PASS**.
- Focused frontend reporting contract and Administration component tests:
  **7/7 PASS**.
- Non-visual browser access/readiness/accessibility check: **1/1 PASS**.
- Linux Playwright English/Simplified/Traditional visual matrix: **3/3 PASS**
  without snapshot updates on the confirmation run.
- Internationalization audit: **9365** literal English sources with **100%**
  Simplified Chinese and Traditional Chinese coverage.
- Full isolated exact-toolchain Gate using Node **24.18.0** and npm **11.16.0**:
  **PASS**. It completed **2996/2996** Python tests, **1155/1155** frontend
  tests, generated-artifact checks, type checking, code/format/style/boundary/UI
  lint, production build and build-budget verification.
- Dependency audits: **0 vulnerabilities** for the complete dependency tree and
  **0 vulnerabilities** with development dependencies omitted.
- One pre-Gate contract-test defect was corrected before the final run: the
  P8-03 Item publish schema scan now ends at the adjacent MBOM schema boundary
  instead of scanning unrelated later schemas. The Item/MBOM/reporting contract
  regression set passed **20/20** before the final Gate.

## Rollback and next boundary

Rollback removes the additive read-only response member and Administration
status table. No schema or business-data rollback is required. Existing Site
settings remain unchanged.

The next implementation task may add only the proved idempotent internal-user
provisioning boundary. It must retain disabled self signup, create no password
or MFA truth, accept no generic User writer, preserve ERPNext ownership, require
an authenticated least-privilege service actor, and prove create/exact replay/
disable/stale/conflict/rollback behavior before any production activation.
