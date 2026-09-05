from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

_SUPPORT_DOCTYPES = (
    "npi_erp_tool_asset_mapping",
    "npi_erp_tool_asset_operation_receipt",
)

_ASSET_FIELDS = (
    {
        "fieldname": "custom_npi_source_section",
        "label": "NPI One Source",
        "fieldtype": "Section Break",
        "insert_after": "asset_name",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_npi_source_stream_key",
        "label": "NPI Source Stream Key",
        "fieldtype": "Data",
        "insert_after": "custom_npi_source_section",
        "read_only": 1,
        "unique": 1,
        "hidden": 1,
        "no_copy": 1,
        "print_hide": 1,
    },
    {
        "fieldname": "custom_npi_tooling_master_title",
        "label": "NPI Tooling Master Title",
        "fieldtype": "Data",
        "insert_after": "custom_npi_source_stream_key",
        "read_only": 1,
        "length": 140,
    },
    {
        "fieldname": "custom_npi_physical_set_serial",
        "label": "NPI Physical Set Serial",
        "fieldtype": "Data",
        "insert_after": "custom_npi_tooling_master_title",
        "read_only": 1,
        "length": 80,
    },
    {
        "fieldname": "custom_npi_tooling_requirement_kind",
        "label": "NPI Tooling Requirement Kind",
        "fieldtype": "Select",
        "insert_after": "custom_npi_physical_set_serial",
        "read_only": 1,
        "options": "new_tool\ncustomer_owned_intake\ncopy_or_additional_set\nmodification\nrepair\ncapacity_need",
    },
    {
        "fieldname": "custom_npi_source_tooling_revision",
        "label": "NPI Source Tooling Revision",
        "fieldtype": "Data",
        "insert_after": "custom_npi_tooling_requirement_kind",
        "read_only": 1,
        "length": 140,
    },
    {
        "fieldname": "custom_npi_acceptance_evidence_reference",
        "label": "NPI Acceptance Evidence Reference",
        "fieldtype": "Data",
        "insert_after": "custom_npi_source_tooling_revision",
        "read_only": 1,
        "length": 140,
    },
)


def execute() -> None:
    sync_tool_asset_schema()


def sync_tool_asset_schema(*, reload_support_doctypes: bool = True) -> None:
    _reject_incompatible_existing_fields()
    create_custom_fields({"Asset": list(_ASSET_FIELDS)}, update=False)
    _reject_incompatible_existing_fields()
    if reload_support_doctypes:
        for doctype in _SUPPORT_DOCTYPES:
            frappe.reload_doc(
                "npi_erpnext_connector",
                "doctype",
                doctype,
                force=True,
            )


def _reject_incompatible_existing_fields() -> None:
    expected = {value["fieldname"]: value for value in _ASSET_FIELDS}
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": "Asset", "fieldname": ("in", tuple(expected))},
        fields=[
            "fieldname",
            "fieldtype",
            "options",
            "read_only",
            "unique",
            "hidden",
        ],
        limit_page_length=len(expected),
    )
    for row in rows:
        definition = expected[str(row.fieldname)]
        if (
            str(row.fieldtype) != definition["fieldtype"]
            or str(row.options or "") != str(definition.get("options", ""))
            or int(row.read_only or 0) != int(definition.get("read_only", 0))
            or int(row.unique or 0) != int(definition.get("unique", 0))
            or int(row.hidden or 0) != int(definition.get("hidden", 0))
        ):
            raise RuntimeError(
                "An existing Asset custom field conflicts with the NPI Tool Asset connector."
            )
