# P9-00 Phase 9 Anchor Validation

Status: `PASS — LEVEL 2`

## Purpose

P9-00 converts the Phase 8 Level 3 PASS into a bounded Phase 9 audit anchor. It
does not implement Phase 9 product behavior and does not contact or modify any
external system.

## Accepted predecessor evidence

- P8-09 diagnostics-off checkpoint:
  `6235502363e34b1279a0c0e26d8d6aecbbd7811f`.
- Exact-SHA ordinary CI `33342183499`: repository, frontend, visual and secret
  lanes all passed.
- Final Level 3 `33342817983`: repository `99341407027`, frontend
  `99341406968`, visual `99341406989`, secret `99341406965`, controlled
  preflight `99342574101` and cumulative runtime `99342604163` all passed.
- Runtime artifact `9741314098`, visual artifact `9741125285` and gitleaks
  artifact `9741066445` are recorded with their checksums in the P8-09 validation
  and Phase 8 Gate report.

## Audit result

- The Phase 9 requirement inventory is complete and split into P9-01 through
  P9-08 atomic boundaries in `implementation/phase-9-requirement-anchor.md`.
- Current LaunchFlow architecture, ownership and contracts stay the baseline;
  P9-00 authorizes no redesign, refactor or product implementation.
- External supplier/customer portals (`FR-CO-003`, `FR-CO-004`) and real-project
  pilots M9-04/M9-05 remain user-approved post-V1.2 deferrals.
- Controlled representative UAT for both project types remains required, with no
  real-project-pilot or real-user-adoption claim.
- Production compatibility facts remain governed by P8-07F and the final full
  read-only reconciliation remains a mandatory release condition.

## Validation evidence

Local Level 1/2 evidence is green: the current-task and reconciliation verifiers
pass, 40 focused governance tests pass, the generated trace is current,
`git diff --check` passes, and repository verification passes 2,712 Python tests
plus its prototype, visual-governance and reconciliation checks. The local runner
used a temporary `python` to `python3` PATH shim because this host exposes only the
`python3` command; no repository file was changed for that environment difference.

The initial checkpoint `2422aeef9b290a69f71acf686eb5776a03d24d8d`
produced ordinary CI `33344582849`: frontend, visual and secret passed, while
repository exposed the exact clean-checkout/local-worktree epoch mismatch below.
The closed repair checkpoint
`065803ae484d885001259de8238ef01d0ad311e4` then passed ordinary CI
`33345162833`: repository `99347769577`, frontend `99347769578`, secret
`99347769608` and visual `99347769452` all passed. Controlled jobs were
correctly skipped for the ordinary event.

P9-00 is complete. `product_code_authorized` remains false; the separate
controller transition activates only the P9-01 audit/plan task.

Ordinary CI `33344582849` exposed one governance-test epoch mismatch: its clean
checkout correctly contained the two committed portal deferrals, while the local
worktree also contained the user's preserved, uncommitted M9-04/M9-05 deferral
updates. The repair accepts only those two exact complete states (2 or 4 paired
decision/release/rollback blocks); a partial pilot decision still fails closed.
No user-owned document was staged or rewritten.

## Rollback

Restore the accepted P9-00 checkpoint
`065803ae484d885001259de8238ef01d0ad311e4`. No
database, Site, production system, schema, API, worker, UI or translation state is
created or modified by P9-00.
