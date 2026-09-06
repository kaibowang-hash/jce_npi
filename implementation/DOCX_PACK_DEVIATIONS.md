# DOCX / Execution Pack Deviations

Historical snapshot date: 2026-07-21

Historical decision: The repository V1.2 Execution Pack was treated as the
sole machine-execution baseline. This decision and the table below are retained
as evidence of the then-current Phase 3/P5 planning state. They were
`SUPERSEDED_FOR_REQUIREMENT_COMPLETENESS` by the accepted 2026-07-25 additive
reconciliation; they must not be used as current recovery instructions.

| Area | DOCX content | Pack content | Current decision | Future human review | Current code impact |
|---|---|---|---|---|---|
| Phase numbering | The DOCX places the platform/experience shell in its Phase 1, the first vertical slice in Phase 2, and Project/Gate/collaboration in Phase 3. | `implementation/EXECUTION_PLAN.md` defines controller Phase 3 as the React industrial App Shell, Siemens UI adapter, and i18n foundation; business Project/Gate work is Phase 4. | Use Pack controller phases. | Yes, documentation crosswalk only. | None; do not add Phase 4 business logic to Phase 3. |
| Requirement identifiers | The DOCX annex uses `UX-*`, `ARCH-*`, `FR-TX-*`, `COD-*`, and `I18N-*` families. | The Pack assigns `FR-UX-001..037`, `NFR-UX-001..002`, and `NFR-LOC-001..002` to Phase 3. | The 41 Pack-traced IDs are the complete current acceptance scope. | Yes, create a later trace crosswalk. | None beyond Pack requirements. |
| Requirement counts | The DOCX states 229 requirements; extraction and Pack normalization produce different counts. | `implementation/REQUIREMENT_TRACEABILITY.csv` contains the normalized Pack inventory. | Do not use count differences as a Gate or add missing DOCX-only work. | Yes, editorial/trace reconciliation. | None. |
| DOCX-only requirements | The DOCX contains requirements not represented in the Pack's Phase 3 trace. | The Pack does not assign those items to current implementation. | Keep them out of Phase 3. | Yes, product-owner review for a future Pack revision. | None; implementation is forbidden unless added to a future approved Pack. |
| Screenshot dimensions | DOCX visual evidence references 1440×900 and 1920×1080. | `industrial-ux`, Pack visual baseline, and acceptance rules require 1366×768 and 1920×1080, including 125%/150% zoom. | Use only the Pack matrix for the current Gate. | Optional after Phase 3. | Tests and screenshots target the Pack matrix. |
| Phase 3 scope wording | DOCX Phase 3 language includes Project/Gate/collaboration capability. | Pack Phase 3 is UI shell/i18n foundation and prototype states; formal Project/Gate behavior starts later. | Implement shell and Pack-defined states only, without business persistence or workflow rules. | Yes, during later business-phase planning. | Prevents premature Project/Gate domain implementation. |

## Recording rule

Future DOCX/Pack differences must be appended here with the same six fields. A
difference alone is not a global blocker. A material authority conflict pauses
only its dependent work and is reported without silently choosing a rule.

## 2026-07-25 accepted reconciliation resolution

| Measure | Accepted result |
|---|---:|
| Authoritative DOCX IDs | 229 |
| Pre-reconciliation Pack IDs | 173 |
| Same IDs | 134 |
| DOCX-only IDs | 95 |
| Pack-only normalized IDs | 39 |
| Addendum clarification IDs | 13 |
| Current trace union | 281 |

The pre-reconciliation assessment is reproducible at immutable checkpoint
`930b5a28cb995df12f251994a36f7502525ed94a`. Source paths in
`implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv` are interpreted at that
checkpoint, not at their later amended contents. The verifier also locks the
exact original 173-ID set digest.

Current resolutions:

- `UX-001..036`, `ARCH-001..012`, `FR-TX-001..018`, `COD-001..022` and
  `I18N-001..007` now have direct machine-trace rows. Alias rows link to
  normalized Pack IDs; they do not duplicate implementations.
- The controller keeps its established Phase numbering. Requirement/task
  placement is crosswalked in the amended backlog rather than renumbering
  historical evidence.
- Existing Phase 3/4/P5-00 Gate reports retain their original counts and
  conclusions. The 281-ID trace does not retroactively mark new aliases or
  acceptance deltas as implemented.
- 1440×900 is added to the future trilingual P0 visual matrix alongside
  1366×768 and 1920×1080. It does not invalidate the already accepted
  1366×768/1920×1080 evidence.
- The seven unique Tooling List gaps are scheduled into the specialized Phase
  6 import task with a safe inspection Skill, while production column
  semantics and rollback cutoffs remain scoped decisions.

## 2026-07-27 append-only FR-UX-043 correction

The user-approved 2026-07-26 amended plan contains `FR-UX-043`, but the
2026-07-25 repository addendum and generator predate that instruction. The ID
is appended as `P0`, Phase 5, `ADDENDUM_DIRECT`, self-canonical and allocated
to R1-05/UX-A3. The current union is therefore 282 IDs: 173
`PACK_CANONICAL`, 95 `DOCX_RECONCILED` and 14 `ADDENDUM_DIRECT`.

This corrects current machine coverage only. The historical 281-ID R1-01
checkpoint, its validation counts and every earlier Gate conclusion remain
unchanged.
