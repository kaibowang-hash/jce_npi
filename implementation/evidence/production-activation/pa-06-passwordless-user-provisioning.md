# PA-06 Passwordless Internal-User Provisioning

Status: **LOCAL LEVEL 3 PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-04 (Asia/Bangkok)

## Outcome

The existing operation-specific ERPNext authorization replacement now owns the
minimum local Frappe User lifecycle needed for Microsoft Entra sign-in. One
enabled event for a missing canonical lowercase email identity creates one
Frappe System User with only the technical `Desk User` role. Exact replay is a
no-op after verifying both projection and local-user state. Later full
replacements enable or disable the same User in the same transaction as the
projection and immutable audit.

The API result reports the actual local-user state and disposition. The
System Manager-only production activation page therefore reports LaunchFlow
user provisioning as ready while continuing to report the ERPNext sender as
externally unverified and the ERP business adapters as not implemented.

## Fixed safety boundary

- `targetUserId` is one canonical lowercase email and remains part of the
  existing payload/hash/version contract.
- Creation sets `send_welcome_email=0`, the Frappe no-welcome-mail flag and no
  password. Passwords, MFA factors, provider secrets and session cookies remain
  outside the contract and storage path.
- The only local role created is Frappe's technical `Desk User`; NPI business
  roles and Project/organization scopes remain the ERPNext-owned read-only
  projection and replace effective grants only when enforcement is enabled.
- Existing Website Users, System Managers, `Administrator`, `Guest` and the
  authenticated service actor cannot be promoted or taken over.
- Missing disabled users remain absent. Existing managed System Users are
  enabled or disabled without deleting history or silently changing roles.
- User and projection writes require the same actor/target-bound context
  capability. There is no generic User or DocType writer.
- Ingress and enforcement remain independently default-disabled. This task
  neither implements the ERPNext sender nor activates any production adapter.

## Verification evidence

- Focused authorization domain/API/repository/metadata/runtime-verifier and
  enforcement suite: **28/28 PASS**.
- Focused authorization plus reporting regression suite: **62/62 PASS**.
- Frontend generated-artifact check, type check, full lint and affected unit
  tests: **PASS**; affected unit tests pass **7/7**.
- Internationalization audit: **9364** literal English sources with **100%**
  Simplified Chinese and Traditional Chinese coverage.
- Non-visual browser accessibility/overflow check: **1/1 PASS**.
- Linux English/Simplified/Traditional visual matrix: **3/3 PASS** on both the
  update and no-update confirmation runs; all three baselines were inspected.
- Pinned Frappe `version-15` commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` was imported from a temporary exact
  checkout into the repository's disposable `npi.localhost` Site. The fixture
  proved passwordless User creation, exact replay, stale rejection, local User
  disable/fail-closed behavior, one projection and two audits, then rolled the
  transaction back. Sanitized evidence checksum:
  `b59907d89016b6af98e46019f49231bd0f2c901e1bf4397246aabd9a91b3824d`.
- Full isolated exact-toolchain Gate: **PASS** with Python **3000/3000**,
  frontend **1155/1155** across **78/78** test files, the i18n audit above,
  production builds and dependency audits reporting **0 vulnerabilities**.

No production LaunchFlow Site, ERPNext Site, AWS resource or external identity
provider was contacted or changed.

## Rollback and next boundary

Rollback keeps both authorization switches disabled, reverts the additive
local-user lifecycle and response fields, and retains accepted projection/audit
history. Do not enable self signup or add local NPI roles as fallback.

The remaining user-access blocker is outside LaunchFlow: a separately reviewed
ERPNext custom-app sender must emit the exact versioned replacement using the
approved identity, role and scope mappings and a least-privilege service actor.
It must pass version-equivalent Sandbox create/replay/disable/stale/lost-event/
timeout-after-commit/reconciliation tests before either production switch is
enabled.
