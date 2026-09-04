# P4-03 Implementation Boundary — Gate Templates and Controlled Evidence

Status: **ACCEPTED — see `p4-03-validation.md`**

Recorded: 2026-07-23

Atomic task: `P4-03 — Gate templates and controlled evidence`

Requirement allocation: `FR-SG-001`, `FR-SG-002`, `FR-SG-004`

## 1. Repository facts

- P4-01 creates immutable published Project Template versions and Project Gate
  shells, but a Gate definition currently contains only key, title, and
  sequence.
- P4-02 provides explicit Project members and dated assignments. A membership,
  RACI row, or reviewer field does not grant Gate approval authority.
- The current `NPI File Revision` is an administrative foundation. It does not
  yet carry enough tenant, Project, stable Frappe File, MIME, size, or
  optimistic-version identity to be accepted as Project-scoped evidence.
- The existing Gate SPA is an explicitly labeled Phase 3 prototype and includes
  P4-04 decision behavior. It is not an accepted live P4-03 path.
- Pinned Frappe private-file authorization permits a File owner to read the raw
  private URL and may reuse a URL for equal content. A raw Attach URL therefore
  cannot be the NPI Project authorization boundary.
- Production Gate contents, skip/condition rules, duration rules, role mapping,
  scan-provider policy, and later-domain evidence mappings remain unavailable.

## 2. Selected minimum vertical slice

P4-03 will implement the following additive path:

> publish an exact Gate Template version → bind it to a new Project Template
> version → create a Project Gate shell with that exact reference → explicitly
> freeze Project-specific requirement owners, reviewers, and due dates → append
> an exact controlled evidence reference → read it from the live trilingual Gate
> evidence workspace

### 2.1 Versioned Gate Template

Use an independent `GateTemplate` aggregate rather than changing the canonical
payload of already-published P4-01 Project Template versions.

- A stable Gate Template root owns numbered draft/published versions.
- A version declares its applicable Project types and ordered requirement
  definitions.
- Each definition has a stable key, literal-English title, required/optional
  classification, priority, and an allowlist of evidence kinds.
- Publication creates a canonical SHA-256 snapshot. A published version is
  immutable; changes require a new numbered version.
- No production default template or business rule package is installed.

New Project Template versions may bind each Gate definition to one exact
published Gate Template global ID, version, and snapshot hash. Legacy published
Project Template versions retain their original canonical payload and hash and
remain readable as unconfigured Gate shells.

### 2.2 Frozen Project Gate requirements

A retry-safe, System-Manager-only command freezes a configured Gate exactly
once after the Project team exists.

- The command accepts the Gate expected version, one explicit Gate due date,
  and explicit owner member plus reviewer member identities for every template
  requirement.
- Every supplied member must be an existing internal member of the same
  Project and tenant. Reviewer assignment confers no approval permission.
- The command copies the exact Gate Template version/hash and canonical
  requirement definitions into an immutable Project Gate requirement snapshot,
  adds the Project-specific identities and dates, hashes the result, records
  actor/time, increments the Gate optimistic version, and writes audit and
  idempotency records atomically.
- It does not infer assignments from RACI, calculate due dates, decide whether
  a Gate may pass, or create approval authority.

### 2.3 Controlled evidence reference

An append-only evidence-reference aggregate records:

- tenant, Project, Gate, and frozen requirement identity;
- an allowlisted evidence kind and source object type;
- exact object global ID and exact revision/optimistic version;
- a canonical object hash or immutable SHA-256;
- actor/time and its own stable identity.

The first bounded resolvers are:

- a same-Project WBS item at an exact optimistic version and canonical hash;
- a same-Project private File Revision with a stable Frappe File identity,
  exact revision and SHA-256, and its real `pending`, `clean`, `infected`, or
  `failed` scan state.

Unsupported Document Revision, Trial, Quality Inspection, Customer Approval,
external-link, and other future resolvers fail explicitly as unavailable. The
command never accepts `latest`, a raw private-file URL, a client-supplied scan
result, or a client-supplied digest as proof.

P4-03 adds no normal-user upload/download route. The live BFF returns safe
metadata only and never exposes a raw `/private/files/...` URL. Evidence
replacement, detachment, satisfaction, decision use, and decision snapshots
remain later policy.

### 2.4 Live Gate evidence workspace

The accepted SPA route is
`/projects/{projectId}/gates/{gateId}`. The Phase 3 fixture stays available only
under an explicit demo route.

The live page reads a strict Gate Evidence ViewModel and shows:

- Project and Gate identity plus exact Gate Template version/hash;
- frozen required/optional requirements with explicit owner, reviewers, due
  date, priority, and allowed evidence kinds;
- exact evidence object version/hash and real file scan state;
- missing evidence and unsafe scan counts without claiming that a Gate is
  decision-ready; and
- normal, loading, empty, read-only, not-found/no-permission, validation,
  conflict, retryable, and invalid-response states.

The page contains no pass, conditional pass, waiver, reopen, decision snapshot,
or approval-authority behavior. Evidence attachment remains a strict BFF
command; the SPA will not expose a UUID/DocType free-form picker while no
authorized exact-version choice endpoint exists.

## 3. Non-scope

- Gate review, pass/fail/conditional/waiver decisions, P0 pass blocking,
  immutable decision snapshots, reopening, or dependency invalidation
  (`P4-04`).
- Live My Work, notification delivery, contextual activity, or Project
  lifecycle controls (`P4-05` or later).
- Production template contents, standard durations, skip conditions, computed
  due dates, RACI-to-approval mapping, or segregation-of-duties policy.
- Normal-user file upload/download, raw Attach URLs, scanner/provider
  integration, file classification, retention, watermarking, or external
  sharing.
