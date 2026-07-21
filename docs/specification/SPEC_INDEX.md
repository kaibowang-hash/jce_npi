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
- Architecture/integration: `docs/ARCHITECTURE.md`, `docs/ERPNEXT_INTEGRATION.md`
- UX/i18n: `docs/UX_INTERACTION_SPEC.md`, `docs/LOCALIZATION_SPEC.md`, `design/*`
- Acceptance: `docs/ACCEPTANCE_TESTS.md`
- Contracts: `contracts/data-ownership.yaml`, `contracts/npi-api.openapi.yaml`, `contracts/integration-event.schema.json`, `contracts/terminology-allowlist.yaml`
- Roadmap/backlog: `implementation/ROADMAP.md`, `implementation/backlog.yaml`
- Reference-only source: `docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`
- Skills: `.agents/skills/*/SKILL.md`; `industrial-ux` is the Siemens-classic industrial UX guard and `frappe-i18n` is the zero-mixed-language guard.

## Import verification

- ZIP integrity: `unzip -t` passed; every entry in `SHA256SUMS.txt` passed on 2026-07-21.
- Pack root resolved by `AGENTS.md` at `NPI_Codex_Execution_Pack_V1.2/` inside the archive.
- All Markdown, YAML, CSV, JSON, OpenAPI, schema, skill and reference index files were read.
- DOCX XML text (105,147 bytes extracted) was read as a cross-check; machine execution remains based on canonical text specifications and contracts.
- Original input artifacts remain at repository root and are ignored; the normalized DOCX copy is retained under `docs/reference/`.

