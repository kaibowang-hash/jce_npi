# P5-03 Baseline and Impact Invalidation Validation

Recorded: `2026-08-05T09:14:10Z`

Status:
`PASS — LEVEL 2 BASELINE AND IMPACT INVALIDATION TASK GATE`

Requirement:
`FR-DS-006` (`TECHNICAL_VERIFIED`)

Product checkpoint:
`302b1e90d3561b57d6815dca186e5c33bcb8e693`

Complete ordinary CI:
[`30990594281`](https://github.com/kaibowang-hash/jce_npi/actions/runs/30990594281)
(`PASS`, exact product SHA)

Final unchanged controlled-Site Gate:
[`30991177478`](https://github.com/kaibowang-hash/jce_npi/actions/runs/30991177478)
(`PASS`, exact product SHA, diagnostic activation closed)

## Delivered vertical slice

- Added one independent Project-scoped publish-once baseline-policy authority;
  no Project owner, RACI assignment, `System Manager`, transport role or UI
  visibility is treated as business authority.
- Added immutable baseline and ordered member history that server-resolves an
  exact currently released Document Revision, its release event/snapshot and
  complete live private File Revision/hash/size/MIME/scanner-owned `clean`
  evidence. A caller cannot supply a mutable URL, `latest`, storage identity or
  scan truth.
- Added actor-bound create-command idempotency, payload conflict detection,
  exact response replay and the frozen receipt -> baseline -> member -> audit
  -> response -> receipt-seal transaction order.
- Added strict Project BFF/OpenAPI list/create operations and a separate
  fail-closed P5-03 route switch; normal users never use generic DocType CRUD
  or Frappe Desk as the product flow.
- Added `release_baseline` through the existing exact Gate-evidence command.
  The same transaction creates one explicit dependency per exact member; it
  does not infer a production dependency matrix.
- Added deterministic append-only old/new successor impact lineage. Only a
  registered predecessor can affect the exact Gate. Existing Gate Review
  invalidation, immutable prior decisions and successor cycles remain the sole
  review/resolution mechanism.
- Added dense Project Documents and Gate Review workspace presentation for
  immutable packages and visible successor impact, including honest
  permission, unavailable, stale/conflict, processing and failure behavior.
- Added literal-English sources and direct Simplified/Traditional Chinese
  catalogs through the accepted Frappe v15 CSV and local React `t()` chain.

No production G2/G5/G6/ECN package policy, baseline authority, automatic
dependency matrix, replacement/effectivity/retention rule, CAD/PDM connector,
EBOM, Item/MBOM publication, ERPNext execution or production credential was
installed or inferred.

## Controlled-runtime convergence

The historical diagnostic and blocker evidence remains append-only. The final
recovery continued from the exact remote branch rather than rewriting it:

1. The response-contract predicate checkpoint `9d25e50` passed affected
   `168/168` but its first ordinary CI was red. The bounded CI root was closed
   by the audited transitive dependency update in `10472ec`; later ordinary
   PR runs are green without lowering the audit criterion.
2. The single authorized closed baseline-create diagnostic sequence isolated
   the exact retained member release-snapshot binding. Repair `fe76938`
   compares the released lifecycle event with the release snapshot, removes
   the diagnostic activation and changes no public contract, permission,
   ownership, lock, version, audit, idempotency or transaction order.
3. The unchanged Gate then advanced to exact Gate-evidence attachment. The
   closed evidence-attach diagnostic isolated Frappe Datetime rehydration at
   dependency reconstruction; `1df0b60` normalizes only that persistence
   adapter boundary while retaining canonical UTC API/domain text.
4. `5729ee3` corrected only the synthetic successor lock-version precondition.
   `302b1e9` corrected only cross-process verifier replay selection so it uses
   the exact released baseline member revision rather than the first revision
   in successor history. These verifier/fixture corrections do not change a
   product requirement or PASS criterion.

Every repair checkpoint first passed ordinary PR CI. The final exact-SHA
ordinary CI `30990594281` passed, followed by the unchanged controlled-Site
workflow `30991177478`.

## Level 2 verification

### Local affected checks

| Boundary | Command/result |
|---|---|
| baseline, Document, Gate evidence/review, contract, permission and runtime modules | `python3 -m unittest -v` over the 18 affected tracked modules — `233/233 PASS` |
| affected React data sources and workspaces | `npm run test:unit --` five affected files — `162/162 PASS` |
| Frappe-compatible translation chain | `npm run lint:i18n` — extractor `7/7 PASS`; `3,232` literal-English sources; direct `zh` and `zh-TW` coverage `100%` |
| reconciled trace integrity | `python3 scripts/verify_v1_2_reconciliation.py` and `tests.test_v1_2_reconciliation` — script PASS and `17/17 PASS` before the truthful completion-state update |
| task diff | `git diff --check f088d70..302b1e9` — PASS |

The workstation exposes `python3` rather than a `python` alias; the initial
alias attempt did not execute a test and the same bounded commands passed with
`python3`. This is not a product, CI or controlled-runtime failure.

### Exact-SHA complete ordinary CI

Run `30990594281` passed all repository and fixed-Linux visual jobs on
`302b1e9`, including:

- development configuration, JSON and Python compilation;
- complete repository verification, full frontend generation/type/lint/unit/
  coverage/build/brand and both npm audit scopes;
- complete non-visual browser E2E;
- governed fixed-Linux visual evidence; and
- current-tree plus complete pull-request-history secret scans.

The ordinary pull-request event correctly skipped the controlled-Site job.

### Final unchanged controlled-Site Gate

Run `30991177478` matched exact SHA `302b1e9`. Its repository, non-visual E2E,
security and visual jobs passed. The controlled job passed:

- exact Bench/uv/Yarn tool verification;
- the pinned Frappe commit and disposable Site/database guards;
- installation and two migrations of both NPI Apps;
- baseline creation, sealed replay/conflict, exact Gate attachment,
  dependency registration, registered and unregistered successors, impact
  lineage, Gate Review invalidation/successor resolution, route disable/
  recovery, cross-process exact-revision replay and bounded cleanup; and
- the PASS-only artifact record.

Artifact `8924223239` is
`p5-document-runtime-30991177478` (`348` bytes). Its extracted `result.txt`
has SHA-256
`6038ab3371de189330b8046e16315b19dc1f41ee8165e1da2fbfd6f2aac37153`
and records `result=PASS`, exact head SHA `302b1e9`, run `30991177478`, the
fixed disposable runtime marker and the unchanged document-runtime command.

## Requirement, domain, permission and security review

- `FR-DS-006` is satisfied for the approved generic technical scope: exact
  released revision/File/hash packages are immutable, exact Gate references
  register dependencies explicitly, and successor impact preserves baseline,
  evidence and prior decision history.
- Baseline identity, policy lifecycle, create command, deterministic hashes,
  member/event invariants, actor-bound replay/conflict, concurrency locks,
  audit and delete guards are explicit. Published/released history cannot be
  overwritten or deleted through a normal path.
- Authorization precedes protected resolution. Guest, external, unrelated
  Project/tenant and unbound actors fail closed without receiving protected
  object detail. Baseline authority and Gate-evidence authority remain
  independent server decisions.
- There is no core patch, unrestricted `ignore_permissions`, direct SQL,
  cross-database access, generic browser CRUD, raw private URL, external
  request, production secret, destructive migration, TODO/stub or fake
  success.
- Additive DocTypes and repeated migrations are proven on the disposable Site.
  After retained history exists, rollback is a reviewed forward fix plus the
  P5-03 route switch; baselines, members, dependencies, impacts, reviews,
  audits and receipts are never deleted or rewritten.

## UX, accessibility and i18n review

The exact Linux Gate passed the affected English/Simplified Chinese/
Traditional Chinese browser and visual cases, including:

- `p5-03-document-baseline-en-1366x768-100`;
- `p5-03-document-baseline-zh-1440x900-125`;
- `p5-03-document-baseline-zh-TW-1920x1080-150`;
- `p5-03-gate-baseline-impact-en-1366x768-100`;
- `p5-03-gate-baseline-impact-zh-1440x900-125`; and
- `p5-03-gate-baseline-impact-zh-TW-1920x1080-150`.

Original-resolution manual review confirms neutral surfaces dominate, the
industrial teal is the only main accent, ordinary controls/panels are square
with one-pixel boundaries and no card-wall/gradient/strong-shadow treatment,
tables remain dense, the toolbar/inspector/status bar hierarchy is stable and
status uses text plus symbols rather than color alone. The 125% and 150%
cases retain the engineering context and scrollable table boundary.

All labels/actions are delivered through literal-English sources and direct
catalog entries. Chinese ordinary UI copy is translated; retained English in
the fixtures is limited to allowlisted product/engineering terms, identifiers,
user/email values and clearly synthetic business data. No new terminology
decision was made. Keyboard/focus, labels, non-hover access and accessibility
checks remain in the affected component/browser Gate.

## Changed-files to affected-tests

| Change boundary | Affected evidence |
|---|---|
| baseline domain, seven DocTypes and persistence adapters | baseline domain/metadata/Frappe/repository tests; controlled migrations/runtime |
| BFF/OpenAPI/ownership | Document API/contract and authorization-before-resolution tests |
| Gate evidence/dependency and Gate Review reuse | Gate template/evidence/review domain, repository, API, contract and runtime tests |
| successor impact atomicity | Document repository rollback/impact tests and complete controlled runtime |
| Project Documents and Gate UI | five affected frontend unit files plus P5-03 non-visual and six exact trilingual visual cases |
| catalogs | direct catalog audit, placeholders/terminology/mixed-language scan and trilingual browser evidence |
| runtime verifier/fixture-only corrections | runtime-verifier unit suite plus exact-SHA controlled Site |

## Task conclusion and next task

`PASS — LEVEL 2 P5-03`.

`FR-DS-006` advances to `TECHNICAL_VERIFIED`. Production baseline authority,
contents, completeness, retention/replacement and external connectors remain
explicit Class-B/scoped holds and are not overclaimed.

Phase 5 remains `IN_PROGRESS`. Standing automatic-transition authority
activates only `P5-04 — EBOM revision and comparison` at its
Requirement/domain audit for `FR-DS-011` and `FR-DS-012`. P5-05 and Phase 6
remain inactive.
