# V1.2 Reconciliation Decision Requests

Date: 2026-07-25

These are Class-B decisions from the accepted reconciliation. Each hold is
scoped to its dependent requirement; none authorizes a guessed default.

| ID | Decision | Options and impact | Recommendation | Current state / dependency |
|---|---|---|---|---|
| DR-REC-001 | My Work detail interaction | A: retain right inspector everywhere; B: inline expansion in My Work only with drawer/Object Page fallback; C: replace inspectors globally. | B preserves queue context without weakening sustained engineering workspaces. | `PENDING_PRODUCT_OWNER`; blocks FR-UX-042 only. |
| DR-REC-002 | Variance exception color | A: every non-zero difference is abnormal; B: only outside a versioned tolerance is abnormal; C: per-metric policy chooses A/B. | C with B as the safe common policy; never infer a tolerance. | `PENDING_PRODUCT_OWNER`; blocks final FR-TX-020 visual semantics. |
| DR-REC-003 | Controlled paper forms and wet signatures | Select exact forms, document owners, required signers, wet/electronic signature and retention rules. | Start with generic snapshot/registry infrastructure; enable no controlled form without its approved mapping. | `PENDING_BUSINESS_POLICY`; blocks FR-PRN-003 forms, not FR-PRN-001/002 foundation. |
| DR-REC-004 | Print delivery/copy numbering | A: controlled PDF only; B: PDF plus browser print; C: B plus numbered controlled copies. | A until copy-control policy exists. | `PENDING_PRODUCT_OWNER`; blocks browser/direct-copy claims. |
| DR-REC-005 | Icon sources | A: existing iX/company adapters and supplied company brand assets; B: add Octicons through dependency/license ADR. | A. | `RESOLVED_BY_CURRENT_PACK_AND_USER_ASSET_RULE`; Octicons are not approved. |
| DR-REC-006 | ERP/JCE display identity | Supply approved display text, icon package, usage rules and legal wording, or retain current ERPNext display identity. | Retain stable `ERPNEXT` internal identity and current display until an approved package exists. | `PENDING_EXTERNAL_ASSET`; blocks FR-BR-002 only. |
| DR-REC-007 | Tooling List value semantics | Classify each relevant source column as Customer Standard, estimate, TP measured actual or calculated result, including effectivity. | Approve a versioned mapping overlay; never infer from column names alone. | `PENDING_BUSINESS_DATA_OWNER`; blocks formal import mapping activation, not parser/provenance work. |
| DR-REC-008 | Import rollback cutoff | Define whether rollback is allowed after downstream references, approvals, trials, exports or integrations. | Allow only unused-batch rollback; otherwise preserve history and use forward correction. | `PENDING_BUSINESS_POLICY`; destructive downstream rollback remains denied. |
| DR-REC-009 | Released Trial Summary contract and event identity | Approve the exact release authority, event type, payload version, redaction rules and ERP/JCE consumer mapping. Repository event types use dotted names; the report's illustrative `trial_summary_released` string is not adopted as a contract value. | Prepare an NPI-owned immutable snapshot and use a dotted candidate such as `trial_summary.released` only after the Phase 7/8 contract review. | `PENDING_INTEGRATION_CONTRACT`; blocks the exact event and external projection, not the NPI-owned snapshot model. |
| DR-REC-010 | Distinct Tooling lifecycle policies | Approve exact state codes, transitions, skip/reopen/terminal rules and authority for Tooling Requirement, Tooling Revision and each physical Tooling Set. | Keep the three state machines independent and versioned; retain only invariant separation until the Phase 6 policy is approved. | `PENDING_PRODUCT_OWNER`; blocks formal lifecycle commands, not identity, applicability, provenance or parser work. |

## Brand facts resolved by the supplied package

- `docs/Brand Asset/Brand Asset Instruction.csv` and the exact five SVGs in
  that folder are the sole brand-asset authority.
- LaunchFlow display-brand work may proceed within those exact usage scopes.
- No JCE Core asset or legal display text was supplied. Codex must not create,
  search for or substitute one.
- The supplied assets do not authorize a second visual design system or a
  change to the approved industrial teal/neutral UI tokens.
