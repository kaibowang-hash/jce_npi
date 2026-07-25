# P5-01 Reconciliation Hold Checkpoint

Recorded: `2026-07-25T20:46:57Z`

Status: **IN_PROGRESS — V1_2_RECONCILIATION_HOLD**

- Branch: `codex/npi-v1.2-implementation`
- Starting synchronized remote checkpoint:
  `6099ac2351567665478ff911bc07c4ef55ab3ee1`
- Atomic task: `P5-01 — Document and design revision`
- Phase: `5 — Part Design, Documents, Baselines, and EBOM`
- P5-01 is not `PASS`; P5-02 and Phase 6 are not active.
- This is a user-directed recoverable execution hold, not an
  `AUTOPILOT_CONTROLLER.md` Hard Blocker and not a product requirement change.

## 1. Implemented scope

The retained minimum internally consistent unit is the bounded P5-01
backend/domain/DocType/repository/BFF/API/contract slice:

- stable `ControlledDocument`, immutable `DocumentRevision`, exact private
  `FileRevision` association, typed relationship, edit-lock event and
  disabled share-grant domain invariants;
- versioned document policy metadata with no production policy or business
  fixture installed;
- nine additive controlled DocTypes and guarded controllers;
- Frappe repository behavior for exact tenant/Project/object authorization,
  actor-bound idempotency, optimistic versions, append-only audit/history,
  safe private-file creation and orphan cleanup;
- strict document BFF routes and payload parsing, route-disable recovery,
  unavailable external/CAD/PDM truth, capability checks and exact audited
  binary retrieval;
- a binary response boundary that prepares headers before commit, emits no
  bytes before the audit transaction commits, and fails closed on commit,
  after-commit or response-assembly uncertainty;
- closed OpenAPI request/response schemas for the nine bounded routes and
  explicit data-ownership declarations;
- direct Simplified Chinese and Traditional Chinese coverage for all 257 new
  backend/DocType source strings, plus the regenerated React catalog; and
- focused domain, metadata, controller, repository, API and contract tests.

No production ERPNext, CAD/PDM, scanner/provider, document policy, external
principal, sharing rule or business UAT result was invented.

## 2. Unfinished scope

P5-01 remains incomplete. This checkpoint does not include or claim:

- the live Project Design/Documents workspace;
- multipart/blob browser transport, frontend parser/view models, components,
  dirty-state integration, E2E scenarios or visual evidence;
- focused migration and real Frappe Site runtime evidence;
- the complete P5-01 permission/runtime/three-language UI acceptance matrix;
- a complete P5-01 Level 2 Task Gate;
- `VERIFIED` status for any of the seven P5-01 requirement rows; or
- document review/release, baselines, EBOM, P5-02 or Phase 6 scope.

The seven P5-01 trace rows therefore remain
`IN_PROGRESS_V1_2_RECONCILIATION_HOLD`.

## 3. Removed temporary drafts

The following unvalidated expansion drafts were restored exactly to the
starting checkpoint and have no retained diff:

- `.github/workflows/ci.yml`
- `.gitignore`
- `frontend/playwright.config.ts`
- `frontend/vite.config.ts`
- `frontend/scripts/normalize-coverage-summary.mjs`
- `frontend/src/app/app-shell.tsx`
- `frontend/src/app/app.tsx`
- `frontend/src/domain/view-models.ts`
- `frontend/src/i18n/copy.ts`
- `frontend/src/pages/project-page.tsx`
- `frontend/src/pages/project-workspace.tsx`

`frontend/src/generated/catalogs.ts` is retained only as the deterministic
catalog generated from the current backend/DocType translation sources; it is
not a new frontend product sub-slice.

## 4. Exact changed-file inventory

### Backend, domain and DocTypes

