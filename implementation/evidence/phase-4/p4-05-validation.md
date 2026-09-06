# P4-05 Validation — Live My Work, Activity, and Project Controls

Status: **PASS — LEVEL 3 FULL RELEASE GATE**

Validated: 2026-07-25

Branch: `codex/npi-v1.2-implementation`

Starting checkpoint: `71d628e028a7ac225df562e21ad44cd11beddb3d`

Atomic task: `P4-05 — Live My Work, activity, and Project controls`

Requirement allocation: `FR-PM-008`, `FR-PM-011`, `FR-PM-012`,
`FR-CO-001`, `FR-CO-002`, and `FR-CO-006`

## 1. Bounded outcome

P4-05 completes the Phase 4 technical Project-control path:

> maintain a rebuildable assignment projection from exact governed sources →
> query the current actor's live My Work queue with source-specific
> reauthorization → bind an immutable synthetic Project Control Policy →
> assess four-dimensional health and execute only authorized lifecycle
> transitions → retain contextual internal activity and reusable learning →
> operate the complete path in the trilingual industrial SPA

The delivered boundary includes:

- a normalized, rebuildable My Work assignment projection for exact Domain
  Work Item owners, current Gate Review assignees, and exact invalidation
  responsibilities;
- query-time source, tenant, Project, membership, assignment, capability,
  terminal-state, and target-route revalidation, with unknown or stale sources
  failing closed;
- stable keyset pagination, explicit server `asOf`, current-user time zone,
  due state, source identity/version, why-assigned and next-action codes, and
  honest availability-aware counts;
- `today`, `overdue`, `project`, priority-vocabulary/value,
  `approval`, and `blocker` work views without inventing one cross-domain
  priority model;
- immutable published Project Control Policy versions, exact frozen authority
  bindings, closed health evaluators, append-only assessments, and
  policy-driven pause/cancel/resume/complete commands;
- explicit `unassessed` and `unavailable` behavior when production formulas,
  actuals, thresholds, authorities, or prerequisites are absent, including
  fail-closed Project completion;
- terminal-Project guards across prior Project Work, Gate Evidence, and Gate
  Review mutation paths;
- append-only internal comments, same-Project internal mentions, URL-free
  controlled attachment metadata, allowlisted object links, follow state, and
  a persisted Project activity timeline;
- append-only retrospective, lesson, and template-improvement records with
  exact source Project Template identity; a template improvement is visibly a
  proposal only and never changes or publishes a template;
- fourteen strict P4-05 BFF/direct routes with authentication,
  authorization-before-resolution, CSRF, sealed actor-bound idempotency,
  optimistic versions, privacy-safe errors, audit, trace identity, and a
  tested emergency route-disable/forward-fix switch; and
- live trilingual My Work, Controls, Activity, and Learning workspaces with
  loading, empty, denied, read-only, invalid, conflict, retryable, final,
  processing, available, and unavailable behavior.

No production health formula, actual-cost source, lifecycle authority,
completion-prerequisite package, notification delivery, external user,
mail/print/portal surface, production learning workflow, ERPNext connection,
or business UAT result is installed or claimed.

## 2. Changed-files → affected-tests map

| Change surface | Direct and boundary evidence |
|---|---|
| My Work domain, source refresh hooks, normalized projection, signed cursor, query-time revalidation, rebuild and terminal deactivation | `tests/test_phase4_my_work_domain.py`; `tests/test_phase4_my_work_repository.py`; P4-02/P4-03/P4-04 repository regressions; live rebuild/deactivation/runtime probes |
| Project Control Policy, health/lifecycle rules, frozen authorities and immutable history | `tests/test_phase4_project_controls_domain.py`; `tests/test_phase4_project_control_policy_version_controller.py`; controller/metadata/runtime verifier tests |
| Project controls, comments, followers, activity, learning, receipts and transaction rollback | `tests/test_phase4_project_controls_controllers.py`; `tests/test_phase4_project_controls_api.py`; live comment/follow/learning/replay/rollback probes |
| BFF, request security, route-disable switch, terminal guards and source-specific permissions | Project Controls contract/API tests; shared Project Work, Gate Evidence, and Gate Review repository/API regressions; all fourteen disabled/recovered route probes |
| OpenAPI, data ownership, DocTypes and additive rebuild patch | `tests/test_phase4_project_controls_contract.py`; `tests/test_phase4_project_controls_metadata.py`; JSON/OpenAPI/ownership checks; two guarded Site synchronizations |
| Strict My Work and Project Controls frontend clients/view models | My Work and Project Controls data-source unit tests; shared Project/Project Work parser regressions; TypeScript and full frontend verification |
| Live Work and Project governance UI, conflict recovery, keyboard navigation and proposal semantics | Live My Work and governance component/router tests; `frontend/tests/e2e/p4-05-live.spec.ts`; complete non-visual browser matrix |
| Shared English source copy, direct Chinese catalogs, time-zone labels and visual surfaces | 2,221-entry catalog checks; formatter/copy tests; 18 affected P4-05 visual cases; complete forced and clean 188-case visual matrices |
| Runtime, migration, rollback and recovery | `scripts/verify_project_controls_runtime.py`; complete `scripts/verify-frappe-runtime.sh`; projection rebuild rollback; command rollback; route disable/recovery; cross-process replay |
| Security, trace and release truth | complete Python/frontend/browser matrices; independent permission/domain/security/migration/release review; requirement trace review; prohibited-pattern scan and `git diff --check` |

