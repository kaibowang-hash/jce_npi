app_name = "npi_core"
app_title = "NPI Core"
app_publisher = "NPI One"
app_description = "NPI One domain and security foundation"
app_email = "engineering@example.invalid"
app_license = "MIT"
required_apps = []

fixtures = [
    {
        "doctype": "Role",
        "filters": [["role_name", "=", "NPI API User"]],
    }
]

before_request = ["npi_core.bff.route_request"]
after_request = ["npi_core.bff.attach_response_headers"]

doc_events = {
    "NPI WBS Item": {
        "on_update": (
            "npi_core.gate_review.frappe_repository."
            "queue_gate_review_dependency_evaluation"
        )
    },
    "NPI File Revision": {
        "on_update": (
            "npi_core.gate_review.frappe_repository."
            "queue_gate_review_dependency_evaluation"
        )
    },
    "NPI Domain Work Item": {
        "on_update": (
            "npi_core.gate_review.frappe_repository."
            "queue_gate_review_work_item_evaluation"
        )
    },
    "File": {
        "on_update": (
            "npi_core.gate_review.frappe_repository."
            "queue_gate_review_file_dependency_evaluation"
        )
    },
}

# Desk is intentionally limited to administration and support.
has_website_permission = {"NPI Audit Event": "npi_core.permissions.deny_public_access"}
