# P4-03 Takeover Reconciliation

Status: **EVIDENCE_CONFIRMED**

Reconciled: `2026-07-25T05:32:32Z`

Branch: `codex/npi-v1.2-implementation`

P4-03 final commit:
`0fd4762a01fd10fe6851df07ead1c5e4e7a42473`

Takeover starting remote HEAD:
`df8ccae3f87ff3afbf4d06696f4a69ca91de92d9`

Reviewed committed range:
`0fd4762a01fd10fe6851df07ead1c5e4e7a42473...df8ccae3f87ff3afbf4d06696f4a69ca91de92d9`

## Evidence integrity

- The P4-03 commit exists and is an ancestor of the takeover HEAD.
- `implementation/evidence/phase-4/p4-03-validation.md` has the same Git blob
  at P4-03 and at the takeover HEAD:
  `7272e5e9b5f0c99416ad9aef41becfd144b16f1d`.
- Its Level 3 result remains a bounded P4-03 `PASS`; it does not claim Gate
  decisions, production approval policy, waiver, reopen, invalidation, future
  evidence resolvers, uploads, or production scanner/ERP behavior.
- The `FR-SG-001`, `FR-SG-002`, `FR-SG-004`, and `FR-CO-006` trace rows point
  to existing source, tests, runtime verifiers, and the unchanged P4-03
  validation evidence.
- No P4-03 Gate Template implementation or controlled File Revision/Evidence
  DocType was deleted. No evidence was found of fabricated results, removed
  tests, weakened permission checks, or rewritten P4-03 history.

## Changed files to affected P4-03 tests

| Post-P4-03 change | P4-03 effect | Reconciliation |
|---|---|---|
| `gate_template/**` and Gate Template DocTypes | No change | Reuse P4-03 evidence; no rerun |
| `gate_evidence/frappe_repository.py` | Review dependency refresh after controlled evidence changes and exact requirement `globalId` projection | 46 direct P4-02/P4-03 repository/controller/metadata tests passed |
| Gate Shell controller/metadata, hooks, transport role | Adds review-state/version and command-transport boundaries around the shared Gate aggregate | Gate Review/Gate Shell and metadata tests passed |
| OpenAPI/BFF | Adds the review service and requires exact evidence requirement identity | Gate Evidence contract plus Gate Review contract tests passed |
| Gate evidence/review data sources and live Gate route | The accepted route now embeds P4-03 evidence in the P4-04 Review Room | Direct parser/page tests and bounded live Gate E2E passed |
| Shared session, i18n, catalogs, and Review Room visuals | Changes current Gate rendering without changing the frozen P4-03 evidence model | Generation/type/i18n checks, 72 live Gate cases, and 23 exact Review Room visuals passed |

## Targeted regression result

No P4-03 full Gate was repeated. In particular, `make verify`, the historical
153-case E2E set, and the 159-case visual matrix were not rerun.

| Check | Result |
|---|---|
| P4-02/P4-03 repository/controller/metadata boundary | `PASS — 46/46` |
| Gate Evidence contract plus current Gate Shell boundary | `PASS — 11/11` |
| Gate Review Python affected suite | `PASS — 123/123` |
| Evidence parser, review parser, and Review Room component lane | `PASS — 116/116`, including `18/18` direct Gate Evidence parser cases |
| Current live Gate Review/Evidence non-visual spec | `PASS — 72/72` |
| Current affected Review Room exact visual comparison | `PASS — 23/23` at zero pixel tolerance |
| Generated artifacts, TypeScript, and direct Chinese catalogs | `PASS — 1742` literal English sources with complete `zh`/`zh-TW` coverage |
| Representative original-resolution review | `PASS` for normal Simplified Chinese, no-permission Simplified Chinese, and high-risk Traditional Chinese confirmation |
| Prohibited-pattern scan and `git diff --check` | `PASS` |

The current focused Frappe runtime retry did not start because the local
MariaDB container was stopped and Docker reported a stale OCI task while
restoring it. The last committed focused runtime remains valid for the P4-03
surface. The current File-delete invalidation runtime case is P4-04 acceptance
work and remains explicitly pending; it does not falsify or reopen the
unchanged P4-03 evidence.

## Conclusion

P4-03 remains `PASS` and its evidence is **EVIDENCE_CONFIRMED**. Shared
post-P4-03 surfaces received bounded regression coverage. There is no evidence
for `REOPEN_REQUIRED`, and no reason to repeat the P4-03 Level 3 Gate.
