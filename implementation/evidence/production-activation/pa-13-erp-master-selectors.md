# PA-13 ERP master-data selectors

Status: TEST_RELEASE_PASS — the requested dropdown slice is deployed and live
verified. Global implementation/production closure remains unclaimed pending
the separately governed production compatibility reconciliation.

## Scope and source evidence

The user authorized changing ERPNext-derived manual inputs into dropdowns.
Work occurs in the isolated full-integration worktree based on
`07ae1fefc0c8e1ed299106e6579952ca5008b5e2`; the dirty main checkout is preserved.
Read-only source inspection on ERPNext-test confirmed `Mold Trial Report.workstation`
is a Link to `Workstation`, while the legacy `machine` field is plain Data.
The bounded catalog maps Workstation name, workstation_name, disabled,
workstation_type and modified, using optional metadata checks for v15/v16.
No ERP core, published template, business document or production ERP was changed.

## Changes and checks

| Changed scope | Affected evidence |
| --- | --- |
| Catalog projection, Workstation hooks and additive Select enums | master-data domain/repository/API/worker/metadata tests |
| Selection validation and ERP Unicode references | selection, Project/Tooling/Trial domain and repository tests |
| Searchable selector and closed BFF parser | selector and source unit tests; loading/empty/error/retry/disabled/paging/keyboard cases |
| Project customer, Tooling customer/import, Trial machine/material | existing page/API tests and Trial planning/execution browser tests |
| English sources and Frappe CSVs | generated catalogs, coverage, mixed-language scans, three-locale UI evidence |

Catalog absence, stale sync, disabled/deleted entries and denied scope do not
produce selectable fallback text. ERP IDs are submitted exactly; display names
and stock units are populated from the projection. This does not assert machine
booking, capacity, parameter acquisition or ERP execution verification.
Existing domain authorization/version/audit checks and exact replay precede new
catalog validation, preserving historical references and idempotency behavior.

## Migration, release and rollback

Local evidence on 2026-09-06:

- Full repository: 3,182 tests PASS. Subsequent machine mapping/status/metadata
  and selection checks: 25 tests PASS; final exact-SHA CI must recheck the delta.
- Pinned Node 24.18.0 / npm 11.16.0 frontend gate: 1,190 tests PASS, full build,
  type/lint/boundary/UI checks PASS; 9,501 English sources with 100% direct
  zh/zh-TW coverage; both dependency audits report zero vulnerabilities.
- Existing Trial planning/execution browser suites: 16/16 PASS, including
  localized dropdown keyboard/a11y checks and real BFF transport tests.
- Three screenshots under `pa13/erp-master-machine-{en,zh,zh-TW}.png` use
  local controlled fixtures, not live ERP connection evidence.
- Browser tests caught the shared client's path/query split; the selector now
  uses its query option and tests the actual HTTP client, not only a mocked method.
- ERPNext-test read-only preflight confirms connector 0.10.0. No test business
  document was created or modified.

Online LaunchFlow SSH preflight was rejected by automatic safety review because
it classified the live LaunchFlow host within the production connection hold.
No LaunchFlow connection or mutation was made. The user has been asked to confirm
the precise scope: backup/update LaunchFlow plus ERPNext-test, never JCE Core
production ERPNext. Do not retry that host without resolving this authority hold.
Release Gate: BLOCKED pending exact-SHA Level 3, scope clarification and live proof.

The implementation is committed locally as `4b32e724`. A subsequent push to the
existing `kaibowang-hash/jce_npi` GitHub repository and Level 3 workflow dispatch
was also rejected before execution by automatic review, requiring explicit
authorization to transmit this code and its controlled test evidence to that
destination. No push or new CI run occurred. Resolve both the GitHub and online
deployment scope approvals before continuing; do not work around either rejection.

