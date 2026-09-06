app_name = "npi_integration"
app_title = "NPI Integration"
app_publisher = "NPI One"
app_description = "Reliable NPI One integration foundation"
app_email = "engineering@example.invalid"
app_license = "MIT"
required_apps = ["npi_core"]

# Local read-only consumer injection. This hook resolves only NPI One's
# persisted projection heads; it does not configure or contact ERPNext.
npi_erp_projection_reader_factory = (
    "npi_integration.projections.frappe_repository.projection_reader_factory"
)

# P9-04 interactive authorization remains inert until its Site policy is
# explicitly enabled. The resolver reads only the local ERP-owned projection.
npi_authorization_projection_resolver = (
    "npi_integration.authorization_projection.frappe_repository."
    "resolve_authorization_projection"
)

# P8-02 recovery is deliberately operation-specific and bounded. It only
# requeues pending receipts or processing receipts whose claim lease expired.
scheduler_events = {
    "all": [
        "npi_integration.inbound_project.worker.recover_inbound_project_receipts",
        "npi_integration.item_publish.worker.recover_item_publish_outbox_messages",
        "npi_integration.mbom_publish.worker.recover_mbom_publish_outbox_messages",
        "npi_integration.tool_asset_request.worker.recover_tool_asset_outbox_messages",
        "npi_integration.engineering_change.worker.recover_engineering_change_work",
        "npi_integration.trial_summary_publish.worker.recover_trial_summary_deliveries",
        "npi_integration.project_publish.worker.recover_project_publish_requests",
    ]
}

# Every immutable technical summary gets an Outbox row in the same transaction.
# The hook never contacts ERPNext; the background worker remains inert until an
# exact non-production Sandbox profile and credential reference are configured.
doc_events = {
    "NPI Engineering Project": {
        "after_insert": (
            "npi_integration.project_publish.service.queue_engineering_project"
        )
    },
    "NPI Released Trial Summary Revision": {
        "after_insert": (
            "npi_integration.trial_summary_publish.service."
            "queue_released_trial_summary"
        )
    }
}

# These resolvers are inert unless the fixed disposable-runtime marker and
# explicit process environment are both present. They never read production
# endpoints or persist raw webhook secrets.
npi_inbound_project_profile_resolver = (
    "npi_integration.inbound_project.connector_runtime.resolve_profile"
)
npi_inbound_project_secret_resolver = (
    "npi_integration.inbound_project.connector_runtime.resolve_secret"
)

# P8-03 remains inert outside either the explicit disposable marker or an exact
# non-production Site profile. The connector runtime preserves the synthetic
# proof and adds one closed, authenticated Item Sandbox operation. Credentials
# are injected by opaque environment reference and never stored in Site config.
npi_item_publish_profile_resolver = (
    "npi_integration.item_publish.connector_runtime.resolve_profile"
)
npi_item_publish_adapter_registry = (
    "npi_integration.item_publish.connector_runtime.resolve_adapter_registry"
)

# P8-04 preserves the disposable synthetic proof and adds one exact,
# default-disabled non-production ERPNext Sandbox adapter.
npi_mbom_publish_profile_resolver = (
    "npi_integration.mbom_publish.connector_runtime.resolve_profile"
)
npi_mbom_publish_adapter_registry = (
    "npi_integration.mbom_publish.connector_runtime.resolve_adapter_registry"
)

# P8-05 preserves the disposable synthetic proof and adds exact,
# default-disabled non-production ERPNext Sandbox create/update adapters.
npi_tool_asset_execution_profile_resolver = (
    "npi_integration.tool_asset_request.connector_runtime.resolve_profile"
)
npi_tool_asset_adapter_registry = (
    "npi_integration.tool_asset_request.connector_runtime.resolve_adapter_registry"
)

# P9-01C preserves its exact disposable proof and adds one default-disabled,
# authenticated non-production ERPNext summary adapter and inbound signing-key
# resolver. Endpoint and credential values remain outside source control.
npi_engineering_change_profile_resolver = (
    "npi_integration.engineering_change.connector_runtime.resolve_profile"
)
npi_engineering_change_secret_resolver = (
    "npi_integration.engineering_change.connector_runtime.resolve_secret"
)
npi_engineering_change_adapter_registry = (
    "npi_integration.engineering_change.connector_runtime.resolve_adapter_registry"
)
