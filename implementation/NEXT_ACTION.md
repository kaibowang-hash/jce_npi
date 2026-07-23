# Next Action

Status: `IN_PROGRESS`

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

## Next safely executable Cloud task

Current controller phase: `4 — Project Work Items and Stage Gates`.

Implement atomic task `P4-02 — Team, RACI, WBS, and domain work items` from
`implementation/phase-4-requirement-anchor.md`:

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

Cloud must run and report only checks available in Cloud. Any acceptance step
requiring Docker, a rebuilt Codespace, or the local Frappe runtime is retained
as environment-specific external validation and must use the existing
Codespaces evidence until a relevant toolchain/runtime change requires fresh
Codespaces proof. Missing Docker or registry HTTP 403 in Cloud does not revoke
or overwrite an earlier valid Codespaces Gate.
