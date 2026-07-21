# Quality Gate

Every phase report must state `PASS` or `BLOCKED` and cite reproducible commands/results for applicable static analysis, unit, API/integration, frontend, E2E, visual, i18n/mixed-language, permission/security, migration/rollback and diff/trace reviews. Non-applicable checks require a reason.

Release is blocked by fake success, accepted-path TODOs, permission bypass, direct ERP database access, core patches, dual-master fields, undocumented migration, failed checks, Desk as the user product, non-industrial UI, missing translations or mixed UI languages. Gate criteria cannot be weakened to fit implementation.

Environment remediation cannot pass on configuration inspection alone. After a Codespaces rebuild, `make verify-dev-environment` must succeed and record actual Node, package-manager, Python, Docker/Compose, Bench, Vite and Frappe pin evidence. Phase 1.1 satisfied this rule on 2026-07-21; future toolchain changes require equivalent fresh-target evidence.