New patches reload only the NPI support DocTypes to add the machine enum; they
do not alter standard ERPNext DocTypes or erase history. Receiver upgrade must
precede connector upgrade and machine reconciliation. Prior exact images,
connector release and fresh backups must be retained. Roll back application
releases without destructive schema downgrade; do not delete master snapshots.

Full release and authenticated live checks remain pending. This task does not
claim production readiness or replace the required final production compatibility
reconciliation under its separate authorization boundary.

## Explicit authorization after the review holds

The user answered “允许” to the precise request to push code and controlled test
screenshots to existing `kaibowang-hash/jce_npi`, run complete CI, and after PASS
back up and update LaunchFlow and ERPNext-test, without connecting to or changing
JCE Core production ERPNext. Both previous pre-execution review holds are now
resolved by this new authority; their historical records above remain unchanged.
Release Gate is still pending exact-SHA ordinary/Level 3 and live evidence.

## Initial activation and live ordering repair

Release `695afbbbf60b3a28740c5990f83b637a4a06a01b` passed ordinary CI
`34038154058` and Level 3 `34038151983`: 3,183 repository tests, 1,191 frontend
tests, 478 browser cases and 135 fixed visual cases. The controlled v15 runtime
job `101500713678` passed; artifact `9991052328` has digest
`sha256:825c490de36058dce4ee2708f7f58b98704a9aa3e7dd7e5b617b7c1d24ad7fef`.
All 9,501 English sources retain complete zh/zh-TW coverage and audits are clean.

LaunchFlow was backed up and upgraded to that exact backend and SPA revision;
all ten services and the public health contract passed. The encrypted backup
checksum is `deceb9d89da92191fd54374a3c5c96fb50ab16c8cfd4e6b6edb4d723b7fd3675`.
Backend image digest is `0fe73accfc7798c0818b6cf87a3e425ccde348026b3ceda3e4f718be7645d466`;
SPA image digest is `3ebdeb8c0b5a0a432fae49a3ce6a495a85048d82a2b1d1e893e3c53a7ca9e914`.
The SPA uses the fully verified immutable spa-builder layer from the unchanged
Containerfile and its identical final pinned Nginx/COPY/health-check stage;
unused legacy-builder backend stages were not needed for packaging.

ERPNext-test routing was explicitly verified to use `jce.1` (v16), not the
co-located older v15 Site. A full database/config/public/private backup and
checksum verification preceded connector 0.11.0 deployment. Standard Frappe
migration unexpectedly removed three pre-existing orphan Report definitions.
All three were restored transactionally from their exact Deleted Document
snapshots, with substantive content and role hashes matching. One already-dangling
role reference was retained exactly through the public insert recovery option;
normal create permissions and Report validation remained enabled. No Role was
created, no permission granted, no core source written, and recovery audit is
retained. Do not repeat Site-wide orphan cleanup for the code-only correction.

Live Workstation synchronization exposed SQL collation order differing from the
contract's code-point order, causing the sender's sorted/unique validation to
reject the catalog before transmission. Connector 0.11.1 sorts the complete
bounded projection before hashing, without changing keys, dropping duplicates,
loosening receiver validation or altering master records. A regression covers
case/Unicode order, hash stability across DB ordering and duplicate rejection
for all five kinds. This code-only connector correction still needs its exact
CI and test-host activation; LaunchFlow source and schema need no further update.

At that checkpoint the real Chrome session required login. The authenticated
session subsequently became available; the final evidence below supersedes
the pending CI, activation and login states above.

## Final test release and authenticated evidence — 2026-09-06T15:31Z

Exact connector correction `569be6ed61ac7fff92383e4a3a6826a9678e5edb` passed
ordinary CI `34041371487` and complete Level 3 `34041369501`: 3,184 repository
tests, 1,191 frontend tests, 478 browser tests and 135 visual cases. The v15
controlled runtime job `101509448770` passed; artifact `9992001278` digest is
`sha256:68831613a4d893dae4dca87038213b9d9c9ea7b203bc445ce61921a5393c9842`.
Its restore and forward-fix checks are true and productionContact is false.
All 9,501 English sources retain complete zh/zh-TW coverage; audits report zero
vulnerabilities. The original three-locale controlled screenshots remain valid
because the correction changes no frontend file.

