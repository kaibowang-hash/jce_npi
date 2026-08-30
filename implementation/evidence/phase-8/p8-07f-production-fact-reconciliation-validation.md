# P8-07F Production Fact Reconciliation Validation

Date: `2026-08-30`

Status: **IN PROGRESS — FACTS RECONCILED; FINAL LEVEL 3 PENDING**

## Accepted Gates

- P8-07 product: exact SHA
  `edf89e79cd815cbde60e2940ae9d580479336d75`, ordinary `33277289693`,
  Level 3 `33277905251`.
- P8-07F governance: exact SHA
  `d919d695972260fa86d5df7fa60033e6adb62f49`, ordinary `33279778063`,
  Level 3 `33280319184`.
- P8-07F facts activation: exact SHA
  `c8d3b3c0e9fd3f8d92a1679713ef8afc0157ff20`, ordinary `33281944546`:
  secret `99178460514`, repository `99178460580`, visual `99178460608`,
  frontend `99178460653`.
- Fixed Bench-root harness: exact SHA
  `9ab9bd5199e5521f3a72e701c3fa4338d6e866db`, ordinary `33295753975`:
  secret `99215002723`, repository `99215002838`, visual `99215002811`,
  frontend `99215002791`.
- APP_STATUS token harness: exact SHA
  `be03972abd13b60284a8f950eae7cdf7776781d7`, ordinary `33296694027`:
  secret `99217479469`, repository `99217479519`, visual `99217479571`,
  frontend `99217479523`.

## Read-only operation ledger

At `2026-08-30T00:04:24Z` / `2026-08-30T07:04:24+07:00`, the collector
attempted only `ERP_VERSION` through source label
`JCE_CORE_PRODUCTION_REDACTED`. The result was
`UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT`.

No stdout/stderr, endpoint, host, user, key, secret, Site identifier, raw
version, business value or response shape was accepted, displayed or committed.
The private state file was not created. `INSTALLED_APPS` and all five APP
operations were not invoked. There was no retry, SSH alias probe, command or
allowlist change, REST fallback, privilege expansion, Site/console/SQL action,
production write, replay or reconciliation action.

At `2026-08-30T05:35:04Z` / `2026-08-30T12:35:04+07:00`, the user requested a
connection check. Exact SHA
`5b72a85503ba77f6d55b94255f1d805bbcf5475d` had passed ordinary CI
`33283299773`, so the collector attempted the same single allowlisted
`ERP_VERSION` operation. It again returned
`UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT`. No stdout/stderr,
endpoint, host, user, key, secret, Site identifier, version row, business value
or response shape was accepted or displayed. The private state file was not
created, no later operation ran and the failure category remains unknown by
design.

## Bench-root harness correction

Official Bench behavior and repository inspection show that `bench version`
reports apps for the current Bench directory, while the collector previously
ran every operation from the SSH login directory. The user confirmed the
default relative root `frappe-bench` and supplied the runtime Site privately;
the Site value is intentionally absent from Git and evidence.

The candidate binds all seven existing commands to the exact literal wrapper
`cd frappe-bench && exec <allowlisted-command>`. No dynamic root, arbitrary
shell token or new operation is accepted. It also accepts the official
four-token app/version/branch/parenthesized-commit row while rejecting malformed
or non-hex commit shapes. Product, contract, schema, ownership, frontend and
workflow behavior remain unchanged. Production retry is prohibited until this
candidate passes exact-SHA ordinary CI.

Harness-repair Level 1 passes in a clean linked worktree: collector-focused
`10/10`, collector/current/reconciliation `49/49`, complete repository Python
`2670/2670`, collector self-check, current-task verification, V1.2
reconciliation, Python compilation, complete repository verification and
`git diff --check`. The exact fourteen paths are accepted and an unauthorized
fifteenth is rejected. Static diff inspection confirms the private runtime Site
value is absent. No SSH or other production operation ran during validation.

An earlier local state-path preflight rejected a path outside the operating
system temporary root before SSH started. It is not a production operation.

## Accepted fixed-root discovery and next fail-closed boundary

At `2026-08-30T06:10:50Z` / `2026-08-30T13:10:50+07:00`, the accepted
fixed-root collector ran only `ERP_VERSION` followed by private-Site
`INSTALLED_APPS`. It accepted Frappe `15.79.0`, ERPNext `15.77.0`, twenty Bench
apps and a verified Site-app subset. Only anonymous custom-app labels, versions,
timestamps and two checksums were emitted. The Site value and custom app names
remain private temporary state.

