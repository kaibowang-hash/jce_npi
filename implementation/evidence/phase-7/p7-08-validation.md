# P7-08 Level 2 Validation — Mobile Field Actions

Recorded: `2026-08-16T01:10:00Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact final product checkpoint:
`31114021cf18cf5e32c22902de5150ed2922e7ba`

Primary requirement: `UX-020`

Reconciled Pack anchors: `FR-UX-016` and `NFR-UX-001`

## 1. Outcome

P7-08 delivers one bounded phone/tablet field-action surface over the same
live Trial and Gate BFF capabilities used on desktop:

- exact Project, Trial Plan/Round or Gate/cycle/policy/version, blocker,
  permission, conflict and held-authority truth remains visible;
- Trial photo selection stays local until the unchanged bounded private upload
  command, and only an exact clean File Revision may be bound;
- scanned or manually entered cavity references are exact-matched only against
  already-authorized workspace values; review and apply are separate and
  neither submits a command;
- Trial issue capture and Gate review/decision reuse the unchanged Project-
  first capability, CSRF, optimistic version/hash, actor-bound idempotency,
  audit, receipt, retry and conflict paths; and
- enumerated complex engineering matrices remain desktop surfaces while
  mobile retains bounded critical summaries and an explicit same-authorized-
  link desktop handoff.

No backend route, API, Schema, permission, ownership, business state machine,
dependency, migration, runtime fixture or external adapter changed. Mobile
grants no new authority and no production ERPNext or other external target was
contacted.

## 2. Checkpoint evidence

| Checkpoint | Result | Durable evidence |
|---|---|---|
| reviewed scan and desktop-handoff primitives | `PASS` at `300bc167fbe2912a5a7fac7e31c86f025521749e` | `implementation/evidence/phase-7/p7-08-primitives-checkpoint.md` |
| live Trial field actions | `PASS` at `290c66fe3e2e5c53058b5253b844c6332902f189` | `implementation/evidence/phase-7/p7-08-trial-field-checkpoint.md` |
| live Gate field review | `PASS` at `5e8384f968e1b3e147d5810117ea46b252f483da` | Gate summary/action/state assertions and the governed P7-08 visual matrix in the final product diff |
| historical zoomed Gate visual repair | `PASS` at `31114021cf18cf5e32c22902de5150ed2922e7ba` | Assertions use the actual `(width <= 920px)` responsive boundary and preserve the intended mobile/desktop truth |

The initial checkpoint-3 ordinary run `31898005702` failed only five retained
zoomed Traditional-Chinese Gate snapshots: an effective CSS width of `910px`
correctly selected the mobile layout while the historical test expected the
desktop table. Repair commit `3111402` aligned the test with the actual media
query, regenerated only those five fixed-Linux baselines and independently
reviewed them. It changed no product DOM, style, API, permission, behavior or
PASS criterion.

## 3. Exact-SHA ordinary Gate

Ordinary pull-request workflow `31898840279` passed at the exact final product
SHA:

- repository job `95046204818`: `1,921` tracked Python tests PASS;
- frontend job `95046204781`: `59/59` files, `918/918` unit tests and
  `421/421` non-visual E2E PASS; coverage is
  `80.31% / 80.16% / 82.81% / 82.96%`; all `7,471` direct English sources
  have Simplified- and Traditional-Chinese translations; vulnerability audits
  report zero findings;
- secret job `95046204823`: current tree and `491` branch commits contain no
  leak; artifact `9250529122`, digest
  `sha256:8813adb499eadba0d0d534d97bae78816112340a895918cbcfd988b3e3471adb`;
  and
- visual job `95046204879`: governed fixed-Linux matrix `119/119` PASS;
  artifact `9250577462`, digest
  `sha256:c17989f4bf4f4cf9df637224cb9c2ac5b74e1c852ac579219aff3cf2866a83d6`.

A clean temporary worktree also passed `bash scripts/verify.sh`. The host
worktree result is not cited because an unrelated user-owned untracked image
under `frontend/public/` intentionally trips the brand guard.

## 4. Final cumulative Level 3 Gate

Workflow `31899480493` passed every Level 3 lane at the unchanged exact SHA:

- repository `95047888121`: `1,921` tests PASS;
- frontend `95047888180`: `918/918` unit, `421/421` E2E, complete direct
  trilingual coverage, coverage thresholds and zero-vulnerability audits PASS;
- secret `95047888120`: full `492`-commit tree/history scan PASS; artifact
  `9250685703`, digest
  `sha256:4b50bf64677d400172941d8cc54eed037fca73f120282e581e24746065c58c78`;
- visual `95047888417`: `119/119` PASS; artifact `9250730442`, digest
  `sha256:db8697a4f128150c67b04a72f89a122ceccf3f0fef2f0b0a4a2393e9016fe759`;
- controlled preflight `95049302368`: exact-SHA and Gate-mode checks PASS;
  and
- cumulative disposable runtime `95049356690`: P5, P6 and P7-01 through
  P7-07 runtime plus the unchanged P7-08 presentation boundary PASS; artifact
  `9250918326`, digest
  `sha256:84bff2803a329960e6a0ebcd9f46c48d499a1d13387ef9a61b1e6b7c881840f2`.

The runtime result file hashes to
`sha256:edd107253ac1a008cd976570f5bd761761145e6c57ea729f2018049113635a0d`
and records `result=PASS`, exact head SHA, `gate_mode=level_3`, Site
`npi.localhost`, database `npi_one_runtime`, the disposable-runtime marker,
scope `p5-01-through-p7-07`, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and the Trial-only verifier
command.

The cumulative proof retains two Plan revisions, two planned Rounds, exact
input locks, Actuals, samples/cavities, defects/verifications, conclusions,
readiness/handover/observation truth and two immutable Released Trial
Summaries. Same- and cross-process replay, two migrations, route disable/
recovery, redaction and disposable cleanup pass. Machine, formal ERP quality,
customer, Gate/readiness external authority and integration traffic remain
explicitly unavailable; no production adapter is installed or contacted.

## 5. Requirement, security and review disposition

`UX-020` advances to `TECHNICAL_VERIFIED`. The result covers live responsive
Trial issue/photo/scan and Gate authorized-action paths with direct English,
Simplified-Chinese and Traditional-Chinese, keyboard/touch/zoom/accessibility,
honest denied/read-only/blocked/conflict/processing states and desktop complex-
table preservation.

Task Diff Review over `dda9c13..3111402` covers `10` commits, `39` files,
`3,343` additions and `224` deletions. No API, Schema, dependency, migration,
permission command or production integration changed; no accepted-path TODO,
FIXME or placeholder remains. The evidence-based release review reports zero
P0, P1 or P2 findings.

## 6. Rollback and limitations

Before retained use, the responsive presentation commits may be reverted.
After retained Trial, File, issue, Gate receipt or audit history exists,
rollback disables only the independent mobile presentation and uses a reviewed
forward repair; it never rewrites retained domain history. Desktop Trial and
Gate workspaces remain the recovery path.

Offline sync, background upload/queue, camera barcode decoding, native apps,
device management, biometric/signature semantics, mobile-only authority,
production ERPNext and all external execution remain outside this task.

## 7. Decision

P7-08 passes Level 2. Because it is the final Phase 7 task, the cumulative
Level 3 decision is recorded in `implementation/phase-7-gate.md`. Standing
continuous-delivery authority may activate only `P8-00 — Phase 8 requirement
anchor`; production ERPNext remains prohibited.
