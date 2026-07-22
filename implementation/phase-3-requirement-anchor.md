# Phase 3 Requirement Anchor

Status: **TECHNICAL_PASS_PENDING_UAT — release-gated technical evidence complete; business review and provenance-backed sample data pending**
Baseline date: 2026-07-22
Machine execution baseline: repository V1.2 Execution Pack

## Current governing decision

The user's 2026-07-21 decision makes the repository V1.2 Execution Pack the sole machine-execution baseline for the current implementation. The V1.2 DOCX remains product background and a future reconciliation source only.

- Phase 3 scope and acceptance are exactly the Pack requirements assigned to Phase 3 in `implementation/REQUIREMENT_TRACEABILITY.csv`.
- DOCX/Pack phase names, requirement identifiers/counts, and screenshot-size differences do not block Pack-scoped work.
- DOCX-only requirements are recorded in `implementation/DOCX_PACK_DEVIATIONS.md`; they are not added to Phase 3 and may not enlarge its scope.
- Visual dimensions, screenshot evidence, and the test matrix follow the Pack's actual design, acceptance, implementation, and Skill files.
- Requirements from multiple sources must not be merged into a broader implicit requirement.
- Pack-internal material conflicts still block only the affected implementation.
  The stale requirement mappings and localization metadata identified during the
  Phase 3 re-read are normalized in this anchor and ADR-005; the remaining UAT,
  sample-data, and device-evidence limitations are recorded below without
  changing the approved execution scope.

This anchor was created before implementation. Phase 1.1 dynamic verification
subsequently passed on 2026-07-21. The Phase 3 shell, localization foundation,
and explicit prototype flows are implemented. The repaired repository,
frontend, migration, local-runtime, post-fix browser, exact visual, and manual
review gates passed. The release-gated technical result does not close the
business acceptance limitations in section 5.6.

## 1. Files actually read

The following repository sources were read for this anchor:

- Governance and state: `AGENTS.md`, `GOAL.md`, `README_FOR_CODEX.md`, `CHANGELOG_V1.2.md`, `implementation/PHASE_STATUS.yaml`, `implementation/REQUIREMENT_TRACEABILITY.csv`, `implementation/QUALITY_GATE.md`, `implementation/BLOCKERS.md`, `implementation/EXECUTION_PLAN.md`, `implementation/ROADMAP.md`, `implementation/backlog.yaml`, `implementation/DECISION_LOG.md`, `implementation/RISK_REGISTER.md`, `implementation/phase-0-gate.md`, `implementation/phase-1-gate.md`, `implementation/phase-1.1-gate.md`, and `implementation/phase-2-gate.md`.
- Formal V1.2 requirement source: the complete `docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`, extracted and read through its final paragraph, including its requirement annex.
- Pack product, architecture, domain, UX, localization, and acceptance sources: `docs/PRODUCT_SPEC.md`, `docs/DETAILED_REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md`, `docs/ERPNEXT_INTEGRATION.md`, `docs/TOOLING_AND_TRIAL.md`, `docs/UX_INTERACTION_SPEC.md`, `docs/LOCALIZATION_SPEC.md`, `docs/ACCEPTANCE_TESTS.md`, `docs/specification/SPEC_INDEX.md`, `docs/REPOSITORY_FACTS.md`, and the relevant files under `docs/reference/`.
- Visual and token sources: `design/UI_VISUAL_BASELINE.md`, `design/COMPONENT_USAGE.md`, `design/design-tokens.json`, and all five baseline images under `specs/ui/` (My Work, Project Cockpit, Tooling Cockpit, Trial Workspace, and ERP Execution Panel), including visual inspection.
- Contracts and localization sources: `contracts/data-ownership.yaml`, `contracts/terminology-allowlist.yaml`, the API/event/schema contracts relevant to the Pack, `localization/README.md`, and the Simplified/Traditional Chinese seed catalogs.
- Phase 3 review instructions: `.agents/skills/industrial-ux/SKILL.md`, `.agents/skills/frappe-i18n/SKILL.md`, and the Pack prompts relevant to UI, localization, and acceptance (`prompts/03_*`, `prompts/04_*`, and `prompts/05_*`).
- Approved decisions: every file under `docs/decisions/`.
- Repository history and current Git status were inspected. Unrelated concurrent
  work remains user-owned and outside this documentation normalization.

