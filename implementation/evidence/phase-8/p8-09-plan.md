# P8-09 Plan — Approved JCE Core Display Identity

Status: **AUDIT PLAN PASS — CHECKPOINT-1 ACTIVATION AWAITS EXACT-SHA ORDINARY CI**

Audit date: 2026-08-31

Audit base: `45f6a4d5654608fa22c968d9b22e233b8af80852`

Predecessor product checkpoint:
`fc43c4aa5b876d98e9123977c6d5441ac088632a`

Requirement: `FR-BR-002`

P8-08 evidence base: diagnostics-off checkpoint
`1e0f3facfa31f382b469df4b8084a3c64231674b`, ordinary CI `33330200775`,
final Level 3 `33330886346`, governance closeout
`45f6a4d5654608fa22c968d9b22e233b8af80852` and ordinary CI
`33332397724`.

Product-code authorization: **false until this plan's exact-SHA ordinary CI
passes and a separate activation transition is committed and passes its own
exact-SHA ordinary CI**.

Audit-plan checkpoint: `5c6793b3406ded8257b927ad89fbd9dba67bab4c`

Audit-plan ordinary CI: `33333259174` (**PASS**) — repository
`99315542644`, governed visual `99315542679`, frontend `99315542699` and
secret `99315542712`; controlled lanes correctly skipped.

Checkpoint-1 product paths remain conditional on this separate activation
commit's exact-SHA ordinary PASS.

## 1. Audit conclusion

The approved source package already contains the only allowed ERP/JCE display
asset: `docs/Brand Asset/Core.png`. The file is a 7158 x 1486 RGBA PNG with
SHA-256
`0c7182882022cf190925c90f0004c77aaca4dd513b86ccd0f23efb30171e0e42`.
The package's CSV assigns it as the standard JCE Core/ERPNext logo and forbids
substitution. The approved display name is exactly `JCE Core`.

The frontend already centralizes LaunchFlow assets in
`frontend/src/ui-adapters/display-brand.tsx` and centralizes source-system
presentation in `SourceSystemIdentity`. The current brand verifier explicitly
holds `Core.png` out of production output. P8-09 therefore needs no new design
system, route, domain, API, schema, persistence, permission or integration
abstraction. The smallest implementation is to activate the exact PNG through
the existing adapter and use it from the existing source-system identity seam
when the stable value is `ERPNEXT`.

`ERPNEXT` is already widespread as a contract, schema, ownership, persistence
and routing value. Every such occurrence remains unchanged. Explanatory copy
that describes ERPNext product behavior is not bulk-renamed. P8-09 changes only
standalone ERP/JCE identity presentation: the exact logo is visible, and the
approved `JCE Core` name is the accessible/text fallback.

## 2. Frozen display contexts

| Context | Treatment |
|---|---|
| `SourceSystemIdentity` with technical value `ERPNEXT` | exact `Core.png`; accessible name and keyboard tooltip `JCE Core` |
| source badge and read-only editable-system identity using that primitive | reuse the same adapter output; no copied asset path |
| text-only source-system fallback | exact `JCE Core`; technical value remains `ERPNEXT` |
| API/event/schema/persistence/permission/routing values | unchanged `ERPNEXT`; never localized or mapped to the display name |
| explanatory sentences, acknowledgement strings and formal ERPNext product semantics | unchanged unless a later separately proved presentation requirement authorizes a specific literal |
| LaunchFlow wordmark, favicon, loading and company-footer contexts | unchanged existing five-SVG adapter behavior |

The PNG must remain byte-exact, non-inline and emitted exactly once by the
production build. It must not be copied to `public/`, converted, optimized,
cropped, recolored, redrawn or reconstructed. Its internal colors are a narrow
identity-mark exception and do not change industrial component tokens.

## 3. Accessibility, localization and surfaces

- `JCE Core` is a retained proper display name in English, Simplified Chinese
  and Traditional Chinese; no translated variant or mixed-language fallback is
  invented.
- The image has non-empty accessible text through the adapter and a keyboard-
  reachable tooltip wherever it replaces visible source text.
- Decorative rendering is prohibited for source/editable-system identity.
- The full supplied mark preserves aspect ratio, remains legible at compact
  source-badge scale and does not introduce document overflow at supported zoom.
- Visual evidence covers the real industrial light surface and a controlled
  neutral-dark contrast surface without introducing a dark theme or changing
  the supplied pixels.
- Missing, changed, duplicated or undecodable asset bytes fail the build/test
  boundary. There is no substitute icon, remote fetch, data URI or optimistic
  text/logo fallback.

## 4. Security and technical-identity invariants

