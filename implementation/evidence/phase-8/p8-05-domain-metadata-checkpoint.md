# P8-05 Checkpoint 1 — Tool Asset Domain, Contracts and Guarded Metadata

Recorded: `2026-08-24`

Status: `IMPLEMENTED — AWAITS EXACT-SHA ORDINARY CI`

Frozen-plan transition SHA:
`937c5d72c29ec189f69ea5b2384eef64847698bf`

Frozen-plan ordinary CI: `32656436943` (`PASS`)

Jobs:

- secret scan `97235796099` — `PASS`;
- governed visual `97235796223` — `PASS`;
- frontend `97235796241` — `PASS`;
- repository `97235796253` — `PASS`; and
- controlled lanes skipped, as the transition contained no runtime behavior.

## Implemented boundary

Checkpoint 1 adds only behavior-free technical foundations:

- pure immutable `create_tool_asset` and `update_tool_asset` v2 source,
  business-approval reference, zero-or-one mapping expectation, profile,
  request, field-result, aggregate-result, fault and mapping-decision domains;
- a closed default-disabled profile configuration model. Mock and disposable
  synthetic modes are network-free; Sandbox requires explicit non-production
  HTTPS, host allowlist, secret reference and response authentication, and no
  profile is installed by default;
- additive closed request/result event schemas, OpenAPI components and field
  ownership declarations. No route or browser command is added;
- additive guarded metadata for request/idempotency v2, shared Outbox schema 3,
  stream guard, attempt, aggregate and field result, mapping observation and
  mapping head. No fixture, migration row, route, repository writer, enqueue,
  worker or adapter caller exists; and
- direct Frappe v15 English-source `zh` / `zh-TW` catalog coverage for every
  new label, Select value and translatable guarded validation message.

The retained P6 `create_or_update_tool_asset` v1 Mock preparation contract and
rows keep their existing operation/options and validators. Item Outbox schema
1 and MBOM Outbox schema 2 remain separate. The new Tool Asset branch is shared
Outbox schema 3 and cannot convert from either predecessor branch.

## Frozen truth and scoped holds

- One exact physical Tooling Set is the only mapping subject and maps to zero
  or one formal ERP Asset.
- Create requires exact unmapped expectation. Update requires exact current
  mapping version, formal Asset identity, target version and observation hash.
- NPI acceptance evidence remains distinct from business approval, ERP
  approval and Asset success.
- Partial and uncertain results remain durable truth and never advance formal
  mapping. Only an authenticated, authoritative, complete Sandbox result may
  produce an `advance` decision under exact compare-and-set.
- P8-01 remains the sole read-only Asset status/location/maintenance projection
  owner. No ERP-owned field becomes editable.
- Actual ERPNext Asset method, field, Company, Category, Location, naming,
  depreciation, maintenance, approval and service-scope mappings remain scoped
  Class B/C holds. No production ERPNext/JCE endpoint, credential, data or
  network contact occurs.

## Changed-files to affected-tests evidence

- execution domain and config -> `tests.test_phase8_tool_asset_domain`,
  `tests.test_phase8_tool_asset_config`;
- event/OpenAPI/ownership contracts ->
  `tests.test_phase8_tool_asset_contract`;
- guarded request/idempotency/Outbox/support DocTypes and translations ->
  `tests.test_phase8_tool_asset_metadata`;
- closed-boundary/no-route/no-worker/no-network assertions ->
  `tests.test_phase8_tool_asset_security`;
- predecessor compatibility -> `tests.test_phase6_tool_asset_request_domain`,
  `tests.test_phase6_tooling_acceptance_metadata`, all affected Item domain/
  config/contract/metadata/security tests and all affected MBOM domain/config/
  contract/metadata/security tests.

Final Level 1 results:

- checkpoint Tool Asset suites `28/28 PASS`;
- affected Item suites `146/146 PASS`;
- affected MBOM suites `126/126 PASS`;
- retained P6 Tool Asset/acceptance suites `30/30 PASS`;
- current-task and reconciliation units `33/33 PASS`, with both executable
  verifiers passing;
- generated catalog check and i18n audit `PASS`: `8,284` literal English
  sources have `100%` direct `zh` / `zh-TW` coverage, and all `7/7` catalog
  extractor governance tests pass;
- focused Python compilation `PASS`; `11` JSON documents, `3` YAML documents
  and both symmetric no-header CSV catalogs parse cleanly;
- post-commit manifest simulation `PASS`: exactly `51` task paths are allowed
  and there is no 52nd task path; and
- `git diff --check` `PASS`.

The Python Level 1 total is `363/363 PASS`. No test, threshold, permission,
contract, ownership or production boundary was weakened.

## Transition boundary

Checkpoint 2 remains closed until this checkpoint's exact product SHA passes
ordinary CI. It alone may introduce Project-first fixed list/detail/create/
update commands and atomic request + Outbox + audit behavior. Checkpoint 1 does
not authorize persistent business rows, command routes, worker, adapter,
network, UI, formal mapping or target activation.
