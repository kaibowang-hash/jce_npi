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
EXPECTED_UX_REMEDIATION_ALLOCATION = {
    "UX-003": ("9", "PLANNED_FULL_PRODUCT_UAT"),
    "UX-004": ("6", "ANCHORED_P6_01_TOOLING_WORKSPACE"),
    "UX-007": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-011": ("5", "TECHNICAL_VERIFIED"),
    "UX-016": ("8", "ANCHORED_P6_07_PHASE_8_ASYNC_JOB_TRUTH"),
    "UX-018": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-020": ("7", "PLANNED_PHASE_7_MOBILE_FIELD_ACTIONS"),
    "UX-026": ("5", "PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD"),
    "UX-027": ("5", "TECHNICAL_VERIFIED_FOUNDATION"),
    "UX-028": ("5", "TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD"),
    "UX-030": ("5", "TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD"),
    "UX-035": ("5", "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE"),
    "UX-036": ("5", "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE"),
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
                f"{requirement_id} must retain the completed P5-06 trace truth"
            )
        if actual_evidence != expected_evidence:
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
    if len(tooling_ids) != 18:
        raise ReconciliationVerificationError(
            "expected 18 anchored Phase 6 Tooling requirements"
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
    verify_trace_sets()
    verify_brand_package()
    print("V1.2 reconciliation verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
