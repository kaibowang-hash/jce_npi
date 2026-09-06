---
name: repo-discovery
description: Inspect the repository, runtime, CI, Frappe/ERPNext apps, tests, migrations and evidence before planning or changing NPI One. Use in M0 and whenever facts about the existing codebase are needed.
---

# Repository Discovery

## Trigger
Use before architecture decisions, scaffolding, migrations, CI changes or claims about existing capabilities.

## Steps
1. Read root and nearest `AGENTS.md`.
2. Inventory repository roots, languages, package managers, framework versions and app/site structure.
3. Find authoritative run/test/build commands from config and CI; do not invent.
4. Locate Frappe apps, `hooks.py`, `modules.txt`, DocType JSON/Python/JS, patches, fixtures, permissions, whitelisted methods, webhooks and background jobs.
5. Locate frontend entry points, design system, routing, state/data fetching, tests and build outputs.
6. Locate integration code, credentials references, queues, event schemas, mapping and observability.
7. Produce:
   - facts with file/line evidence;
   - unknowns;
   - risks;
   - commands actually executed and results;
   - no-code recommended next step.

## Guardrails
- M0 is read-only except agreed documentation output.
- Do not run destructive migrations or connect to production.
- Do not infer production topology from local compose files alone.
- Do not state a test passes without running it.
- Redact secrets and personal data.
