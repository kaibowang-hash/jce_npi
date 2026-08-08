from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/npi_core/npi_core/tooling/frappe_repository.py"
SOURCE = PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APPLICABILITY_VALIDATOR_SOURCE = (
    ROOT
    / "apps/npi_core/npi_core/npi_core/doctype/npi_tooling_applicability/npi_tooling_applicability.py"
).read_text(encoding="utf-8")


def function(name: str) -> str:
    matches = [
        node
        for node in ast.walk(TREE)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name}, found {len(matches)}")
    value = ast.get_source_segment(SOURCE, matches[0])
    if value is None:
        raise AssertionError(f"Unable to read {name}")
    return value


class Phase6ToolingRepositoryTest(unittest.TestCase):
    def test_scope_authorizes_project_before_protected_master_resolution(self) -> None:
        value = function("authorize_scope")
        self.assertLess(
            value.index("self._authorized_project(project_id)"),
            value.index("self._master_for_project(project, tooling_master_id)"),
        )
        lowered = SOURCE.casefold()
        for forbidden in (
            "ignore_" "permissions",
            "frappe.db." "sql",
            "commit()",
            "rollback()",
            "http://",
            "https://",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_every_command_locks_project_and_seals_one_atomic_order(self) -> None:
        command_shapes = {
            "create_part": (
                "self._insert_receipt(",
                '"doctype": "NPI Engineering Part"',
                "self._insert_part_revision(",
                "root.save()",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_part_revision": (
                "self._insert_receipt(",
                "self._insert_part_revision(",
                "root.save()",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_requirement": (
                "self._insert_receipt(",
                "self._insert_requirement(",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_master": (
                "self._insert_receipt(",
                "self._insert_master(",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_applicability": (
                "self._insert_receipt(",
                "self._insert_applicability(",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_tooling_set": (
                "self._insert_receipt(",
                "self._insert_tooling_set(",
                "self._append_audit(",
                "response = self._tooling_set_collection(",
                "self._seal_receipt(",
            ),
            "create_tooling_intake": (
                "self._insert_receipt(",
                "self._insert_tooling_intake(",
                "self._append_audit(",
                "response = self._tooling_set_detail(",
                "self._seal_receipt(",
            ),
            "create_tooling_intake_evidence_reference": (
                "self._insert_receipt(",
                "self._insert_tooling_intake_evidence(",
                "self._append_audit(",
                "response = self._tooling_set_detail(",
                "self._seal_receipt(",
            ),
        }
        for name, atomic_order in command_shapes.items():
            with self.subTest(name=name):
                value = function(name)
                self.assertLess(
                    value.index("self._locked_authorized_project(project_id)"),
                    value.index("self._command_context("),
                )
                self.assertIn("with tooling_command_write():", value)
                positions = [value.index(fragment) for fragment in atomic_order]
                self.assertEqual(positions, sorted(positions))

    def test_reference_commands_replay_before_mutable_reference_resolution(self) -> None:
        requirement = function("create_requirement")
        self.assertLess(
            requirement.index("self._command_context("),
            requirement.index("self._part_revision_for_project("),
        )
        applicability = function("create_applicability")
        replay = applicability.index("self._command_context(")
        for fragment in (
            "self._same_tenant_master(",
            "self._part_revision_for_project(",
            "self._require_project_reference(project, product)",
            "self._require_project_reference(project, model)",
            "self._applicabilities(project)",
        ):
            self.assertLess(replay, applicability.index(fragment))

        set_create = function("create_tooling_set")
        replay = set_create.index("self._command_context(")
        for fragment in (
            "self._master_for_project(",
            "self._requirement_for_set(",
            "self._require_customer_reference(",
        ):
            self.assertLess(replay, set_create.index(fragment))

        intake = function("create_tooling_intake")
        replay = intake.index("self._command_context(")
        for fragment in (
            "self._master_for_project(",
            "self._tooling_set_for_project(",
            "self._intakes_for_set(",
        ):
            self.assertLess(replay, intake.index(fragment))

        evidence = function("create_tooling_intake_evidence_reference")
        replay = evidence.index("self._command_context(")
        for fragment in (
            "self._master_for_project(",
            "self._tooling_set_for_project(",
            "self._intake_for_set(",
            "self._file_revision_for_project(",
        ):
            self.assertLess(replay, evidence.index(fragment))

    def test_part_successor_uses_exact_version_current_predecessor_and_projection(self) -> None:
        value = function("create_part_revision")
        for fragment in (
            "int(root.optimistic_version) != expected_version",
            "require_current=True",
            "part.advance(revision)",
            "predecessor_global_id=part.current_revision_global_id",
            "predecessor_snapshot_hash=part.current_revision_snapshot_hash",
            "root.current_revision_global_id = str(advanced.current_revision_global_id)",
            "int(root.optimistic_version) != advanced.optimistic_version",
        ):
            self.assertIn(fragment, value)

    def test_applicability_binds_exact_scope_successor_and_effectivity(self) -> None:
        value = function("create_applicability")
        for fragment in (
            "self._same_tenant_master(project, tooling_master_id)",
            "require_current=True",
            "previous.applicability_version != expected_version",
            "validate_applicability_successor(previous, applicability)",
            "ensure_no_effectivity_overlap(applicability, retained)",
            "value.relationship_key_hash == applicability.relationship_key_hash",
        ):
            self.assertIn(fragment, value)
        reference = function("_require_project_reference")
        self.assertIn("len(matches) != 1", reference)
        self.assertIn("row.source_system", reference)
        self.assertIn("row.source_object_id", reference)
        insert = function("_insert_applicability")
        self.assertIn("_applicability_version_key(", insert)
        self.assertIn("value.tenant_id", insert)
        version_key = function("_applicability_version_key")
        self.assertIn("hashlib.sha256(", version_key)
        self.assertIn(
            'f"{tenant_id}:{relationship_global_id}:{applicability_version}".encode()',
            version_key,
        )
        self.assertIn(
            'f"{self.tenant_id}:{applicability.relationship_global_id}:"',
            APPLICABILITY_VALIDATOR_SOURCE,
        )
        self.assertIn(
            'f"{applicability.applicability_version}"',
            APPLICABILITY_VALIDATOR_SOURCE,
        )

    def test_applicability_diagnostic_covers_each_atomic_substage(self) -> None:
        value = function("create_applicability")
        for code in (
            "P601_APPLICABILITY_CREATE_PROJECT_LOCK",
            "P601_APPLICABILITY_CREATE_IDEMPOTENCY_CONTEXT",
            "P601_APPLICABILITY_CREATE_REFERENCE_LOAD",
            "P601_APPLICABILITY_CREATE_REFERENCE_VALIDATE",
            "P601_APPLICABILITY_CREATE_RETAINED_LOAD",
            "P601_APPLICABILITY_CREATE_PREDECESSOR_RESOLVE",
            "P601_APPLICABILITY_CREATE_DOMAIN_BUILD",
            "P601_APPLICABILITY_CREATE_DOMAIN_VALIDATE",
            "P601_APPLICABILITY_CREATE_RECEIPT_INSERT",
            "P601_APPLICABILITY_CREATE_RELATIONSHIP_INSERT",
            "P601_APPLICABILITY_CREATE_AUDIT_APPEND",
            "P601_APPLICABILITY_CREATE_RESPONSE_BUILD",
            "P601_APPLICABILITY_CREATE_RECEIPT_SEAL",
        ):
            with self.subTest(code=code):
                self.assertEqual(value.count(code), 1)

    def test_receipt_replay_revalidates_instance_actor_scope_payload_and_seal(self) -> None:
        value = function("_receipt_replay")
        for fragment in (
            '"tenant_id"',
            '"project_global_id"',
            '"actor_user_id": self.actor',
            '"operation"',
            '"idempotency_key_hash"',
            '"payload_hash"',
            '"target_object_type"',
            '"target_global_id"',
            '"response_hash"',
            '"sealed"',
            "sha256_json(response)",
            "for_update=True",
        ):
            self.assertIn(fragment, value)
        self.assertNotIn("frappe.session.user", value)

    def test_public_projection_is_bounded_and_keeps_later_truth_unavailable(self) -> None:
        cockpit = function("_cockpit_response")
        for fragment in (
            '"lifecycle": self._unavailable("lifecycle_policy_unavailable")',
            '"revision": self._tooling_revision_capability(project)',
            '"physicalSet": self._unavailable("physical_set_not_delivered")',
            '"trial": self._unavailable("trial_not_delivered")',
            '"erp": self._unavailable("erp_projection_unavailable")',
        ):
            self.assertIn(fragment, cockpit)
        for forbidden in (
            "lifecycleState",
            "setCount",
            "assetId",
            "shotCount",
            "credential",
            "erpnextEndpoint",
        ):
            self.assertNotIn(forbidden, cockpit)
        bounded = function("_bounded_documents")
        self.assertIn("limit_page_length=maximum + 1", bounded)
        self.assertIn("if len(names) > maximum", bounded)

    def test_physical_set_scope_intake_successor_and_file_evidence_are_exact(
        self,
    ) -> None:
        tooling_set = function("_tooling_set_for_project")
        for fragment in (
            "row.tenant_id",
            "row.project_global_id",
            "row.tooling_master_global_id",
        ):
            self.assertIn(fragment, tooling_set)
        customer = function("_require_customer_reference")
        self.assertIn('str(row.reference_type) == "customer"', customer)
        self.assertIn("len(matches) != 1", customer)

        intake = function("create_tooling_intake")
        for fragment in (
            "expected_version != previous.intake_version",
            "previous.intake_version + 1",
            "validate_intake_successor(previous, intake)",
            "ToolingIntakeVersionConflict",
        ):
            self.assertIn(fragment, intake)
        intake_collection = function("_intakes_for_set")
        self.assertIn("maximum=_MAX_INTAKES", intake_collection)
        self.assertIn("validate_intake_successor", intake_collection)

        file_revision = function("_file_revision_for_project")
        for fragment in (
            "row.tenant_id",
            "row.project_global_id",
            'str(row.scan_state) != "clean"',
            "has_live_private_file_identity(row)",
        ):
            self.assertIn(fragment, file_revision)
        evidence = function("create_tooling_intake_evidence_reference")
        self.assertIn("available_difference_ids", evidence)
        self.assertIn("ToolingEvidenceConflict", evidence)

    def test_set_queries_are_bounded_and_never_project_private_urls(self) -> None:
        for name, maximum in (
            ("_tooling_sets_for_master", "_MAX_SETS"),
            ("_intakes_for_set", "_MAX_INTAKES"),
            ("_evidence_for_set", "_MAX_EVIDENCE"),
        ):
            with self.subTest(name=name):
                self.assertIn(f"maximum={maximum}", function(name))
        response = function("_evidence_response")
        self.assertNotIn("fileUrl", response)
        self.assertNotIn("frappe_file_id", response)
        set_response = function("_tooling_set_response")
        for reason in (
            "formal_supplier_unavailable",
            "lifecycle_policy_unavailable",
            "erp_projection_unavailable",
        ):
            self.assertIn(reason, set_response)
        self.assertIn("self._tooling_set_source_revision_response(value)", set_response)


if __name__ == "__main__":
    unittest.main()
