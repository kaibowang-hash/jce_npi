# P7-06 Repository and BFF Checkpoint

Recorded: `2026-08-14T11:52:18Z`

Status:
`PASS — PROJECT-FIRST EXACT PRODUCTION-TRANSITION REPOSITORY BOUNDARY`

Primary requirements: `FR-NP-014` and `FR-NP-015`.

Exact product checkpoint:
`7aeceff6fd75180bbe7efddfc9ee4d2c382e43ef`

Ordinary PR CI:
`31797120347` (`success`; `pull_request`; exact product SHA)

## Delivered boundary

- Activated only the eleven frozen Production Transition policy/catalog and
  Project workspace/package/acknowledgement/observation routes.
  Authentication precedes request parsing, mutation requires CSRF, policy
  commands require an enabled same-tenant System Manager, and Project routes
  authorize the Project before resolving any secondary identity. The
  independent `npi_p7_06_routes_disabled` switch remains default-closed unless
  configured to exact `false`.
- Implemented guarded policy create, optimistic draft edit, immutable publish
  and exact published-version successor commands with no installed business
  default. Catalog results use the exact authorized Project snapshot and only
  applicable same-tenant published policies.
- Implemented exact package creation and succession under frozen Scheme A.
  The caller submits only published-policy `requirementKey`, source kind, ID
  and expected version. The server reauthorizes and canonicalizes every source,
  injects the published requirement's `manifestRole`, rejects duplicate or
  cross-requirement reuse of one kind/ID tuple, and enumerates the complete
  bounded set of unresolved same-Project Work Items itself.
- Closed source resolution to the nine frozen kinds: readiness revision,
  Domain Work Item, released Document, release Baseline, clean private live
  File Revision, Tooling capacity scenario, Trial defect revision, Trial
  review reference and Trial conclusion. Exact tenant, Project, version, hash,
  unique-tip and transitive release/File/currentness chains are revalidated
  under the command lock; mutable names, latest pointers and raw private URLs
  are never accepted as source truth.
- Implemented current-package-only acknowledgement by the exact authenticated
  enabled frozen User/member/role slot. Member and role effectivity, versions
  and canonical hashes are revalidated before insert. A successor inherits no
  acknowledgement, and `fullyAcknowledged` remains a query-time projection
  that never changes the package snapshot.
- Implemented independent observation creation and unique-tip succession over
  exact context/retrospective references. An optional exact historical
  handover reference remains reference-only. Actual SOP, first-batch yield,
  customer complaints, production cycle and Tooling stability are always the
  server-fixed identity-free offline provider set, so absent external truth
  derives only `not_evaluable`, never zero, pass or stable.
- Bound every command receipt to exact tenant, nullable Project, actor,
  operation, idempotency key, canonical request, target and sealed canonical
  response. Receipt, immutable domain row and append-only audit are one
  transaction. Duplicate races replay only the matching actor-bound response;
  changed payload, target, tenant, Project, actor or corrupt response fails
  closed.
- Persisted audit summaries retain actor/time/request/trace, exact policy and
  predecessor identities/hashes, source resolutions, package supersession,
  acknowledgement slot and observation disposition without raw private URLs,
  tokens, secrets or arbitrary external payloads.

## Tenant-isolation forward fix

Checkpoint 1 opened no route and installed no policy or other business row.
Before checkpoint 2 could create retained history, the repository review found
that a globally unique policy code and a tenant-free policy-version snapshot
would not prove the frozen same-tenant authority boundary. Checkpoint 2
therefore completes one additive pre-row forward fix:

- policy roots now retain required read-only `tenant_id` and a unique
  `policy_code_key_hash` derived from exact tenant plus case-folded policy code,
  instead of making the display code globally unique;
- policy versions retain `tenant_id`, include it in the immutable canonical
  snapshot and bind version-key identity to the tenant-owned policy chain;
- handover and observation domains reject a published policy from another
  tenant even if all other applicability fields match; and
- OpenAPI, ownership, metadata validation, response validation and sealed
  command-replay validation all carry and revalidate the exact tenant.

