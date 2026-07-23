# Last Run

- Timestamp: `2026-07-23T03:20:38Z`
- Branch: `codex/npi-v1.2-implementation`
- Starting HEAD: `24e901d8b908`
- Starting upstream state: ahead 0 / behind 0
- Atomic task: `P4-01 — Project template and live cockpit vertical slice`
- Result: `PASS`
- Current phase: `4 — Project Work Items and Stage Gates`
- Next task: `P4-02 — Team, RACI, WBS, and domain work items`

## P4-01 outcome

- Added generic versioned Project templates and nine additive persistence
  DocTypes without installing a production default.
- Added a strict domain service and Frappe repository that atomically creates
  a draft Engineering Project plus G0/G1 shells from an exact immutable
  published-template snapshot.
- Enforced tenant-scoped explicit business codes, stable UUID identity,
  expected version, actor-bound idempotency, rollback-safe races, audit, CSRF,
  closed request fields, correlated request/trace IDs, and controller guards
  for children and controlled history.
- Added strict create/query Project contracts and live BFF routes under
  `/api/npi/v1`, with owner/System Manager authorization and IDOR-safe
  not-found behavior.
- Switched the accepted Project cockpit path to the live BFF while retaining
  the fixture only as an explicit demo. Normal and required non-normal states
  pass in `en`, `zh`, and `zh-TW`.
- Kept FR-PM-001, FR-PM-003, and FR-PM-004 at truthful partial/foundation
  status; production deliverables/roles/duration, complete required-reference
  policy, charter fields, and the formal immutable G1 baseline remain future
  work.

## Verification

| Command / review | Result |
|---|---|
| `make verify` | `PASS` — 120/120 Python tests, 153/153 frontend tests, static/type/style/boundary/UI/i18n checks, coverage, build, and both npm audits |
| `npm --prefix frontend run test:e2e` | `PASS` — 103/103 non-visual Chromium tests |
| `npm --prefix frontend run test:visual:update` | `PASS` — 141/141 forced baseline generation |
| clean exact visual comparison | `PASS` — native Playwright shards 71/71 + 70/70 at `maxDiffPixelRatio: 0` |
| three-image live Project manual review | `PASS` — English, Simplified Chinese, and Traditional Chinese at original resolution |
| `make frappe-site-init` plus idempotent rerun | `PASS` — Frappe 15.115.4 at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| `make frappe-runtime-verify` | `PASS` — live create/query, permissions, CSRF, sequential idempotent replay/conflicts, audit, mutation guards, localization, and cleanup; aggregate adapter tests cover race rollback/reload |
| prohibited-pattern and whitespace review | `PASS` |

The final aggregate retains 738 literal English sources with complete direct
`zh` and `zh-TW` coverage. Coverage is 93.63% lines/statements, 91.23%
branches, and 91.05% functions. The production build transformed 392 modules;
the main JavaScript asset is 789.33 kB minified / 199.73 kB gzip, so R-010
remains open. Both npm audits found zero vulnerabilities.

The real Frappe Project runtime created exactly two Gate shells, replayed an
identical command without duplication, returned 409 for changed idempotency
payload and business-code/version conflicts, returned 403 for tenant mismatch,
returned 404 for IDOR, denied generic Project CRUD, denied nine standalone
child mutations and seven history deletes, recorded one audit event, and
confirmed that no template is installed by migration.

Complete evidence is in
`implementation/evidence/phase-4/p4-01-validation.md`. Phase 4 remains
`IN_PROGRESS`; P4-02 is active under the automatic-transition authority.