## 3. Level 2 and Level 3 evidence

| Command or review | Result |
|---|---|
| `python -m unittest discover -s tests -v` | `PASS`: 587 Python tests; no test or threshold was removed |
| focused final hook-failure selection | `PASS`: 26 tests prove only `KeyError`, `TypeError`, and `ValueError` deactivate a malformed derived Gate assignment; operational `RuntimeError` propagates and rolls back |
| Node 24 container `npm run verify` | `PASS`: 19 files / 492 unit and component tests, i18n generation/checks, coverage, build, TypeScript, ESLint, Prettier, style, boundary, industrial-UI, install-script and both npm audit checks |
| Frappe-compatible i18n audit | `PASS`: 2,221 literal English sources with 100% direct `zh` and `zh-TW` coverage; no fallback-English acceptance |
| frontend coverage | `PASS`: 84.87% statements, 84.01% branches, 89.66% functions, and 86.79% lines; thresholds and source scope were not lowered |
| production build | `PASS`: 404 modules; main asset 1,091,572 B / 273,498 B gzip; Project route 74,308 B / 17,458 B gzip; live My Work route 11,763 B / 3,936 B gzip; Gate route 57,650 B / 13,716 B gzip. The visible size warning remains open as R-010 |
| install-script and npm security checks | `PASS`: exact strict allowlist retained; zero complete-tree and production-only vulnerabilities |
| additive Site synchronization and idempotent rerun | `PASS`: new controlled DocTypes and `rebuild_my_work_projection` patch synchronized twice on the guarded disposable Site; no production policy or business record was installed |
| complete live Frappe runtime | `PASS`: base BFF/localization, Project, Project Work fresh and cross-process replay, Gate Evidence, Gate Review, and P4-05 Project Controls/My Work compatibility all completed |
| live My Work rebuild | `PASS`: 296 exact sources produced 184 retained projection rows and 127 active assignments; an injected partial refresh rolled back atomically and two complete rebuilds were identical |
| live terminal and command rollback | `PASS`: reassignment and terminal-state projections deactivate exactly; injected Project-control failure leaves no activity, audit, or idempotency residue |
| live route disable/recovery | `PASS`: all 14 P4-05 BFF/direct routes changed `enabled → disabled → recovered`; two prior routes stayed available; persisted switch state returned `true → false → absent` |
| live sealed replay | `PASS`: a committed Project-control command replayed its exact response in a second process without duplicate history |
| complete non-visual Playwright | `PASS`: 227/227 Chromium cases under one worker; `.last-run.json` records `passed` with an empty failed-test list |
| affected P4-05 visual matrix | `PASS`: 18/18 trilingual My Work, Controls, Activity, Learning, health and lifecycle cases before the full matrix |
| forced complete visual regeneration | `PASS`: 188/188; required because the final shared 2,221-entry catalog changed the Catalog fingerprint rendered across prior pages |
| clean complete visual comparison | `PASS`: 188/188 at unchanged `maxDiffPixelRatio: 0`; results contain only the passing `.last-run.json` |
| original-resolution visual review | `PASS`: three-language My Work detail/time-zone, four health dimensions/evaluator, lifecycle prerequisites/reason/impact, and proposed-not-applied learning evidence are complete, readable and free of blocking overlap or mixed ordinary-language copy |
| independent release/security/domain/migration review | `PASS`: no blocker, major, or minor finding; an independent 160-test selection and `git diff --check` passed |

The host `make verify` correctly stopped at its Node/npm preflight because the
host shell exposes Node 18 instead of the ADR-011 Node 24 baseline. It ran no
product assertion and is not counted as a product failure. The same repository
checks were executed on the retained Node 24 target; the final frontend result
above is the direct authoritative run.

The first complete clean visual attempt exposed the same 220–233-pixel
difference on shared Project screenshots. Original-resolution expected,
actual, and diff inspection proved that only the footer Catalog fingerprint
changed from the earlier catalog; layout, content, and language were
unchanged. The repeated same-root failures were stopped, the complete
188-case set was regenerated once, and the independent clean 188-case
comparison passed. No tolerance, assertion, retry, or acceptance threshold
changed.

## 4. Final repair history

### 4.1 Derived-assignment failure semantics

