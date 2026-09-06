# ERPNext Released Trial Summary Connector Runbook

Status: implementation complete for contract, migrations, local Outbox,
Sandbox transport, ERPNext receiver, read-only projection, query APIs and
historical backfill. Production activation is not authorized by this runbook.

Requirement: `FR-INT-015`

## Business result

Every immutable `NPI Released Trial Summary Revision` creates one delivery in
the same NPI One transaction. ERPNext stores one immutable summary header and
its flattened, filterable facts. Later summary revisions append new ERPNext
rows; they never overwrite an earlier Trial record.

The projection includes the exact released summary's:

- Trial input changes and actual process parameters;
- sample batches and cavity-level results;
- Trial and Tooling defects, actions and verification evidence;
- round comparison facts, controlled references and blockers; and
- conclusion, exact source references, source versions and hashes.

The ERPNext copy is engineering evidence only. It has
`formal_mp_acceptance = 0` and does not create or update Quality Inspection,
DMR, NCR, CAPA, Gate, production-acceptance or Tooling-acceptance truth.

## End-to-end flow

1. An authorized NPI One user retains or revises an immutable Released Trial
   Summary after the Trial conclusion is decided.
2. The summary insert hook appends `NPI Trial Summary Delivery` in the same
   database transaction. A rollback removes both; a committed summary cannot
   exist without its delivery row.
3. After commit, the worker binds the exact non-production execution profile,
   appends a numbered attempt, commits the adapter boundary and sends the
   closed `publish_released_trial_summary` command over HTTPS.
4. ERPNext authenticates the dedicated Website User, its service role and the
   HMAC signature, validates the closed payload and hashes, then atomically
   inserts:
   - `NPI ERP Trial Summary`; and
   - one `NPI ERP Trial Summary Fact` per released fact.
5. ERPNext returns a signed receipt containing the exact summary revision ID
   and fact count. NPI One accepts success only when both equal the released
   source.
6. Pre-boundary or authenticated `429/5xx` failures can retry with the same
   idempotency identity. A timeout or unverifiable response after the adapter
   boundary becomes `uncertain` and cannot be redispatched directly.
7. Reconciliation asks ERPNext for the signed idempotency receipt. A matching
   receipt seals success; an authenticated absent receipt permits one safe
   redispatch; a conflicting receipt fails closed.
8. The NPI migration creates missing delivery rows for every historical
   Released Trial Summary without contacting ERPNext. The recovery scheduler
   processes them only after an execution profile is explicitly enabled.

MP conversion is not the copy trigger. The immutable summary release is the
trigger, so the evidence is available before MP and remains queryable after
MP. This avoids making an ERP production state responsible for NPI evidence
retention.

## ERPNext lookup

Assign `NPI ERP Trial Summary Viewer` only to users who may read the projected
engineering evidence. `System Manager` also has read access. Neither role can
create, edit, rename or delete projection rows through these DocTypes.

In ERPNext Desk:

1. Open the `NPI ERP Trial Summary` list from search.
2. Filter by Project Global ID, Trial Round Global ID, conclusion state,
   conclusion code or source date.
3. Open the summary to inspect the exact projection and source hashes.
4. Open `NPI ERP Trial Summary Fact` and filter by Summary Revision Global ID,
   Project Global ID, Trial Round Global ID, fact type, fact key or value
   state. Use `trial_defect` or `tooling_defect` to list defect rows.

The permission-checked read APIs are:

- `npi_erpnext_connector.trial_summary_api.list_trial_summaries`
- `npi_erpnext_connector.trial_summary_api.get_trial_summary`
- `npi_erpnext_connector.trial_summary_api.list_trial_defects`

All collection APIs use deterministic ordering and `start`/`limit` pagination
with a maximum page size of 100. Detail is bounded to 25,000 facts.

## NPI One operations lookup

System Managers use these Project-scoped BFF routes; raw endpoints,
credentials and provider bodies are never returned:

- `GET /api/npi/v1/projects/{projectId}/trial-summary-deliveries`
- `GET /api/npi/v1/projects/{projectId}/trial-summary-deliveries/{deliveryId}`
- `POST .../{deliveryId}:retry`
- `POST .../{deliveryId}:request-reconciliation`

Delivery states are `pending`, `processing`, `succeeded`,
`failed_retryable`, `failed_final` and `uncertain`. Attempt history records the
boundary, authenticated/contract-valid response flags, bounded error code,
trace ID and timestamps.

## Configuration and activation order

Both sides are default closed. Use only an approved non-production Site for
the current adapter.

1. Install or upgrade `npi_erpnext_connector` and migrate the ERPNext Site.
2. Create a dedicated enabled Website User with only
   `NPI ERP Trial Summary Integration Service`; give human readers only
   `NPI ERP Trial Summary Viewer`.
3. Supply the ERPNext switch
   `npi_erp_trial_summary_receiver_disabled = false` only after receiver tests
   and role review pass.
4. Install or upgrade `npi_integration` and migrate the NPI One Site. This
   creates both delivery DocTypes and backfills missing Outbox rows without
   network activity.
5. Configure one exact entry in
   `npi_trial_summary_erp_sandbox_profiles`, then set
   `npi_trial_summary_erp_sandbox_enabled = true`.
6. Inject the API key/secret through the process environment variable
   `NPI_TRIAL_SUMMARY_ERP_SANDBOX_SECRETS`, keyed by the profile's opaque
   `secretReference`. Never persist the secret in Site config, logs or Git.
7. Restart the affected non-production workers through the approved operating
   procedure, publish a representative summary, verify header/fact counts,
   replay, retry and reconciliation, then reconcile all historical deliveries.

The built-in profile parser accepts HTTPS origins whose environment and
hostname are explicitly non-production. It rejects IP literals, localhost,
credentials in URLs, redirects and production/live identifiers.

## Monitoring and recovery

- Alert on aged `pending`, expired `processing`, any `uncertain`, repeated
  `failed_retryable`, and all `failed_final` deliveries.
- Retry only `failed_retryable` or reviewed `failed_final` rows. Never retry an
  `uncertain` row before receipt reconciliation.
- Compare `source_hash`, `projection_id`, `fact_count`, `response_hash` and
  trace ID before closing an incident.
- If the target receipt conflicts with the source hash or identity, stop the
  operation and investigate; do not overwrite either side.

## Rollback

Disable the NPI sender switch and ERPNext receiver switch first. Preserve all
summary, delivery, attempt, projection and fact rows as audit evidence. Revert
application code through a reviewed forward release; do not delete immutable
history or attempt a schema downgrade. Production activation requires its own
approved change, backup, Sandbox/UAT evidence and rollback validation.
