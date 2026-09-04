---
name: npi-domain-guard
description: Protect NPI, project, stage-gate, tooling, trial, design baseline and change domain rules from ambiguous or convenience-driven implementation. Use for domain models, workflows, APIs and reviews.
---

# NPI Domain Guard

## Check invariants
- Every Gate decision freezes concrete evidence versions.
- Released revisions cannot be overwritten.
- Trial rounds lock product/tool/material/plan inputs.
- Major open defects block configured Gates.
- Readiness percentage cannot override blockers.
- Tooling development and ERP asset states remain distinct.
- Formal quality truth remains in ERPNext.
- Shared fields have one owner.
- ERP execution success is separate from NPI approval.
- Historical approvals and mappings are not silently rewritten.

## Ambiguity
Business rule, state, ownership, permission or approval ambiguity is Class B: stop and present options. Destructive or production ambiguity is Class C.

## Model review
For each aggregate specify:
- identity;
- lifecycle;
- commands;
- invariants;
- events;
- permissions;
- version/concurrency;
- audit;
- external references;
- delete/void semantics.

Reject generic CRUD endpoints for actions with business consequences.
