# Next Action

Status: `P5-00 PASS — P5-01 ACTIVE`

Recovery time: `2026-07-25T18:21:56Z`

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
- Completed Phase 5 controller task:
  `P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
  EBOM` (`PASS`).
- Current unfinished atomic task:
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

## Current P5-01 task

Implement only the minimum complete document/design-revision vertical slice
defined by `implementation/phase-5-requirement-anchor.md`.

Primary Requirement IDs:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

P5-01 must:

1. create `implementation/evidence/phase-5/p5-01-plan.md` with exact scope,
   non-scope, Class-B holds, Requirement → Code → Test → Evidence and
   changed-files → affected-tests;
2. set only the seven P5-01 trace rows to `IN_PROGRESS_P5_01`;
3. inventory and extend, without reinterpreting, the existing private
   `FileRevision`, Project authorization, idempotency, audit, BFF, App Shell
   and translation foundations;
4. keep `ControlledDocument`, `DocumentRevision`, and exact private
   `FileRevision` as distinct identities;
5. deliver additive controlled-document/revision/relationship/lock/history
   persistence with strict BFF contracts, server-side tenant/Project/object
   authorization, CSRF, expected versions, actor-bound idempotency, audit and
   transaction rollback;
6. deliver Project-scoped confidentiality and authorized download audit,
   capability-truth preview/download fallback, and explicit unavailable
   external-retrieval/CAD-PDM states;
7. deliver the live industrial Design/Documents workspace with complete
   literal-English and direct `zh`/`zh-TW` coverage; and
8. run the applicable Level 1 repair checks and one complete P5-01 Level 2
   Task Gate, review the diff, update evidence/recovery, commit, push, confirm
   the remote SHA, and automatically activate P5-02.

P5-01 must not review, approve, release, supersede, obsolete, baseline,
publish an EBOM, create an ERP execution request, enable external retrieval,
claim an Office/CAD viewer, connect CAD/PDM/ERPNext, install a production
document policy, or treat the existing `FileRevision.released` flag as a full
document-release workflow. Bottom-level Frappe File retention for released
content remains a mandatory P5-02 server-side release invariant.

## Exact recovery steps

1. Fetch `origin`, check out `codex/npi-v1.2-implementation`, and compare local
   and remote HEAD/ahead-behind without reset, rebase or force push.
2. Confirm the P5-00 checkpoint is committed and pushed; record its exact
   remote SHA in the P5-01 plan/recovery update.
3. Reuse the complete Phase 4 Gate and P5-00 documentation/trace evidence; do
   not rerun either merely to restore context.
4. Read only the Phase 5 anchor, the seven P5-01 trace rows, their indexed
   requirement text, directly related file/project/contracts/ADRs and the
   applicable `frappe-safe-change`, `npi-domain-guard`, `industrial-ux`, and
   `frappe-i18n` Skills.
5. Create and validate the P5-01 plan before product code.
6. Keep Phase 3 external UAT, production document/rule/provider packages,
   external retrieval and production ERPNext/CAD/PDM as scoped holds; they do
   not block the safe NPI-owned P5-01 slice.
7. Implement and validate only P5-01, create a recoverable checkpoint, commit,
   push, confirm the remote SHA and automatically activate P5-02.
