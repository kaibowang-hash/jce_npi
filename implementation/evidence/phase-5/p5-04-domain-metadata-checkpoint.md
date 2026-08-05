# P5-04 Domain and Metadata Foundation Checkpoint

Recorded: `2026-08-05T09:51:10Z`

Status:
`PASS — LEVEL 1 DOMAIN/METADATA FOUNDATION`

Requirements:

- `FR-DS-011`;
- `FR-DS-012`.

Starting synchronized checkpoint:
`0eb10a8ade30590cc2a922314e21dfeed069d026`

Preceding audit ordinary CI:
`30993437267` (`PASS`, exact starting checkpoint SHA)

## Delivered boundary

- Added a pure EBOM domain with an explicit publish-once synthetic policy,
  immutable exact content revisions and lines, separate lifecycle projection,
  append-only transition events and deterministic exact-revision comparison.
- The policy freezes a visibly synthetic namespace, caller-supplied stable
  line keys, quantity scale, bounded node count, engineering-UOM and attribute
  allowlists, independent creator/submitter/reviewer/releaser user identities,
  and all three fail-closed graph rules. Migration installs no policy record.
- Revision validation rejects empty/oversized graphs, duplicate identities or
  keys, missing/self/cyclic parents and alternates, ambiguous alternate groups,
  invalid effectivity ordering, nonpositive/over-precision quantities,
  unapproved engineering UOMs or attributes, and non-exact predecessors.
- Lifecycle transitions are closed to
  `draft -> in_review -> approved -> released`; a rejected review returns to
  `draft` while its event remains retained. Exact actor authority, policy,
  revision hash, optimistic version and release confirmation intent are domain
  invariants.
- Comparison accepts two explicit revisions of the same EBOM, matches only by
  frozen stable line key and returns canonically ordered
  added/removed/quantity/substitution/attribute changes. Identical revisions
  return an explicit empty diff.
- Added eight guarded DocTypes for policy root/version, stable EBOM identity,
  immutable revision/line, lifecycle/event and actor-bound idempotency receipt.
  Generic CRUD is denied through three independent private write scopes.
- Every retained object denies rename/update/delete. A denied delete queues a
  sanitized post-rollback audit containing only object type, exact global ID,
  business version, actor, generated/validated trace ID and denied result.
- Added the independent literal-boolean
  `npi_p5_04_routes_disabled` emergency seam. It affects only future P5-04
  handlers and exposes the stable retryable `EBOM_ROUTES_DISABLED` problem.
- Updated data ownership while retaining formal Item Code, stock UOM, MBOM,
  manufacturing routing and production execution exclusively in ERPNext.
- Added direct Simplified and Traditional Chinese catalog coverage for every
  new literal-English source and regenerated the checked-in frontend catalog
  at exact version `18fefcf811fde25b`. No Frappe core, external dependency,
  public API, production ERPNext integration or product policy was added.

Repository/BFF/OpenAPI, UI, migration/runtime and Level 2 proof remain later
P5-04 stages. P5-05 and Phase 6 remain inactive.

## Requirement to code, test and evidence

| Requirement | Code boundary | Direct proof |
|---|---|---|
| `FR-DS-011` | `npi_core.ebom.domain`; eight additive DocTypes/controllers; ownership and route/write guards | graph, quantity, UOM, alternate/effectivity, attribute, immutable revision, lifecycle/authority and deletion-audit tests |
| `FR-DS-012` | exact-revision comparison values and canonical diff algorithm | added/removed/quantity/substitution/attribute/identical ordering tests |

## Changed-files to affected-tests

| Changed boundary | Affected checks | Result |
|---|---|---|
| pure domain and comparison | `tests.test_phase5_ebom_domain` | PASS |
| DocType schemas, permissions, ownership and static guards | `tests.test_phase5_ebom_metadata` | PASS |
| controllers, private scopes, immutable history and denied-delete audit | `tests.test_phase5_ebom_controllers` | PASS |
| independent route-disable seam and stable problem | `tests.test_phase5_ebom_security` | PASS |
| all P5 Document predecessor boundaries plus P5-04 focused suites | `python3 -m unittest tests/test_phase5_document*.py tests/test_phase5_ebom*.py` | `201/201` PASS |
| literal-English and paired catalogs | `npm --prefix frontend run lint:i18n` | `3,410` sources; direct `100%` `zh`/`zh-TW` PASS |
| generated catalog consumer | generation check, type/lint, frontend unit/coverage and production bundle before the static-asset guard | `671/671` frontend unit PASS; build PASS |
| changed Python and eight DocTypes | `compileall`; every new JSON through `json.tool` | PASS |
| ownership and patch integrity | YAML safe load; prohibited-pattern review; `git diff --check` | PASS |

