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

# P8-02 recovery is deliberately operation-specific and bounded. It only
# requeues pending receipts or processing receipts whose claim lease expired.
scheduler_events = {
    "all": [
        "npi_integration.inbound_project.worker.recover_inbound_project_receipts"
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
