# R1-06 Requirement Anchor — Controlled undo, prototype gate and 1440 visual governance

Date: 2026-07-30
Branch: `codex/npi-v1.2-implementation`
Task: `R1-06 — Controlled undo prototype gate and 1440 visual governance`
Starting synchronized bridge checkpoint:
`373770f988b4cf7707b41a50e96b7a4861d93c3b`

## Authority

This anchor preserves the reconciled meanings in:

- `implementation/V1_2_DOCX_REQUIREMENTS.csv`;
- `implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv`;
- `implementation/REQUIREMENT_TRACEABILITY.csv`;
- `docs/V1_2_RECONCILIATION_ADDENDUM.md`;
- `docs/UX_INTERACTION_SPEC.md`;
- `design/UI_VISUAL_BASELINE.md`;
- `docs/LOCALIZATION_SPEC.md`; and
- `implementation/V1_2_RECONCILIATION_DECISIONS.md`.

It does not merge, renumber, narrow or replace a reconciled requirement.
Existing canonical mappings and earlier accepted technical evidence remain
append-only inputs.

## Exact reconciled requirements

| ID | Priority | Reconciled requirement | Acceptance | Existing canonical mapping | Starting trace |
|---|---|---|---|---|---|
| `UX-026` | P0 | 可逆操作：低风险误操作提供撤销；不可撤销动作必须明确说明后果与恢复路径。 | 批量状态变更可在限定时间撤销或通过审计恢复。 | None; `OTHER_ISOLATED_CASE` | `PLANNED_R1_06_CONTROLLED_UNDO` |
| `UX-030` | P0 | 原型验收：每个新模块先交付可点击原型或 Storybook 状态，再进入业务实现。 | 产品负责人批准原型和交互状态后才开发完整后端。 | None; `OTHER_ISOLATED_CASE` | `PLANNED_R1_06_PROTOTYPE_GATE` |
| `UX-035` | P0 | 工程信息密度：优先使用树表、高密度 Grid、固定列、分组、属性面板、快捷键和上下文菜单，保持经典工程软件的信息密度。 | 1440×900 下核心工作页无需滚动即可看到对象上下文、主要动作、工作列表和属性。 | `FR-UX-025`; `FR-UX-030` | `TECHNICAL_VERIFIED_FOUNDATION` |
| `UX-036` | P0 | 视觉回归：所有 P0 页面在 1440×900 和 1920×1080 建立英文、简体中文和繁体中文视觉回归基线。 | CI 保存三语言差异图；未经批准的布局、颜色、圆角和语言变化阻断合并。 | `FR-UX-026`; `FR-UX-036` | `PLANNED_R1_06_1440_VISUAL_MATRIX` |

The original acceptance text remains controlling. In particular, one bounded
low-risk preference slice cannot be reported as full proof of future business
bulk-status undo, and technical prototype tests cannot be reported as Product
Owner approval.

## Repository facts

1. The live My Work capability response currently returns
   `canRunBulkActions: false` with
   `bulk_action_contract_required`. No approved business bulk-status command,
   eligibility policy, irreversible boundary or recovery authority exists.
2. My Work already has one actor-bound, authenticated grid-preference
   resource and a visible `Reset grid layout` action over a closed view. The
   action changes only the current actor's presentation preference and is the
   narrowest existing low-risk candidate for the controlled-undo prototype.
3. The current preference contract has optimistic versioning and confirmed
   state recovery, but no durable undo command, expiry, consumption record or
   auditable before/after lineage. A client-only rollback or success toast
   would therefore be false.
4. The current P0 visual registry is the six-entry `coreScreens` collection in
   `frontend/tests/e2e/support.ts`: `work`, `project`, `gate`, `tooling`,
   `trial` and `execution`.
5. The existing deterministic visual matrix already preserves 1366×768 and
   1920×1080 evidence plus state, zoom and tablet cases. It does not require a
   complete six-page, three-language, 1440×900 matrix.
6. R1-04 already proves the affected live My Work density at 1440×900 in all
   three locales. That evidence remains reusable but does not by itself close
   all P0-page coverage under `UX-035` or `UX-036`.
7. The temporary R1-05 CI visual lane intentionally verifies only six affected
   R1-05 images. R1-06 must replace that temporary task scope with durable
   fail-closed governance while retaining the R1-05 images as accepted
   evidence.

## Bounded eligible prototype action

The only R1-06 timed-undo candidate is:

> Reset the current authenticated actor's layout for one closed My Work view
> to the code-owned default, then offer one bounded undo that restores the
> exact immediately preceding confirmed layout as a new confirmed preference
> version.

This is an implementation candidate, not a silently approved business policy.
Stage 1 must first produce a clickable trilingual prototype and exact state
contract. Stage 2 may add the command/API/schema only after an actual Product
Owner approval record exists.

Any eventual command must:

- derive tenant and actor from the authenticated session;
- use one fixed resource, grid, schema and closed view ID set;
- record exact before/after canonical layouts, hashes, preference versions,
  actor, request/trace identity, expiry and consumption truth;
- expose a bounded undo candidate only after the reset is server-confirmed;
- implement undo as a new authorized, idempotent server command rather than
  client state rewind;
- recheck actor, permission, expected current preference version/hash, expiry,
  consumption and downstream compatibility;
- restore the previous layout as a new preference version and append an audit
  event;
- reconcile uncertain, lost, conflicting or stale responses before displaying
  success; and
- expire without representing the current state as undone.

