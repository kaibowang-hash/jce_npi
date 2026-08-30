# P8-07F Production Fact Reconciliation Validation

Date: `2026-08-30`

Status: **BLOCKED — PRODUCTION FACTS UNVERIFIED AFTER FAIL-CLOSED READ**

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

## Compatibility result

The failed read proves no production incompatibility. The current LaunchFlow
architecture, ownership, OpenAPI/event contracts and P8-01 through P8-09
implementation remain the default-correct baseline. All production-facing
blueprint rows are `UNVERIFIED` and use
`BUSINESS_DECISION_REQUIRED — FACT/ACCESS ONLY` plus `NO_CHANGE` pending
evidence. No LaunchFlow or ERPNext adjustment task is authorized.

P8-08 remains inactive because the required production consumer/method and
mapping facts are unavailable. M9-04/M9-05 real pilots remain user-approved
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

## Gate conclusion

P8-07F is not complete and no facts-task Level 3 is dispatched. A technical CI
PASS could not substitute for the missing accepted production evidence. The
task is held at the external read boundary, P8-08 remains blocked, and the
standing read-only authorization remains available for a future narrowly
scoped retry only after the external access condition is corrected without
allowlist drift. Any later successful fact collection and final reconciliation
must pass their own exact-SHA ordinary and applicable Gate.
