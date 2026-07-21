# Phase 3 Requirement Anchor

Status: **ACTIVE — Execution Pack scope authorized; Phase 1.1 verification remains prerequisite**  
Baseline date: 2026-07-21  
Machine execution baseline: repository V1.2 Execution Pack

## Current governing decision

The user's 2026-07-21 decision makes the repository V1.2 Execution Pack the sole machine-execution baseline for the current implementation. The V1.2 DOCX remains product background and a future reconciliation source only.

- Phase 3 scope and acceptance are exactly the Pack requirements assigned to Phase 3 in `implementation/REQUIREMENT_TRACEABILITY.csv`.
- DOCX/Pack phase names, requirement identifiers/counts, and screenshot-size differences do not block Pack-scoped work.
- DOCX-only requirements are recorded in `implementation/DOCX_PACK_DEVIATIONS.md`; they are not added to Phase 3 and may not enlarge its scope.
- Visual dimensions, screenshot evidence, and the test matrix follow the Pack's actual design, acceptance, implementation, and Skill files.
- Requirements from multiple sources must not be merged into a broader implicit requirement.
- Pack-internal material conflicts still block implementation. No such conflict was identified during this re-read.

This document is the only Phase 3 artifact created in this step. No React, UI, business module, DocType, integration logic, or generated visual evidence has been created. Phase 1.1 dynamic verification and Phase 3 implementation have not been claimed as complete.

## 1. Files actually read

The following repository sources were read for this anchor:

- Governance and state: `AGENTS.md`, `GOAL.md`, `README_FOR_CODEX.md`, `CHANGELOG_V1.2.md`, `implementation/PHASE_STATUS.yaml`, `implementation/REQUIREMENT_TRACEABILITY.csv`, `implementation/QUALITY_GATE.md`, `implementation/BLOCKERS.md`, `implementation/EXECUTION_PLAN.md`, `implementation/ROADMAP.md`, `implementation/backlog.yaml`, `implementation/DECISION_LOG.md`, `implementation/RISK_REGISTER.md`, `implementation/phase-0-gate.md`, `implementation/phase-1-gate.md`, `implementation/phase-1.1-gate.md`, and `implementation/phase-2-gate.md`.
- Formal V1.2 requirement source: the complete `docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`, extracted and read through its final paragraph, including its requirement annex.
- Pack product, architecture, domain, UX, localization, and acceptance sources: `docs/PRODUCT_SPEC.md`, `docs/DETAILED_REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md`, `docs/ERP_INTEGRATION_SPEC.md`, `docs/TOOLING_TRIAL_SPEC.md`, `docs/UX_INTERACTION_SPEC.md`, `docs/LOCALIZATION_SPEC.md`, `docs/ACCEPTANCE_TESTS.md`, `docs/SPEC_INDEX.md`, `docs/REPOSITORY_FACTS.md`, and the relevant files under `docs/reference/`.
- Visual and token sources: `design/UI_VISUAL_BASELINE.md`, `design/COMPONENT_USAGE.md`, `design/design-tokens.json`, and all five baseline images under `specs/ui/` (My Work, Project Cockpit, Tooling Cockpit, Trial Workspace, and ERP Execution Panel), including visual inspection.
- Contracts and localization sources: `contracts/data-ownership.yaml`, `contracts/terminology-allowlist.yaml`, the API/event/schema contracts relevant to the Pack, `localization/README.md`, and the Simplified/Traditional Chinese seed catalogs.
- Phase 3 review instructions: `.agents/skills/industrial-ux/SKILL.md`, `.agents/skills/frappe-i18n/SKILL.md`, and the Pack prompts relevant to UI, localization, and acceptance (`prompts/03_*`, `prompts/04_*`, and `prompts/05_*`).
- Approved decisions: every file under `docs/adr/`.
- Repository history: commits `2c8b3cc`, `b1d3abc`, `f3168c6`, `3d69031`, and `665a723`, including recent change summaries. The existing uncommitted `.gitignore` modification was treated as user-owned and was not changed.

## 2. Phase 3 requirements currently assigned by the controller

The controller traceability file assigns the following **41** IDs to Phase 3. The Pack-original source for every row is `docs/DETAILED_REQUIREMENTS.md` section 5.0; the DOCX column records the closest formal V1.2 upstream requirement family where a deterministic relationship is visible. The Pack does not contain a reviewed one-to-one crosswalk, so a family reference below is not a claim that the identifiers are equivalent.

