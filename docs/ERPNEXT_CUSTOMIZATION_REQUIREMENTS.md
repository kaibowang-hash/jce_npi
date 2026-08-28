# ERPNext Customization Requirements and Fact Status

Status: **GOVERNED REQUIREMENTS BASELINE — PRODUCTION FACTS NOT COLLECTED**

Date: `2026-08-28`

## Purpose and authority

This document states what must be known, decided, tested and evidenced before
NPI One can rely on an ERPNext customization. It does not claim that ERPNext
must be modified. It does not describe the current production site because no
production fact collection has occurred.

`implementation/REQUIRED_INPUTS.md` remains the sole request for external
facts. Repository contracts describe the NPI One boundary, not the actual
production ERPNext implementation. Screenshots, sample values, local fixtures,
Mock and Synthetic results are never production facts.

Production read-only fact checking is
`QUEUED_NOT_EFFECTIVE`. Connection status is
`PROHIBITED_PENDING_RULE_CHANGE_AND_GATE`. Current `AGENTS.md` and the
autopilot controller prohibit production contact.

No SSH action (including configuration-only inspection), ERP connector or
Site command is authorized by this baseline. It records requirements only.

## Classification and evidence axes

Every register row uses one primary classification:

- **Required** — evidence or an owner decision is required for the named V1.2
  obligation. This does not require an ERP customization.
- **Optional** — a separately approved extension may use it; V1.2 cannot rely
  on it by default.
- **Already Present** — the cited repository-side NPI contract or foundation
  exists. This never asserts that a matching ERP customization exists.
- **Not Required** — the architecture explicitly does not need or permit it.
- **Blocked Pending Fact** — whether a production ERP field, method, schema or
  customization exists cannot be decided from repository evidence.

The independent fact-evidence status is one of:

- `REPOSITORY_CONFIRMED`
- `EXTERNAL_EVIDENCE_REQUIRED`
- `OWNER_APPROVAL_REQUIRED`
- `PROHIBITED_PENDING_RULE_CHANGE_AND_GATE`

No row may move to accepted production fact without a dated, owner-identified,
sanitized provenance record and checksum.

## Verified repository baseline

- Formal Customer, Supplier, Item, MBOM, procurement, stock, manufacturing,
  Quality Inspection/NCR/CAPA, Asset/Maintenance and formal change truth remain
  ERPNext-owned under `contracts/data-ownership.yaml`.
- The browser calls only NPI One BFF/domain APIs. Cross-database access and
  unrestricted generic DocType writers are not required and are prohibited.
- `contracts/npi-api.openapi.yaml` and
  `contracts/integration-event.schema.json` contain operation-specific NPI
  contracts for bounded project ingress, read-only projections, Item, MBOM,
  Tool Asset and formal-quality foundations. They do not prove production ERP
  methods, fields or mappings.
- Execution approval, request, Outbox/Inbox, attempt, result, uncertainty,
  mapping, replay and reconciliation are distinct truths. HTTP acceptance,
  Mock or Synthetic success cannot become formal ERP success.
- Existing P8-01 through P8-06 evidence is network-free. Production versions,
  installed apps, topology and customizations remain unknown.

## Customization and fact register

Each item binds requirements, NPI ownership/contract, ERP owner, rationale,
exact ERP field/method/schema status, permission, migration, test,
go-live/rollback and evidence. `Blocked Pending Fact` means the exact identifier
is intentionally absent rather than guessed.

### Platform, apps and extension inventory

| Item | Classification | Fact status | Requirement IDs | NPI contract / ownership | ERP owner | Exact field, method or schema | Permission | Migration and compatibility | Test / go-live / rollback | Rationale and evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Runtime versions, installed apps and topology | Required | `EXTERNAL_EVIDENCE_REQUIRED` | NFR-INT-001, INT-001..007, INT-010 | Repository pins and local disposable runtime only | ERP platform owner | Blocked Pending Fact — exact production versions, apps, database, storage, locale and topology are unknown | Read-only inventory must be least privilege | Compatibility matrix and supported upgrade path required; no migration is authorized | Validate sanitized inventory and provenance before Sandbox/UAT; rollback is refusal to activate | `REQUIRED_INPUTS.md` section 1; repository facts explicitly say unknown |
| Independent custom app and hooks inventory | Required | `EXTERNAL_EVIDENCE_REQUIRED` | NFR-INT-001, INT-001..007 | NPI extensions must remain in independent apps; no core patch | ERP platform owner | Blocked Pending Fact — app names, hooks, overrides, fixtures, patches, jobs and whitelisted methods are unknown | App/source export only; no mutation | Each accepted extension needs version, dependency, patch/backfill and uninstall/forward-fix analysis | Static source review, install/upgrade in approved Sandbox, rollback proof before activation | Core changes are prohibited; existence of production custom apps is unknown |
| Frappe/ERPNext core patch | Not Required | `REPOSITORY_CONFIRMED` | ARCH-003, NFR-INT-001 | Public APIs, hooks and independent NPI apps only | ERP platform owner | No core symbol or patch is authorized | None | No core migration | Security scan must reject core patch; rollback is removal of any proposed core diff | `AGENTS.md` and `frappe-safe-change` boundary |

