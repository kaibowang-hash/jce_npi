# P5-06 Controlled Print Foundation Plan

Recorded: `2026-08-07T01:00:15Z`

Status:
`PASS — REQUIREMENT, DOMAIN AND EXISTING-CAPABILITY AUDIT`

Task:
`P5-06 — Controlled Frappe print registry and immutable snapshot foundation`

Requirements:
`FR-PRN-001`, `FR-PRN-002`

Starting checkpoint:
`ac890c08e7cfa7c428d1a487805527239f0659f5`

## 1. Audited authority and decision boundary

- The reconciliation amendment and M4 backlog explicitly allocate a generic
  server-side Print Format registry and immutable controlled-output snapshot
  foundation to `M4-06`/P5-06.
- `FR-PRN-001` requires exact selection by object type, Project type,
  Gate/state, language, effective mapping version and copy-control mode. A
  normal user must use the SPA/BFF, and a missing approved mapping fails
  closed.
- `FR-PRN-002` requires one immutable source snapshot with source/version,
  language, actor/time, QR/hash, watermark/copy state and audit. Reuse of the
  same controlled snapshot must never substitute newer live data.
- `DR-REC-003` and `DR-REC-004` do not block this generic foundation. They do
  block every exact production form, signer, retention, browser-print,
  numbered-copy and production delivery policy under `FR-PRN-003`.
- No controlled form or mapping is approved. P5-06 therefore installs no
  enabled registry row, default Print Format, source-to-form mapping, signer,
  copy number, retention period or production print action.

## 2. Audited repository and pinned-runtime facts

- NPI Core has no print route, controlled Print Format mapping, print
  persistence, output snapshot or seeded template. `hooks.py`, the BFF and
  OpenAPI contain no print activation that could be rebranded as completion.
- The existing document-baseline domain supplies the accepted canonical JSON,
  SHA-256, exact-version and append-only validation patterns. It does not
  represent a rendered output.
- `NPI File Revision` validates exact private local Frappe `File` identity,
  byte size, Frappe content hash and independent SHA-256, and exposes URL-free
  metadata. It is document-revision-specific, so a controlled output needs a
  separate immutable artifact record rather than a fake document revision.
- `NPI Audit Event` and the command-scoped append flag provide reusable
  append-only audit infrastructure. Current route switches, Project scoping,
  authorization-before-resolution, actor-bound idempotency and atomic receipt
  patterns are reusable implementation conventions.
- At the repository-pinned Frappe commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, official source provides the
  native `Print Format` DocType/template resolution and
  `frappe.utils.pdf.get_pdf()`. Native `get_rendered_template()` accepts a live
  Document, so P5-06 must not call it in a way that silently reloads current
  source truth after the immutable snapshot is created.
- The pinned Frappe dependency set provides PDF generation but no declared QR
  library. P5-06 may not add a production dependency without an approved ADR;
  QR generation must therefore be a bounded repository-owned deterministic
  SVG utility with fixed-vector tests, or remain fail-closed until such an
  implementation is proven. An external QR service is prohibited.

## 3. Minimum complete vertical slice

P5-06 will deliver:

1. a generic versioned registry mapping with exact tenant, source object type,
   Project type, optional exact Gate key, source state, language, effective
   interval/version, delivery/copy-control capability and exact Frappe Print
   Format identity/content hash;
2. draft/published lifecycle where only one exact published compatible mapping
   may resolve, ambiguous or absent mappings fail closed, and publication is an
   administrative action independent from normal-user print authority;
3. an adapter registry whose source resolvers are server-owned. Browser input
   contains only an exact Project/source identity, optimistic source version,
   requested language and idempotency key; it cannot submit template HTML,
   snapshot fields, actor/time, watermark, copy state, hash or File identity;
4. a canonical immutable snapshot containing exact source identity/version/
   state/hash, Project/type/Gate context, complete server-resolved source data,
   exact registry/format reference and template hash, language, actor/time,
   delivery/copy state, watermark text, verification payload and snapshot
   hash;
5. one-time rendering from the frozen source and exact captured template,
   followed by private local Frappe File persistence with byte length, Frappe
   content hash and independent SHA-256 in a separate immutable output record;
