# P4-03 Validation — Gate Templates and Controlled Evidence

Status: **PASS — LEVEL 3 FULL RELEASE GATE**

Validated: 2026-07-24

Branch: `codex/npi-v1.2-implementation`

Starting checkpoint: `996edc3a57160fb55767b06bddc2fc30c557daec`

Atomic task: `P4-03 — Gate templates and controlled evidence`

Requirement allocation: `FR-SG-001`, `FR-SG-002`, `FR-SG-004`, with the
current Phase 4 contribution to `FR-CO-006`

## 1. Bounded outcome

The implemented vertical slice is:

> publish an exact Gate Template version → bind it to a new Project Template
> version → instantiate an exact Project Gate shell → freeze Project-specific
> requirement assignments and dates exactly once → append exact WBS or private
> File Revision evidence → read URL-free live evidence and real scan state from
> the trilingual Gate evidence workspace

It includes:

- an independent, stable, versioned Gate Template aggregate with deterministic
  UUID identity, contiguous published-version history, applicable Project
  types, ordered requirement definitions, a 500-definition bound, and an
  immutable canonical snapshot hash;
- exact optional Gate Template references on new Project Template versions
  without changing historical P4-01 canonical payloads or hashes;
- one retry-safe System Manager command that freezes the exact Gate Template
  reference, explicit Gate due date, owner member, reviewer members, requirement
  dates, evidence kinds, actor, time, and immutable requirement snapshot;
- append-only exact WBS Item and private File Revision evidence references with
  same-Project and same-tenant validation, source version/hash binding,
  optimistic concurrency, actor-bound idempotency, audit, and atomic rollback;
- a server-derived File Revision identity bound to the exact Frappe File name,
  private URL identity, file name, size, Frappe content hash, SHA-256, revision,
  and real scanner-owned state, while the BFF never returns the raw URL;
- authorization before Gate/evidence resolution, including denial when an
  external Website User happens to equal the stored Project owner identity;
- historical exact Gate Template use after its root is disabled while new
  bindings fail closed; and
- the live `/projects/{projectId}/gates/{gateId}` industrial workspace with
  strict ViewModel validation and explicit loading, empty, read-only, partial,
  not-found, no-permission, validation, conflict, retryable, invalid-response,
  and success states in `en`, `zh`, and `zh-TW`.

The slice does **not** implement Gate decisions, P0 normal-pass blocking,
conditional pass, waiver, decision snapshots, reopen/invalidation policy,
normal-user upload/download, production Gate contents, future evidence
resolvers, live notifications, production ERPNext access, or production
scanner/provider policy. Those remain P4-04, P4-05, later-phase, or Class-B
scope.

## 2. Changed-files → affected-tests map

| Change surface | Direct and boundary evidence |
|---|---|
| Gate Template domain, controllers, repository, and four additive DocTypes | `tests/test_phase4_gate_template_domain.py`; `tests/test_phase4_gate_template_controllers.py`; `tests/test_phase4_gate_template_repository.py`; `tests/test_phase4_template_controllers.py` |
| Gate freeze/evidence domain, controllers, repository, BFF/API, Gate/File additive metadata | `tests/test_phase4_gate_evidence_domain.py`; `tests/test_phase4_gate_evidence_controllers.py`; `tests/test_phase4_gate_evidence_repository.py`; `tests/test_phase4_gate_evidence_api.py`; `tests/test_phase4_gate_evidence_metadata.py` |
| OpenAPI and data ownership | `tests/test_phase4_gate_evidence_contract.py`; aggregate OpenAPI/ownership/static checks in `make verify` |
| Real Frappe identities, authorization, idempotency, append-only history, live scan, rollback, and compatibility | `tests/test_phase4_gate_evidence_runtime_verifier.py`; `scripts/verify_gate_evidence_runtime.py`; focused `--gate-evidence-only`; final `make frappe-runtime-verify` |
| Gate live data source, route, shell, page, non-normal states, accessibility, and XSS/invalid-response closure | `frontend/tests/unit/gate-evidence-data-source.test.ts`; `frontend/tests/unit/gate-evidence-page.test.tsx`; affected router/shell/page unit tests; `frontend/tests/e2e/gate-evidence-live.spec.ts`; complete non-visual E2E matrix |
| Shared English-source copy, direct Chinese catalogs, shell/navigation, and visual baselines | `make verify`; 1,274 direct entries per Chinese locale; 159-case forced visual generation and clean zero-difference comparison; original-resolution manual review |
| Early authorization repair on generic Gate Shell updates | single-worker Black on the controller/test; 20 affected controller/metadata tests; final complete Frappe runtime |

## 3. Level 3 evidence

