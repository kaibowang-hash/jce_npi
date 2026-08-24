# P8-05 Checkpoint 4 — Tool Asset Execution Inspector

Recorded: `2026-08-24`

Status: `IMPLEMENTED — AWAITS EXACT-SHA ORDINARY CI`

## Authorized predecessor

- Exact checkpoint 3 SHA:
  `17406118f2a771644c90ca00272a247f40b1b5b7`.
- Ordinary CI `32667224305` passes repository `97262446049`, frontend
  `97262445982`, secret `97262446040` and governed visual `97262446007`;
  controlled lanes correctly skip.
- This checkpoint changes no command, worker, adapter, target transport,
  transaction, permission, schema ownership or production configuration.

## Implemented boundary

- The Tool Asset detail read model now returns bounded attempts, aggregate and
  five-field result truth, mapping observation, exact current mapping and
  permission facts only after Project/tenant/source/hash containment checks.
- Result and observation views never expose formal Asset identifiers. The
  current formal Asset identifier/version is projected only when an
  authenticated `authoritative_sandbox` success, the exact current mapping
  head and a fresh permitted P8-01 Asset projection all agree.
- The existing Tooling acceptance/Asset workspace gains a compact, square,
  neutral Tool Asset execution inspector. It separates NPI acceptance evidence
  from business approval, displays aggregate and per-field truth, and retains
  exactly one visible primary `Impact Review` action for the applicable fixed
  create or update command.
- Loading, empty, unavailable, no-permission, read-only, conflict, queued,
  processing, Mock, synthetic, partial, failed, uncertain, authoritative and
  stale/mismatched states remain truthful. Retry, reconcile, submit, ERP
  approval, movement and maintenance controls are absent.
- Browser traffic is limited to fixed Project-first NPI BFF routes. Mock and
  disposable synthetic fixtures contain no formal Asset identifiers and make
  no target request.

## Localization, accessibility and visual governance

- Every new visible source is literal English through the existing `t()`
  adapter, with direct no-header `zh` and `zh-TW` catalog entries and generated
  catalog equality.
- Statuses use text plus icon/shape, the primary action keeps visible text,
  Impact Review owns acknowledgement, and keyboard/focus/accessibility tests
  cover the inspector without color-only meaning.
- Three canonical Linux/amd64 baselines cover English, Simplified Chinese and
  Traditional Chinese across `1366x768@125%` and `1920x1080@125/150%`.
  The inspector remains square, flat and dense; narrow effective width stacks
  Impact Review so the full primary action and field outcome phrases remain
  visible.

## Verification state

- Backend/controller affected suites pass `409/409`: Tool Asset `65/65`, P6
  acceptance `35/35`, retained P6 Tool Asset domain `4/4`, Item `146/146`,
  MBOM `126/126`, and current-task/reconciliation `33/33`.
- Focused frontend data-source/workspace tests pass `21/21`; the complete unit
  and coverage run passes `1,060/1,060` without changing the repository's
  thresholds. The complete non-visual browser run passes `454/454`; after the
  final strict P6 route fixture and authoritative-ID assertions, focused P6
  and P8-05 browser runs also pass `22/22` and `4/4`.
- The six affected canonical Linux/amd64 cases pass no-update verification
  twice consecutively. A clean, serial, exact-workflow Bookworm/x64 run with
  Node `24.18`, Playwright `1.61.1` and one worker passes the complete governed
  visual matrix `129/129` in `17.2m`.
- The P6-06 three-image change is an approved semantic composition migration:
  the existing acceptance/Asset context remains visible while the always-
  present default-disabled Tool Asset inspector and direct reason are added.
  A deterministic inspector scroll preserves the complete visible primary
  action at `1440x900@125%`; it changes no product behavior, baseline
  tolerance, threshold or Darwin evidence.
- Manual review confirms square neutral panels, dense tables, visible text and
  non-color status, one primary Impact Review action, retained prior context,
  no mixed language and usable `125%`/`150%` layouts. Only the authenticated,
  authoritative, exact-current P8-05 case shows the controlled fake formal
  identifier; synthetic, partial and all migrated P6 evidence show none.
- Localization audits cover `8,341` literal English sources with `100%` direct
  `zh` and `zh-TW` catalogs; TypeScript, generated-catalog, code/style/format,
  boundary, accessibility and zero-vulnerability audits pass.
- Current-task verification, reconciliation, changed Python compilation,
  JSON/YAML/Frappe-CSV parsing and `git diff --check` pass. Post-commit
  manifest simulation accepts exactly the authorized `32` task paths and
  rejects a thirty-third path.

Canonical Linux/amd64 SHA-256 evidence:

- P6-06 English: `04194f1cff8e05a86b06d45893756f7c8c59ed094a0a242880bddce155b29750`.
- P6-06 Simplified Chinese: `a6d398125f129126acce2556b3fd0e1f8e74a2ce3c847300cb0c183b763a0081`.
- P6-06 Traditional Chinese: `169dbbd09bf97a3ab6958fd3ff8421411b8ccce786df7240d7c03156f72b4403`.
- P8-05 authoritative Traditional Chinese: `6d3cf07ded6caf7965643930bc9967cc0b3c556d2aa21d868f8e467745a92e9b`.
- P8-05 partial Simplified Chinese: `8f6c272b7b045f9d4a091adc5b46ef75c0e789bc5e911edf23bc284f593179ee`.
- P8-05 synthetic English: `c3f5117bec0297d7dad20349760a9c5bee3b8b0fd0665be6ad15fdec8b7575f7`.

## Held scope

- No production ERPNext/JCE or Sandbox contact occurred.
- Actual ERPNext Asset method, fields, naming, Company, Category, Location,
  maintenance/depreciation, business-approval source and production mapping
  remain held.
- P8-06, P8-08/P8-09 and generic P8-07 retry/replay/reconciliation remain
  inactive. Final unchanged Level 3 remains closed until this checkpoint's
  exact-SHA ordinary CI passes.
