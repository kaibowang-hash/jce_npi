# P4-04 Validation — Review, Decision, Snapshot, and Reopen

Status: **PASS — LEVEL 3 FULL RELEASE GATE**

Validated: 2026-07-25

Branch: `codex/npi-v1.2-implementation`

Starting checkpoint: `5244a65805ac10e88cad3f7b9902a5fb191cca8c`

Atomic task: `P4-04 — Review, decision, snapshot, and reopen`

Requirement allocation: `FR-SG-003`, `FR-SG-005`, `FR-SG-006`,
`FR-SG-007`, with the current Phase 4 contribution to `FR-SG-002`,
`FR-SG-004`, and `FR-CO-006`

## 1. Bounded outcome

The implemented vertical slice is:

> publish an exact synthetic Gate Review Policy version → bind enabled
> same-Project internal members to frozen authority slots → complete selected
> parallel and sequential reviews → enforce exact Gate inputs, blockers,
> evidence, scans, and policy-bounded exceptions → build an immutable server
> decision snapshot → reopen or invalidate into a successor cycle while
> preserving all prior history and denying downstream use until re-review

It includes:

- an independent, versioned Gate Review Policy with canonical immutable
  snapshots, exact Gate Template version/hash applicability, bounded
  allowlisted step conditions, explicit final-decision/reopen/exception
  authorities, and no policy installed by migration;
- exact frozen authority bindings for enabled same-Project internal members,
  with review assignment separated from final decision, exception approval,
  reopen authority, Project access, and framework transport permission;
- parallel, sequential, and condition-selected review steps with append-only
  actor, time, opinion, version, hash, policy, assignment, and trace identity;
- fail-closed normal pass checks for selected approvals, required P0 evidence,
  exact private-file identity and live scan state, blocking Domain Work Items,
  reviewed-input drift, and exact decision authority;
- policy-bounded non-P0 exception request and decision handling with
  requester/approver separation, exact eligible requirement and authority,
  bounded reason/risk/opinion text, expiry, and an exact same-Project closure
  action reference;
- server-built immutable pass, conditional-pass, and reject decision
  snapshots, with canonical hashes and enough frozen inputs to reconstruct the
  decision without trusting caller-supplied snapshot content;
- manual reopen and exact-input dependency invalidation into one successor
  review cycle, while preserving the prior decision, reviews, exceptions, and
  snapshot and making the current downstream guard fail closed;
- exact closure-action drift handling, including missing, changed-version, or
  changed-hash references, without creating the out-of-scope impact Domain
  Work Item;
- strict same-origin BFF/OpenAPI commands with CSRF, authentication,
  authorization-before-resolution, optimistic versions, actor-bound sealed
  idempotency, receipt reconciliation, request/trace IDs, and no optimistic
  success;
- denied generic create/update/delete/rename paths for controlled review
  history, including one durable audit record after each denied history delete
  request rolls back; and
- the live trilingual industrial Review Room with server-driven actions,
  reconstructable history, exact dependency lineage, honest known-versus-
  unknown write status, stable locale retranslation, focused high-risk
  confirmation, and loading, empty, read-only, denied, error, conflict,
  processing, exception, decided, reopened, and requires-review states.

The slice does **not** install or approve production Gate contents, review
maps, segregation rules, waiver/deviation eligibility, expiry rules, reopen
reason taxonomies, disabled-member substitution, or production dependency and
downstream matrices. It does not create dependency Domain Work Items, deliver
P4-05 My Work/activity/notification projection, add future Document/Trial/
Quality/Customer evidence resolvers, define production scanner/DMS behavior,
connect to production ERPNext, deploy to production, or substitute technical
fixtures for Phase 3 named business UAT and sanitized-data provenance.

## 2. Changed-files → affected-tests map