## 2. Phase 3 requirements currently assigned by the controller

The controller traceability file assigns the following **41** IDs to Phase 3.
The Pack-original source for `FR-UX-*` is `docs/DETAILED_REQUIREMENTS.md`
section 5.0; the four NFR rows come from section 9. The table deliberately does
not infer a DOCX identifier crosswalk.

| Requirement | Trace status | Authoritative Pack requirement | Delivered reusable implementation or screen fixture | Technical test / evidence and boundary |
|---|---|---|---|---|
| FR-UX-001 | `TECHNICAL_VERIFIED` | Independent NPI Web App; Desk is not the normal-user entry | App Shell and routes | Critical-path route tests never enter Desk |
| FR-UX-002 | `TECHNICAL_VERIFIED_PROTOTYPE` | Unified industrial shell, domain navigation, search, notifications, and environment identity | `AppShell`, navigation, environment marker | Shell navigation, search, and environment identity are proven; notifications expose an honest unavailable state only |
| FR-UX-003 | `TECHNICAL_VERIFIED` | Domain-first information architecture rather than DocType menus | Domain route/navigation model | Users find Project, Tooling, Design, Trial, and NPI work without DocType names |
| FR-UX-004 | `TECHNICAL_VERIFIED_PROTOTYPE` | Unified My Work queue | My Work screen fixture over shared Worklist | Fixture Worklist only; no live queue claim |
| FR-UX-005 | `TECHNICAL_VERIFIED_PROTOTYPE` | Project Cockpit with header, Gate track, next action, metrics, tree, and inspector | Project Cockpit screen fixture | Frequent-task and context-preservation tests use prototype Project data only |
| FR-UX-006 | `TECHNICAL_VERIFIED` | Core objects use Object Pages with anchors/tabs | Reusable Object Page and compact header | Project, Tooling, and Trial fixtures prove hierarchy and keyboard navigation |
| FR-UX-007 | `TECHNICAL_VERIFIED_PROTOTYPE` | Saved Worklist views, filters, sorting, grouping, columns, and server paging | Reusable Worklist/TreeTable | Fixture paging contract only; no live Worklist BFF claim |
| FR-UX-008 | `TECHNICAL_VERIFIED` | Split view and docked context inspector preserve context | Reusable split panes and `DockedInspector` | Selection, scroll, and return context survive detail work |
| FR-UX-009 | `TECHNICAL_VERIFIED` | One visual primary action; high-risk actions use an impact review | Command bar and `ImpactReview` | Primary-action audit and Gate/release/Trial/ERP review fixtures |
| FR-UX-010 | `TECHNICAL_VERIFIED_PROTOTYPE` | Show source, sync state, and editable system | `SourceBadge`, `SyncBadge`, field provenance | Prototype provenance only; no live ERPNext deep-link claim |
| FR-UX-011 | `TECHNICAL_VERIFIED_PROTOTYPE` | Distinguish NPI save/approval from ERP queue/completion/failure | `OperationStatus` and ERP execution fixture | Deterministic execution fixtures only; no target-system completion claim |
| FR-UX-012 | `TECHNICAL_VERIFIED_PROTOTYPE` | All remote operations expose durable async and retry states | Reusable operation state model | State fixtures are proven; no durable remote-operation backend claim |
| FR-UX-013 | `TECHNICAL_VERIFIED_PROTOTYPE` | Core pages cover empty, denied, read-only, error, conflict, and partial-data states | Shared page-state boundary plus per-screen scenarios | Deterministic scenario fixtures only |
| FR-UX-014 | `TECHNICAL_VERIFIED_PROTOTYPE` | Draft, dirty guard, field errors, and version conflict | Form-state and concurrency components | Conflict and field-error fixtures only; no live concurrency backend claim |
| FR-UX-015 | `TECHNICAL_VERIFIED` | Status uses text, icon/shape, and colour together | `SemanticStatus` | Non-colour status and accessible-name tests |
| FR-UX-016 | `TECHNICAL_VERIFIED_PROTOTYPE` | Desktop and field-tablet use, including photo/Trial actions | Responsive shell and Trial field fixture | Photo selection and action preparation only; no upload claim |
| FR-UX-017 | `TECHNICAL_VERIFIED` | Keyboard, focus, labels, and 150% zoom | Shared accessibility behaviours | Keyboard/focus/label/zoom checks across core fixtures |
| FR-UX-018 | `TECHNICAL_VERIFIED_PROTOTYPE` | Unified contextual activity timeline | `ActivityTimeline` in docked inspector | Fixture timeline only; no persisted activity claim |
| FR-UX-019 | `TECHNICAL_VERIFIED_FOUNDATION` | Browser uses aggregated BFF/domain APIs | Typed `/api/npi/v1` client and fixture transport | Session BFF and strict client boundary are proven; no live business ViewModel BFF |
| FR-UX-020 | `TECHNICAL_VERIFIED` | Third-party design system is isolated behind local adapters and company tokens | `frontend/src/ui-adapters/*` | Import-boundary and brand-asset scans |
| FR-UX-021 | `TECHNICAL_VERIFIED` | English-only source; Chinese comes from Frappe catalogs | Local `t()` and Frappe-backed catalog adapter | Literal-source extraction and shared-catalog/runtime tests |
| FR-UX-022 | `TECHNICAL_VERIFIED` | Siemens iX/classic engineering software is the sole UI reference | Shell, adapter, and tokenized styles | Industrial UX rules, exact 129-case comparison, and representative manual review passed |
| FR-UX-023 | `TECHNICAL_VERIFIED` | One industrial teal plus neutral surfaces | Token-generated styles | Palette-ratio and competing-accent audit |
| FR-UX-024 | `TECHNICAL_VERIFIED` | Ordinary radius is 0–2px; panels have no shadow | Token-generated geometry | Computed-style, token, and regenerated exact screenshot checks passed |
| FR-UX-025 | `TECHNICAL_VERIFIED` | Dense tables, trees, split panes, and docked inspectors | Shared layout primitives and screen fixtures | Desktop/zoom interaction and exact screenshot evidence passed |
| FR-UX-026 | `TECHNICAL_VERIFIED` | No non-allowlisted mixed UI language | Locale render and mixed-language scanners | Static and post-fix browser scans found no ordinary mixed-language residue |
| FR-UX-027 | `TECHNICAL_VERIFIED` | User copy only through `_()`, `__()`, or React `t()` | Translation wrappers and extractor | Static scan rejects unwrapped or non-literal display strings |
| FR-UX-028 | `TECHNICAL_VERIFIED` | Controlled terminology and retain abbreviations use the machine-readable glossary | Terminology validator | Unique approved translation and glossary-change checks |
| FR-UX-029 | `TECHNICAL_VERIFIED` | Context help explains terms, read-only fields, and blockers | Reusable contextual-help/explanation component | Read-only and blocked fixtures are understandable without developer docs |
| FR-UX-030 | `TECHNICAL_VERIFIED_PROTOTYPE` | Virtualization, progressive loading, and skeletons for large trees/tables | Worklist virtualization and skeleton primitives | Fixture 10,000-row bounded-DOM check only; no live-server performance claim |
| FR-UX-031 | `PENDING_BUSINESS_UAT_AND_SANITIZED_DATA` | Six realistic clickable golden paths with anonymized data and multi-role review | Six technical screen/flow fixtures and unsigned UAT package | Named business signatures and provenance-backed sanitized data are pending |
| FR-UX-032 | `TECHNICAL_VERIFIED_PROTOTYPE` | Privacy-safe usage metrics | Strictly allowlisted in-memory telemetry adapter | Privacy validation and prototype route views only; no live telemetry endpoint claim |
| FR-UX-033 | `TECHNICAL_VERIFIED` | Siemens iX Classic Light through a version-locked local adapter | Dependency lock, root theme attributes, UI adapter | Version/license/security/bundle record and adapter-boundary tests |
| FR-UX-034 | `TECHNICAL_VERIFIED` | Ordinary Tooling/Gate/Trial/Worklist/Workspace terms are translated in Chinese | Canonical catalogs and terminology mapping | Title/menu/button/field/help/error terminology scan |
| FR-UX-035 | `TECHNICAL_VERIFIED_FOUNDATION` | Locale follows persisted Frappe user language and one translation source | Locale BFF, catalog version, CSRF-protected preference update | Normal-user persistence is proven; non-screen renderers remain foundation only |
| FR-UX-036 | `TECHNICAL_VERIFIED` | English, Simplified Chinese, and Traditional Chinese with verified Frappe codes | `en`, `zh`, and `zh-TW` locale fixtures | Static/runtime coverage and final three-locale browser/visual runs passed |
| FR-UX-037 | `TECHNICAL_VERIFIED` | Third-party built-in labels also use the translation adapter | Adapter-supplied pagination/upload/validation/empty labels | Static and post-fix browser scans contain no third-party default English in Chinese |
| NFR-UX-001 | `TECHNICAL_VERIFIED_PROTOTYPE` | Role workbench plus required mobile/field actions | Role fixtures and responsive field layout | Responsive view and photo selection are proven; upload approval and persisted action update are not |
| NFR-LOC-001 | `TECHNICAL_VERIFIED_FOUNDATION` | Frappe-based localization covers UI, formats, notifications, mail, print, and export | Shared catalogs and locale formatters/renderers | UTC is deterministic prototype output; mail/print/export are renderers only |
| NFR-LOC-002 | `TECHNICAL_VERIFIED` | Core-page translation coverage is 100%; missing/mixed language blocks release | Coverage, placeholder/context, and mixed-language gates | 556/556 direct rows per Chinese locale with placeholder/context parity |
| NFR-UX-002 | `TECHNICAL_VERIFIED` | Design tokens are the sole style source; iX defaults cannot bypass them | Token build and adapter theme overrides | Static token, computed-style, and exact visual audits passed |

