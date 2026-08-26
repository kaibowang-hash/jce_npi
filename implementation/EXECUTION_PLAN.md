# V1.2 Execution Plan

This is the single executable plan derived from the controller instruction, Pack roadmap/backlog and V1.2 specification. Phases 0–9 follow the controller-defined boundaries. Within each phase, existing M0–M9 task IDs remain compatibility references; requirement IDs remain unchanged.

Each phase runs: scope and trace review; atomic task implementation; static, unit, API/integration, frontend, E2E, visual, i18n, permission/security and migration/rollback checks as applicable; trace and diff review; up to five repair rounds; gate report; checkpoint commit; status update; automatic transition.

Phase 0 produces normalized specifications and ADRs only. Phase 1 bootstraps reproducible tooling without business DocTypes. Phase 2 establishes the Frappe app, API/security/audit/job foundations. Phase 3 establishes the React industrial shell, local UI adapter and Frappe-compatible trilingual chain. Phases 4–7 deliver project/gates, design/EBOM, tooling/capacity/import/export, and trial/readiness/Released Trial Summary vertical slices. Phase 8 delivers Mock and sandbox-ready ERP/JCE integration and read-only projection contracts only. Phase 9 delivers change, portfolio/reporting, generic Data Exchange/export/print hardening, migration rehearsal, operations and UAT. Under the user-approved `USER_APPROVED_POST_V1_2_DEFERRED` decision, Phase 9 and final V1.2 completion exclude only FR-CO-003/004 external login/identity/self-service submission/approval UI and portal API. Internal supplier milestones and observations, customer approval evidence and exact version locks, Project/Gate/Trial/Readiness effects, permissions/audit, notification foundation and ERP read-only projections remain required V1.2 scope.

The additive R1 reconciliation bridge is inserted after the recoverable P5-01 backend checkpoint. R1-01 first reconciled the 229 DOCX IDs, 39 Pack-only IDs and 13 then-known clarification IDs without product runtime code. The append-only R1-05 re-anchor adds the user-approved `FR-UX-043`, producing 14 clarification IDs and a 282-row current trace without relabelling historical evidence. Accepted shared UX, LaunchFlow display-brand, controlled-undo/prototype governance and additive 1440×900 trilingual visual remediation then pass a Level 3 bridge gate before the unfinished P5-01 frontend/runtime/i18n slice resumes. Pending Class-B decisions pause only their dependent behavior.

No phase may claim PASS with fake success, placeholders in accepted paths, failed applicable checks, permission bypass, cross-database access, dual-master editing, undocumented migration, Desk-dependent user flows, visual violations, missing core translations, or mixed-language defects.

The FR-CO-003/004 IDs, P1 priorities, authoritative source text, canonical
trace and historical `REMAPPED_PHASE_9` status remain unchanged; the deferral
marker is a decision, not an implementation or waiver status. Restoration is
a separate post-V1.2/future-release controller entry and requires an approved
external identity topology, tenant/Project authorization, file/evidence and
externally binding approval policy, notification/privacy/security threat model,
rollback, tests and release-gate plan. V1.2 cannot claim either portal
implemented, while its final release gate may pass without those exact external
surfaces only if every retained internal collaboration boundary passes.