| Change surface | Direct and boundary evidence |
|---|---|
| Gate Review Policy/domain rules, exact inputs, decisions, reopen, and closure-action drift | `tests/test_phase4_gate_review_domain.py`; `tests/test_phase4_gate_review_policy_repository.py`; `tests/test_phase4_gate_review_repository.py`; Gate Shell and shared Gate evidence regressions |
| Controlled review persistence, history controllers, delete-attempt audit, optimistic versions, and generic CRUD denial | `tests/test_phase4_gate_review_history_controllers.py`; `tests/test_phase4_gate_review_history_metadata.py`; `tests/test_phase4_gate_review_gate_shell.py`; controller/metadata aggregate |
| Repository, dependency hooks, transport capability, strict API, OpenAPI, and ownership boundaries | `tests/test_phase4_gate_review_repository.py`; `tests/test_phase4_gate_review_api.py`; `tests/test_phase4_gate_review_contract.py`; `tests/test_phase4_gate_review_transport_role.py`; shared P4-02/P4-03 contract and repository tests |
| Real Frappe authority, tenant/Project isolation, idempotency, rollback, immutable history, dependency invalidation, and compatibility | `tests/test_phase4_gate_review_runtime_verifier.py`; `scripts/verify_gate_review_runtime.py`; focused `--gate-review-only`; all six final `make frappe-runtime-verify` lanes |
| Strict review/evidence parsers, command coordination, receipts, action codes, and localization lifecycle | `frontend/tests/unit/gate-review-data-source.test.ts`; `frontend/tests/unit/gate-evidence-data-source.test.ts`; `frontend/tests/unit/api-and-telemetry.test.ts`; aggregate frontend unit/coverage lane |
| Review Room actions, failure semantics, 4,000-character inputs, focus, accessibility, and shared primitives | `frontend/tests/unit/gate-evidence-page.test.tsx`; `frontend/tests/unit/primitives-and-objects.test.tsx`; 26-case affected ImpactReview browser lane; complete non-visual browser matrix |
| English source copy, direct Chinese catalogs, catalog hash, shell/shared visuals, and exact baselines | `make verify`; 1,746 direct entries per Chinese locale; forced and clean 170-case visual matrices; zero-tolerance comparison |
| Node/npm security baseline, clean install policy, bootstrap, CI, and environment verification | `tests/test_devcontainer_verifier.py`; static registry/config checks; clean strict `npm ci`; pending-script check; both npm audits; actual fresh-target bootstrap and dynamic environment Gate |
| Requirement truth, task diff, migration, rollback, and release evidence | trace/anchor review; two Site migrations; focused and complete runtime; prohibited-pattern scan; independent release review; `git diff --check` |

## 3. Level 3 evidence

| Command or review | Result |
|---|---|
| `make verify` under Node `v24.18.0` / npm `11.16.0` | `PASS`: 417 Python tests, 337 frontend unit/component tests, devcontainer/config/static/JSON/compile/type/ESLint/Prettier/style/boundary/industrial-UI checks, i18n, coverage, production build, install-script review, both npm audits, trace count, prohibited-pattern scan, and diff check |
| Frappe-compatible i18n audit | `PASS`: 1,746 literal English sources with 100% direct `zh` and `zh-TW` coverage; generated catalogs are current and no fallback-English acceptance is claimed |
| Frontend coverage | `PASS`: 87.11% statements, 87.26% branches, 91.86% functions, and 89.42% lines; thresholds and source scope were not lowered |
| Production build | `PASS`: 398 modules; main asset 988.60 kB / 249.59 kB gzip; lazy Gate route 57.65 kB / 13.75 kB gzip. The visible size warning remains open as R-010 |
| clean `npm ci --strict-allow-scripts`, dependency tree, and pending-script review | `PASS`: 379 packages installed from the lock; only exact application `esbuild@0.25.12` is allowed, optional `fsevents` is denied, no unreviewed script is pending, `npm ls` is clean, and every resolved `brace-expansion` is patched `5.0.8` |
| complete and production-only npm audits | `PASS`: zero vulnerabilities in both trees |
| first `make frappe-site-init` | `PASS`: synchronized the additive P4-04 DocTypes and Gate metadata on the guarded disposable `npi.localhost` Site |
| second `make frappe-site-init` | `PASS`: idempotent migrate and cache refresh at Frappe commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| focused `bash scripts/verify-frappe-runtime.sh --gate-review-only` | `PASS`: exact authority/IDOR behavior, reviews, exceptions, decisions, receipts, history denial/audit, rollback, reopen, closure-action drift, invalidated/refreshed successor cycles, downstream rejection, idempotency, and bounded cleanup |
| final `make frappe-runtime-verify` | `PASS`: all six live lanes completed — base BFF/localization, P4-01 Project, P4-02 Project work fresh execution, P4-02 cross-process sealed replay, P4-03 Gate evidence, and P4-04 Gate review |
| `npm --prefix frontend run test:e2e` | `PASS`: 204/204 non-visual Chromium cases in 7.0 minutes |
| affected ImpactReview browser lane | `PASS`: 26/26 cases in 1.0 minute after the final failure-message, focus, and 4,000-character boundary repairs |
| `npm --prefix frontend run test:visual:update` | `PASS`: complete forced regeneration 170/170 in 5.4 minutes |
| `npm --prefix frontend run test:visual` | `PASS`: clean exact comparison 170/170 in 4.9 minutes at `maxDiffPixelRatio: 0`; no tolerance change |
| actual fresh Node 24 target | `PASS`: retained disposable container `ec87589840647a343123667c386f0f9ff5a9e34fb14e7f0af158c5d766061cb4`, label `npi.fresh-target=p4-04-node24`, created `2026-07-25T07:39:09Z`; missing-state strict global install, idempotent bootstrap, and `make verify-dev-environment` passed with Node `v24.18.0`, npm `11.16.0`, Yarn `1.22.22`, Python `3.11.13`, Docker client/server `28.3.3-1`, Compose `2.40.3`, Bench `5.31.0`, uv `0.11.30`, Vite `5.4.14`, esbuild `0.21.5`, and the pinned Frappe commit |
| Task Diff, contract, permission/security, migration/rollback, trace, and independent release review | `PASS`: no blocker, major, or minor implementation finding remained; no production dependency or business-policy claim was promoted |
| final `git diff --check` | `PASS` |

