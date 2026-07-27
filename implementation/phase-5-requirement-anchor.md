# Phase 5 Requirement Anchor — Design, Documents, Baselines, and EBOM

Status: **ANCHORED — P5-01 CHECKPOINTED AND HELD FOR R1 BRIDGE**

Anchor date: 2026-07-25

Controller phase: 5 — Part Design, Documents, Baselines, and EBOM

Compatibility milestone: M4 — Design and baselines

Starting checkpoint:
`028d551d4e02ad5700b165c21409e14b647babf0`

## 2026-07-25 reconciliation amendment

P5-00 and the original five-task allocation below remain truthful historical
Gate evidence. The current typed trace contains 282 IDs rather than the
pre-reconciliation 173; the append-only addition is `FR-UX-043` under R1-05,
and the retained P5-01 backend checkpoint is
`930b5a28cb995df12f251994a36f7502525ed94a`.

Before any further P5-01 product work:

1. retain the completed R1-01 reconciliation, R1-02 display-brand and R1-03
   navigation/command evidence;
2. deliver R1-04 through R1-06 shared UX/governance remediation;
3. keep R1-07 scoped to DR-REC-001; and
4. pass the triggered Level 3 shared Shell/design/i18n bridge Gate.

The amended M4 plan adds:

- M4-06 for `FR-PRN-001/002`: a generic server-side Print Format registry and
  immutable controlled-output snapshot foundation; and
- M4-07 for `FR-PRN-003`: exact forms, signers and copy policy only after
  DR-REC-003/004.

This amendment does not mark P5-01 complete, activate P5-02, rewrite the
historical 173-ID P5-00 validation, or install a production print policy.

## 1. Authority and bounded outcome

This anchor applies the V1.2 continuous-delivery authority to the Phase 5 M4
vertical slice. It is based on `GOAL.md`, `docs/PRODUCT_SPEC.md`,
`docs/DETAILED_REQUIREMENTS.md`, `docs/ERPNEXT_INTEGRATION.md`,
`docs/UX_INTERACTION_SPEC.md`, `docs/ACCEPTANCE_TESTS.md`,
`implementation/ROADMAP.md`, M4 in `implementation/backlog.yaml`, the current
contracts, and accepted ADR-001, ADR-007, ADR-008, and ADR-009.

The bounded demonstrable path is:

> register a controlled customer input → create a design/document revision →
> review and release it → capture an immutable baseline → reference the exact
> baseline from a Gate → introduce a successor revision and expose its impact →
> create and compare an EBOM revision → validate a formal publish request
> without claiming ERPNext execution

Phase 5 delivers NPI-owned working documents, exact file revisions, design
revision history, review/release records, immutable engineering baselines,
generic impact invalidation, EBOM working revisions and differences, and an
explicit Mock/sandbox-ready formal-publish request boundary. It does not move
formal Item, MBOM, manufacturing routing, inventory, production, cost, or
financial ownership from ERPNext.

## 2. Requirement allocation and task order

The Pack defines exactly five M4 tasks. Phase 5 uses the following compatible
atomic order:

| Atomic task | Primary requirements | Truthful delivery boundary |
|---|---|---|
| P5-01 — Document and design revision | FR-DS-001, FR-DS-003, FR-DS-004, FR-DS-007, FR-DS-008, FR-DS-009, FR-DS-014 | Versioned controlled-document identity and working revisions over exact private File Revisions; explicit numbering/type policy, revision history, locks, Project-scoped confidentiality/download audit, safe preview/download fallback, and connector-unavailable isolation; no production numbering, sharing, viewer, CAD, or PDM rule |
| P5-02 — Review and release workflow | FR-DS-002, FR-DS-005, FR-DS-010 | Policy-bound review, reject, resubmit, approve, release, supersede and obsolete behavior with immutable file/hash/metadata confirmation and fail-closed integrity/security checks |
| P5-03 — Baseline and impact invalidation | FR-DS-006 | Immutable release packages containing exact document/file revisions, exact Gate references, and explicit registered dependencies whose changed inputs create visible impact/invalidation without inventing a production dependency matrix |
| P5-04 — EBOM revision and comparison | FR-DS-011, FR-DS-012 | NPI-owned EBOM working revisions with validated hierarchy, quantities, alternates/effectivity fields, review/release state, and deterministic added/removed/quantity/substitution/attribute differences; no formal MBOM or manufacturing routing |
| P5-05 — Formal publish request stub and contract | FR-DS-013 | An operation-specific, exact-version formal Item/MBOM publish request using the approved Execution Request boundary, explicit Mock default, sandbox-ready contract, partial-result truth, mapping/result records, and no production or optimistic ERP success |