Three `APP_HEAD` reads then completed. The first `APP_STATUS` failed locally
before SSH because its fixed `--untracked-files=no` token contains `=`, which
the closed remote-token grammar rejects. No status/path/file command followed
and no production state changed. The narrow repair substitutes Git's
equivalent fixed `-uno` token, adds an exact command assertion and requires a
new ordinary CI before any application metadata read resumes.

The fixed-token repair changes exactly fifteen allowed paths: the prior
fourteen governance/collector/test paths plus the reconciliation verifier whose
inventory assertions must now accept real versions and checksums while keeping
all missing facts held. In a clean linked worktree, collector/current tests pass
`17/17`, collector/current/reconciliation pass `49/49`, complete repository
Python passes `2670/2670`, and complete repository verification, collector
self-check, current-task verification, reconciliation, compilation and diff
hygiene all pass. The private Site value is absent, product/contracts/frontend/
workflow paths are unchanged, and no additional production operation ran.

At `2026-08-30T06:35:13Z` / `2026-08-30T13:35:13+07:00`, checksum-first
discovery matched the accepted Bench/Site inventories. `APP_HEAD` and
`APP_STATUS` then completed for all twenty apps. Frappe is clean; ERPNext has
one tracked drift; twelve of eighteen anonymous custom apps have tracked drift.
`CUSTOM_APP_01` has 16 tracked paths including hooks/modules/patches;
`CUSTOM_APP_02` has 42 including hooks/modules/patches, 11 DocTypes, fixtures
and overrides. The next `APP_TRACKED_PATHS` result stopped locally because its
line parser could not safely represent a legitimate path. The raw path was not
read, displayed or committed. No later path/file operation ran.

The exact-fourteen candidate changed only `APP_TRACKED_PATHS` to exact
`git ls-files -z` and a NUL-aware ordered, unique, UTF-8, printable,
non-traversing parser. NUL is accepted for no other operation; file reads keep
the stricter path gate. Production path/file operations remained prohibited
until its accepted exact-SHA ordinary CI `33297909199`.

Tracked-path repair Level 1 passes in a clean linked worktree: collector and
current-task focused tests `17/17`; collector/current/reconciliation `49/49`;
complete repository Python `2670/2670`; collector self-check; current-task and
V1.2 reconciliation verifiers; complete repository verification; Python
compilation; all shell syntax; JSON/YAML/CSV parsing; and diff/security hygiene.
The exact fourteen paths are accepted and an unauthorized fifteenth is
rejected. Product, contracts, frontend and workflow paths have zero diff; the
private Site value is absent; no SSH, ERP connector or production operation ran
during validation. Its later governed production evidence is recorded in the
Gate conclusion below.

## Compatibility result

The accepted discovery and later local stop prove no production
incompatibility. The current LaunchFlow
architecture, ownership, OpenAPI/event contracts and P8-01 through P8-09
implementation remain the default-correct baseline. All production-facing
blueprint rows are `UNVERIFIED` and use
`BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY` plus `NO_CHANGE` pending
evidence. No LaunchFlow or ERPNext adjustment task is authorized.

P8-08 remains inactive because the required production consumer/method and
mapping facts are unavailable. The accepted drift facts also prohibit using
dirty app HEAD source as production runtime truth. M9-04/M9-05 real pilots remain user-approved
post-V1.2 deferrals; AT-01/AT-02 controlled non-production UAT remains and is
not real-pilot or adoption evidence. Entra/Frappe/ERP permission ownership is
unchanged.

## Required deliverables

- `docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md` records all affected facts as
  still pending and retains exact provenance.
- `docs/ERPNEXT_PRODUCTION_FACT_INVENTORY.md` contains the sanitized operation
  ledger and complete unknown matrix.
- `docs/LAUNCHFLOW_ERPNEXT_INTEGRATION_BLUEPRINT.md` records the existing
  P8-01 through P8-09 compatibility baseline and minimal-adjustment rules.
- `docs/LAUNCHFLOW_ERPNEXT_COMPATIBILITY_GAP_DECISIONS.md` records the access/
  fact gaps, no-change decisions and escalation rule.

## Bounded-read checkpoint Level 1

