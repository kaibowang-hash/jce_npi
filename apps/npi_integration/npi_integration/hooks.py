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
    ]
}

# These resolvers are inert unless the fixed disposable-runtime marker and
# explicit process environment are both present. They never read production
# endpoints or persist raw webhook secrets.
npi_inbound_project_profile_resolver = (
    "npi_integration.inbound_project.runtime_fixture.resolve_profile"
)
npi_inbound_project_secret_resolver = (
    "npi_integration.inbound_project.runtime_fixture.resolve_secret"
)

# P8-03 remains inert outside the explicit disposable runtime marker. The
# registry contains only the network-free synthetic operation adapter; no
# Sandbox or production endpoint, credential, method, or field mapping exists.
npi_item_publish_profile_resolver = (
    "npi_integration.item_publish.runtime_fixture.resolve_profile"
)
npi_item_publish_adapter_registry = (
    "npi_integration.item_publish.runtime_fixture.resolve_adapter_registry"
)

# P8-04 is inert outside its explicit disposable marker. The only built-in
# adapter is a network-free synthetic batch proof with no formal target IDs.
npi_mbom_publish_profile_resolver = (
    "npi_integration.mbom_publish.runtime_fixture.resolve_profile"
)
npi_mbom_publish_adapter_registry = (
    "npi_integration.mbom_publish.runtime_fixture.resolve_adapter_registry"
)

# P8-05 is inert outside its exact disposable marker. The registry contains
# only operation-specific, network-free synthetic create/update adapters.
npi_tool_asset_execution_profile_resolver = (
    "npi_integration.tool_asset_request.runtime_fixture.resolve_profile"
)
npi_tool_asset_adapter_registry = (
    "npi_integration.tool_asset_request.runtime_fixture.resolve_adapter_registry"
)

# P9-01C is likewise inert outside its exact disposable marker. The built-in
# profile has one network-free adapter and one ephemeral test-only signing key;
# production profiles, endpoints and credentials are deliberately absent.
npi_engineering_change_profile_resolver = (
    "npi_integration.engineering_change.runtime_fixture.resolve_profile"
)
npi_engineering_change_secret_resolver = (
    "npi_integration.engineering_change.runtime_fixture.resolve_secret"
)
npi_engineering_change_adapter_registry = (
    "npi_integration.engineering_change.runtime_fixture.resolve_adapter_registry"
)
