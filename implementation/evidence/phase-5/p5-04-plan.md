# P5-04 Plan — EBOM Revision and Comparison

Recorded: `2026-08-05T09:22:56Z`

Starting synchronized remote checkpoint:
`5676f799ef2af8e1b3006ed69ec2b2f39539600f`

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; IMPLEMENTATION FOUNDATION NEXT**

Requirements:

- `FR-DS-011`; and
- `FR-DS-012`.

Applicable Skills:

- `npi-domain-guard`;
- `frappe-safe-change`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Sources and repository boundaries audited

The audit used only the current task index and directly related facts:

- the two canonical Requirement rows in `docs/DETAILED_REQUIREMENTS.md`;
- `implementation/phase-5-requirement-anchor.md` sections 1–4 and 6–9;
- the two `ANCHORED_P5_04` trace rows;
- `contracts/data-ownership.yaml` `EngineeringItem` and `EBOM_MBOM`
  ownership;
- the accepted Project, Document Revision, release, baseline and Gate
  boundaries delivered by Phases 4 and P5-01 through P5-03;
- the current BFF/OpenAPI/DocType/controller conventions and independent
  server capability model; and
- the accepted Frappe v15 CSV translation chain and industrial workspace
  constraints.

The repository contains no EBOM aggregate, revision, line, comparison, policy,
command receipt, BFF route or end-user EBOM workspace. It also contains no
approved production EBOM numbering, stable line-number policy, quantity
precision, engineering UOM vocabulary, alternate/effectivity semantics,
attribute set, release authority or Item conversion rule.

P5-04 therefore has one safe additive path: build an NPI-owned, explicitly
policy-bound EBOM revision mechanism using deterministic synthetic fixtures,
while keeping every unavailable production fact fail closed. This path does
not change the approved architecture or data ownership and needs no ADR.

## 2. Scope

P5-04 delivers the following minimum complete vertical slice:

> create an NPI-owned EBOM identity and an exact draft revision under one
> explicit published synthetic policy → validate the complete Project-scoped
> parent/child graph, quantities, engineering UOM values, alternate references,
> effectivity fields and controlled attributes → submit the exact revision for
> review → record a separately authorized review decision → release the exact
> approved revision through a separately authorized high-risk confirmation →
> create an immutable successor revision → compare two exact revisions and
> return a deterministic added/removed/quantity/substitution/attribute diff

An EBOM revision is an immutable content snapshot. A changed working draft is
represented by an exact successor revision rather than an in-place overwrite.
Lifecycle state and its optimistic version are maintained separately from the
content snapshot and have append-only events. A released revision and every
comparison input remain retained and cannot be rewritten or deleted.

The closed lifecycle is:

`draft → in_review → approved → released`

A rejected review returns the lifecycle projection to `draft` while retaining
the rejected event. Resubmission records a new review event chain. Releasing a
successor does not silently supersede its predecessor because production
replacement/effectivity semantics are held.

## 3. Non-scope and Class-B holds

P5-04 does not:

- install or infer a production EBOM number, line number/key, quantity scale,
  stock UOM, alternate-selection rule, date/lot/order effectivity rule,
  controlled attribute set, approval quorum, release authority or replacement
  rule;
- create or update a formal ERPNext Item, Item Code, MBOM, submitted BOM,
  manufacturing route, inventory, cost or execution record;
- implement the P5-05 formal publish request or claim Mock/sandbox/ERP success;
- infer a graph, alternate, effectivity or comparison result from Document,
  CAD/PDM, filename, sample data or an external system;
- mutate an exact Document Revision, release package, baseline, Gate evidence,
  Gate review decision or P5-03 impact event;
- expose raw DocType CRUD, make Frappe Desk the normal-user UI, contact a
  production endpoint or weaken the existing Project/tenant boundary; or
- add a production policy record, credential, business sample, dependency or
  destructive migration.

Production numbering, line identity, precision, UOM, alternate/effectivity,
attribute, review/release and formal conversion decisions remain Class-B
holds. They pause only those production rules. The Phase 5 anchor explicitly
allows versioned rules and deterministic synthetic fixtures, so the generic
mechanism, contracts, UI, tests and evidence may proceed without inventing a
production default.

## 4. Frozen domain and persistence design

### 4.1 Stable EBOM and engineering-item identity

`EngineeringBOM` is a stable tenant/Project-scoped NPI identity. It stores an
opaque global ID, an explicitly policy-scoped engineering identity key and the
current latest revision pointer. The key is not an ERPNext Item Code, formal
BOM number or cross-system synchronization key.

Every line freezes one opaque NPI engineering-item identity and descriptive
engineering data. A line cannot carry or imply an ERPNext `item_code`, MBOM ID,
stock-UOM authority or manufacturing routing. P5-05 may later consume only one
exact released snapshot through the Execution Request boundary.

### 4.2 Explicit versioned policy

