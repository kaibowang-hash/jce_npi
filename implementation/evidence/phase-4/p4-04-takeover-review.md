# P4-04 Bounded Takeover Review

Review conclusion: **DOMAIN_FOUNDATION_ACCEPTED**

Task status: **IN PROGRESS — P4-04 is not PASS**

Reviewed: `2026-07-25T05:32:32Z`

Branch: `codex/npi-v1.2-implementation`

Takeover starting remote HEAD:
`df8ccae3f87ff3afbf4d06696f4a69ca91de92d9`

P4-03 trusted commit:
`0fd4762a01fd10fe6851df07ead1c5e4e7a42473`

Committed review range:
`0fd4762a01fd10fe6851df07ead1c5e4e7a42473...df8ccae3f87ff3afbf4d06696f4a69ca91de92d9`

The review also covered the retained, uncommitted P4-04 repair and acceptance
batch present at takeover. No unrelated phase or domain was reviewed.

## Cloud additions

Cloud added the P4-04 vertical-slice foundation:

- an immutable, versioned synthetic Gate Review Policy and explicit frozen
  review/final-decision/reopen/exception authority bindings;
- parallel, sequential, and allowlisted condition-selected reviews;
- fail-closed normal pass and policy-bounded non-P0 exception handling;
- server-built immutable decision snapshots, preserved review cycles, reopen,
  dependency invalidation/refresh events, and a current-decision guard;
- additive controlled DocTypes, repository/controllers, transaction locks,
  actor-bound sealed idempotency receipts, audit, and generic-history mutation
  denial;
- strict same-origin BFF/OpenAPI query, command, and receipt routes;
- WBS/Evidence/File dependency hooks;
- a strict trilingual industrial Gate Review Room with server-driven
  capabilities, command reconciliation, complete immutable-history detail, and
  non-normal states.

No production review policy is installed. Synthetic policy content appears
only in tests and disposable runtime evidence.

## File-level summary

| Surface | Principal files |
|---|---|
| Domain and persistence | `apps/npi_core/npi_core/gate_review/`, seven additive review DocTypes, Gate Shell fields/controllers |
| Transport and contracts | `gate_review_api.py`, `bff.py`, `contracts/npi-api.openapi.yaml`, `contracts/data-ownership.yaml` |
| Dependency handling | `gate_evidence/frappe_repository.py`, `hooks.py`, `verify_gate_review_runtime.py` |
| Live UI | review/evidence data sources, ViewModels, `gate-evidence-page.tsx`, shared command/session primitives |
| Localization and visual evidence | direct `zh`/`zh-TW` catalogs, generated catalog, Gate Review E2E and snapshots |
| Verification and recovery | Gate Review Python suites, parser/page tests, P4-04 plan/checkpoint/recovery documents |

## Requirement coverage

| Requirement | Accepted technical foundation | Deliberately not claimed |
|---|---|---|
| `FR-SG-003` | Published version/hash, fail-closed unknown policy, equal-sequence parallel review, prior-sequence enforcement, allowlisted conditional selection, and separated frozen authorities | Production RACI/approval or segregation mapping |
| `FR-SG-005` | Normal pass blocked by incomplete reviews, missing P0 evidence, unsafe File state, blocking work, stale input, or wrong authority; conditional pass requires exact current closure action, expiry, eligible rule, and requester/approver separation | Production waiver/deviation policy |
| `FR-SG-006` | Caller supplies only stale-input preconditions; server resolves inputs and builds the immutable snapshot; reopen creates a new approval-free cycle and preserves all old history | Task/Release Gate acceptance |
| `FR-SG-007` | Exact invalidated/refreshed events, successor cycle, preserved prior decision lineage, File/WBS/blocker dependency hooks, and downstream denial | Production dependency matrix or P4-05 work projection |

`FR-SG-007` does not require P4-04 to create an impact Domain WorkItem. That
projection belongs to P4-05. The nullable legacy action reference is retained
only for backward-compatible reads.

## Findings and repairs

| Severity | Finding | Result |
|---|---|---|
| High | Reopen/invalidation cleared the Gate latest-decision quartet | Repaired: successor cycles preserve the complete immutable latest decision lineage |
| High | `invalidated`/`refreshed` events used incompatible payloads under schema v1 | Repaired: new writes use v2; the reader accepts only closed historical v1 forms without rewriting hashes |
| High | Legacy exception request references could collide with exact checkpoint forms or infer missing version/hash | Repaired: true v1 ID-only remains non-authorizing, transitional v1 exact is read exactly, and new writes use v2 |
| High | File deletion did not schedule dependency evaluation | Repaired: `on_trash` resolves controlled references before deletion and publishes only after commit |
| High | Workspace `can*` projections did not consistently include command transport admission | Repaired without turning the transport role, System Manager, Project role, or RACI into business approval authority |
| Medium | Frontend rejected a decided historical cycle when its downstream guard was false | Repaired: immutable historical decision detail remains visible while the current guard truthfully denies use |
| Medium | Recovery documents described implementation as not started or only three visuals | Corrected by this takeover review and the current recovery checkpoint |

