# V1.2 Execution Plan

This is the single executable plan derived from the controller instruction, Pack roadmap/backlog and V1.2 specification. Phases 0–9 follow the controller-defined boundaries. Within each phase, existing M0–M9 task IDs remain compatibility references; requirement IDs remain unchanged.

Each phase runs: scope and trace review; atomic task implementation; static, unit, API/integration, frontend, E2E, visual, i18n, permission/security and migration/rollback checks as applicable; trace and diff review; up to five repair rounds; gate report; checkpoint commit; status update; automatic transition.

Phase 0 produces normalized specifications and ADRs only. Phase 1 bootstraps reproducible tooling without business DocTypes. Phase 2 establishes the Frappe app, API/security/audit/job foundations. Phase 3 establishes the React industrial shell, local UI adapter and Frappe-compatible trilingual chain. Phases 4–7 deliver project/gates, design/EBOM, tooling/capacity/import, and trial/readiness vertical slices. Phase 8 delivers mock and sandbox-ready ERP integration only. Phase 9 delivers change, portfolio/reporting, hardening, migration rehearsal, operations and UAT.

No phase may claim PASS with fake success, placeholders in accepted paths, failed applicable checks, permission bypass, cross-database access, dual-master editing, undocumented migration, Desk-dependent user flows, visual violations, missing core translations, or mixed-language defects.

