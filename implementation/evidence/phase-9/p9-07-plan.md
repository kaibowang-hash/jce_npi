# P9-07 — Go-live and Recovery Rehearsal Plan

Recorded: `2026-09-03`

Status: `AUDIT AND PLAN — PRODUCT HELD UNTIL TRANSITION ORDINARY PASS`

Requirements: `NFR-BCP-001`, `NFR-MNT-001`

## Accepted predecessor

P9-06 is complete at exact SHA
`8f5c2292dab6aa48f82c8aade37f3938b023699d`. Ordinary CI `33719574371`
and diagnostics-off Level 3 `33719982252` pass every lane. Fresh cumulative
runtime job `100538152787` completes the P9-06 verifier and cleanup with
`productionContact=false`; artifact `9880193608` retains the accepted digest
and result checksum.

## Audit result

The repository already provides the right reusable base: independent Frappe
apps, pinned Frappe source, exact-SHA CI, automated repository/frontend gates,
one fixed `npi.localhost` disposable Site, strict local database/Site guards,
repeatable migrations, cumulative synthetic runtime and cleanup. Frappe v15's
public Site commands provide full database plus public/private file backup and
restore. No current evidence proves one complete backup-to-restore rehearsal,
an exact release manifest, post-restore forward-fix verification, or measured
non-production recovery duration.

This is a local evidence gap, not an architecture redesign and not permission
to operate production. No new ERPNext fact is required. The transition and
rehearsal must not contact production ERPNext, `jce.1`, production LaunchFlow,
object storage, a remote backup destination or any external service.

## Frozen minimal product slice

Add one fixed non-production rehearsal to the existing Level 3 disposable
runtime. It is not a generic deployment or restore tool and accepts no caller-
selected Site, database, Bench, path, command, app, DocType or external target.
It must:

1. fail closed unless the repository Bench, fixed `npi.localhost` Site, fixed
   `npi_one_runtime` database and exact disposable marker all pass the existing
   guards;
2. record a value-free release manifest containing exact Git and pinned Frappe
   SHAs, installed LaunchFlow app names, app/schema/config-key fingerprints and
   the fixed rehearsal schema version;
3. create only synthetic database and public/private file canaries, take a
   full database/files backup into a mode-`0700` temporary directory, and bind
   file sizes plus SHA-256 checksums without retaining or uploading backup
   bytes;
4. run the existing cumulative verifier and migrations, then add distinct
   post-backup canaries to prove the restore is meaningful;
5. restore the database and both file sets into that same disposable Site,
   require the pre-backup canaries, require the post-backup canaries to be
   absent, and verify the release/schema/config-key fingerprints again;
6. run migration and the cumulative runtime a second time as the forward-fix
   path, proving idempotency and current-code compatibility after restore;
7. emit only bounded timings, versions, hashes, counts, PASS/FAIL and
   `productionContact=false`, then always remove canaries and temporary backup
   material through the controlled cleanup path.

The first implementation may reuse Bench's public `backup --with-files
--compress` and same-version `restore` commands. It must never use downgrade,
arbitrary `--force` input, production backup data or a destructive production
rollback. Secrets remain process inputs and are never logged, persisted in the
release manifest or committed.

## Truth and safety boundaries

- The rehearsal proves engineering recoverability on a fresh disposable
  environment. It does not prove the production daily schedule, off-site copy,
  retention, encryption custody, production data volume, RPO, RTO, SLA or
  operational approval.
- Suggested `RPO <= 24h` and `RTO <= 8h` remain business/IT acceptance targets,
  not inferred PASS claims. Measured local durations are evidence only.
- Exact backup bytes, database names beyond the fixed synthetic identity,
  config values, passwords, encryption keys, file contents, users and business
  records never enter Git artifacts or logs.
- No Frappe/ERPNext core change, production connection, production mutation,
  cross-database write, generic executor, CI workflow change, schema downgrade
  or automatic release/rollback is authorized.
- A failed backup, checksum, restore, canary, migration, cumulative verifier or
  cleanup is an honest Gate failure. HTTP success and Mock output cannot stand
  in for the real disposable-Site operation.

## Changed-files to affected-tests map

| Change | Required evidence |
| --- | --- |
| Rehearsal verifier | manifest canonicalization, allowed facts, redaction, canary lifecycle, fail-closed modes and result-schema tests |
| Runtime shell | syntax, fixed target/path/command assertions, trap cleanup, real backup/files/restore/migrate/forward-fix on the disposable Site |
| Recovery runbook | repository test for commands, responsibilities, monitoring, rollback/forward-fix and explicit production holds |
| Governance/trace | current-task verifier, reconciliation verifier, repository Gate and diff hygiene |

## Acceptance matrix

Unit and contract tests cover valid manifest/result, dirty or wrong SHA,
incorrect Site/marker/database, missing/mutated backup member, public/private
file checksum mismatch, restore failure, missing pre-backup canary, retained
post-backup canary, migration failure, forward-fix failure, cleanup failure,
secret/path/value leakage and production-like target rejection. The controlled
runtime proves normal backup, database and both file restores, exact replay,
post-backup rollback semantics, two migrations, cumulative application checks,
bounded timings/checksums and cleanup.

Level 2 must pass before one exact-SHA ordinary CI and one diagnostics-off
Level 3 at the same final SHA. A same-root failure batch is repaired and
retested together; the task does not fragment into per-check micro-commits.

## Rollout, recovery and ownership

Deploy current independent apps and migrations with the exact release manifest
recorded, keep routes under their existing default-disabled/approved switches,
take and verify a real environment-specific backup under the operator's
approved procedure, perform smoke checks, then activate only approved routes.
Rollback stops activation and restores the reviewed environment backup;
forward-fix deploys a successor exact SHA and reruns migrations and smoke
checks. Immutable audit, Inbox/Outbox, export, archive and execution history is
never deleted to make a rollback look successful.

Repository engineering owns this deterministic rehearsal and runbook. IT/
operations still owns the real environment, backup schedule, storage,
encryption/key custody, monitoring, access, restore window and production
execution. Business and IT must accept final RPO/RTO before production-ready
can be claimed. P9-07 completion therefore means the technical non-production
rehearsal is proven and the production facts/decisions remain explicitly held.

This transition changes governance and evidence only. Product code is held
until its own exact-SHA ordinary CI passes.
