# P9-07 — Go-live and Recovery Rehearsal Validation

Recorded: `2026-09-03`

Status: `IMPLEMENTATION CANDIDATE — EXACT-SHA ORDINARY AND LEVEL 3 PENDING`

Requirements: `NFR-BCP-001`, `NFR-MNT-001`

## Authorization chain

- Accepted predecessor: P9-06 exact SHA
  `8f5c2292dab6aa48f82c8aade37f3938b023699d`, ordinary CI
  `33719574371`, diagnostics-off Level 3 `33719982252`.
- P9-07 governance: exact SHA
  `6c3c30a25138dfdc4e26b0ea20056314b670882a`, ordinary CI
  `33721621988` PASS in both E2E shards, secret, visual, repository, frontend
  verification and aggregate jobs.
- The governance Gate authorized only the fixed non-production rehearsal and
  runbook described by `implementation/evidence/phase-9/p9-07-plan.md`.

## Candidate implementation

The candidate adds one no-argument recovery runner and one fixed verifier to
the existing cumulative disposable-Site Level 3. It accepts only the physical
repository Bench, `npi.localhost`, `npi_one_runtime`, the existing disposable
marker and the current runtime namespace. It records no configuration values.

The runtime sequence creates synthetic database, public-file and private-file
canaries; records a value-free release manifest; performs Frappe's real full
database/files/config backup in private temporary storage; binds exact member
hashes; creates distinct later canaries; restores the backup into the same
disposable Site; proves pre-backup truth returned and later truth disappeared;
replays the exact file tree; runs migration twice; revalidates release, app,
schema and config-key identity; emits only bounded timing/hash facts; then
removes canaries and backup bytes. Any mismatch or cleanup failure fails closed.

No Frappe/ERPNext core, API contract, domain ownership, UI, CI workflow,
production Site, ERPNext adapter/profile or external target is changed.

## Local verification

| Check | Result |
| --- | --- |
| Python compilation for verifier and tests | PASS |
| Shell syntax for runtime Gate and recovery runner | PASS |
| Focused P9-07 verifier/runtime contract tests | `11/11` PASS |
| Current-task and V1.2 reconciliation checks | PASS |
| Repository Level 2 | `2981/2981` PASS |
| Diff hygiene | PASS before candidate commit |

Frontend product files are unchanged. The local machine does not have the
repository's exact Node `24.18.0`, so the frontend task was not rerun under a
different runtime. Governance ordinary CI already passes its exact frontend
lane; the final candidate ordinary CI must pass that lane again at the exact
implementation SHA.

## Final exact-SHA evidence slots

- Implementation SHA: `PENDING`
- Ordinary CI: `PENDING`
- Diagnostics-off Level 3: `PENDING`
- Controlled runtime job/artifact/checksum: `PENDING`
- Release-gate review: `PENDING`

P9-07 and P9-08 activation remain blocked until these exact-SHA slots pass.

## Level 3 runtime stops and bounded cumulative diagnostic

Implementation SHA `0d3891afdc88082845b43f20ac0d2d6d77f55e26`
passes ordinary CI `33723202891`. Its first Level 3 `33723648823` passes all
static/frontend/preflight lanes and exposes only that the new P9-07 Python
helper inherited a repository working directory incompatible with Frappe's
relative log path. Fix SHA `3bc42d9f6cb5bdf684507d366970b8b6b0e0bcdd`
anchors every helper to the fixed Bench `sites` directory; focused tests pass
`12/12` and ordinary CI `33724852712` passes every lane.

Replacement Level 3 `33725286182` and its same-SHA rerun `33726821321` both
pass repository, secret, frontend verification, both E2E shards, aggregate,
visual and controlled preflight. Their fresh disposable-Site runtime then
stops at the same historical P8-03 migrated-legacy 409 problem-code assertion
after both migrations and before the P9-07 rehearsal is reached. Cleanup
passes. The response body, business values and child log output remain
withheld; no P9-07 or product incompatibility is inferred.

Activate only the existing P8-03 post-P8-09 value-free classifier. It can emit
one allowlisted problem branch, `RuntimeError` and an exact deterministic trace,
never the actual response, message, identity or business value. Require one
exact-SHA ordinary PASS and one diagnostic-only controlled Site. A unique tuple
permits one batched fixture-only repair; a successful nonreproduction permits
only classifier closure and no product change. P9-08 and production contact
remain closed.

## Honest holds

This evidence proves only deterministic engineering recovery on a fresh local
disposable environment. It does not prove a production backup schedule,
off-site storage, retention, encryption-key custody, representative production
volume, RPO, RTO, SLA, approval or production execution. Suggested targets of
`RPO <= 24h` and `RTO <= 8h` remain IT/business decisions. The run made no
production ERPNext, `jce.1`, production LaunchFlow, remote storage or other
external contact; `productionContact=false` remains mandatory.

The final full production ERPNext–LaunchFlow read-only compatibility
reconciliation remains a separate mandatory Release Gate. Real pilots M9-04
and M9-05 remain `USER_APPROVED_POST_V1_2_DEFERRED`; controlled non-production
UAT must not be reported as a real pilot or 80-percent real-user adoption.
