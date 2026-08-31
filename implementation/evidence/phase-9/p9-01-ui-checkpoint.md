# P9-01D Project Change Workspace and Release-Proof Checkpoint

Status: `GOVERNANCE FROZEN — EXACT-SHA ORDINARY CI PENDING`

## Accepted predecessor

P9-01C implementation exact SHA
`0c11b1f378b1c962b6d05739f3c1f3cad18ad389` passes ordinary CI
`33363140068`: visual `99398340139`, secret `99398340217`, frontend
`99398340305` and repository `99398340322` all pass. This accepts only the
default-disabled reliable Engineering Change seam; it does not activate a
production profile or authorize a production target call.

## Frozen product boundary

P9-01D adds one dense `Change Control` tab inside the existing live Project
workspace. It does not add a top-level route or navigation domain. The browser
uses only the existing LaunchFlow BFF:

- Project-first Engineering Change list/detail and version-locked create,
  revise, formal-observation-link and close commands from P9-01B;
- the exact implementation-summary request from P9-01C; and
- read-only P8-07 operation projections for inbound observation and outbound
  summary execution.

The workspace shows the current immutable revision, ERP-owned formal identity
and raw state, impact and affected-object matrices, implementation and
revalidation evidence, effectivity, dispositions, costs, closure evidence,
revision/event lineage and permissions. ERP observation fields remain
read-only. LaunchFlow-owned revisions keep exact predecessor version/hash,
CSRF, actor-bound idempotency and audit semantics. No browser calls ERPNext.

## Industrial UI and state matrix

The UI uses rectangular tabs, compact tables, one selected-row inspector,
stable toolbars and one contextual primary action. It must cover loading,
empty, no-permission, read-only, processing, current, drifted, unavailable,
validation, conflict, retryable and final-error states. All visible source
strings are literal English and must have direct Simplified and Traditional
Chinese translations. Keyboard, focus, labels, non-colour state expression,
overflow and WCAG checks are required together with three governed Linux
visual baselines.

## Runtime and release boundary

One fixed disposable-Site verifier must prove default-disabled routes, exact
Project/actor containment, create/revise/formal observation/close, signed
inbound intake, implementation-summary request and network-free execution,
sealed replay, route disable/recovery, log redaction and exact cleanup. It may
use only the existing synthetic runtime adapter and may never represent that
result as formal ERP success.

P9-01D completes only after focused and full repository/frontend/i18n/security
checks, nonvisual E2E, the three governed visuals, migration/rollback checks,
the cumulative Frappe runtime and the sole P9-01 Level 3 all pass. Production
profiles, credentials, ERP configuration and ERP data remain unchanged.

## Exact authorized files

The exact file manifest is `implementation/CURRENT_TASK.json`. Product edits
must not begin until this governance checkpoint's own exact-SHA ordinary CI
passes all repository, frontend, secret and governed visual lanes. User-owned
dirty documentation, local evidence and unrelated snapshots remain preserved.