These are the exact trace qualifiers currently recorded for the 41 Phase 3
rows: 23 `TECHNICAL_VERIFIED`, 14 `TECHNICAL_VERIFIED_PROTOTYPE`, three
`TECHNICAL_VERIFIED_FOUNDATION`, and one
`PENDING_BUSINESS_UAT_AND_SANITIZED_DATA`. A prototype or foundation status
does not imply delivery of the corresponding live service.

The formal DOCX requirement annex contains requirement families that are absent from the current traceability CSV: `UX-001..UX-036`, `ARCH-001..ARCH-012`, `FR-TX-001..FR-TX-018`, `COD-001..COD-022`, and `I18N-001..I18N-007`. A machine extraction found 228 unique DOCX identifiers while the DOCX states 229 requirements, and the Pack traceability CSV has 173 rows. These counts and mappings must be reconciled before the table above can be treated as complete formal traceability.

## 3. Delivered Phase 3 implementation boundary

The implementation boundary is limited to the approved industrial React shell,
the local Siemens iX adapter, tokenized styling, the Frappe-backed localization
adapter/catalog pipeline, explicit prototype fixtures, and their tests.
Delivered files include:

- `frontend/package.json`, an approved lockfile, TypeScript/Vite/test configuration, and `frontend/index.html`;
- `frontend/src/main.tsx`, `frontend/src/app/*`, `frontend/src/ui-adapters/*`, `frontend/src/components/*`, `frontend/src/styles/*`, and `frontend/src/i18n/*`;
- canonical no-header Frappe CSV catalogs under the NPI app translation path,
  with `zh` and `zh-TW` validated against the pinned runtime and then exercised
  through a local development site;
