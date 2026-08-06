# Next Action

Status:
`BLOCKED_EXTERNAL — P5-04 REMAINING CREATE STAGE NON-UNIQUE`

Recovery time: `2026-08-06T04:35:01Z`

Required branch:
`codex/npi-v1.2-implementation`

Recovery checkpoint:
`40c89560aa8a3a8a36ff3b11149499dd72c6705c`

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
  unchanged controlled Gate is also consumed (`1/1`).
- Fixture repair checkpoint `158ef02` passed local `63/63` EBOM and
  `959/959` complete Python, then complete exact-SHA ordinary CI
  `31070341154` passed repository, E2E, both secret lanes and fixed-Linux
  visual; the controlled job remained correctly skipped.
- Final unchanged controlled workflow `31070732986` retained exact SHA
  `158ef02` with diagnostic activation closed. It passed the predecessor
  runtime, policy publication and repaired domain precondition, then emitted
  only `P504_RUNTIME_CREATE / HttpStatusError /
  trace-462662eec74c5c4f9e3e5a07258f1a7b`.
- Its repository job `92517955490` and visual job `92517955368` both passed;
  the workflow failure is confined to the controlled create-stage runtime.
- The former `P504_CREATE_DOMAIN_BUILD / RequestValidationFailed` did not
  recur, so the fixture repair advanced the Gate. The new aggregate tuple is
  non-unique across the remaining create transaction/response stages; the
  authorized diagnostic Site, fixture repair and final Gate are exhausted.
- Recovery checkpoint `40c8956` passed exact-SHA ordinary CI `31071143272`:
  repository job `92519171196`, complete E2E/history secret scan and visual
  job `92519171311` passed; controlled job `92519171741` was correctly skipped.

## First unfinished action

Explicitly authorize one new bounded remaining-create-stage recovery:
reactivate only the already closed response-neutral diagnostic header, run
affected/full ordinary CI, use at most one diagnostic controlled Site, repair
only the uniquely proven remaining verifier/fixture or product root, rerun
affected/full ordinary CI and reserve one final unchanged controlled Gate.
No Requirement, API, permission, Schema, ownership, transaction order,
idempotency, audit or PASS criterion may change.

P5-04 is `BLOCKED_EXTERNAL`. P5-05 and Phase 6 remain inactive.

## Frozen non-scope

- P5-01 through P5-03 remain sealed `PASS`.
- NPI One owns only EBOM working revisions; ERPNext retains formal Item, MBOM,
  routing, stock UOM and execution ownership.
- No production ERPNext access, cross-database write, raw Desk product path,
  core patch, production policy default, TODO/stub or fake success is allowed.
- Existing unrelated workspace changes remain user-owned and must not be
  staged with the checkpoint.
