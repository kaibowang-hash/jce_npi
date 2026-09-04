# P6-08 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-09T20:32:10Z`

Status:
`PASS — TEN-VIEW DOMAIN, CONTROLLED PACKAGE RENDERING, CLOSED CONTRACT AND GUARDED METADATA`

Requirement: `UX-007`, supported by `FR-UX-007`, `FR-UX-025`,
`FR-UX-030`, `NFR-SEC-003` and `NFR-LOC-001`

Exact stable checkpoint:
`5b1560921eda850380d298d7b50375943d7a69e2`

Product and bounded repair commits:

- `cf86cad8f4d0ed5717b0bcede117ca9907beb091` — pure list/preference/export
  domains, deterministic renderer, closed contracts, guarded DocTypes and
  direct tests;
- `0b42ac0aadc599ae6f63d5ea656708528543923f` — complete static catalog source
  inventory for the new controlled values;
- `a76c8b3196a907f62fba0b7abcd2a6be15ec5822` — replace the retained Latin
  workbook-format word in Chinese source labels with complete Chinese; and
- `5b1560921eda850380d298d7b50375943d7a69e2` — promote only eighteen reviewed
  fixed-Linux catalog-footer actuals to their governed targets.

## Delivered boundary

- Added the exact ten code-owned Tooling views: `all`,
  `missing_applicability`, `single_part`, `shared_parts`,
  `missing_physical_set`, `single_physical_set`,
  `multiple_physical_sets`, `missing_design_revision`,
  `has_design_revision` and `customer_owned_set`.
- Added closed search, sort, direction and group vocabularies, deterministic
  result/query snapshots and exact selection references containing only
  `{toolingMasterGlobalId, snapshotHash}`. Selection and filtered modes are
  mutually exclusive, and every result is bounded to `1..100` Masters.
- Added per-actor/tenant/Project/view/grid-schema preferences. Required
  columns cannot be hidden, and the accepted fixed My Work preference route
  was not broadened.
- Added immutable package and actor-bound create/download receipt domains.
  The one-hour validity limit affects only download eligibility; it never
  rewrites package truth.
- Added deterministic standard-library ZIP rendering with exactly
  `manifest.json`, `tooling-objects.csv` and `README.txt`, fixed ordering and
  timestamp, a one-megabyte bound, UTF-8 BOM/CRLF CSV and leading-whitespace-
  aware `= + - @` formula neutralization.
- The manifest records stable keys and explicitly lists omitted raw File
  URL/content, workbook values, external customer/supplier identifiers,
  repair/custody/return text, cost, evidence and ERP/lifecycle truth.
- Added one preference, one immutable package and one actor-bound receipt
  guarded additive DocType, closed OpenAPI component schemas, exact ownership
  rows, operation/target receipt values and direct English/`zh`/`zh-TW`
  catalog coverage.

## Deliberately unavailable

- There is no P6-08 route, repository/BFF query, business row, private File,
  browser action, production ERPNext call or lifecycle command at checkpoint
  1.
- The schemas accept no caller-selected DocType, field list, raw filter
  expression, arbitrary member name or raw private URL.
- `System Manager` is frozen only as the future conservative transport-level
  export authority in addition to exact Project `VIEW`; it is not an approval,
  shared-view publisher, lifecycle or ERP authority.
