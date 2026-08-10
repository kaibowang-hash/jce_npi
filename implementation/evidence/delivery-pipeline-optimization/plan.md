# Delivery Pipeline Optimization — Frozen Plan

Recorded: `2026-08-10`

Status: `FROZEN — IMPLEMENTATION AUTHORIZED`

Starting controller checkpoint:
`937ac245cd8629ff029208d39b54e8cbecfb6a9a`

Retained product checkpoint:
`78efa3ec5c584928f510e4b095ead5a36f2fb376`

## 1. Outcome and baseline

This independent task changes delivery mechanics only. P7-02 remains paused
until the optimization passes a complete Level 3 Gate.

The final P7-01 workflow `31380834335` provides the accepted baseline:

| Boundary | Observed duration | Existing work |
|---|---:|---|
| repository job `93430635765` | about `10m24s` | Python, frontend generation/type/lint/unit/build/audit, non-visual E2E and current-tree secret scan run serially |
| visual job `93430635728` | about `3m35s` | second checkout, npm install, browser install and complete `97/97` visual matrix |
| controlled Site `93430635851` | about `4m46s` | third checkout plus cumulative `p5-01-through-p7-01` disposable Site |

The branch already runs complete ordinary pull-request CI before a controlled
Site dispatch. The manual controlled workflow then repeats the same repository
and visual work. Its critical path is therefore another roughly `10m24s`, even
though the Site itself finishes in roughly `4m46s`. The three P7-01 runtime
repair cycles each paid this duplicate successful-work cost.

The repository job is also internally serial. Python/reconciliation checks,
frontend checks/E2E and secret scanning have no write dependency and can run
as independent fail-closed jobs. Parallelizing them changes elapsed time, not
coverage.

Historical Phase 6/P7 evidence repeatedly isolates exactly eighteen visual
changes to the bottom catalog fingerprint after valid translation additions.
The product catalog hash and its integrity checks are correct; only using that
global hash as screenshot pixels creates unrelated baseline churn.

## 2. Frozen scope and non-scope

The machine-readable authority is `implementation/CURRENT_TASK.json`. It
freezes the exact allowed paths, affected commands, invariants and rollback.

Implementation may only:

1. split the serial ordinary lane into parallel repository, frontend and
   secret-scan jobs while retaining all former commands;
2. add a Level 2 controlled mode that runs only after a machine-verified,
   exact-SHA, successful pull-request ordinary Gate;
3. retain a full Level 3 mode with repository, frontend, both secret lanes,
   complete visual matrix and cumulative controlled Site;
4. upgrade deprecated Action runtimes to reviewed Node.js 24 majors;
5. normalize the catalog fingerprint only inside the eighteen governed P0
   screenshot captures, after first asserting the real catalog value; and
6. validate current task, controller, Requirement allocation, changed paths,
   checks and rollback from one fail-closed manifest.

It may not change product code, public contracts, domain behavior, permission,
ownership, Schema, migrations, translations, catalog generation, visual
components, accepted baselines, tests, thresholds, coverage, Gate labels,
production behavior or external systems.

## 3. Changed-files to affected-tests

| Change surface | Required affected evidence |
|---|---|
| workflow structure and Action majors | workflow contract tests, Dev Container verifier, YAML parse/static structure, exact trigger/secret/job assertions |
| ordinary-lane split | full local `scripts/verify.sh`; separated repository/frontend commands; final CI evidence proving all jobs PASS |
| Level 2 prior-Gate reuse | prior-run response fixture tests for SHA/event/workflow/job/conclusion mismatch and fail-closed network behavior |
| task manifest/state guard | valid repository state plus missing/duplicate/invalid path, Requirement, controller and Git ancestry tests |
| P0 catalog screenshot normalization | direct catalog assertion, P0 registry/spec governance tests and unchanged `18/18` Linux baseline comparison |
| cumulative runtime preflight | current-task verifier, focused Trial runtime contract tests, Shell syntax and final controlled Site |

Level 1 uses the focused commands recorded in the manifest. The completed task
then runs the whole repository and frontend boundaries. Level 3 remains
mandatory because CI and shared visual-governance infrastructure are changed.

## 4. Exact Gate semantics

- Pull requests always run repository, frontend, current-tree plus complete
  branch-history secret scanning, and the complete visual matrix.
- `level_2_controlled` may skip those duplicate jobs only when the supplied
  prior run is a successful pull-request run of this workflow at exactly
  `GITHUB_SHA`, with every required ordinary job successful. The verifier
  rejects missing, foreign, stale, partial, cancelled or failed evidence.
- `level_3` runs the complete ordinary, secret, visual and cumulative Site jobs
  on the final exact SHA. It does not depend on the Level 2 shortcut.
- The current-tree and pull-request-history secret lanes remain distinct and
  trigger-appropriate. Neither is removed.
- Catalog generation and direct `zh`/`zh-TW` integrity remain checked. The P0
  screenshot spec first observes the real version, then substitutes the
  registry-owned stable visual token only for screenshot pixels.

## 5. Level 3 PASS criteria

PASS requires all of the following on one final exact checkpoint:

1. complete local repository verification, non-visual E2E and governed visual
   matrix with no baseline, threshold or coverage reduction;
2. successful pull-request CI at the exact SHA with parallel repository,
   frontend, secret-scan and visual jobs, including full branch-history scan;
3. successful manual `level_3` workflow at the same SHA, including cumulative
   disposable Site through P7-01 and current-tree secret scanning;
4. manifest/controller/phase/Requirement/path consistency PASS;
5. task diff review containing only the frozen paths;
6. migration, rollback, security, i18n and visual evidence unchanged or
   explicitly re-proven; and
7. an evidence-based `release-gate` Skill review with no open blocker.

Only that PASS may close this task and resume the bounded P7-02 audit.

## 6. Rollback

Before P7-02 resumes, rollback is a normal revert of only the optimization
commits and restoration of the former serial workflow. No product or database
rollback exists because this task creates no product row or migration.

After later product work exists, disable only the Level 2 shortcut and use the
retained complete Level 3 path while delivering a reviewed forward fix. Never
rewrite retained CI, runtime or product evidence to simulate rollback.
