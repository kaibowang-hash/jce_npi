---
name: xlsx-tooling-import
description: Inspect, map, design, implement, or review controlled XLSX Tooling List imports for NPI One. Use for customer Tooling workbooks, 43-column mappings, workbook region/image/formula analysis, import provenance, validation, preview, idempotent batches, partial results, correction files, retry, rollback, or reconciliation.
---

# Controlled XLSX Tooling Import

## Start from repository authority

Read:

- `docs/TOOLING_LIST_IMPORT_SPEC.md`;
- `docs/reference/TOOLING_LIST_FIELD_MAPPING.csv`;
- `implementation/V1_2_DOCX_REQUIREMENTS.csv` rows `FR-TX-001..020`;
- `docs/DOMAIN_MODEL.md` Tooling aggregates; and
- `implementation/V1_2_RECONCILIATION_DECISIONS.md`.

Do not treat the mapping CSV as approved production column semantics where a
Decision Request remains open.

## Inspect without mutating

1. Hash the original workbook and retain its exact private File Revision.
2. Run `python scripts/inspect_xlsx.py <workbook>` from this skill directory
   for archive, sheet, formula-error, external-link and floating-image facts.
3. Reject macros, encrypted entries, unsafe archive paths, external
   relationships and configured decompression limits. Never fetch linked
   content or execute formulas/macros.
4. Identify headers, data regions, section rows, shared-Tooling regions and
   summary regions from content/structure; never hard-code Excel row numbers.
5. Inventory merged cells, multi-line/multi-value cells, formulas, errors,
   image anchors and unmapped trailing fields. Avoid printing sensitive cell
   values into normal logs.

## Map normalized aggregates

Keep these identities distinct:

- Part and Part Revision;
- Tooling Requirement;
- Tooling Master and versioned Applicability;
- Tooling Revision;
- each physical Tooling Set/Copy;
- Cavity Map, Insert Applicability and process chain;
- Customer Standard, Trial Actual and Approved Process Baseline;
- Capacity Scenario; and
- Trial / Trial Round.

Preserve source file, batch, worksheet, row, column, raw value, transformation
version and confirmation actor. Blank cells, visual grouping and remarks are
not authority to invent a relationship.

Never:

- infer A/B/C meaning; retain it as Legacy Grade;
- turn `New Tooling` or another state into a Tooling number;
- copy Customer Standard into measured Trial Actual;
- accept `#REF!` or a cached workbook formula as approved capacity truth;
- reduce physical sets to a count;
- duplicate a shared Tooling Master per Project;
- auto-bind an uncertain floating image; or
- silently drop an unmapped column or raw value.

## Design the eight-step job

Implement or review:

1. upload and immutable provenance;
2. position-independent detection;
3. versioned source-to-target mapping;
4. bounded transformations with raw retention;
5. row/field/type/reference/duplicate/business validation;
6. create/update/skip preview and human-confirmation queue;
7. asynchronous actor-bound idempotent execution with explicit partial truth;
8. audit, safe retry, reconciliation and policy-bound rollback.

Use stable error codes and complete translatable English source messages.
Do not report success when rows failed or remain unconfirmed.

## Respect unresolved decisions

Stop only the dependent behavior when the repository lacks:

- Customer Standard/estimate/actual/calculated column classification;
- A/B/C meaning;
- downstream-use rollback cutoff;
- production customer mapping/template approval;
- physical Tooling Set versus ERP asset mapping policy; or
- sanitized acceptance data provenance.

Continue safe parser, provenance, preview, validation, Mock and test work.
Never contact production ERPNext.

## Required evidence

- original hash and archive-safety report;
- detected regions/columns/images with ambiguous matches identified;
- source-to-target mapping diff and unmapped-field report;
- row/field validation and downloadable correction artifact;
- create/update/skip/confirmation preview;
- idempotent replay, partial result, retry and rollback-denial tests;
- exact object-to-source provenance and reconciliation;
- Project/tenant/file/import permissions and audit;
- English/`zh`/`zh-TW` job/error/export coverage; and
- no false success, guessed relationship, hidden constant or destructive
  downstream rollback.