After both gates passed, only the three changed connector files were installed
on ERPNext-test, with a fresh exact-code rollback archive whose SHA-256 is
`cad1cd2e588face11a378bcfee8eb319a3da6a393787b370c1183dd69d1bf420`.
Their deployed checksums equal the exact checked-out release. The fixed
reconciliation was queued and all three relevant Supervisor processes run.
The Site imports connector version `0.11.1`. `bench list-apps` still displays
the last-migration registry value `0.11.0`; this is not the loaded code version
and is not a reason to rerun destructive orphan cleanup. Verify imported version
and exact file checksums for this code-only update.
There was no second Site-wide migration and no further LaunchFlow deployment.
The retained full backups and earlier application releases remain available.
LaunchFlow still runs exact backend/SPA `695afbbb`; its final health contract
passes with ten running services and zero unhealthy services.

Both sides independently report the following matching version/count/payload
hash tuples. All receiver heads are fresh, explicitly sourced from `test`;
each latest delivery succeeded on attempt one without an error code.

| Catalog | Records | Source version | Receiver and delivery-response payload SHA-256 |
| --- | ---: | ---: | --- |
| Customer | 13 | 14 | `31c9e31dc9369be5462834966a5c3098ad28fa6c2978db504e193774854d5fdc` |
| Supplier | 35 | 14 | `25af260e0b6d44063d7dcb7a36259d4c5716de5e53e2ba172af7eebebd1984c4` |
| Item Group | 24 | 14 | `53caf2a0fd4a773d03ed7f82f7cf5f6f19f5bb4adb9332f2e09cfede8efc6ba1` |
| Item | 816 | 14 | `1a6dd947fb7b752db4aa56fdea1aeb9e255d928a99bdbba828fe153d3261503d` |
| Machine | 126 | 1 | `4fe162772ba0666ea055174afd2ebfe2e005a418a39674fee5114616a5a23135` |

Authenticated Chrome verification used the existing user's real session in a
separate verification tab; the user's administration tab was left untouched:

- Trial proposed material lists real ERP items, searches by exact code, accepts
  ArrowDown/Enter selection and automatically fills the source stock unit.
- Trial proposed machine lists real Workstations, pages to the next twenty,
  searches by source-name text and accepts keyboard selection of the exact
  Unicode ERP key. Visual inspection confirms the square industrial selector
  layout and no overlapping clipped dropdown text.
- Tooling import renders a customer combobox and an honest project-scoped empty
  state. This existing project has no customer references. The available
  published create-Project template does not allow customer references, so its
  create form correctly has no customer picker; the allowed-template path is
  covered by regression tests. No template or customer scope was changed to
  manufacture a nonempty live result.
- All drafts were cancelled. No Project, Trial Plan, workbook registration or
  other business record was submitted. The verification tab reports zero
  browser console errors. Live business screenshots were inspected in-session,
  not persisted to Git or uploaded as controlled fixture evidence.

Independent recovery verification confirms all three restored Report definitions
and all three restoration audit records exist. Developer mode was false both
before migration and after recovery, so Report deletion did not remove source
directories. Substantive metadata and existing roles remain unchanged.

Release-gate result for this authorized **test** deployment: PASS. ERP master
ownership, server-side scope/freshness validation, translations and failure
states are unchanged by the live repair. No production ERPNext/JCE-Core contact
occurred. This does not approve workbook production mappings, resource booking,
published-template changes or overall production readiness. The controller
retains IN_PROGRESS solely to avoid asserting global IMPLEMENTATION_COMPLETE
before the separately authorized final production compatibility gate.