The primary trace row for each requirement is:

| Requirement | Primary task | Phase 5 disposition |
|---|---|---|
| FR-DS-001 | P5-01 | Deliver configurable unique document identity without installing production document types, prefixes, or numbering series |
| FR-DS-002 | P5-02 | Complete controlled review/release/supersede/obsolete lifecycle while preserving the draft revision foundation from P5-01 |
| FR-DS-003 | P5-01 | Establish exact major/minor revision identity, reason, effectivity, predecessor/successor and metadata history; P5-02/P5-03 consume exact revisions |
| FR-DS-004 | P5-01 | Deliver typed Project and currently available object links with reverse lookup; unresolved future-domain resolvers remain explicitly unavailable until their owning phases |
| FR-DS-005 | P5-02 | Deliver policy-bound review and immutable approval/confirmation records without inferring production authority or signature policy |
| FR-DS-006 | P5-03 | Deliver immutable exact-version release packages/baselines and Gate evidence references |
| FR-DS-007 | P5-01 | Deliver bounded checkout/edit locks, administrative recovery audit, and no silent overwrite |
| FR-DS-008 | P5-01 | Deliver confidentiality, Project authorization, download audit, and an expiring/revocable share-grant foundation; actual external-user retrieval remains fail closed until the approved external identity/sharing policy exists |
| FR-DS-009 | P5-01 | Deliver permission-checked preview capability metadata and safe fallback to integrity/download actions; no unsupported format is represented as previewable |
| FR-DS-010 | P5-02 | Reuse the P5-01 exact private-file metadata foundation and block release unless the required integrity and scanner-owned safety policy is satisfied |
| FR-DS-011 | P5-04 | Deliver NPI-owned EBOM working revisions only; formal Item/MBOM ownership remains ERPNext |
| FR-DS-012 | P5-04 | Deliver deterministic exact-revision differences usable by review and P5-05 request preparation |
| FR-DS-013 | P5-05 | Deliver the formal publish request stub/contract and mapping/result truth; actual ERPNext execution and reconciliation remain Phase 8 |
| FR-DS-014 | P5-01 | Deliver connector-neutral source/derivative metadata and explicit connector failure isolation; an actual CAD/PDM adapter remains held until a provider contract exists |

Shared allocation does not duplicate persistence ownership. For example,
P5-01 owns the revision aggregate, P5-02 appends review/release history,
P5-03 freezes exact revision references, and P5-05 consumes an exact released
EBOM/baseline snapshot. Later tasks may strengthen a requirement's status but
must not rewrite earlier immutable history.

The following staged acceptance remains explicit:

- `FR-DS-008` can reach only a technical foundation in Phase 5 while actual
  external-user retrieval is unavailable; external identity/portal delivery
  remains Phase 9 scope.
- `FR-DS-009` cannot claim complete Office/CAD preview without an approved
  provider. Permission-checked capability truth and a hash/download fallback
  remain the safe boundary.
- `FR-DS-013` can reach only a technical foundation in Phase 5 because real
  ERPNext Item/MBOM execution and reconciliation remain Phase 8.
