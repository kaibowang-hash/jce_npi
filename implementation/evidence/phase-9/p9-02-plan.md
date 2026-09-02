# P9-02 — Portfolio, KPI and Internal Collaboration Plan

Recorded: `2026-09-03`

Status: `P9-02C FRONTEND LOCAL PASS — P9-02D FINAL GATE AUTHORIZED`

Base checkpoint:
`ea6112fa04e08cee6920407df426efc685cea98b`

## Outcome and boundaries

P9-02 implements only the accepted M8-02 boundary for `FR-SG-008`,
`FR-SG-009`, `FR-CO-005`, `FR-CO-007`, `FR-RP-001` through `FR-RP-007` and
`INT-014`. It reuses the current Project, Gate, My Work, Tooling, Trial,
Readiness, Change and ERP projection implementations. It does not redesign
those domains or create a second system of record.

Every cross-object query is server-side permission filtered. NPI engineering
truth remains NPI One owned; ERP customer, supplier, Item, procurement, cost,
quality and Asset truth remains read-only and source-labelled. Missing, stale
or unavailable ERP truth remains explicit and never becomes zero, healthy or
successful synthetic data. BI is read-only and cannot write back.

External supplier/customer portals (`FR-CO-003`/`FR-CO-004`) and M9-04/M9-05
real-project pilots remain `USER_APPROVED_POST_V1_2_DEFERRED`. P9-02 creates no
external identity surface and makes no real-user adoption claim. No production
ERPNext read is needed for this audit because accepted P8-07F inventory and
existing P8 projections cover the source boundary; any later proven freshness
gap must use the standing task-scoped read-only delta process.

## Current implementation audit

| Requirement | Existing reusable implementation | Proven gap | Planned minimum |
| --- | --- | --- | --- |
| `FR-SG-008` | My Work already calculates overdue/today state and exposes blockers; Gate/project rules are versioned. | No scheduler-backed reminder/escalation delivery or live notification feed. Ownership currently marks delivery unavailable. | Add an internal, idempotent due-notification projection and operation-specific scheduler entry; critical audit notifications cannot be disabled. |
| `FR-SG-009` | Project cockpit, Gate state and target SOP are persisted and permission checked. | No cross-project management query or filters. | Add one bounded permission-filtered portfolio query with customer, PM, project type, factory and SOP-month filters. |
| `FR-CO-005` | Audits, My Work and integration failures already expose actionable internal facts. Shell notification control is an explicit placeholder. | No live in-app/email delivery feed. | Add operation-specific notification delivery/read APIs and explicit failed/unavailable truth; no generic message sender. |
| `FR-CO-007` | Project WorkItem already owns actions and decision requests with source/version/audit. | No meeting-minute source record or source link. | Add a versioned internal meeting-minute command that can atomically create linked action/decision WorkItems. |
| `FR-RP-001` | Individual Project/Tooling/Trial/Change APIs exist and enforce Project authorization. Shell search is an explicit placeholder. | No bounded cross-object search endpoint. | Add permission-filtered typed search with fixed object families, deterministic pagination and direct object routes. |
| `FR-RP-002` | Project, Gate, My Work, risk/issue and ERP projection facts exist. | No management portfolio aggregation. | Aggregate read-only portfolio rows; label NPI/ERP fields and freshness. |
| `FR-RP-003` | My Work and Project cockpit already provide milestones, overdue work, blockers, decisions and integration operations. | No consolidated PM cross-project view. | Reuse the same portfolio contract with PM-oriented saved filters and object drill-down; no duplicate ownership. |
| `FR-RP-004` | Tooling, trial quality, acceptance and ERP cost/Asset projections exist. | No cross-project tooling summary. | Add source-labelled tooling rollups with unavailable/stale handling. |
| `FR-RP-005` | Readiness, production transition, trial, documents and customer approval evidence exist. | No cross-project NPI readiness summary/review-pack entry. | Add source-labelled readiness rollups and links to existing controlled export/print seams; no new uncontrolled export. |
| `FR-RP-006` | Audited timestamps and lifecycle facts exist. | KPI definitions and trend endpoint are absent. | Freeze named calculations, numerator/denominator, source, time zone and availability before exposing monthly trends. Excel/PDF hardening remains P9-06; P9-02 provides the governed data/view only. |
| `FR-RP-007` | Gate, readiness, production-transition and integration policies already use operation-specific versioned commands and audit. | No consolidated read-only configuration inventory; generic field/status administration would violate architecture. | Reuse existing commands and add a read-only administration catalog with capability links. No generic DocType/config writer. |
| `INT-014` | Existing BFF and ERP projections are read-only, source-labelled and permission checked. | No explicit reporting/BI read contract. | Add a bounded read-only reporting contract suitable for later incremental extraction; no reverse write, browser-direct ERP, ETL credential or production job. |

## Atomic checkpoints

1. `P9-02A` freezes exact reporting/search/KPI/notification/meeting contracts,
   ownership and the implementation path set after this audit/plan transition
   passes ordinary CI.
2. `P9-02B` implements the backend vertical slice: permission-filtered search
   and portfolio/KPI queries, explicit source/freshness truth, versioned meeting
   minutes, linked WorkItems and idempotent notification delivery.
3. `P9-02C` implements the industrial React surfaces: live Project Portfolio,
   global search, notification feed, reporting drill-down, configuration
   inventory and Project meeting-minutes workflow in English, Simplified
   Chinese and Traditional Chinese.