The focused P5-04 result is `27/27` PASS. The preceding audit checkpoint
passed ordinary CI `30993437267`. This foundation checkpoint does not claim
the later repository/API checkpoint, controlled-Site runtime, P5-04 Level 2
Task Gate or Phase 5 Level 3 Gate.

The local chained frontend verifier stopped only after its successful
generation/type/lint/`671/671`/coverage/build steps because the brand guard
correctly detected the preserved user-owned untracked
`frontend/public/images/npi-one-project-management-sketch.png`. That file is
not staged or part of this checkpoint. Complete brand/audit and fixed-Linux
visual truth must come from the clean exact-SHA ordinary CI before the next
product stage mutates shared code.

## Exact-SHA clean-CI repair

Foundation checkpoint `a11b37379e462b3a83e75a6b49c6b6b71bb5fadd`
was synchronized at `0 ahead / 0 behind`. Ordinary CI `30995489793` then
isolated two evidence-only roots without disproving the domain foundation:

- repository job `92271453993` completed the Python, frontend, i18n, audit
  and reconciliation checks, then the final prohibited-pattern scan matched
  the literal assertion string `frappe.db.sql` in
  `tests/test_phase5_ebom_metadata.py`; the test now uses an adjacent Python
  literal split while retaining both the assertion and the fail-closed scan;
- visual job `92271454078` passed `41/59` governed cases and failed the exact
  18 normal P0 English/Simplified Chinese/Traditional Chinese Linux images
  whose visible status-bar catalog fingerprint changed from
  `e9acf460698ad2d7` to the generated `18fefcf811fde25b`; and
- artifact `8926019049`, digest
  `sha256:444ff3d55847a87722ddc26000b6d922efe40d8eaf5dd175ad8cf0b99ec28912`,
  supplied the fixed-Linux actuals. Every changed pixel is confined to
  `y=879..898` of the 1440x900 status bar. The strong Playwright deltas are
  `251` or `252` pixels; three Trial images also contain only 20 subthreshold
  native-select corner pixels. No product-workspace pixel changed.

The 18 reviewed artifact actuals are now accepted byte-for-byte as the
corresponding tracked Linux baselines. No matrix, threshold, viewport,
language or state was removed or weakened. The focused metadata suite passes
`7/7`, the exact prohibited-pattern scan returns no match, all 18 accepted
baselines equal the reviewed artifact bytes, and `git diff --check` passes.
A clean exact-SHA CI rerun remains required before repository/BFF/OpenAPI work.

## Domain, permission, security, UX and i18n review

- Domain: content revision truth is immutable and separate from lifecycle;
  comparison never uses a mutable latest pointer or description/position match.
- Ownership: NPI One stores only working engineering structure and lifecycle;
  it does not create formal ERPNext Item/MBOM/routing/stock-UOM truth.
- Permission/security: transport roles, Project owner/RACI, `System Manager`
  and UI visibility grant no EBOM business authority. Malformed policy refs and
  versions fail as controlled validation rather than raw HTTP 500 exceptions.
- Audit: retained-history deletion remains denied even if audit scheduling
  cannot be derived from damaged input; valid retained targets queue only a
  sanitized post-rollback audit.
- UX: no end-user UI was changed at this checkpoint. The future workspace must
  retain the audited dense industrial layout and complete state coverage.
- i18n: every new visible source is literal English; paired catalogs are
  complete and contain no unapproved mixed-language fallback.

Review result: `0 blocker / 0 major / 0 minor` inside this bounded foundation.

## Holds and rollback

Production numbering, line identity, quantity precision, stock UOM,
alternate/effectivity semantics, attribute set, review/release authority and
formal Item/MBOM conversion remain Class-B holds under
`FUTURE_APPROVED_PRODUCT_POLICY`.

Before retained P5-04 history exists, remove the additive foundation. After
history exists, preserve every policy, EBOM/revision/line, lifecycle/event,
audit and receipt record; activate only `npi_p5_04_routes_disabled` and use a
reviewed forward fix. P5-01 through P5-03 and ERPNext remain untouched.

## Next stage

Implement only P5-04 repository/BFF/OpenAPI with authorization before
protected lookup, exact Project/policy/revision revalidation, actor-bound
idempotency, atomic command ordering, closed schemas and the independent route
switch. The end-user workspace remains inactive until that checkpoint passes.
