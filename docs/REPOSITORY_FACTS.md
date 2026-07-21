# Repository and Runtime Facts

On 2026-07-21 the repository was a greenfield Git repository on `main` with only two untracked inputs: the V1.2 ZIP and DOCX. No Frappe, ERPNext, React, database, Redis, CI or application code existed. Work moved to `codex/npi-v1.2-implementation` before writes.

The ZIP passed archive and SHA-256 checks. Its root contains 45 specified files plus directories. `rg` is absent, so discovery uses `find`/`grep`. Production ERPNext topology, credentials, version and customizations are unknown by design; no production connection is permitted. Phase 1 must establish executable version pins and commands rather than infer them.

Target repository roots are `apps/npi_core`, `apps/npi_integration`, `frontend`, `contracts`, `design`, `docs`, `implementation` and `.agents/skills`. The machine-readable contracts already exist; runtime and CI do not yet exist.