This correction creates no compatibility bypass, default policy, tenant
mapping or destructive data rewrite. Disposable-Site migration proof remains
checkpoint 4. Once any retained policy, package, acknowledgement, observation,
receipt or audit history exists, rollback is only independent route/workspace
disable plus a reviewed forward repair; retained history is never deleted,
rewritten, renumbered or copied to simulate reversal.

## Deliberately inactive

- No Production Transition SPA data source, workspace or controlled-Site
  runtime fixture was added in checkpoint 2.
- No Gate input/evidence hook, Gate decision or G7 transition exists. P7-06
  does not mutate Project lifecycle, Work Items or Tooling, and acknowledgement
  is not an electronic signature, approval or production acceptance.
- No provider adapter, credential, ERPNext/customer contact, network request,
  Outbox/Inbox message, external projection, release or print effect was
  introduced. Trial, readiness and capacity evidence remains NPI context and
  never becomes a production actual.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| policy repository and tenant forward fix | same-tenant code reuse, cross-tenant catalog/UUID denial, optimistic draft/publish/successor locks, immutable roots/chains and tenant-bound snapshots/replay |
| package and nine source resolvers | Project-first IDOR denial, exact version/hash/currentness, released-document/File locks, Scheme A assignment/counting, full unresolved enumeration and no latest substitution |
| acknowledgement and observation repositories | current-tip-only actor slot, User/member/role drift/effectivity, successor non-inheritance, independent reference usage, fork rejection and five mandatory offline providers |
| BFF/API/response validation | eleven frozen routes, auth-before-body, CSRF/authority/idempotency, independent switch and recursively closed tenant/Project/target-bound responses |
| transaction/audit boundary | duplicate/replay/conflict/rollback, receipt-response sealing, exact audit summaries, no URL/token/secret and zero Gate/ERP/network/Outbox effects |

The six focused Production Transition domain, metadata, contract, resolver-
seam, repository and API suites contain `107` test cases, all included in the
successful exact-SHA repository lane. Independent scope, security and
repository audits report no P0/P1 finding.

## Exact-SHA CI evidence

- Repository job `94756537757`: PASS with `1,851` tracked Python tests plus
  current-task, V1.2 reconciliation and repository verification.
- Frontend job `94756537820`: PASS with `56` test files, `881/881` unit tests,
  `388/388` non-visual E2E tests, `7,193` direct English sources with `100%`
  `zh`/`zh-TW` coverage, statements `80.14%` and zero vulnerabilities.
- Secret job `94756537745`: PASS for `49` committed P7-06 task paths, `26`
  pull-request-range commits and `455` complete branch-history commits with no
  leak. Gitleaks artifact `9217790725` has digest
  `sha256:c7076242aa2f4728c853e5fed0bb3d082eb079eca72a3588882ee3945e8b9ebd`.
- Visual job `94756537718`: PASS at the unchanged `109/109` fixed-Linux
  governed matrix. Artifact `9217889371` has digest
  `sha256:f577e500df2b343b5d4dee3a804997e3359554ea5a0a964f92027a9993895f6f`.
- Controlled preflight `94758839280` and runtime `94758839769` skip as
  required because checkpoint 2 intentionally adds no runtime fixture. This is
  checkpoint 2 PASS, not the P7-06 Level 2 or Level 3 Gate.

## Next authorized checkpoint

Checkpoint 3 alone is active: add the strict Production Transition data source
and dense trilingual Project workspace with exact handover manifest,
receiving-group and slot acknowledgement, unresolved-action, immutable-history,
observation source/state, retrospective and unavailable-provider truth. Cover
loading, empty, read-only, permission, validation, conflict, processing, retry,
superseded and external-unavailable states in English, `zh` and `zh-TW`, plus
accessibility and affected fixed-Linux visuals.

The live data source and UI are closed to the complete Project workspace GET
and acknowledgement by the current signed-in actor for an exact eligible slot
on the unique current package. Checkpoint 3 exposes no policy
create/edit/publish/successor, package create/supersede or observation
create/revise transport, controls or forms.

Controlled runtime and Level 2 remain checkpoint 4. Formal receiving-
organization and bilateral authority, signature/approval/G7, Gate/Project/
Work Item/Tooling mutation, actual SOP and external production actuals,
stability authority, ERP/network/Outbox, release, projection and production
print remain held. Level 3 remains reserved for the applicable Phase, PR or
release boundary.
