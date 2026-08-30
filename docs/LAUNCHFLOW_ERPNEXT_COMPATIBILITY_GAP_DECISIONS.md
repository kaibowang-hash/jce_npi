# LaunchFlow–ERPNext Compatibility Gap and Decision Register

Status: **OPEN — PRODUCTION FACTS PARTIALLY VERIFIED; NO PRODUCT GAP PROVEN**

Date: `2026-08-30`

## Decision baseline

The approved LaunchFlow architecture, data ownership, OpenAPI/event contracts
and P8-01 through P8-09 design/code are the default-correct baseline. P8-07F is
compatibility reconciliation, not redesign or refactoring. The incomplete
production read does not prove an incompatibility and authorizes no adjustment.

Adjustment priority remains: `NO_CHANGE`; configuration/mapping only; one
minimal LaunchFlow adapter/mapping/config change; one minimal additive
operation-specific ERP custom-app change; business decision only for a proven
ownership or workflow conflict.

## Gap register

| ID | Evidence gap | Fact result | Compatibility impact | Required next action | Product action |
|---|---|---|---|---|---|
| P8-07F-GAP-001 | Exact production Frappe/ERPNext version | Resolved fact: Frappe `15.79.0`, ERPNext `15.77.0`; accepted sanitized checksums retained | Version comparison is available, but version alone proves no P8 target binding | Reuse the accepted inventory and perform delta-first verification only when freshness changes | `NO_CHANGE`; no version incompatibility proven |
| P8-07F-GAP-002 | Installed-app inventory | Resolved fact: twenty installed apps and a private-Site subset were checksum-verified; identities remain deliberately redacted | App presence is known without disclosing private identity; capability mapping is still not proved | Reuse anonymous checksums; request identity-specific evidence only through an owner-sanitized bundle when a current task requires it | `NO_CHANGE`; no app task authorized |
| P8-07F-GAP-003 | Runtime-only Custom Fields, Property Setters, Scripts, Workflows, roles, permissions, service scopes and Naming Series | Frozen source-only operations cannot prove facts not represented in tracked custom-app source | These areas remain `UNVERIFIED` even if source collection later succeeds | Use only a separately gated, side-effect-free, operation-specific sanitized metadata source or an owner-supplied evidence bundle; do not use console, SQL, export-fixtures or improvised commands | `NO_CHANGE`; affected production binding remains held |
| P8-07F-GAP-004 | P8-01 through P8-09 production object/method mappings | Bounded clean-app summaries exposed several unrelated APIs but no exact P8 method, field, permission or lifecycle contract | No row can be classified `DIRECT_MATCH` or adjusted | Reconcile only against clean runtime-equivalent source and accepted runtime metadata | `NO_CHANGE` pending evidence; P8-08 blocked |
| P8-07F-GAP-005 | ERPNext and custom-app tracked source drift | ERPNext has one tracked drift; twelve of eighteen custom apps have tracked drift | `git show HEAD` would misrepresent runtime source and could create a false compatibility claim | Supply clean declared worktrees or an owner-sanitized checksummed drift/source bundle; compare version/HEAD/status/path checksums first | `NO_CHANGE`; dirty source is not accepted evidence |
| P8-07F-GAP-006 | Two relevant DocType candidates | Both stopped at sensitive-content preflight; no raw path, source, field or value was emitted | Exact declarative schema remains unknown; weakening the scanner would violate the approved boundary | Supply sanitized owner evidence for only those candidates, or use a separately gated metadata source | `NO_CHANGE`; no field/schema adjustment is authorized |

## Decisions

| Decision | Result | Rationale and consequence |
|---|---|---|
| P8-07F-D-001 | Preserve current architecture/contracts | A production access failure is not an incompatibility. No domain, API, event, workflow, object, permission or stack redesign is allowed. |
| P8-07F-D-002 | Stop each affected branch fail closed | The accepted collector completed only allowlisted bounded operations. It stopped individual source branches on dirty runtime truth and sensitive-content risk, with no alias probe, command drift, REST fallback or privilege expansion. |
| P8-07F-D-003 | Hold P8-08 | P8-08 depends on a real target consumer/adapter fact. It cannot activate while required production compatibility evidence is `UNVERIFIED`. |
| P8-07F-D-004 | Keep production mutation out of P8-07F | Any proven ERP or LaunchFlow adjustment becomes a separate smallest atomic task with its own Gate and rollback/forward-fix. |
| P8-07F-D-005 | Preserve M9-04/M9-05 deferral | Real customer-owned-tool and new-tool pilots are user-approved post-V1.2 work. AT-01/AT-02 controlled non-production UAT remains but cannot be described as a real pilot or 80% real-user use. |
| P8-07F-D-006 | Preserve identity/permission ownership | Entra owns authentication/MFA, the NPI Frappe Site owns session and server-side authorization, and ERPNext owns editable internal-user/role/scope truth. The failed fact read does not alter this approved boundary. |
| P8-07F-D-007 | Do not promote dirty HEAD source | Runtime tracked drift is evidence that committed HEAD is not the complete production source. Compatibility stays unverified until clean or sanitized runtime-equivalent evidence exists. |

## No-change list

- Do not modify ERPNext or Frappe core.
- Do not connect the browser directly to ERPNext.
- Do not add a generic DocType writer or caller-selected method.
- Do not create dual-master fields or silently overwrite an owner system.
- Do not treat Mock, Synthetic, HTTP acceptance or an unverified response as
  target success.
- Do not rename existing contracts, redesign domains/workflows, merge or split
  objects, replace the stack, rewrite permissions or add generalized
  abstractions through this fact task.

## Escalation rule

A future accepted production fact that conflicts with an existing contract,
data owner, API, workflow or architecture stops only the affected
implementation. Record the exact difference, evidence/checksum, impact and
smallest reversible options in an ADR/business decision. Do not silently adapt
or implement a nearby optimization.