The final exact sixteen documentation/governance/test paths pass in a clean
linked worktree: collector/current/reconciliation focused tests `49/49`, full
repository Python `2670/2670`, collector self-check, current-task verification,
V1.2 reconciliation, repository verification, prototype-approval and governed
visual-baseline checks, Python compilation, shell syntax, JSON/CSV parsing,
security scans and diff hygiene. The exact sixteen paths are accepted and an
unauthorized seventeenth is rejected. `apps/`, `contracts/`, `frontend/` and
`.github/` have zero diff. The working-tree M9 deferral and identity/permission
ownership documentation changes remain unstaged and are not part of this
checkpoint.

## Gate conclusion

P8-07F is not complete and no facts-task Level 3 is dispatched. Version/Site
discovery, complete anonymized HEAD/status facts and all twenty tracked-path
inventories are accepted. The NUL-framing repair passes at
`acbd6882869a4a8c27eb653019080354055f74a8` / ordinary `33297909199` with
repository `99220637261`, visual `99220637358`, frontend `99220637376` and
secret `99220637391` all passing.

The final bounded read window ran from `2026-08-30T07:07:57Z` through
`2026-08-30T07:14:52Z`. It summarized only six clean custom apps. ERPNext and
twelve custom apps have tracked drift; two relevant DocType candidates stopped
at sensitive-content preflight; runtime-only metadata remains unavailable
through the frozen source operations. No raw path, source, field, value,
private identity or Site was emitted, and private mode-0600 state was deleted.

No P8 target binding or incompatibility is proved. P8-07F is held on external
sanitized source/runtime evidence, P8-08 remains blocked, and neither a Level 3
nor an adjustment task is authorized. Recovery requires clean declared
worktrees or an owner-sanitized checksummed source/drift bundle, sanitized
evidence for the stopped candidates and a separately gated side-effect-free
runtime-metadata source.

## Authoritative final compatibility checkpoint

The preceding sections preserve the fail-closed collection history. This
section supersedes their former incomplete conclusion without deleting that
audit trail.

- The filterless Single DocType locale reader passed exact-SHA ordinary CI at
  `77b4258f3b086420e0ae7769bd95830bf9dabfaa` / `33312664804`: secret
  `99260395010`, visual `99260395168`, repository `99260395171` and frontend
  `99260395257` all passed.
- At `2026-08-30T13:07:50.798302Z`, the sole remaining `SYSTEM_LOCALE`
  operation accepted country `Thailand`, language `en-GB` and time zone
  `Asia/Chongqing`. The sanitized result checksum is
  `sha256:cc94b21fbc7a0556244ef71b117359ab7ee38022e8b32e5999d5b417fdcbe355`;
  the validated envelope checksum is
  `sha256:c554853696236992c4209f30796a39a41e434d4b066f92d52bc24d9532737945`.
- The operating-system temporary mode-0600 state was removed and verified
  absent. No SQL, console, arbitrary method, write, replay, reconciliation,
  Site mutation or repeated metadata-family collection occurred.
- Reused accepted evidence includes Frappe `15.79.0`, ERPNext `15.77.0`,
  twenty apps, accepted current tracked worktree source, 27 present of 28
  frozen relevant DocTypes, their DocFields, 120 DocPerm rows, fixed runtime
  metadata families, aggregate File URL shapes and Mold/Mold Repair/Mold Trial
  Report current-source structure. Exact checksums remain in the inventory.
- The accepted facts reconcile with the existing P8-01 through P8-09
  architecture, data ownership, OpenAPI/event contracts and code. No concrete
  architecture or ownership conflict exists; no product or ERP adjustment task
  is authorized. The detailed blueprint records `DIRECT_MATCH` or
  `CONFIG_OR_MAPPING_ONLY` outcomes and only conditional smallest fallbacks.
- Database topology, a named least-privilege service principal, owner-approved
  raw-code mappings, Sandbox/UAT, deployment/support evidence and any
  production enablement remain explicit holds. They do not block P8-08 design
  and implementation, but unresolved applicable facts block production-ready
  and final implementation closeout.
- M9-04 and M9-05 remain `USER_APPROVED_POST_V1_2_DEFERRED`; AT-01/AT-02 stay
  controlled non-production UAT and are not real-pilot or adoption evidence.

The P8-07F bounded fact/compatibility result is therefore
`PASS_BOUNDED_COMPATIBILITY_RECONCILIATION_LEVEL_3_PENDING`. This checkpoint
is product-zero and production-write-zero. Its sole remaining action is one
exact-SHA ordinary CI followed by one P8-07F Level 3. P8-08 becomes the next
authorized atomic task only if that Level 3 passes.