The prototype will use a finite repository-owned duration for demonstrating
available, countdown and expired states. The production duration remains part
of the Product Owner approval record and cannot be inferred from a fixture.

## Explicitly ineligible actions

R1-06 must never display a generic Undo for:

- Gate review decisions, approvals, waivers, reopen or invalidation;
- document/design release, publish, baseline or formal EBOM actions;
- registered File/Document Revision detach, delete, replacement or history
  mutation;
- Tooling, Trial, quality, change or Project lifecycle transitions;
- external execution submit, retry, replay, cancel or reconciliation;
- delete, cancel, void, destructive import rollback or retained-history
  mutation;
- shared-view publish or rollback while its authority policy is held;
- any action whose policy does not explicitly classify it as low-risk and
  reversible before an irreversible boundary; and
- every current My Work bulk action while
  `canRunBulkActions` remains false.

These paths require visible consequence copy and their already-authorized
forward-correction, new-revision, reopen, retry, reconciliation or support
path. Absence of an approved recovery command remains an explicit unavailable
state, never an invented link or optimistic success.

## Prototype-before-business-implementation gate

The R1-06 gate has two independent facts:

1. **Technical prototype evidence** — a clickable deterministic route, story
   or fixture covers normal, undo-available/countdown, processing, success,
   expired, conflict, denied and retryable/final error states in `en`, `zh`
   and `zh-TW`, with keyboard/focus/accessibility and industrial-layout
   evidence.
2. **Product Owner approval** — an externally owned, dated approval identifies
   the reviewed prototype revision, accepted eligible action, duration,
   consequence/recovery copy and state set.

Automated tests, screenshots, Codex review or a signed technical validation
cannot create fact 2. Until it exists, the complete backend/business command
stage is fail-closed and may not begin. Independent 1440 visual-governance work
continues because it does not depend on that product decision.

The durable governance rule must require future new business modules to link
their prototype revision, complete state inventory and actual Product Owner
approval before a task can enter full business implementation. A continuation
of an existing module records which newly introduced interaction was approved;
it does not reopen unaffected historical modules or treat a fixture as UAT.

## Visual-governance acceptance boundary

R1-06 adds, and does not replace, a machine-enforced visual contract:

- every registered P0 core screen has exact 1440×900, 100% zoom, normal-state
  baselines for `en`, `zh` and `zh-TW`;
- the P0 registry and expected 18-case cross-product are checked
  fail-closed, so adding a P0 screen without all three cases fails;
- each case verifies selected locale, direct translation purity, state
  readiness, no document-level overflow and exact zero-tolerance comparison;
- 1440 density assertions verify visible object context, one primary action,
  the work surface/list and applicable properties/inspector without
  document-level scrolling;
- existing 1366×768, 1920×1080, zoom, state and tablet cases remain in the
  complete visual matrix;
- CI runs in the repository's fixed-digest Linux renderer and uploads bounded
  Playwright reports/test results/diff images when the matrix fails; and
- baseline changes require a reviewed source change and original-resolution
  inspection. Renderer drift alone never authorizes unrelated bulk updates.

The matrix proves the current registered P0 contexts. Future P0 pages must join
the registry and cross-product before their task gate; R1-06 does not fabricate
not-yet-implemented Phase 5–9 pages.

## Scope

- Freeze the exact four reconciled requirements and trace targets.
- Deliver the bounded My Work reset/undo clickable prototype.
- Add a durable prototype-approval manifest/verifier that remains truthful
  when approval is pending.
- After real approval only, implement the fixed actor-bound reset/undo command
  vertical slice.
- Add the current six-page, three-language 1440×900 P0 visual matrix and
  fail-closed CI coverage/artifact rules.
- Run the R1-06 Level 2 Task Gate and the mandatory cumulative R1 shared
  Shell/design/i18n Level 3 exit Gate.

## Non-scope and scoped holds

- No business bulk-status command or claim that the bulk acceptance of
  `UX-026` is fully verified.
- No undo for any ineligible action or generic undo service.
- No Product Owner self-approval, representative-user UAT signature or
  production business-duration inference.
- No rewriting of unrelated historical visual baselines.
- No activation of R1-07 without `DR-REC-001`.
- No P5-01 continuation until R1-06 and the cumulative R1 exit Gate pass.
- No `Core.png` activation, ERPNext/JCE/CAD/PDM connection, production rule,
  external file behavior or pending Decision Request inference.

## Trace targets

- `UX-026`:
  `TECHNICAL_VERIFIED_FOUNDATION_BULK_POLICY_HELD` after the approved personal
  layout reset/undo command passes; before approval it remains
  `PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD`.
- `UX-030`:
  `TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD` while the durable gate
  and prototype evidence pass but the external Product Owner record remains
  unsigned; it can become `TECHNICAL_VERIFIED` only with the real approval
  evidence and enforcement proof.
- `UX-035`:
  retain `TECHNICAL_VERIFIED_FOUNDATION` until all current six registered P0
  contexts pass the explicit 1440 density assertions, then advance to
  `TECHNICAL_VERIFIED_CURRENT_P0_SCOPE`.
- `UX-036`:
  `TECHNICAL_VERIFIED_CURRENT_P0_SCOPE` after the fail-closed 18-case 1440
  cross-product, preserved 1920/legacy matrix, CI diff artifacts and review
  controls pass.

No trace status may imply future unimplemented P0 pages, a future bulk-status
policy, unsigned product approval or business UAT.
