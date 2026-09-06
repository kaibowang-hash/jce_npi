# PA-13 ERP master-data selectors

Status: IN_PROGRESS — local checks pass; explicit release authority received;
exact-SHA CI and live activation remain pending.

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

The real Chrome session now requires login; the user was asked to sign in again.
Authenticated dropdown interaction remains pending and is not claimed PASS.