### Metadata, workflow and permissions

| Item | Classification | Fact status | Requirement IDs | NPI contract / ownership | ERP owner | Exact field, method or schema | Permission | Migration and compatibility | Test / go-live / rollback | Rationale and evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| DocTypes, Custom Fields and Property Setters | Blocked Pending Fact | `EXTERNAL_EVIDENCE_REQUIRED` | FR-PM-002, FR-DS-013, FR-TL-011..016, FR-TR-006, FR-NP-006 | Ownership objects and OpenAPI schemas define NPI concepts only | ERP business-object owners | Blocked Pending Fact — exact production DocTypes, fields, types, options, mandatory rules and indexes are unknown | Export metadata without record contents | Additive/rename/drop/backfill and version compatibility must be decided per accepted field; no change is pre-authorized | Metadata diff, zero-row migration, representative Sandbox lifecycle, forward-fix/rollback | A matching NPI property name does not prove an ERP field |
| Workflows, states, actions and naming series | Blocked Pending Fact | `OWNER_APPROVAL_REQUIRED` | FR-PM-002, FR-DS-013, FR-TL-011..016, FR-TR-006, FR-NP-006 | NPI engineering approval remains separate from ERP execution approval | ERP process owners | Blocked Pending Fact — exact workflow/state/action/naming identifiers are unknown | Named business owner plus segregated service permission | Historical records and submitted-document compatibility required | State-transition matrix, rejection/reopen tests, forward-only recovery; activation withheld on mismatch | Repository status names must not be mapped by similarity |
| Roles, DocPerm, User Permissions, sharing and service users | Required | `EXTERNAL_EVIDENCE_REQUIRED` | NFR-INT-001, INT-001..007, INT-010 | Actor, Project, tenant, permission and trace are server enforced | ERP security owner | Blocked Pending Fact — exact roles, service principals and scopes are unknown | Least privilege, operation split, non-Guest/non-Administrator, no broad fallback | Permission changes require reviewed additive plan and revocation path | Positive/negative matrix, cross-tenant denial, expired/disabled principal, audit; revoke on rollback | NPI roles do not imply ERP roles |

### Operation APIs, events and reliability

| Item | Classification | Fact status | Requirement IDs | NPI contract / ownership | ERP owner | Exact field, method or schema | Permission | Migration and compatibility | Test / go-live / rollback | Rationale and evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Operation-specific commands | Blocked Pending Fact | `EXTERNAL_EVIDENCE_REQUIRED` | INT-003, INT-004, INT-005, INT-007 | NPI request identity, source/version/hash, actor, trace, expected target version and result truth | ERP operation owner | Blocked Pending Fact — exact production method names and request/response schemas are unknown | Separate least-privilege authority per operation; no caller-selected method | Versioned additive contract and compatibility window required | Contract, permission, validation, duplicate, stale, partial and timeout-after-commit tests; disable profile to rollback | Generic DocType write is Not Required and prohibited |
| Read-only projections and reconciliation readers | Required | `EXTERNAL_EVIDENCE_REQUIRED` | INT-001, INT-006, INT-007, INT-010 | P8-01 immutable observation/head order/freshness and downstream read-only consumers | ERP data owners | Blocked Pending Fact — exact source methods, fields, filters, order and version tokens are unknown | Project/tenant-scoped service read only | Mapping version and stale/unavailable behavior required; no backfill until approved | Current/drifted/unavailable, reorder, pagination, permission and source-removal tests; disable reader on rollback | Unavailable is never pass and reconciliation never silently wins |
| Webhooks, signatures and Inbox landing | Blocked Pending Fact | `EXTERNAL_EVIDENCE_REQUIRED` | INT-002, NFR-INT-001 | Raw-body verification, Inbox-first durable landing, event/version replay protection | ERP integration owner | Blocked Pending Fact — event types, versions, signing scheme and delivery contract are unknown | Dedicated sender identity and allowlisted event types | Key rotation and version coexistence plan required | Invalid/old/future signature, duplicate/reordered/conflict, restart and quarantine tests; disable ingress on rollback | No webhook is assumed to exist |
| Idempotency, retry, DLQ, replay and reconciliation | Already Present | `REPOSITORY_CONFIRMED` | FR-RP-009, NFR-INT-001, INT-002..007 | NPI operation-specific foundations preserve request/event identity and uncertain no-redispatch | ERP operation owners retain target truth | Production target semantics are Blocked Pending Fact | Replay requires original authority and immutable identity | No historical rewrite; forward-only repair | 429, 5xx, business 4xx, partial, expired credential, stale mapping, restart and timeout-after-commit; rollback disables dispatch, never deletes history | Technical foundations exist; P8-07 operational product remains unauthorized |

