# P9-04 — Security Hardening and Production Compatibility Plan

Recorded: `2026-09-03`

Status: `FACT-DELTA COLLECTOR — EXACT-SHA ORDINARY CI REQUIRED`

## Outcome and fixed authority

P9-04 covers `NFR-SEC-001`, `NFR-SEC-003` and `INT-012`. It applies the
approved authority split without redesigning the existing security model:
Microsoft Entra owns authentication and MFA, the NPI Frappe Site owns its
session, and ERPNext owns enabled internal users, NPI roles and approved access
scopes. LaunchFlow continues to enforce every role, tenant, Project, object,
file, export and operation boundary server-side.

The current LaunchFlow architecture, OpenAPI/event contracts and P8-01 through
P8-09 implementation are the default-correct baseline. Compatibility decisions
use only `DIRECT_MATCH`, `CONFIG_OR_MAPPING_ONLY`,
`MINOR_LAUNCHFLOW_ADJUSTMENT`, `MINOR_ERPNEXT_CUSTOM_APP_ADJUSTMENT`,
`BUSINESS_DECISION_REQUIRED` or `NOT_APPLICABLE`. No difference evidence means
`DIRECT_MATCH` and `NO_CHANGE`.

## Reused facts and proven delta need

The accepted P8-07F inventory already proves the production Frappe/ERPNext
versions, installed apps, current tracked-worktree status, declarative metadata
families, relevant DocTypes and DocPerm structure. It also proves that no
dedicated P8/P9 operation-specific authorization-projection API or accepted
integration role was found in the inspected custom-app sources.

That inventory intentionally did not retain the exact Role Profile membership,
System User enabled/disabled aggregate, Project/Company/Customer/Supplier User
Permission usage, active Social Login provider metadata or self-signup setting.
Those facts directly affect the approved P9-04 fail-closed behavior and cannot
be guessed. One task-scoped delta is therefore necessary; no version, app,
source, DocType, DocPerm or unrelated metadata is recollected.

## Zero-contact governance transition

This plan, controller transition and collector change make no SSH, Site, ERP,
browser, database or other external connection. Production contact remains
closed until this exact transition commit passes ordinary CI. The ordinary run
ID and exact SHA are mandatory collector inputs and the governed paths must be
clean.

After that PASS, exactly one `security-metadata` invocation may use SSH alias
`JCE-Core`, fixed bench root `frappe-bench` and the privately configured Site.
Transport remains BatchMode, strict host-key, no TTY, no forwarding, one short
connection per read, 30-second command timeout and bounded stdout. The command
has no caller-selected method, DocType, field, filter, path or pagination.

The fixed read set is:

- `Role Profile`: name, profile label and modification timestamp, followed only
  by each returned profile's role names;
- `Social Login Key`: name, provider name, enabled flag and modification
  timestamp only;
- aggregate counts for System Users (total/enabled/disabled) and User
  Permissions (total plus Project, Company, Customer and Supplier scope kinds);
- `Website Settings.disable_signup` only.

The collector expressly excludes User name/email/API keys, User Permission
user/for-value, Social Login client ID/secret, endpoints, tokens, cookies,
business rows and Script bodies. Output is sanitized before stdout and binds
task, timestamp/timezone, redacted source, per-operation checksums and aggregate
checksum. Any permission, version, shape, pagination, count, sensitive-value or
allowlist drift fails closed without fallback or scope expansion.

## Current LaunchFlow audit

The existing request boundary rejects Guest users and preserves Frappe roles,
per-Site tenant identity and external-user classification. Domain repositories
already enforce Project membership/ownership, role, object and file scopes;
integration commands separately require enabled System Users and the dedicated
`NPI API User` role. These controls are reused.

Two possible gaps require the production delta and then a single implementation
decision:

1. the central interactive principal resolver does not itself prove an enabled,
   current ERP-authoritative authorization projection; and
2. the repository has no operation-specific ingress or immutable local
   projection for ERP-owned enabled/role/scope replacement and revocation.

No product fix is authorized by this transition. After the sanitized result is
accepted, P9-04 may implement only the smallest local projection/adapter and
fail-closed checks proven necessary. Any ERPNext endpoint or additive custom-app
change remains a separate task; no production ERPNext mutation is permitted.

## Test, Gate and rollback

Focused tests prove the exact command arrays, sanitized output shape, bounded
pagination/count consistency, secret-field exclusion, exact task/SHA/ordinary
preflight and zero-contact self-check. The transition requires exact-SHA
ordinary CI before the one production read. The later product batch requires
affected security/API/runtime tests, complete Level 2, exact-SHA ordinary CI and
one diagnostics-off Level 3.

Rollback before product work reverts only this plan, controller transition and
collector/test extension to P9-03 product checkpoint
`957d307d26bc93fedb08b03fae25f15d0241e1d7`; no external state exists to undo.
After product work, revert only the independently accepted P9-04 projection and
authorization paths, retain the evidence as invalidated history and forward-fix
without granting fallback access.
