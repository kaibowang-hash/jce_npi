# Next Action

Status:
`BLOCKED_EXTERNAL — P5-04 POST-LIFECYCLE CREATE STAGE OPAQUE`

Recovery time: `2026-08-06T07:53:33Z`

Required branch:
`codex/npi-v1.2-implementation`

Recovery checkpoint:
`6a4ba7c43e778f22a8de45ce9be8bf5c07a63aac`

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

After the preceding sequence was exhausted, the user requested that the
problem be fixed. This resumes the same Goal with a new independent bounded
post-revision-create sequence on `16ed463`: existing first-create diagnostic
`0/1`, uniquely proved repair `0/1`, and reserved final Gate `0/1`. All prior
runs and counters remain immutable history.

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
- New diagnostic checkpoint `40d2d47` passed complete exact-SHA ordinary CI
  `31073500593`; repository `92526237591` and visual `92526237583` passed and
  controlled job `92526238095` correctly remained skipped.
- The sole diagnostic workflow `31073915463` retained that exact SHA and
  emitted only `P504_CREATE_REVISION_INSERT / ValidationError /
  trace-9b23575185625a1998ac184bfefaa272`. Its repository and visual companions
  passed and disposable cleanup completed.
- Cross-validation uniquely proves the product root: exact policy identity
  fields used only as query filters were absent from the selected row passed
  into domain hydration. The repair selects existing `policy_global_id` and
  `policy_version` fields only and has closed diagnostic activation.
- Repair checkpoint `f4aba87` passed local controller/runtime `25/25`, EBOM
  `64/64`, related Document `70/70`, complete Python `960/960` and complete
  exact-SHA ordinary CI `31075372272`. Repository `92532129789` and visual
  `92532130528` passed; controlled job `92532130580` correctly skipped.
- The sole final unchanged workflow `31075730002` retained exact SHA
  `f4aba87`. Repository `92533233067`, visual `92533232990`, predecessor
  runtime, migrations and cleanup passed; controlled job `92533233034`
  returned only `P504_RUNTIME_CREATE / HttpStatusError /
  trace-6fa26f47b241558db7fdafa0b9c1a46e`.
- With diagnostic activation closed, no `P504_CREATE_*` substage exists for
  that trace. The result cannot uniquely prove recurrence of the revision
  insert or a later create failure. Diagnostic, repair and final Gate are all
  consumed `1/1`.
- Controller checkpoint `16ed463` passed complete ordinary CI `31076595986`;
  repository and visual passed, while controlled runtime correctly skipped.
  The new recovery reactivated only the existing response-neutral diagnostic
  on the first create request.
- Diagnostic checkpoint `1400a8b` passed complete ordinary CI `31079745399`.
  Its sole diagnostic Site `31080379082` passed repository job `92547610775`
  and visual job `92547610707`; controlled job `92547611196` uniquely emitted
  `P504_CREATE_LIFECYCLE_INSERT / ValidationError /
  trace-16676d79fc405e76805261a931550f32`.
- The preceding line insert already validates the same exact revision parent,
  tenant, Project and snapshot hash. The lifecycle controller then hands its
  canonical string ID directly to a domain type whose `_uuid` boundary accepts
  only `UUID`. That exact failure is translated to the observed
  `ValidationError`, uniquely selecting one type-boundary repair. Diagnostic
  activation is now closed.
- Repair checkpoint `6a4ba7c` passed affected validation and complete exact-SHA
  ordinary CI `31081784934`; repository `92552039959` and visual
  `92552040040` passed, and controlled runtime correctly skipped.
- The sole final unchanged workflow `31082337133` retained SHA `6a4ba7c` with
  diagnostics closed. Repository `92553782998` and visual `92553782973`
  passed. Controlled job `92553782979` passed setup, migrations, predecessor
  runtime and cleanup, then returned only `P504_RUNTIME_CREATE / HttpStatusError /
  trace-ef925ea360245bd6b58daf326b910afe`.
- The final aggregate tuple is non-unique across recurrence of lifecycle insert
  and later projection/audit/response/receipt stages. Diagnostic, repair and
  final Gate are consumed `1/1`; no further edit or dispatch is authorized.

## First unfinished action

Obtain explicit authority for one new bounded post-lifecycle create-stage
diagnostic/repair sequence. It must use only the existing response-neutral
first-create diagnostic, affected/full ordinary CI, at most one diagnostic
Site, one repair only for a uniquely proved root, diagnostics closed before
ordinary CI and one final unchanged Gate. Do not infer a product edit from the
current aggregate tuple.

P5-04 is `BLOCKED_EXTERNAL`. P5-05 and Phase 6 remain inactive.

## Frozen non-scope

- P5-01 through P5-03 remain sealed `PASS`.
- NPI One owns only EBOM working revisions; ERPNext retains formal Item, MBOM,
  routing, stock UOM and execution ownership.
- No production ERPNext access, cross-database write, raw Desk product path,
  core patch, production policy default, TODO/stub or fake success is allowed.
- Existing unrelated workspace changes remain user-owned and must not be
  staged with the checkpoint.