### Master data, capacity, files and security

| Item | Classification | Fact status | Requirement IDs | NPI contract / ownership | ERP owner | Exact field, method or schema | Permission | Migration and compatibility | Test / go-live / rollback | Rationale and evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Company, Site, tenant, Customer, Supplier, Item, UOM, currency and naming mapping | Blocked Pending Fact | `OWNER_APPROVAL_REQUIRED` | FR-PM-002, FR-DS-013, FR-TL-011..016 | Stable NPI identities and explicit mapping expectations | ERP master-data owners | Blocked Pending Fact — authoritative company/site codes, series, UOM and mapping keys are unknown | Scoped service read; writes only through separately approved operation | Mapping version, collision, rename and historical-identity plan required | Missing/duplicate/stale mapping and UOM/precision tests; disable operation and retain mapping history on rollback | Sample codes are not authoritative |
| Indexes, capacity, locks and transaction limits | Required | `EXTERNAL_EVIDENCE_REQUIRED` | NFR-INT-001, FR-RP-009 | NPI bounded paging, claims, CAS and transaction ordering | ERP database/platform owner | Blocked Pending Fact — production indexes, lock behavior, limits and supported query plans are unknown | Observation only; no database access for operators | Any index proposal requires DBA evidence and independent migration/rollback approval | Explain-plan/capacity/lock tests in approved non-production environment; no production DDL in this task | Local performance cannot prove production capacity |
| Files, attachments and controlled references | Blocked Pending Fact | `OWNER_APPROVAL_REQUIRED` | FR-DS-013, FR-TL-011..016, FR-NP-006 | NPI private immutable evidence and controlled references | ERP/DMS/file owners | Blocked Pending Fact — storage, classification, link, retention and scanner contracts are unknown | Short-lived authorized access; no raw private URL | Retention, checksum, reference-version and orphan handling required | MIME/size/scanner/permission/expiry/checksum tests; revoke delivery and retain audit on rollback | File bytes must not be copied or inferred without approved ownership |
| Secrets, endpoint allowlist and audit | Required | `PROHIBITED_PENDING_RULE_CHANGE_AND_GATE` | NFR-INT-001, INT-001..007, INT-010 | NPI records actor/service identity and trace; browser holds no ERP secret | ERP security owner | No endpoint, host, user, key or credential is recorded here | Secret manager, operation-specific least privilege, outbound allowlist | Rotation/revocation and audit-retention plan required | Expired/revoked principal, allowlist denial, redaction and audit completeness; rollback revokes principal/profile | Production values are prohibited from repository evidence |

### Delivery, migration and operations

