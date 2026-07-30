# P5-01 Frontend and Runtime-Ready Checkpoint

Recorded: `2026-07-30T15:09:42Z`

Starting synchronized checkpoint:
`9198dc9c54d314c9927ff5aa68ce17253f6f4afe`

Task:
`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Result:

`IN_PROGRESS CHECKPOINT — FRONTEND/BROWSER/STATIC RUNTIME PASS; CONTROLLED
FRAPPE SITE PROOF PENDING`

This is not the P5-01 Level 2 Task Gate, does not mark any requirement
complete and does not activate P5-02.

## Delivered vertical slice

- Added one strict browser data source for the retained Project-scoped
  document list, detail, create, lease, revision, capability and binary
  content contracts. Closed response parsing rejects additive or malformed
  success data.
- Added a dense Project Documents workspace showing the exact document,
  policy, immutable revision, File Revision/hash/scan, typed relationship,
  lock history and external-provider truth.
- Added create, checkout, check-in, administrative recovery and multipart
  revision interactions over the existing BFF. The multipart client does not
  claim browser-owned MIME, size, hash, privacy, scan, release, actor, tenant,
  File identity or URL truth.
- Added reauthorized URL-free native preview/download. A binary response is
  accepted only with exact private/no-store, sandbox CSP, no-referrer,
  nosniff, content-disposition, length and MIME headers; the browser receives
  a transient Blob and no stable private URL.
- Replaced the prototype route-dirty assumption with registered workspace
  dirty state shared by App navigation, Project tabs, browser history and
  `beforeunload`. Cancel preserves input and restores focus.
- Covered normal, empty, loading, no-policy, read-only, unavailable,
  malformed response, conflict, processing, retryable/final error and
  provider-unavailable truth without optimistic success.
- Added only literal-English sources plus direct `zh` and `zh-TW`
  translations. `PDM` remains the retained technical abbreviation; ordinary
  interface language is fully translated.
- Added a fail-closed controlled-Site verifier for the exact nine retained
  DocTypes, two additive/idempotent migrations, disposable synthetic
  policy/Project/document identities, exact CSRF/idempotency/replay,
  immutable revision/private File Revision, live pending-to-clean scanner
  observation, binary integrity, locks, typed relationships, audit traces,
  Guest/IDOR denial and route-disable recovery.

No production policy, role mapping, scanner/provider, external connector,
CAD/PDM, sharing, review/release, baseline, EBOM, ERPNext connection,
dependency or schema was added.

## Requirement → code → test → evidence

| Requirement | Code | Tests and evidence |
|---|---|---|
| `FR-DS-001` | `frontend/src/api/document-data-source.ts`; `frontend/src/pages/project-document-workspace.tsx` | strict data-source units; live workspace browser normal/empty/read-only/error states; three-language visuals |
| `FR-DS-003` | retained document domain/repository plus live revision/file workspace | retained `63/63`; document data-source and workspace units; controlled-Site verifier ready |
| `FR-DS-004` | retained relationships plus typed relationship UI | retained backend/contract checks; browser exact relationship truth; controlled-Site typed query |
| `FR-DS-007` | registered dirty state in `workspace-navigation.ts`, `app.tsx` and Project tabs | App/navigation units; real App dirty-guard browser case |
| `FR-DS-008` | retained lock commands plus workspace checkout/check-in/recovery | retained repository/API checks; workspace units; controlled-Site lock/audit lane ready |
| `FR-DS-009` | retained URL-free capabilities plus strict Blob response path | HTTP/data-source units; native-preview browser case; controlled-Site binary integrity lane ready |
| `FR-DS-014` | explicit unavailable external/CAD/PDM capability presentation | workspace units and trilingual browser truth; no connector activation |

## Changed files → affected tests

| Changed boundary | Affected verification |
|---|---|
| strict HTTP/FormData/Blob handling | `api-and-telemetry.test.ts`; `document-data-source.test.ts`; complete frontend unit coverage |
| document data source and workspace | `document-data-source.test.ts`; `project-document-workspace.test.tsx`; Project workspace units; P5-01 browser suite |
| App/Project dirty navigation | shell/page/workspace units; real App dirty-guard browser case |
| translations/generated catalog/styles | generated check; ESLint/Prettier/Stylelint/boundary/UI/i18n; build; three exact visual cases |
| controlled runtime shell/verifier | `test_phase5_document_runtime_verifier`; retained Phase 4 runtime safety/verifier suites; R1 runtime contract suites |

## Passing evidence

- P5-01 retained backend/domain/DocType/repository/API/contract:
  `68/68` after adding the five verifier contract tests.
- Shared runtime safety and retained Phase 4/R1 verifier regression:
  `85/85`.
- Affected frontend unit group:
  `124/124`.
- Complete frontend unit coverage:
  `658/658` in `32/32` files.
- Coverage:
  statements `83.23%`, branches `81.43%`, functions `86.46%`, lines
  `85.25%`.
- Generated artifacts, TypeScript, affected ESLint, Prettier, Stylelint,
  module boundaries and industrial UI static audit:
  `PASS`.
- Frappe-compatible i18n:
  `2,860` literal-English sources with direct `100%` `zh` and `100%`
  `zh-TW` coverage.
- Production frontend build and display-brand guard:
  `PASS`.
- P5-01 non-visual browser:
  `6/6`.
- P5-01 exact zero-tolerance visual comparison:
  `3/3` for English `1366×768@100%`, Simplified Chinese
  `1440×900@125%` and Traditional Chinese `1920×1080@150%`.
- Original-resolution industrial/accessibility/mixed-language/overflow
  inspection:
  `PASS`.
- `git diff --check`:
  `PASS`.
- The preceding controller-only checkpoint passed CI `#75`, run
  `30550637406`.

