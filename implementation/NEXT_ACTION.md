# Next Action

Status: `IN_PROGRESS`

Current phase: `4 — Project Work Items and Stage Gates`.

Complete atomic task `P4-00`: create the Phase 4 requirement anchor before
business code. Reconcile the controller/ROADMAP/backlog M3 boundary with the
Pack trace rows; freeze the Project, Team/RACI, unified WorkItem, Gate template,
Evidence, review/snapshot/reopen, activity/comment, and My Work integration
scope; map requirements to domain objects, APIs, permissions, audit,
localization, UI states, migrations, tests, evidence, and rollback.

Record explicit Class-B holds instead of inventing production truth for:

- project numbering, customer/order ownership, and ERP-triggered draft creation;
- production template contents, durations, skip rules, RACI-to-approval mapping,
  and segregation of duties;
- the final persisted WorkItem kind/lifecycle vocabulary;
- project health/cost thresholds and ownership;
- Gate waiver/conditional-pass authority, automatic invalidation dependencies,
  and pause/cancel/resume/close approval rules.

Do not silently expand Phase 4 into portfolio/KPI, Gantt/OpenProject integration,
external portals, live notifications, ERP-owned actual-cost synchronization, or
formal ERP-triggered project creation. Continue with generic/versioned NPI-owned
infrastructure and explicit synthetic fixtures where production rule mappings
are held. Use only `implementation/REQUIRED_INPUTS.md` for external facts, never
contact production ERPNext, and preserve `TECHNICAL_PASS_PENDING_UAT` for Phase
3 until named business evidence arrives.
