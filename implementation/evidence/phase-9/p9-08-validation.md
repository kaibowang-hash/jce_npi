# P9-08 — Controlled Full-Product UAT Validation

Recorded: `2026-09-03`

Status: `FINAL ERP READ-ONLY RECONCILIATION PASS — FINAL EVIDENCE ORDINARY AND LEVEL 3 PENDING`

Requirement: `UX-003`

## Authorization

- Accepted P9-07 predecessor:
  `d911c2bcecb228cee0f4830c868e0d0fdf35d3e2`; ordinary CI
  `33730217862`; diagnostics-off Level 3 `33730710124`; release-gate PASS.
- P9-08 governance:
  `4ee5d301997215526d245c27f4dbc0497b5003cf`; ordinary CI
  `33732955637` PASS.
- Governance jobs: frontend verify `100576877339`; secret
  `100576877474`; E2E shard 2 `100576877502`; repository `100576877546`;
  E2E shard 1 `100576877594`; visual `100576877621`; frontend aggregate
  `100578369221`.

## Implemented evidence

The batch adds no product behavior, contract, schema, role, workflow, adapter,
translation or visual baseline. It adds:

- one strict `p9-08-controlled-uat.v1` manifest for AT-01 and AT-02;
- one fail-closed Python verifier with duplicate-key, exact-shape, route,
  requirement, evidence-file, selector, family, scenario and claim checks;
- seven focused verifier tests;
- two Playwright route-context checks consuming the same manifest.

All twenty frequent development activities bind existing executable evidence.
Seventeen required families are covered: Project/My Work, permissions,
documents/baselines, EBOM, Gates, Tooling, Trial, quality/readiness, ERP
projections, ERP execution, integration operations, Change Control,
reporting/collaboration, security, data exchange, recovery and
localization/visual truth.

## Controlled results

| Scenario | Qualifying | Denominator | Ratio | Golden and fault | Result |
| --- | ---: | ---: | ---: | --- | --- |
| AT-01 customer-owned mold | 9 | 10 | 90% | present | PASS |
| AT-02 new tooling | 9 | 10 | 90% | present | PASS |
| Combined | 18 | 20 | 90% | present | PASS |

The numerator contains only activities that start from My Work or remain in
the same Project and governed child workspace. The sole nonqualifying activity
in each scenario is permission-filtered reporting at `/reports`; it remains in
the denominator so the result is not manufactured by excluding a real user
activity. Background, administrator and ERP-owned execution are outside both
counts because they are not LaunchFlow end-user development activities.

Manifest canonical checksum:
`sha256:a9866b40ff467b82096be1cd9696cfc7cda1b5de283cf9ffc4faefe94594c411`.
The verifier emits `productionContact=false`.

This is a controlled non-production technical UAT result. It is not a real
pilot, real-project observation or measurement that 80 percent of real users
use the product. M9-04 and M9-05 remain user-approved post-V1.2 deferred.

## Local Level 2

| Check | Result |
| --- | --- |
| Manifest JSON and verifier | PASS; AT-01 `9/10`, AT-02 `9/10`, overall `18/20` |
| Focused Python verifier tests | `7/7` PASS |
| Consolidated Playwright route-context checks | `2/2` PASS |
| Python compilation and diff hygiene | PASS |
| Complete repository verification | `2990/2990` PASS |
| Frontend type, lint, boundaries and industrial UI audit | PASS |
| Frontend i18n | `9322` literal English sources; 100% direct `zh`/`zh-TW` coverage |
| Frontend coverage | `1140/1140` PASS; statements `80.06%`; branches `79.50%`; functions `82.10%`; lines `82.65%` |
| Production build and bundle budgets | PASS |
| Dependency audit | PASS; zero vulnerabilities |

The first local frontend coverage run had one unrelated existing Trial test
exceed its five-second host timeout; an immediate exact-test retry passed in
`997ms`, and the unchanged complete retry passed `1140/1140`. No code or
threshold changed.

The local final brand scan is intentionally not called PASS: it detects a
pre-existing user-owned untracked file under `frontend/public`. The task does
not move, delete, stage or allowlist that file. The candidate's clean-checkout
exact-SHA ordinary CI must pass the unchanged brand guard and full frontend
lane.

