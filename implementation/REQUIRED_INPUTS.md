# Required External Inputs

Status: **OPEN — partial external dependency, not a global blocker**
Updated: 2026-07-24

This is the single complete request for external facts that are not present in
the repository. Supply one dated, owner-identified, sanitized, read-only bundle
rather than sending credentials or incremental production extracts. Production
ERPNext access is prohibited; any future sandbox access requires separate
approval and must reject production endpoints.

## 1. Current ERPNext reconciliation package

Provide:

1. Exact Frappe and ERPNext versions/builds, installed apps and versions,
   deployment topology, database type, file-storage mode, enabled locales,
   System Settings language, representative User language values, and supported
   Bench/container development commands.
2. Source or exports for every ERPNext custom app and extension: `hooks.py`,
   modules, DocTypes, patches, fixtures, overrides, whitelisted methods,
   scheduled jobs, reports, print formats, client/server scripts,
   notifications, webhooks, and workspace customizations.
3. Exports of Custom Fields, Property Setters, Workflows and Workflow
   States/Actions, Naming Series, Roles, Role Profiles, DocPerm/custom
   permissions, User Permissions, sharing rules, and integration/service-user
   scopes. Do not include passwords, tokens, cookies, keys, or other secrets.
4. Current schemas, states, ownership, and edit authority for Customer,
   Supplier, Item/Variant, BOM/MBOM, purchasing/receiving, inventory,
   manufacturing, Quality Inspection/NCR/CAPA, Asset/Maintenance, ECR/ECO/ECN,
   File/Attachment, and every custom project/tooling/trial object.
5. A field-level inventory for every integration: endpoint and operation,
   request/response or webhook schema, authentication method described without
   secrets, signatures, idempotency keys, retries, dead-letter/replay and
   reconciliation behavior, rate limits, error codes, and known failure cases.
6. Sanitized representative records and relationship diagrams for at least one
   customer-owned-tool project and one new-tool project, including revisions,
   approvals, released files, tooling, trial rounds, quality outcomes,
   purchase/manufacturing references, and failed/pending integration examples.
   Preserve stable surrogate relationships while removing personal,
   commercial, and secret data.
7. The authoritative Tooling List workbook/template and column dictionary,
   including the expected 43-column interpretation, A/B/C-face,
   overmold/insert rules, required/optional fields, units, validation, revision
   history, and approved sample rows.
8. Master-data and coding rules: company/site/factory, the trusted NPI tenant
   identifier for each Site and any approved principal-to-tenant mapping,
   customer/supplier/item naming, UOM, currency, timezone, fiscal/calendar
   conventions, naming series, document retention, attachment classification,
   and controlled terminology.
9. Current Project, Gate, Tooling, Trial, Change, approval/release, and ERP
   execution SOPs, including Gate condition/skip rules, evidence eligibility,
   P0 pass blocking, waiver/reopen/invalidation authority, scanner/provider and
   file-retention policy, and the temporal policy for disabled members and
   their historical/future role or substitution relations, plus named business
   owners empowered to resolve differences between SOP, ERP configuration,
   V1.2 contracts, and representative data.
10. A provenance manifest for every export: source system/site, extraction
    command or report, timestamp and timezone, responsible owner, redaction
    method, record counts, and checksum.

## 2. Phase 3 business acceptance package

Provide the completed
`implementation/evidence/phase-3/business-uat.md` record with:

- named Project Management, Engineering/Tooling, and Quality reviewers;
- all six flows recorded in `en`, `zh`, and `zh-TW`, including duration,
  context switches, findings, owners, and resolution evidence;
- signatures or an equivalent auditable approval record for all three roles;
- no open Severe usability finding; and
- provenance-backed sanitized data for the two representative project types
  above, so fixture-only technical paths are not misrepresented as real UAT.

## 3. Scope affected while inputs are open

The missing bundle does not block NPI-owned domain work, contracts, explicit
mocks, sandbox-ready adapters, automated tests, UI, localization, or operating
documentation. Continue those tasks under the approved Pack.

Pause only implementation or acceptance that would otherwise guess an existing
ERP customization, field mapping, numbering/state rule, sandbox behavior, or
real-data business result. Production activation, production credentials, and
production data operations remain out of scope even after this package is
provided unless separately authorized.

## 4. Intake validation

The package is usable only when every file appears in the provenance manifest,
checksums match, relationships survive redaction, secret scanning is clean, and
the named owners resolve material contradictions. Record accepted facts and
field ownership in contracts/ADRs before implementing the affected behavior;
do not infer missing fields from screenshots or sample values.