`EngineeringBOMPolicy` is an administrative Project-scoped root and
`EngineeringBOMPolicyVersion` is a publish-once immutable snapshot. A version
freezes:

- a visibly synthetic namespace and EBOM-key pattern;
- `lineIdentityMode = caller_supplied_stable_key`;
- an exact positive quantity scale and maximum node count;
- an exact engineering-UOM allowlist whose values are not called stock UOM;
- an exact controlled-attribute-key allowlist;
- exact creator, review-submitter, reviewer and release-authority user IDs;
- closed graph, alternate and effectivity validation flags; and
- immutable canonical content and SHA-256 hash.

Only the fail-closed modes above are supported. The authority sets are
independent; Project ownership, membership, assignment, RACI, transport roles,
`System Manager`, Document release authority and UI visibility grant none of
them implicitly. Migration creates no policy. Tests and controlled runtime use
only namespaced synthetic policies.

### 4.3 Immutable revision and line snapshot

`EngineeringBOMRevision` freezes:

- exact tenant, Project, EBOM and policy identity/hash;
- monotonic positive revision number and exact predecessor identity/hash;
- bounded reason and optional engineering effectivity note;
- actor/time/request/trace identity;
- a complete canonically ordered line snapshot; and
- the canonical revision SHA-256 hash.

`EngineeringBOMLine` freezes one unique stable line key, optional parent line
key, opaque engineering-item identity, bounded English-source-neutral business
description, exact positive decimal quantity rendered at the policy scale,
engineering UOM, optional alternate-for line key/group, optional bounded
effectivity start/end dates and a closed controlled-attribute map.

Server validation rejects an empty or oversized graph, duplicate line keys,
missing/cross-revision parents or alternate references, self references,
parent or alternate cycles, ambiguous alternate groups, nonpositive or
over-precision quantities, unapproved engineering UOM/attribute keys, invalid
date ranges, duplicate revision numbers and any predecessor that is not the
same EBOM's current exact latest revision.

### 4.4 Lifecycle, review and release

`EngineeringBOMRevisionLifecycle` is the only mutable projection and uses an
optimistic lifecycle version. `EngineeringBOMLifecycleEvent` is append-only
and freezes exact from/to state, revision/policy snapshot hashes, actor,
authority binding, bounded decision/reason, confirmation intent, request,
trace, time and event hash.

The normal command flow is:

1. creator creates the exact immutable draft revision;
2. exact submitter moves `draft` to `in_review`;
3. exact reviewer approves to `approved` or rejects to `draft`;
4. exact release authority confirms the high-risk action and moves the exact
   approved revision to `released`; and
5. every command requires the current lifecycle version, actor-bound
   idempotency key, trusted CSRF and the exact published policy/hash.

No caller can select an event actor, state, hash or authorization result. Any
failure rolls back revision/lines, lifecycle/event, audit and idempotency
history atomically. Released content and events deny update, rename and delete.

### 4.5 Deterministic exact-revision comparison

Comparison accepts two exact same-tenant/same-Project revisions after Project
authorization. It never compares either input with a mutable “latest” pointer.
Lines are matched only by their frozen stable line keys and returned in
canonical line-key order:

- missing only from the prior revision: `removed`;
- missing only from the later revision: `added`;
- same line key with a different exact decimal quantity: `quantity`;
- same line key with changed engineering-item identity, alternate-for key or
  alternate group: `substitution`; and
- same line key with changed parent, engineering UOM, description,
  effectivity or controlled attributes: `attribute`.

One line may expose multiple typed changes where the facts require it. Each
entry contains exact old/new values and sorted changed-field names. The summary
counts are derived from the returned entries. Identical revisions return an
explicit empty diff; missing/unauthorized/cross-Project references fail without
object-existence disclosure.

## 5. BFF and OpenAPI boundary

Planned normal-user routes are:

| Method and path | Purpose |
|---|---|
| `GET /projects/{projectId}/eboms` | list safe EBOM/revision summaries, exact published synthetic policies and server capabilities |
| `POST /projects/{projectId}/eboms` | create one stable EBOM and exact first draft revision |
| `GET /projects/{projectId}/eboms/{ebomId}` | load exact revision/lifecycle/line/event history and capabilities |
| `POST /projects/{projectId}/eboms/{ebomId}/revisions` | create one exact immutable successor draft |
| `POST /projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}:submit-review` | enter review under exact policy authority |
| `POST /projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}:review` | append exact approve/reject decision |
| `POST /projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}:release` | separately authorized confirmed release |
| `GET /projects/{projectId}/eboms/{ebomId}/compare?fromRevisionId=…&toRevisionId=…` | deterministic exact-revision comparison |

All schemas are closed and bounded. Commands require authenticated internal
principal, normal-user transport permission, trusted Frappe CSRF,
actor-bound idempotency, exact expected versions and policy identity/hash.
Resolution remains authorize-before-protected-lookup. Stable problems cover
policy unavailable, graph validation, lifecycle/version conflict, independent
authority unavailable, idempotency conflict, route disabled and the existing
authentication/CSRF/validation families without leaking protected identities.

