app_name = "npi_erpnext_connector"
app_title = "NPI ERPNext Connector"
app_publisher = "NPI One"
app_description = "Operation-specific ERPNext sender for LaunchFlow"
app_email = "engineering@example.invalid"
app_license = "MIT"
required_apps = []

# Installation is inert. Both hooks and scheduled jobs return without queuing or
# contacting LaunchFlow unless the exact Site switch is explicitly set to false.
doc_events = {
    "User": {
        "after_insert": "npi_erpnext_connector.hooks_runtime.queue_user_change",
        "on_update": "npi_erpnext_connector.hooks_runtime.queue_user_change",
        "on_trash": "npi_erpnext_connector.hooks_runtime.queue_user_change",
    },
    "User Permission": {
        "after_insert": (
            "npi_erpnext_connector.hooks_runtime.queue_user_permission_change"
        ),
        "on_update": (
            "npi_erpnext_connector.hooks_runtime.queue_user_permission_change"
        ),
        "on_trash": (
            "npi_erpnext_connector.hooks_runtime.queue_user_permission_change"
        ),
    },
}

scheduler_events = {
    "cron": {
        "*/5 * * * *": [
            "npi_erpnext_connector.worker.recover_pending_deliveries"
        ]
    },
    "hourly": ["npi_erpnext_connector.worker.reconcile_all_users"],
}
