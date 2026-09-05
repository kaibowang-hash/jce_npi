app_name = "npi_erpnext_connector"
app_title = "NPI ERPNext Connector"
app_publisher = "NPI One"
app_description = "Operation-specific ERPNext integration for LaunchFlow"
app_email = "engineering@example.invalid"
app_license = "MIT"
required_apps = ["erpnext"]
after_install = "npi_erpnext_connector.install.after_install"

fixtures = [
    {
        "doctype": "Role",
        "filters": [
            [
                "role_name",
                "in",
                [
                    "NPI ERP Integration Service",
                    "NPI ERP MBOM Integration Service",
                    "NPI ERP Tool Asset Integration Service",
                    "NPI ERP Trial Summary Integration Service",
                    "NPI ERP Trial Summary Viewer",
                ],
            ]
        ],
    }
]

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
    "Project": {
        "after_insert": "npi_erpnext_connector.hooks_runtime.queue_project_create",
    },
    "Customer": {
        "after_insert": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_update": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_trash": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
    },
    "Supplier": {
        "after_insert": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_update": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_trash": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
    },
    "Item Group": {
        "after_insert": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_update": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_trash": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
    },
    "Item": {
        "after_insert": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_update": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
        "on_trash": "npi_erpnext_connector.hooks_runtime.queue_master_data_change",
    },
}

scheduler_events = {
    "cron": {
        "*/5 * * * *": [
            "npi_erpnext_connector.worker.recover_pending_deliveries",
            "npi_erpnext_connector.project_worker.recover_project_deliveries",
            "npi_erpnext_connector.master_data_worker.recover_master_data_deliveries",
        ],
        "*/15 * * * *": [
            "npi_erpnext_connector.worker.reconcile_all_users",
            "npi_erpnext_connector.project_worker.reconcile_projects",
            "npi_erpnext_connector.master_data_worker.reconcile_master_catalogs",
        ],
    },
}
