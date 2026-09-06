"""Original, reviewable new-tool collaboration draft; never an approval policy.

Concept-to-launch structure follows the existing NPI G0-G7 domain and the
general APQP phases described by AIAG. No proprietary checklist is copied.
MC means Materials Control. Named personnel, dates, durations, exception rules,
Gate approvers and customer-specific acceptance criteria require configuration.
"""

from __future__ import annotations

import json
from uuid import uuid4


DEPARTMENTS = (
    "engineering",
    "quality",
    "purchasing",
    "sales",
    "warehouse",
    "materials_control",
)


def _gate_definitions():
    from frappe import _

    return (
        ("G0", _("Customer requirements and opportunity review")),
        ("G1", _("Feasibility and project authorization")),
        ("G2", _("Product design and DFM baseline")),
        ("G3", _("Tooling design and manufacturing authorization")),
        ("G4", _("Tooling completion and trial readiness")),
        ("G5", _("Trial validation and sample approval review")),
        ("G6", _("NPI and pilot production readiness")),
        ("G7", _("Production handover and launch review")),
    )


def draft_documents(template_code: str, title: str) -> tuple[dict, dict, dict]:
    """Return fresh administrative documents, all unpublished, with no defaults installed."""
    template_id, policy_id = str(uuid4()), str(uuid4())

    def lifecycle(initial, states):
        return {
            "initialStateKey": initial,
            "states": [
                {"key": key, "labelSource": label, "terminal": terminal}
                for key, label, terminal in states
            ],
        }

    common = (
        ("open", "Open", False),
        ("in_progress", "In progress", False),
        ("closed", "Closed", True),
    )
    policy = {
        "doctype": "NPI Project Work Policy Version",
        "policy_global_id": policy_id,
        "policy_key": "injection_collaboration",
        "policy_version": 1,
        "title": title,
        "publication_state": "draft",
        "role_keys": json.dumps(DEPARTMENTS),
        "wbs_states": json.dumps(
            lifecycle(
                "not_started",
                (
                    ("not_started", "Not started", False),
                    ("in_progress", "In progress", False),
                    ("completed", "Completed", True),
                    ("cancelled", "Cancelled", True),
                ),
            )
        ),
        "work_item_lifecycles": json.dumps(
            [
                {
                    "kind": "risk",
                    **lifecycle(
                        "identified", (("identified", "Identified", False), *common)
                    ),
                },
                {"kind": "issue", **lifecycle("open", common)},
                {"kind": "action", **lifecycle("open", common)},
                {
                    "kind": "decision_request",
                    **lifecycle(
                        "requested", (("requested", "Requested", False), *common)
                    ),
                },
            ]
        ),
    }
    return (
        {
            "doctype": "NPI Project Template",
            "global_id": template_id,
            "template_code": template_code,
            "title": title,
            "enabled": 1,
        },
        {
            "doctype": "NPI Project Template Version",
            "project_template": template_id,
            "template_version": 1,
            "title": title,
            "publication_state": "draft",
            "applicable_project_types": json.dumps(["new_tool"]),
            "reference_rules": [],
            "gates": [
                {"gate_key": key, "title": label, "sequence": index}
                for index, (key, label) in enumerate(_gate_definitions(), 1)
            ],
        },
        policy,
    )