- `frontend/tests/*` and narrowly scoped repository scripts for dependency-boundary, token, translation-coverage, mixed-language, accessibility, and visual checks.

This scope does **not** authorize Project, Tooling, Trial, Change, gate-decision, or ERP integration business logic. It also does not authorize new business DocTypes, fixtures presented as real data, production ERP access, or a change to the approved architecture.

## 4. Final technical evidence

The detailed results and limitations are recorded in
`implementation/evidence/phase-3/technical-test-results.md`,
`runtime-validation.md`, `dependency-review.md`, and `visual-review.md`.

- A lockfile-clean install, aggregate repository verification with 58 Python
  tests, full frontend verification with 110 unit/component tests, 92.96%
  statement/line coverage, production build, and both dependency audits passed.
- Static adapter/BFF boundaries, token geometry, restrained colour/shadow rules,
  one-primary-action behavior, strict BFF path/CSRF/error handling,
  privacy-safe telemetry validation, and literal/context-aware i18n extraction
  passed.
- The post-fix 63-test nonvisual Chromium run passed in 2.6 minutes, covering
  the six technical golden paths, deterministic state matrix, three-locale
  purity, WCAG A/AA scan, keyboard/focus, desktop/zoom, tablet, phone, and
  computed-style checks.
- All 129 rendered baselines were force-regenerated and passed in 4.3 minutes.
  A clean comparison then passed 129/129 at `maxDiffPixelRatio: 0` in 3.9
  minutes, and six representative images passed manual review at original
  resolution.
