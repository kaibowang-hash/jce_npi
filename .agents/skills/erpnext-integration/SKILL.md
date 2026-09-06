---
name: erpnext-integration
description: Design, implement or review reliable NPI One to ERPNext integrations, shared-object ownership, execution requests, webhooks, idempotency, retry, replay and reconciliation.
---

# ERPNext Integration

## Required reading
- `docs/ERPNEXT_INTEGRATION.md`
- `contracts/data-ownership.yaml`
- `contracts/npi-api.openapi.yaml`
- `contracts/integration-event.schema.json`

## Rules
- No cross-database access.
- Browser never calls ERPNext directly.
- Use operation-specific ERP commands, not unrestricted generic DocType writes.
- Every write has idempotency key, expected version, actor, trace and input hash.
- Record execution separately from engineering approval.
- Webhooks validate signature, land in Inbox first and process idempotently.
- Classify retryable vs final errors; do not retry business validation blindly.
- Replay preserves original event/request identity and records replay identity.
- Reconciliation creates visible differences; never silently wins over sensitive fields.
- Field ownership changes require contract + ADR + migration.

## Test fault cases
duplicate event, reordered event, timeout after remote commit, 429, 5xx, business 4xx, partial batch success, expired credentials, stale mapping, target unavailable, worker restart, replay.
