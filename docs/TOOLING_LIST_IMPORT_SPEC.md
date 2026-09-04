# Tooling List Controlled Import Specification

Status: `RECONCILED_PHASE_6_REQUIREMENT`

Source: the Tooling List analysis and mapping embedded in
`docs/reference/NPI_Tooling_Product_Spec_V1.2.docx`.

## 1. Observed customer workbook

| Fact | Observed value |
|---|---|
| Worksheet/range | One worksheet, used range `A1:AQ87`, 43 columns |
| Business rows | 66 Part rows plus shared-Tooling sections and a color-master summary |
| Appearance flag | 39 `Y`, 26 `N`, 1 blank |
| Shared Tooling flag | 14 `Y`, 50 `N`, 2 blank |
| Tooling number contamination | 35 rows contain `New Tooling` state text in the Tooling-number field |
| Material distribution | PP 27, ABS 19, PA66 6, POM 6, TPE 3, PC 2, SAN 2, ABS+PC 1 |
| Cavity distribution | 2 cavities 30, 4 cavities 19, 1 cavity 12, 8 cavities 5 |
| Data-quality findings | Multi-values/newlines, tonnage and machine-type mixing, undefined A/B/C, blank-implied relations, and at least one `#REF!` |

These facts describe the analyzed source workbook; they are not production
defaults, constraints or hard-coded customer rules.

## 2. Eight-step controlled flow

1. **Upload** — retain the original private file, SHA-256, customer, Project,
   template version and immutable import-batch identity.
2. **Detect** — identify title/header, data regions, section rows,
   shared-Tooling regions, summary regions and floating-image anchors without
   fixed row numbers.
3. **Map** — show source column to target aggregate/field mapping and allow a
   versioned customer-specific mapping template.
4. **Transform** — split multi-valued models/identifiers/Tooling numbers,
   separate number from state, normalize units, and separate machine tonnage
   from machine type while retaining raw values.
5. **Validate** — report required/type/reference/duplicate errors, `#REF!`,
   mixed units, states embedded in identifiers, undefined A/B/C and forbidden
   hidden capacity constants.
6. **Preview** — show exact create/update/skip candidates and relations.
   Ambiguous relationships and image matches require human confirmation.
7. **Execute** — run an asynchronous, bounded, idempotent batch with per-row
   and per-field results, explicit partial success and safe retry.
8. **Audit/rollback** — trace every created object to file/batch/row/raw value
   and transformation. Rollback is available only under an approved cutoff;
   downstream-used data is never destructively removed by assumption.

## 3. Object and provenance rules

- A spreadsheet row is an import envelope, not a Tooling aggregate.
- Part, Part Revision, Tooling Requirement, Tooling Master, Applicability,
  Tooling Revision, Tooling Set, Cavity, Insert, Process Baseline and Capacity
  Scenario retain distinct identities.
- Blank Tooling numbers never inherit the prior row merely because a
  spreadsheet visually groups rows.
- Shared Tooling creates versioned Applicability, not duplicate masters.
- Planned copy quantity never substitutes for physical Tooling Set records.
- `New Tooling` and similar state text is retained raw, parsed into a candidate
  state, and removed from the candidate identifier only after confirmed
  transformation.
- A/B/C values remain `Legacy Grade`; their meaning is not inferred.
- Imported calculated capacity is evidence for comparison. A `#REF!` or
  unverified formula result never becomes an approved capacity result.
- Every normalized value retains source file, batch, row, source column, raw
  value, transformation version and confirmation actor where applicable.

## 4. Mapping

`docs/reference/TOOLING_LIST_FIELD_MAPPING.csv` is the complete reviewed
43-column source mapping. Runtime mapping templates may version customer
aliases but cannot silently remove a source column or weaken its validation.

The mapping identifies likely target objects and fields. It does not settle
whether each numeric source column is Customer Standard, estimate, measured
actual or calculated output; that classification remains DR-REC-007.

## 5. Images

- Enumerate floating images and their worksheet anchors without executing
  macros or external links.
- Produce candidate Part/source-row matches using bounded deterministic facts.
- Never auto-bind an uncertain image.
- Human confirmation records the candidate, selected target, actor, time and
  reason.
- Store the registered private file revision/hash; a workbook-internal image
  relationship is provenance, not authorization.

## 6. Result and correction artifacts

The user-visible job exposes:

- queued, processing, partially succeeded, succeeded, failed-retryable,
  failed-final and rolled-back/rollback-denied truth;
- counts of create/update/skip/warning/error/confirmation-required rows;
- row/field errors with stable codes, localized complete messages and trace ID;
- a downloadable correction workbook/CSV with only authorized fields;
- the exact mapping/template/transformation versions; and
- retry/rollback eligibility and the reason an action is unavailable.

No transient toast, server log or optimistic success substitutes for the
durable operation result.

## 7. Security and rollback

- Accept only approved XLSX input within configured size/row/image limits.
- Reject macros, path traversal, external relationships and decompression
  limits that exceed policy; never fetch linked content.
- Authorize Project, customer scope, file confidentiality, import command and
  every created/updated target server-side.
- Use actor-bound idempotency and optimistic versions.
- Redact confidential data in correction/export artifacts and audit every
  download.
- Until DR-REC-008 is resolved, the safe default is to deny destructive
  rollback after any imported object has a downstream reference and require a
  reviewed forward correction.

## 8. Acceptance fixture

Phase 6 must include a sanitized, provenance-backed workbook fixture covering:

- inserted/deleted title rows;
- data, shared-Tooling and summary regions;
- multi-line identifiers;
- `New Tooling` embedded in Tooling number;
- a `#REF!` formula;
- blank required values and mixed units;
- undefined A/B/C values;
- dual-shot/overmold and insert candidate notes;
- one confidently anchored and one ambiguous floating image; and
- partial success, safe retry, rollback-allowed and rollback-denied outcomes.

The analyzed production/customer workbook itself is not committed unless
explicitly sanitized and approved.