The first complete non-visual browser attempt produced `0/204` because the
execution sandbox denied Vite's local `127.0.0.1:4173` bind with `EPERM`; it
entered no product test and is not counted as evidence. The complete run was
then executed once in the permitted local-binding environment and passed
204/204.

The first forced visual update completed 169/170 before one transient blank-page
timeout. That incomplete run is not counted. A complete forced regeneration
then passed 170/170, followed by a separate clean 170/170 zero-difference
comparison.

## 4. Repair history

### 4.1 Closure lineage, immutable-history audit, and long-text boundaries

The final dependency review found that an exact exception closure action could
change or disappear without invalidating a decided Gate. The repository now
compares the retained exact action identity, version, and hash, increments the
protected Gate input version under the controlled dependency scope, creates
exactly one successor cycle/event, preserves the prior decision, and keeps
downstream use denied. Repeated evaluation is a no-op. A focused real-runtime
case proves the transition and rolls its disposable fixture back.

Generic deletion of each controlled review-history type was already denied,
but the denied attempt did not survive the request rollback as durable audit
evidence. The controller now queues one exact actor/target/version/trace audit
for the post-rollback transaction while preserving the deletion denial. Unit
and live runtime checks prove one audit per target and unchanged retained
history.

Review opinions, exception reasons/risks/opinions, and reopen reasons now share
the same 4,000-character API/domain/controller boundary. The Review Room also
enforces `maxLength` and bounded state updates. Exact 4,000-character inputs
are accepted and 4,001-character inputs are rejected; no browser-only limit is
trusted.

### 4.2 High-severity npm advisory and Node 24 baseline

The first Level 3 audit correctly failed after the newly published
`GHSA-mh99-v99m-4gvg` identified `brace-expansion <=5.0.7` as High severity.
The finding was not suppressed. ADR-011 moves the exact development/CI
baseline from end-of-life Node 18 to Active LTS Node `24.18.0` with bundled npm
`11.16.0`, upgrades only the affected development-tool parents, preserves
product dependencies, and resolves every vulnerable path to `5.0.8`.

The independent application Gate used the official Linux x64 archive only
after its SHA-256 matched Node's published value
`55aa7153f9d88f28d765fcdad5ae6945b5c0f98a36881703817e4c450fa76742`.
The repository verifier now inspects and rejects an executing Node/npm version
that differs from the pins instead of allowing a stale shell or fallback
runtime to produce a false Gate. The actual fresh target then proved the
native pinned lifecycle.

### 4.3 Strict install-script policy

npm 11's `allowScripts` metadata alone is advisory unless strict mode is
enabled. The application therefore sets `strict-allow-scripts=true`, permits
only exact `esbuild@0.25.12`, explicitly denies optional `fsevents`, checks for
pending scripts, and runs strict clean installation from the frontend
directory in Make and CI so the project `.npmrc` is loaded.

The separate global Vite smoke tool permits only exact esbuild `0.21.5` and its
exact optional macOS-only `fsevents@2.3.3` hook; fsevents remains absent on
Linux. The bootstrap rejects broad or unversioned script approval and
`--dangerously-allow-all-scripts`.

### 4.4 Repository verifier and upstream credential scope

The prohibited-pattern scan previously treated any nonzero `rg` result as
success, so an unavailable command or scan error could be mistaken for “no
matches.” The verifier now requires `rg`, accepts only exit 1 as no finding,
fails on exit 0 matches, and propagates every other error. Static mutation
tests reject restoration of each false-success form.

The registry verifier can use an existing GitHub token to avoid anonymous API
limits, but adds `Authorization` only for the exact HTTPS
`api.github.com` origin with no userinfo and default port. Independent review
reproduced Python's default cross-origin redirect forwarding; the repaired
redirect handler now rejects every authenticated redirect that leaves that
origin before a new request is created. Tests prove that HTTP downgrade,
non-default ports, npm, normal GitHub web URLs, lookalike hosts, and
cross-origin redirects never receive the token.

### 4.5 Local Docker stale service recovery

The final migration/runtime prerequisite initially stopped before product
execution because Docker retained stale OCI task state for the controlled
MariaDB/Redis containers. Only the exact stale task directories were moved to
a recoverable `/tmp` backup. The named containers and volumes were preserved;
no database reset, volume deletion, replacement Site, or production data
operation occurred. Both migrations, the focused runtime, and the complete
six-lane runtime then passed.

