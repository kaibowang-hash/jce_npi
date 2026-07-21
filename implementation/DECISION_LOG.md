# Decision Log

| Date | Decision | Basis | Reversible / rollback |
|---|---|---|---|
| 2026-07-21 | `GOAL.md` is the sole canonical goal entry; no duplicate `00_GOAL.md`. | Controller compatibility rule | Yes; index-only decision |
| 2026-07-21 | Use controller Phases 0–9 and map Pack M0–M9 tasks into them. | Higher-priority instruction | Yes; trace mapping can evolve |
| 2026-07-21 | Target Frappe v15 LTS-compatible custom app and CSV translations until executable environment verification; pin exact patch in Phase 1. | Stability and Pack localization guidance | Yes; upgrade via ADR/migration |
| 2026-07-21 | React 18 + TypeScript + Vite; local `npi-ui` adapter around Siemens iX Classic Light. | Required architecture and replaceability | Yes; adapter isolates library |
| 2026-07-21 | MariaDB and Redis use isolated local containers; browser uses NPI BFF only. | Frappe compatibility and security boundary | Yes; compose teardown/volume backup |
| 2026-07-21 | ERP integration defaults to Mock; sandbox requires explicit URL/credentials; production endpoints are rejected. | Controller prohibition | Yes; configuration-only activation |