- Shared Masters have not yet crossed a live repository boundary. Exact
  Project-relative containment, stale/IDOR denial, artifact persistence and
  download reauthorization remain checkpoint 2 work.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/export_domain.py` | ten exact views, closed query values, deterministic snapshots, preference invariants, mutually exclusive modes, `1..100` bounds, immutable one-hour package and actor-bound receipt rules in `test_phase6_tooling_export_domain.py` |
| `tooling/export_rendering.py` | exact members, deterministic bytes/hashes, language freeze, CSV BOM/CRLF, formula neutralization, omitted-field vocabulary and size bound in `test_phase6_tooling_export_rendering.py` |
| guarded DocTypes/controllers | exact fields/options/defaults, no generic export/print/delete and cumulative receipt operation/target values in `test_phase6_tooling_export_metadata.py` |
| OpenAPI and data ownership | closed additive schemas only, no live paths, exact ownership and absence of raw URL/ERP/lifecycle claims in the P6-08 contract/metadata suites |
| translation catalogs/generated catalog | generation and `5,638` literal English sources at complete direct `zh`/`zh-TW` coverage and mixed-language audit |
| fixed-Linux visual baselines | eighteen byte-for-byte reviewed catalog-footer actuals; complete final `91/91` matrix |

## Local and exact-SHA CI evidence

Local affected evidence passed:

- direct P6-08 domain/rendering/metadata suites: `17/17`;
- related localization/contracts: `99/99`, followed by focused repair checks
  at `58/58` and `10/10`;
- catalog generation, YAML parse, Python compile, V1.2 reconciliation, P0
  visual governance and `git diff --check`: PASS; and
- i18n audit: `5,638` literal English sources with 100% direct `zh`/`zh-TW`
  coverage.

The serial ordinary-CI evidence isolates every repair without weakening a
Requirement, route, authority, schema, test, matrix, threshold or PASS rule:

1. Run `31333165745` at `cf86cad` failed before product tests because the
   new Select options were not all static catalog sources.
2. Run `31333331309` at `0b42ac0` passed all `1,381` Python tests, then failed
   only the mixed-language `XLSX` source label and eighteen P0 footer
   fingerprints. Visual artifact `9043598943`, digest
   `sha256:c8d0c1581254eb27df3724fd77886c95badfeb6b1b516c4cdff68c71b0b390b8`,
   retained the candidates.
3. Run `31333560139` at `a76c8b3` passed repository job `93295544700`; visual
   job `93295544644` remained `73/91` only because the direct translation
   changed the catalog digest. Artifact `9043672316`, digest
   `sha256:aad9eb75cdcfc59a89ed92269e9b2d8713aac8a2c99dc90381c8bf299a544761`,
   retained all actual/diff pairs. Pixel audit found zero changed pixels above
   `y=860`; ordinary English changes were confined to
   `x=559..676, y=882..891`, Chinese to `x=496..613, y=882..891`. The known trial-image
   lower-right antialiasing remained below threshold and outside business UI.
4. Baseline-only commit `5b15609` copied exactly those eighteen CI actuals to
   their Linux targets and changed no source component or visual rule.

Final ordinary CI `31334024291` passes exact stable checkpoint `5b15609`:

- repository job `93296765481`: PASS in `9m33s` — `1,381/1,381` tracked
  Python tests, `796/796` frontend unit tests in `50` files, `343/343`
  non-visual E2E, `5,638` direct trilingual sources at 100% `zh`/`zh-TW`,
  zero dependency vulnerabilities and both current/history Gitleaks lanes;
- visual job `93296765409`: PASS — `91/91` fixed-Linux cases;
- controlled runtime job `93296765721`: correctly skipped;
- visual artifact `9043803661`, digest
  `sha256:bfd63a8c9b79be26aee8e650d11dbaabba48732246de4e9eb5286a4efa85086e`;
  and
- Gitleaks artifact `9043879733`.

## Review, rollback and next checkpoint

Task Diff Review confirms that checkpoint 1 is additive, creates no business
row or File and activates no route. Before retained rows, rollback may remove
the additive foundation; after activation, use a reviewed forward repair and
disable only the independent P6-08 routes while retaining immutable package,
receipt, File and audit truth.

Checkpoint 1 is PASS. P6-08 remains in progress. Autopilot next implements
only checkpoint 2: independently default-closed Project-first Tooling list,
preference, package-create and package-download BFF routes; stable server
paging/query snapshots; exact shared-Master containment; conservative
`System Manager` plus Project `VIEW` export authorization; single-transaction
private artifact/hash/audit/receipt persistence; creator-bound one-hour POST
download; and permission, IDOR, replay, stale, expiry, formula, redaction and
hash tests. The live SPA, controlled Site, production ERPNext and any
Tooling/lifecycle authority remain inactive.
