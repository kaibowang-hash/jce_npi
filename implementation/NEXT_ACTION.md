# Next Action

Status:
`IN_PROGRESS — P5-04 REMAINING CREATE STAGE DIAGNOSTIC`

Recovery time: `2026-08-06T04:48:37Z`

Required branch:
`codex/npi-v1.2-implementation`

Recovery checkpoint:
`c7edac8411614efab1a56348964f7c274cb6f18b`

## Authority

The user explicitly authorized one new bounded P5-04 remaining-create-stage
recovery on `c7edac8`: reactivate only the existing response-neutral
diagnostic, require affected/full ordinary CI, use at most one diagnostic
Site, repair only the uniquely proved root, rerun affected/full ordinary CI
and reserve one final unchanged Gate before Autopilot continues.

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
- The historical create-stage diagnostic dispatch and final Gate are consumed
  (`1/1` each) and remain immutable history. The newly authorized
  remaining-create-stage sequence has separate counters: diagnostic `0/1`,
  uniquely proved repair `0/1`, final unchanged Gate `0/1` reserved.
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

Run the affected create diagnostic/verifier tests and the complete ordinary
local CI from the exact `c7edac8` recovery base with only the first create
request diagnostic active. Commit and push that checkpoint, require exact-SHA
ordinary CI PASS, then execute at most one diagnostic controlled Site.
No repair is permitted before its closed tuple uniquely proves and direct
contract/DocType/permission/transaction cross-validation confirms one root.

P5-04 is `IN_PROGRESS_DIAGNOSTIC`. P5-05 and Phase 6 remain inactive.

## Frozen non-scope

- P5-01 through P5-03 remain sealed `PASS`.
- NPI One owns only EBOM working revisions; ERPNext retains formal Item, MBOM,
  routing, stock UOM and execution ownership.
- No production ERPNext access, cross-database write, raw Desk product path,
  core patch, production policy default, TODO/stub or fake success is allowed.
- Existing unrelated workspace changes remain user-owned and must not be
  staged with the checkpoint.