Implementation candidate
`1761323f934e762b706405e74e059071d26e9564` passes exact-SHA ordinary CI
`33734762911` in repository `100582623939`, secret `100582624107`, frontend
verification `100582624172`, E2E shard 1 `100582624283`, E2E shard 2
`100582624021`, visual `100582624087` and frontend aggregate `100583921017`.
The clean checkout passes the unchanged brand guard; the user-owned local asset
remains untouched.

The established collector has no P9-08 task identity. A zero-contact narrow
transition therefore adds only one fixed full-refresh operation plus exact
cleanup. It binds every app source signature, accepted runtime metadata family,
locale/File aggregate, P9-01 change scope and P9-04 security scope. It accepts
no caller-selected remote scope. Detailed sanitized output remains in a local
mode-0600 temporary result and is deleted after evidence promotion. No SSH or
Site contact occurs until this transition passes exact-SHA ordinary CI.

Collector transition `1323db574b147f2b43c69502ecdf5b2f25d9976b`
passes exact-SHA ordinary CI `33736062145`. Its first authorized read attempt
failed closed at runtime metadata parsing because Frappe v15 represents a
successful empty `frappe.client.get_list` result as exact empty stdout. No
result file survived. The bounded parser correction gives exact empty stdout
the same empty-list meaning already proven for the P9-01 and P9-04 fixed
collectors; whitespace, non-JSON, non-list and non-zero/stderr responses remain
rejected. Repair `194733fc72df6fc045727074991eb70acf0aab8f` passes
exact-SHA ordinary CI `33736966780`.

The repeated fixed operation completed at
`2026-09-03T09:16:57.085930Z`, performing 268 bounded reads over twenty
applications and nineteen runtime metadata families with
`production_write=false`. Canonical result checksum
`sha256:466520fe71fdd9cb6de4acf5a8cb2eaefbb58df19b6f564e62474c091ca69ddb`
matched independent calculation. The final compatibility evidence classifies
all current dependencies; anonymous-app source, additive runtime metadata,
File aggregate volume and ECR Workflow changes are assessed production drift
with no contract/ownership conflict and `NO_CHANGE`. There is no actual
dependency classified `UNVERIFIED`, `LAUNCHFLOW_DRIFT` or `BOTH_DRIFTED`.
The private mode-0600 result was deleted by the exact cleanup operation.

## Remaining gates

1. Commit and push the final sanitized evidence/state and require ordinary CI
   PASS at that exact SHA.
2. Run one final diagnostics-off Level 3 and release-gate review at that final
   evidence SHA.

No production write, SQL, console, migration, service action, permission
change, replay/reconciliation action, credential collection or core change is
authorized. Rollback removes only the manifest, verifier, tests and P9-08
evidence.

## Final Level 3 fixture repair

Final evidence candidate `1b277bae5cb1337e82b5287aa5d29ae38c901210`
passes exact-SHA ordinary CI `33739258581` in every ordinary lane. Its
diagnostics-off Level 3 `33739791065` passed repository, secret, frontend,
both E2E shards, visual, aggregate and controlled preflight. The cumulative
disposable runtime job `100600373402` then stopped at the historical P8-03
migrated-legacy problem-code assertion; cleanup passed. No production system
was contacted.

The same family had previously been uniquely classified as a retained
same-effect Guard. Static preflight of every remaining migrated-legacy call
showed one avoidable interval: the fixture removed its exact disposable Guard
before starting the Web process, then performed startup, login, context and
read probes before the reconciliation POST. The product Guard precedence and
expected problem contract remain correct.

The product-zero repair moves the existing marker-gated exact Guard isolation
inside `legacy-only`, immediately before the POST, and requires a second
fixture process to observe the committed legacy row with zero Guard rows. It
does not accept an alternate problem code, change product repositories, enable
diagnostics, alter CI or contact production. Focused static/unit preflight is
`31/31` PASS, Python compilation, shell syntax and diff hygiene pass. The
single batched repair requires exact-SHA ordinary CI, followed by one
replacement diagnostics-off Level 3.