- `FR-DS-014` has no independent M4 backlog task. P5-01 owns the optional
  connector seam and failure isolation so it is not omitted; a real CAD/PDM
  connection remains held.
- The current generic OpenAPI Execution Request seed and in-memory
  Outbox/Inbox foundation are not P5-05 evidence. P5-05 must replace the open
  payload with operation-specific Item/MBOM contracts and complete
  permission, CSRF, idempotency, version, state, persistence, fault and
  no-fake-success evidence.

## 3. Ownership and vocabulary frozen before implementation

### 3.1 Controlled document and file identity

- `ControlledDocument` is the stable engineering/business identity. A
  `DocumentRevision` is one immutable numbered revision of that identity.
- `FileRevision` is the exact private binary identity and integrity snapshot
  already established by the Phase 2/P4-03 foundation. A document revision may
  reference exact File Revisions; the two concepts must not be collapsed.
- The existing integer `FileRevision.revision` and `released` flag remain their
  original exact-file/evidence semantics. Neither is a major/minor
  `DocumentRevision` nor a complete document approval/release workflow.
- Frappe `File` storage or a future object store owns binary transport. NPI One
  owns document/revision metadata, authorization, hashes, scan observation,
  release history, baselines, and audit.
- A raw private-file URL is never Project authorization and is never exposed as
  a stable public business link. Every preview/download command re-authorizes
  tenant, Project, document, exact revision, confidentiality, and current
  grant state.
- Released, superseded, obsolete, baseline-member, review, confirmation, and
  download-audit records are retained. A released revision is never overwritten
  or physically deleted through a normal-user path.
- Existing protection of the `NPI File Revision` projection does not yet prove
  protection of its underlying Frappe `File`. P5-02 must block deletion of
  released/retained binary content at the server-side File boundary as part of
  release integrity; P5-00/P5-01 do not claim that invariant early.

### 3.2 Document lifecycle and policy

- The controlled state family is `draft`, `in_review`, `approved`, `released`,
  `superseded`, and `obsolete`. Stable English codes remain untranslated
  contract values; display labels use the shared Frappe-compatible catalogs.
- A change to released content creates a new revision. Major/minor selection,
  effective-date rules, required reasons, document-type eligibility, and
  transition authority come only from an exact versioned policy.
- Review assignment and final release authority are separate. Project
  ownership, RACI, `System Manager`, or the `NPI API User` transport role does
  not silently grant business approval.
- Approval/confirmation freezes the exact document revision, File Revision
  identities, hashes, metadata, policy/input snapshot, actor, time, request,
  trace, and confirmation evidence.
- Checkout/edit lock is an overwrite-prevention mechanism, not an approval or
  authorization grant. Administrative recovery preserves the former holder,
  reason, actor, time, and affected revision.

### 3.3 Baseline and impact

- A release package/baseline is an immutable set of exact document revision and
  File Revision/hash references. A later file or document revision never
  replaces a baseline member.
- A Gate may reference an exact baseline through the existing exact-evidence
  boundary; neither “latest” nor a mutable URL is accepted.
- A successor revision can invalidate only explicitly registered exact
  dependencies. The system records old/new input hashes and visible affected
  objects, preserves the prior Gate/baseline history, and fails downstream use
  closed until the owning review resolves it.
- Phase 5 does not infer a production drawing/Tooling/Trial/quality/ECN
  dependency matrix from filenames, document types, screenshots, or test data.

### 3.4 EBOM, Item, MBOM, and execution

- NPI One owns engineering draft Item identity and EBOM working revisions
  before formal release. ERPNext owns formal `item_code`, formal MBOM,
  manufacturing routing, stock UOM authority, and execution transactions.
- EBOM and MBOM are different objects. Publishing an EBOM never changes NPI
  ownership into direct MBOM edit authority.
- P5-05 creates a formal execution request from one exact released EBOM and
  baseline/approval snapshot. It records operation, object/version, actor,
  trace, idempotency identity, payload hash, approval evidence, validation, and
  per-node mapping/result truth.
