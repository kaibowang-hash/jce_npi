# Project initialization production release

User authorization: 2026-09-06, deploy the previously implemented role-based
Project initialization to production. Task: PROJECT-INITIALIZATION-RELEASE.
Release Gate: PASS. Exact code release 1509101557622611a9417bb9417e4181c31f48f4
is deployed on LaunchFlow; the closeout below records the final facts.
The task activation manifests in this exact release remain its historical
invocation metadata; the shared workspace controller was not advanced.

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

## Candidate verification and fixture correction

Candidate cd32fc90 passes local Python 3195/3195 and pinned frontend 1208/1208,
all four unchanged coverage thresholds, type/lint, 9645-source complete Chinese
coverage, build/budgets/brand and both zero-vulnerability dependency audits.
Exact-SHA ordinary 34040573713 and Level 3 34040573816 pass repository,
frontend verification, secret scan, first E2E shard and the complete visual lane.
The second E2E shard fails eight missing-translation assertions before runtime.

Those fixtures had synthesized Frappe response messages from the newly slimmed
browser catalog. They now load the full source CSV through the existing CSV
parser in a test-only server translator, which fails on missing sources. The
product still displays server-localized messages verbatim. No scanner,
threshold, golden image or production message was bypassed. Both complete
exact-SHA gates must rerun after this correction. No production mutation occurred.

## Exact release gate and production result — 2026-09-06

- Code SHA: `1509101557622611a9417bb9417e4181c31f48f4`.
- [Ordinary CI 34041123050](https://github.com/kaibowang-hash/jce_npi/actions/runs/34041123050): PASS on that exact SHA.
- [Level 3 CI 34041119846](https://github.com/kaibowang-hash/jce_npi/actions/runs/34041119846): PASS on that exact SHA, including the complete browser/visual matrix and controlled Frappe runtime.
- Downloaded runtime artifact `p8-integration-runtime-34041119846` states
  `result=PASS`, `gate_mode=level_3`, the exact code SHA and the pinned Frappe
  commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`.
- The unchanged production build script passed from a clean detached checkout.
  Both immutable image labels match the code SHA. The release pointer and all
  seven application services now use it; all ten required services are running.
- HTTPS, authentication-required response, scheduler and container health pass.
  No schema migration, production ERPNext/JCE-Core contact, adapter activation,
  credential change or access grant occurred.
- The original prior release `695afbbbf60b3a28740c5990f83b637a4a06a01b`, image
  pair, private environment copy and all named volumes were retained. The armed
  pre-switch recovery was not needed; the first backup check stopped before any
  image/environment/pointer switch, and the successful run disarmed recovery
  only after health passed.

The user account's temporary-directory quota prevented the initial transfer.
The complete bundle was instead transferred into a root-private release staging
folder and verified as SHA-256
`44ff2c3e9a52417697289491267d7c0b6850867250af2b0a9274bdf61cacd100`.
Partial files from this task were removed. No unrelated images, containers,
archives, volumes or workspace changes were deleted.

### Independently verified full backup

The retained backup helper creates `SHA256SUMS` through output redirection before
its file enumeration, so the manifest incorrectly includes its own changing
contents. The first independent check proved that all four actual payloads
(database, public files, private files and Site configuration) matched and only
the manifest's self-reference failed. Production remained on the prior release.

A root-private deployment wrapper requires exactly those four payloads and the
original five-entry manifest, rejects missing/extra/symlinked files, and verifies
every original payload hash. It removes only the invalid self-reference, creates
a new AES-256 encrypted archive, independently decrypts it and checks every entry
of the corrected complete manifest. Valid repair and tampered-payload rejection
were tested before executing it. The immutable repository backup helper was not
modified; its manifest defect remains a documented maintenance follow-up.

Verified pre-switch encrypted archive SHA-256:
`dfb2ea7f55794024acec2a4eb172da218e990d42b57e09c14ed570693e70189a`.
After the requested role configuration, a second corrected, independently
verified full backup captures those records and again passes health:
`e2580419542d191cf8aa932a2782cbebc834a2a005da165582f66c46e348db62`.
Extracted plaintext staging from both successful backups and the failed first
verification was removed; encrypted archives and private logs are retained.

### Authenticated result and actual requested configuration

The production UI verifies Team role initialization, the bound-policy Plan
editor, the six-department readiness editor, and Administration links for Project,
Gate and work-policy versions. The existing ERPNext-test connection remains.

The user's original six-department and role-only requests were then completed
through the authenticated product/admin interfaces: create the requested original
Project/template/work-policy draft bundle, review and publish its work policy,
and initialize the current Project with exactly six role definitions. The UI
confirms the saved configuration and shows the exact bound policy in Plan.
No personal account/date prerequisite, placeholder user or permission grant was
introduced. These are the user's actual configuration records, not smoke-test
business records. Business identifiers and identities are not copied here.

The G0–G7 Project template remains a draft pending actual Gate evidence/approval
rules. Existing Project Gate snapshots were preserved. No readiness blockers,
Gate approvals, dates, personal assignments or plan baseline were fabricated.
Rollback after configuration must preserve these immutable records and use a
compatible policy-label reader; do not restore the pre-configuration database or
delete published records as a routine rollback.

Real local logs, exact-SHA JSON results, runtime result, complete CI visual
artifact, production build and deployment/health results are retained in the
shared workspace at `implementation/evidence/development/project-initialization-release-local/`.
The local owned verification container was removed. This documentation closeout
does not change the deployed code SHA or assert deployment of its later commit.
