# P6-01 Plan — Part, Tooling Requirement, Master, Applicability and Cockpit

Recorded: `2026-08-07T09:58:00Z`

Starting synchronized remote checkpoint:
`6b5d034fb2910d692f0499961fb5b30ab72cfd8f`

Starting exact-SHA ordinary CI:
`31167356140` (`PASS`; repository `92831145862`, visual `92831145989`,
controlled runtime correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/CONTRACT/METADATA FOUNDATION NEXT**

Requirements:

- `FR-TX-001`;
- `FR-TX-002`;
- `UX-004` foundation;
- `FR-TL-001` development-record foundation; and
- `FR-TL-003` Project/product/Part/Tooling relationship foundation.

Applicable Skills:

- `npi-domain-guard`;
- `frappe-safe-change`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Sources and existing-capability conclusion

The audit used the P6-00 Phase anchor, the five current trace rows, M5-01,
the matching DOCX and Pack requirements, `DOMAIN_MODEL.md`,
`TOOLING_AND_TRIAL.md`, the coarse Tooling ownership contract, the accepted
Project authorization/audit/idempotency patterns, and the current Tooling SPA
prototype.

Repository truth is:

- there is no live Part, Part Revision, Tooling Requirement, Tooling Master or
  Tooling Applicability aggregate, DocType, repository, BFF route or runtime;
- `frontend/src/pages/tooling-page.tsx` is explicitly in-memory and its
  release/acceptance actions persist no record or audit;
- the Project owner/current internal member/System Manager containment logic,
  request security, audit, actor-bound idempotency, exact optimistic version,
  route switch, error envelope and direct trilingual chain are reusable
  mechanisms, not inherited Tooling authority;
- the current ownership contract is correct at the NPI/ERP split but too
  coarse for the five P6-01 identities; and
- no approved production Tooling lifecycle, numbering rule, cross-tenant
  catalogue, deduplication key, external master-data adapter or ERP endpoint is
  present.

The safe additive path needs no architecture ADR. It must not convert the
prototype into a fake persisted success path or treat a Project, EBOM line,
spreadsheet row, Tooling Revision, physical Set or Trial as one convenience
Tooling record.

## 2. Scope and truthful completion boundary

P6-01 delivers one minimum complete vertical slice:

> open an authorized Project -> create one stable Part with an immutable exact
> Part Revision -> record why that Project needs Tooling -> create one logical
> Tooling Master or reference an already-authorized same-tenant Master -> append
> an exact versioned/effective Applicability that binds the Master to the
> Project and exact product/model/Part Revision context -> reopen the same live
> Tooling cockpit and observe the identities, applicability, provenance,
> permission and unavailable downstream truth

The slice proves non-collapse and shared-master reuse. It does not claim that
Revision, physical Set, cavity, Trial, manufacturing, cost, acceptance, Asset,
capacity or import requirements are complete. Accordingly, `FR-TX-001`,
`UX-004`, `FR-TL-001` and `FR-TL-003` remain foundation truth after P6-01;
later Phase 6 tasks supply their dependent aggregates and sections.

## 3. Non-scope and scoped holds

P6-01 does not install or infer:

- production Tooling Requirement, Revision or Set lifecycle states,
  transitions, skip/reopen/terminal rules or authorities (`DR-REC-010`);
- a production Tooling/Part numbering rule, naming series, customer/supplier
  deduplication rule or automatic merge;
- ownership/custody/repair authorization and physical Set intake (`P6-02`);
- Tooling Revision, specification, cavities, inserts, process chains or
  external identifiers (`P6-03`);
- supplier, PO, cost, defect, process baseline, capacity, acceptance, Asset,
  import/export or real ERPNext behavior (`P6-04..P6-08`);
- a production policy, fixture/default, customer workbook, adapter, endpoint,
  credential or outbound request; or
- generic Desk CRUD for normal users.

There is no shared lifecycle-state field in the P6-01 metadata or public
contract. Cockpit sections owned by later tasks return explicit
`unavailable`/empty capability truth with stable reasons; they never display
synthetic completion.

## 4. Frozen domain design

### 4.1 Stable identities

- `Part` is the tenant-stable NPI engineering identity. It is not an ERPNext
  Item and contains no formal Item success claim.
- `PartRevision` is an immutable, append-only exact version of one Part. A
  successor references the exact predecessor and advances only a guarded
  current-revision pointer.
- `ToolingRequirement` is a Project-scoped statement of need. Its explicit
  kind is one of the specification-defined new, customer-owned intake,
  copy/additional set, modification, repair or capacity-need concepts. It is
  neither the logical Tooling identity nor a physical Set.
- `ToolingMaster` is the stable same-tenant logical identity. It has no
  Project-owned lifecycle, Revision, Set count, formal Asset identity or
  mutable ERP state in P6-01.
- `ToolingApplicability` is an immutable append-only version of one normalized
  Master-to-Project/product/model/Part Revision relationship. It carries a
  stable logical relationship identity, exact version/predecessor, effectivity,
  source and snapshot hash. A new version is a new row; prior effectivity is
  retained.

### 4.2 Applicability and shared-master invariants

- An applicability always resolves the exact same tenant, authorized Project,
  Tooling Master, Part and Part Revision before insertion.
- Product/model references use the Project's existing typed reference truth;
  browser-supplied raw DocTypes, URLs, filters or arbitrary source systems are
  rejected.
- A stable normalized relationship key prevents two active representations of
  the same exact Master/Project/product/model/Part scope. Version/effectivity
  overlap fails closed; it never silently overwrites an earlier row.
- Reuse accepts only an exact Master identity the actor is already allowed to
  reference. A missing, cross-tenant, unrelated or ambiguous identity is the
  same unavailable response; no global Tooling catalogue is disclosed.
- A shared Master produces multiple Applicability relationships, not cloned
  Master records. A copy/additional-set Requirement does not increment a
  quantity field; P6-02 creates exact physical Sets.

### 4.3 Authorization and command boundary

- Route/method/CSRF and Project authorization run before protected Part,
  Requirement, Master or Applicability resolution.
- Internal Project owner, one exact current enabled internal Project member and
  same-tenant System Manager may view the Project-scoped cockpit projection.
  Guest, Website/external, tenant mismatch, duplicate/ambiguous membership and
  unrelated users receive one indistinguishable unavailable response.
- Until an approved Tooling authority policy exists, only the same-tenant
  internal System Manager may create Part/Revisions, Requirements, Masters or
  Applicabilities. The BFF exposes the resulting `can*` capability truth; the
  SPA does not infer authority from visibility.
- Every mutation is a narrow BFF command with actor-bound idempotency, exact
  current version where applicable, request/trace identity, one transaction,
  append-only audit and sealed replay. The browser cannot submit tenant,
  actor, source ownership, hash, internal relationship key or audit fields.
- All queries and errors are bounded and `private, no-store`; no protected
  identifier or validation detail leaks before authorization.

The System Manager-only mutation posture is a fail-closed implementation
boundary, not a new production business role policy. Broader lifecycle or
approval authority remains held by `DR-REC-010`.

## 5. Planned closed BFF contract

| Method and path | Purpose |
|---|---|
| `GET /projects/{projectId}/tooling` | bounded Project Tooling worklist/cockpit summaries, capabilities and explicit unavailable downstream sections |
| `GET /projects/{projectId}/tooling/{toolingMasterId}` | one authorized Master plus exact Requirement, Part Revision and Applicability history/projection |
| `POST /projects/{projectId}/parts` | create stable Part plus immutable initial Revision |
| `POST /projects/{projectId}/parts/{partId}/revisions` | append an exact immutable successor Part Revision |
| `POST /projects/{projectId}/tooling-requirements` | record one exact Project need without lifecycle mutation |
| `POST /projects/{projectId}/tooling-masters` | create one same-tenant logical Master with no Revision/Set/Asset claim |
| `POST /projects/{projectId}/tooling-applicabilities` | append initial or successor exact version/effectivity for an authorized Master and scope |

All request/response/error objects are closed and bounded. Collections use a
stable signed keyset or an explicit bounded initial result; no unbounded Desk
list is exposed. The stable unavailable family includes
`TOOLING_UNAVAILABLE`, `TOOLING_ROUTES_DISABLED`,
`TOOLING_VERSION_CONFLICT`, `TOOLING_APPLICABILITY_CONFLICT`,
`TOOLING_REFERENCE_UNAVAILABLE` and the existing authentication, CSRF,
validation, idempotency and internal-error families.

## 6. Persistence and ownership plan

The additive metadata boundary is:

- `NPI Engineering Part`;
- `NPI Engineering Part Revision`;
- `NPI Tooling Requirement`;
- `NPI Tooling Master`;
- `NPI Tooling Applicability`; and
- `NPI Tooling Command Idempotency`.

DocTypes use UUID identities, explicit tenant/Project containment, immutable or
guarded fields, no rename/delete, no normal-user export/print/email and no
generic normal-user create/write. `ToolingApplicability` stores immutable
logical identity/version/predecessor/effectivity/snapshot truth rather than a
mutable child-table convenience copy.

`contracts/data-ownership.yaml` will gain exact rows for the P6-01 objects:
NPI One owns engineering Part/Revision, Requirement, logical Master and
Applicability truth; ERPNext Item/Asset/Supplier/PO/cost/location/maintenance
truth remains unavailable/read-only external ownership. No mapping is written
without a later confirmed execution response.

The metadata migration is additive and idempotent. It creates no business row,
policy, fixture, mapping, adapter or external identifier and performs no
backfill from EBOM, Project references, prototype fixtures or spreadsheets.

## 7. Live cockpit and i18n plan

- Exact UUID Tooling routes use a new server-backed data source; the existing
  `TL-26018-01` prototype remains explicit reference evidence until the live
  route has passed its own matrix.
- The live surface keeps the industrial Object Page: compact identity/source
  header, one conditional primary action at most, stable object tree/worklist,
  central applicability/Part revision table and docked inspector.
- It displays current exact identities, applicability version/effectivity,
  source/editability, next available action and downstream capability truth.
  It must not render the prototype's release/acceptance commands against live
  data while lifecycle policy is unavailable.
- Normal, empty, loading, no-permission, read-only, unavailable, validation,
  version/applicability conflict, processing, retryable/final and unsaved-
  context states are explicit. Keyboard, focus, labels and non-color-only
  status remain mandatory.
- Every new visible source string is literal English through `t()` and receives
  complete direct `zh` and `zh-TW` catalog coverage. No new translation stack
  or mixed-language fallback is permitted.

## 8. Planned checkpoints

1. **Domain/contract/metadata foundation** — pure invariants, six additive
   guarded DocTypes, ownership rows, closed OpenAPI schemas and metadata/
   contract/security tests; no route or live UI.
2. **Repository/BFF checkpoint** — authorized Project-first queries and narrow
   commands, transaction/idempotency/audit, route switch and exact API tests.
3. **Live cockpit checkpoint** — server data source, dense SPA projection,
   direct trilingual coverage, accessibility, state and affected visual tests.
4. **Controlled runtime and Task Gate** — disposable-Site create/reuse/
   applicability/replay/rollback/IDOR/route-disable proof, complete ordinary CI
   and P6-01 Level 2 review.

Complete ordinary CI is required before a controlled-Site boundary.
Diagnostics remain closed unless an opaque exact-SHA failure starts one
governed response-neutral diagnostic cycle under the standing authority.

## 9. Requirement -> code -> test -> evidence

| Requirement | Planned delivery | Required evidence |
|---|---|---|
| `FR-TX-001` | distinct Part/Revision, Requirement, Master and Applicability now; explicit unavailable Revision/Set/Trial dependencies | non-collapse domain/metadata/contract/runtime tests and foundation trace truth |
| `FR-TX-002` | one Master referenced by multiple versioned/effective Project/product/model/Part relationships | reuse/no-clone, stable relationship key, overlap/version, cross-tenant/IDOR and runtime tests |
| `UX-004` | live dense identity/applicability cockpit with honest downstream capabilities | component/state/accessibility/direct trilingual/browser/visual evidence; remains foundation until later sections are live |
| `FR-TL-001` | Project Tooling development Requirement and logical Master foundation | need-kind, provenance, Project containment and no-fake-ownership/Asset tests |
| `FR-TL-003` | multi-Part/multi-Master Project relationships and exact Part Revision applicability | cardinality, exact-revision, shared-master and Project cockpit tests; cavity/Trial trace remains later-task foundation |

Final P6-01 evidence will be recorded in
`implementation/evidence/phase-6/p6-01-validation.md`.

## 10. Changed-files -> affected-tests

| Expected change surface | Minimum direct checks |
|---|---|
| `apps/npi_core/npi_core/tooling/**`, `tooling_api.py` | new domain/repository/API/security suites and focused compilation |
| six additive DocTypes, hooks/patches only if required | metadata/controller immutability, denied generic CRUD/delete, additive/idempotent Site migration |
| `bff.py`, request-security/error/route-switch integration | method/CSRF/direct-handler/IDOR/unavailable/error-envelope regressions |
| OpenAPI and data ownership | parse/reference/closed-schema/route/ownership assertions |
| Project containment and typed references | existing Project/member/reference plus Document/EBOM authorization regression |
| Tooling data source/router/page/app wiring | parser/transport/component/type/lint/boundary and prototype-isolation tests |
| styles and translation catalogs | complete direct `zh`/`zh-TW`, terminology/mixed-language, accessibility and affected visual matrix |
| controlled runtime verifier/workflow scope | migrations, create/reuse/non-collapse, idempotent replay/conflict, audit, rollback, IDOR and route disable/recovery |
| implementation trace/evidence | Requirement uniqueness, Task Diff, YAML/source/evidence and `git diff --check` |

## 11. Migration, rollback and exit

Before retained P6-01 history exists, a disposable environment may restore
checkpoint `6b5d034`. After retained rows exist, rollback sets the dedicated
Tooling route switch to disabled, preserves every Part/Revision, Requirement,
Master, Applicability, audit and idempotency row, and deploys a reviewed
forward repair. It never merges/deletes Masters, rewrites effectivity or
relabels an ERP mapping.

The audit passes. Autopilot may start only checkpoint 1, the pure
domain/contract/additive-metadata foundation. P6-02 and every later lifecycle,
physical Set, ERP, import and export behavior remain inactive.