4. `P9-02D` runs disposable-Site runtime, normal/empty/no-permission/stale/
   unavailable/conflict/duplicate/scheduler-failure tests, full visual/i18n/
   accessibility evidence, exact-SHA ordinary CI and one final Level 3.

Each checkpoint is a complete batch. Failures from the same root are
preflighted and repaired together; one failure must not create one commit.

## P9-02A/B implementation checkpoint

The audit/plan exact SHA `4123eb86c930c9c091cfb18a67a37ae9552fdd04`
passed ordinary CI `33662703332`, releasing the product hold. The resulting
backend candidate implements the frozen reporting/search/KPI/configuration,
meeting-minute, linked WorkItem and internal notification seams. Full
repository verification passes 2,883 tests; the only initial security-scan
hit was the scanner token written literally inside its own metadata test, and
the corrected test plus the exact scan now pass with zero matches.

P9-02C is limited to one live Portfolio/Reporting/Administration workspace,
the existing Shell search and notification controls, and one Project meeting
tab. Exact frontend source, test and three-locale visual paths are frozen in
`CURRENT_TASK.json`. No generic writer, new domain, external identity, ERP
mutation or production ERP contact is introduced.

## P9-02C frontend checkpoint

Backend catalog-repair SHA
`2432144515e8b632ee2a50bf717c2a6e919c2bf2` passes complete ordinary CI
`33669976985`, including repository, secret, frontend verification, both
complete nonvisual E2E shards, governed visual and aggregate frontend lanes.

The frontend checkpoint implements the exact frozen paths as one batch. The
Shell now uses the permission-filtered typed search and recipient-only
notification APIs. Portfolio, KPI trend and read-only administration views
consume their operation-specific contracts without a generic writer or BI
writeback. Project meeting minutes are immutable and may create only their
atomically linked action or decision WorkItems through the existing Project
command boundary. Source/freshness, stale, partial and unavailable truth stay
explicit.

Local validation passes TypeScript typecheck, the full frontend lint chain,
`103/103` affected unit tests, `3/3` P9-02 functional E2E tests and `3/3`
governed English/Simplified-Chinese/Traditional-Chinese visual tests. The
i18n audit covers 8,982 literal English sources with 100% `zh` and `zh-TW`
coverage. The three regenerated snapshots were inspected at their governed
viewports and scales after correcting table separation and translated primary
button width. Production compilation succeeds; the final local brand step
correctly stops on a user-owned untracked `frontend/public` asset that remains
untouched and excluded, so clean-tree exact-SHA CI is the authoritative full
build proof.

P9-02D is now limited to the exact frontend checkpoint ordinary CI, the
planned disposable-Site normal/fault/security proof, Level 2 and one final
diagnostics-off Level 3. No production ERPNext connection is needed or
authorized.

Frontend checkpoint `07d42c8cc12479ca4ab9844f7ec501d728166b16`
ordinary CI `33675136726` then exposed one bounded frontend batch: invalid
dialog ARIA on the native search input, aggregate statement coverage at
79.67%, and inactive navigation colour drift in existing Shell snapshots.
The single repair removes the invalid attributes, restores the prior inactive
colour without disabling the new routes, and adds real filter, response,
search, notification, retry, read and preference coverage. Local lint,
typecheck, `1,115/1,115` units, 80.01% statements and `10/10` affected
functional/accessibility E2E pass. No CI workflow, threshold, existing visual
baseline, contract or ownership rule changes.

Repair SHA `6fdf8cba91d7c552f60d99b11b5b845be57ef592` ordinary CI
`33678023797` then passed repository, secret, frontend verification and E2E
shard 1. Its remaining 19 visual failures were all the same Portfolio inactive
colour assertion, while E2E shard 2 retained the pre-P9-02 six-command count
and old Project index. The complete final batch normalizes Portfolio's inactive
legacy colour and updates that existing keyboard test for the approved nine
commands and current Project index. No visual baseline or product behavior is
rewritten.

## Test and evidence plan

- Pure domain and contract tests for filters, cursors, KPI calculation,
  availability, source/freshness labels, idempotency and meeting lineage.
- Repository/API security tests for member/admin boundaries, row filtering,
  direct-object lookup denial, critical-notification subscription rules, CSRF,
  actor, optimistic version and audit.
- Fault tests for empty data, stale ERP projections, provider unavailable,
  partial source availability, scheduler retry, duplicate delivery, conflict,
  timeout-after-commit and notification failure without fake success.
- Frontend unit and E2E tests for loading, empty, no permission, read-only,
  unavailable, stale, partial and retryable states; keyboard/focus and
  non-colour status expression.
- Governed English, `zh` and `zh-TW` screenshots at the established viewport
  and scale matrix, with literal-English source and complete catalog coverage.
- Changed-files-to-tests mapping, exact-path task verification, ordinary CI
  and final diagnostics-off Level 3 including the cumulative disposable Site.

## Rollback

Before product implementation, revert only the P9-02 audit/plan transition to
accepted CI-OPT-02 checkpoint `ea6112fa`. After product implementation, disable
new routes and scheduler hooks, preserve immutable meeting/notification/audit
history, and use a reviewed forward fix. No ERPNext, production database or
external-state rollback is part of this task.
