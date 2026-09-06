---
name: frappe-safe-change
description: Implement or review Frappe changes safely without patching core, leaking Desk as the product UI, weakening permissions or creating unsafe migrations. Use for backend, DocType, hook, job and migration work.
---

# Frappe Safe Change

## Rules
- Independent custom app/site; no Frappe or ERPNext core edits.
- DocType persistence is allowed, but expose business commands/queries through explicit NPI APIs.
- Validate permissions server-side for every whitelisted method.
- Use background jobs for long operations and surface operation status.
- Use transactions and Outbox for domain changes that emit integration events.
- Submitted/released/approved records must not be mutable without controlled revision/reopen.
- Fixtures and patches must be idempotent.
- Avoid unrestricted `ignore_permissions`, `frappe.db.sql`, and dynamic method invocation.
- Do not log secrets or full sensitive payloads.
- Desk views are admin/support only unless a task explicitly says otherwise.

## Migration checklist
- compatible read/write window;
- index and lock impact;
- backfill strategy;
- retry/idempotency;
- forward-fix/rollback;
- test on production-like volume;
- no hidden destructive default.

## Verification
Run the actual repository formatter, lint, unit tests, migration test and permission tests. Report exact commands/results.