### 4.6 Browser sandbox and exact visual evidence

The local-port `EPERM` browser attempt was classified as an environment
preflight failure rather than a product failure or partial pass. No tests,
retries, or assertions were weakened; the valid complete run passed 204/204.

Four final failure-semantics sources changed the generated catalog version
from `fe87273ddba85cf7` to `a35cf1717e9e4a04`. Because the shared catalog and
Node/Vite rendering boundary affect application-wide screenshot hashes, the
complete visual set was forcibly regenerated instead of accepting stale
images. The final baseline change comprises 153 PNGs: six Gate Review, twelve
Project live, six Project workspace, and 129 shared visual-matrix images. The
single transient blank image from the incomplete 169/170 attempt was discarded
through a complete rerun; the separate clean run proves 170/170 exact matches.

## 5. Security, migration, and recovery

- No Frappe or ERPNext core file was patched. No production ERPNext endpoint,
  credential, database, scanner, DMS, or customer data was contacted.
- Browser operations remain on strict NPI BFF routes. Authentication, CSRF,
  Project authorization, tenant isolation, and exact Gate/cycle membership
  checks occur before protected resolution.
- `NPI API User` is a non-Desk framework transport capability, not approval
  authority. Project ownership, RACI, reviewer identity, role membership, or
  `System Manager` status does not bypass the exact frozen policy authority.
- Guest, external, cross-tenant, cross-Project, disabled, unassigned, stale,
  and mismatched actors fail closed. Generic controlled-history writes remain
  denied and denied deletes are audited without allowing the deletion.
- Commands bind actor, operation, Project, Gate, expected versions, input
  hashes, idempotency key, and trace identity. Lost or uncertain responses
  retain a bounded receipt for reconciliation and never claim optimistic
  success.
- Exact private File evidence remains URL-free and revalidates live identity,
  privacy, hash, version, and scan state at decision and dependency time.
- Schema changes are additive and the same guarded Site migrated twice
  successfully. Existing Gates remain fail-closed until explicitly bound to
  an exact review policy and cycle.
- Before retained P4-04 history exists, the starting checkpoint may be
  restored. After reviews, exceptions, events, or decisions are retained,
  rollback disables the new BFF/live routes, preserves additive tables and
  immutable history, denies downstream use, and deploys a reviewed forward
  fix. It never deletes approvals or rewrites a decision.
- The Node security rollback must not restore Node 18 or another end-of-life
  or known-vulnerable runtime. Any replacement requires a supported LTS line,
  exact registry/checksum review, strict clean installs, both audits, and
  equivalent fresh-target plus Full Release Gate evidence.

## 6. Requirement truth

- `FR-SG-003` is a technically verified foundation: versioned parallel,
  sequential, and condition-selected review with exact actor/time/opinion/
  version evidence is proven; the production review policy and approval map
  remain a Class-B hold.
- `FR-SG-005` is a technically verified foundation: fail-closed blockers and
  policy-bounded non-P0 exceptions with reason, risk, approver, expiry, and
  exact closure action are proven; no production waiver or deviation policy is
  installed.
- `FR-SG-006` is technically verified for immutable server-built decisions,
  preserved prior approvals/history, and controlled successor-cycle reopen.
  It does not authorize a production reopen reason taxonomy.
- `FR-SG-007` is a technically verified foundation for exact-input
  invalidation, successor cycles, preserved decisions, and downstream denial.
  P4-05 owns work projection, and no production dependency matrix or
  dependency-generated Domain Work Item is claimed.
- `FR-SG-002` retains its truthful foundation status: exact frozen Gate inputs
  and P0 normal-pass blocking are proven against a synthetic policy, while
  production Gate contents remain held.
- `FR-SG-004` retains its truthful foundation status: exact WBS/private File
  evidence and decision-time snapshots are proven; Document, Trial, Quality,
  Customer, and external-link resolvers remain later work.
- `FR-CO-006` retains its truthful foundation status: current P4-04 UI/API
  copy is directly covered in `en`, `zh`, and `zh-TW`, while later activity,
  notification, external-user, email, print, and delivery surfaces remain
  open.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; this technical Gate does not
  replace named external business sign-off or provenance-backed sanitized-data
  review.

## 7. Final gate decision

The bounded P4-04 implementation and every applicable Level 3 executable lane
are green. The final independent release review found no release-blocking
implementation, security, permission, migration, rollback, contract, visual,
localization, or traceability issue. Tests, coverage thresholds, strict install
policy, and visual tolerance were not weakened to obtain the result.

P4-04 is `PASS`. P4-05 is active under the existing automatic-transition
authorization. This decision accepts the generic technically verified review
and decision foundation only; it does not claim production policy approval,
production ERPNext readiness, Phase 3 business UAT, or production deployment.