No remaining P0/P1 product-code blocker was found in the bounded review. No
TODO, stub, unconditional success, test-only production bypass,
`ignore_permissions`, cross-database write, mutable historical overwrite, or
synthetic-as-production assertion was found.

## Security, authority, and immutability

- Review assignment, final decision, exception approval, and reopen authority
  are distinct frozen policy slots.
- Project visibility and the `NPI API User` transport role do not grant
  approval authority.
- Authentication, CSRF, transport admission, Project/Gate isolation, current
  internal membership, and exact frozen authority are all required.
- Generic create/update/delete/rename of controlled review history is denied.
- Decision snapshots are server-built and hashed. Old decisions, reviews,
  exceptions, events, and cycles are append-only and remain readable.
- Stale cycle versions, stale input hashes, invalidated decisions, legacy
  non-exact closure references, and unsafe evidence fail closed.
- Production RACI, waiver, invalidation, substitution, and segregation rules
  remain explicit Class-B holds rather than invented defaults.

## Targeted verification

| Check | Result |
|---|---|
| Current Gate Review Python affected suite | `PASS — 123/123` |
| P4-02/P4-03 repository/controller/metadata boundary | `PASS — 46/46` |
| Gate Evidence contract/current Gate Shell boundary | `PASS — 11/11` |
| Evidence parser, review parser, and Review Room unit/component tests | `PASS — 116/116` |
| Generated sources and TypeScript | `PASS` |
| Direct ESLint and Prettier for changed frontend files | `PASS` |
| Direct Python compilation | `PASS` |
| i18n audit | `PASS — 1742` literal English sources; complete direct `zh` and `zh-TW` |
| Current Gate Review non-visual E2E | `PASS — 72/72` |
| Current Review Room visual matrix | `PASS — 23/23` clean exact comparison |
| Original-resolution industrial/i18n review | `PASS` for representative normal, no-permission, and high-risk confirmation states |
| Closed OpenAPI contract tests, changed JSON parse, prohibited-pattern scan, and `git diff --check` | `PASS` |

Python Black and the standalone PyYAML parse command were unavailable in the
current base Python environment. This is not represented as a pass; direct
Python compilation, the affected test suite, JSON parsing, and closed OpenAPI
contract tests did pass.

The focused live Frappe command was attempted once. It stopped before product
execution because controlled MariaDB was unavailable. Restoring the existing
Compose services then failed with Docker's stale-container OCI task error.
Therefore the current File-delete commit/rollback behavior, additive migration
rerun, and complete runtime compatibility remain pending. The earlier focused
runtime at the committed checkpoint remains historical evidence only.

## Current implemented and unfinished boundary

Implemented and retained:

- domain, additive persistence, repository/controllers, exception and
  invalidation event persistence;
- strict API/BFF and permission boundaries;
- current-decision downstream guard;
- live trilingual Review Room, complete current state/command/dialog fixtures,
  and exact current Review Room baselines.

Still unfinished:

- current-schema migration and idempotent rerun;
- focused live Frappe verification of the final File-delete/legacy-history
  repairs and complete P4-01/P4-02/P4-03/P4-04 runtime compatibility;
- complete P4-04 module coverage/build/audit and final Task Diff,
  permission/security, traceability, and recovery review;
- P4-04 Level 2 Task Gate and the single triggered Level 3 Full Release Gate;
- all production policy inputs and Phase 3 external business UAT.

## Conclusion and exact recovery

The bounded takeover conclusion is **DOMAIN_FOUNDATION_ACCEPTED**. This means
the P4-04 domain/implementation foundation and the current repair batch are
accepted for continuation; it is not a P4-04 Task `PASS`.

Resume only P4-04:

1. restore the existing controlled MariaDB/Redis services without resetting or
   deleting their volumes;
2. run the additive migration and idempotent rerun;
3. rerun `bash scripts/verify-frappe-runtime.sh --gate-review-only`, including
   File-delete rollback/commit and preserved latest-decision lineage;
4. run the remaining P4-04 Level 2 Task Gate;
5. repair only real affected failures; then run the single required Level 3
   boundary and `release-gate` review;
6. activate P4-05 only after P4-04 has genuine complete Gate evidence.
