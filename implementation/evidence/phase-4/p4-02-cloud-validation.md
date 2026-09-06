# P4-02 Cloud validation checkpoint

Date: 2026-07-23  
Decision: `IN_PROGRESS — BROWSER EVIDENCE PENDING`

This checkpoint resumes the committed P4-02 implementation at remote HEAD
`ed348a0`. The remote head is a descendant of CLI checkpoint `53d7a5d`, and no
product implementation was repeated or rolled back.

## Changed files to affected tests

| Change surface | Affected checks |
|---|---|
| Project-work domain, repository, controllers, DocTypes, BFF and OpenAPI | Complete Python repository suite in `make verify`; committed disposable Frappe runtime evidence in `LAST_RUN.md` |
| Project-work data source, workspace, copy and styles | Frontend generation, TypeScript, lint, 205 unit/component tests, build and audit in `make verify`; non-visual and visual Playwright matrices |
| Shared literal catalog and `zh` / `zh-TW` CSV catalogs | Static extraction, placeholder parity, direct coverage and mixed-language audit in `make verify`; all 147 visual cases because the rendered catalog hash changed |
| Existing visual baselines | Forced regeneration, clean exact comparison at `maxDiffPixelRatio: 0`, then representative original-resolution `en`, `zh`, and `zh-TW` review |

## Cloud checks

| Command | Result |
|---|---|
| `git fetch origin codex/npi-v1.2-implementation` plus ancestry/status review | `PASS` — local and remote HEAD were `ed348a0`; checkpoint `53d7a5d` is an ancestor; initial worktree was clean |
| `npm --prefix frontend ci` under Node 18.20.8 / npm 10.8.2 | `PASS` — 432 packages installed; zero audit findings |
| `make verify` under Node 18.20.8 / npm 10.8.2 | `PASS` — 211 Python tests and 205 frontend tests; generation, type, lint, format, style, boundary, industrial UI, i18n, coverage, build and both npm audits passed; 1083 literal English sources have complete direct `zh` and `zh-TW` coverage |
| `npm --prefix frontend run test:e2e` | `ENVIRONMENT LIMITATION` — Playwright Chromium revision 1228 was not present; the run was stopped after reproducing only browser-launch failures |
| `cd frontend && npx playwright install chromium` | `ENVIRONMENT LIMITATION` — the Cloud network returned HTTP 403 for every official Playwright CDN attempt |

The failed launch generated no product-test result. Generated reports and
traces from that environment-only attempt were removed, and committed evidence
was restored before this checkpoint.

## Gate decision

P4-02 remains `IN_PROGRESS`. `make verify` is current and passing, but the
non-visual matrix, forced 147-case regeneration, exact clean comparison,
representative original-resolution trilingual review, and final independent
release-gate decision remain required. P4-03 is not activated. The committed
Codespaces/Frappe runtime evidence remains valid because this checkpoint
changes documentation only.
