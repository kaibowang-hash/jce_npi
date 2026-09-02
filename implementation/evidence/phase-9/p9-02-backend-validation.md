# P9-02A/B Backend and P9-02C Frontend Validation

Recorded: `2026-09-03`

Status: `P9-02C CI BATCH REPAIR LOCAL PASS — PENDING EXACT-SHA ORDINARY CI`

The accepted P9-02 audit/plan checkpoint is
`4123eb86c930c9c091cfb18a67a37ae9552fdd04`, ordinary CI run
`33662703332`.

The backend candidate implements only the frozen read-only reporting and
internal collaboration seams: permission-filtered global search and Project
portfolio, fixed KPI definitions with explicit availability, a read-only
operation-specific configuration catalog, immutable meeting minutes linked
atomically to Project WorkItems, and recipient-scoped idempotent internal
notifications. It retains source, version, actor, audit, deterministic paging
and no-fake-success semantics.

Validation:

- Full repository verifier: `2,883 passed`.
- Focused reporting, collaboration, Phase 4 compatibility, task-manifest and
  reconciliation tests: `135 passed`.
- Direct SQL forbidden-pattern scan: zero matches after removing the literal
  scanner token from its own metadata test.
- `TODO`/`FIXME` scan: zero matches in the P9-02 implementation.
- `git diff --check`: PASS.

The first backend-candidate ordinary run `33669485519` confirmed repository
and secret lanes, then all frontend lanes stopped at the same pre-server
catalog check. The cause was one batch of new Frappe metadata/error source
strings missing from both Chinese catalogs, plus nine reporting labels that
are not yet literal frontend sources. The repair adds every currently required
metadata/error translation, removes only those not-yet-used labels, regenerates
the React catalogs, and replaces unapproved Latin format abbreviations with
complete Chinese wording. Generated-catalog check, 8,863-source i18n audit at
100% `zh`/`zh-TW` coverage, TypeScript typecheck and diff check all pass.

No production ERPNext connection, credential, endpoint, business value or
external write was used. User-owned dirty documentation, local evidence,
screenshots, public assets and developer files remain excluded.

## Accepted backend catalog repair

Exact SHA `2432144515e8b632ee2a50bf717c2a6e919c2bf2` passes complete ordinary
CI `33669976985`: repository `100380878712`, secret `100380878741`, frontend
verification `100380878336`, E2E shards `100380878683`/`100380878742`, visual
`100380878555` and frontend aggregate `100382821023` all succeed.

## Frontend candidate

The exact frozen P9-02C paths implement live permission-filtered global
search, recipient-only notifications, one Project Portfolio/KPI/read-only
administration workspace and immutable Project meeting minutes. Direct object
routes reject prefix collisions and protocol-relative values. ERP values stay
read-only, source-labelled and explicitly stale, partial or unavailable; the
administration surface exposes no generic writer.

Local affected verification:

- TypeScript typecheck and the complete frontend lint chain: PASS.
- Data-source, component, shell, route and Project integration units:
  `103/103` PASS.
- Functional P9-02 Playwright scenarios: `3/3` PASS.
- Governed English, Simplified Chinese and Traditional Chinese visuals:
  `3/3` PASS and manually inspected.
- i18n: 8,982 literal English sources, 100% `zh`/`zh-TW` coverage.
- Production compilation and brand unit guard: PASS before the final static
  tree check; that check stops only on a pre-existing user-owned untracked
  `frontend/public` asset. It is neither staged nor modified, and clean-tree
  exact-SHA CI remains the authoritative complete build proof.
- `git diff --check`: PASS.

The one observed E2E failure was test orchestration only: two local Playwright
commands were started concurrently against port 4173. Serial rerun passed all
three functional scenarios without a product change. No production ERPNext
connection or external write occurred.

## Frontend exact-SHA ordinary CI batch repair

Frontend checkpoint `07d42c8cc12479ca4ab9844f7ec501d728166b16`
was pushed unchanged, then ordinary CI `33675136726` passed repository
(`2,883` tests) and secret scanning but failed the frontend lanes for three
fully identified causes in the same batch:

- the native search input carried dialog-only `aria-expanded` and
  `aria-haspopup` attributes, producing the same `aria-allowed-attr` failure
  across both nonvisual E2E shards;
- the new frontend paths reduced aggregate statement coverage from the frozen
  80% floor to 79.67%; and
- making Portfolio, Analytics and Administration navigable changed only their
  inactive navigation text/icon colour in pre-existing full-Shell snapshots.

The batch repair removes the invalid input attributes while retaining the
labelled results dialog, restores the exact legacy inactive navigation colour
without disabling any new route, and adds behavioral coverage for all search
result kinds, unavailable/short search, recipient notification variants,
read marking, preference save/retry, the complete frozen reporting filter set,
deterministic cursor use and malformed response rejection. No threshold,
workflow, snapshot or product contract is weakened.

Local batch proof:

- complete frontend lint/typecheck: PASS; i18n remains 8,982 literal English
  sources with 100% `zh`/`zh-TW` coverage;
- all 73 frontend unit files pass `1,115/1,115`; statement coverage is 80.01%,
  branches 79.82%, functions 82.17% and lines 82.57%;
- the three P9-02 functional scenarios plus all seven display-brand/Shell
  accessibility scenarios pass `10/10`;
- the CI visual diff was inspected and confined to the three newly enabled
  inactive navigation entries; the repair applies their exact prior colour,
  keeps active-route styling and preserves navigation behavior; and
- `git diff --check`: PASS.

Production ERPNext was not contacted. The next action is one exact-SHA
ordinary CI for this complete repair batch, followed automatically by P9-02D
disposable runtime, Level 2 and the sole final Level 3.
