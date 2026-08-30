# LaunchFlow–ERPNext Compatibility Gap and Decision Register

Status: **OPEN — PRODUCTION FACTS UNVERIFIED; NO PRODUCT GAP PROVEN**

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
| P8-07F-GAP-001 | Exact production Frappe/ERPNext version | One allowlisted `ERP_VERSION` attempt returned no accepted output | Cannot compare target version with existing contracts/runtime assumptions | ERP platform owner corrects the external read-only access condition within the frozen command and least-privilege boundary; then rerun the same operation once under a future task-scoped attempt | `NO_CHANGE`; no product incompatibility proven |
| P8-07F-GAP-002 | Runtime Site parameter for installed-app inventory | Local runtime parameter absent; `INSTALLED_APPS` was not invoked after the first stop | Installed apps and custom-app set remain unknown | Provide the runtime parameter outside Git only after `ERP_VERSION` succeeds; never record its value | `NO_CHANGE`; no app task authorized |
| P8-07F-GAP-003 | Runtime-only Custom Fields, Property Setters, Scripts, Workflows, roles, permissions, service scopes and Naming Series | Frozen source-only operations cannot prove facts not represented in tracked custom-app source | These areas remain `UNVERIFIED` even if source collection later succeeds | Use only a separately gated, side-effect-free, operation-specific sanitized metadata source or an owner-supplied evidence bundle; do not use console, SQL, export-fixtures or improvised commands | `NO_CHANGE`; affected production binding remains held |
| P8-07F-GAP-004 | P8-01 through P8-09 production object/method mappings | No accepted production metadata or method evidence | No row can be classified `DIRECT_MATCH` or adjusted | Resume bounded collection only after GAP-001; reconcile each row against the existing design | `NO_CHANGE` pending evidence; P8-08 blocked |

## Decisions

| Decision | Result | Rationale and consequence |
|---|---|---|
| P8-07F-D-001 | Preserve current architecture/contracts | A production access failure is not an incompatibility. No domain, API, event, workflow, object, permission or stack redesign is allowed. |
| P8-07F-D-002 | Stop after the first failed allowlisted operation | The user-approved boundary requires immediate fail-closed behavior. No retry, alias probe, command drift, REST fallback or privilege expansion occurred. |
| P8-07F-D-003 | Hold P8-08 | P8-08 depends on a real target consumer/adapter fact. It cannot activate while required production compatibility evidence is `UNVERIFIED`. |
| P8-07F-D-004 | Keep production mutation out of P8-07F | Any proven ERP or LaunchFlow adjustment becomes a separate smallest atomic task with its own Gate and rollback/forward-fix. |
| P8-07F-D-005 | Preserve M9-04/M9-05 deferral | Real customer-owned-tool and new-tool pilots are user-approved post-V1.2 work. AT-01/AT-02 controlled non-production UAT remains but cannot be described as a real pilot or 80% real-user use. |
| P8-07F-D-006 | Preserve identity/permission ownership | Entra owns authentication/MFA, the NPI Frappe Site owns session and server-side authorization, and ERPNext owns editable internal-user/role/scope truth. The failed fact read does not alter this approved boundary. |

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