| Item | Classification | Fact status | Requirement IDs | NPI contract / ownership | ERP owner | Exact field, method or schema | Permission | Migration and compatibility | Test / go-live / rollback | Rationale and evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Migration, backfill and compatibility package | Required | `OWNER_APPROVAL_REQUIRED` | NFR-INT-001, INT-001..007 | Additive guarded NPI migrations; immutable history; explicit mapping versions | ERP app/data owners | Blocked Pending Fact — production starting schema and row population are unknown | Separate migration authority; not a runtime service permission | Dry-run, zero-row, representative-row, restart, downgrade/forward-fix and checksum plan required | Approved Sandbox twice, backup/restore evidence, reconciliation before go-live; rollback or forward-fix chosen explicitly | No migration/backfill is authorized by this document |
| Sandbox and business UAT | Required | `EXTERNAL_EVIDENCE_REQUIRED` | FR-PM-002, FR-DS-013, FR-TL-011..016, FR-TR-006, FR-NP-006, NFR-INT-001 | Default-disabled profiles and truthful Mock/Synthetic evidence | ERP owner plus named business owners | Blocked Pending Fact — authenticated Sandbox contract and sanitized representative data are absent | Dedicated Sandbox principal, never production fallback | Version-equivalent environment and reset plan required | Both project types, success/fault/replay/reconcile, permissions and signed UAT; rollback disables profile | Network-free runtime is not Sandbox or UAT evidence |
| Deployment, monitoring and support | Required | `OWNER_APPROVAL_REQUIRED` | NFR-INT-001, FR-RP-009 | Explicit profiles, health, trace-safe errors and visible operation truth | ERP platform/support owners | Blocked Pending Fact — deployment unit, health source, alerts, support ownership and SLO are unknown | Deployment and runtime identities separated | Rollout order, compatibility window, alert routing and support handoff required | Preflight, canary where approved, health/metrics/log redaction, queue/DLQ alerts; disable profile and forward-fix | No restart, reload or scheduler action is authorized here |
| Optional future ERP extensions | Optional | `OWNER_APPROVAL_REQUIRED` | INT-008, INT-009, INT-011..014 | Later change/file/summary/mobile extensions remain scoped holds | Relevant ERP business owners | Blocked Pending Fact | No authority until separate requirement/controller | Separate ADR, contract, migration and release plan | Independent tests/Gate; removal without rewriting V1.2 history | Must not be bundled into V1.2 activation |

## Read-only fact-collection activation Gate

The current request is queued only. Before any connection, a separate approved
higher-priority change must amend both `AGENTS.md` and the controller and pass
its own Gate. Its frozen plan must define all of the following without placing
secret values in the repository:

1. An exact read-only allowlist reviewed against the target version.
2. A least-privilege principal with no Administrator equivalence.
3. Non-interactive BatchMode, no TTY, no port forwarding, no agent forwarding
   and strict host-key verification; the frozen future command contract must
   also disable interactive prompts and agent/forwarding inheritance.
4. Short connection and command timeouts, bounded output and deterministic
   pagination/count limits.
5. Redaction before persistence, audit identity, timestamp/timezone,
   extraction provenance and checksums.
6. A denylist that includes every write or elevation path: no sudo, migrate,
   update, restart, reload, cache mutation, scheduler control, console,
   DocType mutation, configuration mutation, service/queue mutation,
   permission change, webhook/job execution, adapter dispatch, replay,
   reconciliation action or target command.
7. Immediate stop on permission insufficiency, version mismatch, unknown
   output shape, secret exposure or allowlist drift. Missing facts stay
   blocked; privileges are never broadened during collection.

This document contains no runnable connection command or production endpoint.

## Validation and acceptance checklist

- [ ] Every register row has one of the five classifications and one allowed
  fact-evidence status.
- [ ] Every proposed customization has exact Requirement IDs, NPI
  contract/ownership, ERP owner, rationale, exact ERP identifier or explicit
  Blocked Pending Fact, permission, migration, test, go-live/rollback and
  evidence.
- [ ] Accepted external evidence is dated, sanitized, owner-identified,
  checksum-verified and listed in the sole `REQUIRED_INPUTS.md` provenance
  manifest.
- [ ] No endpoint, host, user, key, credential, secret, personal datum or
  commercially sensitive value appears in committed evidence.
- [ ] Screenshots, samples, local fixtures, Mock and Synthetic data are not
  treated as production facts.
- [ ] Ownership contracts and OpenAPI/event schemas are updated only after a
  proven field/operation decision; field ownership changes also have ADR and
  migration approval.
- [ ] Normal, duplicate, reordered, stale, conflict, permission, 429, 5xx,
  business 4xx, partial, timeout-after-commit, expired credential, target
  unavailable, restart, replay and reconciliation cases pass in the approved
  environment.
- [ ] Migration, backup/restore, forward-fix/rollback, monitoring, support,
  Sandbox UAT and production activation evidence pass the applicable release
  Gate.

## Explicit no-change list

This baseline authorizes no ERPNext or Frappe core change; no production or
Sandbox connection; no endpoint/profile/credential; no Custom Field, Property
Setter, DocType, Workflow, Role, permission, service user, Naming Series,
index, patch, fixture, migration, backfill, webhook, job, scheduler, report,
print format, client/server script, adapter, queue or configuration change; no
API, event, ownership, product, UI or runtime change; no target write, replay,
reconciliation action or historical rewrite; and no requirement status or
business approval change.

Rollback of this documentation task is a documentation-only revert to the
accepted P8-07 governance transition while retaining all immutable product,
trace and evidence history.
