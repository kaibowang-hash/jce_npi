# Next Action

Status: `IN_PROGRESS — P4-03 ACTIVE`

First incomplete phase: `3 — React App Shell Siemens UI and i18n Foundation`.

Phase 3 status: `TECHNICAL_PASS_PENDING_UAT` — **not** `PASS`.

## First pending task — external validation

Complete `FR-UX-031` business UAT with named Project Management,
Engineering/Tooling, and Quality reviewers using provenance-backed sanitized
data, then record signatures, findings, timings, context switches, and closure
of every Severe finding. This task is environment/business specific and cannot
be completed or signed by Codex. It remains the first incomplete requirement.

`implementation/phase-3-gate.md` nevertheless records the exact Pack-approved
continuation state: the technical release gate is `PASS`, the phase remains
`TECHNICAL_PASS_PENDING_UAT`, the external inputs are not a global blocker, and
Phase 4 is explicitly activated for independent NPI-owned domain work. Therefore
Phase 4 may continue without changing Phase 3 to `PASS` or concealing its UAT
obligation.

## Current implementation checkpoint

Current controller phase: `4 — Project Work Items and Stage Gates`.

Completed atomic task: `P4-02 — Team, RACI, WBS, and domain work items`.

P4-02 passed its Level 2 Task Gate on 2026-07-23. The final cumulative evidence
includes the committed 211-Python/205-frontend aggregate, 63 directly affected
Python tests, a fresh real Frappe runtime, the complete eight-case P4-02 browser
spec, supplemental browser shards, all 147 exact visual cases, six
original-resolution trilingual reviews, Task Diff/trace review, and an
independent release-gate `PASS`. The prior Cloud browser limitation is closed
for this task.

Current atomic task: `P4-03 — Gate templates and controlled evidence`.

P4-03 owns versioned Gate templates, frozen Gate requirement snapshots,
explicit requirement owners/reviewers/dates/evidence types, structured
references to exact domain-object revisions, and private-file revision
references whose real scan state remains visible. It must preserve P4-01/P4-02
authorization, tenant, CSRF, optimistic concurrency, idempotency, audit, trace,
history, localization, and industrial UI boundaries.

Do not implement Gate decisions, conditional pass/waiver policy, immutable
decision snapshots, reopen/invalidation behavior, live notifications, the full
My Work projection, production template contents, production ERPNext access,
or any held production mapping in P4-03. Those remain assigned to P4-04,
P4-05, later phases, or Class-B input.

## Exact resume point

Start only the P4-03 atomic task:

1. read the P4-03 rows in the Phase 4 anchor, `FR-SG-001`,
   `FR-SG-002`, `FR-SG-004`, the Gate/evidence domain specifications, current
   OpenAPI/data-ownership contracts, accepted security/file ADRs, and the
   applicable domain/safe-change/i18n/industrial-UX skills;
2. inventory the existing P4-01 Gate Shell and file/version foundations before
   choosing the smallest additive data and API surface;
3. record P4-03 scope, non-scope, assumptions, risks, changed-files-to-tests
   map, migration/rollback plan, and any Class-B decision hold before changing
   product code;
4. implement one complete vertical slice from a published versioned Gate
   template to a frozen Project Gate-requirement snapshot and exact controlled
   evidence reference;
5. run affected incremental checks during repair and the complete P4-03 Level 2
   Task Gate only when the slice is internally complete; and
6. do not activate P4-04 until P4-03 has durable evidence, truthful traceability,
   Task Diff review, and a passing Gate.

The earlier Phase 3 business UAT remains the first incomplete external task.
P4-02's final evidence is in
`implementation/evidence/phase-4/p4-02-validation.md`. A complete Level 3 gate
remains required at the later Phase/PR boundary.
