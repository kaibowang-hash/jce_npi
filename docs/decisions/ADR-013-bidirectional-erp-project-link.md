# ADR-013 — Bidirectional ERP Project link without dual-master fields

Status: Accepted by the user's explicit 2026-09-06 instruction that Project integration must be bidirectional.

## Decision

Engineering Project remains NPI One-owned. Transport is bidirectional by source:

- ERPNext-origin Projects use the existing signed `erpnext.project.created` Inbox path and create one NPI draft.
- NPI-origin Engineering Projects transactionally create one `create_erp_project` execution request. ERPNext allocates its formal Project ID and returns an authenticated result.
- NPI's authenticated business user is stored as ERPNext `owner`/Created By. A separate least-privilege Website User authenticates transport and remains recorded on the receipt.
- Both directions use immutable mapping records. An ERP Project created from an NPI command is excluded from the ERPNext-origin sender, preventing a loop.
- Timeouts become `uncertain` and are reconciled by the original idempotency key before any repeat create.
- Project-scoped Item, MBOM, Tool Asset, Trial Summary and Engineering Change profiles may inherit one tenant template only after a durable ERP Project binding exists and only when all existing tenant profiles are identical except for profile and Project identity.

Field ownership does not become bidirectional: business code, engineering title/type, target SOP, Gate/lifecycle and health remain NPI-owned; ERPNext owns the formal Project ID and its formal execution records.

## Alternatives rejected

- Making ERPNext and NPI freely edit the same Project fields would create an unresolved dual-master conflict.
- Creating the ERP Project synchronously in the browser would bypass Outbox durability and expose ERP credentials.
- Reusing the ERPNext-origin source-binding receipt for an NPI-origin command would conflate two immutable provenance models.

## Rollback

Disable the NPI Project publication profile and the ERPNext Project publication receiver. Existing Project mappings and request/attempt/result evidence remain read-only. No ERP Project is deleted automatically.
