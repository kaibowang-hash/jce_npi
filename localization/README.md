# Localization catalogs and seeds

The pinned Frappe 15.115.4 source uses application CSV catalogs named for the
runtime language codes. NPI One's canonical runtime catalogs are therefore:

- `apps/npi_core/npi_core/translations/zh.csv` for Simplified Chinese;
- `apps/npi_core/npi_core/translations/zh-TW.csv` for Traditional Chinese.

Runtime catalogs have **no header row**. Each UTF-8 CSV row contains either
`source_string,translated_string` or
`source_string,translated_string,context`, exactly as accepted by the pinned
Frappe loader. English is the literal source language and does not require a
parallel English translation catalog.

The files under `localization/seed/` remain provisional authoring examples.
They intentionally retain descriptive filenames and a header so people can
review their intent. They are not runtime catalogs and must never be copied or
imported unchanged into a site. Phase 3 converts reviewed seed content into the
canonical no-header catalogs and validates every row before use.

The React source extractor accepts only literal `t("English source", ..., context)`
calls and emits a deterministic source/context manifest. That manifest is
validated against the same NPI app catalogs. At runtime React obtains the
catalog resolved for the authenticated Frappe user through the NPI BFF; it does
not load the seed files or maintain a parallel i18n store.

Rules:

- English source strings are literal and canonical.
- `zh` and `zh-TW` must be updated together with 100% coverage for touched core
  flows; Traditional Chinese may not rely on parent-language fallback.
- Context and named placeholders must match between source and both catalogs.
- Missing translations and non-allowlisted mixed-language output block release.
- Catalog extraction, conversion, validation, and BFF loading must be
  reproducible commands covered by CI.
- Frappe v15 reads these App CSV files directly. Site initialization runs
  `clear-cache`; it must not run `build-message-files`, which regenerates and
  overwrites source catalogs for all installed languages.
