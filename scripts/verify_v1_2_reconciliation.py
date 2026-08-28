#!/usr/bin/env python3
"""Verify the accepted V1.2 DOCX–Pack reconciliation and brand package."""

from __future__ import annotations

import csv
import hashlib
import struct
import subprocess
import sys
import zlib
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "implementation/V1_2_DOCX_REQUIREMENTS.csv"
COVERAGE = ROOT / "implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv"
TRACE = ROOT / "implementation/REQUIREMENT_TRACEABILITY.csv"
TOOLING_MAPPING = ROOT / "docs/reference/TOOLING_LIST_FIELD_MAPPING.csv"
ADDENDUM = ROOT / "docs/V1_2_RECONCILIATION_ADDENDUM.md"
BRAND_DIRECTORY = ROOT / "docs/Brand Asset"
BRAND_INSTRUCTIONS = BRAND_DIRECTORY / "Brand Asset Instruction.csv"

EXPECTED_TRACE_KINDS = {
    "PACK_CANONICAL": 173,
    "DOCX_RECONCILED": 95,
    "ADDENDUM_DIRECT": 14,
}
EXPECTED_PACK_ID_SET_SHA256 = (
    "2150b062153317c2b3f06362c3d3b00aff25f10b2bdaebbb452ebda1e5f666fb"
)
PRE_RECONCILIATION_CHECKPOINT = "930b5a28cb995df12f251994a36f7502525ed94a"
EXPECTED_COVERAGE_COUNTS = {
    "EXPLICIT_SAME_ID": 134,
    "EXPLICIT_EQUIVALENT": 23,
    "GOVERNANCE_COVERED_NOT_REQUIREMENT_TRACEABLE": 22,
    "NARRATIVE_EXPLICIT_NOT_TRACEABLE": 12,
    "EXPLICIT_CONSOLIDATED_NO_ALIAS": 7,
    "PARTIAL_EXPLICIT": 9,
    "PARTIAL_NARRATIVE": 5,
    "NARRATIVE_ONLY_HIGH_RISK": 5,
    "MISSING_UNIQUE_REQUIREMENT": 7,
    "OTHER_ISOLATED_CASE": 5,
}
ADDENDUM_IDS = {
    "FR-UX-038",
    "FR-UX-039",
    "FR-UX-040",
    "FR-UX-041",
    "FR-UX-042",
    "FR-UX-043",
    "FR-PRN-001",
    "FR-PRN-002",
    "FR-PRN-003",
    "FR-INT-015",
    "FR-BR-001",
    "FR-BR-002",
    "FR-TX-019",
    "FR-TX-020",
}
EXPECTED_POST_V1_2_DEFERRED_PORTALS = {"FR-CO-003", "FR-CO-004"}
EXPECTED_POST_V1_2_DEFERRED_PORTAL_EVIDENCE = {
    "implementation/phase-4-requirement-anchor.md",
    "implementation/backlog.yaml",
    "implementation/ROADMAP.md",
    "implementation/EXECUTION_PLAN.md",
    "implementation/DECISION_LOG.md",
}
EXPECTED_UX_REMEDIATION_ALLOCATION = {
    "UX-003": ("9", "PLANNED_FULL_PRODUCT_UAT"),
    "UX-004": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-007": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-011": ("5", "TECHNICAL_VERIFIED"),
    "UX-016": ("8", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-018": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-020": ("7", "TECHNICAL_VERIFIED"),
    "UX-026": ("5", "PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD"),
    "UX-027": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-028": ("5", "TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD"),
    "UX-030": ("5", "TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD"),
    "UX-035": ("5", "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE"),
    "UX-036": ("5", "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE"),
}
EXPECTED_P7_ANCHOR_ALLOCATION = {
    "P7-01": {"FR-TR-001"},
    "P7-02": {
        "FR-NP-004",
        "FR-NP-005",
        "FR-TR-002",
        "FR-TR-003",
        "FR-TR-010",
    },
    "P7-03": {"FR-TR-004", "FR-TR-009"},
    "P7-04": {"FR-TR-005", "FR-TR-006", "FR-TR-007", "FR-TR-008"},
    "P7-05": {
        "FR-NP-001",
        "FR-NP-002",
        "FR-NP-003",
        "FR-NP-006",
        "FR-NP-007",
        "FR-NP-008",
        "FR-NP-009",
        "FR-NP-010",
        "FR-NP-011",
        "FR-NP-012",
        "FR-NP-013",
    },
    "P7-06": {"FR-NP-014", "FR-NP-015"},
    "P7-07": {"FR-PRN-002", "FR-INT-015", "FR-TR-008"},
    "P7-08": {"UX-020"},
}
EXPECTED_P7_ANCHOR_EVIDENCE = {
    "implementation/phase-7-requirement-anchor.md",
    "implementation/evidence/phase-7/p7-00-validation.md",
}
EXPECTED_P7_02_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/evidence/phase-7/p7-02-plan.md",
    "implementation/evidence/phase-7/p7-02-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-7/p7-02-repository-bff-private-file-checkpoint.md",
    "implementation/evidence/phase-7/p7-02-live-workspace-checkpoint.md",
    "implementation/evidence/phase-7/p7-02-validation.md",
}
EXPECTED_P7_03_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/evidence/phase-7/p7-03-plan.md",
    "implementation/evidence/phase-7/p7-03-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-7/p7-03-repository-bff-single-tip-checkpoint.md",
    "implementation/evidence/phase-7/p7-03-live-quality-workspace-checkpoint.md",
    "implementation/evidence/phase-7/p7-03-validation.md",
}
EXPECTED_P7_04_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/evidence/phase-7/p7-04-plan.md",
    "implementation/evidence/phase-7/p7-04-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-7/p7-04-repository-bff-policy-checkpoint.md",
    "implementation/evidence/phase-7/p7-04-live-review-workspace-checkpoint.md",
    "implementation/evidence/phase-7/p7-04-validation.md",
}
EXPECTED_P7_05_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/evidence/phase-7/p7-05-plan.md",
    "implementation/evidence/phase-7/p7-05-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-7/p7-05-repository-bff-gate-input-checkpoint.md",
    "implementation/evidence/phase-7/p7-05-live-readiness-workspace-checkpoint.md",
    "implementation/evidence/phase-7/p7-05-validation.md",
}
EXPECTED_P7_06_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/evidence/phase-7/p7-06-plan.md",
    "implementation/evidence/phase-7/p7-06-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-7/p7-06-repository-bff-checkpoint.md",
    "implementation/evidence/phase-7/p7-06-live-production-transition-workspace-checkpoint.md",
    "implementation/evidence/phase-7/p7-06-validation.md",
}
EXPECTED_P7_07_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/evidence/phase-7/p7-07-plan.md",
    "implementation/evidence/phase-7/p7-07-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-7/p7-07-repository-bff-source-adapter-checkpoint.md",
    "implementation/evidence/phase-7/p7-07-live-released-summary-workspace-checkpoint.md",
    "implementation/evidence/phase-7/p7-07-validation.md",
}
EXPECTED_P7_07_PRINT_EVIDENCE = EXPECTED_P7_07_EVIDENCE | {
    "implementation/V1_2_RECONCILIATION_DECISIONS.md",
    "implementation/phase-5-requirement-anchor.md",
    "apps/npi_core/npi_core/controlled_print/rendering.py",
    "apps/npi_core/npi_core/controlled_print/qr.py",
    "apps/npi_core/npi_core/controlled_print/frappe_repository.py",
    "frontend/src/api/controlled-print-data-source.ts",
    "tests/test_phase5_controlled_print_rendering.py",
    "tests/test_phase5_controlled_print_repository_transaction.py",
    "scripts/verify_controlled_print_runtime.py",
    "implementation/evidence/phase-5/p5-06-validation.md",
    "implementation/phase-5-gate.md",
}
EXPECTED_P7_07_INTEGRATION_EVIDENCE = EXPECTED_P7_07_EVIDENCE | {
    "implementation/V1_2_RECONCILIATION_DECISIONS.md",
}
EXPECTED_P7_08_EVIDENCE = EXPECTED_P7_ANCHOR_EVIDENCE | {
    "implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv",
    "docs/V1_2_RECONCILIATION_ADDENDUM.md",
    "frontend/src/components/mobile-field-actions.tsx",
    "frontend/src/pages/live-trial-page.tsx",
    "frontend/src/pages/gate-evidence-page.tsx",
    "frontend/tests/unit/mobile-field-actions.test.tsx",
    "frontend/tests/e2e/p7-08-mobile-field-actions.spec.ts",
    "implementation/evidence/phase-7/p7-08-plan.md",
    "implementation/evidence/phase-7/p7-08-primitives-checkpoint.md",
    "implementation/evidence/phase-7/p7-08-trial-field-checkpoint.md",
    "implementation/evidence/phase-7/p7-08-validation.md",
    "implementation/phase-7-gate.md",
}
EXPECTED_P7_COMPLETED_TRACES = {
    "FR-NP-001": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_05_EVIDENCE),
    "FR-NP-002": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_05_EVIDENCE),
    "FR-NP-003": (
        "7",
        "TECHNICAL_VERIFIED_NPI_CONFIRMATION_FOUNDATION_FORMAL_ERP_MAPPING_HELD",
        EXPECTED_P7_05_EVIDENCE,
    ),
    "FR-NP-006": (
        "7",
        "TECHNICAL_VERIFIED_CONTROLLED_REPORT_FOUNDATION_FORMAL_ERP_QUALITY_HELD",
        EXPECTED_P7_05_EVIDENCE,
    ),
    "FR-NP-007": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_05_EVIDENCE),
    "FR-NP-008": (
        "7",
        "TECHNICAL_VERIFIED_CAPACITY_SCENARIO_FOUNDATION_RUN_AT_RATE_ACTUAL_HELD",
        EXPECTED_P7_05_EVIDENCE,
    ),
    "FR-NP-009": (
        "7",
        "TECHNICAL_VERIFIED_TRIAL_ACTION_FOUNDATION_PRODUCTION_RECORD_HELD",
        EXPECTED_P7_05_EVIDENCE,
    ),
    "FR-NP-010": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_05_EVIDENCE),
    "FR-NP-011": (
        "7",
        "TECHNICAL_VERIFIED_CONTROLLED_CONFIRMATION_FOUNDATION_FORMAL_HR_PROJECTION_HELD",
        EXPECTED_P7_05_EVIDENCE,
    ),
    "FR-NP-012": (
        "7",
        "TECHNICAL_VERIFIED_NPI_SUPPLIER_FOUNDATION_FORMAL_ERP_AND_RISK_MUTATION_HELD",
        EXPECTED_P7_05_EVIDENCE,
    ),
    "FR-NP-013": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_05_EVIDENCE),
    "FR-NP-014": (
        "7",
        "TECHNICAL_VERIFIED_IMMUTABLE_HANDOVER_ACKNOWLEDGEMENT_FOUNDATION_FORMAL_ORGANIZATION_AND_G7_AUTHORITY_HELD",
        EXPECTED_P7_06_EVIDENCE,
    ),
    "FR-NP-015": (
        "7",
        "TECHNICAL_VERIFIED_OBSERVATION_REVIEW_FOUNDATION_ACTUAL_SOP_EXTERNAL_METRICS_AND_STABILITY_AUTHORITY_HELD",
        EXPECTED_P7_06_EVIDENCE,
    ),
    "FR-PRN-002": (
        "7",
        "TECHNICAL_VERIFIED_RELEASED_SUMMARY_CONTROLLED_OUTPUT_FOUNDATION_PRODUCTION_FORM_POLICY_HELD",
        EXPECTED_P7_07_PRINT_EVIDENCE,
    ),
    "FR-INT-015": (
        "7",
        "TECHNICAL_VERIFIED_NPI_SUMMARY_SOURCE_FOUNDATION_EXTERNAL_PROJECTION_HELD",
        EXPECTED_P7_07_INTEGRATION_EVIDENCE,
    ),
    "FR-TR-001": (
        "7",
        "TECHNICAL_VERIFIED_FOUNDATION_RESOURCE_RESERVATION_HELD",
        EXPECTED_P7_ANCHOR_EVIDENCE
        | {
            "implementation/evidence/phase-7/p7-01-plan.md",
            "implementation/evidence/phase-7/p7-01-domain-metadata-checkpoint.md",
            "implementation/evidence/phase-7/p7-01-repository-bff-checkpoint.md",
            "implementation/evidence/phase-7/p7-01-live-workspace-checkpoint.md",
            "implementation/evidence/phase-7/p7-01-validation.md",
        },
    ),
    "FR-NP-004": (
        "7",
        "TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD",
        EXPECTED_P7_02_EVIDENCE,
    ),
    "FR-NP-005": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_02_EVIDENCE),
    "FR-TR-002": (
        "7",
        "TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD",
        EXPECTED_P7_02_EVIDENCE,
    ),
    "FR-TR-003": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_02_EVIDENCE),
    "FR-TR-004": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_03_EVIDENCE),
    "FR-TR-005": (
        "7",
        "TECHNICAL_VERIFIED_FOUNDATION_GATE_EFFECT_POLICY_HELD",
        EXPECTED_P7_04_EVIDENCE,
    ),
    "FR-TR-006": (
        "7",
        "TECHNICAL_VERIFIED_NPI_REFERENCE_FOUNDATION_FORMAL_ERP_PROJECTION_HELD",
        EXPECTED_P7_04_EVIDENCE,
    ),
    "FR-TR-007": (
        "7",
        "TECHNICAL_VERIFIED_INTERNAL_REFERENCE_FOUNDATION_CUSTOMER_AUTHORITY_HELD",
        EXPECTED_P7_04_EVIDENCE,
    ),
    "FR-TR-008": (
        "7",
        "TECHNICAL_VERIFIED_IMMUTABLE_RELEASED_SUMMARY_FOUNDATION_FORMAL_RELEASE_HELD",
        EXPECTED_P7_04_EVIDENCE | EXPECTED_P7_07_EVIDENCE,
    ),
    "FR-TR-009": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_03_EVIDENCE),
    "FR-TR-010": (
        "7",
        "TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD",
        EXPECTED_P7_02_EVIDENCE,
    ),
    "UX-020": ("7", "TECHNICAL_VERIFIED", EXPECTED_P7_08_EVIDENCE),
}
EXPECTED_P7_CARRIED_FOUNDATIONS = {}
EXPECTED_P8_ANCHOR_ALLOCATION = {
    "P8-01": {"FR-PM-010", "INT-001", "INT-006", "INT-007", "INT-010"},
    "P8-02": {"FR-PM-002", "INT-002"},
    "P8-03": {"INT-003"},
    "P8-04": {"INT-004"},
    "P8-05": {"INT-005"},
    "P8-06": {"INT-007", "FR-TR-006", "FR-NP-006"},
    "P8-07": {"FR-RP-009", "NFR-INT-001"},
    "P8-09": {"FR-BR-002"},
}
EXPECTED_P8_ANCHOR_EVIDENCE = {
    "implementation/phase-8-requirement-anchor.md",
    "implementation/evidence/phase-8/p8-00-validation.md",
}
EXPECTED_P8_01_COMPLETED_EVIDENCE = {
    "implementation/evidence/phase-8/p8-01-plan.md",
    "implementation/evidence/phase-8/p8-01-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-8/p8-01-repository-bff-checkpoint.md",
    "implementation/evidence/phase-8/p8-01-product-ui-checkpoint.md",
    "implementation/evidence/phase-8/p8-01-validation.md",
}
EXPECTED_P8_01_COMPLETED_ALLOCATION = {
    "FR-PM-010": "TECHNICAL_VERIFIED_COST_PROJECTION_FOUNDATION_BUDGET_EAC_POLICY_HELD",
    "INT-001": "TECHNICAL_VERIFIED_READ_ONLY_PROJECTION_FOUNDATION_INBOUND_RECONCILIATION_HELD",
    "INT-006": "TECHNICAL_VERIFIED_READ_ONLY_COST_PROJECTION_FOUNDATION_INBOUND_RECONCILIATION_HELD",
    "INT-007": "TECHNICAL_VERIFIED_READ_ONLY_QUALITY_STATUS_PROJECTION_FOUNDATION_LINKAGE_POLICY_HELD",
    "INT-010": "TECHNICAL_VERIFIED_READ_ONLY_PROJECT_COST_PROJECTION_FOUNDATION_EAC_POLICY_HELD",
}
EXPECTED_P8_01_EVIDENCE_REQUIREMENTS = set(
    EXPECTED_P8_01_COMPLETED_ALLOCATION
) | {"FR-TL-008", "FR-TR-006", "FR-NP-006"}
EXPECTED_P8_02_COMPLETED_EVIDENCE = {
    "implementation/evidence/phase-8/p8-02-plan.md",
    "implementation/evidence/phase-8/p8-02-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-8/p8-02-ingress-landing-checkpoint.md",
    "implementation/evidence/phase-8/p8-02-worker-project-checkpoint.md",
    "implementation/evidence/phase-8/p8-02-validation.md",
}
EXPECTED_P8_02_COMPLETED_ALLOCATION = {
    "FR-PM-002": "TECHNICAL_VERIFIED_INBOUND_PROJECT_DRAFT_FOUNDATION_PRODUCTION_MAPPING_HELD",
    "INT-002": "TECHNICAL_VERIFIED_SIGNED_INBOX_PROJECT_DRAFT_FOUNDATION_PRODUCTION_INBOUND_RECONCILIATION_HELD",
}
EXPECTED_P8_03_COMPLETED_EVIDENCE = {
    "implementation/evidence/phase-8/p8-03-plan.md",
    "implementation/evidence/phase-8/p8-03-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-8/p8-03-command-outbox-checkpoint.md",
    "implementation/evidence/phase-8/p8-03-worker-adapter-result-checkpoint.md",
    "implementation/evidence/phase-8/p8-03-item-inspector-checkpoint.md",
    "implementation/evidence/phase-8/p8-03-final-level-3-recovery.md",
    "implementation/evidence/phase-8/p8-03-validation.md",
}
EXPECTED_P8_03_COMPLETED_ALLOCATION = {
    "INT-003": "TECHNICAL_VERIFIED_ITEM_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
    "FR-DS-013": "TECHNICAL_VERIFIED_ITEM_PORTION_MBOM_AND_PRODUCTION_SANDBOX_MAPPING_HELD",
}
EXPECTED_P8_04_COMPLETED_EVIDENCE = {
    "implementation/evidence/phase-8/p8-04-plan.md",
    "implementation/evidence/phase-8/p8-04-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-8/p8-04-command-outbox-checkpoint.md",
    "implementation/evidence/phase-8/p8-04-worker-adapter-result-checkpoint.md",
    "implementation/evidence/phase-8/p8-04-mbom-execution-inspector-checkpoint.md",
    "implementation/evidence/phase-8/p8-04-validation.md",
}
EXPECTED_P8_04_COMPLETED_ALLOCATION = {
    "INT-004": "TECHNICAL_VERIFIED_MBOM_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
    "FR-DS-013": "TECHNICAL_VERIFIED_ITEM_AND_MBOM_PORTIONS_PRODUCTION_SANDBOX_MAPPING_AND_WHOLE_REQUIREMENT_HELD",
}
EXPECTED_P8_05_COMPLETED_EVIDENCE = {
    "implementation/evidence/phase-8/p8-05-plan.md",
    "implementation/evidence/phase-8/p8-05-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-8/p8-05-worker-execution-checkpoint.md",
    "implementation/evidence/phase-8/p8-05-execution-inspector-checkpoint.md",
    "implementation/evidence/phase-8/p8-05-validation.md",
}
EXPECTED_P8_05_COMPLETED_ALLOCATION = {
    "INT-005": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
    "FR-TL-011": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-012": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-013": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-014": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-015": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-016": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
}
EXPECTED_P8_06_COMPLETED_EVIDENCE = {
    "implementation/evidence/phase-8/p8-06-plan.md",
    "implementation/evidence/phase-8/p8-06-domain-metadata-checkpoint.md",
    "implementation/evidence/phase-8/p8-06-validation.md",
}
EXPECTED_P8_06_COMPLETED_ALLOCATION = {
    "INT-007": "TECHNICAL_VERIFIED_FORMAL_QUALITY_LINK_FOUNDATION_PRODUCTION_SANDBOX_POLICY_HELD",
    "FR-TR-006": "TECHNICAL_VERIFIED_FORMAL_QUALITY_REFERENCE_PORTION_PRODUCTION_SANDBOX_POLICY_AND_WHOLE_REQUIREMENT_HELD",
    "FR-NP-006": "TECHNICAL_VERIFIED_FORMAL_QUALITY_LINK_PORTION_PRODUCTION_SANDBOX_POLICY_AND_WHOLE_REQUIREMENT_HELD",
}
ERP_CUSTOMIZATION_REQUIREMENTS = ROOT / "docs" / "ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md"
EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_EVIDENCE = (
    "docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md"
)
EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_HOLD_STATUSES = {
    "INT-001": "TECHNICAL_VERIFIED_READ_ONLY_PROJECTION_FOUNDATION_INBOUND_RECONCILIATION_HELD",
    "INT-002": "TECHNICAL_VERIFIED_SIGNED_INBOX_PROJECT_DRAFT_FOUNDATION_PRODUCTION_INBOUND_RECONCILIATION_HELD",
    "INT-003": "TECHNICAL_VERIFIED_ITEM_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
    "INT-004": "TECHNICAL_VERIFIED_MBOM_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
    "INT-005": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
    "INT-006": "TECHNICAL_VERIFIED_READ_ONLY_COST_PROJECTION_FOUNDATION_INBOUND_RECONCILIATION_HELD",
    "INT-007": "TECHNICAL_VERIFIED_FORMAL_QUALITY_LINK_FOUNDATION_PRODUCTION_SANDBOX_POLICY_HELD",
    "INT-010": "TECHNICAL_VERIFIED_READ_ONLY_PROJECT_COST_PROJECTION_FOUNDATION_EAC_POLICY_HELD",
    "FR-PM-002": "TECHNICAL_VERIFIED_INBOUND_PROJECT_DRAFT_FOUNDATION_PRODUCTION_MAPPING_HELD",
    "FR-DS-013": "TECHNICAL_VERIFIED_ITEM_AND_MBOM_PORTIONS_PRODUCTION_SANDBOX_MAPPING_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-011": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-012": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-013": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-014": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-015": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TL-016": "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
    "FR-TR-006": "TECHNICAL_VERIFIED_FORMAL_QUALITY_REFERENCE_PORTION_PRODUCTION_SANDBOX_POLICY_AND_WHOLE_REQUIREMENT_HELD",
    "FR-NP-006": "TECHNICAL_VERIFIED_FORMAL_QUALITY_LINK_PORTION_PRODUCTION_SANDBOX_POLICY_AND_WHOLE_REQUIREMENT_HELD",
}
EXPECTED_P8_CARRIED_FOUNDATIONS = {
    "FR-DS-013": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-008": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-011": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-012": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-013": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-014": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-015": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TL-016": ("6", "TECHNICAL_VERIFIED_FOUNDATION"),
    "FR-TR-006": (
        "7",
        "TECHNICAL_VERIFIED_NPI_REFERENCE_FOUNDATION_FORMAL_ERP_PROJECTION_HELD",
    ),
    "FR-NP-006": (
        "7",
        "TECHNICAL_VERIFIED_CONTROLLED_REPORT_FOUNDATION_FORMAL_ERP_QUALITY_HELD",
    ),
    "FR-INT-015": (
        "7",
        "TECHNICAL_VERIFIED_NPI_SUMMARY_SOURCE_FOUNDATION_EXTERNAL_PROJECTION_HELD",
    ),
    "UX-016": ("8", "TECHNICAL_VERIFIED_FOUNDATION"),
}
EXPECTED_P8_SCOPED_HOLDS = {
    "INT-008": ("9", "HELD_PHASE_9_CHANGE_DOMAIN"),
    "INT-009": ("8", "SCOPED_HOLD_EXTERNAL_FILE_CONSUMER_MAPPING"),
    "INT-011": ("8", "SCOPED_HOLD_TARGET_SUMMARY_FIELD_MAPPING"),
    "INT-012": (
        "8",
        "SCOPED_HOLD_EXTERNAL_IDENTITY_TOPOLOGY_AND_SCOPES",
    ),
    "INT-013": (
        "8",
        "SCOPED_HOLD_OPTIONAL_PROVIDER_AND_OWNERSHIP_DECISION",
    ),
    "INT-014": ("9", "HELD_PHASE_9_REPORTING_BI_BOUNDARY"),
}
EXPECTED_R1_03_TRACE = {
    "FR-UX-039": (
        "TECHNICAL_VERIFIED",
        {
            "apps/npi_core/npi_core/localization_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/api/session.ts",
            "frontend/src/app/app-shell.tsx",
            "frontend/tests/e2e/r1-03-shell.spec.ts",
            "scripts/verify_frappe_runtime.py",
            "implementation/evidence/reconciliation/r1-03-validation.md",
        },
    ),
    "UX-011": (
        "TECHNICAL_VERIFIED",
        {
            "frontend/src/app/app-shell.tsx",
            "frontend/src/pages/project-governance-workspace.tsx",
            "frontend/tests/unit/project-governance-workspace.test.tsx",
            "frontend/tests/e2e/r1-03-shell.spec.ts",
            "implementation/evidence/reconciliation/r1-03-validation.md",
        },
    ),
    "UX-018": (
        "TECHNICAL_VERIFIED_FOUNDATION",
        {
            "frontend/src/app/command-palette.tsx",
            "frontend/src/app/router.ts",
            "frontend/tests/unit/pages-and-shell.test.tsx",
            "frontend/tests/unit/router.test.tsx",
            "frontend/tests/e2e/r1-03-shell.spec.ts",
            "implementation/evidence/reconciliation/r1-03-validation.md",
        },
    ),
}
EXPECTED_R1_04_TRACE = {
    "FR-UX-038": (
        "TECHNICAL_VERIFIED",
        {
            "apps/npi_core/npi_core/grid_personalization/domain.py",
            "apps/npi_core/npi_core/grid_personalization/frappe_repository.py",
            "apps/npi_core/npi_core/grid_personalization_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/ui-adapters/dense-grid-layout.ts",
            "frontend/src/ui-adapters/dense-grid.tsx",
            "frontend/src/components/live-my-worklist.tsx",
            "frontend/tests/unit/dense-grid.test.tsx",
            "frontend/tests/e2e/r1-04-grid.spec.ts",
            "scripts/verify_grid_personalization_runtime.py",
            "implementation/evidence/reconciliation/r1-04-validation.md",
        },
    ),
    "UX-007": (
        "TECHNICAL_VERIFIED_FOUNDATION",
        {
            "frontend/src/ui-adapters/dense-grid.tsx",
            "frontend/src/components/live-my-worklist.tsx",
            "frontend/src/components/worklist.tsx",
            "frontend/tests/unit/dense-grid.test.tsx",
            "frontend/tests/e2e/r1-04-grid.spec.ts",
            "implementation/evidence/reconciliation/r1-04-validation.md",
            "implementation/phase-6-requirement-anchor.md",
            "implementation/evidence/phase-6/p6-00-validation.md",
            "apps/npi_core/npi_core/tooling/export_domain.py",
            "apps/npi_core/npi_core/tooling/export_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/api/tooling-list-data-source.ts",
            "frontend/src/components/tooling-list-workspace.tsx",
            "frontend/tests/unit/tooling-list-data-source.test.ts",
            "frontend/tests/unit/tooling-list-workspace.test.tsx",
            "frontend/tests/e2e/p6-08-tooling-list-live.spec.ts",
            "scripts/verify_tooling_export_runtime.py",
            "implementation/evidence/phase-6/p6-08-validation.md",
        },
    ),
    "UX-027": (
        "TECHNICAL_VERIFIED_FOUNDATION",
        {
            "apps/npi_core/npi_core/grid_personalization/controller.py",
            "apps/npi_core/npi_core/grid_personalization/frappe_repository.py",
            "apps/npi_core/npi_core/grid_personalization_api.py",
            "apps/npi_core/npi_core/npi_core/doctype/npi_my_work_grid_preference/npi_my_work_grid_preference.json",
            "frontend/src/api/grid-preferences-data-source.ts",
            "frontend/src/components/my-work-grid-personalization.ts",
            "frontend/src/components/live-my-worklist.tsx",
            "frontend/tests/unit/grid-preferences-data-source.test.ts",
            "frontend/tests/unit/my-work-grid-personalization.test.tsx",
            "tests/test_r1_04_grid_personalization_repository_api.py",
            "frontend/tests/e2e/r1-04-grid.spec.ts",
            "scripts/verify_grid_personalization_runtime.py",
            "implementation/evidence/reconciliation/r1-04-validation.md",
        },
    ),
    "UX-028": (
        "TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD",
        {
            "apps/npi_core/npi_core/grid_personalization/controller.py",
            "apps/npi_core/npi_core/grid_personalization/domain.py",
            "apps/npi_core/npi_core/grid_personalization/frappe_repository.py",
            "apps/npi_core/npi_core/npi_core/doctype/npi_published_grid_view/npi_published_grid_view.json",
            "apps/npi_core/npi_core/npi_core/doctype/npi_published_grid_view_revision/npi_published_grid_view_revision.json",
            "tests/test_r1_04_grid_personalization_domain.py",
            "tests/test_r1_04_grid_personalization_repository_api.py",
            "scripts/verify_grid_personalization_runtime.py",
            "implementation/evidence/reconciliation/r1-04-plan.md",
            "implementation/evidence/reconciliation/r1-04-validation.md",
        },
    ),
}
EXPECTED_R1_05_STAGE_1_TRACE = {
    "FR-UX-040": (
        "TECHNICAL_VERIFIED",
        {
            "apps/npi_core/npi_core/inspector_preferences/domain.py",
            "apps/npi_core/npi_core/inspector_preferences/frappe_repository.py",
            "apps/npi_core/npi_core/inspector_preferences_api.py",
            "apps/npi_core/npi_core/bff.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/api/my-work-inspector-preferences-data-source.ts",
            "frontend/src/ui-adapters/resizable-pane.tsx",
            "frontend/src/components/my-work-inspector-personalization.ts",
            "frontend/src/components/live-my-worklist.tsx",
            "frontend/tests/unit/resizable-pane-separator.test.tsx",
            "frontend/tests/unit/my-work-inspector-personalization.test.tsx",
            "frontend/tests/unit/my-work-inspector-preferences-data-source.test.ts",
            "tests/test_r1_05_inspector_preferences_domain.py",
            "tests/test_r1_05_inspector_preferences_api.py",
            "tests/test_r1_05_inspector_preferences_contract.py",
            "frontend/tests/e2e/r1-05-panes.spec.ts",
            "scripts/verify_frappe_runtime.py",
            "scripts/verify_project_controls_runtime.py",
            "implementation/evidence/reconciliation/r1-05-stage-1-validation.md",
        },
    ),
}
EXPECTED_R1_05_STAGE_2_TRACE = {
    "FR-UX-041": (
        "TECHNICAL_VERIFIED",
        {
            "frontend/src/components/attachment-workflow.ts",
            "frontend/src/components/field-attachment-primitives.tsx",
            "frontend/src/pages/trial-page.tsx",
            "frontend/src/pages/gate-evidence-page.tsx",
            "frontend/src/styles/app.css",
            "frontend/tests/unit/field-attachment-primitives.test.tsx",
            "frontend/tests/unit/pages-and-shell.test.tsx",
            "frontend/tests/unit/gate-evidence-page.test.tsx",
            "frontend/tests/e2e/r1-05-field-attachments.spec.ts",
            "frontend/tests/e2e/states-locales-accessibility.spec.ts",
            "apps/npi_core/npi_core/translations/zh.csv",
            "apps/npi_core/npi_core/translations/zh-TW.csv",
            "frontend/src/generated/catalogs.ts",
            "implementation/evidence/reconciliation/r1-05-stage-2-validation.md",
        },
    ),
}
EXPECTED_R1_05_STAGE_3_TRACE = {
    "FR-UX-043": (
        "TECHNICAL_VERIFIED",
        {
            "frontend/src/ui-adapters/action-policy.ts",
            "frontend/src/ui-adapters/npi-ui.tsx",
            "frontend/src/components/field-attachment-primitives.tsx",
            "frontend/src/components/object-components.tsx",
            "frontend/src/styles/app.css",
            "frontend/scripts/verify-boundaries.mjs",
            "frontend/tests/unit/action-policy.test.ts",
            "frontend/tests/unit/compact-action.test.tsx",
            "frontend/tests/e2e/r1-05-panes.spec.ts",
            "frontend/tests/e2e/r1-05-field-attachments.spec.ts",
            "implementation/evidence/reconciliation/r1-05-stage-3-validation.md",
        },
    ),
}
EXPECTED_R1_06_STAGE_1_TRACE = {
    requirement_id: (
        (
            "PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD"
            if requirement_id == "UX-026"
            else "TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD"
        ),
        {
            "frontend/src/components/controlled-undo-prototype-model.ts",
            "frontend/src/components/controlled-undo-prototype.tsx",
            "frontend/src/pages/work-page.tsx",
            "frontend/src/styles/app.css",
            "apps/npi_core/npi_core/translations/zh.csv",
            "apps/npi_core/npi_core/translations/zh-TW.csv",
            "frontend/src/generated/catalogs.ts",
            "frontend/tests/unit/controlled-undo-prototype.test.tsx",
            "frontend/tests/e2e/r1-06-controlled-undo-prototype.spec.ts",
            "implementation/prototype-approvals/r1-06-my-work-grid-reset.json",
            "scripts/verify_prototype_approvals.py",
            "tests/test_prototype_approvals.py",
            "implementation/evidence/reconciliation/r1-06-stage-1-prototype-review.md",
            "implementation/evidence/reconciliation/r1-06-stage-1-validation.md",
        },
    )
    for requirement_id in ("UX-026", "UX-030")
}
EXPECTED_R1_06_STAGE_3_TRACE = {
    "UX-035": (
        "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE",
        {
            "frontend/src/components/live-my-worklist.tsx",
            "frontend/src/styles/app.css",
            "frontend/tests/e2e/r1-04-grid.spec.ts",
            "frontend/tests/e2e/r1-04-grid.spec.ts-snapshots/r1-04-grid-en-1440x900-100-linux.png",
            "frontend/tests/e2e/r1-04-grid.spec.ts-snapshots/r1-04-grid-zh-1440x900-100-linux.png",
            "frontend/tests/e2e/r1-04-grid.spec.ts-snapshots/r1-04-grid-zh-TW-1440x900-100-linux.png",
            "implementation/evidence/reconciliation/r1-04-validation.md",
            ".github/workflows/ci.yml",
            "frontend/tests/e2e/p0-visual-registry.json",
            "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts",
            "scripts/verify_devcontainer.py",
            "scripts/verify_p0_visual_governance.py",
            "tests/test_devcontainer_verifier.py",
            "tests/test_p0_visual_governance.py",
            "implementation/evidence/reconciliation/r1-06-stage-3-validation.md",
            "implementation/evidence/reconciliation/r1-06-validation.md",
        },
    ),
    "UX-036": (
        "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE",
        {
            ".github/workflows/ci.yml",
            "frontend/tests/e2e/p0-visual-registry.json",
            "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts",
            "frontend/tests/e2e/visual-matrix.spec.ts",
            "frontend/tests/e2e/states-locales-accessibility.spec.ts",
            "implementation/evidence/phase-3/visual-review.md",
            "scripts/verify_devcontainer.py",
            "scripts/verify_p0_visual_governance.py",
            "tests/test_devcontainer_verifier.py",
            "tests/test_p0_visual_governance.py",
            "implementation/evidence/reconciliation/r1-06-stage-3-validation.md",
            "implementation/evidence/reconciliation/r1-06-validation.md",
        },
    ),
}
EXPECTED_P5_01_COMPLETED_TRACE = {
    requirement_id: (
        status,
        {
            "implementation/evidence/phase-5/p5-01-reconciliation-hold.md",
            "implementation/evidence/reconciliation/r1-shared-bridge-level-3-validation.md",
            "implementation/phase-5-requirement-anchor.md",
            "implementation/evidence/phase-5/p5-01-plan.md",
            "implementation/evidence/phase-5/p5-01-resume-audit.md",
            "implementation/evidence/phase-5/p5-01-frontend-runtime-checkpoint.md",
            "implementation/evidence/phase-5/p5-01-controlled-runtime-projection-validation-blocker.md",
            "implementation/evidence/phase-5/p5-01-post-checkout-recovery.md",
            "implementation/evidence/phase-5/p5-01-validation.md",
        },
    )
    for requirement_id, status in {
        "FR-DS-001": "TECHNICAL_VERIFIED_FOUNDATION",
        "FR-DS-003": "TECHNICAL_VERIFIED",
        "FR-DS-004": "TECHNICAL_VERIFIED_FOUNDATION",
        "FR-DS-007": "TECHNICAL_VERIFIED_FOUNDATION",
        "FR-DS-008": "TECHNICAL_VERIFIED_FOUNDATION",
        "FR-DS-009": "TECHNICAL_VERIFIED_FOUNDATION",
        "FR-DS-014": "TECHNICAL_VERIFIED_FOUNDATION",
    }.items()
}
EXPECTED_P5_02_COMPLETED_TRACE = {
    requirement_id: (
        status,
        {
            "implementation/phase-5-requirement-anchor.md",
            "implementation/evidence/phase-5/p5-02-plan.md",
            "implementation/evidence/phase-5/p5-02-controlled-metadata-checkpoint.md",
            "implementation/evidence/phase-5/p5-02-implementation-checkpoint.md",
            "implementation/evidence/phase-5/p5-02-validation.md",
        },
    )
    for requirement_id, status in {
        "FR-DS-002": "TECHNICAL_VERIFIED",
        "FR-DS-005": "TECHNICAL_VERIFIED_FOUNDATION",
        "FR-DS-010": "TECHNICAL_VERIFIED_FOUNDATION",
    }.items()
}
EXPECTED_P5_02_PRIORITIES = {
    "FR-DS-002": "P0",
    "FR-DS-005": "P0",
    "FR-DS-010": "P0",
}
EXPECTED_P5_03_COMPLETED_TRACE = {
    "FR-DS-006": (
        "TECHNICAL_VERIFIED",
        {
            "implementation/phase-5-requirement-anchor.md",
            "implementation/evidence/phase-5/p5-03-plan.md",
            "implementation/evidence/phase-5/p5-03-domain-metadata-checkpoint.md",
            "implementation/evidence/phase-5/p5-03-repository-api-checkpoint.md",
            "implementation/evidence/phase-5/p5-03-validation.md",
        },
    )
}
EXPECTED_P5_06_TRACE = {
    "FR-PRN-001": (
        "TECHNICAL_VERIFIED",
        {
            "implementation/V1_2_RECONCILIATION_DECISIONS.md",
            "implementation/phase-5-requirement-anchor.md",
            "apps/npi_core/npi_core/controlled_print/domain.py",
            "apps/npi_core/npi_core/controlled_print/frappe_repository.py",
            "apps/npi_core/npi_core/controlled_print_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/components/controlled-print-action.tsx",
            "tests/test_phase5_controlled_print_repository.py",
            "scripts/verify_controlled_print_runtime.py",
            "implementation/evidence/phase-5/p5-06-validation.md",
            "implementation/phase-5-gate.md",
        },
    ),
    "FR-PRN-002": (
        "TECHNICAL_VERIFIED",
        {
            "implementation/V1_2_RECONCILIATION_DECISIONS.md",
            "implementation/phase-5-requirement-anchor.md",
            "apps/npi_core/npi_core/controlled_print/rendering.py",
            "apps/npi_core/npi_core/controlled_print/qr.py",
            "apps/npi_core/npi_core/controlled_print/frappe_repository.py",
            "frontend/src/api/controlled-print-data-source.ts",
            "tests/test_phase5_controlled_print_rendering.py",
            "tests/test_phase5_controlled_print_repository_transaction.py",
            "scripts/verify_controlled_print_runtime.py",
            "implementation/evidence/phase-5/p5-06-validation.md",
            "implementation/phase-5-gate.md",
        },
    ),
}
EXPECTED_P6_02_TRACE = {
    "FR-TL-001": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-001",
        {
            "apps/npi_core/npi_core/tooling/domain.py",
            "apps/npi_core/npi_core/tooling/frappe_repository.py",
            "frontend/src/pages/live-tooling-page.tsx",
            "frontend/src/pages/tooling-set-workspace.tsx",
            "scripts/verify_tooling_runtime.py",
            "implementation/evidence/phase-6/p6-01-validation.md",
            "implementation/evidence/phase-6/p6-02-validation.md",
            "Requirement ownership custody repair and return provenance are live while exact lifecycle and authority policy remains held by DR-REC-010",
        },
    ),
    "FR-TL-004": (
        "P0",
        "TECHNICAL_VERIFIED",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-004",
        {
            "apps/npi_core/npi_core/tooling/domain.py",
            "apps/npi_core/npi_core/tooling/frappe_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "frontend/src/pages/tooling-set-workspace.tsx",
            "tests/test_phase6_tooling_domain.py",
            "tests/test_phase6_tooling_repository.py",
            "scripts/verify_tooling_runtime.py",
            "implementation/evidence/phase-6/p6-02-validation.md",
            "customer owner transport arrival photo accessories five inspections differences and customer confirmation are retained authorized and live",
        },
    ),
    "FR-TX-003": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/domain.py",
            "apps/npi_core/npi_core/tooling/frappe_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-set-workspace.tsx",
            "tests/test_phase6_tooling_domain.py",
            "tests/test_phase6_tooling_repository.py",
            "scripts/verify_tooling_runtime.py",
            "implementation/evidence/phase-6/p6-02-validation.md",
            "one immutable record per physical Set and no quantity collapse are proven while source Revision Supplier lifecycle ERP location Asset and later execution remain P6-03 P6-04 P6-06 and Phase 8",
        },
    ),
}
EXPECTED_P6_03_TRACE = {
    "FR-TL-002": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-002",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "tests/test_phase6_tooling_revision_domain.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "closed core unit-bearing Tooling specification is live while unapproved mold-type extensions remain unavailable",
        },
    ),
    "FR-TL-003": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-003",
        {
            "apps/npi_core/npi_core/tooling/domain.py",
            "apps/npi_core/npi_core/tooling/frappe_repository.py",
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "frontend/src/pages/live-tooling-page.tsx",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "scripts/verify_tooling_runtime.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-01-validation.md",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "multi-Project Part Master Applicability and exact cavity mapping are live while Trial and quality results remain Phase 7",
        },
    ),
    "FR-TL-006": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-006",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "apps/npi_core/npi_core/tooling/manufacturing_domain.py",
            "apps/npi_core/npi_core/tooling/manufacturing_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "frontend/src/pages/tooling-manufacturing-workspace.tsx",
            "tests/test_phase6_tooling_revision_repository.py",
            "scripts/verify_tooling_revision_runtime.py",
            "scripts/verify_tooling_manufacturing_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "implementation/evidence/phase-6/p6-04-validation.md",
            "immutable Tooling Revision lineage and released design evidence are live while Tooling approval release and manufacturing authority remain held by DR-REC-010",
        },
    ),
    "FR-TX-004": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "FR-TL-003; FR-TL-010",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "tests/test_phase6_tooling_revision_domain.py",
            "tests/test_phase6_tooling_revision_repository.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "exact cavity identity status and Part mapping are proven while cavity Trial defect and capacity results remain Phase 7 and P6-05",
        },
    ),
    "FR-TX-005": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "tests/test_phase6_tooling_revision_domain.py",
            "tests/test_phase6_tooling_revision_repository.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "ordered primary second-shot and overmold structure is proven while combined Trial remains Phase 7",
        },
    ),
    "FR-TX-006": (
        "P0",
        "TECHNICAL_VERIFIED",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "tests/test_phase6_tooling_revision_domain.py",
            "tests/test_phase6_tooling_revision_repository.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "insert model version changeover duration and evidence-bound validation state are structured queryable and runtime proven",
        },
    ),
    "FR-TX-007": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "tests/test_phase6_tooling_revision_domain.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "one-to-many Part and Tooling external identities retain raw source and effectivity while production workbook splitting remains P6-07",
        },
    ),
    "FR-TX-008": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/revision_domain.py",
            "apps/npi_core/npi_core/tooling/revision_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "frontend/src/pages/tooling-revision-workspace.tsx",
            "tests/test_phase6_tooling_revision_domain.py",
            "scripts/verify_tooling_revision_runtime.py",
            "implementation/evidence/phase-6/p6-03-validation.md",
            "controlled material color compliance and process facts bind to exact Part Revision while automatic impact action remains Phase 9",
        },
    ),
}
EXPECTED_P6_04_TRACE = {
    "FR-TL-005": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-005",
        {
            "apps/npi_core/npi_core/tooling/manufacturing_domain.py",
            "apps/npi_core/npi_core/tooling/manufacturing_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-manufacturing-workspace.tsx",
            "tests/test_phase6_tooling_manufacturing_domain.py",
            "tests/test_phase6_tooling_manufacturing_repository.py",
            "scripts/verify_tooling_manufacturing_runtime.py",
            "implementation/evidence/phase-6/p6-04-validation.md",
            "internal sourcing estimate budget and released proposal evidence are live while formal funding PO and G3 readiness remain unavailable",
        },
    ),
    "FR-TL-007": (
        "P1",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-007",
        {
            "apps/npi_core/npi_core/tooling/manufacturing_domain.py",
            "apps/npi_core/npi_core/tooling/manufacturing_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-manufacturing-workspace.tsx",
            "tests/test_phase6_tooling_manufacturing_domain.py",
            "tests/test_phase6_tooling_manufacturing_repository.py",
            "scripts/verify_tooling_manufacturing_runtime.py",
            "implementation/evidence/phase-6/p6-04-validation.md",
            "ordered milestones and append-only internal observations are live while supplier login portal and supplier-authored updates remain unavailable",
        },
    ),
    "FR-TL-008": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-008",
        {
            "apps/npi_core/npi_core/tooling/manufacturing_domain.py",
            "apps/npi_core/npi_core/tooling/manufacturing_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/data-ownership.yaml",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-manufacturing-workspace.tsx",
            "tests/test_phase6_tooling_manufacturing_contract.py",
            "tests/test_phase6_tooling_manufacturing_repository.py",
            "scripts/verify_tooling_manufacturing_runtime.py",
            "implementation/evidence/phase-6/p6-04-validation.md",
            "closed read-only ERP projection and unavailable default are live while adapter observations procurement execution and actual cost remain Phase 8",
        },
    ),
}
EXPECTED_P6_05_TRACE = {
    "FR-TL-009": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-009",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "tests/test_phase6_tooling_engineering_controls_repository.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "immutable defect action responsibility target-round intention and verification truth are live while final Trial and G5 G6 policy integration remains Phase 7",
        },
    ),
    "FR-TL-010": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-010",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "future Trial context target-round references and separated comparison slots are live while Trial rounds and comparisons remain Phase 7",
        },
    ),
    "FR-TL-017": (
        "P2",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-017",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_contract.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "closed unavailable ERP IoT shot-count source and calibration projection is live while source observations remain Phase 8",
        },
    ),
    "FR-TL-018": (
        "P2",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-018",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_contract.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "closed unavailable health and maintenance-policy projection is live while scoring thresholds and advice remain Phase 8",
        },
    ),
    "FR-TX-009": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "versioned Customer Standard process truth is live while Trial Actual and Approved Baseline creation remain Phase 7",
        },
    ),
    "FR-TX-010": (
        "P0",
        "TECHNICAL_VERIFIED",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "tests/test_phase6_tooling_engineering_controls_repository.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "complete explicit capacity inputs formula version provenance successors and deterministic recomputation are runtime proven without hidden business constants",
        },
    ),
    "FR-TX-011": (
        "P0",
        "TECHNICAL_VERIFIED",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "tests/test_phase6_tooling_engineering_controls_repository.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "part day month assembly bottleneck and gap outputs are server-derived versioned and runtime proven after changed inputs",
        },
    ),
    "FR-TX-019": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/V1_2_RECONCILIATION_ADDENDUM.md",
        "ADDENDUM_DIRECT",
        "FR-TX-019",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "contracts/npi-api.openapi.yaml",
            "contracts/data-ownership.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "Customer Standard Trial Actual and Approved Baseline are disjoint typed layers while Phase 7 retains actual and approval creation",
        },
    ),
    "FR-TX-020": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/V1_2_RECONCILIATION_ADDENDUM.md",
        "ADDENDUM_DIRECT",
        "FR-TX-020",
        {
            "apps/npi_core/npi_core/tooling/engineering_controls_domain.py",
            "apps/npi_core/npi_core/tooling/engineering_controls_repository.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-engineering-controls-workspace.tsx",
            "tests/test_phase6_tooling_engineering_controls_domain.py",
            "scripts/verify_tooling_engineering_controls_runtime.py",
            "implementation/evidence/phase-6/p6-05-validation.md",
            "exact rule-versioned comparison and four textual states are live while production red semantics remain held by DR-REC-002",
        },
    ),
}
EXPECTED_P6_06_TRACE = {
    "FR-TL-011": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-011",
        {
            "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            "apps/npi_core/npi_core/tooling/acceptance_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-acceptance-asset-workspace.tsx",
            "tests/test_phase6_tooling_acceptance_domain.py",
            "tests/test_phase6_tooling_acceptance_repository.py",
            "scripts/verify_tooling_acceptance_runtime.py",
            "implementation/evidence/phase-6/p6-06-validation.md",
            "immutable nine-category acceptance evidence and Mock request input are live while business approval official quality and real Asset execution remain Phase 7 and Phase 8",
        },
    ),
    "FR-TL-012": (
        "P0",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-012",
        {
            "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            "apps/npi_integration/npi_integration/tool_asset_request/domain.py",
            "apps/npi_integration/npi_integration/tool_asset_request/frappe_repository.py",
            "contracts/data-ownership.yaml",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-acceptance-asset-workspace.tsx",
            "tests/test_phase6_tool_asset_request_domain.py",
            "tests/test_phase6_tooling_acceptance_repository.py",
            "scripts/verify_tooling_acceptance_runtime.py",
            "implementation/evidence/phase-6/p6-06-validation.md",
            "one physical Tooling Set is the sole zero-or-one mapping subject while formal Asset ID confirmation and reconciliation remain Phase 8",
        },
    ),
    "FR-TL-013": (
        "P1",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-013",
        {
            "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            "apps/npi_core/npi_core/tooling/acceptance_repository.py",
            "contracts/data-ownership.yaml",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-acceptance-asset-workspace.tsx",
            "tests/test_phase6_tooling_acceptance_domain.py",
            "tests/test_phase6_tooling_acceptance_repository.py",
            "scripts/verify_tooling_acceptance_runtime.py",
            "implementation/evidence/phase-6/p6-06-validation.md",
            "closed read-only unavailable Asset projection is live while authenticated location life maintenance movement and repair observations remain Phase 8",
        },
    ),
    "FR-TL-014": (
        "P1",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-014",
        {
            "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            "apps/npi_core/npi_core/tooling/acceptance_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-acceptance-asset-workspace.tsx",
            "tests/test_phase6_tooling_acceptance_domain.py",
            "tests/test_phase6_tooling_acceptance_repository.py",
            "scripts/verify_tooling_acceptance_runtime.py",
            "implementation/evidence/phase-6/p6-06-validation.md",
            "immutable move loan return archive and scrap Project evidence is live while actual Asset movement and approval execution remain Phase 8",
        },
    ),
    "FR-TL-015": (
        "P1",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-015",
        {
            "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            "apps/npi_core/npi_core/tooling/acceptance_repository.py",
            "contracts/data-ownership.yaml",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-acceptance-asset-workspace.tsx",
            "tests/test_phase6_tooling_acceptance_domain.py",
            "tests/test_phase6_tooling_acceptance_repository.py",
            "scripts/verify_tooling_acceptance_runtime.py",
            "implementation/evidence/phase-6/p6-06-validation.md",
            "immutable critical and wear spare recommendations are live while formal Item supplier mapping and inventory remain ERPNext Phase 8 truth",
        },
    ),
    "FR-TL-016": (
        "P1",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "docs/DETAILED_REQUIREMENTS.md",
        "PACK_CANONICAL",
        "FR-TL-016",
        {
            "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            "apps/npi_core/npi_core/tooling/acceptance_repository.py",
            "apps/npi_core/npi_core/tooling_api.py",
            "contracts/npi-api.openapi.yaml",
            "frontend/src/pages/tooling-acceptance-asset-workspace.tsx",
            "tests/test_phase6_tooling_acceptance_domain.py",
            "tests/test_phase6_tooling_acceptance_repository.py",
            "scripts/verify_tooling_acceptance_runtime.py",
            "implementation/evidence/phase-6/p6-06-validation.md",
            "immutable repair authorization quote responsibility downtime and verification evidence is live with customer-owned authorization enforced while formal repair cost and history remain Phase 8",
        },
    ),
}
P6_07_COMMON_EVIDENCE = {
    "apps/npi_core/npi_core/tooling/xlsx_inspector.py",
    "apps/npi_core/npi_core/tooling/import_domain.py",
    "apps/npi_core/npi_core/tooling/import_execution_domain.py",
    "apps/npi_core/npi_core/tooling/import_repository.py",
    "apps/npi_core/npi_core/tooling/import_execution_repository.py",
    "apps/npi_core/npi_core/tooling_import_api.py",
    "contracts/data-ownership.yaml",
    "contracts/npi-api.openapi.yaml",
    "frontend/src/api/tooling-import-data-source.ts",
    "frontend/src/pages/tooling-import-workspace.tsx",
    "tests/test_phase6_tooling_import_execution_repository.py",
    "scripts/verify_tooling_import_runtime.py",
    "implementation/evidence/phase-6/p6-07-validation.md",
}
EXPECTED_P6_07_TRACE = {
    "FR-TX-012": (
        "P0",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "passive position independent Tooling List inspection and immutable source provenance are live for exact sanitized XLSX bytes"
        },
    ),
    "FR-TX-013": (
        "P0",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "all 43 reviewed columns raw values formulas states grades and image anchors retain immutable provenance without executing formulas"
        },
    ),
    "FR-TX-014": (
        "P0",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "immutable mapping proposal preview and explicit ambiguous relationship and image confirmation are live while production mapping remains unavailable"
        },
    ),
    "FR-TX-015": (
        "P0",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "bounded asynchronous execution persists immutable per row and per field partial success failure and target binding truth"
        },
    ),
    "FR-TX-016": (
        "P1",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "allowlisted correction artifacts failed row only retry and successful row non duplication are live and runtime proven"
        },
    ),
    "FR-TX-017": (
        "P0",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "immutable reconciliation and strict rollback eligibility allow unchanged batch created unused targets and durably deny downstream used targets"
        },
    ),
    "FR-TX-018": (
        "P0",
        "6",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "",
        P6_07_COMMON_EVIDENCE
        | {
            "Project first authorization actor bound sealed replay route recovery redacted logs and no ERP integration traffic are runtime proven"
        },
    ),
    "UX-016": (
        "P0",
        "8",
        "TECHNICAL_VERIFIED_FOUNDATION",
        "implementation/V1_2_DOCX_REQUIREMENTS.csv",
        "DOCX_RECONCILED",
        "FR-UX-012",
        P6_07_COMMON_EVIDENCE
        | {
            "durable row field job progress retry reconciliation and rollback truth are live while the shared Phase 8 execution job center remains held"
        },
    ),
}
EXPECTED_P5_01_PRIORITIES = {
    "FR-DS-001": "P0",
    "FR-DS-003": "P0",
    "FR-DS-004": "P0",
    "FR-DS-007": "P1",
    "FR-DS-008": "P0",
    "FR-DS-009": "P1",
    "FR-DS-014": "P2",
}
EXPECTED_BRAND_INSTRUCTIONS = {
    "Company LOGO.svg": (
        "Website Footer",
        "Use it in the website footer, to indicate that the platform is the "
        "company's asset",
    ),
    "Loading.svg": (
        "Loading Page, Start Page",
        "User see this logo on a blank page when entering the website, or "
        "while loading",
    ),
    "LaunchFlow Icon.svg": (
        "Used as Website Favicon and Place Indicates this Platform",
        "Favicon, also when place mentions the platform (e.g. when the "
        'platform contains information like "Source: NPI One (or '
        "LaunchFlow), use this icon to replace the text instead)",
    ),
    "LaunchFlow-logo_White.svg": (
        "Standard LOGO, used for dark backgraounds",
        "",
    ),
    "LaunchFlow-logo_Standard.svg": (
        "Standard LOGO, used for light backgraounds",
        "",
    ),
    "Core.png": (
        "Standard LOGO for JCE Core or Erpnext. Use this LOGO to replace text "
        '"Erpnext" or "JCE Core".',
        "",
    ),
}
EXPECTED_BRAND_HASHES = {
    "Brand Asset Instruction.csv": (
        "b2714c36408f9503d41b9c003d1dd5e4f75bb8040467f74336d8fbd5cb2d9822"
    ),
    "Company LOGO.svg": (
        "856237b6bb2a9fb2d3674c7ede318eb8e3630a0ab12c451d64a25122e272a8ff"
    ),
    "LaunchFlow Icon.svg": (
        "bddf68cb729a1da8378dfdc1136173b6a014706fec6b58e8421d0f4ae8892452"
    ),
    "LaunchFlow-logo_Standard.svg": (
        "d2397fc9a21067a78655e9e84c4645a22cd1e4cc88835f665f7cbb7a29f6e2b6"
    ),
    "LaunchFlow-logo_White.svg": (
        "55b9ab1e7b4ab9330acfc73c2ddb099db38c865d0704781f256c2cf113d4226d"
    ),
    "Loading.svg": ("730e9e621881afbc1d3cb8520792b2ddc75f6b9dc4035311599a105a934cc253"),
    "Core.png": ("0c7182882022cf190925c90f0004c77aaca4dd513b86ccd0f23efb30171e0e42"),
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_ALLOWED_CRITICAL_CHUNKS = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
PNG_ANIMATION_CHUNKS = {b"acTL", b"fcTL", b"fdAT"}
PNG_VALID_BIT_DEPTHS = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}
PNG_CHANNELS_BY_COLOR_TYPE = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
MAX_BRAND_PNG_FILE_BYTES = 5 * 1024 * 1024
MAX_BRAND_PNG_DIMENSION = 8192
MAX_BRAND_PNG_PIXELS = 16_000_000
MAX_BRAND_PNG_DECODED_BYTES = 64 * 1024 * 1024


