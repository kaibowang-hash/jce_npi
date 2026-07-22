# Phase 3 Visual Review

Review date: 2026-07-22

Technical visual outcome: **PASS**

Business usability sign-off: **PENDING**

The visual result applies to the Phase 3 industrial SPA prototype and its
explicit fixture states. It does not convert the unsigned business UAT or the
missing provenance-backed sanitized data into accepted evidence.

## Automated baseline result

`npm run test:visual:update` force-regenerated all 129 deterministic Chromium
screenshots with `--update-snapshots=all` and passed 129/129 in 4.3 minutes. A
subsequent clean comparison with `npm run test:visual` also passed 129/129 in
3.9 minutes at
`maxDiffPixelRatio: 0`, proving the checked baseline matches the final rendered
implementation rather than relying on update mode or a percentage tolerance.

The matrix contains:

- 18 locale views: six core screens in `en`, `zh`, and `zh-TW` at 1366x768;
- 30 geometry views: six screens at the required 1366x768 and 1920x1080
  desktop/125%/150% zoom-equivalent combinations;
- 78 state views: 13 non-normal states for each of the six core screens,
  including loading, empty, no-permission, read-only, partial, error, conflict,
  validation, queued, processing, retryable failure, final failure, and dirty;
- three 768x1024 field-tablet Trial views, one per locale.

Every visual case first checked its expected state surface, visible language
purity (including relevant attributes and open shadow roots), and absence of
document-level overflow. The 390x844 field-phone path is covered by the
non-visual interaction suite; it is not represented as a screenshot in this
129-image baseline.

## Manual representative review

Six regenerated files under
`frontend/tests/e2e/visual-matrix.spec.ts-snapshots/` were inspected at original
resolution. The sampled top bars show zero notifications and each sampled
status bar shows the current `12e5adf665b2cd30` fixture catalog version, which
also confirms that the superseded text-bearing baselines were not retained:

| Screenshot | Review focus | Finding |
|---|---|---|
| `locale-project-en-1366x768-100-linux.png` | English Project Cockpit and normal desktop hierarchy | Stable shell, compact object header, Gate track, engineering panels, one primary action, and docked inspector are visible without Desk chrome or a card wall |
| `locale-tooling-zh-1366x768-100-linux.png` | Simplified Chinese Tooling Cockpit | UI labels are localized; retained product terms, identifiers, units, and fixture business data remain distinguishable from UI copy; dense tree/table/inspector structure is preserved |
| `locale-execution-zh-TW-1366x768-100-linux.png` | Traditional Chinese execution and reconciliation | Queue, processing, partial/failure semantics remain textually distinct; ERPNext ownership and retry status are explicit and do not imply false completion |
| `geometry-project-1920x1080-150-linux.png` | Project page at the 1920x1080, 150% zoom-equivalent case | The actual 1280x720 raster retains the object identity, Gate track, blocker, actions, and inspector without document overflow |
| `state-gate-error-zh-1920x1080-100-linux.png` | Simplified Chinese terminal error state | The localized business error, retry action, trace identifier, and textual error state remain visible; severity colour is supplemental rather than the sole signal |
| `field-tablet-trial-zh-TW-768x1024-100-linux.png` | Traditional Chinese field-tablet Trial task | Trial identity, locked inputs, photo action, parameter table, and primary conclusion command remain available in the narrow engineering layout without horizontal document scrolling |

## Industrial UX findings

- **Palette:** neutral white/grey surfaces dominate. Industrial teal is the
  single non-semantic primary accent; success, warning, and danger colours are
  confined to small status marks, text, or low-saturation state surfaces. No
  competing decorative palette was observed.
- **Geometry:** ordinary panels, buttons, inputs, tabs, and table surfaces use
  square or 0-2 px geometry. The automated computed-style gate passed across
  all six core screens.
- **Shadow and boundary:** page hierarchy is carried by one-pixel borders,
  dividers, headers, selected rows, and status lines. No panel shadow, gradient,
  glass effect, floating pill navigation, or decorative illustration was
  observed.
- **Density and hierarchy:** the fixed application bar, rectangular domain
  navigation, compact headers/toolbars, trees, tables, split workspaces, and
  docked inspectors keep object identity, lifecycle state, blockers, source,
  and next action visible. The sampled normal pages do not substitute KPI card
  walls for engineering detail.
- **Action and status:** each sampled work context exposes one visual primary
  action. Status uses text plus icon/shape and, where applicable, colour.
  Error and ERP partial/failure states are explicit rather than optimistic.
- **Accessibility:** the final clean, standalone non-visual Playwright suite
  passed 63/63 in 2.6 minutes, including keyboard/focus,
  accessible-name/disclosure, 150% zoom-equivalent, and axe WCAG A/AA checks.
- **Language:** automated language scans passed all 129 cases. Manual review
  found no ordinary non-allowlisted English UI label in the sampled Chinese
  views and no Chinese UI copy in the sampled English view. Business data,
  codes, units, and approved retained terms are intentionally unchanged.

## Remaining acceptance boundaries

The screenshots use deterministic prototype fixtures, UTC, and the local
fallback/session model; they are not provenance-backed operational records.
They do not prove a live Worklist BFF, user/company timezone, notification
service, mail/print/export pipeline, telemetry endpoint, ERPNext deep link, or
target-system execution. The three required business representative reviews
and sanitized-data walkthroughs remain pending in `business-uat.md`.