| Phase 3 requirement | Pack-original source | Closest full-DOCX V1.2 source | Planned implementation files (after unblock) | Planned test / evidence |
|---|---|---|---|---|
| FR-UX-001 | Detailed Requirements §5.0 | UX-001, ARCH-002 | `frontend/src/app/*`, App Shell adapter | Shell structure, keyboard order, EN/zh/zh-TW screenshots |
| FR-UX-002 | Detailed Requirements §5.0 | UX-002, UX-033 | `frontend/src/app/navigation/*` | Stable navigation and route-state tests |
| FR-UX-003 | Detailed Requirements §5.0 | UX-025 | `frontend/src/app/my-work/*` | Worklist density, sorting/filtering, state fixtures |
| FR-UX-004 | Detailed Requirements §5.0 | UX-010 | `frontend/src/app/project-cockpit/*` | Cockpit layout and responsive evidence |
| FR-UX-005 | Detailed Requirements §5.0 | UX-003, UX-005 | `frontend/src/components/worklist/*` | Table/tree interaction and accessibility tests |
| FR-UX-006 | Detailed Requirements §5.0 | UX-006 | `frontend/src/components/object-page/*` | Object-page hierarchy and focus tests |
| FR-UX-007 | Detailed Requirements §5.0 | UX-007 | `frontend/src/components/inspector/*` | Docked inspector and resize tests |
| FR-UX-008 | Detailed Requirements §5.0 | UX-008 | `frontend/src/components/timeline/*` | Timeline semantics and non-colour status tests |
| FR-UX-009 | Detailed Requirements §5.0 | UX-013 | `frontend/src/components/gate/*` | Gate evidence presentation tests only; no gate business logic |
| FR-UX-010 | Detailed Requirements §5.0 | UX-019, ARCH-011 | `frontend/src/components/file-view/*` | Version/immutable-release presentation states |
| FR-UX-011 | Detailed Requirements §5.0 | UX-016 and ERP execution narrative | `frontend/src/components/erp-execution/*` | Honest pending/error/partial/retry states; no fake success |
| FR-UX-012 | Detailed Requirements §5.0 | UX-016, UX-017 | `frontend/src/components/status/*` | Text/icon/shape status semantics |
| FR-UX-013 | Detailed Requirements §5.0 | UX-017, COD-012 | `frontend/src/components/feedback/*` | Error, retry, trace/request-ID rendering |
| FR-UX-014 | Detailed Requirements §5.0 | UX-012, UX-015 | `frontend/src/components/compare/*` | Comparison layout and keyboard tests |
| FR-UX-015 | Detailed Requirements §5.0 | UX-015, UX-021 | `frontend/src/components/baseline/*` | Baseline/change visual states only |
| FR-UX-016 | Detailed Requirements §5.0 | UX-020 | `frontend/src/components/change-impact/*` | Impact summary and confirmation presentation |
| FR-UX-017 | Detailed Requirements §5.0 | UX-021 | `frontend/src/components/release/*` | Released/read-only visual-state tests |
| FR-UX-018 | Detailed Requirements §5.0 | UX-009 | `frontend/src/components/command-bar/*` | One-primary-action rule audit |
| FR-UX-019 | Detailed Requirements §5.0 | ARCH-004 and UX shell narrative | `frontend/src/app/routes/*` | Browser uses BFF route boundary; static import/API audit |
| FR-UX-020 | Detailed Requirements §5.0 | UX-023, ARCH-003 | `frontend/src/ui-adapters/*` | No raw Siemens component imports outside adapter |
| FR-UX-021 | Detailed Requirements §5.0 | UX-022, I18N-001, I18N-002 | `frontend/src/i18n/*` | Literal-English extraction and catalog reuse tests |
| FR-UX-022 | Detailed Requirements §5.0 | UX-024 | `frontend/src/styles/*` | Token, radius, shadow, colour, and density audit |
| FR-UX-023 | Detailed Requirements §5.0 | UX-031 | `frontend/tests/accessibility/*` | WCAG/keyboard/focus/label/contrast checks |
| FR-UX-024 | Detailed Requirements §5.0 | UX-032 | `frontend/tests/usability/*` | Task-completion fixtures and acceptance record |
| FR-UX-025 | Detailed Requirements §5.0 | UX-033, UX-035 | `frontend/src/app/responsive/*` | Supported viewport and zoom matrix |
| FR-UX-026 | Detailed Requirements §5.0 | I18N-003, I18N-007 | Frappe app translation catalogs after runtime verification | Three-locale coverage and no-fallback checks |
| FR-UX-027 | Detailed Requirements §5.0 | I18N-001, I18N-002, COD-015, COD-022 | Python/JS/React i18n adapters | `_()`, `__()`, `t()` extraction/static checks |
| FR-UX-028 | Detailed Requirements §5.0 | I18N-004 | `frontend/src/i18n/formatters.*` | Locale date/time/number/currency tests |
| FR-UX-029 | Detailed Requirements §5.0 | No deterministic annex-ID mapping found | Help/context components, path pending | Human-approved provenance required before implementation |
| FR-UX-030 | Detailed Requirements §5.0 | UX-029 | Build configuration and performance tests | Bundle/load/input performance evidence |
| FR-UX-031 | Detailed Requirements §5.0 | UX-030 | `frontend/tests/visual/*` | Prototype fidelity and review evidence |
| FR-UX-032 | Detailed Requirements §5.0 | No deterministic annex-ID mapping found | Telemetry adapter, path pending | Privacy-safe telemetry contract and test; provenance decision required |
| FR-UX-033 | Detailed Requirements §5.0 | ARCH-003, UX-023, UX-024 | `frontend/package.json`, lockfile, adapter boundary | Dependency/license/version and boundary checks |
| FR-UX-034 | Detailed Requirements §5.0 | I18N-003, I18N-004 | Translation extraction/build scripts | Reproducible catalog build and validation |
| FR-UX-035 | Detailed Requirements §5.0 | I18N-002, I18N-005 | Terminology lint/config | Controlled-term and mixed-language scan |
| FR-UX-036 | Detailed Requirements §5.0 | UX-022, I18N-002, I18N-007 | Visual-test locale fixtures | EN/zh/zh-TW screenshots for required states |
| FR-UX-037 | Detailed Requirements §5.0 | I18N-006 | Third-party default-label adapter | No untranslated library defaults test |
| NFR-UX-001 | Detailed Requirements §5.0 | NFR-UX-001 | Shell/styles/components above | Industrial visual gate |
| NFR-LOC-001 | Detailed Requirements §5.0 | NFR-LOC-001 | i18n files/catalogs above | Three-language completeness gate |
| NFR-LOC-002 | Detailed Requirements §5.0 | I18N family; no same DOCX NFR ID | Locale formatters/catalog validation | Locale-format and fallback gate; ID decision required |
| NFR-UX-002 | Detailed Requirements §5.0 | UX family; no same DOCX NFR ID | Accessibility/responsive test suites | Accessibility and viewport gate; ID decision required |

