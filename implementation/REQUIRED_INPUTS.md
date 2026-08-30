# Required External Inputs

Status: **OPEN — P8-07F FIRST READ FAILED CLOSED; PRODUCTION FACTS UNVERIFIED**
Updated: 2026-08-30

This is the single complete request for external facts that are not present in
the repository. Supply one dated, owner-identified, sanitized, read-only bundle
rather than sending credentials or incremental production extracts. The
P8-07F may instead collect only the same necessary facts through its fixed
`JCE-Core` read-only boundary. Governance and activation Gates passed, but the
first `ERP_VERSION` attempt at `2026-08-30T00:04:24Z` produced no accepted
output and stopped the run. Never provide or record credentials,
endpoint/host/user/key values, secrets or unrelated business records.

The acceptance/status matrix for these inputs is
`docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md`. That matrix is not a second
request and contains no production values. This file remains the sole source
for requesting, receiving and recording external fact provenance.

Before asking again or connecting, check
`docs/ERPNEXT_PRODUCTION_FACT_INVENTORY.md`. It currently contains no accepted
production fact. After the external read condition is corrected without
allowlist drift, resume from `ERP_VERSION`; later reuse fresh accepted facts and
perform only a task-scoped delta. Record task
ID, purpose, timestamp/timezone, operation ID, redacted source, version/
checksum, finding, unknown and contract/ownership impact. Stop on permission,
version, output-shape, sensitive-content, allowlist or write-boundary drift.

Current provenance: task `P8-07F-FACTS`; source
`JCE_CORE_PRODUCTION_REDACTED`; activation SHA `c8d3b3c0`; ordinary
`33281944546`; operation `ERP_VERSION`; result
`UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT`; checksum
`NOT_AVAILABLE_NO_ACCEPTED_OUTPUT`. No subsequent operation ran.

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
7. The authoritative Tooling List workbook/template and owner-approved column
   dictionary, including the expected 43-column interpretation, A/B/C-face,
   overmold/insert rules, required/optional fields, units, validation, revision
   history, and approved sample rows. The checked-in
   `docs/reference/TOOLING_LIST_FIELD_MAPPING.csv` is the DOCX-proposed mapping
   and trace source; it is not production column-semantics approval.
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

## 2. Project control and collaboration production-activation package

The generic versioned/fail-closed Phase 4 foundation is complete. Provide one
owner-approved, versioned package before activating these production rules:

1. Project health formulas, dimension inputs, units, green/yellow/red
   thresholds, aggregation, manual-assessment authority, red recovery
   requirements, and the exact ERP-owned actual-cost source plus unavailable
   and stale-data semantics.
2. The allowed pause, cancel, resume, and complete transitions for each
   Project state; exact authority slots and segregation constraints; and the
   authoritative blocker, controlled-file, handover, and cost-readiness
   prerequisites for completion.
3. Project collaboration retention, notification-delivery, mention,
   attachment, and external-user participation rules. Until supplied,
   notifications remain explicitly unavailable and collaboration remains
   internal and contextual.
4. Project-learning classification, retention, search visibility, and the
   named governance path that may accept a `template_improvement` proposal
   into a future immutable Project Template version. The implemented proposal
   record must not be applied automatically.

Until this package passes the intake validation below, the implementation must
continue to use versioned configurable rules, exact frozen authorities,
synthetic fixtures, and fail-closed unavailable states. No production policy
or default is installed.

## 3. Phase 5 document, baseline, EBOM, and connector activation package

Before production document/release, external sharing, CAD/PDM, or formal
Item/MBOM behavior is activated, provide one owner-approved versioned package:

1. Document types, required metadata, prefix/numbering series, uniqueness and
   reservation scope, major/minor revision rules, effective dates, replacement
   semantics, lifecycle transitions, and retention/destruction policy.
2. Review/release roles, exact approval and segregation rules, delegation,
   electronic-confirmation or reauthentication strength, release/baseline
   authority, and the required G2/G5/G6/ECN baseline contents.
3. Confidentiality classes, Project/customer access rules, download/export
   audit and watermark requirements, external identity and share-delivery
   mechanism, expiry/revocation rules, and incident response.