## Final checkpoint Level 1 and task review

- Collector/current/reconciliation focused checks pass `33/33`; collector
  self-check reports `remote_contact=false` and only the frozen operation and
  metadata-family sets.
- Current-task verification, reconciliation generation/verification, Python
  compilation, JSON/YAML/CSV parsing, 282-row unchanged requirement-status
  proof and `git diff --check` pass.
- `apps/`, `contracts/`, `frontend/` and `.github/` have zero tracked task
  diff. No production endpoint, Site value, identity, credential, raw source,
  Script text, URL or business record is committed.
- The cached task diff is exact 24 paths; the post-commit task union is 26
  paths, both fit the frozen 28-path manifest, and an unauthorized 25th cached
  path is rejected.
- The complete local 62-test collector/current/reconciliation run has 61
  passing checks and one known non-task working-tree assertion caused by the
  user's preserved uncommitted M9-04/M9-05 deferral entries. The task does not
  stage, rewrite or weaken that assertion; exact-SHA ordinary CI validates the
  committed tree independently.

## Final Level 3 failure and bounded diagnostic

Consolidated checkpoint `fa27a8bf9bc8b14a04c47e914494fa647d121385`
passes ordinary `33314378471` in all four lanes. Level 3 `33315047916` passes
repository `99266800693`, secret `99266800783`, frontend `99266800799`, visual
`99266800901` and preflight `99268509347`. Runtime `99268539395` passes pinned
Bench and disposable Site initialization, then fails in cumulative
verification; cleanup passes.

Fixed-label filtering returns exactly
`Local Frappe Item publish migrated-legacy runtime verification failed.` No
raw or child output, response content, business value, identity, message or
stack was read. Product, contract, schema, workflow and production-state diff
remain zero. Open one product-zero diagnostic at `0/1,0/1,0/1`, using only the
existing collection-fallback exact-39 code/type/trace mechanism. Exact-SHA
ordinary PASS must precede one Level 2 controlled run. P8-08 remains held.

## Migrated-legacy bounded diagnostic result

Product-zero checkpoint `68ae96ba7f688197f9d7254852605fc12c20b52b`
passes ordinary `33316649569`: visual `99271218200`, frontend `99271218361`,
secret `99271218387` and repository `99271218408` all pass. Its sole Level 2
controlled run `33317301069` passes preflight `99272978193` and cumulative
runtime `99273014159` in 8m57s. Exact-39 success emits zero safe tuples.

No raw or child output, response content, business value, identity, message or
stack was read. No production connection or product change occurred. The
diagnostic cycle is frozen at `1/1,0/1,0/1`; no product repair is evidenced.
All Item publish diagnostics are disabled. The only remaining action is one
new exact-SHA ordinary PASS followed by exactly one final Level 3. P8-08 stays
held until that Gate passes.

Diagnostics-off Level 1 passes 59 focused verifier/current/collector tests and
150 complete Item publish tests. Collector self-check confirms
`remote_contact=false`; current-task verification, V1.2 reconciliation,
Python compilation, shell syntax, JSON/YAML parsing and `git diff --check` all
pass. The task diff remains exact 10 governance/verifier paths, while product,
contract, schema, workflow and production-state diff remain zero. Existing
user working-tree changes remain unmodified and unstaged.

## Final diagnostics-off release Gate

Diagnostics-off exact checkpoint
`d8aba50580ffd7a0ca3fca0493cf49f84a6a1e8c` passes ordinary
`33317964484`: visual `99274761074`, secret `99274761113`, frontend
`99274761122` and repository `99274761227` all pass.

The sole final Level 3 `33318628754` passes secret `99276531908`, visual
`99276531987`, repository `99276532009`, frontend `99276532019`, controlled
preflight `99278115691` and cumulative runtime `99278148500`. The runtime
result record, artifact upload and cleanup all pass. No production connection,
restricted child output, business value, identity, message or stack was read.

P8-07F is therefore `PASS_LEVEL_3`. Its bounded compatibility result remains
product-zero and production-write-zero, and no evidence-backed LaunchFlow or
ERPNext adjustment task exists. P8-08 audit may start. Production activation,
Sandbox/UAT, unresolved business mappings and the final full release
compatibility reconciliation remain separate Gates.
