# ADR-012: LaunchFlow display-brand adapter and supplied assets

Status: Accepted for the bounded LaunchFlow display brand

Date: 2026-07-25

Amended: 2026-07-25 — deferred `Core.png` / `JCE Core` registration under the
user-approved plan dated 2026-07-26; the R1-02 boundary remains unchanged.

## Context

The product currently uses stable internal names such as `npi_core`,
`/api/npi/v1` and NPI-owned DocType identities. Rewriting those identities
would create migration and contract risk without user value.

The user supplied `docs/Brand Asset/` and directed that its CSV and exact
assets be the only source for brand-related development. At this ADR's initial
acceptance, the folder contained:

- `Brand Asset Instruction.csv`;
- `Company LOGO.svg`;
- `Loading.svg`;
- `LaunchFlow Icon.svg`;
- `LaunchFlow-logo_Standard.svg`; and
- `LaunchFlow-logo_White.svg`.

After initial acceptance, the user supplied `Core.png`, added its CSV usage
rule and approved the `JCE Core` display name. That later input resolves
DR-REC-006 but is allocated to FR-BR-002/Phase 8/M7-09; it does not expand the
R1-02 LaunchFlow implementation boundary.

## Decision

1. Introduce one local display-brand configuration/adapter for user-facing
   LaunchFlow name and asset selection.
2. Use the supplied files unchanged and only in the CSV-authorized contexts:
   company logo in the website footer, Loading asset on blank entry/start/load
   surfaces, LaunchFlow icon as favicon and visual platform/source identity,
   standard logo on light backgrounds, and white logo on dark backgrounds.
3. Preserve translated accessible names, tooltips and alternative text even
   where a visible platform/source text label is replaced by the icon.
4. Preserve stable technical identities initially, including package/App
   names, DocType names, database identities, `/api/npi/v1` and integration
   system code `ERPNEXT`.
5. Do not derive a new product palette, redraw/modify a mark, use an unrelated
   company asset as an ERP/JCE icon, browse for substitute branding, or add a
   second design system.
6. Keep ERP/JCE runtime display identity unchanged during R1-02. The later
   approved `Core.png`/`JCE Core` input is registered now and activated only by
   FR-BR-002/Phase 8/M7-09; that allocation does not block LaunchFlow work.
7. Treat colors inside the unchanged supplied SVGs as a narrow brand-mark
   exception. They do not alter the industrial teal/neutral component tokens.
8. Use `Loading.svg` only for a blank entry/start/full-surface loading state,
   not as a routine inline spinner or decorative illustration.
9. Place `Company LOGO.svg` in the website footer on a neutral light surface
   that preserves the source asset's contrast. It is not a header mark,
   platform source icon, legal-name replacement, or ERP/JCE identity.

## Consequences

- The user-facing product can migrate to LaunchFlow without schema, API or
  integration churn.
- Brand paths and contexts become testable behind one adapter.
- Existing Siemens iX Classic Light layout and company-owned industrial UI
  tokens remain the visual system; the supplied assets provide identity, not
  component styling.
- Brand changes affect shared shell, favicon/loading/footer/source identity,
  localization catalogs and the affected trilingual visual matrix.

## Alternatives rejected

- Rename internal packages, routes and DocTypes immediately: unnecessary
  migration/compatibility risk.
- Reuse `Company LOGO.svg` as an ERP/JCE icon: contradicts its footer-only CSV
  scope.
- Invent or retrieve a JCE Core asset: contradicts the user's sole-source
  instruction. The subsequently supplied `Core.png` is the only approved
  Phase 8 source.
- Keep brand references scattered across pages: makes usage rules difficult to
  enforce and audit.

## Rollback

Before downstream branded history exists, revert the display adapter and asset
references while retaining the supplied source package. After branded outputs
exist, deploy a reviewed forward configuration change; do not rewrite
historical controlled snapshots or audit records.

No database or contract migration is introduced by this ADR.