An independent `npi_p5_04_routes_disabled` switch disables only P5-04 routes
and capabilities while retaining all earlier Phase 5 behavior.

## 6. Workspace, UX and i18n

The existing Project Design/Documents workspace gains an `EBOM` working area;
no Desk form is exposed. The bounded industrial layout uses a stable toolbar,
dense revision table, hierarchical line tree/table, exact-revision comparison
table and right inspector. It keeps square boundaries, single deep-teal primary
action, compact icon-first secondary actions through the repository adapter,
text-plus-shape states and no decorative card wall.

The UI covers loading, normal, empty, no-permission, read-only, validation,
conflict, processing, retryable/final failure, identical comparison, released
and source-unavailable states. Release uses a review step with translated
impact summary and explicit focus recovery. Frontend capability truth mirrors
the server but never grants authority.

Every source string is literal English through Frappe `_()` or React `t()`,
with direct `zh` and `zh-TW` CSV translations, mixed-language scans and fixed
three-language browser/visual evidence. Business descriptions, engineering
identity keys, hashes, UOM values and allowlisted `EBOM`/`MBOM`/`ERPNext`
terminology remain data or approved-retain values, never untranslated UI copy.

## 7. Requirement → code → test → evidence

| Requirement | Planned code | Required proof | Evidence |
|---|---|---|---|
| `FR-DS-011` | EBOM policy/domain, immutable revision/line/lifecycle/event DocTypes, repository/BFF/OpenAPI, Project EBOM workspace | graph/quantity/UOM/alternate/effectivity validation; lifecycle/authority/concurrency/idempotency/rollback; migration/runtime; UI/i18n/permission | P5-04 checkpoints and final validation report |
| `FR-DS-012` | deterministic exact-revision comparison domain, BFF contract and dense comparison UI | add/remove/quantity/substitution/attribute/identical ordering; cross-Project/unauthorized denial; component/E2E/visual | P5-04 checkpoints and final validation report |

## 8. Changed files → affected tests

| Change boundary | Minimum affected proof |
|---|---|
| EBOM domain/policy/graph/lifecycle/comparison | new P5-04 domain tests plus unaffected P5 document-domain smoke |
| additive DocTypes/controllers/hooks | metadata/controller immutability tests, compile, additive two-migration controlled-Site proof |
| Frappe repository and command transactions | graph/authority/version/idempotency/rollback/audit tests plus prior Document/Baseline repository compatibility |
| BFF/API/OpenAPI/settings | auth/CSRF/IDOR/closed-schema/replay/conflict/route-disable tests plus contract parser and prior Document API compatibility |
| frontend data source/view models/workspace | TypeScript/lint/unit/component/a11y tests and affected Project Documents workspace states |
| English/zh/zh-TW copy | extractor, direct-catalog coverage, terminology and mixed-language scans |
| industrial visual surface | fixed-Linux exact EN/zh/zh-TW screenshots at approved sizes/scales and original-resolution review |
| trace/controller/evidence | trace reconciler, controller tests, diff/secret/placeholder review and Task Gate report |

Level 1 checks are grouped by proven root cause. P5-04 Level 2 runs the complete
EBOM module plus affected Project/Document/Baseline/API/security/i18n/UI/runtime
checks. It does not replace the Phase 5 Level 3 Gate after P5-05.

## 9. Migration and rollback

The migration is additive: install only the EBOM policy/version, root,
revision, line, lifecycle, event and command-receipt DocTypes/indexes. It adds
no production policy, authority, sample EBOM, mapping or destructive backfill,
and must pass install plus two consecutive controlled-Site migrations.

Rollback is forward-only and preserves history:

1. activate `npi_p5_04_routes_disabled`;
2. stop new EBOM commands while keeping P5-01 through P5-03 routes available;
3. retain every EBOM identity, revision, line, lifecycle/event, policy, audit
   and idempotency row;
4. never delete or reopen a released revision; and
5. deploy a reviewed forward fix before re-enabling routes.

ERPNext is unaffected because P5-04 has no external dispatch or production
connection.

## 10. Audit decision and first implementation slice

The Requirement/domain audit passes. The design keeps EBOM distinct from MBOM,
keeps formal ERP ownership intact, makes unknown production rules explicit
holds, and creates exact Code/Test/Evidence and impact maps without changing a
reconciled Requirement.

The first implementation slice is the controlled metadata/domain foundation:

1. policy, graph, revision, lifecycle and deterministic comparison values;
2. additive guarded DocTypes and controllers;
3. independent route-disable/controlled-write flags; and
4. focused domain, metadata and controller Level 1 tests.

Repository, BFF/OpenAPI, frontend, controlled runtime and the Level 2 Task Gate
remain inside the same P5-04 atomic task and cannot be reported complete until
their real evidence passes.
