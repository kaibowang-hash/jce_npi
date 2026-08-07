# P5-06 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-07T02:03:59Z`

Status:
`PASS — LEVEL 1 DOMAIN, CLOSED CONTRACT AND GUARDED METADATA`

Requirements:
`FR-PRN-001`, `FR-PRN-002`

Exact stable checkpoint:
`68a79fd2f1572bd4b15c42bc6e4f1d038c272ebc`

## Delivered boundary

- Added a pure versioned controlled-print registry domain with an exact
  published mapping resolver. Missing and ambiguous mappings fail closed;
  there is no language, Gate, source-state, format or version fallback.
- Added canonical immutable source, registry, print snapshot, private output
  and access-event values with independent SHA-256 identities, version-4 UUID
  identities, bounded source/template payloads and a URL-free public output.
- Added six additive DocTypes for registry roots and versions, immutable print
  snapshots, exact private output identity, append-only access history and
  actor/Project-bound command idempotency.
- Closed every metadata write behind an administrative-registry or NPI-command
  flag. Published mappings and controlled history are immutable and deletion
  is denied through the existing audited history guard.
- Added exact-parent validation across tenant, Project, registry version,
  snapshot, output and private local Frappe File identity. A snapshot requires
  one enabled, published and effective mapping whose exact source context,
  language, copy/delivery state, watermark and hashes match.
- Added closed capability/create/detail/content OpenAPI vocabulary and NPI-owned
  ownership rows without enabling a route, arbitrary DocType/template input,
  raw private URL or external integration.
- Added literal English sources and direct `zh`/`zh-TW` coverage. The generated
  React catalog contains `3,856` governed sources at 100% coverage.

## Deliberately unavailable

- No production Print Format, registry row, mapping, fixture or default is
  installed; registry roots default disabled and versions default draft.
- No live BFF route, source adapter, renderer, Frappe File write, UI action or
  synthetic Site setup exists in this checkpoint.
- Browser/device print, numbered copies, exact production forms, signers,
  retention and original/copy semantics remain unavailable under
  `DR-REC-003` and `DR-REC-004`.
- No ERPNext endpoint, credential, request, mutation or cross-database access
  was introduced. No package or external QR/rendering service was added.

## Local affected and regression evidence

- focused domain/metadata/contract: `20/20` PASS;
- all contract tests: `85/85` PASS;
- all metadata tests: `88/88` PASS;
- localization tests: `41/41` PASS;
- complete Python regression: `1,034/1,034` PASS;
- generated catalog check and i18n audit: PASS, `3,856` literal English
  sources, direct `100%` `zh` and `100%` `zh-TW`;
- OpenAPI/ownership YAML and all additive DocType JSON parsed successfully;
- prototype approval, P0 visual governance and V1.2 reconciliation verifiers:
  PASS;
- prohibited backend-pattern scan and `git diff --check`: PASS.

The local devcontainer verifier could not resolve the Microsoft registry from
the restricted desktop sandbox. This was environment-only: both exact-SHA
ordinary CI runs reached and passed the same online devcontainer verification,
and the final repository job passed the complete repository verification.

## Exact-SHA ordinary CI and bounded visual proof

Product commit `07111e35d2a50fe5a98674d8422f6f70b98b4287`
ran ordinary pull-request CI `31138842148`:

- repository `92744201653` passed complete repository verification, non-visual
  E2E, Gitleaks and the complete pull-request-history secret scan;
- controlled runtime `92744202228` correctly skipped; and
- visual `92744201698` passed `47/65` and failed only the eighteen durable P0
  screenshots. Every reported difference was the visible footer catalog
  fingerprint changing from `2ad33967abb8b251` to `8c614f1fb035060a` after
  the governed translation catalog grew. No component, state, density,
  permission, accessibility or layout change was present.

The stable Linux actuals from artifact `8979072126` were copied byte-for-byte
to only their eighteen matching Linux evidence images in isolated commit
`68a79fd`. No threshold, assertion, matrix member or PASS rule changed; all
user-owned Darwin screenshots remained untracked and untouched.

Final ordinary CI `31139557282` passed at exact stable checkpoint `68a79fd`:

- repository job `92746365839`: PASS, including complete E2E and both secret
  lanes;
- visual job `92746365786`: PASS, `65/65`;
- controlled runtime job `92746366536`: correctly skipped;
- visual artifact `8979344607`, digest
  `sha256:3aa906402ec918ed7c1903b10d8e0e410aa867d39ba1f5fe71feb5d187c5b67e`;
  and
- Gitleaks artifact `8979442055`, digest
  `sha256:afd2f6b41bc34dcb4cd2865190a53285081f3a6468d01bf58f9e42ca20b2462f`.

Local `HEAD`, the remote tracking ref and the run head are the same exact
checkpoint.

## Review and next checkpoint

This checkpoint establishes structure and invariants only. It does not claim
a working print flow or an approved production form. P5-06 remains in
progress. Autopilot next implements the exact server-owned source adapter and
registry repository, deterministic verification SVG, frozen-template render,
private File/output persistence, actor-bound idempotency/audit transaction and
closed BFF capability/detail/content behavior. A normal-user route remains
disabled until that checkpoint proves authorization-before-resolution,
one-time rendering and retained-byte reuse.