The formal DOCX requirement annex contains requirement families that are absent from the current traceability CSV: `UX-001..UX-036`, `ARCH-001..ARCH-012`, `FR-TX-001..FR-TX-018`, `COD-001..COD-022`, and `I18N-001..I18N-007`. A machine extraction found 228 unique DOCX identifiers while the DOCX states 229 requirements, and the Pack traceability CSV has 173 rows. These counts and mappings must be reconciled before the table above can be treated as complete formal traceability.

## 3. Planned Phase 3 implementation boundary

After the blockers are resolved, the intended boundary is limited to the approved industrial React shell, the local Siemens iX adapter, tokenized styling, the Frappe-backed localization adapter/catalog pipeline, and their tests. Candidate files are:

- `frontend/package.json`, an approved lockfile, TypeScript/Vite/test configuration, and `frontend/index.html`;
- `frontend/src/main.tsx`, `frontend/src/app/*`, `frontend/src/ui-adapters/*`, `frontend/src/components/*`, `frontend/src/styles/*`, and `frontend/src/i18n/*`;
- verified Frappe translation catalogs under the existing app path, only after actual Frappe version, language codes, extraction commands, and runtime resolution are demonstrated;
- `frontend/tests/*` and narrowly scoped repository scripts for dependency-boundary, token, translation-coverage, mixed-language, accessibility, and visual checks.

This scope does **not** authorize Project, Tooling, Trial, Change, gate-decision, or ERP integration business logic. It also does not authorize new business DocTypes, fixtures presented as real data, production ERP access, or a change to the approved architecture.

## 4. Planned checks and visual evidence

No item below has been claimed as executed or passed:

