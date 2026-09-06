# Required External Inputs

Status: **NO USER INPUT REQUIRED FOR P8-07F OR P8-08 START — PRODUCTION ACTIVATION INPUTS RETAINED**
Updated: 2026-08-30

Authoritative current state: exact SHA `77b4258f` passes ordinary CI
`33312664804`; the sole remaining `SYSTEM_LOCALE` read succeeds and removes
private state. The bounded P8-07F production facts are reconciled, no concrete
incompatibility is proved and no external bundle is requested for P8-07F or
P8-08 start. Database topology, a named least-privilege service principal,
owner-approved business-code mappings, Sandbox/UAT, deployment/support and
production enablement evidence remain required only where a later production
activation or production-ready claim depends on them. Future ERP-dependent
tasks must reuse the inventory and perform only freshness/delta reads when
needed; no credential or sensitive value belongs here.

This remains the single place for any future external fact request. No bundle
is requested while the newly authorized, separately gated read-only
self-collection can supply the missing facts; never send credentials or
incremental production extracts. The P8-07F collected only the safely
observable subset through its fixed
`JCE-Core` read-only boundary. Governance and activation Gates passed. After
two earlier no-output attempts, fixed-root SHA `9ab9bd5199e5521f3a72e701c3fa4338d6e866db`
and ordinary `33295753975` enabled an accepted sanitized Bench/Site discovery.
The status-token repair passes at `be03972a` / ordinary `33296694027`. The
NUL-framing repair passes at `acbd6882` / ordinary `33297909199`; complete
anonymized HEAD/status and all twenty path inventories are accepted. Six clean
custom apps yielded bounded source summaries. ERPNext and twelve of eighteen
custom apps have tracked drift, so their HEAD content is not runtime truth.
Two relevant DocType candidates stopped at sensitive-content preflight, and
runtime-only metadata remains outside the frozen source-only allowlist. The
private state is deleted and this production-read window is closed.
On 2026-08-30 the user explicitly authorized governed self-collection of the
current tracked worktree, structural summaries for the two stopped DocType
candidates and fixed application-layer runtime metadata. No external source
bundle is currently requested. Do not reconnect yet: the zero-contact
`P8-07F-CURRENT-RUNTIME-GOVERNANCE` transition must pass exact-SHA ordinary CI
and Level 3, and the separate collector expansion must pass its own exact-SHA
ordinary CI first. A later fail-closed stop may create one new, exact external
input; it does not reopen this whole package.

Never provide or record credentials,
endpoint/host/user/key values, secrets or unrelated business records.

The acceptance/status matrix for these inputs is
`docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md`. That matrix is not a second
request and contains no production values. This file remains the sole source
for requesting, receiving and recording external fact provenance.

Before supplying anything after a future fail-closed stop, check
`docs/ERPNEXT_PRODUCTION_FACT_INVENTORY.md`. It now contains the accepted
version, installed-app, anonymized HEAD/status and tracked-path baseline. Do not
repeat already accepted inventory. The previously missing evidence is now
authorized for separately gated, bounded and sanitized self-collection. Record
task ID, purpose, timestamp/timezone, redacted source, version/checksum,
finding, unknown and contract/ownership impact. Never provide credentials or
raw private production values.

Current provenance: task `P8-07F-FACTS`; source
`JCE_CORE_PRODUCTION_REDACTED`; fixed-root SHA `9ab9bd51`; status-token SHA
`be03972a`; NUL-framing SHA `acbd6882`; ordinary `33297909199`; final accepted
checksum-confirming window `2026-08-30T07:07:57Z` through
`2026-08-30T07:14:52Z`; operations `ERP_VERSION`, `INSTALLED_APPS`, `APP_HEAD`,
`APP_STATUS`, all twenty `APP_TRACKED_PATHS` and a bounded clean-app subset of
`APP_FILE_HASH`/`APP_FILE_READ`; Bench checksum
`sha256:bc5f2b2653647c21c6cee66e357951831f4e1e512ca9bcb641f8b017fef9b815`;
Site-inventory checksum
`sha256:cec7d8128c63e6b79bc6fcf9da558378d2c134a9f96a9a5a8b36a585b319c0fd`.
The Site value remains private and is not persisted here.

The user has since confirmed the default relative Bench root `frappe-bench`
and supplied the task-scoped runtime Site privately. The Site value is not
repeated or persisted here. Fixed-root discovery and HEAD/status reads pass.
The path repair and bounded read are complete. The expanded authorization does
not permit treating dirty worktrees as `HEAD`, weakening redaction, direct SQL,
console, generic methods or caller-selected runtime queries. The new
governance and activation Gates must freeze the exact current-source and
application-layer metadata operations before they can run.

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
