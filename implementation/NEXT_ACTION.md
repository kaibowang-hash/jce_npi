# Next Action

Status: `IN_PROGRESS`

Current phase: `4 — Project Work Items and Stage Gates`.

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
