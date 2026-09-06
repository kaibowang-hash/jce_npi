# P9-04 Production Security Fact Delta

Recorded: `2026-09-03`

## Accepted provenance

- Collector exact SHA: `76d40c2aed74716943eeefabb1b4162e8ba994f9`.
- Ordinary CI: `33697388327`, exact-SHA PASS after rerunning only the failed
  historical P6-08 loading-state job at the same SHA; no code or test changed.
- Read-only operation: fixed `P9_SECURITY_AUTHORIZATION_METADATA` /
  `security-metadata` through the approved transport boundary.
- Completion time: `2026-09-03T07:07:46+07:00`.
- Redacted source: `JCE_CORE_PRODUCTION_REDACTED`.
- Aggregate sanitized result checksum:
  `sha256:0919d57016166b07899a3a0648ef975755413027e6e2d29606720308df84afb8`.
- Production writes, service actions, identities, permission values, secrets,
  endpoints and business records: zero.

## Facts and compatibility result

| Fact | Accepted sanitized result | Decision | Product consequence |
|---|---|---|---|
| System Users | 28 total, 21 enabled, 7 disabled | `DIRECT_MATCH` for ERP ownership | Consume a full enabled/disabled projection; never provision a default role |
| User Permissions | 14 total; Company 7; Project/Customer/Supplier 0 | Company `CONFIG_OR_MAPPING_ONLY`; other scope kinds `BUSINESS_DECISION_REQUIRED` | Keep exact Project/organization scope enforcement; activation waits for an approved source map |
| Role Profiles | Six standard business profiles; no NPI-specific profile | `CONFIG_OR_MAPPING_ONLY` first | Use a closed NPI role allowlist; any ERP role/profile addition is a separate task |
| Social Login | Office 365 and Wework enabled | Office 365 `DIRECT_MATCH` | Reuse supported Frappe federation; no custom password/MFA |
| Self signup | Disabled, storage shape `DIGIT_STRING` | `DIRECT_MATCH`, `NO_CHANGE` | Unknown/unprojected principal still fails closed |
| NPI authorization sender/API | Not proved in accepted source/runtime inventory | Concrete minimal seam gap | Add only a default-disabled NPI ingress/projection now; ERP sender remains separate |

## Frozen local product adjustment

The accepted smallest LaunchFlow adjustment is one independent
`NPI Authorization Projection` read-only support DocType, one fixed
`replace_user_authorization` schema-v1 endpoint, a controlled service write
capability, and an optional principal resolver enabled only by an exact Site
switch. Events are complete replacements and bind source/target systems,
source version, target user mapping, validity window, roles, Project and
Company/Customer/Supplier scopes, event/payload/projection hashes, request and
trace. The raw source subject is accepted only at ingress and persisted only
as SHA-256.

Existing domain authorization remains unchanged. No Frappe User role is
mutated. Missing, disabled, expired, unmapped, hash-invalid, out-of-order or
unapproved projections fail closed. The route and resolver are both disabled
by default so rollout can seed and validate before enforcement.

## Verification and rollback

Focused tests cover closed schema/hash parsing; role/scope bounds; service
actor and target-user checks; create/replace/disable; exact replay;
stale/conflict/tamper; organization denial; route default-disable; unique-race
retry; API error rollback; immutable metadata; translations and no generic
writer. The cumulative disposable-Frappe verifier migrates twice, persists one
projection, proves exact replay and projected principal behavior, rejects a
stale event, applies complete revocation, verifies audit cardinality, and rolls
back every fixture row.

Rollback disables the two Site switches, reverts only the additive P9-04
route/projection/resolver files and uses a reviewed forward fix for already
accepted audit evidence. It does not grant local fallback access, alter the
approved authority split or require any production ERPNext change.

## Remaining activation holds

Stable Entra-to-Frappe identity key, exact NPI role names, Project/Customer/
Supplier source fields, least-privilege service actor, delivery/revocation
SLA, reconciliation cadence, version-equivalent Sandbox and controlled UAT
remain required. No unresolved hold is treated as success, and no ERPNext
production customization is authorized by this task.
