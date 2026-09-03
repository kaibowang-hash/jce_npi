# P9-07 — Go-live and Recovery Rehearsal Validation

Recorded: `2026-09-03`

Status: `PASS_LEVEL_3`

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

## Final exact-SHA evidence

- Implementation SHA: `d911c2bcecb228cee0f4830c868e0d0fdf35d3e2`
- Ordinary CI: `33730217862` — PASS
- Ordinary jobs: secret `100568187027`; visual `100568187187`; E2E shard 1
  `100568187192`; repository `100568187234`; frontend verify `100568187279`;
  E2E shard 2 `100568187376`; frontend aggregate `100569594776`.
- Diagnostics-off Level 3: `33730710124` — PASS
- Level 3 jobs: frontend verify `100569742499`; secret `100569742677`; E2E
  shard 2 `100569742708`; repository `100569742720`; visual `100569742798`;
  E2E shard 1 `100569742893`; frontend aggregate `100571202183`; controlled
  preflight `100571230546`; controlled runtime `100571300835`.
- Controlled runtime: PASS in `9m51s`; backup `3s`, restore `5s`, forward-fix
  `9s`; restore and forward-fix verified; cleanup PASS;
  `productionContact=false`.
- Artifact: `9884231883`, name `p8-integration-runtime-33730710124`, GitHub
  digest
  `sha256:2d4fdb0d1f5293a20d0c4feecf663011712da857f168088a15abe731a25c1ef2`.
- Bounded `result.txt` checksum:
  `sha256:9c6b501e20ceeec9abd728f8165b02b05682ebb34e86e4dda010245515bffb93`.
- Result evidence checksum:
  `sha256:54483fd8a5c75d23e3f6307ddfa9b6d800364495f76a291d5d8a3ea799701541`.
- Release-gate review: `PASS`.

All temporary diagnostic switches are off. P9-07 is complete and P9-08 may
activate automatically.

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

## Diagnostic result and canonical manifest repair

Diagnostic checkpoint `7578272417cbaecfacfbefb6a2d7d1c3bf6731dc`
passes exact-SHA ordinary CI `33728309450`. Its sole diagnostic-only workflow
`33728821857` passes repository job `100563932258`, secret job `100563932281`
and controlled preflight `100564251382`. Controlled runtime `100564321162`
crosses the historical P8-03 boundary with success-zero classifier output and
then fails only at the P9-07 post-restore release-identity comparison.

Static inspection proves one deterministic local verifier defect without
reading configuration values: `release_manifest()` constructed `appNames` as
a Python tuple; JSON persistence necessarily loads it as a list; the
post-restore exact dictionary comparison therefore failed even when all three
application names were identical. The minimal repair emits and validates only
the canonical JSON array/list form, adds an exact round-trip regression, and
turns the temporary P8-03 classifier off. It changes no backup, restore,
migration, product, schema, configuration, production or external behavior.

The repair's affected suite passes `83/83`; complete repository Level 2 passes
`2983/2983`; current-task, V1.2 reconciliation, Python compilation, shell
syntax and diff hygiene checks pass. The host exposes only `python3`, so the
repository script was run with a private temporary `python` shim pointing to
that same interpreter; the shim was removed immediately after the check.

The repair checkpoint requires its own exact-SHA ordinary CI PASS and one final
diagnostics-off Level 3 before P9-07 can pass or P9-08 can activate.

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