## CI #76 diagnosis and bounded repair

Recorded: `2026-07-30T15:50:30Z`

The product checkpoint `e687ede91c5d95860a019f5a57c9b04e63466614`
was pushed and CI `#76`, run `30556235620`, exercised the complete
repository and governed visual jobs. Two evidence defects were found; neither
was accepted as a product PASS:

- The repository job reached the prohibited-pattern scan after the Python,
  frontend, coverage, build, brand and audit checks passed. A verifier unit
  test contained the exact forbidden source token as its negative assertion,
  so the repository scanner correctly failed closed. The test now constructs
  that negative token without embedding the scanner pattern. Its `5/5`
  affected tests pass and the exact repository scan returns no match.
- Adding the retained document translations changed the generated catalog
  version from `82a93beb772c049c` to `f36f17fab18f412b`. The six retained
  R1-05 visual cases passed; all eighteen governed R1-06 P0 cases failed
  because that version is visible in the footer.

The failed visual artifact `8764951776` was downloaded in full and verified
against GitHub's digest:
`94536ac05da25aa38a00612f9dd92aabcc6adc350d0cab6270e9dac3a6cf386a`.
It contained exactly eighteen actual and eighteen diff images. All actuals
were `1440×900`. Pixel comparison against the retained Linux baselines found
the primary changed bounds only in the catalog footer text
(`x=496/560..677`, `y=882..892`), with `771..786` changed pixels per image.
The English Trial actual also contained twenty one-level RGB
anti-aliasing pixels at bottom control corners. The eighteen verified actuals
were promoted as one governed Linux baseline set; the exact baseline
inventory/dimension verifier, its `7/7` unit tests, the affected runtime
verifier `5/5`, reconciliation verifier, prohibited-pattern scan and
`git diff --check` pass locally.

This bounded repair remains pending a fresh fixed-runner CI result. It does
not change P5-01 completion state or substitute for the controlled-Site
proof below.

### CI #77 dirty-guard regression repair

Recorded: `2026-07-30T16:05:10Z`

Checkpoint `b89600281e5487b6d7869dd5571d0bfa5ec841e3` passed the
fixed-Linux governed visual job and the repository's complete
`scripts/verify.sh` in CI `#77`, run `30558847983`. The later complete
non-visual Playwright run found one real regression: the P5 App integration
had made the existing discard-unsaved-changes review executable without a
reason, while the retained browser-history contract still required one.
The run failed `1/285`; the remaining `284/285` cases passed. Secret and
history scans did not run after that failure.

The App now retains the Impact Review default that requires a reason. The
existing App unit test and new P5 Project-tab browser test both assert that
the discard command is disabled before a reason and enabled only after one
is supplied. The affected unit file passes `31/31`; both affected browser
cases pass `2/2` and then `10/10` across five repetitions. TypeScript,
affected ESLint, affected Prettier and `git diff --check` pass. This repair
is pending a new complete CI run and does not relax or skip the retained
high-risk interaction contract.

### CI #78 history-scan repair

CI `#78`, run `30559919155`, passed the fixed-Linux governed visuals,
complete `scripts/verify.sh`, all `285/285` non-visual Playwright cases and
the current-tree gitleaks scan. Its final full PR-history scan found one
`generic-api-key` false positive introduced by the P5 checkpoint:
`npi_p5_01_routes_disabled`, the internal boolean route-disable key used by
the fixed disposable Frappe runtime shell. It contains no credential and
cannot authenticate to any service.

Because the introducing commit is already shared, history was not rewritten.
The exact commit/file/rule/line fingerprint is added to `.gitleaksignore`.
The repository's closed fingerprint verifier and its negative unit matrix
are updated to require exactly this reviewed entry together with the three
previously reviewed synthetic fingerprints. Path-only entries, wildcard
lines, comments, blanks and unreviewed additional fingerprints remain
rejected. This forward-only repair is pending a new complete CI run.

### Complete CI checkpoint and controlled-Site channel

CI `#79`, run `30560612349`, passed on exact remote head
`86f3fde02303a5088c5ec4d4be906efcdb83c96d`. Both jobs and every declared
step completed:

- repository: complete `verify-dev-config`, `scripts/verify.sh`, `285/285`
  non-visual Playwright, current-tree gitleaks and complete PR-history
  gitleaks;