6. reprint/download behavior that returns the same retained output bytes and
   appends a new access/audit event; it never rerenders from current live data
   under the same snapshot identity;
7. Project membership plus independent print authority, CSRF, authorization-
   before-resolution, actor-bound idempotency, changed-payload conflict,
   atomic snapshot/output/audit/receipt persistence, protected content access
   and an independent route-disable/recovery switch;
8. a BFF-only capability/create/detail/content contract and reusable dense,
   translated print action/status surface that is unavailable when no approved
   mapping resolves; and
9. a controlled disposable-Site proof using only a visibly synthetic mapping,
   source and custom Print Format created through guarded administrative test
   setup and removed during cleanup. No synthetic fixture is installed by a
   migration or shipped as a production default.

## 4. Frozen safe implementation decisions

- Mapping resolution is exact and deterministic. No implicit fallback to
  Frappe's `Standard` format, default Print Format, another language, latest
  version or less-specific mapping is accepted.
- Registry publication freezes the exact resolved template content and its
  SHA-256. A later edit or rename of the live Print Format cannot alter an
  already published mapping or retained output.
- Output creation freezes source and template before rendering. Rendering uses
  the captured template plus the immutable snapshot, not a newly loaded live
  source Document.
- The verification payload identifies only the snapshot and its cryptographic
  hash. The rendered-file hash is recorded separately, avoiding a
  self-referential PDF/QR hash.
- No public route accepts a raw DocType, arbitrary method, template name or
  JSON payload. Supported source adapters are closed server code; adding an
  exact domain form remains P5-07 work after approval.
- Until `DR-REC-004` is resolved, the foundation permits controlled retained
  PDF delivery only. Browser print, direct device printing, numbered copies
  and claims about original/copy semantics remain unavailable. Copy-control
  fields are structural and receive no guessed production value.
- Existing Frappe permissions and NPI Project authorization remain mandatory.
  Neither `ignore_permissions` nor direct raw File URLs are normal-user access
  mechanisms.
- No external URL, ERPNext call, service credential, production Print Format
  or new runtime dependency is introduced.

These are reversible implementation details or direct consequences of the
accepted requirements/holds; they do not resolve a Class-B policy decision.

## 5. Scope and non-scope

In scope:

- pure registry/snapshot/output/event/idempotency domain and closed contracts;
- additive guarded NPI Core DocTypes and exact ownership vocabulary;
- server-owned mapping/source resolution, immutable rendering and private
  artifact access;
- BFF capability/create/detail/content routes, independent route switch and
  reusable SPA print affordance/status truth;
- direct English/`zh`/`zh-TW` catalogs, accessibility, browser/visual proof;
- controlled synthetic runtime proof, two migrations, cleanup and complete
  Level 2/Phase 5 Level 3 evidence.

Out of scope:

- any approved production form or default mapping;
- exact signer, wet/electronic signature, owner or retention rules;
- browser/direct-device printing, copy numbering or production copy policy;
- editable template design in the normal-user SPA or Desk as the product UI;
- public arbitrary DocType/Print Format selection;
- remote file storage, external QR/rendering services or ERPNext access; and
- Trial Summary, Tooling forms or any later domain form coverage.

## 6. Primary risks and controls

| Risk | Control |
|---|---|
| Live data changes between mapping, snapshot and rendering | Lock and validate exact source/version; persist canonical source snapshot before rendering; render only the frozen payload |
| Frappe silently falls back to Standard/latest format | Exact published registry lookup and template hash; absent, disabled, changed or ambiguous mapping fails closed |
| Template edit changes a retained output | Freeze resolved template content/hash at publication; retained snapshot downloads the original private artifact rather than rerendering |
| Browser injects template/data/actor/copy truth | Closed source adapter and operation-specific schemas; all controlled fields are server-derived |
| Private output leaks through File URL | URL-free API metadata and a Project/authority-checked BFF content route; exact private local File identity/hash validation |
| Duplicate command creates multiple controlled outputs | Actor + Project + operation + idempotency identity with canonical payload hash and sealed replay |
| Output is persisted without snapshot/audit or vice versa | One transaction and explicit snapshot -> private File -> output -> audit -> receipt sealing order with rollback proof |
| QR introduces an unreviewed dependency or network call | Repository-owned deterministic SVG implementation with fixed vectors; no package or external service |
| Generic foundation is mistaken for approved form coverage | No seeded mapping/format/provider activation; explicit unavailable UI; trace keeps `FR-PRN-003` decision-held |
| Reprint silently uses newer source/template | Return the exact retained artifact and append audit; never reuse snapshot identity for regenerated bytes |

