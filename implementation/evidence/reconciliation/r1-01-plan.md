# R1-01 Plan — DOCX / Pack Reconciliation and Machine Trace

Status: `COMPLETE — see r1-01-validation.md`

Date: 2026-07-25

Starting product checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

## Scope

- deterministically extract all 229 DOCX requirements and the 43-column
  Tooling mapping without re-authoring source text;
- reproduce the accepted pre-reconciliation 134/95/39 set relationship and
  ten coverage categories at the immutable starting checkpoint;
- retain the original 173 Pack rows, add 95 DOCX rows and 13 clarification
  rows with explicit `trace_kind`/`canonical_ids`;
- amend requirement, domain, UX, i18n, acceptance, roadmap, backlog,
  decision, risk, deviation, input and recovery documents;
- add a bounded passive XLSX Tooling inspector Skill and adversarial tests;
- register the supplied brand CSV and exact five SVGs as the sole
  brand-development source; and
- preserve every already accepted Phase 3/4/P5-00 and P5-01 checkpoint result.

## Non-scope

- no frontend/backend product runtime, BFF route, DocType, database migration,
  public API, event schema or external integration behavior;
- no production Tooling column semantics, lifecycle, tolerance, rollback,
  print/signature, My Work amendment, Trial Summary event or ERP/JCE brand
  decision;
- no product use of the supplied assets; that begins at R1-02;
- no change to `contracts/data-ownership.yaml` or the live translation
  allowlist; and
- no production ERPNext/JCE/CAD/PDM connection or credential.

## Accepted facts and assumptions

- The user-supplied reconciliation report is accepted as an additive Pack
  amendment.
- The DOCX and Pack source state are interpreted at the starting product
  checkpoint above.
- Reconciliation tooling is permitted even though product runtime code is
  prohibited.
- Alias traces do not constitute duplicate product requirements or inherited
  implementation claims.

## Class-B holds

`DR-REC-001..010` in
`implementation/V1_2_RECONCILIATION_DECISIONS.md` pause only their named
dependent behavior. In particular, exact Tooling state machines and the
illustrative underscored Trial Summary event name are not adopted.

## Risks

- generated trace drift or double counting;
- circular “pre-reconciliation” evidence after live specs are amended;
- sensitive XLSX content leaking through structural inspection;
- active/macro/external/corrupt XLSX content being accepted;
- brand assets being modified, substituted or used outside their CSV scope;
- historical Gate evidence being silently regenerated or relabelled; and
- remediation gaps entering the trace without executable task allocation.

## Planned change surface

- reconciliation/addendum/specification/plan/evidence Markdown and YAML;
- generated requirements, coverage, mapping and typed trace CSVs;
- deterministic extraction/generation/verification scripts;
- `.agents/skills/xlsx-tooling-import/` and focused tests;
- exact supplied `docs/Brand Asset/` files plus a directory-scoped binary
  attribute that prevents Git from normalizing their source bytes; and
- repository verification wiring.

Product app, frontend, OpenAPI, event schema, DocType and migration files are
not part of the task.

## Changed-files to affected-tests map

| Change family | Required checks |
|---|---|
| DOCX extraction / generated CSV | extraction `--check`; 229 unique IDs; exact family counts; 43 unique columns |
| coverage / typed trace | generation `--check`; 10 category counts; 173/95/13 kinds; 281 unique IDs; exact original Pack-ID digest; canonical mappings |
| brand package | exact file set, CSV rows, SHA-256 values, XML parse, no active/external SVG content |
| XLSX Skill / inspector | Skill validator; unit and CLI adversarial fixtures; compile; Black; flake8; Bandit |
| YAML / Markdown / recovery state | safe YAML parse; link/target and current-state assertions; `git diff --check`; independent diff review |
| historical evidence | tracked Phase 4 evidence hashes unchanged from HEAD |

## Task Gate and rollback

R1-01 uses a Level 2 documentation/trace/tooling Gate. Product runtime,
browser, migration, i18n extraction and visual matrices are not rerun because
their code and accepted evidence are unchanged.

Before downstream R1 work, rollback can revert this task checkpoint. After
later tasks depend on the typed IDs, use a reviewed forward addendum; never
erase original requirement IDs or rewrite historical Gate evidence.
