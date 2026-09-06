# Project initialization production release

User authorization: 2026-09-06, deploy the previously implemented role-based
Project initialization to production. Task: PROJECT-INITIALIZATION-RELEASE.
Release Gate: IN PROGRESS; no production mutation by this task yet.

## Base and scope

Read-only SSH to the authorized LaunchFlow host verifies the online release
695afbbbf60b3a28740c5990f83b637a4a06a01b and ten running services. The exact
base has ordinary and Level 3 PASS (34038151983 and 34038154058).
The isolated branch retains that release's ERP master-data selectors, existing
integration code and settings. It excludes unrelated uncommitted changes from
the shared development workspace. Production ERPNext/JCE-Core is not contacted.

FR-PM-001/005/006: a published policy catalog, no-person/date role initialization,
Team/Plan/baseline setup, an original unpublished G0–G7 injection-moulding
Project/work-policy draft, six-department readiness template configuration and
administrative links. Existing Project snapshots are not rewritten. Personal
assignments do not gate role setup, and role definitions do not grant access.
No approver or automatic Gate pass is invented. See docs/PROJECT_INITIALIZATION.md.

## Review and impact map

- Project work API/repository/BFF additions: exact authorization, CSRF, Project
  version, audit, private responses and idempotent replay; complete Project
  module tests and new setup permission/pagination/rollback cases.
- Setup transport/UI: correlated closed response shapes, role-only payload,
  wrong-response rejection, retry, conflict, retained identities, plan and
  baseline review; focused component tests and trilingual browser evidence.
- Admin/readiness/label changes: existing module tests, source coverage,
  mixed-language/accessibility and complete visual regression matrix.
- Catalog emission and lazy setup import: all literal frontend sources remain
  sourced from the complete Frappe CSV catalogs, backend messages stay in CSV;
  extraction guards, full frontend tests/build/budget/audit and complete matrix.
- No DocType schema, permission model, migration, new dependency, core file,
  secret, ERP connector or ownership change is introduced by this release.

## Gate and deployment plan

Require complete local checks followed by exact-SHA ordinary and Level 3 CI.
Use the existing production immutable image build and independently verified
full encrypted backup. Preserve the current exact image pair, release pointer,
private environment copy and all named Site/database/files/log volumes.

The existing rollback helper's maintenance/HTTP-200 health conflict remains
known. For this schema-neutral release, arm a bounded maintenance-off recovery
of the prior environment, image pair and release pointer before recreating the
application services. Keep database/Redis and secrets unchanged. Verify all ten
services, scheduler, HTTPS/unauthenticated API contract and authenticated Project
setup/configuration rendering. Do not create fake business records for smoke
checks and do not activate any ERP adapter or workflow approval.

Rollback restores the retained image selection and pointer with maintenance
off, then repeats health checks; no schema downgrade or historical deletion.
A failure stops the switch and restores service rather than asserting success.