- The local Frappe runtime installed and migrated both apps and proved the
  normal-user locale, CSRF, error, no-store, trace, and cleanup contracts
  without contacting ERPNext or production.
- The aggregate Python gate proves that a cache-invalidation failure after
  User save rolls back the transaction, restores the in-memory language, keeps
  the current request locale unchanged, and returns a safe retryable error.

## 5. DOCX/Pack deviations and acceptance limitations

The differences in sections 5.1–5.3 are non-blocking under the current governing
decision and are tracked in `implementation/DOCX_PACK_DEVIATIONS.md`. Sections
5.4 and 5.5 record completed runtime and dependency evidence. Section 5.6
records the remaining Pack-internal acceptance limitations without changing
scope.

### 5.1 Phase definition conflict

The full V1.2 DOCX phase model places the platform/experience shell in its Phase 1, the first vertical slice in Phase 2, and Project/Gate/collaboration work in Phase 3. The controller Pack (`implementation/EXECUTION_PLAN.md` and status files) defines controller Phase 3 as the React industrial shell/localization layer and defers formal business capability to later phases. The Pack phase model is used for implementation; the difference does not expand or block Phase 3.

### 5.2 Requirement identifier and count conflict

The DOCX annex and Pack use different identifiers for substantially overlapping UI and localization requirements. At least 95 DOCX IDs from the `UX`, `ARCH`, `FR-TX`, `COD`, and `I18N` families are absent from `implementation/REQUIREMENT_TRACEABILITY.csv`; conversely, Pack requirements such as `FR-UX-029`, `FR-UX-032`, `NFR-LOC-002`, and `NFR-UX-002` do not have a deterministic same-ID DOCX origin. Only Pack-traced Phase 3 requirements are implemented now; DOCX-only identifiers remain outside the current scope.

### 5.3 Visual evidence viewport conflict

The full DOCX (`UX-036` and its visual-evidence text) requires 1440×900 and 1920×1080 evidence. The Pack visual baseline, acceptance material, and `industrial-ux` skill require 1366×768 and 1920×1080, plus 125% and 150% zoom checks. The Pack matrix is authoritative for the current Gate.

### 5.4 Frappe localization facts and runtime proof

