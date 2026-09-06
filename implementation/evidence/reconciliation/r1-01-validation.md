# R1-01 Validation — DOCX / Pack Reconciliation and Machine Trace

Result: `PASS — LEVEL 2 DOCUMENTATION/TRACE/TOOLING TASK GATE`

Date: 2026-07-25

Starting synchronized product checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

## Delivered boundary

- Extracted 229 unique DOCX requirements with exact family counts.
- Extracted 43 unique Tooling List source-column mappings.
- Reproduced the accepted pre-reconciliation inventory:
  173 Pack IDs, 134 same IDs, 95 DOCX-only IDs and 39 Pack-only normalized
  IDs.
- Added 13 clarification IDs and produced one 281-ID trace:
  173 `PACK_CANONICAL`, 95 `DOCX_RECONCILED`, 13 `ADDENDUM_DIRECT`.
- Fixed coverage evidence to immutable checkpoint `930b5a2` and locked the
  exact original 173-ID set digest.
- Allocated every partial/isolated UX ID to a concrete R1, Phase 6/7/8 or
  final-UAT task. Thirty equivalent UX/I18N aliases and 34 ARCH/COD governance
  rows are explicit non-blocking links rather than false implementation
  claims.
- Added the accepted addendum, decision requests, Tooling import specification,
  roadmap/backlog/acceptance/domain/UX amendments and recovery errata without
  rewriting historical Gates.
- Added the bounded `xlsx-tooling-import` Skill, passive inspector and
  adversarial tests.
- Registered the exact supplied brand CSV/five-SVG package as the only future
  brand-development source.
- Preserved the package byte-for-byte with a directory-scoped Git binary
  attribute, including the source CSV BOM/CRLF bytes required by its locked
  SHA-256.

No frontend/backend product runtime, BFF route, OpenAPI, event schema, DocType,
database migration, data-ownership contract, translation allowlist or external
integration behavior changed.

## Deterministic reconciliation checks

Command:

```text
python scripts/verify_v1_2_reconciliation.py
```

Result: `PASS`.

This command independently runs all generated-artifact freshness checks and
then validates:

- 229/43/281 unique-key cardinalities;
- ten accepted coverage category counts;
- 173/95/13 trace-kind counts;
- the exact 173-ID Pack set SHA-256;
- exact canonical-ID mappings;
- the immutable pre-reconciliation checkpoint on every coverage row;
- 13 exact UX remediation phase/status allocations;
- 30 linked UX/I18N aliases, 34 ARCH/COD governance rows and 18 Phase 6
  Tooling rows;
- all 13 addendum IDs; and
- exact brand filenames, CSV instructions, SHA-256 values and self-contained
  passive SVG structure.

## Focused automated checks

```text
python -m unittest \
  tests.test_v1_2_reconciliation \
  tests.test_xlsx_tooling_import_skill -v
```

Result: `PASS — 16/16`.

The 13 XLSX safety cases cover:

- cell-error value redaction;
- external relationships;
- archive traversal, duplicate/canonical collisions and CRC failure,
  including an unreferenced member;
- VBA/XLM/macro-enabled content, ActiveX and orphan binary parts;
- ASCII and UTF-16 DTD/entity declarations;
- input-size and drawing-anchor bounds; and
- the accepted passive structural report.

## Skill and Python quality

```text
uv run --with pyyaml python \
  /home/vscode/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/xlsx-tooling-import
```

Result: `PASS — Skill is valid`.

```text
black --check <seven reconciliation/skill/test Python files>
flake8 --ignore=E501,W503,E704 <same files>
bandit -q .agents/skills/xlsx-tooling-import/scripts/inspect_xlsx.py
python -m py_compile <same files>
```

Result: `PASS`.

Independent adversarial forward testing also returned structured CLI rejection
with exit 2 and no traceback for macro/XLM/ActiveX, arbitrary cached error
values, external links, traversal/symlink/collisions, ASCII/UTF-16 DTD/entity,
CRC damage, XML depth, input size and oversized drawing anchors.

## Repository structure and evidence checks

```text
uv run --with pyyaml python <safe-load every repository YAML file>
git diff --check
test -z "$(git diff --name-only -- implementation/evidence/phase-4)"
```

Result: `PASS`.

The unrelated regenerated Phase 4 Playwright report was backed up to
`/tmp/r1-01-unrelated-playwright-report-index.html` and restored to HEAD before
the Gate. Existing Phase 3/4/P5-00 evidence was not altered.

`git check-attr` confirms the supplied brand directory is `-text`/`-diff`, so
`git diff --check` passes without rewriting the sole-source CSV or SVG bytes.

Product tests, migrations, Frappe runtime, frontend build, i18n extraction,
browser and visual matrices were not rerun: R1-01 changes only
specification/trace/planning metadata and offline reconciliation tooling.
R1-02 and later shared Shell/i18n work carry their affected and eventual
Level 3 bridge checks.

## Decision and rollback review

- DR-REC-001..010 remain scoped to their dependent behavior.
- No Tooling state machine, production column semantics, tolerance,
  destructive rollback, controlled form/signature rule, JCE display asset or
  Trial Summary event identity was invented.
- R1-01 can be reverted before downstream adoption. Once later tasks depend on
  these IDs, corrections use another additive reviewed crosswalk; original IDs
  and historical Gate evidence are never deleted or rewritten.

## Transition

R1-01 is complete. Activate only:

`R1-02 — LaunchFlow display brand adapter and exact supplied assets`

P5-01 remains checkpointed/held. R1-07 remains scoped to DR-REC-001. P5-01
cannot resume until the shared R1 Shell/design/i18n Level 3 bridge Gate passes.