- preserve every `ERPNEXT` enum/const in OpenAPI, event schemas, TypeScript and
  Python models, stored rows, permissions, ownership and adapter routing;
- introduce no endpoint, URL, host, credential, token, cookie, provider payload
  or production contact;
- create no browser-direct ERP access, generic DocType writer, target command,
  Inbox/Outbox row, replay, reconciliation or target-success assertion;
- keep image source selection centralized in the local display adapter;
- reject alternate filenames, byte hashes, inline/base64 payloads and duplicate
  production emissions; and
- preserve all user-owned dirty/untracked files and existing local assets.

## 5. Single implementation checkpoint

Only after this plan and a separate activation transition pass exact-SHA
ordinary CI, one bounded presentation checkpoint may:

1. register `Core.png` as the exact ERP/JCE identity asset in the existing
   display-brand adapter;
2. render it from `SourceSystemIdentity` only for stable `ERPNEXT` input;
3. return `JCE Core` from the text-only source-system display mapping;
4. register the retained term in the existing terminology/translation chain;
5. update the build verifier from deferred-Core rejection to exact-one approved
   Core emission while retaining all negative asset controls; and
6. add focused unit, direct-trilingual E2E, accessibility, scale/overflow and
   governed visual evidence.

The activation transition must enumerate exact product/test paths and every
actually affected tracked Linux visual baseline. Wildcards and blanket
snapshot authorization are prohibited. Eligible non-snapshot paths are:

- `contracts/terminology-allowlist.yaml`
- `apps/npi_core/npi_core/translations/zh.csv`
- `apps/npi_core/npi_core/translations/zh-TW.csv`
- `frontend/scripts/verify-display-brand.mjs`
- `frontend/src/components/primitives.tsx`
- `frontend/src/generated/catalogs.ts`
- `frontend/src/i18n/copy.ts`
- `frontend/src/styles/app.css`
- `frontend/src/ui-adapters/display-brand.tsx`
- `frontend/tests/e2e/display-brand.spec.ts`
- `frontend/tests/unit/display-brand.test.tsx`
- `frontend/tests/unit/formatters-and-copy.test.ts`
- this plan and the exact governance/controller paths frozen by activation.

The supplied `Core.png` source file is evidence, not a changed path. Any
additional page, contract, backend, asset or snapshot path requires a factual
stop and a separate exact manifest expansion before editing.

## 6. Verification map

| Changed area | Required evidence |
|---|---|
| adapter and asset build | exact filename/hash/dimensions, one direct non-inline reference, one byte-exact emitted file, decode succeeds, no alternate or duplicate |
| source identity primitive | `NPI_ONE` behavior unchanged; `ERPNEXT` produces Core mark with `JCE Core` accessible identity; `COMPUTED` remains text |
| stable technical identity | targeted scans and existing contract/data-source tests prove `ERPNEXT` values unchanged and `JCE Core` absent from technical contracts/backend |
| i18n | literal English source, direct zh/zh-TW retained-term rows, generated-catalog check, mixed-language scan |
| UX/a11y | keyboard tooltip, alt/accessible name, compact scale, light/dark contrast, no overflow, Axe and three-locale screenshots |
| regression | complete frontend unit/coverage, affected nonvisual E2E, governed visual matrix, repository/current-task/reconciliation and diff checks |

The product checkpoint must pass exact-SHA ordinary CI before exactly one
P8-09/Phase-8 final Level 3. The Level 3 uses only repository and fixed local
disposable-Site evidence; it must not contact production ERPNext/JCE.

## 7. Migration, rollback and holds

P8-09 has no database, DocType, patch, fixture, API, event or contract
migration. Before release, rollback removes only the Core adapter mapping and
restores the previous ERPNext presentation while retaining the supplied source
package. After branded outputs exist, rollback is a reviewed forward display
configuration repair; no historical record or technical identifier is
rewritten.

Production activation, P8-07F standing read-only access, `DR-REC-009`,
Sandbox/UAT, M9-04/M9-05 real pilots and the final full production
compatibility reconciliation remain separate holds. P8-09 authorizes no
external or production action and no product adjustment beyond this approved
display identity.

## 8. Explicit non-scope

- renaming `ERPNEXT`, API/event fields, routes, DocTypes, packages, ownership or
  permissions;
- changing explanatory business semantics or acknowledgement contract values;
- redesigning the Shell, source badges, integration UX or component system;
- adding a second theme, new palette, external image dependency or substitute
  brand asset;
- modifying ERPNext/Frappe core or production configuration;
- browser-direct ERP access, cross-database access, generic writers, dual-master
  fields or Mock/HTTP fake success; and
- any unrelated refactor, cleanup, optimization or user-owned worktree change.