- Production ERPNext/DMS, Trial, Quality, Customer Approval, or Document
  Revision mappings.
- Evidence detach/replace/correct semantics or external URL fetching.

## 4. Assumptions and Class-B holds

- System Manager remains the only current `ADMINISTER` principal. Project owner
  access remains `VIEW`; P4-03 does not widen it.
- Exact Project member identities, reviewer identities, and dates are supplied
  explicitly for the synthetic acceptance slice. Production assignment and
  duration policies remain held.
- Applicable Project types are enforced. Arbitrary Gate skip/condition
  evaluation is not introduced until an authoritative rule package exists.
- File Revision schema additions are nullable for migration safety. A legacy
  incomplete row fails closed at the evidence resolver and is never guessed or
  auto-associated with a Project.
- Scan state is observational in P4-03. `pending`, `failed`, and `infected`
  remain visible and are never converted to `clean` or described as satisfied.
- Requirement evidence completeness is not Gate satisfaction. P4-04 owns the
  policy that blocks normal pass when required P0 evidence is missing.

## 5. Security and consistency rules

- Authenticate and authorize the Project before resolving Gate, requirement,
  cursor, evidence, or file identifiers.
- Validate tenant and Project identity across every related record; unrelated,
  external, cross-tenant, and IDOR attempts fail without existence leakage.
- Mutating BFF commands require Frappe CSRF, request/trace identity, strict
  request fields, expected Gate version, and an idempotency key.
- Frozen requirements and evidence references are controlled history: no
  generic DocType mutation, update, rename, or physical delete.
- Each command commits Gate/evidence, audit, and idempotency state atomically;
  stale versions, duplicate conflicts, validation errors, and injected failures
  leave no partial state.
- Audit summaries contain only allowlisted identities, versions, hashes,
  counts, and states; never content, raw URLs, tokens, or full request payloads.
- Every user-visible source string remains literal English and uses the shared
  Frappe-compatible `t()`/`_()` translation chain with complete `zh` and
  `zh-TW` entries.

## 6. Expected change surface and affected checks

| Change surface | Direct checks before the final gate |
|---|---|
| Gate Template domain, DocTypes, canonical publication, and Project Template binding | Domain unit tests; published immutability; legacy hash compatibility; duplicate/version validation; controller permission tests |
| Gate freeze and evidence append repositories | Command/API tests for authorization-before-resolution, tenant/Project integrity, expected version, idempotent replay/conflict, audit, and injected transaction rollback |
| File Revision additive identity and resolver | Controller/resolver tests for legacy fail-closed behavior, stable File identity, private-only metadata, exact SHA/revision, real scan states, and no raw URL |
| OpenAPI, BFF route, and data ownership | OpenAPI validation; strict request/response contract tests; route allowlist and CSRF tests; ownership/schema audits |
| Live Gate data source, route, page, and App Shell | Strict validator/component/router tests; Gate-focused E2E for the state matrix, permission/IDOR, XSS safety, keyboard/axe, and three languages |
| Catalog and visual surface | Translation extraction/coverage/mixed-language checks; one final catalog generation; one final exact visual update and clean comparison; representative original-resolution review |
| Migration and rollback | Real Frappe install/migrate and idempotent rerun; legacy Project Template/Gate/File Revision compatibility; forward-fix/route-disable recovery evidence |

Repair loops use only Level 1 directly affected checks. The complete P4-03 Task
Gate runs once after the slice is internally complete. Because P4-03 necessarily
changes public OpenAPI, DocType Schema, and permission boundaries, its final
validation escalates to one Level 3 Full Release Gate as required by
`implementation/QUALITY_GATE.md`; this is not repeated during implementation.

## 7. Primary risks and controls

| Risk | Control |
|---|---|
| Existing P4-01 snapshot hashes change | Independent Gate Template aggregate; legacy canonical payload branch; compatibility fixtures |
| RACI or reviewer assignment accidentally grants authority | Explicit membership validation only; unchanged authorization map; negative permission tests |
| Mutable or “latest” evidence breaks auditability | Exact revision/version/hash resolver and append-only references |
| Raw private file URL bypasses Project access | Metadata-only BFF; no URL/download accepted path; same-content cross-Project tests |
| Fake clean or fake Gate readiness | Persist and display real scan state; no satisfaction/decision claim |
| Partial records on retry, conflict, or failure | expected version, idempotency, one transaction, injected-failure assertions |
| Prototype decision UI is mistaken for live P4-03 | Explicit demo route; separate live evidence workspace with no decision controls |
| Global catalog hash invalidates visual baselines repeatedly | Stabilize copy first; regenerate and compare the complete matrix once at final gate |

## 8. Migration and rollback

All schema changes are additive. New identity fields on legacy-compatible
records remain nullable at the database migration boundary, while new P4-03
commands require complete identities. No migration guesses tenant, Project,
member, File, scan, or evidence relationships; ambiguous legacy records fail
closed and are reported as unavailable.

Before retained P4-03 data exists, the disposable development Site may restore
the prior task checkpoint. After Gate requirement or evidence history exists,
rollback disables the new BFF routes and live route, leaves additive tables,
snapshots, evidence, files, idempotency, and audit history intact, and deploys a
reviewed forward fix. The App is not uninstalled and controlled history is not
deleted. ERPNext remains unaffected because P4-03 performs no ERP write.

## 9. Exit rule

P4-03 may be marked `PASS` only when the complete bounded vertical slice,
traceability, Task Diff review, migration/recovery evidence, trilingual live UI,
and independent `release-gate` review pass. `FR-SG-001`, `FR-SG-002`, and
`FR-SG-004` must retain truthful foundation/partial status for every acceptance
criterion intentionally left to P4-04 or later.
