# P8-09 Validation — Approved JCE Core Display Identity

Date: 2026-08-31

Requirement: `FR-BR-002`

Result: **TECHNICAL PASS — PRESENTATION-ONLY IDENTITY; TECHNICAL CODE UNCHANGED**

## Delivered boundary

P8-09 presents the approved `JCE Core` identity only through the existing
display-brand adapter and `SourceSystemIdentity` seam. It emits the byte-exact
`docs/Brand Asset/Core.png` asset once in the production build and preserves
`ERPNEXT` as the technical value in API, event, schema, persistence,
permission, ownership and routing boundaries.

This task adds no DocType, row, patch, fixture, API, event, worker, external
request, target mapping, credential or production operation. It does not
rename ERPNext business semantics or claim Sandbox, UAT or production
acceptance.

## Exact checkpoints

| Checkpoint | Exact SHA | CI evidence |
|---|---|---|
| audit plan | `5c6793b3406ded8257b927ad89fbd9dba67bab4c` | ordinary `33333259174` PASS |
| activation | `f92f2a028905367868b16bdd748d477ffbadeb94` | ordinary `33334024759` PASS |
| test-manifest expansion | `66f5a3a95bb32e4cbdf0b9837c2dc5f5acb8aa24` | ordinary `33335381357` PASS |
| product | `f7f8dffe782c8fa6e2c4aea9620c112f03cabcd5` | ordinary `33336799864`; three authorized visual deltas only |
| visual-manifest expansion | `e3fad5647f6f9eae52938441676bd0037e054ba3` | ordinary `33337516645`; same three authorized deltas only |
| visual repair | `3bfeff8aa7b98e085feeeb7c5370455abf000973` | ordinary `33338620540` PASS |
| final predecessor diagnostic | `5505d215a42308b277a0e580832752420420aacc` | ordinary `33341193951`; controlled `33341711275` PASS success-zero |
| diagnostics off | `6235502363e34b1279a0c0e26d8d6aecbbd7811f` | ordinary `33342183499` PASS |
| final release Gate | `6235502363e34b1279a0c0e26d8d6aecbbd7811f` | Level 3 `33342817983` PASS |

The first Level 3 exposed only a later P8-03 Item migrated-legacy outer
boundary after all P8-09 presentation checks had passed. A product-zero,
exact-67 diagnostic subsequently passed with success-zero output, so no Item
product repair was evidenced. All nine Item diagnostic flags were disabled
before the authoritative final Gate.

## Product evidence

- approved display text: exact `JCE Core`;
- technical system code: exact `ERPNEXT`, unchanged;
- approved asset: `docs/Brand Asset/Core.png`;
- asset dimensions/mode: `7158 x 1486`, RGBA;
- asset SHA-256:
  `0c7182882022cf190925c90f0004c77aaca4dd513b86ccd0f23efb30171e0e42`;
- full unit/coverage checkpoint: `1086/1086`;
- nonvisual E2E checkpoint: `458/458`;
- governed Linux visual matrix: `135/135` after the exact three reviewed
  Tooling baseline updates;
- literal English sources: `8586`, with direct `100%` zh and zh-TW coverage;
- exact-one non-inline Core asset build emission and negative asset guards:
  PASS; and
- backend/integration-contract scan for display-name leakage into technical
  values: PASS.

## Final Level 3 evidence

Run `33342817983` at exact SHA
`6235502363e34b1279a0c0e26d8d6aecbbd7811f` passed:

- secret scan `99341406965`;
- frontend `99341406968`, including full E2E;
- governed visual `99341406989`;
- repository `99341407027`;
- controlled preflight `99342574101`; and
- cumulative runtime `99342604163`, including fixed Bench/Site setup, runtime
  verification, result recording, artifact upload and cleanup.

Artifacts are provenance-bound by GitHub artifact metadata:

- runtime `9741314098`, SHA-256
  `def1200134b9b9509c6dfe7a4983d74fd272cf0c211df27b7b049f9fa65a37d9`;
- visual `9741125285`, SHA-256
  `0f7c5a428fef1a8e8a75f1c3bbc38dc2946c15d91c69b1fb73da8d8ab9c7ddb3`;
  and
- secret scan `9741066445`, SHA-256
  `1462db6b87d1f89c6a66c8f29a0932f03f35fa8696aa8cb3f378002362382434`.

The preceding exact-SHA ordinary run `33342183499` also passed repository
`99339703987`, frontend `99339704058`, secret scan `99339704008` and governed
visual `99339703927`.

## Holds and rollback

P8-09 closes only the approved presentation seam. `DR-REC-009`, production
activation, Sandbox/UAT, target-specific mappings, business approval, the
final full production ERPNext↔LaunchFlow read-only compatibility
reconciliation, FR-CO-003/004 external portals and M9-04/M9-05 real-project
pilots remain held or explicitly deferred. Controlled non-production UAT is
still required and cannot be reported as a real pilot or real-user adoption.

Rollback removes only the Core adapter mapping, text mapping, translations
and presentation evidence. It never rewrites `ERPNEXT`, persisted data,
contracts, ownership or any external system.
