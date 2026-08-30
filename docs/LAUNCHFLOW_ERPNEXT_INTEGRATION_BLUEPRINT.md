# LaunchFlow–ERPNext Compatibility Blueprint

Status: **BASELINE RECORDED — PRODUCTION SIDE UNVERIFIED**

Date: `2026-08-30`

## Reading this blueprint

This document records how LaunchFlow already integrates with ERPNext and the
minimum facts needed to decide whether the production installation matches.
It is not a redesign, implementation plan or production-change authorization.

Because the first allowlisted production operation produced no accepted
output, every ERP-actual column is `UNVERIFIED`. The closed compatibility
vocabulary has no evidence-free match state, so each row is
`BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY` with `NO_CHANGE` pending
evidence. This does not assert a business conflict. No adjustment task may be
created until one concrete incompatibility is proven.

## P8-01 through P8-09 compatibility matrix

| Capability / requirement | Existing LaunchFlow design and code | Objects, owners and direction | Production ERP fact | Compatibility / minimal difference | Reliability, security and tests | Rollout, rollback and evidence |
|---|---|---|---|---|---|---|
| P8-01 read-only ERP projections / `INT-001`, `INT-006`, `INT-010` | `apps/npi_integration/.../projections` and `npi.erp-projection.v1` retain immutable observation/head truth for Customer, Supplier, Item, tooling procurement cost, Project cost, formal quality and Tool Asset status. | ERP owns source business fields; NPI projection service owns append-only observation/head. `ERPNEXT_TO_NPI`, Project/consumer scoped; source version/time/payload/hash preserved. | `UNVERIFIED`: versions, source methods, exact fields, filters, permissions and freshness tokens unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. No mapping or adapter adjustment proven. | Actor-bound service access; Project containment; same unavailable result for absent/foreign; order/conflict/freshness/replay tests; unavailable never means pass. | Keep production profile disabled. Validate exact source mappings in Sandbox/UAT, monitor trace/freshness/conflict; rollback disables reader, history stays immutable. Evidence: P8-01 contracts/code/Level3 plus inventory GAP-001/004. |
| P8-02 signed ERP source ingress / `INT-002`, `FR-PM-002` | Fixed POST `/api/npi/v1/integration/erpnext/project-source-events`; raw-body signature verification, Inbox-first durable landing and at most one NPI Project draft from submitted Quotation or Sales Order. | ERP owns submitted source document/event; NPI inbound service owns authenticated receipt, binding and Project-draft seed. `ERPNEXT_TO_NPI`; schema v1, trace/event/source/hash and idempotency fixed. | `UNVERIFIED`: production webhook/API, event names, signing/version contract, Quotation/Sales Order states, service scope unknown. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. | Invalid/stale/future signature, duplicate key, duplicate/reordered/conflicting event, timeout/restart, cross-Project and permission tests; replay uses original identity. | Enable only an operation-specific production profile after Sandbox/UAT and key-rotation evidence; monitor Inbox/quarantine/trace; rollback disables ingress without deleting evidence. P8-02 Level3 and GAP-004. |
| P8-03 released Item publish / `INT-003` | `item_publish` implements `publish_released_item` schema v1 over exact released source/hash, expected target version, actor, trace and idempotency; durable request/Outbox/attempt/result/mapping truth. | NPI owns engineering release snapshot and request; ERP owns formal Item code, stock UOM, group/naming and target version. `NPI_TO_ERPNEXT` command with authenticated target result back. | `UNVERIFIED`: production Item fields, naming/UOM/group rules, operation method/schema and permission unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. | Exact source/mapping/CAS, duplicate, stale/conflict, 4xx/429/5xx, partial, timeout-after-commit uncertainty/no redispatch, replay/reconcile and permission tests. | Default-disabled adapter; configure only exact mapping if facts match. Sandbox/UAT before enable; monitor attempt/result/mapping; rollback disables profile, preserves history. P8-03 Level3 and GAP-004. |
| P8-04 released MBOM publish / `INT-004` | `mbom_publish` implements `publish_released_mbom` schema v2 over exact released EBOM topology and authenticated Item mappings, with immutable node/result truth and submitted-BOM protection. | NPI owns released topology/request; ERP owns formal BOM ID, target version, submission, routing and manufacturing lifecycle. `NPI_TO_ERPNEXT` with per-node target confirmation. | `UNVERIFIED`: BOM/MBOM fields, routing/submission lifecycle, operation method, mapping and service permission unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. | Missing Item mapping, topology drift, duplicate/stale/conflict, partial node result, submitted conflict, timeout-after-commit, uncertain no-redispatch, replay/reconcile and rollback tests. | Enable only after P8-03 mappings and Sandbox/UAT. Monitor per-node outcomes and submitted conflicts; rollback disables profile, never overwrites submitted BOM. P8-04 Level3 and GAP-004. |
| P8-05 Tool Asset create/update and projection / `INT-005`, `FR-TL-011..016` | `tool_asset_request` implements fixed create/update operation kinds under `create_or_update_tool_asset`; one physical Tooling Set maps to zero-or-one Asset; P8-01 is the only status/location/maintenance projection owner. | NPI owns immutable tooling/acceptance request evidence; ERP owns Asset ID, state, location, shot count, maintenance/movement/repair/spares. Bidirectional operation-specific boundary, never dual-master. | `UNVERIFIED`: Asset fields/lifecycle/location/maintenance methods, approval and permission unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. | Exact physical-set/mapping/version locks, duplicate/conflict, partial/uncertain result, timeout-after-commit, stale projection, permission, replay/reconcile and rollback tests. | Separate create/update scopes, Sandbox/UAT and business approval required. Monitor mapping/result/projection drift; rollback disables operations and reader. P8-05 Level3 and GAP-004. |
| P8-06 formal Quality/NCR/CAPA reference / `INT-007`, `FR-TR-006`, `FR-NP-006` | `quality_link` implements local `link_observed_formal_quality_reference` schema v1 to an exact current P8-01 observation. It does not write or interpret formal ERP quality truth. | ERP owns Quality Inspection/NCR/CAPA identity, status/result, approval and lifecycle; NPI owns immutable Project/Trial/readiness/report reference and current/drifted/unavailable view. `ERPNEXT_TO_NPI` reference only. | `UNVERIFIED`: exact DocTypes, identifiers, status/result codes, lifecycle, permissions and policy unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. No quality pass/Gate mapping may be inferred. | Exact Project/source/head locks, replay/conflict/tamper, permission-safe not-found, rollback, stale/current/unavailable and raw-code tests. | No production write to roll back. Validate mapping and owner-approved raw-code policy separately; monitor head drift. P8-06 Level3 and GAP-004. |
| P8-07 operation center, logical DLQ, replay and reconciliation / `FR-RP-009`, `UX-016`, `NFR-INT-001` | `integration_operations` schema/API v1 derives logical DLQ from five owning operations: receive Project submission, publish Item, publish MBOM, create Tool Asset, update Tool Asset. Replay is only exact retryable/non-uncertain; reconciliation is intent/observation and never target-success assertion. | Each P8-02..05 service owns immutable execution truth; P8-07 owns Project-scoped reads/action receipts/audit. Direction follows owning operation; actor/trace/idempotency/source/hash retained. | `UNVERIFIED`: target retry/error/rate-limit semantics, service permissions, operational support and reconciliation readers unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. | Cross-Project denial, exact action eligibility, uncertain no-redispatch, duplicate/restart/partial/stale/conflict, trusted observation, audit and permission tests. | Production execution stays disabled. Sandbox/UAT verifies target semantics; monitor queues/claims/attempts/logical DLQ; rollback disables action profile, history retained. P8-07 Level3 and GAP-004. |
| P8-08 Released Trial Summary read-only seam / `FR-INT-015` | Reuse the immutable NPI Released Trial Summary (`npi.released_trial_summary.v1`, presentation/redaction companions) and prepare only a read-only adapter/projection seam with explicit unavailable state. Exact external event, payload/consumer mapping and receipt remain held. | NPI owns released summary and redaction; any ERP consumer owns its accepted target reference only. Proposed `NPI_TO_ERPNEXT_SUMMARY`, versioned and idempotent, with trace/hash and no browser direct access. | `UNVERIFIED`: production consumer, method, fields, permission, receipt and retention unavailable. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`; P8-08 remains blocked and inactive. | Required future tests: normal, unavailable, permission, duplicate, stale/conflict, redaction, timeout-after-commit, partial receipt, retry/replay/reconcile and rollback. | Do not activate before production facts and Sandbox/UAT. Rollback is profile disable with immutable source retained. Evidence: phase-8 anchor, existing released-summary code/contracts, GAP-001/004. |
| P8-09 JCE Core display identity / `FR-BR-002` | Show approved `JCE Core` text and exact `docs/Brand Asset/Core.png` only in ERP/JCE display contexts; internal API/event/schema code remains `ERPNEXT`. | Display identity is presentation-only; technical source/target ownership and codes do not change. No data direction or business writer is introduced. | `UNVERIFIED`: production surfaces were not inspected; no production branding change is assumed. | `BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY`; `NO_CHANGE`. | Exact asset/hash/usage, accessible name, scale/light/dark and EN/zh/zh-TW tests; scans reject technical-code renaming or substitute marks. | Rollback removes only the display adapter. No core/ERP data change. Evidence: FR-BR-002 anchor, ADR-012, GAP-004. |

## Common interface and operating boundary

- Browser → NPI BFF only. NPI → ERP uses fixed operation-specific adapters;
  no generic DocType writer or direct database access.
- Every command/query binds an explicit version, actor/service authority,
  Project/tenant scope, trace/request ID, idempotency identity and source/hash
  or expected target version.
- Webhook ingress lands in Inbox after exact raw-body authentication. Commands
  commit request plus Outbox before enqueue. Attempts/results/mappings remain
  immutable; timeout after crossing the adapter boundary is uncertain and not
  automatically redispatched. Replay and reconciliation retain original
  authority and evidence.
- Permission and audit are server enforced. Entra owns authentication/MFA, the
  NPI Frappe Site owns session/domain authorization, and ERPNext owns editable
  internal-user/role/scope truth.
- Rollout order is production facts → compatibility decision → separately
  approved smallest adjustment if any → version-equivalent Sandbox → AT-01/
  AT-02 controlled non-production UAT → profile enablement and monitoring.
  M9-04/M9-05 real pilots are not V1.2 evidence.

## Final release reconciliation

Before implementation/release closeout, repeat the complete read-only
comparison. Each row must be `STILL_MATCHES`, `PRODUCTION_DRIFT`,
`LAUNCHFLOW_DRIFT`, `BOTH_DRIFTED` or `UNVERIFIED`, with accepted evidence,
checksum, owner, impact and remediation. Required `UNVERIFIED` or unresolved
drift blocks `IMPLEMENTATION_COMPLETE` and production-ready. The same
minimal-adjustment hierarchy applies; the review cannot authorize or perform a
production change.
