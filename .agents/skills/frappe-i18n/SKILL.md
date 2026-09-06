---
name: frappe-i18n
description: Implement or review Frappe-compatible internationalization for NPI One. Enforces literal English source strings, complete Simplified/Traditional Chinese translations, controlled terminology, locale formatting and zero mixed-language UI. Use for every user-visible text change.
---

# Frappe Internationalization Guard

## Before changing user-visible text
- Read `docs/LOCALIZATION_SPEC.md` and `contracts/terminology-allowlist.yaml`.
- Confirm the actual Frappe version, language codes, extraction/build commands, and the official translation workflow from the ADR. Frappe v15 and earlier commonly use app CSV files; v16 supports Gettext PO/MO while custom apps may continue using CSV. Do not guess or create a parallel catalog.
- List every new/changed English source string and every screen, error, notification, email, print or export affected.

## Implementation rules
- English is the only source language.
- Python: `_()` / `frappe._()`.
- Frappe JavaScript: `__()`.
- React: local `t()` adapter only.
- Translation calls receive extractable English string literals, never variables, Chinese keys or page-path keys.
- Use complete messages and stable placeholders; do not concatenate translated fragments.
- Keep API/status/database values stable and untranslated.
- Use locale-aware date/number/currency/list formatting.
- Add Simplified and Traditional Chinese translations in the same PR.
- Third-party components must receive translated labels through adapters; default English labels are defects.

## Mixed-language rule
- Chinese UI may contain only retain-listed abbreviations/product names, business data, identifiers, file names and units in English.
- `Tooling`, `Gate`, `Trial`, `Worklist`, `Workspace`, `Save`, `Status` and other ordinary labels must be translated in Chinese UI.
- 英文界面 may not contain Chinese UI copy.
- Missing translations must be obvious in development and block release for touched core flows.

## Required evidence
- Translation catalog diff for English source, Simplified Chinese and Traditional Chinese.
- Placeholder/context consistency test.
- Hardcoded display-string scan.
- Chinese ordinary-English residual scan with retain allowlist.
- English Chinese-character residual scan.
- English, Simplified Chinese and Traditional Chinese screenshots/E2E evidence.
- Coverage report with zero missing strings for touched core flows.
