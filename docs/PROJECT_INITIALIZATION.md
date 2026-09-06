# Project initialization and injection-moulding collaboration

This guide covers the Project setup workspace deployed on 2026-09-06 at code
release `1509101557622611a9417bb9417e4181c31f48f4`. The requested six-department
work policy has been published and the current Project role framework initialized.
The G0–G7 Project template was subsequently published after the user reported
its absence in the Create project dropdown. Gate approval rules remain
independently reviewed, versioned configuration.

## Configuration locations

An enabled internal System Manager uses Administration for Project templates,
Project template versions, Gate templates, Gate template versions and Project
Work Policy versions. The capability table links to the corresponding supported
Frappe administrative configuration pages. Ordinary Project work stays in the
LaunchFlow Project workspace.

| Configuration | Location | Purpose |
|---|---|---|
| Project template | `/app/npi-project-template` | Template identity and availability |
| Project template version | `/app/npi-project-template-version` | Applicable Project types, ordered Gates, exact Gate-template references |
| Gate template / version | `/app/npi-gate-template`, `/app/npi-gate-template-version` | Gate evidence, review and approval requirements |
| Project Work Policy version | `/app/npi-project-work-policy-version` | Role keys and WBS/work-item lifecycles |
| NPI readiness template | Project → NPI readiness → Configure readiness template | Review a six-department checklist, save a draft, explicitly review publication |

Readiness templates use their existing domain commands. Raw readiness DocType
writes are controlled and are not an alternative editor. The setup editor
retains its saved draft while open; complete review/publication in that session.
It does not provide a library for reopening arbitrary historical draft versions.

## Initialization sequence

1. In Portfolio, open Create project and select the existing published
   `INJECTION-SIX-DEPT` / six-department injection-moulding template, version 1.
   It is available for `new_tool` and supplies the G0–G7 stage framework. Reuse
   it for each new Project; do not create another template for every Project.
   Administrators use the Injection-moulding collaboration template action in
   Team and responsibilities only when a separate fresh draft bundle is needed.
2. Project stage-framework publication and Gate approval configuration are
   separate. The existing domain permits ordered Gate definitions without a
   Gate-template binding. When a binding is configured, it must identify the
   exact published, applicable Gate-template version and snapshot. Publishing
   the Project framework does not approve Gates or invent evidence, approvers,
   approval quorum or waivers. Review those rules for actual Gate execution.
3. In Team and responsibilities, choose **Initialize project roles** and an
   exact published work policy. Review the six role definitions and confirm.
   This initializes the Project's role framework without names, dates, dummy
   users, personal assignments or permission grants. A role definition remains
   distinct from its eventual role holders. Existing Project assignments are
   retained. The **Role definitions** action shows the bound role framework.
   Personal role holders can be configured through Add team assignments when
   work is scheduled; this is not a prerequisite for template or role setup.
4. In Plan, add rows or load the suggested injection plan. Assign the exact
   retained Project role, set actual business dates, parent relationships and
   dependencies, then review/save. The suggested rows have no guessed dates,
   users, owners or durations. Existing row identities and omitted records are
   preserved. Existing persisted rows cannot be deleted through this editor.
5. Capture a named baseline after reviewing the saved plan. This creates an
   immutable snapshot. Later plan edits remain distinct from that baseline.
6. In NPI readiness, review/save/publish the six-department checklist, then
   initialize it separately using the published template, applicable industry,
   exact Project members and due dates. Each suggested item initially requires
   one exact released document, is required, has weight 1 and P0 blocking, and
   references G6. Review these editable draft choices against the customer and
   Project requirements before publication.

Published versions and already-created Project Gate snapshots are immutable.
Creating or publishing a richer template does not add Gates to an existing
Project. A Project created with only G0 cannot use a G6 readiness item. Use a new
Project created from the reviewed complete template, or a separately governed
change to the existing Project's configuration; never rewrite its historical
snapshot. Team, plan and baselines can still be initialized on the existing
Project using its own current version.

## Original six-department draft

The following is a review proposal for a new-tool injection-moulding Project,
not a certified APQP checklist or an automatically approved company procedure.
MC is interpreted as Materials Control. Templates and Project role initialization
do not require the user to supply personnel or dates. The structure uses the existing G0–G7
NPI model. AIAG's publicly described APQP planning-to-launch structure informed
the organization; no proprietary checklist is reproduced:
[AIAG APQP](https://www.aiag.org/training-and-resources/manuals/details/APQP-3).

| Stage | Review purpose | Proposed collaborating departments |
|---|---|---|
| G0 | Customer requirements and opportunity | Sales, Engineering, Quality |
| G1 | Feasibility and Project authorization | Engineering, Quality, Purchasing, Sales, MC |
| G2 | Product design and DFM baseline | Engineering, Quality, Sales |
| G3 | Tooling design and manufacturing authorization | Engineering, Purchasing, Quality, MC |
| G4 | Tooling completion and trial readiness | Engineering, Quality, Purchasing, Warehouse, MC |
| G5 | Trial validation and sample review | Engineering, Quality, Sales |
| G6 | NPI and pilot-production readiness | Engineering, Quality, Purchasing, Sales, Warehouse, MC |
| G7 | Production handover and launch review | All six departments |

| Department / role key | Proposed responsibility and evidence |
|---|---|
| Engineering / `engineering` | Feasibility, DFM, tooling design/manufacture, trial corrections, process instructions, technical handover |
| Quality / `quality` | Inspection plan, sample and dimensional validation, defect closure evidence, pilot quality controls |
| Purchasing / `purchasing` | Supplier readiness, tooling/external-service purchasing follow-up, resin/component availability |
| Sales / `sales` | Customer requirements, sample submission/feedback, customer approval evidence and delivery commitments |
| Warehouse / `warehouse` | Receiving, lot identification, storage, inventory traceability and packaging readiness |
| MC / `materials_control` | Material demand/arrival coordination, pilot material availability and supply-plan exceptions |

The plan starter contains 16 editable work items covering these stages. The
work-policy draft provides Not started, In progress, Completed and Cancelled
WBS state labels and suitable Open / In progress / Closed work-item labels. These
lifecycle labels do not themselves authorize any business transition or Gate.

## Recovery and rollback

Writes require the authenticated session's CSRF token, internal administrator
permission, exact Project version and idempotency key. A lost response retains
the same command identity and payload for retry. A version conflict requires
loading the current Project before creating a new command. The template bundle
is written with its audit and receipt in one transaction; a failed insert rolls
back the bundle. It does not change the source Project's version or Gates.

No migration, ERP connection, new dependency or production-default installation
is included. UI/API rollout can be rolled back while retained records remain
readable. Never delete audit history, published templates or captured baselines
as a rollback technique.