- visual: exact fixed-Linux governed matrix and bounded artifact upload.

This closes the three bounded CI repair loops without weakening a Gate,
rewriting history or including unrelated local changes. It is reusable
frontend/browser/static/security evidence but still does not replace the real
controlled-Site proof.

The current host has no Docker or fixed Bench. The existing CI workflow now
adds a manual-only `document_runtime` job so the next proof can run on a
fresh ephemeral GitHub runner. It installs only the exact toolchain-pinned
Bench and uv versions, requires the runner-provided Yarn to equal the exact
pinned version, initializes the repository's pinned Frappe commit and fixed
disposable `npi.localhost` Site, then runs the unchanged `--document-only`
command. The job records only non-secret result metadata, uploads it for 30
days and removes only its own ephemeral Compose volumes. It has read-only
repository permissions, contains no production hostname or secret binding
and does not alter the normal pull-request CI path.

The first dispatch, run `30562284484`, reached the exact remote SHA and failed
before Bench initialization, Site creation, Compose startup or database
writes. npm 11 correctly rejected Yarn's package preinstall script because
the generic `--strict-allow-scripts` invocation had no package-specific
allowlist. The repair removes that unnecessary global install: the hosted
runner already reported Yarn `1.22.22`, and the job now fails closed unless
Bench, uv and Yarn each report the exact repository-pinned version. No script
allowlist or runtime Gate was weakened.

The second dispatch, run `30563106063`, again used the exact remote SHA.
Both pinned Python packages installed successfully and the runner again
reported Yarn `1.22.22`, but one silent CLI rendering comparison returned
nonzero before initialization. Distribution metadata, rather than a CLI's
presentation string, is the canonical installed-package version source. The
second bounded repair therefore compares exact `frappe-bench` and `uv`
versions through Python package metadata, retains the exact Yarn CLI version
check, and still fails closed before initialization on any mismatch.

The third dispatch, run `30564025523`, passed exact tool verification and
pinned Frappe Bench initialization, started only the guarded disposable
MariaDB/Redis services, passed the controlled database identity guard and
created the fresh `npi.localhost` Frappe Site. It then failed before NPI app
installation or the document verifier because the pinned Bench generated
`sites/apps.txt` without a terminal newline and the first app append produced
the invalid registry token `frappenpi_core`. Cleanup stopped and removed both
containers, both new volumes and the runner-local network. The bounded repair
adds only a checked line boundary before an app-name append; it rejects a
missing or symlinked registry and does not delete, replace or reinterpret
existing app entries.

The app-registry repair checkpoint
`5dfb99df923ed112ea4eae2ea1b8019ec723d953` passed normal CI run
`30564533440`, including the complete repository, `285/285` browser,
fixed-Linux visual and both secret lanes. Manual run `30565065165` then
passed exact tool and pinned Bench setup, created the guarded disposable
Site, installed both NPI apps, ran the Site migration during initialization
and entered the unchanged document verifier. Its second migration also
completed before the schema fixture correctly failed closed: the verifier
still required an obsolete `response_payload` field even though the
authoritative DocType, repository, controller and metadata tests consistently
use the sealed `response_snapshot` plus `response_sealed` pair. Cleanup
removed both containers, both new volumes and the runner-local network. The
bounded repair aligns only that verifier inventory with the existing sealed
idempotency contract and adds a regression assertion; it does not change the
DocType, database or business behavior.

The schema-inventory repair checkpoint
`56e1b75d6b34fd000df34d0ab70016d9163143f4` passed normal CI run
`30565607707`. Manual run `30566120000` passed the corrected schema fixture,
both migrations and all guarded setup boundaries. The next real command,
synthetic Project creation, returned HTTP `422` because the fixture supplied
non-email owner `Administrator`; the retained Project command requires a
canonical email owner. Cleanup again removed both containers, both volumes
and the runner-local network.

## Controlled-Site proof blocked after five repair rounds

The required command is:

```text
bash scripts/verify-frappe-runtime.sh --document-only
```

On the current local host it failed closed before migration or fixture writes
because the fixed physical repository Bench does not exist. The repository
preflight then confirmed that this host has no Docker CLI, Docker daemon or
Compose v2. No production Site or external integration was contacted.

The five complete genuine rounds and root cause are retained in
`implementation/evidence/phase-5/p5-01-controlled-runtime-blocker.md`.
Because the necessary Gate still fails after the fifth round, the controller
requires `BLOCKED_EXTERNAL`.

The single user action required is:

`Explicitly authorize one additional bounded P5-01 controlled-runtime repair round beyond the five-round limit.`

Until then, no sixth repair or dispatch is permitted. P5-01 and all seven
requirements remain incomplete, and P5-02 remains inactive.

## Rollback and recovery

Before retained P5-01 business history exists, revert the bounded P5-01
frontend/runtime-ready checkpoint. Once controlled document history exists,
disable only the tested P5 document route switch, preserve document, File
Revision, lock, audit and idempotency history, and deploy a reviewed forward
fix. Never delete or rewrite retained revisions or audit evidence.
