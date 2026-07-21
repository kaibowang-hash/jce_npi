app_name = "npi_core"
app_title = "NPI Core"
app_publisher = "NPI One"
app_description = "NPI One domain and security foundation"
app_email = "engineering@example.invalid"
app_license = "MIT"
required_apps = []

# Desk is intentionally limited to administration and support.
has_website_permission = {"NPI Audit Event": "npi_core.permissions.deny_public_access"}
