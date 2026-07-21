# ADR-005: Localization chain

Status: Accepted. English literal source strings flow through Frappe-compatible CSV catalogs for `zh` and `zh-TW` (exact codes verified against the pinned v15 runtime in Phase 1). React calls only local `t()` and loads the same app catalogs. Missing core translations and mixed-language output fail CI.