- Mock validation or request acceptance is not ERP success. Mock mode cannot
  return a formal Item/MBOM identifier or `succeeded`. Sandbox use requires
  explicit configuration, production hosts remain rejected, and actual
  adapter/retry/replay/reconciliation behavior remains Phase 8.
- Partial success is visible at node level. Safe retry targets only eligible
  failed nodes and never overwrites submitted ERP BOMs or silently wins a
  mapping conflict.

## 4. Class-B holds

Missing facts pause only their dependent production rule or connector. They do
not block generic/versioned NPI-owned infrastructure, explicit synthetic
fixtures, contracts, Mock behavior, tests, UI, localization, or documentation.

| Held production fact | Safe Phase 5 boundary |
|---|---|
| Document classes, required metadata, prefixes, numbering series, uniqueness scope and reservation rules | Use an explicit versioned policy and deterministic synthetic policies in tests. Install no production default and do not derive a number from sample filenames. |
| Major/minor revision rules, effective dates, replacement semantics and lifecycle transitions | Preserve explicit revisions and exact predecessor/successor links. Fail closed when the selected versioned policy does not authorize a transition. |
| Review/release authorities, segregation, delegation, electronic-confirmation strength and reauthentication | Freeze exact policy/member bindings and separate review from release. Do not infer authority from RACI, Project ownership, support roles, or external users. |
| Customer confidentiality classes, retention, watermark/export rules, external identity, share delivery, expiry, revocation and download policy | Implement Project-scoped internal authorization, audit and a disabled-by-default expiring grant model. External retrieval remains unavailable until the approved policy and identity boundary exist. |
| Upload limits, MIME allowlist, antivirus provider, quarantine/retention and failure escalation | Reuse scanner-owned states, make `pending`/`failed`/`infected` visible, and block policy-required release. Never fabricate `clean`. |
| PDF/image/Office/CAD preview providers, derived-file trust, viewer origins and signed-link lifetimes | Publish capability truth and safe fallback. Unsupported/untrusted previews remain unavailable; a raw URL never grants access. |
| Required Project/product/part/Tooling/Trial/Gate/change relationships and automatic impact matrix | Validate implemented exact resolvers and expose later-domain links as unavailable. Use only explicit dependency registrations; do not infer completeness. |
| G2/G5/G6/ECN baseline contents, release authority, replacement and retention | Provide immutable generic baselines with synthetic acceptance fixtures. Install no production Gate-to-baseline policy. |
| EBOM numbering, line identity, quantity precision, UOM, alternates, effectivity, attribute set, release conditions and Item conversion | Use versioned explicit rules and fixed deterministic test fixtures. Do not infer formal Item codes, stock UOM, MBOM routing, or conversion from engineering samples. |
| ERPNext Item/BOM custom fields, endpoints, expected versions, submitted-BOM restrictions, node mappings, partial-success and reconciliation behavior | P5-05 stops at strict Mock/sandbox-ready contracts. Phase 8 owns the real adapter after the reconciliation package is accepted. |
| CAD/PDM provider, authentication, property/part-list mapping, derivative format and failure/retry semantics | Keep the connector optional and unavailable by default. Basic manual document/revision/release flow must pass without it. |

The complete external request remains centralized in
`implementation/REQUIRED_INPUTS.md`. Production credentials, production data,
and production ERPNext/CAD/PDM access are neither required nor authorized.

## 5. P5-01 minimum complete vertical slice

P5-01 is the next active task. It must deliver:

- additive controlled-document, immutable document-revision, exact relationship,
  lock/history, and command-idempotency persistence without installing
  production document/numbering policy;
- one explicit versioned synthetic document policy in tests, never as a
  migration default;
- a controlled private-file registration/upload boundary that extends the
  existing exact File Revision foundation, computes and retains integrity
  metadata server-side, starts in the real scanner-owned state, and exposes no
  raw stable URL;
