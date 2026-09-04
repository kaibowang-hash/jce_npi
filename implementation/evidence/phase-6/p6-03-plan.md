# P6-03 Plan — Tooling Revisions, Specifications, Cavities, Inserts and Process Chain

Recorded: `2026-08-07T22:10:17Z`

Starting synchronized checkpoint:
`36e2b9b16f4168f2d04e84f98dd370bd2f39c635`

Starting exact-SHA ordinary CI:
`31222318731` (`PASS`; repository `93009313398`, visual `93009313360`,
controlled runtime `93009313685` correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/CONTRACT/METADATA FOUNDATION NEXT**

Requirements:

- `FR-TX-004..008`;
- `FR-TL-002`;
- `FR-TL-003`; and
- `FR-TL-006`.

Applicable Skills:

- `repo-discovery`;
- `npi-domain-guard`;
- `frappe-safe-change`;
- `xlsx-tooling-import`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Sources and existing-capability conclusion

The audit used the Phase 6 requirement anchor, M5-03, all eight current trace
rows, the matching DOCX and Pack requirements, `DOMAIN_MODEL.md`,
`TOOLING_AND_TRIAL.md`, the accepted reconciliation decisions, the P6-01 and
P6-02 Level 2 evidence, the ownership contract, the passive XLSX inspector,
the live Tooling BFF/contracts and the strict Tooling SPA data source.

Repository truth is:

- P6-01 provides exact Part Revision, Requirement, Master and versioned
  Applicability identity; P6-02 adds independently immutable physical Sets,
  but no Tooling Revision, cavity, insert, process-chain or controlled Part
  specification record exists;
- the current cockpit and Set response intentionally return
  `tooling_revision_not_delivered`; the strict frontend parser rejects any
  invented exact Revision projection;
- `EngineeringPartRevision` is immutable and already provides the exact Part
  version boundary, while its material/color/compliance/process ownership row
  remains explicitly unavailable for P6-03;
- `NPI Tooling Set` is an immutable P6-02 snapshot. Source-Revision truth
  cannot be introduced by rewriting or rehashing that row; an append-only
  exact binding projection is required;
- no Tooling lifecycle policy exists. `DR-REC-010` still blocks exact
  Requirement/Revision/Set state codes, transitions, release/supersession
  commands and business authorities, but does not block immutable revision
  identity, engineering specification structure or source provenance;
- the 531-line XLSX inspector and adversarial tests are passive parser-safety
  evidence only. The reviewed 43-column mapping is not a production mapping
  and P6-03 must not activate an import, formula result or workbook-derived
  relationship; and
- formal Supplier, ERP Asset/location/execution, combined Trial results and
  production impact-workflow truth remain later-task responsibilities.

The safe path is additive and needs no architecture ADR. Exact lifecycle and
later execution capabilities remain unavailable rather than being inferred
from a revision number, cavity state, source identifier or free-text remark.

## 2. Scope and truthful completion boundary

P6-03 delivers this minimum complete vertical slice:

> open an authorized Project and Tooling Master -> select exact current Part
> Applicabilities -> record one immutable controlled Part specification ->
> create an immutable Tooling Revision containing unit-bearing engineering
> specifications, exact controlled Document Revision provenance, exact
> cavity-to-Applicability mapping, versioned insert applicability and
> one-to-many external identities -> create an ordered
> versioned parent/second-shot/overmold process chain from exact Part and
> Tooling Revision references -> bind one previously unbound physical Set to
> its exact source Tooling Revision without changing the Set snapshot ->
> reopen the live workspace and observe the complete structure plus honest
> unavailable release, Supplier, ERP and combined-Trial capabilities

The slice proves structure and provenance, not manufacturing authorization.
Creating a revision does not approve or release it. A source binding records
which engineering revision a physical Set came from; it does not declare that
revision released or authorize manufacturing or Trial use.

Final trace status is evidence-driven. In particular:

- cavity identity/mapping can be live while cavity-level Trial/defect/capacity
  results remain Phase 7/P6-05 dependencies;
- material/color/compliance truth can be live while automatic impact-case
  creation remains Phase 9; and
- immutable Revision history can be live while design approval/release and
  formal lifecycle commands remain held by `DR-REC-010`.

## 3. Non-scope and scoped holds

P6-03 does not install or infer:

- exact Tooling Requirement, Revision or Set lifecycle states, transitions,
  skip/reopen/terminal rules, release/supersession commands or authorities
  (`DR-REC-010`);
- a claim that a Tooling Revision is approved, released or valid as a
  manufacturing/Trial basis;
- a formal Supplier, make/buy decision, milestone, PO, receipt, invoice,
  actual cost or supplier portal (`P6-04` and ERPNext);
- an ERPNext Asset ID/state, location, movement, shot count, maintenance,
  execution request, endpoint, credential or successful target result;
- a combined Trial, cavity-level Trial result, defect, capacity result or
  process baseline (`P6-05`, Phase 7 and Phase 8);
- an automatic impact assessment, change case, blocker, severity or color
  policy for material/color/compliance changes;
- a production Tooling-list mapping, workbook upload/API, row transformation,
  formula execution, external-content fetch or workbook-derived auto-binding;
- a general-purpose arbitrary specification key, arbitrary source system,
  raw private-file URL, CAD geometry comparison or external signature; or
- a production policy, fixture/default, adapter, dependency or external
  mutation.

P6-03 permits one initial exact Set-source binding only. Rebinding a physical
Set after modification or supersession requires a later approved policy and
is not inferred from the newest Tooling Revision.

## 4. Frozen domain design

### 4.1 Immutable Tooling Revision and specification

- `ToolingRevision` is an append-only engineering snapshot for one exact
  same-tenant Tooling Master. It has an immutable UUID, sequential revision
  number, bounded label, exact predecessor UUID/hash, actor/request/trace
  provenance and canonical snapshot hash.
- The repository locks and validates the authorized Master, exact current tip
  and expected predecessor before inserting the next revision. Concurrent or
  branched revision creation fails closed; no mutable `latest` identity or
  browser-authored revision number is trusted.
- The snapshot contains a closed, unit-bearing `ToolingSpecification` for the
  required core semantics: Tooling type, mold-base/core materials, hardness,
  surface treatment, cavity count, hot-runner facts, dimensions, weight,
  clamp/tie-bar/injection/machine requirements, target cycle, target life,
  warranty, customer standards/interfaces, spares and delivery documents.
- Numeric facts retain decimal text, unit and source context. The server uses
  no hidden tonnage, cycle, life, cavity or capacity default. Unsupported
  mold-type extensions remain unavailable until a controlled schema/code is
  approved; arbitrary JSON keys are rejected.
- No lifecycle `status`, `released`, `approved` or convenience manufacturing
  flag exists in this task. The response exposes the lifecycle capability as
  unavailable with `lifecycle_policy_unavailable`.
- Optional design provenance references exact authorized immutable controlled
  Document Revision UUIDs and snapshot hashes. It never returns a raw private
  file URL, performs CAD geometry comparison or inherits a Document lifecycle
  decision as Tooling Revision approval/release.

### 4.2 Cavity and insert structure

- Each revision contains bounded, independently UUID-identified cavity rows.
  A row has an exact cavity identifier, one exact current/effective
  `ToolingApplicability`, its exact Part Revision, and the factual structural
  state `enabled` or `sealed`.
- Cavity identifiers are unique within one Revision and the declared cavity
  count equals the exact row set. Cross-Project, cross-Master, stale,
  overlapping or unrelated Applicability references fail closed.
- Cavity rows expose a stable future Trial/defect/capacity reference identity,
  but P6-03 returns those result capabilities as unavailable and stores no
  fabricated result.
- Each `InsertApplicability` row has its own UUID, insert/changeover code,
  immutable version, exact applicable Part/Applicability and optional model
  reference, changeover duration with unit, and factual validation state
  `not_validated` or `validated`.
- A validated insert row requires exact internal actor/time/reason evidence in
  the immutable snapshot. This factual validation flag is not a Tooling
  Revision lifecycle approval or release.

### 4.3 Controlled Part specification and external identities

- `PartControlledSpecification` is one immutable specification snapshot for
  one exact same-Project Part Revision. A later material/color/compliance
  change requires a new Part Revision and a new exact specification; the old
  snapshot is never overwritten.
- Closed specification kinds cover material family, grade, trademark, color,
  color masterbatch, FDA/compliance facts and secondary process. Every entry
  has an independent UUID, normalized value/code, raw source value, source
  identity/effectivity and optional unit without treating customer text as
  authority.
- Part external identities are retained in the Part specification and Tooling
  external identities in the Tooling Revision. Each one-to-many identity has
  type (`customer`, `sn`, `kw`, `th` or `supplier_reference`), value, source
  and effectivity. `supplier_reference` is provenance only and never becomes
  a formal ERPNext Supplier.
- External values are never primary keys. Duplicate/effectivity conflicts are
  explicit, and multi-valued raw cells are not auto-split by P6-03.

### 4.4 Ordered process chain

- `ToolingProcessChainRevision` is a Project-scoped append-only version with
  immutable UUID, logical chain UUID, sequential version, exact predecessor
  and canonical snapshot hash.
- Its bounded steps are strictly ordered and independently identified. Each
  step states `primary_molding`, `second_shot` or `overmold`, exact input and
  output Part Revisions, exact Tooling Revision, parent/overmold relationship
  and unit-bearing machine requirement.
- Step order is contiguous, references are Project-authorized and the chain
  graph is acyclic. Blank Tooling numbers, remarks, concatenated codes and
  unconfirmed workbook relationships are rejected as authority.
- Combined Trial planning/results remain explicitly unavailable until Phase 7;
  process-chain structure does not claim a successful combined Trial.

### 4.5 Physical Set source binding

- `ToolingSetRevisionBinding` is append-only and records the initial exact
  source Tooling Revision for one authorized physical Set. It contains its own
  UUID, Project/Master/Set/Revision identities, exact snapshot hashes,
  actor/request/trace provenance and binding reason.
- The command succeeds only when the Set has no prior binding and all
  identities share Project, tenant and Master containment. It never rewrites
  `NPI Tooling Set`, its hash, intake history or evidence.
- With P6-03 enabled, the Set response returns a closed union: the exact source
  Revision projection when bound, otherwise the existing
  `tooling_revision_not_delivered` unavailable value. Disabling P6-03 restores
  the unavailable projection without hiding or deleting retained bindings.

### 4.6 Authorization and command boundary

- Method/CSRF and Project authorization run before Master, Revision, Part,
  Applicability, Set or chain resolution.
- Same-tenant authorized internal users may read. Until approved Tooling
  policy exists, only internal System Manager may create specification,
  Revision, process-chain or Set-binding records; the BFF returns exact
  capability truth.
- All mutations use actor-bound idempotency, exact predecessor/current-version
  checks, one transaction, append-only audit and sealed replay. Browser input
  cannot provide tenant, actor, hashes, internal keys, audit fields or generic
  DocType/filter/SQL values.
- Collections and nested structures are bounded and stably ordered. Protected
  and absent identities remain indistinguishable unavailable responses with
  `private, no-store`.

## 5. Planned additive BFF contract

P6-01/P6-02 paths and meanings remain closed. P6-03 adds only:

| Method and path | Purpose |
|---|---|
| `GET /projects/{projectId}/tooling/{toolingMasterId}/revisions` | bounded immutable Revision summaries and exact capabilities |
| `GET /projects/{projectId}/tooling/{toolingMasterId}/revisions/{revisionId}` | exact specification, cavities, inserts, external IDs and lineage |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/revisions` | create the next immutable Revision from one exact predecessor |
| `GET/POST /projects/{projectId}/parts/{partId}/revisions/{partRevisionId}/controlled-specification` | read or create the one immutable controlled Part specification |
| `GET/POST /projects/{projectId}/tooling-process-chains` | read bounded chain revisions or create one exact ordered chain revision |
| `GET /projects/{projectId}/tooling-process-chains/{processChainRevisionId}` | read one authorized exact process-chain revision |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/revision-binding` | append the initial exact Set-source Revision binding |

The existing cockpit `downstream.revision` becomes an exact available
capability only while the independent P6-03 route switch is enabled. Existing
Set `sourceRevision` becomes the closed exact/unavailable union described
above. Lifecycle, Supplier, ERP and Trial capability fields remain unchanged
and unavailable.

## 6. Persistence and ownership plan

Checkpoint 1 adds only four guarded DocTypes:

- `NPI Tooling Revision`;
- `NPI Part Controlled Specification`;
- `NPI Tooling Process Chain Revision`; and
- `NPI Tooling Set Revision Binding`.

Strict nested specification/cavity/insert/external-identity/process-step
objects are retained as bounded canonical immutable snapshots with independent
child UUIDs and exact hashes. Repository queries expose typed structures and
bounded exact searches; generic Desk CRUD, export, print and arbitrary JSON
mutation remain denied.

The existing `NPI Tooling Command Idempotency` and append-only audit mechanism
are reused with four exact operation/target pairs. The shared receipt
controller whitelist and administrator-visible translations gain only those
closed values.

`contracts/data-ownership.yaml` activates NPI One ownership for Tooling
Revision/specification/cavity/insert/process-chain truth, exact Part controlled
specification and append-only Set-source binding. Formal Supplier and
Asset/location/maintenance remain ERPNext-owned; lifecycle remains
`FUTURE_APPROVED_TOOLING_POLICY`.

Migration is additive and idempotent. It creates no business row, Revision,
specification, chain, binding, policy, default, backfill, mapping, adapter or
external connection. Existing Tooling Masters, Part Revisions and Sets remain
byte-for-byte valid and show unavailable P6-03 truth until an authorized
command appends it.

## 7. Live Tooling workspace and i18n plan

- The selected-Master workspace gains a dedicated dense Revision/specification
  surface without replacing the P6-01 cockpit or P6-02 Set/intake surface.
- Revision tree/table/inspector views show lineage, core unit-bearing
  specifications, cavities, inserts, external IDs and exact source hashes.
  A Project-level process-chain view shows ordered parent/second-shot/overmold
  steps and machine requirements.
- Part controlled specification is edited only against an exact current Part
  Revision. The Set inspector exposes a one-time source-binding action only
  when the exact capability is available and the Set remains unbound.
- One context has at most one primary action. Lifecycle release/approve,
  Supplier, ERP, Trial results and impact actions remain visible unavailable
  states rather than enabled placeholders.
- Normal, empty, loading, no-permission, read-only, unavailable, validation,
  predecessor/effectivity conflict, processing and retry states are explicit.
  Keyboard, focus, labels and non-color-only state remain mandatory.
- Every visible source string is literal English through `t()` with direct,
  complete `zh` and `zh-TW` coverage. No missing-translation fallback,
  sentence concatenation or translated contract enum is allowed.

## 8. Planned checkpoints

1. **Domain/contract/metadata foundation** — pure Revision/specification/
   cavity/insert/external-identity/process-chain/binding invariants, four
   guarded additive DocTypes, ownership rows, receipt values, closed OpenAPI
   schemas and domain/metadata/contract/security tests; no active route.
2. **Repository/BFF checkpoint** — Project-first bounded reads and narrow
   commands, exact containment/effectivity/current-tip checks, transaction,
   idempotency, audit, independent route switch and API/IDOR tests.
3. **Live workspace checkpoint** — strict data source, dense Revision/
   specification/cavity/insert/process-chain UI, Set binding, complete
   trilingual/accessibility/state and affected visual tests.
4. **Controlled runtime and Task Gate** — disposable-Site immutable successor,
   cavity/insert/specification/external-ID/process-chain/binding persistence,
   replay/conflict/rollback/IDOR and independent route-disable proof, complete
   ordinary CI and P6-03 Level 2.

Complete ordinary CI is mandatory before a controlled-Site boundary.
Diagnostics stay closed unless an opaque exact-SHA failure activates one
governed response-neutral diagnostic cycle under standing authority.

## 9. Requirement to code to test to evidence

| Requirement | Planned delivery | Required evidence |
|---|---|---|
| `FR-TX-004` | exact cavity UUID/identifier to current/effective Applicability and Part Revision, enabled/sealed structure; later Trial/defect/capacity result unavailable | cavity uniqueness/count/containment, stale and cross-Project denial, UI and runtime; truthful foundation/completion status from evidence |
| `FR-TX-005` | immutable ordered primary/second-shot/overmold chain with exact Part/Tooling Revisions and machine requirements; combined Trial unavailable | ordering/acyclic/reference/blank-authority rejection, UI and runtime |
| `FR-TX-006` | versioned insert/changeover rows with exact applicability/model, duration and evidence-bound validation fact | insert version/query/validation/effectivity tests, UI and runtime |
| `FR-TX-007` | one-to-many Part and Tooling external identities with source/effectivity, never primary identity | duplicate/effectivity/raw-value/IDOR tests, UI and runtime |
| `FR-TX-008` | immutable material/grade/trademark/color/masterbatch/compliance/secondary-process links to exact Part Revision; automatic impact action unavailable | controlled-kind/raw-provenance/exact-revision/immutability tests, UI and runtime |
| `FR-TL-002` | closed unit-bearing core Tooling specification in each immutable Revision | type/unit/boundary/hash tests, trilingual dense inspector and runtime |
| `FR-TL-003` | Project/Master/Part Applicability extended by exact cavity mapping; later Trial result unavailable | cross-Project/reference/cavity mapping and runtime evidence; retained foundation status where later dependencies remain |
| `FR-TL-006` | immutable Tooling Revision lineage and exact controlled Document Revision provenance; approval/release commands remain policy-held | successor/conflict/hash/document-containment/audit and explicit unavailable lifecycle evidence; foundation status only |

Final evidence will be recorded in
`implementation/evidence/phase-6/p6-03-validation.md`.

## 10. Changed-files to affected-tests

| Expected change surface | Minimum direct checks |
|---|---|
| `tooling/domain.py` | Revision lineage/hash, controlled Document Revision provenance, closed spec/unit facts, cavity count/mapping, insert versions, external identity effectivity, Part spec, process-chain order/acyclicity and Set binding |
| four additive DocTypes and Tooling validation | exact parent/tenant containment, immutable snapshots, denied generic CRUD/delete, receipt values and additive/idempotent migration |
| OpenAPI and data ownership | parse/reference/closed schema/new paths/exact-or-unavailable Set projection/ownership/no-fake-release-or-ERP assertions |
| Tooling repository/API/security/BFF | Project-first authorization, current tip, exact Part/Applicability/Master/Set containment, replay/conflicts/audit/rollback/IDOR and independent switch |
| Tooling data source and live workspace | strict parser/transport, revision/spec/cavity/insert/chain/binding operational states, accessibility and prototype isolation |
| catalogs/styles | literal English plus direct `zh`/`zh-TW`, terminology/mixed-language, industrial boundary and affected visual matrix |
| runtime verifier/workflow | two revision tips/conflict, Part spec, cavities/inserts/IDs, ordered overmold chain, initial Set binding, retained predecessors, replay/rollback/IDOR and route disable/recovery |
| controller/evidence | YAML, V1.2 reconciliation, Task Diff Review and `git diff --check` |

## 11. Migration, rollback and exit

Before retained P6-03 rows exist, a disposable environment may restore the
starting checkpoint and migrate fresh. After retained rows exist, rollback
disables only P6-03 routes and exact projections, preserves every Revision,
specification, cavity/insert/external identity, process chain, Set binding,
audit and idempotency receipt, and uses a reviewed forward repair. It never
rewrites a P6-01 Master/Part/Applicability, a P6-02 Set/intake/evidence record,
or a referenced external/ERP object.

The audit passes. Autopilot may start only checkpoint 1, the pure domain,
closed contract and additive metadata foundation. Repository routes, live SPA
activation and controlled-Site execution remain inactive until their preceding
checkpoints pass. P6-04 and later behavior remains inactive.
