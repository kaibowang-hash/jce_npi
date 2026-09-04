# P6-02 Plan — Customer-owned Intake and Physical Tooling Sets

Recorded: `2026-08-07T17:09:06Z`

Starting synchronized checkpoint:
`49a8931d0e9ab66ea132f232f4eb144879fd4ae0`

Starting exact-SHA ordinary CI:
`31200277175` (`PASS`; repository `92938356572`, visual `92938356975`,
controlled runtime `92938357521` correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/CONTRACT/METADATA FOUNDATION NEXT**

Requirements:

- `FR-TX-003`; and
- `FR-TL-004`.

Applicable Skills:

- `repo-discovery`;
- `npi-domain-guard`;
- `frappe-safe-change`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Sources and existing-capability conclusion

The audit used the Phase 6 requirement anchor, M5-02, the two current trace
rows, the matching DOCX and Pack requirements, `DOMAIN_MODEL.md`,
`TOOLING_AND_TRIAL.md`, the exact P6-01 aggregate/runtime evidence, the
ownership contract, accepted File Revision controls and the live Tooling SPA.

Repository truth is:

- P6-01 provides live, distinct Requirement, Master and Applicability
  identities, Project-first authorization, actor-bound idempotency, audit and
  a dedicated route switch, but no physical Set or intake record exists;
- `NPI File Revision` already provides an exact private file identity, content
  hash, scan truth and Project/tenant containment. P6-02 may reference a live
  clean revision; it must not expose raw private URLs, mutate customer files,
  bypass the controlled Document workflow or claim signature verification;
- Project references can prove one exact authorized customer identity. There
  is no authorized live Supplier projection for P6-02 to relabel as formal
  supplier truth;
- the current cockpit explicitly returns `physical_set_not_delivered` and has
  no Set/intake data source, command or durable evidence surface;
- `DR-REC-010` still blocks exact Requirement/Revision/Set lifecycle states,
  transitions and authorities, but does not block stable Set identity,
  ownership/custody provenance or immutable intake evidence; and
- source Tooling Revision belongs to P6-03, formal Supplier projection to
  P6-04, and Asset/state/location/maintenance truth to ERPNext/P6-06/Phase 8.

The safe path is additive and needs no architecture ADR. It must expose those
later fields as unavailable instead of inventing a status, source Revision,
Supplier, location or Asset value.

## 2. Scope and truthful completion boundary

P6-02 delivers this minimum complete vertical slice:

> open an authorized Project and logical Tooling Master -> select an exact
> `customer_owned_intake` Requirement and the Project's exact customer
> reference -> create one independently identified physical Tooling Set ->
> record an immutable arrival intake with transport, custody responsibility,
> repair authorization, return conditions, accessories and all five required
> inspection areas -> retain each difference as an independently identified
> issue -> attach exact clean private arrival-photo/inspection evidence and,
> when requested, append exact customer-confirmation evidence -> reopen the
> live Tooling workspace and observe the Set, intake, evidence, permissions
> and unavailable downstream ERP/Revision/lifecycle truth

The same Set command also proves `copy_or_additional_set` non-collapse by
creating each physical copy in a separate request with a separate immutable
UUID. A planned or copied quantity is never accepted as a substitute for Set
records.

P6-02 can technically verify `FR-TL-004`. `FR-TX-003` becomes a technically
verified foundation for independent physical identity and per-Set serial/
provenance; its exact source Tooling Revision, formal Supplier, approved Set
lifecycle state, ERP location and Asset mapping remain explicitly dependent on
P6-03/P6-04/P6-06/Phase 8 and cannot be claimed complete here.

## 3. Non-scope and scoped holds

P6-02 does not install or infer:

- exact Set lifecycle state codes, transitions, skip/reopen/terminal rules or
  business authorities (`DR-REC-010`);
- Tooling Revision/specification, release or supersession (`P6-03`);
- a formal Supplier, PO, receipt, invoice, actual cost or supplier portal
  (`P6-04` and ERPNext);
- an ERPNext Asset ID/state, formal physical location, movement, shot count,
  maintenance or successful execution result (`P6-06` and Phase 8);
- a customer login, electronic signature, legal acceptance rule, automatic
  approval or external notification;
- an automatic Domain WorkItem, lifecycle blocker or severity policy for an
  intake difference;
- customer-file upload, overwrite, release, deletion, remote fetch or raw
  private-file URL exposure; or
- a production policy, fixture/default, workbook mapping, adapter, endpoint,
  credential or external mutation.

Serial numbers remain recorded provenance, not global identities or an
unapproved deduplication key. Duplicate-looking serials never merge Sets.

## 4. Frozen domain design

### 4.1 Physical Set identity

- `ToolingSet` is one touchable physical copy with a tenant-stable immutable
  UUID. It references one exact same-tenant Master, one authorized Project and
  one exact `customer_owned_intake` or `copy_or_additional_set` Requirement.
- Each create command creates exactly one Set. It accepts no quantity and does
  not update a Set counter on Requirement or Master.
- The physical serial is required and retained exactly after bounded
  normalization, but the UUID remains identity. The server does not infer a
  tenant-wide or Master-wide serial uniqueness rule.
- For customer-owned intake, ownership is proved by the Requirement kind and
  one exact customer reference already attached to the Project. Browser input
  cannot supply an arbitrary source system, DocType or customer outside that
  Project.
- Required custody responsibility, repair-authorization reference and return
  conditions are immutable provenance statements. They record the supplied
  boundary without inventing an authorization decision engine.
- Lifecycle, source Tooling Revision, formal Supplier, ERP location and Asset
  projections are separately returned as explicit unavailable capabilities.
  No convenience `status` field is added.

### 4.2 Intake and difference truth

- `ToolingIntake` is an immutable append-only version for one exact Set. The
  initial version records transport provider/reference, arrival time, custody
  handover, accessories, inspections, differences, actor/request/trace and a
  canonical snapshot hash. A correction is a successor version; it never
  overwrites the earlier arrival snapshot.
- Accessory and difference rows receive independent UUIDs inside the bounded
  immutable snapshot. Planned, declared and received quantities remain
  separate; free-text remarks never replace a quantity difference.
- Exactly the required inspection categories are structured:
  `appearance`, `water_circuit`, `hot_runner`, `electrical` and `safety`.
  Each records an observation and whether a difference was observed. P6-02
  defines no pass/fail lifecycle state, color or automatic blocker.
- Every recorded difference identifies its source inspection/accessory row,
  description and whether customer confirmation is required. The issue list
  is visible and immutable; it is not silently converted into a generic
  WorkItem or an approved customer decision.

### 4.3 Retained evidence and confirmation

- `ToolingIntakeEvidenceReference` is append-only and binds an exact intake
  version to an exact live, private, clean, same-tenant/same-Project `NPI File
  Revision`. It snapshots the File Revision UUID/version, SHA-256, Frappe
  content hash, MIME type, size and attachment role without returning a raw
  URL.
- Allowed evidence roles are closed to arrival photo, transport document,
  accessory document, inspection evidence and customer confirmation. A
  customer-confirmation reference also identifies the exact difference UUIDs
  it addresses.
- Recording customer-confirmation evidence proves only that the internal actor
  retained the supplied exact evidence for the exact differences. It does not
  assert an electronic signature, external identity verification or lifecycle
  approval.
- File content, scan state and released state are never mutated by P6-02.
  Missing, dirty, cross-Project, stale, ambiguous or non-live file identities
  fail closed with the same unavailable boundary.

### 4.4 Authorization and command boundary

- Method/CSRF and Project authorization execute before Master, Requirement,
  Set, Intake, difference or File Revision resolution.
- P6-01 Project visibility rules remain unchanged. Until a production Tooling
  authority policy exists, only the same-tenant internal System Manager may
  create Sets, intake versions or evidence references. The BFF exposes exact
  `can*` capability truth; the SPA never infers write authority from read
  access.
- Every mutation uses actor-bound idempotency, exact current version where
  applicable, request/trace identity, one transaction, append-only audit and
  sealed replay. Browser input cannot provide tenant, actor, hashes, internal
  keys, audit fields or raw Frappe file identities.
- Queries and errors stay bounded and `private, no-store`; unrelated and
  cross-tenant identities remain indistinguishable unavailable responses.

## 5. Planned additive BFF contract

The P6-01 routes and response meanings remain unchanged. P6-02 adds only these
closed subresources under an already-authorized Master:

| Method and path | Purpose |
|---|---|
| `GET /projects/{projectId}/tooling/{toolingMasterId}/sets` | bounded physical Set summaries, current intake/evidence counts, capabilities and explicit unavailable Revision/ERP fields |
| `GET /projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}` | one authorized Set with immutable intake versions, differences and URL-free evidence metadata |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/sets` | create exactly one independent Set from one exact eligible Requirement |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/intakes` | append an initial or successor immutable intake version |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/intakes/{intakeId}/evidence` | append one exact retained File Revision reference, including scoped customer-confirmation evidence |

Collections are explicitly bounded and stably ordered; no raw Desk list,
DocType, filter, SQL fragment, URL or arbitrary source system is accepted.
Existing Tooling error, request-security and idempotency families are reused;
new conflict codes distinguish stale intake version and duplicate exact
evidence without leaking protected identities.

## 6. Persistence and ownership plan

Checkpoint 1 adds only:

- `NPI Tooling Set`;
- `NPI Tooling Intake`; and
- `NPI Tooling Intake Evidence Reference`.

The existing `NPI Tooling Command Idempotency` and append-only audit mechanism
are reused. The three DocTypes use UUID identity, exact tenant/Project/Master/
Requirement containment, immutable snapshots/hashes, no rename/delete, no
normal-user export/print/email and no generic normal-user write.

`contracts/data-ownership.yaml` gains exact rows: NPI One owns Set identity,
customer ownership/custody provenance, intake observations/differences and
evidence references. P6-03 owns future exact source Revision; ERPNext owns
formal Supplier, Asset ID/state, physical location, shot count and maintenance.
Unavailable target fields cannot be browser-authored or persisted as success.

Migration is additive and idempotent. It creates no business row, Set,
intake, evidence link, policy, default, mapping, adapter or backfill.

## 7. Live Tooling workspace and i18n plan

- The existing dense Tooling workspace gains a selected-Master physical-Set
  tree/table/inspector fed by the new strict data source. P6-01 identity and
  Applicability views remain intact.
- The workspace exposes one conditional primary action, then guided Set,
  intake and evidence commands. File selection reuses Project-scoped
  controlled-file metadata; users never type or receive a private URL.
- The Set inspector shows immutable identity/serial/owner/custody, intake
  versions, five inspection categories, accessory differences, confirmation
  requirements and exact evidence metadata. Revision, lifecycle, Supplier,
  location and Asset remain visibly unavailable with text, not fake blanks.
- Normal, empty, loading, no-permission, read-only, unavailable, validation,
  stale-version, evidence conflict, processing and retry states are explicit.
  Keyboard, focus, labels and non-color-only state remain mandatory.
- Every visible source string is literal English through `t()` with complete
  direct `zh` and `zh-TW` coverage. No new translation stack or fallback is
  permitted.

## 8. Planned checkpoints

1. **Domain/contract/metadata foundation** — pure Set/intake/evidence
   invariants, three additive guarded DocTypes, ownership rows, closed OpenAPI
   schemas and domain/metadata/contract/security tests; no active route.
2. **Repository/BFF checkpoint** — Project-first queries and narrow commands,
   exact Requirement/customer/File Revision containment, transaction,
   idempotency, audit, route switch and API/IDOR tests.
3. **Live workspace checkpoint** — strict Set/intake data source, dense
   trilingual UI, file picker, accessibility/state and affected visual tests.
4. **Controlled runtime and Task Gate** — disposable-Site per-Set non-collapse,
   customer intake, retained photo/difference/confirmation, replay/conflict,
   rollback, IDOR and route-disable proof, complete ordinary CI and Level 2.

Complete ordinary CI is mandatory before a controlled-Site boundary.
Diagnostics stay closed unless an opaque exact-SHA failure activates one
governed response-neutral diagnostic cycle under standing authority.

## 9. Requirement to code to test to evidence

| Requirement | Planned delivery | Required evidence |
|---|---|---|
| `FR-TX-003` | one UUID record per physical Set and per-Set serial/provenance; no quantity collapse; exact later Revision/Supplier/lifecycle/location/Asset dependencies remain unavailable | domain non-collapse, two-Set copy, metadata, API, IDOR and controlled runtime; foundation trace truth |
| `FR-TL-004` | exact customer owner, transport, arrival photos, accessory list, five inspection areas, difference list and optional customer-confirmation evidence | domain/contract, retained-file/hash, permission, trilingual UI and controlled runtime; technical verification truth |

P6-02 also adds exact ownership/custody evidence to the existing `FR-TL-001`
foundation without claiming the still-held lifecycle/authority policy complete.

Final evidence will be recorded in
`implementation/evidence/phase-6/p6-02-validation.md`.

## 10. Changed-files to affected-tests

| Expected change surface | Minimum direct checks |
|---|---|
| `tooling/domain.py` | per-Set identity/non-collapse, eligible Requirement, immutable intake version/hash, five inspection categories, accessory/difference and confirmation scope |
| three additive DocTypes and Tooling validation | containment, immutable fields, denied generic CRUD/delete, exact JSON/hash and additive/idempotent migration |
| OpenAPI and data ownership | parse/reference/closed-schema/subresource/ownership/no-fake-ERP assertions |
| Tooling repository/API/security/routes | Project-first authorization, same-tenant Master/Requirement/customer/file, replay/conflict/audit/rollback/IDOR and switch tests |
| Tooling data source/page/router | strict parser/transport, Set/intake/evidence states, accessibility, unsaved-context and prototype-isolation tests |
| catalogs/styles | direct English/zh/zh-TW coverage, terminology/mixed-language and affected visual matrix |
| runtime verifier/workflow | two independent Sets, intake/photo/difference/confirmation persistence, retained private file, replay, rollback, IDOR and route disable/recovery |
| controller/evidence | YAML, reconciliation, Task Diff Review and `git diff --check` |

## 11. Migration, rollback and exit

Before retained P6-02 rows exist, a disposable environment may restore the
starting checkpoint and migrate fresh. After Set/intake/evidence history
exists, rollback disables only P6-02 routes, preserves every UUID, snapshot,
difference, exact File Revision reference, audit and idempotency receipt, and
uses a reviewed forward repair. It never deletes or merges physical Sets,
rewrites an intake or alters referenced customer files.

The audit passes. Autopilot may start only checkpoint 1, the pure domain,
closed contract and additive metadata foundation. Repository routes, live SPA
activation and controlled-Site execution remain inactive until their preceding
checkpoints pass. P6-03 and later behavior remains inactive.
