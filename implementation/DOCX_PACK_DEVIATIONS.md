# DOCX / Execution Pack Deviations

Date: 2026-07-21  
Decision: The repository V1.2 Execution Pack is the sole machine-execution baseline. The V1.2 DOCX is supplementary background and cannot enlarge or override the current Pack scope.

| Area | DOCX content | Pack content | Current decision | Future human review | Current code impact |
|---|---|---|---|---|---|
| Phase numbering | The DOCX places the platform/experience shell in its Phase 1, the first vertical slice in Phase 2, and Project/Gate/collaboration in Phase 3. | `implementation/EXECUTION_PLAN.md` defines controller Phase 3 as the React industrial App Shell, Siemens UI adapter, and i18n foundation; business Project/Gate work is Phase 4. | Use Pack controller phases. | Yes, documentation crosswalk only. | None; do not add Phase 4 business logic to Phase 3. |
| Requirement identifiers | The DOCX annex uses `UX-*`, `ARCH-*`, `FR-TX-*`, `COD-*`, and `I18N-*` families. | The Pack assigns `FR-UX-001..037`, `NFR-UX-001..002`, and `NFR-LOC-001..002` to Phase 3. | The 41 Pack-traced IDs are the complete current acceptance scope. | Yes, create a later trace crosswalk. | None beyond Pack requirements. |
| Requirement counts | The DOCX states 229 requirements; extraction and Pack normalization produce different counts. | `implementation/REQUIREMENT_TRACEABILITY.csv` contains the normalized Pack inventory. | Do not use count differences as a Gate or add missing DOCX-only work. | Yes, editorial/trace reconciliation. | None. |
| DOCX-only requirements | The DOCX contains requirements not represented in the Pack's Phase 3 trace. | The Pack does not assign those items to current implementation. | Keep them out of Phase 3. | Yes, product-owner review for a future Pack revision. | None; implementation is forbidden unless added to a future approved Pack. |
| Screenshot dimensions | DOCX visual evidence references 1440×900 and 1920×1080. | `industrial-ux`, Pack visual baseline, and acceptance rules require 1366×768 and 1920×1080, including 125%/150% zoom. | Use only the Pack matrix for the current Gate. | Optional after Phase 3. | Tests and screenshots target the Pack matrix. |
| Phase 3 scope wording | DOCX Phase 3 language includes Project/Gate/collaboration capability. | Pack Phase 3 is UI shell/i18n foundation and prototype states; formal Project/Gate behavior starts later. | Implement shell and Pack-defined states only, without business persistence or workflow rules. | Yes, during later business-phase planning. | Prevents premature Project/Gate domain implementation. |

## Recording rule

Future DOCX/Pack differences must be appended here with the same six fields. A DOCX difference alone is not a blocker. A conflict between Pack files remains a blocker and must be reported without silently choosing one source.
