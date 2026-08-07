# P6-01 Applicability-create Diagnostic Checkpoint

Updated: `2026-08-07T15:23:00Z`

Status: `IN_PROGRESS_DIAGNOSTIC`; this is not a P6-01 Task Gate PASS.

## Trigger evidence

Receipt repair checkpoint `84ac63b` passed complete ordinary CI `31190599179`.
Final unchanged workflow `31191425881` retained that exact SHA. Repository
`92908918643`, visual `92908918453`, pinned Bench, disposable Site, migrations,
retained P5 runtime and all preceding P6-01 commands passed. Controlled job
`92908918591` then reported only that the first synthetic Applicability command
did not return HTTP 201. No unique implementation root is yet proven.

## Bounded diagnostic

Only the first synthetic Applicability-create request sends
`X-NPI-Diagnostic-Scope: p601-applicability-create-v1`. Server instrumentation
is additionally route-gated and can record at most one allowlisted substage,
validated exception type and exact trace ID. It records no payload, business
value, message, stack, credential or response body. Diagnostic recording is
secondary and cannot change the response, transaction, rollback or safe public
problem response.

Counters are diagnostic `0/1`, uniquely proved repair `0/1`, final unchanged
Gate `0/1`. Affected and complete ordinary CI must pass before the sole
diagnostic Site. Only its uniquely proved root may be repaired; activation must
then close before final ordinary CI and one unchanged controlled Gate.

No Requirement, public API, permission, Schema intent, ownership, transaction,
idempotency, audit, baseline, threshold or PASS criterion changes. Production
lifecycle, numbering, Tooling Revision/Set/Trial, mapping, adapter, ERPNext
endpoint, credential and production default remain absent.

## Local validation before checkpoint

Changed-files to affected-tests mapping:

- diagnostic context, API route gate and repository substages ->
  `tests.test_phase6_tooling_api`, `tests.test_phase6_tooling_repository`;
- one-request verifier activation and sanitized parser ->
  `tests.test_phase6_tooling_runtime_verifier`;
- control/evidence changes -> YAML parse, reconciliation and diff checks.

Results: affected `23/23` PASS; complete tracked Python `1,130/1,130` PASS;
Python compilation, workflow/status YAML parse, prototype approval, P0 visual
governance, V1.2 reconciliation and `git diff --check` PASS; prohibited pattern
scan returned no matches. Complete exact-SHA ordinary CI remains mandatory
before the sole diagnostic Site.
