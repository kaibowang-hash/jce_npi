# Next Action

Status: `IN_PROGRESS — PAUSED_BY_USER`

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

## Paused implementation checkpoint

Current controller phase: `4 — Project Work Items and Stage Gates`.

Current unfinished atomic task: `P4-02 — Team, RACI, WBS, and domain work
items`.

The user paused continuous implementation on 2026-07-23 after requesting a
recoverable checkpoint. Do not start P4-03. P4-02 remains `IN_PROGRESS` and is
not a Gate `PASS`.

The checkpoint contains the bounded P4-02 implementation:

- add Project membership, explicit Project role assignments, substitute users,
  and bounded effective dates;
- represent RACI explicitly and keep Project roles separate from Gate approval
  authority unless a future versioned policy grants it;
- add WBS parent/child work, dependencies, owners, planned/actual dates,
  milestones, status, and progress with parent and dependency cycle rejection;
- provide plan-baseline comparison and a critical-task indicator without adding
  a Gantt dependency, resource optimizer, or OpenProject integration;
- persist `risk`, `issue`, `action`, and `decision_request` as distinct domain
  kinds that share context/owner/due/severity/blocking relations but do not
  share one invented convenience lifecycle;
- expose strict authorized queries by Project, stage, owner, and overdue state;
  and
- extend the live Project context only as required to prove this vertical slice,
  with complete literal-English source and direct `zh`/`zh-TW` translations.

Retain P4-01's fail-closed per-Site tenant boundary, owner/admin authorization,
CSRF, strict BFF contracts, expected version, audit, trace identity, and
immutable history protections. Use explicit synthetic role/lifecycle fixtures
only. Do not invent production role-to-approval mappings, implement live
notifications or the full My Work projection assigned to P4-05, contact
production ERPNext, or weaken any Class-B hold in the Phase 4 anchor.

## Exact resume point

When the user explicitly resumes delivery, continue P4-02 only:

1. review the checkpoint diff and the resolved HMAC-cursor and named-placeholder
   findings;
2. record the P4-02 `changed-files → affected-tests` map and run a Level 2 Task
   Gate: the complete Project-work module plus every affected API, permission,
   integration, E2E, i18n, and visual check;
3. use the catalog source-to-page mapping to run affected English, `zh`, and
   `zh-TW` cases, then perform representative original-resolution industrial UI
   and trilingual review; do not regenerate unrelated visual cases merely
   because the catalog hash changed;
4. review P4-02 Requirement ID traceability, the complete Task Diff, and every
   acceptance criterion, and write durable Task Gate evidence;
5. escalate to Level 3 if the impact boundary cannot be established reliably;
   independently, run Level 3 at the later Phase-end, PR-merge, or release
   boundary and retain its complete evidence;
6. only after every applicable Gate passes, mark P4-02 `PASS` and activate
   P4-03.

The earlier Phase 3 business UAT remains the first incomplete external task.
No Hard Blocker exists; this is an explicit user-requested pause.