4. File upload limits, MIME allowlist, antivirus/scanner provider and
   quarantine behavior, PDF/image/Office preview policy, trusted derived-file
   rules, viewer origins, signed-link lifetimes, and error/retention semantics.
5. The authoritative document-to-Project/product/part/Tooling/Trial/Gate/change
   relationship requirements and automatic impact/invalidation matrix.
6. EBOM numbering, line identity, quantity precision, UOM, alternates,
   effectivity, attribute set, review/release conditions, Item conversion, and
   formal MBOM mapping rules.
7. ERPNext Item/BOM schemas and customizations, operation-specific sandbox
   endpoint definitions, expected versions, submitted-BOM restrictions,
   per-node mapping/result and partial-success behavior, reconciliation, and
   safe retry rules. Do not provide production credentials or endpoints.
8. CAD/PDM provider and version, authentication design without secrets,
   attribute/part-list mapping, derivative format, callback or polling
   contract, retry/final-failure behavior, and sanitized representative files.

Until this package passes intake validation, Phase 5 uses versioned synthetic
policies, exact immutable references, explicit unavailable states, Mock-default
Execution Requests, and fail-closed external/connector behavior. No production
policy, connector, mapping, or formal ERP result is inferred.

## 4. Reconciliation decision and display-identity package

Provide owner-approved decisions for:

1. `DR-REC-001`: whether My Work uses page-specific inline expansion with
   drawer/Object Page fallback;
2. `DR-REC-002`: tolerance/rule ownership and when a Tooling/process variance
   receives exception color;
3. `DR-REC-003/004`: exact controlled forms, owners/signers, wet/electronic
   signature, PDF/browser-print and numbered-copy/retention policy;
4. `DR-REC-007/008`: source-column Standard/estimate/actual/calculated
   classification and the downstream-use rollback cutoff;
5. `DR-REC-009`: Released Trial Summary authority, dotted event identity,
   payload/version, redaction and read-only consumer mapping; and
6. `DR-REC-010`: independent Tooling Requirement, Tooling Revision and
   physical Tooling Set states, transitions, skip/reopen/terminal rules and
   authority.

The brand package is complete for its currently approved purposes:
`docs/Brand Asset/Brand Asset Instruction.csv`, its exact five LaunchFlow SVGs
and `Core.png` are the sole source. The approved `JCE Core` display name,
`Core.png` and its usage rule resolve DR-REC-006; runtime activation remains
allocated to Phase 8/M7-09. Do not send, retrieve or create substitute marks.

Each open decision pauses only the dependent behavior named in
`implementation/V1_2_RECONCILIATION_DECISIONS.md`. Safe parser/provenance,
immutable snapshots, generic print registry, Mock/sandbox-ready contracts and
unrelated NPI-owned work continue.

## 5. Phase 3 business acceptance package

Provide the completed
`implementation/evidence/phase-3/business-uat.md` record with:

- named Project Management, Engineering/Tooling, and Quality reviewers;
- all six flows recorded in `en`, `zh`, and `zh-TW`, including duration,
  context switches, findings, owners, and resolution evidence;
- signatures or an equivalent auditable approval record for all three roles;
- no open Severe usability finding; and
- provenance-backed sanitized data for the two representative project types
  above, so fixture-only technical paths are not misrepresented as real UAT.

## 6. Scope affected while inputs are open

The missing bundle does not block NPI-owned domain work, contracts, explicit
mocks, sandbox-ready adapters, automated tests, UI, localization, or operating
documentation. Continue those tasks under the reconciled Pack and accepted
addendum.

Pause only implementation or acceptance that would otherwise guess an existing
ERP customization, field mapping, numbering/state rule, sandbox behavior, or
real-data business result. Production activation, production credentials, and
production data operations remain out of scope even after this package is
provided unless separately authorized.

## 7. Intake validation

The package is usable only when every file appears in the provenance manifest,
checksums match, relationships survive redaction, secret scanning is clean, and
the named owners resolve material contradictions. Record accepted facts and
field ownership in contracts/ADRs before implementing the affected behavior;
do not infer missing fields from screenshots or sample values.
