# CI-OPT-02 — Diagnostic Fast Path and Playwright Throughput

Recorded: `2026-09-02`

Status: `FROZEN — IMPLEMENTATION ACTIVE`

Predecessor product checkpoint:
`a439043f96976c562edb8d4af69d51c709390043`

## Outcome

This independent delivery task shortens bounded diagnostic cycles without
changing product behavior or weakening the final release boundary. P9-01 is
accepted only because ordinary CI `33638920721` and diagnostics-off Level 3
`33640546810` pass at its exact product SHA. P9-02 remains paused until this
task passes a complete exact-SHA Level 3.

The diagnostic-only workflow mode always verifies the current repository,
current-tree secrets and cumulative disposable Site. It may reuse frontend and
visual results only from the latest successful ordinary pull-request run on
the same repository branch, when that run's SHA is an ancestor and every
intervening path is an exact diagnostic harness, diagnostic verifier/test or
controller path. Product paths are denied; every unclassified path is unknown.
Denied, unknown, stale, foreign, non-ancestor, incomplete or unavailable
evidence automatically selects the full CI path.

The resulting attestation contains only fixed classification, counts, run/SHA
provenance and explicit `eligible_for_merge=false` /
`eligible_for_release=false`. It never contains changed path values, runtime
payloads, identities, business data or secrets. Diagnostic mode is never a
merge, release or Level 3 Gate.

## Five-run baseline

Durations are seconds from accepted successful ordinary pull-request runs.

| Run | SHA | Repository | Frontend | Nonvisual E2E | Visual | Secret |
|---|---|---:|---:|---:|---:|---:|
| `33624647220` | `70684e30` | 69 | 637 | 447 | 318 | 22 |
| `33628445755` | `7669d554` | 70 | 824 | 610 | 287 | 24 |
| `33631552203` | `7e9e0f24` | 73 | 781 | 568 | 310 | 22 |
| `33634947509` | `749c0096` | 70 | 877 | 630 | 278 | 18 |
| `33638920721` | `a439043f` | 72 | 852 | 624 | 302 | 20 |

| Lane | P50 | P95 (nearest-rank) |
|---|---:|---:|
| Repository | 70 | 73 |
| Frontend | 824 | 877 |
| Nonvisual E2E | 610 | 630 |
| Visual | 302 | 318 |
| Secret | 22 | 24 |

The nonvisual E2E step is the ordinary critical path. The first bounded change
is therefore four Playwright workers for nonvisual tests only. Visual tests
remain at two workers and retries remain zero.

## Changed files to tests

| Surface | Required evidence |
|---|---|
| prior-Gate verifier | exact-run regressions plus latest-run, ancestry, allow/deny/unknown, network and safe-output unit tests |
| CI workflow | workflow static contract, YAML/static validation, full-fallback and final GitHub run evidence |
| Playwright scripts | list discovery, complete nonvisual run, visual worker static guard, retries-zero guard |
| task/controller state | current-task verifier, reconciliation and exact allowed-path diff |

No tests, coverage, threshold, required lane or final Gate may be removed,
retried or relabelled. No mutable Frappe Site is cached.

## Stability and fallback rule

After the implementation's exact-SHA ordinary PASS, rerun the unchanged
frontend job twice at the same SHA. All three four-worker attempts must pass
with identical discovered test count and zero retries. Record E2E P50/P95.
Four workers are insufficient only if the three-run E2E P50 is not at least
20% lower than the 610-second baseline or any run flakes. In that case, and
only then, add native two-way Playwright shards with one aggregate required
check, rerun the same three-run stability proof and retain every test.

## PASS and rollback

PASS requires focused tests, full repository/frontend checks, three stable
four-worker runs, exact-SHA ordinary CI, complete Level 3 including the
cumulative disposable Site, and an evidence-based release-gate review. P9-02
then resumes automatically.

Before P9-02, rollback is a normal revert of only this task. After P9-02,
disable `diagnostic_only` and restore two nonvisual workers while retaining the
complete ordinary and Level 3 paths; use a reviewed forward fix. There is no
product, database, ERPNext or external-state rollback.
