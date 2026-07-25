# Next Action

Status: `PHASE 4 PASS — P5-00 ACTIVE`

Recovery time: `2026-07-25T17:54:13Z`

Active execution goal:
`implementation/ACTIVE_EXECUTION_GOAL.md`

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- First incomplete acceptance phase:
  `3 — React App Shell Siemens UI and i18n Foundation`.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; named business UAT and
  provenance-backed sanitized-data review are externally unsigned.
- Latest completed implementation phase:
  `4 — Project Work Items and Stage Gates` (`PASS`).
- Completed Phase 4 atomic tasks: `P4-01` through `P4-05`.
- P4-05 result: `PASS — LEVEL 3 FULL RELEASE GATE`.
- Current authorized implementation phase:
  `5 — Part Design, Documents, Baselines, and EBOM` (`IN_PROGRESS`).
- Current unfinished atomic task:
  `P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
  EBOM`.
- First product task after P5-00 passes:
  `P5-01 — Document and design revision`.
- Compatibility Pack task:
  `M4-01 — Document and design revision`.

## Completed Phase 4 boundary

P4-01 through P4-05 deliver the bounded Project/Gate technical foundation:

- immutable versioned Project templates and live Project cockpit;
- explicit Team/RACI, WBS, plan baseline and distinct Domain Work Items;
- immutable Gate templates, frozen requirements and controlled evidence;
- versioned review policies, exact frozen authority, immutable decisions,
  preserved-cycle reopen, dependency invalidation and downstream denial;
- live current-actor My Work projection with exact source revalidation;
- versioned Project Control Policy, four-dimensional health, fail-closed
  lifecycle control, internal activity and reusable learning; and
- complete strict BFF, audit, permission, English-source/`zh`/`zh-TW`, browser
  and industrial visual evidence.

Complete Phase evidence:

- `implementation/phase-4-gate.md`
- `implementation/evidence/phase-4/p4-05-validation.md`

No production Project/Gate/control policy, production ERPNext connection,
notification/external-user/mail/print/portal delivery, or Phase 3 business-UAT
result is claimed.

## Passed evidence — do not repeat merely to restore context

- Python: `587/587 PASS`.
- Frontend unit/component: `492/492 PASS`.
- Frappe-compatible i18n: `2,221` literal English sources with complete direct
  `zh` and `zh-TW`.
- Frontend coverage: 84.87% statements, 84.01% branches, 89.66% functions,
  86.79% lines.
- Build/audit: 404 modules; strict install-script policy; zero complete and
  production-only npm vulnerabilities; visible bundle warning retained.
- Additive/idempotent Site synchronization: `PASS`.
- Complete cumulative live Frappe runtime: `PASS`, including a 296-source /
  184-row / 127-active My Work rebuild, injected rollback, terminal
  deactivation, fourteen-route disable/recovery and cross-process replay.
- Complete non-visual Playwright: `227/227 PASS`.
- Forced full visual regeneration: `188/188 PASS`.
- Separate clean visual comparison:
  `188/188 PASS` at unchanged `maxDiffPixelRatio: 0`.
- Original-resolution three-language visual review: `PASS`.
- Independent requirement, domain, permission/security, migration/rollback and
  release reviews: `PASS`, no blocker/major/minor finding.

The host Node 18 `make verify` preflight rejection ran no product assertion.
The retained Node 24 target evidence above is authoritative.

## Current P5-00 task

Create `implementation/phase-5-requirement-anchor.md` before any Phase 5
business code. P5-00 must:

1. read the Phase 5/M4 Pack boundary and relevant accepted ADRs/contracts;
2. allocate `FR-DS-001` through `FR-DS-014` without changing their acceptance
   meaning;
3. reconcile document/design revision, controlled files, baselines, impact
   invalidation, EBOM revision/comparison and formal publish-request scope;
4. preserve ERPNext ownership of formal Item/MBOM/manufacturing execution and
   prohibit production ERPNext access;
5. explicitly allocate or hold external sharing (`FR-DS-008`), ERP publish
   (`FR-DS-013`) and CAD/PDM connector (`FR-DS-014`);
6. record Class-B holds, scope/non-scope, requirement-to-task mapping,
   changed-files-to-tests expectations, migration and rollback;
7. define the exact P5-01 through final Phase 5 task sequence using Pack M4;
8. update trace/status/decision/risk/blocker/recovery records;
9. run the applicable P5-00 documentation/trace Gate; and
10. commit, push, confirm the remote SHA, then automatically activate P5-01.

P5-00 must not invent a production document classification, numbering,
approval, retention, baseline, EBOM, Item/MBOM mapping, sharing, CAD/PDM or
ERPNext rule. It must not start P5-01 product code early.

## Exact recovery steps

1. Fetch `origin`, check out `codex/npi-v1.2-implementation`, and compare local
   and remote HEAD/ahead-behind without reset, rebase or force push.
2. Confirm the P4-05/Phase 4 checkpoint is committed and pushed; record its
   exact remote SHA in `ACTIVE_EXECUTION_GOAL.md`.
3. Reuse `implementation/phase-4-gate.md` and
   `implementation/evidence/phase-4/p4-05-validation.md`; do not rerun their
   complete Gates only to restore context.
4. Read the Phase 5/M4 requirement sources, `FR-DS-001..FR-DS-014`, relevant
   contracts, data ownership, accepted ADRs and applicable Skills.
5. Create and validate `implementation/phase-5-requirement-anchor.md`.
6. Keep Phase 3 external UAT and production ERPNext/rule packages as scoped
   holds; they do not block safe NPI-owned P5-00 work.
7. After P5-00 `PASS`, create a recoverable checkpoint, commit, push, confirm
   the remote SHA and activate only `P5-01 — Document and design revision`.
