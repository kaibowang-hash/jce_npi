# Next Action

Status:
`IN_PROGRESS_REPAIR_VALIDATION — P5-04 SYNTHETIC FIXTURE NAMESPACE`

Recovery time: `2026-08-06T04:02:59Z`

Required branch:
`codex/npi-v1.2-implementation`

Recovery checkpoint:
`008e6ed2c55d08dd53639942fb2392649d3af6c9`

## Authority

The user authorized the previously requested bounded P5-04 create-stage
diagnostic/repair sequence by asking to repair and continue the existing
Goal/Autopilot.

The sequence permits:

1. one closed response-neutral create diagnostic checkpoint;
2. affected tests and complete exact-SHA ordinary CI;
3. at most one diagnostic controlled Site;
4. one repair only when an in-scope verifier/fixture or product root is
   uniquely proven;
5. affected tests, complete ordinary CI and one final unchanged controlled
   Gate; and
6. automatic continuation only after P5-04 Level 2 passes.

It may not change Requirements, public API, permissions, Schema, ownership,
transaction order, idempotency, audit or PASS criteria.

## Current evidence

- Diagnostic checkpoint `008e6ed` passed complete exact-SHA ordinary CI
  `31069567886`: repository, complete E2E, both secret lanes and fixed-Linux
  visual passed; the controlled job remained correctly skipped.
- The sole diagnostic workflow `31069924517` retained exact SHA `008e6ed`.
  The controlled job passed pinned Bench, disposable Site, migrations,
  unchanged P5-01/02/03 runtime, policy publication, authorization probes and
  cleanup, then emitted only `P504_CREATE_DOMAIN_BUILD /
  RequestValidationFailed / trace-79bcd3a2408c5f71bb8c0cad8bd9db21`.
- Domain, policy fixture and create-payload cross-validation uniquely proves
  one synthetic fixture precondition defect: the fixture policy used
  `synthetic_runtime`, its EBOM key used the unrelated `synthetic_ebom_`
  prefix, while the frozen domain requires `syntheticNamespace + "-"` and
  the accepted P5-04 policy namespace is `synthetic_ebom`.
- The bounded repair defines that namespace once, uses it in the policy and
  key, preserves the domain rule and closes diagnostic activation before the
  reserved final Gate. Focused and complete EBOM tests pass `43/43` and
  `63/63` respectively.
- Complete tracked Python passes `959/959`; compilation, V1.2 reconciliation,
  trace uniqueness, YAML parse, prohibited-pattern and `git diff --check`
  pass.
- The diagnostic dispatch allowance is consumed (`1/1`); the reserved final
  unchanged controlled Gate remains unused.

## First unfinished action

Commit and push only the two-file synthetic fixture repair plus synchronized
controller/evidence files. Require complete ordinary CI on that exact SHA;
only after it passes, execute the single reserved final unchanged controlled
Gate with diagnostic activation closed.

P5-04 remains `IN_PROGRESS_REPAIR_VALIDATION`. P5-05 and Phase 6 remain
inactive until the final Gate and Level 2 evidence pass.

## Frozen non-scope

- P5-01 through P5-03 remain sealed `PASS`.
- NPI One owns only EBOM working revisions; ERPNext retains formal Item, MBOM,
  routing, stock UOM and execution ownership.
- No production ERPNext access, cross-database write, raw Desk product path,
  core patch, production policy default, TODO/stub or fake success is allowed.
- Existing unrelated workspace changes remain user-owned and must not be
  staged with the checkpoint.
