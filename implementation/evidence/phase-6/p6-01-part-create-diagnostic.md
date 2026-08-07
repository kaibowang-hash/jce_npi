# P6-01 Part-create Diagnostic Checkpoint

Updated: `2026-08-07T15:23:00Z`

Status: `REPAIR EFFECTIVE — GATE ADVANCED`; this is not a P6-01 Task Gate PASS.

## Trigger evidence

Exact runtime-verifier checkpoint `42e2435` passed complete ordinary CI
`31186227371`: repository `92891339039`, fixed-Linux visual `92891338846` at
`73/73`, and controlled runtime `92891340007` correctly skipped. Controlled
workflow `31186957232` retained the exact SHA. Repository `92893817844`, visual
`92893817888`, pinned Bench, disposable Site, migrations and all cumulative P5
runtime checks passed. Controlled job `92893817778` failed only when the first
P6-01 `part.create` returned non-201. The closed verifier did not expose a
unique implementation or fixture root.

## Bounded diagnostic

The diagnostic is header-gated to the first synthetic Part-create request and
is response-neutral. It can record only one allowlisted substage code, a
validated exception type and the exact trace ID. It cannot record request
payloads, business values, messages, stack traces, credentials or response
changes. Diagnostic recording is secondary and cannot change the original
exception, transaction, rollback or safe public problem response.

Before dispatch, counters were diagnostic `0/1`, uniquely proved repair `0/1`,
final unchanged Gate `0/1`. Affected and complete ordinary CI were required
before that diagnostic Site. Only its uniquely proved root may be repaired;
diagnostic activation must then close before the final ordinary CI and
unchanged controlled Gate.

No Requirement, public API, permission, Schema intent, ownership, transaction,
idempotency, audit, baseline, threshold or PASS criterion changes. Production
lifecycle, numbering, Tooling Revision/Set/Trial, mapping, adapter, ERPNext
endpoint, credential and production default remain absent.

## Diagnostic result and unique root

Diagnostic checkpoint `7bd0819` passed complete ordinary CI `31188466252`:
repository `92898914533`, visual `92898914186` at `73/73`, and controlled
runtime `92898915318` correctly skipped. The sole diagnostic Site
`31189263393`, controlled job `92901612106`, returned only:

`P601_PART_CREATE_RECEIPT_INSERT / ValidationError /
trace-fdeec6ebee38563791fb6f338ef1aa0e`

All prior create substages and every predecessor passed. Pinned Frappe
`Document.insert()` calls `_set_defaults()` and the framework's Select fallback
uses the first listed option when a new value is empty. The optional
`target_object_type` listed `part` first. Therefore the new unsealed receipt was
silently defaulted to an already-bound target and its own invariant correctly
raised `ValidationError`.

The unique repair prepends the empty Select option and sets verifier diagnostic
activation to false. The allowed sealed target values remain exactly `part`,
`part_revision`, `tooling_requirement`, `tooling_master` and
`tooling_applicability`. At that point counters were diagnostic `1/1`, repair
`0/1` in progress, final unchanged Gate `0/1`.

## Repair result

Repair checkpoint `84ac63b` passed complete ordinary CI `31190599179`:
repository `92906131044`, visual `92906130984` at `73/73`, and controlled
runtime skipped. Final unchanged workflow `31191425881` retained the same SHA.
Repository `92908918643` and visual `92908918453` passed. Controlled job
`92908918591` passed the pinned environment, Site, migrations, retained P5
runtime and the earlier P6-01 commands, then the first Applicability create did
not return HTTP 201. The receipt insert root did not recur; counters for this
cycle are diagnostic `1/1`, repair `1/1`, final Gate `1/1` and the repair is
effective. The new downstream opaque stage is governed separately.
