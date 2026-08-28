# Quality Gate

Validation uses three cumulative levels. A lower level optimizes feedback time;
it never deletes a test, lowers coverage or PASS criteria, or waives a later
Task, Phase, PR, or release boundary.

| Level | Trigger | Required validation |
|---|---|---|
| 1 — Incremental Check | Small fix, local refactor, or test correction inside one task | Changed-file format/lint/type checks; directly related unit/component tests; affected page/language/visual cases; necessary targeted security/permission tests; `git diff --check`. |
| 2 — Task Gate | Atomic task complete | Complete current-module tests; affected API, permission, integration, E2E, i18n and visual checks; current Requirement ID traceability; Task Diff Review; every task acceptance criterion. |
| 3 — Full Release Gate | Phase end, PR merge readiness, production release, public architecture/contract/Schema/auth/permission change, shared design/i18n/core-infrastructure change, or unbounded multi-domain impact | Whole-repository type/lint/tests; all API, permission, integration and E2E; complete trilingual and visual matrices; security, migration, rollback and recovery; complete traceability; `release-gate` Skill; durable complete evidence. |

Every change records a `changed-files → affected-tests` impact map. Prefer
affected checks when the boundary is reliable; shared component or translation
changes initially exercise affected pages only. The complete visual matrix,
whose actual case count is recorded in each Level 3 evidence report, runs at
Level 3 or when the
change is demonstrably global. Uncertain impact escalates to Level 3.

Related failures from one root cause may be fixed as a batch. Rerun affected
checks after the batch, then run the boundary Gate once they pass; do not rerun
the complete Gate after every individual repair.

Every Phase and Level 3 report must state `PASS` or `BLOCKED` and cite
reproducible commands/results for applicable static analysis, unit,
API/integration, frontend, E2E, visual, i18n/mixed-language,
permission/security, migration/rollback/recovery and diff/trace reviews.
Non-applicable checks require a reason. All Level 3 results are retained as
complete evidence; Level 1 or Level 2 success never substitutes for a Phase
Gate.

Release is blocked by fake success, accepted-path TODOs, permission bypass, direct ERP database access, core patches, dual-master fields, undocumented migration, failed checks, Desk as the user product, non-industrial UI, missing translations or mixed UI languages. Gate criteria cannot be weakened to fit implementation.

An ERPNext-integrated release must also reconcile every applicable row in
`docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md`: one of the five explicit
classifications, exact requirement/ownership/ERP-owner binding, proven exact
field or method (or a still-blocking fact), least privilege, migration,
compatibility, fault tests, Sandbox/UAT, deployment, monitoring/support and
rollback/forward-fix evidence. Repository contracts, Mock/Synthetic fixtures,
screenshots and samples do not prove production configuration. Any future
production read-only collection is a separate Gate that first changes the
higher-priority prohibition and freezes an exact least-privilege allowlist;
this documentation task grants no connection authority.

Environment remediation cannot pass on configuration inspection alone. After a Codespaces rebuild, `make verify-dev-environment` must succeed and record actual Node, package-manager, Python, Docker/Compose, Bench, Vite and Frappe pin evidence. Phase 1.1 satisfied this rule on 2026-07-21; future toolchain changes require equivalent fresh-target evidence.
