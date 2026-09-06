"""Reviewed P6-07 mapping candidates; never a production activation authority."""

from __future__ import annotations


REVIEWED_MAPPING_CANDIDATES = (
    ("Item", "Import Row", "source_row_seq"),
    ("Mold No.", "Tooling Master / External ID", "customer_mold_no"),
    ("Part Name English", "Part Revision", "part_name_en"),
    ("Chinese name", "Part Revision", "part_name_zh"),
    ("Picture", "Part / File", "primary_image"),
    ("appearance part Y/N", "Part Revision", "is_appearance_part"),
    ("Model", "Applicability", "product_model / variant"),
    ("SN P/N", "External Identifier", "identifier_value"),
    ("KW P/N", "External Identifier", "identifier_value"),
    ("TH Part Number", "External Identifier", "identifier_value"),
    ("KW Tooling No.", "Tooling External ID", "identifier_value"),
    ("Cavity", "Tooling Revision / Cavity Map", "cavity_count"),
    ("Usage Per Unit", "Part Applicability", "usage_per_assembly"),
    ("Part Material", "Material Spec", "material_family"),
    ("Material trademark", "Material Spec", "brand_or_trade_name"),
    ("FDA", "Compliance Requirement", "compliance_type/status"),
    ("secondary process", "Secondary Process", "process_type"),
    ("Material Grade", "Material Spec", "grade"),
    ("Color Master CN", "Color Spec / External ID", "color_master_cn"),
    ("Color description", "Color Spec / External ID", "color_description"),
    ("Lijun code", "Color Spec / External ID", "supplier_color_code_lijun"),
    ("Color Master Thailand", "Color Spec / External ID", "color_master_th"),
    ("calculated weight", "Process Baseline", "calculated_net_weight"),
    ("actual weight", "Process Baseline", "actual_net_weight"),
    ("runner weight", "Process Baseline", "runner_weight"),
    ("allocated runner + net per cavity", "Process Baseline", "gross_weight_per_cavity"),
    ("injection cycle seconds", "Process Baseline", "cycle_time_sec"),
    ("Supplier", "Tooling Build / Supplier Link", "supplier"),
    ("tonnage", "Machine Requirement", "clamp_tonnage / machine_type"),
    ("initial tooling set quantity", "Tooling Requirement", "initial_set_qty"),
    ("single-set daily output", "Capacity Scenario Result", "daily_part_output_per_set"),
    ("single-set daily assembly units", "Capacity Scenario Result", "daily_assembly_units_per_set"),
    ("copied tooling sets", "Tooling Requirement / Tooling Set", "copy_set_qty"),
    ("total tooling sets", "Capacity Scenario Input", "active_set_count"),
    ("total daily output", "Capacity Scenario Result", "total_daily_part_output"),
    ("total daily assembly units", "Capacity Scenario Result", "total_daily_assembly_units"),
    ("monthly capacity", "Capacity Scenario Result", "monthly_assembly_capacity"),
    ("common tooling Y/N", "Tooling Applicability", "is_shared"),
    ("A", "Legacy Classification", "legacy_a"),
    ("B", "Legacy Classification", "legacy_b"),
    ("C", "Legacy Classification", "legacy_c"),
    ("remarks", "Notes / Structured Relations", "remarks_raw"),
    ("unnamed trailing note", "Import Raw Field", "unmapped_extra"),
)


def reviewed_mapping_rows() -> tuple[dict[str, str], ...]:
    """Return fresh proposal rows so callers cannot mutate the catalog."""

    return tuple(
        {
            "source_column": source_column,
            "target_object": target_object,
            "suggested_field": suggested_field,
        }
        for source_column, target_object, suggested_field in REVIEWED_MAPPING_CANDIDATES
    )