- First complete Phase 1.1 dynamic checks after a Codespaces rebuild: Node, the approved package manager, Python, Docker CLI/approved alternative, Bench/Frappe development path, and React build tooling.
- Clean dependency install from the lockfile, build, TypeScript check, lint, unit/component tests, and production bundle check.
- Static enforcement that Siemens packages are imported only through the local adapter; browser calls only the NPI BFF boundary; token values, 0–2 px ordinary radius, restrained shadows, one primary colour, and one primary action are enforced.
- Keyboard, focus, accessible-name, contrast, non-colour status, resize, and supported zoom checks.
- Normal, loading, empty, no-permission, read-only, error, conflict, asynchronous-processing, and partial-ERP-result states using explicit test fixtures—not placeholder content or fabricated operational data.
- Literal-English source scan; Frappe extraction/build; English, Simplified Chinese, and Traditional Chinese coverage; placeholder/context parity; controlled terminology; third-party-default translation; and mixed-language scan. Missing translations must fail rather than silently fall back to English.
- Real rendered screenshots for all three languages at the finally approved viewport matrix, including 125% and 150% zoom where required. Evidence must be produced by the runnable application and may not be mocked or manually fabricated.
- Pack Phase 3 acceptance checks and both `industrial-ux` and `frappe-i18n` review gates, followed by the repository release gate before any checkpoint commit.

## 5. DOCX/Pack deviations and runtime prerequisites

The differences in sections 5.1–5.3 are non-blocking under the current governing decision and are tracked in `implementation/DOCX_PACK_DEVIATIONS.md`. Section 5.4 is a Phase 1.1 runtime verification item. Section 5.5 is handled by the approved ADR and lockfile verification during implementation.

### 5.1 Phase definition conflict

The full V1.2 DOCX phase model places the platform/experience shell in its Phase 1, the first vertical slice in Phase 2, and Project/Gate/collaboration work in Phase 3. The controller Pack (`implementation/EXECUTION_PLAN.md` and status files) defines controller Phase 3 as the React industrial shell/localization layer and defers formal business capability to later phases. The Pack phase model is used for implementation; the difference does not expand or block Phase 3.

### 5.2 Requirement identifier and count conflict

The DOCX annex and Pack use different identifiers for substantially overlapping UI and localization requirements. At least 95 DOCX IDs from the `UX`, `ARCH`, `FR-TX`, `COD`, and `I18N` families are absent from `implementation/REQUIREMENT_TRACEABILITY.csv`; conversely, Pack requirements such as `FR-UX-029`, `FR-UX-032`, `NFR-LOC-002`, and `NFR-UX-002` do not have a deterministic same-ID DOCX origin. Only Pack-traced Phase 3 requirements are implemented now; DOCX-only identifiers remain outside the current scope.

### 5.3 Visual evidence viewport conflict

The full DOCX (`UX-036` and its visual-evidence text) requires 1440×900 and 1920×1080 evidence. The Pack visual baseline, acceptance material, and `industrial-ux` skill require 1366×768 and 1920×1080, plus 125% and 150% zoom checks. The Pack matrix is authoritative for the current Gate.

### 5.4 Frappe language-code verification conflict

ADR-005 records `zh` and `zh-TW` as verified CSV catalog codes. However, `contracts/terminology-allowlist.yaml` still labels `zh-CN-provisional` and `zh-TW-provisional` as provisional and explicitly says M0 must verify deployed language codes; `localization/README.md` likewise says the seeds are provisional. There is no usable live Bench/site evidence in the repository proving the deployed Frappe version, actual user-language values, resolution order, extraction command, or catalog loading. The English-source policy is clear, but the required Frappe translation mechanism cannot yet be truthfully declared operational.

### 5.5 Dependency approval evidence

The architecture approves the Siemens iX package family and local adapter pattern, but Phase 3 has no reviewed lockfile or dependency record proving exact versions, licenses, maintenance/security posture, bundle impact, and alternatives for the production dependencies. Repository policy prohibits silently adding production dependencies without that evidence.

## 6. ERPNext reconciliation evidence check

The repository does **not** contain a complete existing ERPNext customization baseline or sufficient actual business material. The evidence found is limited to NPI One contracts/specifications, newly created NPI app foundations, and synthetic localization/test material. `docs/REPOSITORY_FACTS.md` explicitly records production ERPNext version/topology/customizations as unknown. No existing ERPNext custom-app source, site export, custom fields/property setters/workflows, role/permission export, integration inventory, or sanitized representative business records were found. Production ERPNext must not be connected.

