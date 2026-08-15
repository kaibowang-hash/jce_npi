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
