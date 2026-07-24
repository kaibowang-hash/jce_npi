from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
CONTROLLER_ROOT = ROOT / "apps/npi_core/npi_core"

SYSTEM_MANAGER_ONLY = [
    {
        "role": "System Manager",
        "read": 1,
        "write": 1,
        "create": 1,
        "export": 0,
        "print": 0,
        "email": 0,
    }
]


class Phase4GateReviewHistoryMetadataTest(unittest.TestCase):
    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            field["fieldname"]: field
            for field in metadata["fields"]  # type: ignore[index]
        }

    def test_history_doctypes_are_read_only_system_manager_scaffolds(self) -> None:
        for folder in (
            "npi_gate_review_cycle",
            "npi_gate_review_record",
            "npi_gate_review_exception",
            "npi_gate_review_event",
            "npi_gate_decision_snapshot",
        ):
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                fields = self.fields(metadata)
                self.assertEqual(metadata.get("autoname"), "field:global_id")
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertEqual(metadata.get("read_only"), 1)
                self.assertEqual(metadata.get("track_changes"), 1)
                self.assertEqual(metadata.get("permissions"), SYSTEM_MANAGER_ONLY)
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in fields.values())
                )

    def test_cycle_has_exact_frozen_review_boundary(self) -> None:
        metadata = self.load("npi_gate_review_cycle")
        fields = self.fields(metadata)
        self.assertEqual(
            set(fields),
            {
                "global_id",
                "cycle_key",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "gate_shell",
                "cycle_number",
                "trigger",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "policy_snapshot",
                "authority_bindings",
                "selected_steps",
                "input_snapshot",
                "input_hash",
                "prior_cycle_global_id",
                "prior_decision_snapshot_global_id",
                "prior_decision_hash",
                "state",
                "optimistic_version",
                "started_by",
                "started_at",
            },
        )
        self.assertEqual(fields["cycle_key"].get("unique"), 1)
        self.assertEqual(fields["gate_shell"].get("fieldtype"), "Link")
        self.assertEqual(fields["gate_shell"].get("options"), "NPI Gate Shell")
        for fieldname in ("tenant_id", "project_global_id", "gate_global_id"):
            self.assertEqual(fields[fieldname].get("search_index"), 1)
        self.assertEqual(
            fields["trigger"].get("options"),
            "manual_start\nmanual_reopen\ndependency_change",
        )
        self.assertEqual(
            fields["state"].get("options"),
            "active\ndecided\ninvalidated",
        )

    def test_append_only_record_event_and_decision_fields_are_exact(self) -> None:
        expected = {
            "npi_gate_review_record": {
                "global_id",
                "review_key",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "cycle_global_id",
                "cycle_number",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "review_step_key",
                "review_step_sequence",
                "authority_slot",
                "assigned_member_global_id",
                "assigned_user_id",
                "assigned_display_name",
                "actor_user_id",
                "outcome",
                "opinion",
                "occurred_at",
                "reviewed_input_hash",
                "cycle_version_before",
                "cycle_version_after",
                "request_id",
                "trace_id",
                "record_snapshot",
                "record_snapshot_hash",
            },
            "npi_gate_review_event": {
                "global_id",
                "event_key",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "cycle_global_id",
                "successor_cycle_global_id",
                "action_global_id",
                "event_type",
                "actor_user_id",
                "occurred_at",
                "request_id",
                "trace_id",
                "payload",
                "payload_hash",
            },
            "npi_gate_decision_snapshot": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "cycle_global_id",
                "cycle_number",
                "outcome",
                "actor_user_id",
                "occurred_at",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "decision_snapshot",
                "snapshot_hash",
                "input_snapshot",
                "input_hash",
                "review_hashes",
                "exception_hashes",
                "cycle_version",
                "request_id",
                "trace_id",
            },
        }
        for folder, fieldnames in expected.items():
            with self.subTest(folder=folder):
                fields = self.fields(self.load(folder))
                self.assertEqual(set(fields), fieldnames)
        self.assertEqual(
            self.fields(self.load("npi_gate_review_record"))["review_key"].get(
                "unique"
            ),
            1,
        )
        self.assertEqual(
            self.fields(self.load("npi_gate_review_event"))["event_key"].get(
                "unique"
            ),
            1,
        )
        self.assertEqual(
            self.fields(self.load("npi_gate_decision_snapshot"))[
                "cycle_global_id"
            ].get("unique"),
            1,
        )

    def test_exception_fields_preserve_request_and_one_way_decision(self) -> None:
        fields = self.fields(self.load("npi_gate_review_exception"))
        self.assertEqual(
            set(fields),
            {
                "global_id",
                "exception_key",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "cycle_global_id",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "requirement_global_id",
                "requirement_key",
                "exception_kind",
                "reason",
                "risk",
                "requester_member_global_id",
                "requester_user_id",
                "requested_at",
                "expires_at",
                "closure_action_global_id",
                "state",
                "approver_authority_slot",
                "approver_member_global_id",
                "approver_user_id",
                "approval_opinion",
                "decided_at",
                "optimistic_version",
                "request_snapshot",
                "request_snapshot_hash",
                "decision_snapshot",
                "decision_snapshot_hash",
            },
        )
        self.assertEqual(fields["exception_key"].get("unique"), 1)
        self.assertEqual(
            fields["state"].get("options"),
            "pending\napproved\nrejected",
        )

    def test_controllers_use_one_flag_and_never_import_domain_or_bypass_frappe(self) -> None:
        validation = (
            CONTROLLER_ROOT / "gate_review/frappe_validation.py"
        ).read_text(encoding="utf-8")
        sources = [validation]
        for folder in (
            "npi_gate_review_cycle",
            "npi_gate_review_record",
            "npi_gate_review_exception",
            "npi_gate_review_event",
            "npi_gate_decision_snapshot",
        ):
            sources.append(
                (
                    DOCTYPE_ROOT
                    / folder
                    / f"{folder}.py"
                ).read_text(encoding="utf-8")
            )
        combined = "\n".join(sources)
        self.assertIn(
            'GATE_REVIEW_COMMAND_FLAG = "npi_gate_review_command_write"',
            validation,
        )
        self.assertIn("hashlib.sha256", validation)
        self.assertIn("deny_gate_review_history_delete", combined)
        self.assertNotIn("gate_review.domain", combined)
        self.assertNotIn("ignore_" + "permissions", combined)
        self.assertNotIn("frappe.db." + "sql", combined)


if __name__ == "__main__":
    unittest.main()