- Project-scoped confidentiality metadata, server-authorized download audit,
  and an explicitly unavailable external-retrieval state with bounded
  expiring/revocable share-grant records that grant no access by themselves;
- strict create/query/new-revision/check-out/check-in/recover-lock and
  permission-checked preview/download-capability BFF contracts under
  `/api/npi/v1`;
- exact tenant/Project/object authorization before protected identity or
  validation detail, external-principal denial, Frappe CSRF, optimistic
  versions, actor-bound idempotency, transaction rollback, audit, and trace;
- a live industrial Project Design/Documents workspace with dense revision
  history, source/editability, file integrity/scan/preview truth, lock state,
  normal/non-normal command behavior, and no normal-user Desk dependency; and
- literal English source strings, complete direct `zh` and `zh-TW`
  translations, component/contract/permission/runtime/migration/E2E/
  accessibility/visual evidence, and an explicit changed-files-to-tests map.

P5-01 does not review, approve, release, supersede, baseline, publish an EBOM,
create an ERP execution request, enable external retrieval, claim an Office/CAD
viewer, or connect CAD/PDM/ERPNext. Its accepted revision path may use only
clearly synthetic policy and file fixtures.

## 6. Acceptance and evidence plan

### Domain and contract

- stable document identity is distinct from immutable revision and binary
  identities;
- document numbers are unique within the exact policy scope and concurrent
  reservation leaves one winner with no partial record;
- released/history records reject overwrite/delete and new content creates a
  successor revision;
- major/minor, state, effective date, and relationship inputs are strict and
  policy-bound;
- lock acquisition/release/recovery is versioned, actor-bound and audited;
- file hash/size/MIME identity is computed and revalidated server-side, and
  scanner state cannot be selected by a browser command;
- preview/download never weakens document/File/Project authorization;
- baselines and Gate evidence freeze exact revisions/hashes;
- impact invalidation preserves prior decisions and exact old/new lineage;
- EBOM graphs reject missing/cross-Project references, cycles, duplicate line
  identity, invalid quantity, invalid effectivity, and ambiguous alternates;
- EBOM comparison is deterministic and covers add/remove/quantity/substitution/
  attribute change;
- formal publish requests bind exact released input, approval evidence,
  idempotency and payload hash, and Mock never reports ERP completion; and
- transaction failure leaves no partial document, revision, release, baseline,
  EBOM, mapping, request, audit, or idempotency history.

### Permission and security

- guest, external, tenant-mismatched and unrelated-Project access fail without
  object-existence disclosure;
- view, contribute, lock, review, release, baseline, share, download, EBOM and
  publish-request authorities are independent server decisions;
- upload, preview, export, administrative lock recovery, approve and obsolete
  are likewise independent capabilities; assignment, Project ownership,
  transport roles and front-end visibility never grant them implicitly;
- expiring/revoked grants, download logging, filename/content-disposition,
  traversal, MIME confusion, XSS, CSRF, IDOR, raw-URL, oversized-file, infected
  file, and stale-version cases are covered as applicable;
- external users cannot review, release, baseline, publish, or trigger ERP
  execution;
- execution requests use operation-specific schemas and never expose service
  credentials to the browser; and
- no `ignore_permissions`, direct SQL, raw browser DocType CRUD, core patch,
  dual-master field, production secret, production endpoint, TODO/stub fake
  success, or destructive migration is introduced.

### Runtime, UI, localization, and integration readiness

- additive install/migrate and an idempotent rerun pass on the controlled Site;
- complete prior Phase runtime compatibility remains green;
- normal-user BFF paths prove immutable files/revisions, authorization,
  command replay/conflict, rollback, audit and route disable/recovery;
- each affected workspace covers loading, normal, empty, no-permission,
  read-only, validation, conflict, processing, retryable/final failure,
  partial/unavailable source, dirty-leave and success states;