The development environment pins Frappe branch `version-15` at commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`. The rebuilt local checkout reports
Frappe 15.115.4 and provides `frappe/translations/zh.csv` and
`frappe/translations/zh-TW.csv`. Its translation loader reads no-header two- or
three-column application CSV files, resolves the user's language before system
and English fallbacks, and overlays child-language translations after the
parent catalog. ADR-005, `contracts/terminology-allowlist.yaml`, and
`localization/README.md` now consistently select `en`, `zh`, and `zh-TW`.

The disposable `npi.localhost` Site installed and migrated both NPI apps. A
dedicated Website User exercised the loopback BFF and proved 556 direct entries
for each catalog, `zh` and `zh-TW` persistence across fresh sessions, an
unchanged `en` Administrator preference, CSRF enforcement, controlled
malformed/missing/extra/wrong-type request failures, no-store delivery,
body/header trace correlation, rejection of `zh-CN`, unchanged state after
rejected mutations, and exact fixture deletion. Successful bootstrap includes
only `userId`, `language`, `allowedLanguages`, `csrfToken`, and `catalog`.
Independent catalog validation still prevents `zh-TW` from silently inheriting
missing Simplified Chinese rows. The generated browser catalog version is
`12e5adf665b2cd30`; the BFF runtime version is a full SHA-256 value.

### 5.5 Dependency approval evidence

`frontend/package-lock.json`, ADR-003, and the Phase 3 dependency review record
the exact React and Siemens iX versions, MIT licenses, upstream metadata,
alternatives, adapter-scoped rollback, bundle impact, and upgrade rule. A clean
install consumed the lockfile, both complete and production-only audits found
zero known vulnerabilities, and the production build retained its visible
761.17 kB entry-chunk warning as a measured baseline rather than weakening the
threshold.

### 5.6 Phase 3 acceptance limitations

- **Business UAT:** FR-UX-031 requires six realistic clickable workflows to be
  reviewed by Project Management, Engineering/Tooling, and Quality
  representatives. Codex can implement the technical paths, capture metrics,
  and provide a complete script and unsigned result template, but it cannot act
  as those representatives. Until they complete the walkthroughs and severe
  findings are closed, the truthful outcome is
  `TECHNICAL_PASS_PENDING_UAT`, not a signed business acceptance.
- **Representative data:** the repository has no provenance-backed sanitized
  Project/Tooling/Trial/ERP sample package. Explicit contract-backed fixtures
  may be used for technical implementation and must be labelled as fixtures;
  they cannot be presented as real operational data or satisfy the real-data
  clause of FR-UX-031. This limits that requirement's final acceptance without
  expanding Phase 3 into ERP reconciliation or production access.
- **Device evidence:** the Pack desktop matrix remains 1366×768 and 1920×1080
  plus 125% and 150% zoom-equivalent layouts. A 768×1024 field-tablet visual and
  interaction test plus a 390×844 phone interaction test separately prove the
  named Trial review, photo, and prepared-action use case. These are technical
  prototype results, not a substitute for the pending representative UAT.

## 6. ERPNext reconciliation evidence check

The repository does **not** contain a complete existing ERPNext customization baseline or sufficient actual business material. The evidence found is limited to NPI One contracts/specifications, newly created NPI app foundations, and synthetic localization/test material. `docs/REPOSITORY_FACTS.md` explicitly records production ERPNext version/topology/customizations as unknown. No existing ERPNext custom-app source, site export, custom fields/property setters/workflows, role/permission export, integration inventory, or sanitized representative business records were found. Production ERPNext must not be connected.

### Required ERPNext Reconciliation material

`implementation/REQUIRED_INPUTS.md` is the single complete request for the
sanitized ERPNext reconciliation, representative-data, provenance, ownership,
SOP, and business-UAT inputs. It explicitly excludes secrets and production
access and defines how the package will be validated.

The missing ERPNext evidence did not block Phase 3 and does not block
contract-backed NPI-owned Project/Gate work, explicit mocks, or sandbox-ready
adapters in later phases. It blocks only affected ERP-specific mappings,
reconciliation claims, sandbox activation, and production activation until the
required facts and separate approvals exist.

## 7. Deferred reconciliation decisions

The following decisions or external inputs remain deferred and do not invalidate
the Phase 3 technical gate:

1. Approve a DOCX-to-Pack requirement crosswalk and resolve the 229-stated/228-extracted/173-traced count discrepancy, including whether Pack-only IDs are approved requirements or normalization errors.
2. Reconcile the differing DOCX screenshot matrix after the Pack-defined Phase 3 Gate; current evidence uses only the Pack matrix.
3. Supply and approve `implementation/REQUIRED_INPUTS.md` before affected
   ERP-specific mappings, reconciliation claims, or activation are accepted.

## 8. Proceed decision

The repaired technical checks and release gate are complete. Because
`FR-UX-031` still requires named business reviewers and provenance-backed
sanitized data, the truthful acceptance state is
`TECHNICAL_PASS_PENDING_UAT`, not an unqualified business PASS. The DOCX/Pack
differences and missing production ERPNext reconciliation package do not
trigger a global stop. Automatic phase transition remains a controller action;
this anchor does not authorize scope expansion, production access, or lowered
gates.
