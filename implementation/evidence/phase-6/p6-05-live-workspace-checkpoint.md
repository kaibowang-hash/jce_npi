# P6-05 Live Engineering Controls Workspace Checkpoint

Recorded: `2026-08-08T20:19:57Z`

Status:
`PASS — LEVEL 1 LIVE WORKSPACE, I18N, ACCESSIBILITY AND VISUAL EVIDENCE`

Requirements:
`FR-TX-009`, `FR-TX-010`, `FR-TX-011`, `FR-TX-019`, `FR-TX-020`,
`FR-TL-009`, `FR-TL-010`, `FR-TL-017`, `FR-TL-018`

Exact stable checkpoint:
`1340f9b3f7167174277580c7aaedc9f9dcc97326`

Primary product checkpoint:
`aeb00bb91a099c9aa33bb9a0b39ebd4f54a3b88e`

## Delivered boundary

- Added a strict engineering-controls data source for the one read and three
  immutable append routes frozen at checkpoint 2. Closed parsers reject
  caller-supplied Trial Actual, approval, Gate, lifecycle, status and capacity
  result claims before protected data reaches the page.
- Added a dense selected-Tooling-Master workspace with distinct defect/action/
  verification lineage, Customer Standard / Trial Actual / Approved Baseline
  fact columns, versioned capacity inputs/results and a separate unavailable
  ERP/IoT health section.
- Exposed only server-returned defect, Customer Standard and capacity
  capabilities. Defect severity and explicit blocking intent remain separate;
  there is no Domain Work Item, Gate or Tooling lifecycle mutation.
- Kept Trial Actual exactly `not_measured`, Approved Process Baseline exactly
  `unavailable`, and shot-count/calibration/maintenance/health truth exactly
  unavailable. No copy, approve, target retry, ERP/IoT or maintenance action
  is rendered.
- Covered loading, empty, transport failure/retry, validation, conflict,
  processing, exact field ownership, invalid forms, read-only capability and
  successful defect/process/capacity command states.
- Added direct literal English source coverage and complete `zh`/`zh-TW`
  translations, keyboard/accessibility checks, six non-visual P6-05 browser
  cases and three fixed-Linux visual cases.

## Failure and repair history

Initial exact product run `31275192910` at `aeb00bb` did not pass and was not
represented as a checkpoint. Repository verification, `768` frontend unit
tests and coverage passed, but the complete non-visual browser matrix reported
three locale variants of one obsolete P6-01 assertion: it allowed only one or
two collection reads and did not admit the newly activated exact selected-
Master read. The visual job reported `29` expected differences: `26` existing
Tooling/P0 screenshots changed because the live Tooling tabs or catalog
fingerprint legitimately changed, and the three new P6-05 Linux baselines did
not yet exist.

Artifact `9026822983`, digest
`sha256:e948c50fd65c40d8565255f7bc0a653a570c7a8c011fb0c032d0101f2243dcee`,
retained the complete Playwright report, all changed existing actual/diff
pairs and the three new P6-05 actuals in report data. The three new English,
Simplified Chinese and Traditional Chinese engineering-control screens and
representative inherited Tooling/P0 candidates were inspected at original
resolution. The retained R1-06 differences were only `242–253` catalog-footer
pixels per screen.

Repair `1340f9b` separates collection and exact selected-Master requests,
requires one or two of each under React development execution, and still
permits only header-free GETs to those two exact paths. It copied only the `29`
reviewed CI actuals to their Linux targets and added the P6-05 baseline path to
artifact retention. It changed no production component, public contract,
threshold, visual tolerance, language requirement or governed test case.

## Changed-files -> affected-tests

| Change surface                                                    | Direct evidence                                                                                                                  |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| strict engineering-controls contract and data source              | four route/parser/envelope/invalid-success tests plus complete frontend type/lint verification                                   |
| dense engineering-controls workspace and live Tooling composition | eight component tests and six non-visual browser cases covering operational, capability, command, accessibility and error states |
| catalogs and industrial CSS                                       | complete i18n/mixed-language/UI audits plus three direct P6-05 visuals                                                           |
| P6-01/P6-02/shared P0 screenshots                                 | artifact-proved Linux actual/diff review and final complete zero-tolerance `85/85` matrix                                        |
| P6-01 live request observer                                       | three direct locale E2E cases plus final `332/332` non-visual matrix; only bounded collection/exact-Master GETs are accepted     |
| CI visual evidence path                                           | final successful upload contains the new P6-05 Linux baselines and complete governed report                                      |

## Exact-SHA ordinary CI

Ordinary CI `31276200829` passed exact stable checkpoint `1340f9b`:

- repository job `93150013305`: PASS — `1,243` tracked Python tests, `46`
  frontend test files and `768` unit tests, `332` non-visual E2E, `4,901`
  literal English sources at `100%` direct `zh`/`zh-TW`, statements `80.35%`,
  branches `79.68%`, functions `82.36%`, lines `82.54%`, zero dependency
  vulnerabilities and both secret lanes (`30` current commits and `275`
  complete pull-request branch commits);
- visual job `93150013277`: PASS — `85/85` fixed-Linux governed cases,
  including the three direct P6-05 screens;
- controlled runtime job `93150013750`: correctly skipped because checkpoint
  4 was not active at this SHA;
- visual artifact `9027099115`, digest
  `sha256:323537fcfddf051542bc055a13ff7b0af151fd41ca60cd28530f7c1046191ec8`;
  and
- Gitleaks artifact `9027167708`, digest
  `sha256:9d36b28461a12777c8a78e833d9a79354577fc55e183d686876f1e3b191d3d29`.

## Review, rollback and next checkpoint

No deterministic prototype value, Trial identity/actual, approval, Gate or
Tooling lifecycle command, ERP/IoT endpoint, credential, adapter, target
result, shot count, health score or maintenance advice entered the live route.
Rollback disables only `npi_p6_05_routes_disabled` and removes the live
composition while preserving every retained immutable defect/process/capacity
row, audit and receipt. It does not rewrite P6-01 through P6-04 history,
controlled Document/Gate truth, Trial/quality objects or any ERPNext object.

Checkpoint 3 is PASS. P6-05 remains in progress. Autopilot next implements
only checkpoint 4: cumulative disposable-Site defect succession/actions/
evidence/blocking, Customer Standard separation with absent actual/baseline,
capacity successor recomputation/bottleneck/gap, replay/conflict/rollback/
IDOR and independent P6-05 route disable/recovery, followed by complete
ordinary CI and the P6-05 Level 2 Task Gate.
