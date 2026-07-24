# P4-04 Final Cloud Handoff Checkpoint

Status: **IN PROGRESS — backend foundation only; P4-04 is not PASS**

Recorded: `2026-07-24T09:02:26Z`

Starting local/remote checkpoint:
`ad4c3234c055066e21ff6fdd95dc40e33f222933`

Branch: `codex/npi-v1.2-implementation`

Requirements: `FR-SG-003`, `FR-SG-005`, `FR-SG-006`, `FR-SG-007`, with the
current Phase 4 contribution to `FR-CO-006`

## Checkpoint decision

The explicit final-handoff instruction stopped new product development. The
retained minimum consistent unit is a bounded P4-04 backend foundation:

- a canonical pure domain for frozen Gate inputs, versioned synthetic review
  policy, explicit authority bindings, parallel/sequential review,
  policy-bounded exceptions, immutable decisions, new-cycle reopen/
  invalidation transitions, and the current-decision guard;
- administrative policy root/version persistence and exact policy loading;
- controlled Cycle, Review Record, Exception, Event, and Decision Snapshot
  history scaffolds;
- Gate Shell review-input version, state, and exact cycle/policy/decision
  references;
- a non-Desk, unassigned transport-role fixture;
- seven strict BFF routes with closed OpenAPI and ownership contracts.

No production policy is installed. No P4-05 work is retained.

The API protocol is not represented as live. Its default factory names the
future `npi_core.gate_review.frappe_repository`, which is absent. A late
repository draft was excluded because it called undefined persistence and
impact-action helpers and had no tests. Associated unverified idempotency,
transport DocPerm, audit-permission, impact-action, and frontend drafts were
also excluded. The retained review/history DocTypes and Gate Shell therefore
remain System-Manager-only.

## Changed files to affected checks

| Changed files | Directly affected checks |
|---|---|
| `apps/npi_core/npi_core/gate_review/domain.py`; `tests/test_phase4_gate_review_domain.py` | pure-domain focused tests; Black; Python compile; literal-source scan |
| `gate_review/frappe_policy_repository.py`; policy root/version DocTypes/controllers | policy metadata, controller, and repository tests |
| `gate_review/frappe_validation.py`; Cycle/Record/Exception/Event/Decision DocTypes/controllers | review-history metadata and controller tests; controlled-history pattern scan |
| Gate Shell metadata/controller | Gate Shell focused tests; P4-03 Gate evidence metadata/controller regression; Project metadata permission regression |
| `hooks.py`; `fixtures/role.json` | exact transport-role fixture tests |
| `gate_review_api.py`; `bff.py`; OpenAPI and ownership contracts | focused API tests; review/project/evidence contract compatibility; YAML/local `$ref` validation; Python compile |
| recovery, traceability, decision, risk, blocker, and task evidence | YAML/CSV/Markdown consistency; final `git diff --check` |

## Level 1 evidence

The affected test strategy was cumulative. Passing broad P4-03 evidence was
not restarted.

| Command or review | Result |
|---|---|
| `/usr/local/py-utils/bin/pytest -q tests/test_phase2_metadata.py tests/test_phase4_project_metadata.py tests/test_phase4_project_contract.py tests/test_phase4_project_work_metadata.py tests/test_phase4_gate_evidence_metadata.py tests/test_phase4_gate_evidence_controllers.py tests/test_phase4_gate_evidence_contract.py tests/test_phase4_gate_review_domain.py tests/test_phase4_gate_review_policy_metadata.py tests/test_phase4_gate_review_policy_controllers.py tests/test_phase4_gate_review_policy_repository.py tests/test_phase4_gate_review_history_metadata.py tests/test_phase4_gate_review_history_controllers.py tests/test_phase4_gate_review_gate_shell.py tests/test_phase4_gate_review_transport_role.py tests/test_phase4_gate_review_api.py tests/test_phase4_gate_review_contract.py` | Initial run: 121 passed, 1 failed. The failure exposed an unverified future `NPI API User` DocPerm residue. The residue and untested idempotency scaffold were removed rather than weakening the existing metadata contract. |
| `/usr/local/py-utils/bin/pytest -q tests/test_phase4_project_metadata.py` | PASS — 11/11 after the permission-residue repair |
| `/usr/local/py-utils/bin/pytest -q tests/test_phase4_gate_review_domain.py` | PASS — 16/16 after final literal-translation call repair and late-file stabilization |
| `/usr/local/py-utils/bin/pytest -q tests/test_phase4_project_contract.py tests/test_phase4_gate_evidence_contract.py tests/test_phase4_gate_review_contract.py` | PASS — 29/29 against the final retained contract |
| Gate Shell focused lane | PASS — 7/7 plus 23/23 directly affected P4-03 metadata/controller regressions |
| Policy metadata/controller/repository lane | PASS — 9/9 |
| Review-history metadata/controller lane | PASS — 11/11 |
| Transport-role fixture lane | PASS — 3/3 |
| API/strict-contract focused lane | PASS — 17/17 |
| `/usr/local/py-utils/bin/black --check apps/npi_core/npi_core/gate_review/domain.py` | PASS — final domain file unchanged by Black |
| Direct changed-file `py_compile`, OpenAPI/data-ownership YAML parsing, and local `$ref` review | PASS |
| prohibited implementation scan | PASS for `ignore_permissions`, `db_insert`, `set_user`, raw `frappe.db.sql`, TODO/FIXME, and fake-success paths in the retained P4-04 scope |
| `git diff --check` | PASS |

## Known failing Level 1 criterion

`node frontend/scripts/build-catalog.mjs --check` fails closed after source
extraction. The retained backend/DocType sources produce 1539 literal sources,
while each existing Chinese catalog contains 1274 entries:

- `zh`: 265 missing direct translations;
- `zh-TW`: 265 missing direct translations.

The missing catalog entries are not waived and no fallback-English production
claim is made. They should be completed once the remaining P4-04 backend
source copy stabilizes, then the generated React catalog and affected
mixed-language checks must be updated together.

## Not delivered or validated

- core Frappe Gate review repository and live workspace hydration;
- actor-bound idempotency persistence, transport DocPerms, exact member/
  authority checks, fixed lock order, audit/seal/rollback, concurrency and
  replay;
- automatic evidence/WBS/File dependency invalidation and deterministic
  blocking impact action;
- Site migration, real Frappe permission/CRUD denial, runtime and live API
  evidence;
- React review room/data source, component/E2E/accessibility tests, direct
  trilingual catalogs, screenshots, and visual comparison;
- P4-04 Level 2 Task Gate and required contract/Schema/auth-triggered Level 3;
- Phase 3 external named-reviewer UAT and sanitized-data sign-off;
- production approval/exception/invalidation/segregation policy or production
  ERPNext access.

## Recovery boundary

Resume P4-04 from the complete protocol and persistence scaffolds in this
checkpoint. Implement one bounded repository/permission unit first, with
direct repository, IDOR, authority, transaction, concurrency, generic-CRUD
denial, and idempotency tests. Do not resurrect the excluded partial draft.
After backend copy stabilizes, complete direct `zh`/`zh-TW` coverage once.
P4-05 remains inactive until the complete P4-04 Gate passes.
