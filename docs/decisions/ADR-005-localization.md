# ADR-005: Localization chain

Status: Accepted

## Decision

English literal source strings are the only authoring keys. The NPI custom app
uses Frappe v15 CSV catalogs for Simplified Chinese (`zh`) and Traditional
Chinese (`zh-TW`). React calls only the local `t()` adapter and receives the
authenticated user's Frappe-resolved catalog through the NPI BFF. Missing core
translations, placeholder/context mismatches, unwrapped display strings, and
non-allowlisted mixed-language output fail CI and release review.

## Pinned runtime evidence

The reproducible development environment pins Frappe branch `version-15` at
commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`. That checkout identifies itself
as Frappe **15.115.4** in `frappe/__init__.py` and contains both
`frappe/translations/zh.csv` and `frappe/translations/zh-TW.csv`.

The pinned implementation establishes these facts:

- application catalogs are loaded from `<app>/translations/<lang>.csv`;
- accepted CSV rows contain two fields or three fields with optional context;
- runtime CSV files have no header row;
- user language resolves from `User.language`, then the system default, then
  the current local language, and finally `en`;
- `bench --site <site> build-message-files` calls
  `rebuild_all_translation_files()` and rewrites App source CSV files for every
  installed language; it is not a deployment compiler and is prohibited from
  Site initialization because it can discard the independently reviewed NPI
  catalog;
- Frappe v15 loads custom App CSV catalogs at runtime, so deployment invalidates
  runtime translations with `bench --site <site> clear-cache` after migration.

These source facts settle the catalog format and language-code decision. The
Phase 3 local-runtime gate then installed and migrated both NPI apps on the
disposable `npi.localhost` Site and exercised the BFF with a dedicated Website
User. It proved 556 direct entries per Chinese locale, controlled `zh` and
`zh-TW` updates across fresh authenticated sessions, an unchanged `en`
Administrator preference, rejection of `zh-CN`, CSRF enforcement, controlled
malformed/invalid request errors, no-store catalog delivery, response trace
correlation, and deletion of the exact disposable user. The proof used
loopback HTTP only; no ERPNext or production system was contacted.

## Parent-language inheritance caveat

Frappe treats `zh-TW` as a child of `zh`: it loads the parent catalog first and
then overlays child translations. That framework behaviour is not permission
to ship incomplete Traditional Chinese. An absent `zh-TW` row could silently
inherit Simplified Chinese, violating NPI One's 100% locale coverage rule.
Therefore CI compares the complete extracted source/context manifest with both
catalogs independently and rejects reliance on parent fallback for touched core
flows.

## React extraction and delivery

The repository-owned React extractor scans only literal
`t("English source", params?, context?)` calls and emits a deterministic
source/context manifest. It rejects variables, Chinese keys, path keys, and
concatenated sentences. Catalog tooling uses that manifest to validate the
canonical no-header NPI app CSV files; it does not create a second translation
database.

The NPI BFF returns exactly `userId`, `language`, `allowedLanguages`,
`csrfToken`, and the catalog resolved for the authenticated Frappe session.
Session responses use `Cache-Control: private, no-store` and an `X-Trace-ID`;
Problem Details responses carry the same trace in their body. `getLocale()`
reads that session fact, and `setLocale()` uses a controlled NPI BFF `PUT` with
the trusted in-memory Frappe CSRF token to update the current user's preference.
Missing/wrong CSRF, malformed JSON, missing/extra/wrong-type fields, and an
unsupported locale receive controlled errors and do not mutate the preference.
The browser strips caller-supplied CSRF headers, fails closed when a trusted
token is unavailable, reconciles an indeterminate update through a fresh
bootstrap before retrying, and does not claim that an unconfirmed update was
saved. It never chooses an unrelated locale from its own store, imports
provisional seeds at runtime, or calls raw Frappe DocType CRUD to change
language.

The preference mutation constructs and validates its response catalog before
editing the User, then saves and invalidates the user's translation cache in a
single request transaction. If cache invalidation fails, the request boundary
rolls the transaction back, restores the in-memory User language, preserves the
original request locale, and returns a retryable safe 500. A dedicated Python
test proves that failure path so error rendering cannot switch to an
uncommitted locale.

The direct `zh` and `zh-TW` source catalogs each contain 556 entries. The
generated frontend catalog version is `12e5adf665b2cd30`; the runtime BFF uses
a full 64-character SHA-256 catalog version. These identifiers are cache and
consistency facts, not translated business values.

## Authoring seeds

`localization/seed/*.provisional.csv` files are review aids with descriptive
filenames and a header. They are not installable runtime catalogs. Phase 3
converts reviewed content to `zh.csv` and `zh-TW.csv`, removes the header, and
validates encoding, duplicate source/context pairs, placeholders, terminology,
coverage, and mixed-language output.

## Consequences and rollback

The custom React extractor and BFF catalog adapter become tested infrastructure
but remain replaceable behind `t()`. Rolling back the React delivery mechanism
does not change English source strings or Frappe catalogs. Changing Frappe
format, locale codes, or the single-source policy requires a new ADR with
migration, cache invalidation, compatibility tests, and rollback evidence.
