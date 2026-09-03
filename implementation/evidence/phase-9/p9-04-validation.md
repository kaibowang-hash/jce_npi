# P9-04 Authorization Projection Validation

## Decision

P9-04 keeps the approved Microsoft Entra / Frappe / ERPNext authority split
and existing LaunchFlow authorization model. The production fact delta proves
one concrete compatibility gap: ERPNext owns enabled internal-user, role and
approved scope truth, while LaunchFlow had no operation-specific way to accept
and enforce that complete projection. The implemented adjustment is therefore
local, additive, default-disabled and reversible; it is not a security-model
redesign.

## Implemented boundary

- One closed schema-v1 `replace_user_authorization` operation accepts a full
  ERPNext-owned replacement with source version, validity window, target user,
  roles, Project access, Company/Customer/Supplier scopes and event/payload/
  projection hashes.
- One read-only support DocType stores the target mapping and only a SHA-256 of
  the source subject. It never mutates Frappe User roles or stores credentials,
  provider secrets, MFA factors or session cookies.
- The operation requires an enabled System User with the exact integration
  role and a controlled write capability. Unknown fields, unsupported roles,
  invalid targets, stale versions, different same-version payloads and
  malformed hashes fail closed.
- The ingress and principal enforcement have independent exact Site switches
  and are disabled by default. Once deliberately enabled after seeding, the
  projection replaces effective roles/scopes; missing, expired, disabled,
  unmapped or invalid truth rejects the session without a fallback role.
- Existing tenant, Project, object, file, export and operation checks remain
  authoritative. The only new shared primitive is exact Company/Customer/
  Supplier scope authorization.

## Evidence

The P9-04 focused suite passes 24 tests before the final batch. The corrected
batch additionally verifies canonical Project IDs at the principal boundary
and the Frappe Datetime controller shape. Repository verification covers the
full Python suite, OpenAPI/ownership contracts, symmetric `zh`/`zh-TW`
catalogs, current-task scope and reconciliation.

The first exact-SHA ordinary candidate run `33701715690` was not accepted:
all independent repository, secret, visual and E2E lanes passed, while the
frontend lane correctly rejected stale generated React catalogs after the
new Frappe CSV messages were added. The single repair batch regenerates only
the three affected React catalog artifacts, records them in task scope and
adds the catalog freshness check to Level 1. A later exact-SHA ordinary run
must replace, not reinterpret, this failed candidate.

The cumulative disposable local Frappe v15 `--projection-only` gate passes
after a fresh guarded Site rebuild. It proves all retained P5 through P9-03
predecessor migrations, route-disable/recovery and cross-process replay paths,
then proves P9-04 create, exact replay, stale rejection, full disable/revocation,
projected principal resolution, two immutable audits and unconditional fixture
rollback. The P9-04 evidence checksum is
`78b360450bbada55d31853f765f0f15f565165a23ce4a379b1c69cb3721f89c1` and the
runtime reports `productionContact=false`.

This candidate record deliberately does not claim an exact-SHA CI or Level 3
result before those external gates run. The first successor controller
transition must bind the immutable P9-04 product SHA, ordinary run and sole
diagnostics-off Level 3 run before activating P9-05.

## Activation holds

Production activation remains blocked on the approved stable Entra-to-Frappe
identity key, exact NPI role names and role mapping, Project/Customer/Supplier
scope sources, least-privilege service actor and ERP custom-app sender,
delivery/revocation SLA, reconciliation cadence, version-equivalent Sandbox
and controlled UAT. P9-04 neither implements nor authorizes any production
ERPNext change.

## Rollback

Disable both P9-04 Site switches first. Revert the additive route, projection,
resolver, contract and metadata as one product commit; do not restore local
roles as a fallback. Retain accepted audit and fact evidence as invalidated
history and use reviewed forward repair after any external event was accepted.