- `apps/npi_core/npi_core/api.py`
- `apps/npi_core/npi_core/bff.py`
- `apps/npi_core/npi_core/document_api.py`
- `apps/npi_core/npi_core/documents/__init__.py`
- `apps/npi_core/npi_core/documents/domain.py`
- `apps/npi_core/npi_core/documents/frappe_repository.py`
- `apps/npi_core/npi_core/documents/frappe_validation.py`
- `apps/npi_core/npi_core/foundation/errors.py`
- `apps/npi_core/npi_core/request_security.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_controlled_document/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_controlled_document/npi_controlled_document.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_controlled_document/npi_controlled_document.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_command_idempotency/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_command_idempotency/npi_document_command_idempotency.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_command_idempotency/npi_document_command_idempotency.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_lock_event/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_lock_event/npi_document_lock_event.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_lock_event/npi_document_lock_event.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_policy/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_policy/npi_document_policy.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_policy/npi_document_policy.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_policy_version/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_policy_version/npi_document_policy_version.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_policy_version/npi_document_policy_version.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_relationship/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_relationship/npi_document_relationship.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_relationship/npi_document_relationship.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_revision/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_revision/npi_document_revision.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_revision/npi_document_revision.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_revision_file/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_revision_file/npi_document_revision_file.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_revision_file/npi_document_revision_file.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_share_grant/__init__.py`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_share_grant/npi_document_share_grant.json`
- `apps/npi_core/npi_core/npi_core/doctype/npi_document_share_grant/npi_document_share_grant.py`

### Contracts and localization

- `apps/npi_core/npi_core/translations/zh.csv`
- `apps/npi_core/npi_core/translations/zh-TW.csv`
- `contracts/data-ownership.yaml`
- `contracts/npi-api.openapi.yaml`
- `frontend/src/generated/catalogs.ts`

### Focused tests

- `tests/test_phase5_document_api.py`
- `tests/test_phase5_document_contract.py`
- `tests/test_phase5_document_controllers.py`
- `tests/test_phase5_document_domain.py`
- `tests/test_phase5_document_metadata.py`
- `tests/test_phase5_document_repository.py`

### Recovery, trace and evidence

- `implementation/ACTIVE_EXECUTION_GOAL.md`
- `implementation/BLOCKERS.md`
- `implementation/LAST_RUN.md`
- `implementation/NEXT_ACTION.md`
- `implementation/PHASE_STATUS.yaml`
- `implementation/REQUIREMENT_TRACEABILITY.csv`
- `implementation/evidence/phase-5/p5-01-plan.md`
- `implementation/evidence/phase-5/p5-01-reconciliation-hold.md`

The inventory contains exactly 55 retained changed or new files.

## 5. Changed-files to affected-checks

| Change surface | Direct affected checks |
|---|---|
| document domain, repository, controllers and API | six P5-01 Python suites; Python compile, Black and flake8 |
| shared API/BFF/request-security/error paths | five directly affected existing BFF/API suites plus foundation regression |
| nine DocType JSON files and two YAML contracts | JSON/YAML parse; P5-01 metadata/controller/contract suites |
| two Frappe translation CSV files and generated catalog | catalog generation check and complete i18n audit |
| trace, phase, recovery and evidence files | safe YAML parse, trace row/count assertion and `git diff --check` |

## 6. Tests passed and still valid

| Check | Result |
|---|---|
| P5-01 repository, API, domain, metadata, controller and contract suites | `PASS — 63/63` after final formatting |
| Binary response/failure matrix | `PASS — 15/15`; included again in the final 63-test run |
| Directly affected existing foundation and five BFF/API regression suites | `PASS — 107/107` |
| Python compilation for changed backend and focused tests | `PASS` |
| Black check, one file per invocation to avoid the container multi-file finalizer hang | `PASS — 22/22 formatted files` |
| flake8 for the changed Python surface (`E501`, `W503` and Black-canonical Protocol-stub `E704` ignored) | `PASS` |
| New DocType JSON parse | `PASS — 9/9` |
| OpenAPI, data ownership and phase-status YAML parse | `PASS — 3/3` |
| Generated catalog freshness | `PASS` |
| Literal source and translation audit | `PASS — 2478 sources; 100% zh/zh-TW coverage` |
| Requirement trace integrity | `PASS — 173 unique IDs; exactly seven held P5-01 rows` |
| Exact changed-file inventory reconciliation | `PASS — 55/55 paths` |
| Bounded prohibited-pattern scan | `PASS — no production TODO/FIXME, permission bypass, direct SQL or raw HTTP endpoint` |
| Independent bounded checkpoint review | `PASS — no must-fix; runtime/permission/Level 2 gaps remain explicitly unfinished` |
| Final whitespace/diff check | `PASS` |

The accepted Phase 4 Level 3 result in
`implementation/phase-4-gate.md` and the P5-00 documentation/trace Task Gate
in `implementation/evidence/phase-5/p5-00-validation.md` remain valid and
reusable. They were not rerun. No unrelated Phase 4 or full-repository Gate
was run for this hold checkpoint.

## 7. Truthful checkpoint result

This Level 1 evidence establishes only that the retained current work unit is
internally consistent and recoverable. It does not satisfy the complete
existing Pack acceptance for P5-01, so P5-01 remains
`IN_PROGRESS — V1_2_RECONCILIATION_HOLD`.

## 8. First resume action

After the hold is explicitly lifted and an accepted DOCX–Pack reconciliation
result exists, fetch this branch and verify its synchronized checkpoint SHA.
Then compare the retained backend/domain/DocType/repository/BFF/API/contracts
against that accepted reconciliation result and either retain them or apply
the smallest required correction. Only after that comparison may the
unfinished P5-01 frontend/runtime/UI evidence slice resume.