Gate Review assignment refresh must deactivate malformed derived state without
turning an operational repository failure into a false successful commit. The
final hook catches only closed data-shape/value exceptions per actor,
deactivates that source fail-closed, and lets an operational `RuntimeError`
escape so the caller transaction rolls back. Focused tests cover every caught
type and propagation.

### 4.2 Live-work keyboard and conflict behavior

A work-row keyboard handler previously also reacted to bubbled Enter/Space
events from nested actions. It now activates only when the row itself owns the
event. HTTP 409 has an explicit conflict state, trace, warning, and
`Reload latest data` action; reload discards stale pagination/cursor state and
queries the first current page before accepting another action.

### 4.3 Proposal truth and time-zone copy

Template-improvement creation and detail surfaces now display `Proposed` and
state that the feedback does not change or publish a Project Template. My Work
uses `Due time zone`; the live-work shell uses `System time zone`; shared pages
retain the generic label where that is the truthful context. All new strings
use literal English sources and complete direct Simplified/Traditional Chinese
translations.

### 4.4 Visual evidence completeness

The P4-05 matrix includes full work surfaces plus dedicated original-resolution
locator evidence for My Work details, health/lifecycle tables, learning
proposal semantics, and lifecycle-dialog authority/prerequisite/reason/impact.
The final shared-catalog change then triggered the complete global
regeneration and zero-difference comparison described above.

## 5. Security, migration, and rollback

- No Frappe or ERPNext core file was patched. No production ERPNext endpoint,
  credential, database, scanner, DMS, customer data, notification provider, or
  external user was contacted.
- The browser uses only strict NPI BFF routes. Authentication, CSRF, tenant,
  Project, exact assignment, capability, authority, expected-version and
  terminal-state checks are server enforced.
- System Manager, Project ownership, RACI, evidence reviewer identity, or a
  stale projection does not make an item the actor's work or grant lifecycle
  authority.
- The My Work index is only a derived locator. Query-time authorization and
  source validation remain authoritative; unknown, inaccessible, stale,
  cross-tenant, cross-Project and terminal sources fail closed.
- Controlled policy versions, health, lifecycle, activity, learning and
  idempotency history deny generic mutation/deletion. Commands bind actor,
  operation, Project, expected versions, input hash, idempotency key and trace.
- Schema changes are additive. Existing Projects receive no guessed policy,
  health, authority, follower, activity or learning data. The rebuild patch
  changes only the derived assignment projection from exact existing sources.
- Before retained P4-05 history exists, the starting checkpoint can restore
  the disposable development state. After retained history exists, rollback
  sets the tested route-disable switch, preserves additive tables and
  immutable records, and deploys a reviewed forward fix. It never deletes
  activity/health/lifecycle/learning history or rewrites authority.

## 6. Requirement truth

- `FR-PM-008` is `TECHNICAL_VERIFIED`: configurable closed progress, cost,
  quality and risk health evaluators, aggregation, explicit unavailable state,
  and required red reason/recovery behavior are live and tested without
  installing a production formula.
- `FR-PM-011` is `TECHNICAL_VERIFIED_FOUNDATION`: Project completion and
  lifecycle controls fail closed and audit exact policy/authority/prerequisite
  state; production completion, handover and cost-readiness rules remain held.
- `FR-PM-012` is `TECHNICAL_VERIFIED`: retrospective, lesson and proposed
  template-improvement records are persisted and searchable without mutating
  Project Templates.
- `FR-CO-001` is `TECHNICAL_VERIFIED`: append-only contextual Project
  activity, internal comments, mentions, controlled attachment references,
  object links and follow state are live and tested without depending on
  external chat.
- `FR-CO-002` is `TECHNICAL_VERIFIED`: the live current-actor unified work
  center projects and revalidates exact NPI-owned issue, action, risk,
  decision, approval and blocker sources with today, overdue, Project and
  priority views. Integration-exception work remains unavailable until its
  Phase 8 source exists.
- `FR-CO-006` is `TECHNICAL_VERIFIED_FOUNDATION`: every delivered Phase 4
  API/UI surface uses the complete English/`zh`/`zh-TW` chain; future
  notification, external-user, mail, print and delivery surfaces remain open.

Cross-stage contributions are retained without overclaiming custom saved-view
configuration, arbitrary sort/group/column personalization, real-scale
performance, a final all-domain activity timeline, Phase 8 integration
exceptions, production business rules, or Phase 3 external UAT.

## 7. Exit decision

**P4-05 PASS. Phase 4 PASS.**

P4-01 through P4-05 now form the bounded Project, Work Item, Gate, evidence,
review/decision, My Work, activity, health/lifecycle-control and learning
technical foundation required by the Phase 4 anchor. The complete Phase 4
decision is recorded in `implementation/phase-4-gate.md`.

Automatic continuation activates only
`P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
EBOM`. No Phase 5 product code is authorized until that anchor passes.