## 7. Expected change surface

Backend and metadata:

- `apps/npi_core/npi_core/controlled_print/` domain, Frappe validation,
  repository, rendering and deterministic QR utility;
- `apps/npi_core/npi_core/controlled_print_api.py`;
- additive registry, registry-version, snapshot, output, access-event and
  command-idempotency DocTypes under the NPI Core module;
- bounded BFF/error/request-security route integration.

Contracts and ownership:

- closed capability/create/detail/content paths and schemas in
  `contracts/npi-api.openapi.yaml`;
- NPI-owned registry/snapshot/output/audit rows in
  `contracts/data-ownership.yaml`;
- no external event or ERP integration contract.

Frontend and language:

- reusable controlled-print data source and action/status surface, initially
  fail-closed without an approved mapping;
- focused unit/E2E cases and literal-English sources with direct `zh` and
  `zh-TW` translations;
- exact trilingual visual evidence only for the affected source fixture.

Verification/evidence:

- focused P5-06 domain/metadata/repository/API/contract/security/render tests;
- fixed QR vectors and PDF/hash/private-File/reprint proofs;
- disposable-Site verifier extension and bounded cleanup;
- task evidence, trace/controller updates and terminal Phase 5 release gate.

No production dependency or migration default is planned.

## 8. Changed-files to affected-tests plan

| Change boundary | Required affected checks |
|---|---|
| registry/snapshot/output domain | exact matching, ambiguity/absence, publication, canonical hash, frozen source/template, copy/delivery holds and state tests |
| additive DocTypes and guards | metadata validation, immutable/update/delete denial, no defaults, install/migrate twice and rollback tests |
| resolver/render/private File | source/version race, template drift, PDF bytes/hash, QR vectors, private local identity, no live rerender and fault rollback tests |
| authority/idempotency/audit | guest/IDOR/independent authority, authorization-before-resolution, replay/conflict/concurrent winner, atomic audit/receipt tests |
| BFF/OpenAPI/ownership | schema closure, CSRF, exact status/headers, no raw DocType/template/payload/File URL and ownership scans |
| reusable SPA surface/catalogs | unavailable/loading/ready/processing/replay/conflict/failure/download states, keyboard/focus/Axe and direct three-language coverage |
| controlled runtime | two migrations, synthetic format/mapping publication, exact snapshot/output/replay, source/template mutation resistance, route disable/recovery and cleanup |
| complete task | current-module suite, affected E2E/visual/i18n/security, trace/diff review, Level 2 and Phase 5 Level 3 Gate |

## 9. Implementation checkpoints

1. Pure registry/snapshot/output domain, closed OpenAPI/ownership vocabulary
   and additive guarded metadata.
2. Exact resolver, independent authority, idempotency/audit, immutable render,
   private output persistence and BFF content access.
3. Reusable SPA print affordance, direct three-language coverage and affected
   browser/visual evidence without a production mapping.
4. Controlled synthetic Site runtime, Level 2 Task Gate and Phase 5 Level 3
   `release-gate` review.

Each checkpoint runs Level 1 affected checks and exact diff review. Complete
ordinary CI precedes every controlled-Site boundary. P5-06 completes only
after Level 2 and the Phase 5 terminal Gate pass with diagnostics closed.

## 10. Rollback

Before retained controlled output exists, a disposable environment may revert
the P5-06 product checkpoint and migrate fresh. After retained snapshot,
output, access or idempotency history exists, rollback is a reviewed forward
fix: disable create/content routes, preserve every registry version, snapshot,
private File, output, event, audit and receipt, and keep safe metadata reads
available where authorized. Never delete or rewrite controlled history.

## 11. First implementation action

Implement and test only the pure registry/snapshot/output domain, closed
OpenAPI/ownership vocabulary and additive guarded metadata. Do not add a live
route, Frappe renderer, File write, user-facing action or synthetic runtime
fixture until exact mapping, hash, immutability and no-default invariants pass
their affected checks.