class ReconciliationVerificationError(RuntimeError):
    """Raised when a reconciled source or generated artifact is inconsistent."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, strict=True))


def _require_unique(
    rows: list[dict[str, str]], key: str, expected_count: int, label: str
) -> set[str]:
    values = [row[key] for row in rows]
    if len(values) != expected_count or len(set(values)) != expected_count:
        raise ReconciliationVerificationError(
            f"{label} must contain {expected_count} unique {key} values"
        )
    return set(values)


def verify_erp_customization_requirements_document() -> None:
    text = ERP_CUSTOMIZATION_REQUIREMENTS.read_text(encoding="utf-8")
    required_tokens = {
        "Required",
        "Optional",
        "Already Present",
        "Not Required",
        "Blocked Pending Fact",
        "REPOSITORY_CONFIRMED",
        "EXTERNAL_EVIDENCE_REQUIRED",
        "OWNER_APPROVAL_REQUIRED",
        "PROHIBITED_PENDING_RULE_CHANGE_AND_GATE",
        "QUEUED_NOT_EFFECTIVE",
        "## Read-only fact-collection activation Gate",
        "## Validation and acceptance checklist",
        "## Explicit no-change list",
        "BatchMode",
        "no TTY",
        "no port forwarding",
        "no agent forwarding",
        "strict host-key verification",
        "Immediate stop on permission insufficiency",
        "implementation/REQUIRED_INPUTS.md",
    }
    missing = sorted(token for token in required_tokens if token not in text)
    if missing:
        raise ReconciliationVerificationError(
            f"ERP customization requirements document lacks tokens: {missing}"
        )
    required_sections = {
        "### Platform, apps and extension inventory",
        "### Metadata, workflow and permissions",
        "### Operation APIs, events and reliability",
        "### Master data, capacity, files and security",
        "### Delivery, migration and operations",
    }
    if not required_sections.issubset(set(text.splitlines())):
        raise ReconciliationVerificationError(
            "ERP customization requirements document section set drifted"
        )
    if "http://" in text or "https://" in text:
        raise ReconciliationVerificationError(
            "ERP customization requirements document must not contain endpoints"
        )
    register_rows = [
        line for line in text.splitlines() if line.startswith("|") and "---" not in line
    ]
    if len(register_rows) < 16:
        raise ReconciliationVerificationError(
            "ERP customization requirements register is incomplete"
        )
    classifications = {
        "Required",
        "Optional",
        "Already Present",
        "Not Required",
        "Blocked Pending Fact",
    }
    for row in register_rows:
        if row.startswith("| Item |"):
            continue
        columns = [value.strip() for value in row.strip("|").split("|")]
        if len(columns) != 11 or columns[1] not in classifications:
            raise ReconciliationVerificationError(
                "ERP customization requirements register row shape/classification drifted"
            )


def verify_trace_sets() -> None:
    requirements = _read_csv(REQUIREMENTS)
    coverage = _read_csv(COVERAGE)
    trace = _read_csv(TRACE)
    tooling_mapping = _read_csv(TOOLING_MAPPING)

    docx_ids = _require_unique(requirements, "requirement_id", 229, "DOCX requirements")
    coverage_ids = _require_unique(
        coverage, "docx_requirement_id", 229, "coverage matrix"
    )
    trace_ids = _require_unique(trace, "requirement_id", 282, "traceability")
    _require_unique(tooling_mapping, "source_column", 43, "Tooling List field mapping")

    if coverage_ids != docx_ids:
        raise ReconciliationVerificationError(
            "coverage matrix IDs differ from the authoritative DOCX IDs"
        )
    if not docx_ids.issubset(trace_ids):
        raise ReconciliationVerificationError(
            "traceability does not retain all 229 DOCX requirement IDs"
        )
    if not ADDENDUM_IDS.issubset(trace_ids):
        raise ReconciliationVerificationError(
            "traceability does not retain every addendum requirement ID"
        )

    trace_kind_counts = Counter(row["trace_kind"] for row in trace)
    if dict(trace_kind_counts) != EXPECTED_TRACE_KINDS:
        raise ReconciliationVerificationError(
            f"unexpected trace-kind counts: {dict(trace_kind_counts)}"
        )
    coverage_counts = Counter(
        row["coverage_status_before_reconciliation"] for row in coverage
    )
    if dict(coverage_counts) != EXPECTED_COVERAGE_COUNTS:
        raise ReconciliationVerificationError(
            f"unexpected coverage counts: {dict(coverage_counts)}"
        )

    by_id = {row["requirement_id"]: row for row in trace}
    for requirement_id, expected_status in (
        EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_HOLD_STATUSES.items()
    ):
        row = by_id[requirement_id]
        evidence = {
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
        }
        if row["status"] != expected_status:
            raise ReconciliationVerificationError(
                f"{requirement_id} integration-hold status drifted"
            )
        if EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_EVIDENCE not in evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks ERP customization requirements evidence"
            )
    for requirement_id, row in by_id.items():
        evidence = {
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
        }
        if (
            EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_EVIDENCE in evidence
            and requirement_id
            not in EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_HOLD_STATUSES
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} has unauthorized ERP requirements evidence"
            )
    # All legacy exact-evidence assertions below continue to prove their
    # historical sets. The new evidence path is independently proven above,
    # then removed from this in-memory view so it cannot weaken those checks.
    for row in by_id.values():
        row["evidence"] = "; ".join(
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
            and value.strip()
            != EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_EVIDENCE
        )
    for requirement_id in EXPECTED_POST_V1_2_DEFERRED_PORTALS:
        row = by_id[requirement_id]
        evidence = {
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            "P1",
            "9",
            "REMAPPED_PHASE_9",
            "docs/DETAILED_REQUIREMENTS.md",
            "PACK_CANONICAL",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must preserve its canonical remap status"
            )
        if not EXPECTED_POST_V1_2_DEFERRED_PORTAL_EVIDENCE.issubset(evidence):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the approved post-V1.2 deferral evidence"
            )
    brand_row = by_id["FR-BR-001"]
    expected_brand_evidence = {
        "frontend/src/ui-adapters/display-brand.tsx",
        "frontend/scripts/verify-display-brand.mjs",
        "frontend/tests/unit/display-brand.test.tsx",
        "frontend/tests/e2e/display-brand.spec.ts",
        "implementation/evidence/reconciliation/r1-02-validation.md",
    }
    actual_brand_evidence = {
        value.strip() for value in brand_row["evidence"].split(";") if value.strip()
    }
    if (
        brand_row["phase"],
        brand_row["status"],
        brand_row["trace_kind"],
        brand_row["canonical_ids"],
    ) != ("5", "TECHNICAL_VERIFIED", "ADDENDUM_DIRECT", "FR-BR-001"):
        raise ReconciliationVerificationError(
            "FR-BR-001 must retain the verified R1-02 trace state"
        )
    if actual_brand_evidence != expected_brand_evidence:
        raise ReconciliationVerificationError(
            "FR-BR-001 must retain its complete R1-02 runtime evidence set"
        )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_03_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["phase"],
            row["status"],
            row["trace_kind"],
        ) != (
            "5",
            expected_status,
            ("ADDENDUM_DIRECT" if requirement_id == "FR-UX-039" else "DOCX_RECONCILED"),
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the verified R1-03 trace state"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-03 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-03 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_04_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["phase"],
            row["status"],
            row["trace_kind"],
        ) != (
            "5",
            expected_status,
            ("ADDENDUM_DIRECT" if requirement_id == "FR-UX-038" else "DOCX_RECONCILED"),
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the verified R1-04 trace state"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-04 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-04 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_05_STAGE_1_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            "P0",
            "5",
            expected_status,
            "docs/V1_2_RECONCILIATION_ADDENDUM.md",
            "ADDENDUM_DIRECT",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the verified R1-05 Stage 1 trace state"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-05 Stage 1 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-05 Stage 1 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_05_STAGE_2_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            "P0",
            "5",
            expected_status,
            "docs/V1_2_RECONCILIATION_ADDENDUM.md",
            "ADDENDUM_DIRECT",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the verified R1-05 Stage 2 trace state"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-05 Stage 2 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-05 Stage 2 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_05_STAGE_3_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            "P0",
            "5",
            expected_status,
            "docs/V1_2_RECONCILIATION_ADDENDUM.md",
            "ADDENDUM_DIRECT",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the verified R1-05 Stage 3 trace state"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-05 Stage 3 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-05 Stage 3 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_06_STAGE_1_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
        ) != (
            "P0",
            "5",
            expected_status,
            "implementation/V1_2_DOCX_REQUIREMENTS.csv",
            "DOCX_RECONCILED",
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the R1-06 Stage 1 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-06 Stage 1 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-06 Stage 1 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_R1_06_STAGE_3_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
        ) != (
            "P0",
            "5",
            expected_status,
            "implementation/V1_2_DOCX_REQUIREMENTS.csv",
            "DOCX_RECONCILED",
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the R1-06 Stage 3 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete R1-06 Stage 3 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing R1-06 Stage 3 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_P5_01_COMPLETED_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            EXPECTED_P5_01_PRIORITIES[requirement_id],
            "5",
            expected_status,
            "docs/DETAILED_REQUIREMENTS.md",
            "PACK_CANONICAL",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P5-01 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P5-01 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P5-01 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_P5_02_COMPLETED_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            EXPECTED_P5_02_PRIORITIES[requirement_id],
            "5",
            expected_status,
            "docs/DETAILED_REQUIREMENTS.md",
            "PACK_CANONICAL",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P5-02 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P5-02 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P5-02 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_P5_03_COMPLETED_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            "P0",
            "5",
            expected_status,
            "docs/DETAILED_REQUIREMENTS.md",
            "PACK_CANONICAL",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P5-03 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P5-03 evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P5-03 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_status,
        expected_evidence,
    ) in EXPECTED_P5_06_TRACE.items():
        row = by_id[requirement_id]
        completed_trace = EXPECTED_P7_COMPLETED_TRACES.get(requirement_id)
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        expected_phase, effective_status = (
            completed_trace[:2] if completed_trace else ("5", expected_status)
        )
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            "P0",
            expected_phase,
            effective_status,
            "docs/V1_2_RECONCILIATION_ADDENDUM.md",
            "ADDENDUM_DIRECT",
            requirement_id,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P5-06 trace truth"
            )
        permitted_evidence = completed_trace[2] if completed_trace else expected_evidence
        if actual_evidence != permitted_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P5-06 plan evidence set"
            )
        missing_evidence = sorted(
            path for path in expected_evidence if not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P5-06 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_priority,
        expected_status,
        expected_source,
        expected_trace_kind,
        expected_canonical_ids,
        expected_evidence,
    ) in EXPECTED_P6_02_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            expected_priority,
            "6",
            expected_status,
            expected_source,
            expected_trace_kind,
            expected_canonical_ids,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P6-02 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P6-02 evidence set"
            )
        missing_evidence = sorted(
            path
            for path in expected_evidence
            if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P6-02 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_priority,
        expected_status,
        expected_source,
        expected_trace_kind,
        expected_canonical_ids,
        expected_evidence,
    ) in EXPECTED_P6_03_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            expected_priority,
            "6",
            expected_status,
            expected_source,
            expected_trace_kind,
            expected_canonical_ids,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P6-03 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P6-03 evidence set"
            )
        missing_evidence = sorted(
            path
            for path in expected_evidence
            if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P6-03 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_priority,
        expected_status,
        expected_source,
        expected_trace_kind,
        expected_canonical_ids,
        expected_evidence,
    ) in EXPECTED_P6_04_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            expected_priority,
            "6",
            expected_status,
            expected_source,
            expected_trace_kind,
            expected_canonical_ids,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P6-04 trace truth"
            )
        permitted_evidence = expected_evidence | (
            EXPECTED_P8_ANCHOR_EVIDENCE
            if requirement_id in EXPECTED_P8_CARRIED_FOUNDATIONS
            else set()
        ) | (
            EXPECTED_P8_01_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
            else set()
        ) | (
            EXPECTED_P8_02_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_02_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_03_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_03_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_04_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_04_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_05_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_05_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_06_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_06_COMPLETED_ALLOCATION
            else set()
        )
        if actual_evidence != permitted_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P6-04 evidence set"
            )
        missing_evidence = sorted(
            path
            for path in permitted_evidence
            if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P6-04 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_priority,
        expected_status,
        expected_source,
        expected_trace_kind,
        expected_canonical_ids,
        expected_evidence,
    ) in EXPECTED_P6_05_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            expected_priority,
            "6",
            expected_status,
            expected_source,
            expected_trace_kind,
            expected_canonical_ids,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P6-05 trace truth"
            )
        if actual_evidence != expected_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P6-05 evidence set"
            )
        missing_evidence = sorted(
            path
            for path in expected_evidence
            if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P6-05 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_priority,
        expected_status,
        expected_source,
        expected_trace_kind,
        expected_canonical_ids,
        expected_evidence,
    ) in EXPECTED_P6_06_TRACE.items():
        row = by_id[requirement_id]
        completed_status = EXPECTED_P8_05_COMPLETED_ALLOCATION.get(requirement_id)
        effective_phase = "8" if completed_status is not None else "6"
        effective_status = completed_status or expected_status
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            expected_priority,
            effective_phase,
            effective_status,
            expected_source,
            expected_trace_kind,
            expected_canonical_ids,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P6-06 trace truth"
            )
        permitted_evidence = expected_evidence | (
            EXPECTED_P8_ANCHOR_EVIDENCE
            if requirement_id in EXPECTED_P8_CARRIED_FOUNDATIONS
            else set()
        ) | (
            EXPECTED_P8_01_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
            else set()
        ) | (
            EXPECTED_P8_02_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_02_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_03_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_03_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_04_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_04_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_05_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_05_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_06_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_06_COMPLETED_ALLOCATION
            else set()
        )
        if actual_evidence != permitted_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P6-06 evidence set"
            )
        missing_evidence = sorted(
            path
            for path in permitted_evidence
            if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P6-06 evidence files: "
                f"{missing_evidence}"
            )
    for requirement_id, (
        expected_priority,
        expected_phase,
        expected_status,
        expected_source,
        expected_trace_kind,
        expected_canonical_ids,
        expected_evidence,
    ) in EXPECTED_P6_07_TRACE.items():
        row = by_id[requirement_id]
        actual_evidence = {
            value.strip() for value in row["evidence"].split(";") if value.strip()
        }
        if (
            row["priority"],
            row["phase"],
            row["status"],
            row["source"],
            row["trace_kind"],
            row["canonical_ids"],
        ) != (
            expected_priority,
            expected_phase,
            expected_status,
            expected_source,
            expected_trace_kind,
            expected_canonical_ids,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain the completed P6-07 trace truth"
            )
        permitted_evidence = expected_evidence | (
            EXPECTED_P8_ANCHOR_EVIDENCE
            if requirement_id in EXPECTED_P8_CARRIED_FOUNDATIONS
            else set()
        ) | (
            EXPECTED_P8_01_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
            else set()
        ) | (
            EXPECTED_P8_02_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_02_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_03_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_03_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_04_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_04_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_05_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_05_COMPLETED_ALLOCATION
            else set()
        ) | (
            EXPECTED_P8_06_COMPLETED_EVIDENCE
            if requirement_id in EXPECTED_P8_06_COMPLETED_ALLOCATION
            else set()
        )
        if actual_evidence != permitted_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its complete P6-07 evidence set"
            )
        missing_evidence = sorted(
            path
            for path in permitted_evidence
            if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing P6-07 evidence files: "
                f"{missing_evidence}"
            )
    canonical_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "PACK_CANONICAL"
    }
    if len(canonical_ids - docx_ids) != 39:
        raise ReconciliationVerificationError(
            "the trace must retain exactly 39 Pack-only normalized IDs"
        )

    for requirement_id, (
        expected_phase,
        expected_status,
    ) in EXPECTED_UX_REMEDIATION_ALLOCATION.items():
        row = by_id[requirement_id]
        if (row["phase"], row["status"]) != (
            expected_phase,
            expected_status,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} has stale remediation allocation"
            )

    for task_id, requirement_ids in EXPECTED_P7_ANCHOR_ALLOCATION.items():
        anchored_status = f"ANCHORED_{task_id.replace('-', '_')}"
        for requirement_id in requirement_ids:
            row = by_id[requirement_id]
            completed_trace = EXPECTED_P7_COMPLETED_TRACES.get(requirement_id)
            p8_06_status = EXPECTED_P8_06_COMPLETED_ALLOCATION.get(requirement_id)
            expected_phase, expected_status = (
                ("8", p8_06_status)
                if p8_06_status
                else completed_trace[:2]
                if completed_trace
                else ("7", anchored_status)
            )
            if (row["phase"], row["status"]) != (
                expected_phase,
                expected_status,
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} is not allocated to {task_id}"
                )
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            if not EXPECTED_P7_ANCHOR_EVIDENCE.issubset(evidence):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the Phase 7 anchor evidence"
                )
            permitted_completed_evidence = (
                completed_trace[2]
                | (
                    EXPECTED_P8_ANCHOR_EVIDENCE
                    if requirement_id in EXPECTED_P8_CARRIED_FOUNDATIONS
                    else set()
                )
                | (
                    EXPECTED_P8_01_COMPLETED_EVIDENCE
                    if requirement_id in EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
                    else set()
                )
                | (
                    EXPECTED_P8_02_COMPLETED_EVIDENCE
                    if requirement_id in EXPECTED_P8_02_COMPLETED_ALLOCATION
                    else set()
                )
                | (
                    EXPECTED_P8_03_COMPLETED_EVIDENCE
                    if requirement_id in EXPECTED_P8_03_COMPLETED_ALLOCATION
                    else set()
                )
                | (
                    EXPECTED_P8_04_COMPLETED_EVIDENCE
                    if requirement_id in EXPECTED_P8_04_COMPLETED_ALLOCATION
                    else set()
                )
                | (
                    EXPECTED_P8_05_COMPLETED_EVIDENCE
                    if requirement_id in EXPECTED_P8_05_COMPLETED_ALLOCATION
                    else set()
                )
                | (
                    EXPECTED_P8_06_COMPLETED_EVIDENCE
                    if requirement_id in EXPECTED_P8_06_COMPLETED_ALLOCATION
                    else set()
                )
                if completed_trace
                else set()
            )
            if completed_trace and evidence != permitted_completed_evidence:
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks its exact completed task evidence"
                )
            missing_evidence = sorted(
                path for path in evidence if not (ROOT / path).is_file()
            )
            if missing_evidence:
                raise ReconciliationVerificationError(
                    f"{requirement_id} references missing Phase 7 evidence: "
                    f"{missing_evidence}"
                )

    for requirement_id, expected_trace in EXPECTED_P7_CARRIED_FOUNDATIONS.items():
        row = by_id[requirement_id]
        if (row["phase"], row["status"]) != expected_trace:
            raise ReconciliationVerificationError(
                f"{requirement_id} must retain its pre-Phase 7 trace truth"
            )
        evidence = {
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
        }
        if not EXPECTED_P7_ANCHOR_EVIDENCE.issubset(evidence):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the Phase 7 scoped-hold evidence"
            )

    for task_id, requirement_ids in EXPECTED_P8_ANCHOR_ALLOCATION.items():
        anchored_status = f"ANCHORED_{task_id.replace('-', '_')}"
        for requirement_id in requirement_ids:
            row = by_id[requirement_id]
            completed_status = EXPECTED_P8_06_COMPLETED_ALLOCATION.get(
                requirement_id,
                EXPECTED_P8_01_COMPLETED_ALLOCATION.get(
                    requirement_id,
                    EXPECTED_P8_02_COMPLETED_ALLOCATION.get(
                        requirement_id,
                        EXPECTED_P8_03_COMPLETED_ALLOCATION.get(
                            requirement_id,
                            EXPECTED_P8_04_COMPLETED_ALLOCATION.get(
                                requirement_id,
                                EXPECTED_P8_05_COMPLETED_ALLOCATION.get(
                                    requirement_id,
                                    anchored_status,
                                ),
                            ),
                        ),
                    ),
                ),
            )
            expected_trace = (
                ("8", completed_status)
                if completed_status != anchored_status
                else EXPECTED_P8_CARRIED_FOUNDATIONS.get(
                    requirement_id,
                    ("8", anchored_status),
                )
            )
            if (row["phase"], row["status"]) != expected_trace:
                raise ReconciliationVerificationError(
                    f"{requirement_id} is not allocated to {task_id}"
                )
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            if not EXPECTED_P8_ANCHOR_EVIDENCE.issubset(evidence):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the Phase 8 anchor evidence"
                )
            if (
                requirement_id in EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
                and not EXPECTED_P8_01_COMPLETED_EVIDENCE.issubset(evidence)
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the P8-01 completion evidence"
                )
            if (
                requirement_id in EXPECTED_P8_02_COMPLETED_ALLOCATION
                and not EXPECTED_P8_02_COMPLETED_EVIDENCE.issubset(evidence)
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the P8-02 completion evidence"
                )
            if (
                requirement_id in EXPECTED_P8_03_COMPLETED_ALLOCATION
                and not EXPECTED_P8_03_COMPLETED_EVIDENCE.issubset(evidence)
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the P8-03 completion evidence"
                )
            if (
                requirement_id in EXPECTED_P8_04_COMPLETED_ALLOCATION
                and not EXPECTED_P8_04_COMPLETED_EVIDENCE.issubset(evidence)
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the P8-04 completion evidence"
                )
            if (
                requirement_id in EXPECTED_P8_05_COMPLETED_ALLOCATION
                and not EXPECTED_P8_05_COMPLETED_EVIDENCE.issubset(evidence)
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the P8-05 completion evidence"
                )
            if (
                requirement_id in EXPECTED_P8_06_COMPLETED_ALLOCATION
                and not EXPECTED_P8_06_COMPLETED_EVIDENCE.issubset(evidence)
            ):
                raise ReconciliationVerificationError(
                    f"{requirement_id} lacks the P8-06 completion evidence"
                )

    for requirement_id, expected_trace in {
        **EXPECTED_P8_CARRIED_FOUNDATIONS,
        **EXPECTED_P8_SCOPED_HOLDS,
    }.items():
        row = by_id[requirement_id]
        completed_status = EXPECTED_P8_06_COMPLETED_ALLOCATION.get(
            requirement_id,
            EXPECTED_P8_05_COMPLETED_ALLOCATION.get(
                requirement_id,
                EXPECTED_P8_04_COMPLETED_ALLOCATION.get(
                    requirement_id,
                    EXPECTED_P8_03_COMPLETED_ALLOCATION.get(requirement_id),
                ),
            ),
        )
        effective_trace = (
            ("8", completed_status) if completed_status is not None else expected_trace
        )
        if (row["phase"], row["status"]) != effective_trace:
            raise ReconciliationVerificationError(
                f"{requirement_id} does not retain its Phase 8 anchor truth"
            )
        evidence = {
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
        }
        if not EXPECTED_P8_ANCHOR_EVIDENCE.issubset(evidence):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the Phase 8 scoped evidence"
            )
        if (
            requirement_id in EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
            and not EXPECTED_P8_01_COMPLETED_EVIDENCE.issubset(evidence)
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the P8-01 completion evidence"
            )
        if (
            requirement_id in EXPECTED_P8_02_COMPLETED_ALLOCATION
            and not EXPECTED_P8_02_COMPLETED_EVIDENCE.issubset(evidence)
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the P8-02 completion evidence"
            )
        if (
            requirement_id in EXPECTED_P8_03_COMPLETED_ALLOCATION
            and not EXPECTED_P8_03_COMPLETED_EVIDENCE.issubset(evidence)
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the P8-03 completion evidence"
            )
        if (
            requirement_id in EXPECTED_P8_04_COMPLETED_ALLOCATION
            and not EXPECTED_P8_04_COMPLETED_EVIDENCE.issubset(evidence)
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the P8-04 completion evidence"
            )
        if (
            requirement_id in EXPECTED_P8_05_COMPLETED_ALLOCATION
            and not EXPECTED_P8_05_COMPLETED_EVIDENCE.issubset(evidence)
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the P8-05 completion evidence"
            )
        if (
            requirement_id in EXPECTED_P8_06_COMPLETED_ALLOCATION
            and not EXPECTED_P8_06_COMPLETED_EVIDENCE.issubset(evidence)
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} lacks the P8-06 completion evidence"
            )
        missing_evidence = sorted(
            path for path in evidence if "/" in path and not (ROOT / path).is_file()
        )
        if missing_evidence:
            raise ReconciliationVerificationError(
                f"{requirement_id} references missing Phase 8 evidence: "
                f"{missing_evidence}"
            )

    linked_alias_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "DOCX_RECONCILED"
        and row["status"] == "RECONCILED_ALIAS_LINKED_TO_CANONICAL_IDS"
        and row["phase"] == "3"
    }
    governance_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "DOCX_RECONCILED"
        and row["status"] == "RECONCILED_GOVERNANCE_LINKED_NON_PRODUCT"
        and row["phase"] == "0"
    }
    tooling_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if requirement_id.startswith("FR-TX-")
        and row["trace_kind"] == "DOCX_RECONCILED"
        and row["status"].startswith("ANCHORED_P6_")
        and row["phase"] == "6"
    }
    if len(linked_alias_ids) != 30:
        raise ReconciliationVerificationError(
            "expected 30 non-blocking UX/I18N alias links"
        )
    if len(governance_ids) != 34:
        raise ReconciliationVerificationError(
            "expected 34 non-product ARCH/COD governance links"
        )
    if tooling_ids:
        raise ReconciliationVerificationError(
            "completed Phase 6 Tooling requirements must not remain anchored"
        )
    canonical_id_payload = "\n".join(sorted(canonical_ids)) + "\n"
    canonical_id_digest = hashlib.sha256(
        canonical_id_payload.encode("utf-8")
    ).hexdigest()
    if canonical_id_digest != EXPECTED_PACK_ID_SET_SHA256:
        raise ReconciliationVerificationError(
            "the original 173-ID Pack set differs from its accepted baseline"
        )

    for row in coverage:
        if row["pre_reconciliation_checkpoint"] != PRE_RECONCILIATION_CHECKPOINT:
            raise ReconciliationVerificationError(
                "coverage evidence is not fixed to the accepted "
                "pre-reconciliation checkpoint"
            )
        mappings = {
            value.strip()
            for value in row["pack_requirement_ids"].split(";")
            if value.strip()
        }
        unknown = mappings - canonical_ids
        if unknown:
            raise ReconciliationVerificationError(
                f"{row['docx_requirement_id']} maps to non-Pack IDs: "
                f"{sorted(unknown)}"
            )

    addendum_text = ADDENDUM.read_text(encoding="utf-8")
    missing_addendum_ids = sorted(
        requirement_id
        for requirement_id in ADDENDUM_IDS
        if requirement_id not in addendum_text
    )
    if missing_addendum_ids:
        raise ReconciliationVerificationError(
            f"addendum text omits IDs: {missing_addendum_ids}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_svg_is_self_contained(path: Path) -> None:
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise ReconciliationVerificationError(
            f"brand asset is not valid XML: {path.name}"
        ) from exc

    local_root_name = root.tag.rsplit("}", 1)[-1]
    if local_root_name != "svg":
        raise ReconciliationVerificationError(
            f"brand asset root is not SVG: {path.name}"
        )

    disallowed_elements = {"script", "foreignObject", "image"}
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name in disallowed_elements:
            raise ReconciliationVerificationError(
                f"brand asset contains disallowed {local_name}: {path.name}"
            )
        for attribute_name, value in element.attrib.items():
            local_attribute = attribute_name.rsplit("}", 1)[-1].lower()
            normalized_value = value.strip().lower()
            if local_attribute.startswith("on"):
                raise ReconciliationVerificationError(
                    f"brand asset contains an event handler: {path.name}"
                )
            if local_attribute in {"href", "src"} and normalized_value:
                if not normalized_value.startswith("#"):
                    raise ReconciliationVerificationError(
                        f"brand asset contains an external reference: {path.name}"
                    )
            if "url(" in normalized_value and "url(#" not in normalized_value:
                raise ReconciliationVerificationError(
                    f"brand asset contains an external URL: {path.name}"
                )


def _verify_png_is_safe(path: Path) -> None:
    file_size = path.stat().st_size
    if file_size < len(PNG_SIGNATURE) or file_size > MAX_BRAND_PNG_FILE_BYTES:
        raise ReconciliationVerificationError(
            f"brand PNG file size is outside the accepted bound: "
            f"{path.name}={file_size}"
        )

    payload = path.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ReconciliationVerificationError(
            f"brand asset is not a valid PNG signature: {path.name}"
        )

    offset = len(PNG_SIGNATURE)
    seen_ihdr = False
    seen_plte = False
    seen_idat = False
    idat_closed = False
    idat_bytes = 0
    seen_iend = False

    while offset < len(payload):
        if len(payload) - offset < 12:
            raise ReconciliationVerificationError(
                f"brand PNG has a truncated chunk header: {path.name}"
            )

        chunk_length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + chunk_length
        chunk_end = chunk_data_end + 4
        if chunk_end > len(payload):
            raise ReconciliationVerificationError(
                f"brand PNG has a truncated chunk: {path.name}"
            )
        if not all(
            ord("A") <= value <= ord("Z") or ord("a") <= value <= ord("z")
            for value in chunk_type
        ) or not ord("A") <= chunk_type[2] <= ord("Z"):
            raise ReconciliationVerificationError(
                f"brand PNG has an invalid chunk type: {path.name}"
            )

        chunk_data = payload[chunk_data_start:chunk_data_end]
        expected_crc = struct.unpack(">I", payload[chunk_data_end:chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ReconciliationVerificationError(
                f"brand PNG chunk CRC differs for "
                f"{chunk_type.decode('ascii')}: {path.name}"
            )

        if chunk_type in PNG_ANIMATION_CHUNKS:
            raise ReconciliationVerificationError(
                f"animated PNG chunks are not allowed: {path.name}"
            )
        is_critical = chunk_type[0] & 0x20 == 0
        if is_critical and chunk_type not in PNG_ALLOWED_CRITICAL_CHUNKS:
            raise ReconciliationVerificationError(
                f"brand PNG contains unsupported critical chunk "
                f"{chunk_type.decode('ascii')}: {path.name}"
            )
        if not seen_ihdr and chunk_type != b"IHDR":
            raise ReconciliationVerificationError(
                f"brand PNG must begin with IHDR: {path.name}"
            )

        if chunk_type == b"IHDR":
            if seen_ihdr or offset != len(PNG_SIGNATURE) or chunk_length != 13:
                raise ReconciliationVerificationError(
                    f"brand PNG must contain one 13-byte leading IHDR: {path.name}"
                )
            (
                width,
                height,
                bit_depth,
                color_type,
                compression_method,
                filter_method,
                interlace_method,
            ) = struct.unpack(">IIBBBBB", chunk_data)
            if (
                width < 1
                or height < 1
                or width > MAX_BRAND_PNG_DIMENSION
                or height > MAX_BRAND_PNG_DIMENSION
            ):
                raise ReconciliationVerificationError(
                    f"brand PNG dimensions are outside the accepted bound: "
                    f"{path.name}={width}x{height}"
                )
            pixels = width * height
            if pixels > MAX_BRAND_PNG_PIXELS:
                raise ReconciliationVerificationError(
                    f"brand PNG pixel budget is outside the accepted bound: "
                    f"{path.name}={pixels}"
                )
            valid_bit_depths = PNG_VALID_BIT_DEPTHS.get(color_type)
            if valid_bit_depths is None or bit_depth not in valid_bit_depths:
                raise ReconciliationVerificationError(
                    f"brand PNG has an invalid color type/bit depth: {path.name}"
                )
            if (
                compression_method != 0
                or filter_method != 0
                or interlace_method not in {0, 1}
            ):
                raise ReconciliationVerificationError(
                    f"brand PNG has unsupported IHDR methods: {path.name}"
                )
            channels = PNG_CHANNELS_BY_COLOR_TYPE[color_type]
            bytes_per_sample = 1 if bit_depth <= 8 else 2
            decoded_byte_bound = pixels * channels * bytes_per_sample + height * 8
            if decoded_byte_bound > MAX_BRAND_PNG_DECODED_BYTES:
                raise ReconciliationVerificationError(
                    f"brand PNG decoded-byte budget is outside the accepted "
                    f"bound: {path.name}={decoded_byte_bound}"
                )
            seen_ihdr = True
        elif chunk_type == b"PLTE":
            if seen_plte or seen_idat or chunk_length < 3 or chunk_length > 768:
                raise ReconciliationVerificationError(
                    f"brand PNG has an invalid PLTE chunk: {path.name}"
                )
            if chunk_length % 3:
                raise ReconciliationVerificationError(
                    f"brand PNG PLTE length is invalid: {path.name}"
                )
            seen_plte = True
        elif chunk_type == b"IDAT":
            if idat_closed or chunk_length == 0:
                raise ReconciliationVerificationError(
                    f"brand PNG has an invalid IDAT sequence: {path.name}"
                )
            seen_idat = True
            idat_bytes += chunk_length
            if idat_bytes > MAX_BRAND_PNG_FILE_BYTES:
                raise ReconciliationVerificationError(
                    f"brand PNG IDAT budget is outside the accepted bound: "
                    f"{path.name}"
                )
        elif chunk_type == b"IEND":
            if seen_iend or chunk_length != 0 or not seen_idat:
                raise ReconciliationVerificationError(
                    f"brand PNG has an invalid IEND chunk: {path.name}"
                )
            seen_iend = True
        elif seen_idat:
            idat_closed = True

        offset = chunk_end
        if chunk_type == b"IEND":
            if offset != len(payload):
                raise ReconciliationVerificationError(
                    f"brand PNG has trailing data or multiple IEND chunks: "
                    f"{path.name}"
                )
            break

    if not seen_iend:
        raise ReconciliationVerificationError(
            f"brand PNG is missing its unique IEND chunk: {path.name}"
        )


def verify_brand_package() -> None:
    actual_files = {path.name for path in BRAND_DIRECTORY.iterdir() if path.is_file()}
    expected_files = set(EXPECTED_BRAND_HASHES)
    if actual_files != expected_files:
        raise ReconciliationVerificationError(
            "brand package file set differs from its accepted sole-source "
            f"baseline: missing={sorted(expected_files - actual_files)}, "
            f"unexpected={sorted(actual_files - expected_files)}"
        )

    instruction_rows = _read_csv(BRAND_INSTRUCTIONS)
    instructions = {
        row["Document Name"]: (row["Usage Scope"], row["Instruction"])
        for row in instruction_rows
    }
    if len(instruction_rows) != 6 or instructions != EXPECTED_BRAND_INSTRUCTIONS:
        raise ReconciliationVerificationError(
            "brand usage instructions differ from the accepted sole-source CSV"
        )

    for filename, expected_hash in EXPECTED_BRAND_HASHES.items():
        path = BRAND_DIRECTORY / filename
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise ReconciliationVerificationError(
                f"brand asset hash differs for {filename}: {actual_hash}"
            )
        if path.suffix.lower() == ".svg":
            _verify_svg_is_self_contained(path)
        elif path.suffix.lower() == ".png":
            _verify_png_is_safe(path)


def verify_generated_artifacts() -> None:
    commands = (
        ("scripts/extract_v1_2_docx_artifacts.py", "--check"),
        ("scripts/generate_v1_2_coverage_matrix.py", "--check"),
        ("scripts/reconcile_v1_2_traceability.py",),
    )
    for command in commands:
        subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            check=True,
        )


def main() -> int:
    verify_generated_artifacts()
    verify_erp_customization_requirements_document()
    verify_trace_sets()
    verify_brand_package()
    print("V1.2 reconciliation verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