- every user-visible source is literal English with complete direct `zh` and
  `zh-TW`; mixed-language, placeholder and terminology gates pass;
- keyboard/focus/labels, text-plus-shape status, 125%/150% layouts, exact visual
  comparison and original-resolution review preserve the industrial baseline;
- P5-05 fault evidence includes duplicate request, payload conflict, timeout
  after possible commit, 429, 5xx, business 4xx, partial node success, stale
  mapping, unavailable target, restart and replay without contacting
  production; and
- the Phase 5 Level 3 Gate runs once at the Phase boundary and reuses unaffected
  accepted evidence according to `implementation/QUALITY_GATE.md`.

## 7. Migration and rollback

P5-00 itself changes documentation and trace state only. It creates no Schema,
data, route, credential, external request, or runtime feature.

Future Phase 5 Schema changes must be additive and repeatable. Migrations may
install no production document policy, numbering series, approval map,
baseline contents, external share, CAD/PDM connector, EBOM conversion, ERP
mapping, endpoint, credential, or sample business record.

Before retained Phase 5 history exists, a disposable environment may restore
checkpoint `028d551d4e02ad5700b165c21409e14b647babf0`. Once document/release/
baseline/EBOM/request history exists, preserve additive tables and immutable
records, disable affected BFF routes and external dispatch, fail dependent use
closed, and deploy a reviewed forward fix. Never delete released revisions,
approvals, baselines, mappings, request history, or audit as rollback.
ERPNext remains unaffected because production access is prohibited.

## 8. Expected change surface and changed-files-to-tests

Expected Phase 5 product changes are additive `npi_core` document/baseline/EBOM
DocTypes and domain/BFF modules, bounded `npi_integration` request-readiness
code only where P5-05 requires it, strict OpenAPI/data-ownership/event
contracts, Project Design/Documents and EBOM workspaces, canonical translation
catalogs, and focused tests/runtime scripts/evidence. No new production
dependency is authorized by this anchor.

P5-00 itself uses this impact map:

| Changed files | Affected checks |
|---|---|
| `implementation/phase-5-requirement-anchor.md` and recovery/evidence Markdown | required-section/current-task/hold/ownership wording scan; no early P5-01 code assertion |
| `implementation/REQUIREMENT_TRACEABILITY.csv` | CSV shape, 173 unique IDs, exact `FR-DS-001..014` primary-task allocation and source/evidence paths |
| `implementation/PHASE_STATUS.yaml` | safe YAML parse; Phase 3 pending UAT, Phase 4 PASS, Phase 5 IN_PROGRESS |
| `implementation/DECISION_LOG.md`, `RISK_REGISTER.md`, `BLOCKERS.md`, `REQUIRED_INPUTS.md` | single-source external-input, no production-access, ownership and scoped-hold consistency |
| complete P5-00 diff | documentation-only path assertion, prohibited fake-success/production-activation scan, and `git diff --check` |

## 9. Primary risks

Primary risks are mutable “latest” references, conflating document identity
with a binary file, fabricated clean/preview state, raw private URLs,
authorization after object resolution, approval-role conflation, mutable
baselines, guessed impact dependencies, EBOM/MBOM dual mastery, Mock portrayed
as ERP success, partial-result loss, and hidden production connector
assumptions. They remain explicit tests, risks, or scoped holds rather than
convenient defaults.

## 10. P5-00 exit decision

**P5-00 PASS; P5-01 ACTIVE.** Phase 5 scope, non-scope, ownership, vocabulary,
requirement allocation, Class-B holds, five-task order, first vertical slice,
acceptance evidence, migration, rollback, and changed-files-to-tests mapping
are explicit.

The anchor introduces no business code and does not claim any
`FR-DS-001..FR-DS-014` implementation. Their trace rows are anchored to their
primary tasks. `P5-01 — Document and design revision` activates under the
existing continuous-delivery authority.