| Command or review | Result |
|---|---|
| `BLACK_CACHE_DIR=/tmp/npi-p403-black-cache make verify` | `PASS` after the sandbox-only registry DNS retry outside the sandbox: 276 Python tests, 237 frontend unit/component tests, devcontainer/config/static/type/ESLint/Prettier/style/boundary/industrial-UI checks, 1,274 literal English sources with 100% direct `zh` and `zh-TW` coverage, coverage, production build, and both npm audits |
| Frontend coverage | `PASS`: 94.36% lines/statements, 91.56% functions, 89.23% branches |
| Production build | `PASS`: 397 modules; Gate route chunk 11.64 kB / 3.63 kB gzip; main asset 881.93 kB / 222.77 kB gzip; the visible size warning remains open as R-010 |
| npm audits | `PASS`: zero vulnerabilities for the full and production-only trees |
| first `make frappe-site-init` | `PASS`: synchronized the new additive DocType schema on the fixed disposable `npi.localhost` Site |
| second `make frappe-site-init` | `PASS`: idempotent migrate and cache refresh at Frappe commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| focused `bash scripts/verify-frappe-runtime.sh --gate-evidence-only` | `PASS`: exact WBS/File evidence, same-content cross-Project denial, wrong tenant denial, disabled-template history, append-only denial, real infected scan state, URL absence, and bounded cleanup |
| final `make frappe-runtime-verify` | `PASS`: BFF localization, P4-01 Project, P4-02 Project work plus cross-process sealed replay, and P4-03 Gate evidence; P4-02 run `1c26208602604b8b82150ac83b443dbf`; P4-03 run `2e070c8599694beabb6f5cf679a8c54b` |
| non-visual Playwright | `PASS`: 153/153 as five bounded specs — 16/16 core flows, 42/42 Gate evidence, 40/40 live Project, 8/8 Project workspaces, and 47/47 states/locales/accessibility |
| forced exact visual generation | `PASS`: shard 1 80/80 plus shard 2 79/79; 159/159 total |
| clean exact visual comparison | `PASS`: shard 1 80/80 plus shard 2 79/79 at `maxDiffPixelRatio: 0`; 159/159 total |
| original-resolution manual review | `PASS`: Gate evidence English 1366×768, Simplified Chinese 1536×864 at 125% equivalent, Traditional Chinese 910×512 at 150% equivalent, and Traditional Chinese read-only 1920×1080 |
| focused independent security review | `PASS`: ten exact live-file drift/zero-byte, URL-leak, external-owner IDOR, Gate Template bound/version/type, and frozen-snapshot integrity tests; no blocker |
| `git diff --check` | `PASS` after the final visual matrix; rerun after controller documentation updates |

The first unsharded non-visual Playwright process was interrupted by session
continuation after 84 tests and produced no exit status. It was not counted as
evidence. The same complete 153-case set was then executed once as five bounded
specs with explicit successful exits.

## 4. Repair history

### 4.1 Focused runtime schema repair

The first focused File evidence run returned 422 because the disposable Site
still had the pre-P4-03 `NPI File Revision` metadata. A read-only query proved
that `frappe_content_hash` was absent from the live DocType. The Site was
migrated; no product identity check was weakened and no old incomplete row was
reused. A fresh run then attached and replayed the exact File evidence.

### 4.2 Idempotency-code assertion repair

The runtime verifier expected the non-contract code
`IDEMPOTENCY_CONFLICT`; the shared domain contract correctly returns
`IDEMPOTENCY_KEY_CONFLICT`. Only the verifier and its static test were corrected.
Eight affected verifier tests and the focused real runtime passed.

### 4.3 Authorization-before-validation repair

The first complete runtime retry proved that a generic Gate Shell PUT was still
denied but returned Frappe ValidationError 417 before the controller's later
PermissionError 403 guard. The controller now runs the authorization guard at
the start of `before_validate` and retains the `before_save` defense. This
restores the P4-01 403 contract and prevents unauthorized callers from learning
field/state validation details. Single-worker formatting, 20 affected
controller/metadata tests, and the final complete runtime passed. In accordance
with the cumulative validation strategy, the already-passing unrelated
aggregate was not restarted after this two-file repair.

## 5. Security, migration, and recovery

- No production ERPNext endpoint, credential, database, or data was contacted.
- All browser operations remain on strict NPI BFF routes. Generic controlled
  history create/update/delete/rename paths are denied.
- Project authorization precedes Gate, requirement, evidence, File, and
  idempotency resolution. Tenant and Project identity are checked on every
  tenant-bearing relation.
- File evidence is private-only, exact-version, URL-free at the BFF, and
  rechecks the live Frappe File identity and privacy before every accepted read
  or attach. Equal content in another Project remains unavailable.
- Schema changes are additive. New fields on legacy-compatible rows are
  nullable at migration, while incomplete historical rows fail closed as
  unavailable evidence.
- Before retained P4-03 data exists, the prior checkpoint can be restored.
  After retained frozen requirements or evidence exists, rollback disables the
  new BFF/live routes, keeps additive tables and immutable history, and deploys
  a reviewed forward fix. It never deletes controlled evidence or uninstalls
  the App.

## 6. Requirement truth

- `FR-SG-001` is a technically verified foundation: versioned Gate templates,
  sequence, applicable Project types, immutable historical snapshots, and
  disabled-root historical reads are proven; production condition/skip policy
  is not implemented.
- `FR-SG-002` is a technically verified foundation: required/optional
  definitions, explicit owner/reviewer/date/evidence types, and frozen
  snapshots are proven; P0 normal-pass blocking belongs to P4-04.
- `FR-SG-004` is a technically verified foundation: exact WBS and private File
  Revision evidence are proven; Document/Trial/Quality/Customer/external-link
  resolvers and decision-time snapshots remain later work.
- `FR-CO-006` remains a technically verified foundation: current P4-03
  UI/API copy is directly covered in `en`, `zh`, and `zh-TW`, but later
  notification, email, print, external-user, and delivery surfaces remain open.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; no Codex-authored evidence
  substitutes for the named external UAT or sanitized-data provenance.

## 7. Final gate decision

The implementation and all executable Level 3 lanes are green. The final
independent release review found no release-blocking implementation,
security, migration, visual, localization, contract, or traceability issue.
P4-03 is `PASS`; P4-04 is active under the existing automatic-transition
authorization.
