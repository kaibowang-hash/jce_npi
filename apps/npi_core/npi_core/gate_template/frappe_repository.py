from __future__ import annotations

import json
from uuid import UUID, uuid5

import frappe

from npi_core.gate_template.domain import (
    EvidenceKind,
    GateRequirementClassification,
    GateRequirementDefinition,
    GateRequirementPriority,
    GateTemplatePublicationState,
    GateTemplateSnapshot,
    GateTemplateVersion,
)
from npi_core.project.domain import ProjectType


def load_published_gate_template_version(
    gate_template_global_id: UUID,
    gate_template_version: int,
    expected_snapshot_hash: str,
    *,
    require_enabled_root: bool = False,
) -> GateTemplateVersion | None:
    """Load and verify one exact immutable published Gate Template version."""
    version_key = f"{gate_template_global_id}:{gate_template_version}"
    document = _optional_doc("NPI Gate Template Version", version_key)
    if document is None:
        return None
    root = _optional_doc("NPI Gate Template", str(document.gate_template))
    if root is None or (require_enabled_root and int(root.enabled or 0) != 1):
        return None
    if str(root.global_id) != str(document.gate_template_global_id) or str(
        root.template_code
    ) != str(document.gate_template_code):
        raise ValueError("Persisted Gate Template root integrity failed.")

    template = GateTemplateVersion(
        global_id=UUID(str(document.global_id)),
        gate_template_global_id=UUID(str(document.gate_template_global_id)),
        gate_template_code=str(document.gate_template_code),
        gate_template_version=int(document.gate_template_version),
        version=int(document.optimistic_version),
        title=str(document.title),
        publication_state=GateTemplatePublicationState(str(document.publication_state)),
        applicable_project_types=tuple(
            ProjectType(str(value))
            for value in _json_array(document.applicable_project_types)
        ),
        requirements=tuple(
            GateRequirementDefinition(
                key=str(row.requirement_key),
                title=str(row.title),
                classification=GateRequirementClassification(str(row.classification)),
                priority=GateRequirementPriority(str(row.priority)),
                allowed_evidence_kinds=tuple(
                    EvidenceKind(str(value))
                    for value in _json_array(row.allowed_evidence_kinds)
                ),
            )
            for row in document.requirements
        ),
    )
    expected_global_id = uuid5(
        template.gate_template_global_id,
        f"gate-template-version:{template.gate_template_version}",
    )
    if (
        template.publication_state is not GateTemplatePublicationState.PUBLISHED
        or template.gate_template_global_id != gate_template_global_id
        or template.gate_template_version != gate_template_version
        or template.global_id != expected_global_id
        or str(document.version_key) != version_key
        or str(document.snapshot_hash) != template.snapshot_hash
        or expected_snapshot_hash != template.snapshot_hash
    ):
        raise ValueError("Persisted Gate Template version integrity failed.")
    return template


def load_exact_gate_template_snapshot(
    gate_template_global_id: UUID,
    gate_template_version: int,
    expected_snapshot_hash: str,
) -> GateTemplateSnapshot | None:
    """Return an ordered canonical requirement snapshot for one exact ref."""
    template = load_published_gate_template_version(
        gate_template_global_id,
        gate_template_version,
        expected_snapshot_hash,
    )
    return None if template is None else template.snapshot()


def load_available_gate_template_snapshot(
    gate_template_global_id: UUID,
    gate_template_version: int,
    expected_snapshot_hash: str,
) -> GateTemplateSnapshot | None:
    """Return an exact published version only while its root is selectable."""
    template = load_published_gate_template_version(
        gate_template_global_id,
        gate_template_version,
        expected_snapshot_hash,
        require_enabled_root=True,
    )
    return None if template is None else template.snapshot()


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _json_array(value: object) -> list[object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Persisted Gate Template JSON value must be an array.")
    return parsed