### Required ERPNext Reconciliation material

Provide a dated, owner-identified, sanitized, read-only package containing:

1. Exact Frappe and ERPNext versions/builds, installed-app list and versions, deployment topology, database type, file-storage mode, enabled locales, System Settings language, representative User language values, and the supported Bench/container development commands.
2. Source or export of every ERPNext custom app and extension: `hooks.py`, modules, DocTypes, patches, fixtures, overrides, whitelisted methods, scheduled jobs, reports, print formats, client/server scripts, notifications, webhooks, and workspace customizations.
3. Exports of Custom Fields, Property Setters, Workflows and Workflow States/Actions, Naming Series, Roles, Role Profiles, DocPerm/custom permissions, User Permissions, sharing rules, and integration/service-user scopes. Do not include credentials, tokens, session cookies, or private keys.
4. Current schemas, status/state semantics, ownership, and edit authority for Customer, Supplier, Item, Item Variant, BOM/MBOM, purchasing/receiving, inventory, manufacturing, Quality Inspection/NCR/CAPA, Asset/Maintenance, ECR/ECO/ECN, File/Attachment, and every custom mold/tooling/trial/project object.
5. A field-level mapping inventory for every existing integration, including endpoints, commands/queries, webhook payloads, authentication method (described but not secret), signatures, idempotency keys, retries, dead-letter/replay/reconciliation behavior, rate limits, error codes, and known failure cases.
6. Sanitized representative records and relationship diagrams for at least one customer-owned project and one new-tool project, including revisions, approvals, released files, tooling/mold records, trial rounds, quality outcomes, purchase/manufacturing references, and failed/pending integration examples. Preserve stable surrogate relationships while removing personal, commercial, and secret data.
7. The authoritative Tooling List workbook/template and column dictionary, including the expected 43-column interpretation, A/B/C-face, overmold/insert rules, required/optional fields, units, validation, revision history, and approved sample rows.
8. Master-data and coding rules: company/site/factory, customer/supplier/item naming, UOM, currency, timezone, fiscal/calendar conventions, numbering/naming series, document retention, attachment classification, and controlled terminology.
9. Current business SOPs and acceptance evidence for Project, Gate, Tooling, Trial, Change, approval/release, and ERP execution, with named business owners empowered to resolve discrepancies between SOP, ERP configuration, V1.2 contracts, and sample data.
10. A data provenance manifest for every export: source system/site, extraction command or report, timestamp/timezone, responsible owner, redaction method, record counts, and checksum. Any sandbox access must be separately approved and must not be production access.

The missing ERPNext evidence does not block the Pack-defined Phase 3 shell/i18n foundation. It continues to block formal Project, Tooling, Trial, Change, and ERP integration business logic, which is outside Phase 3.

## 7. Deferred reconciliation decisions

The following items are deferred and do not block Pack-scoped Phase 3 work:

1. Approve a DOCX-to-Pack requirement crosswalk and resolve the 229-stated/228-extracted/173-traced count discrepancy, including whether Pack-only IDs are approved requirements or normalization errors.
2. Confirm that controller Phase 3 means only the industrial React shell/localization foundation, and record how this maps to the DOCX phase model.
3. Reconcile the differing DOCX screenshot matrix after the Pack-defined Phase 3 Gate; current evidence uses only the Pack matrix.
4. Resolve ADR-005 against the still-provisional localization contract using evidence from the rebuilt, actual Frappe/Bench runtime; confirm Frappe version, exact language codes, CSV versus PO/MO path, extraction/build command, and runtime user-language resolution.
5. Approve exact Siemens iX/React/build/test dependency versions and the required license, maintenance, security, bundle, alternative, and rollback record.
6. Supply and approve the ERPNext Reconciliation package above, then resolve data ownership, state, permission, and contract discrepancies before any formal Project, Tooling, Trial, Change, or ERP integration business logic is implemented.

## 8. Proceed decision

DOCX/Pack differences no longer trigger a stop. Work proceeds first to the real Phase 1.1 environment Gate. Phase 3 may resume only after that Gate passes. Missing ERPNext reconciliation material continues to prohibit later formal business logic but does not prohibit the Pack-defined Phase 3 shell, localization foundation, test fixtures, or contract-backed prototype states.
