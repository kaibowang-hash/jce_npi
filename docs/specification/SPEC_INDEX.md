# V1.2 Specification Index

## Authority order

1. 2026-07-21 continuous-delivery controller instruction (recorded in `AGENTS.md`)
2. `docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`
3. Pack V1.2 product, architecture, domain, UX, localization and acceptance specifications
4. Contracts, schemas, OpenAPI and ownership rules
5. `AGENTS.md` and repository skills
6. Generated plans and decisions
7. Examples, sketches and legacy naming

## Canonical sources

- Goal compatibility entry: `GOAL.md` (the sole goal document; no duplicate alias)
- Product: `docs/PRODUCT_SPEC.md`, `docs/DETAILED_REQUIREMENTS.md`
- Domain: `docs/DOMAIN_MODEL.md`, `docs/TOOLING_AND_TRIAL.md`
- Architecture/integration: `docs/ARCHITECTURE.md`, `docs/ERPNEXT_INTEGRATION.md`,
  `docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md` (governed fact-status and
  activation requirements; not evidence that production customization exists)
- UX/i18n: `docs/UX_INTERACTION_SPEC.md`, `docs/LOCALIZATION_SPEC.md`, `design/*`
- Acceptance: `docs/ACCEPTANCE_TESTS.md`
- Contracts: `contracts/data-ownership.yaml`, `contracts/npi-api.openapi.yaml`, `contracts/integration-event.schema.json`, `contracts/terminology-allowlist.yaml`
- Roadmap/backlog: `implementation/ROADMAP.md`, `implementation/backlog.yaml`
- Authoritative DOCX and accepted additive reconciliation:
  `docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`,
  `docs/V1_2_RECONCILIATION_ADDENDUM.md`
- Machine requirement artifacts:
  `implementation/V1_2_DOCX_REQUIREMENTS.csv`,
  `implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv`,
  `implementation/REQUIREMENT_TRACEABILITY.csv`
- Tooling import:
  `docs/TOOLING_LIST_IMPORT_SPEC.md`,
  `docs/reference/TOOLING_LIST_FIELD_MAPPING.csv`
- Reconciliation decisions:
  `implementation/V1_2_RECONCILIATION_DECISIONS.md`
- Brand sole source:
  `docs/Brand Asset/Brand Asset Instruction.csv`, the exact five LaunchFlow
  SVGs and `Core.png` in that folder; `Core.png` remains allocated to
  FR-BR-002/Phase 8/M7-09
- Skills: `.agents/skills/*/SKILL.md`; `industrial-ux` is the Siemens-classic
  industrial UX guard, `frappe-i18n` is the zero-mixed-language guard, and
  `xlsx-tooling-import` is the controlled workbook-import guard.

## Import verification

- ZIP integrity: `unzip -t` passed; every entry in `SHA256SUMS.txt` passed on 2026-07-21.
- Pack root resolved by `AGENTS.md` at `NPI_Codex_Execution_Pack_V1.2/` inside the archive.
- All Markdown, YAML, CSV, JSON, OpenAPI, schema, skill and reference index files were read.
- The historical 2026-07-21 DOCX XML cross-check remains import evidence.
- On 2026-07-25 deterministic OOXML extraction produced 229 unique
  requirements and 43 Tooling source columns; the reviewed crosswalk produced
  a 281-ID typed trace. The append-only 2026-07-27 `FR-UX-043` correction
  produces the current 282-ID trace.
  `scripts/verify_v1_2_reconciliation.py` validates generated artifacts, set
  arithmetic, the original Pack-ID digest, and the exact brand package.
- Original input artifacts remain at repository root and are ignored; the normalized DOCX copy is retained under `docs/reference/`.
