# P6-01 Applicability-create Diagnostic Checkpoint

Updated: `2026-08-07T15:43:06Z`

Status: `ROOT PROVEN — REPAIR IN PROGRESS`; this is not a P6-01 Task Gate PASS.

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

## Diagnostic result and unique root

Checkpoint `f82906f` passed complete ordinary CI `31192675103`: repository
`92913143816`, visual `92913143717` at `73/73`, and controlled runtime
`92913144500` correctly skipped. The sole diagnostic workflow `31193365348`
then passed repository `92915506746`, visual `92915506767`, pinned Bench, Site,
migrations and all earlier runtime stages. Controlled job `92915506979`
returned only:

`P601_APPLICABILITY_CREATE_RELATIONSHIP_INSERT / ValidationError /
trace-59e45d5266c05965a8e353f52abe26c5`

Pinned Frappe `Document.insert()` applies `_set_defaults()`, whose Select
fallback uses the first listed option. The request intentionally omits optional
Product and Model references, but both source-system Selects listed `NPI_ONE`
first. Frappe therefore supplied source systems while the paired object IDs
remained empty, and the immutable `ToolingApplicability` paired-reference
invariant correctly raised `ValidationError` during relationship insert.

The unique repair prepends the empty Select option to both optional source
systems and sets verifier diagnostic activation to false. Supported non-empty
values remain exactly `NPI_ONE` and `ERPNEXT`; no relationship, ownership,
transaction, idempotency, audit or public response rule changes. Counters are
diagnostic `1/1`, repair `0/1` in progress, final unchanged Gate `0/1`.

Repair changed-files to affected-tests mapping:

- two optional Select metadata fields -> Phase 6 Tooling metadata and complete
  metadata/i18n source validation;
- diagnostic closure -> Tooling runtime-verifier header/activation tests;
- cumulative safety -> Tooling API/repository diagnostics and retained P5/P6
  Python suites.

Affected Tooling `31/31` and complete tracked Python `1,130/1,130` pass after
the repair. Compilation, YAML parse, prototype/P0 governance, reconciliation,
prohibited-pattern and diff checks pass. Complete exact-SHA ordinary CI and one
final unchanged controlled Gate remain mandatory.
