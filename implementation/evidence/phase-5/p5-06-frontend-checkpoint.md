# P5-06 Controlled Print Frontend Checkpoint

Recorded: `2026-08-07T09:16:14Z`

Status:
`PASS — LEVEL 1 FRONTEND AFFORDANCE AND VISUAL EVIDENCE`

Requirements:
`FR-PRN-001`, `FR-PRN-002`

Exact visual checkpoint:
`83ffafc16b247e8803b4e9874f80d34a6fa7d0f9`

## Delivered boundary

- Added a closed controlled-print data source for exact capability, create,
  detail and retained-content responses. It rejects unrecognized fields,
  unsafe content metadata and raw private File URLs.
- Added one compact, accessible Project-context controlled-print action and
  status surface without creating a second primary action. Loading, denied,
  read-only, unavailable-mapping, processing, replay, conflict, integrity
  failure and retained-download truth are explicit.
- The action remains visibly unavailable when no approved mapping resolves.
  The repository still contains no production source adapter, enabled mapping,
  Print Format, signer, copy-number policy or production default.
- All user-visible copy remains literal English source text with direct `zh`
  and `zh-TW` catalog entries through the existing Frappe-compatible chain.
  The compact action uses the repository icon adapter, translated accessible
  names, keyboard/focus behavior and a non-hover path.

## Findings closed before acceptance

The initial implementation at `d4e09e4` was not accepted as final evidence.
The bounded review found response-shape normalization gaps, an icon-policy
boundary and affected shared Project-document/EBOM visual fingerprints.
`08b12c2` repaired only those proven frontend/test-evidence findings without
changing the public API or product policy. `83ffafc` then sealed the exact
three governed P5-06 Linux baselines after original-resolution review.

No matrix member, pixel threshold, accessibility assertion, translation rule
or PASS criterion was removed or weakened.

## Verification

- Controlled-print data-source and action component unit tests pass, including
  strict response validation, unavailable/denied/read-only/error/replay and
  retained-download behavior.
- The complete frontend unit suite passes in the terminal Gate: `38` files,
  `719/719` tests.
- Complete non-visual browser verification passes `303/303` in the terminal
  Gate, including keyboard/focus and Axe WCAG A/AA checks.
- Direct catalog verification passes at `3,889` literal English sources with
  `100%` `zh` and `100%` `zh-TW` coverage.
- Fixed-Linux visual verification passes `68/68`, including:
  - `p5-06-controlled-print-en-1366x768-100`;
  - `p5-06-controlled-print-zh-1440x900-125`; and
  - `p5-06-controlled-print-zh-TW-1920x1080-150`.

The three cases preserve the square, dense industrial Project shell, neutral
surfaces, one restrained teal primary, text-plus-shape state expression and
usable boundaries at 125%/150% zoom. Ordinary Chinese copy is direct-catalog
translated; retained English is limited to approved technical terms,
identifiers and synthetic business data.

## Security and scope conclusion

The browser cannot select a DocType or Print Format, inject source/template
payload, controlled provenance, actor, watermark/copy truth or private File
identity. It cannot turn an unavailable capability into a create action.
Authorization and exact mapping resolution remain server-side.

Checkpoint 3 is PASS. This evidence authorizes only the controlled synthetic
Site proof and final task/Phase Gates. It does not activate a production form,
mapping, source adapter, signer, copy policy, external QR/rendering service,
dependency, ERPNext endpoint or credential.
