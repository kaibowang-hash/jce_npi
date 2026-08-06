from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "apps/npi_integration/npi_integration/publish_request/frappe_repository.py"
)
SOURCE = PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


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


class Phase5PublishRequestRepositoryTest(unittest.TestCase):
    def test_queries_require_publish_authority_before_released_ebom_resolution(self) -> None:
        for name in ("list_requests", "request_detail"):
            with self.subTest(name=name):
                value = function(name)
                order = (
                    "self._authorized_project(project_id)",
                    "self._published_publish_policy_options(project)",
                    "self._released_context(",
                )
                positions = [value.index(fragment) for fragment in order]
                self.assertEqual(positions, sorted(positions))

    def test_create_is_actor_bound_replay_safe_and_atomically_sealed(self) -> None:
        value = function("create_request")
        order = (
            "self._locked_command_project(project_id)",
            "self._load_exact_publish_policy(",
            "self._require_publish_policy_actor(policy)",
            "self._released_context(",
            "command_payload_hash(",
            "self._receipt_replay(",
            "require_mutable_project(project)",
            "create_mock_publish_request(",
            "with publish_request_write()",
            "self._insert_receipt(",
            "self._insert_request_bundle(",
            "self._append_audit(",
            "response = request.public_dict()",
            "self._seal_receipt(",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        diagnostic_codes = (
            "P505_CREATE_PROJECT_LOCK",
            "P505_CREATE_POLICY_LOAD",
            "P505_CREATE_POLICY_AUTHORITY",
            "P505_CREATE_RELEASED_CONTEXT",
            "P505_CREATE_PAYLOAD_HASH",
            "P505_CREATE_IDEMPOTENCY_REPLAY",
            "P505_CREATE_PROJECT_MUTABILITY",
            "P505_CREATE_DOMAIN_BUILD",
            "P505_CREATE_TRANSACTION_SCOPE",
            "P505_CREATE_RECEIPT_INSERT",
            "P505_CREATE_AUDIT_APPEND",
            "P505_CREATE_RESPONSE_BUILD",
            "P505_CREATE_RECEIPT_SEAL",
        )
        for code in diagnostic_codes:
            with self.subTest(code=code):
                self.assertEqual(value.count(code), 1)

    def test_create_bundle_diagnostics_preserve_insert_order(self) -> None:
        request_bundle = function("_insert_request_bundle")
        node_bundle = function("_insert_node_bundle")
        self.assertEqual(request_bundle.count("P505_CREATE_REQUEST_INSERT"), 1)
        order = (
            "P505_CREATE_MAPPING_INSERT",
            "P505_CREATE_NODE_INSERT",
            "P505_CREATE_RESULT_INSERT",
        )
        positions = [node_bundle.index(code) for code in order]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(node_bundle.count(".insert()"), 3)

    def test_receipt_replay_revalidates_scope_actor_payload_and_sealed_hash(self) -> None:
        value = function("_receipt_replay")
        for fragment in (
            '"tenant_id"',
            '"project_global_id"',
            '"actor_user_id"',
            '"operation"',
            '"idempotency_key_hash"',
            '"payload_hash"',
            '"request_global_id"',
            '"response_hash"',
            '"sealed"',
            "sha256_json(response)",
        ):
            self.assertIn(fragment, value)

    def test_mock_bundle_has_no_dispatch_outbox_or_formal_identifiers(self) -> None:
        value = function("_insert_node_bundle")
        self.assertIn('"source_system": "NPI_ONE"', value)
        self.assertIn('"mapping_state": "unmapped"', value)
        self.assertIn('"phase5_dispatch_allowed": 0', value)
        self.assertNotIn("formal_item_code", value)
        self.assertNotIn("formal_mbom_id", value)
        lowered = SOURCE.casefold()
        for forbidden in (
            "outbox",
            "http://",
            "https://",
            "requests.",
            "frappe.db." "sql",
            "ignore_" "permissions",
            "commit()",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_receipt_command_hash_is_distinct_from_frozen_request_hash(self) -> None:
        controller = (
            ROOT
            / "apps/npi_integration/npi_integration/npi_integration/doctype/"
            "npi_ebom_publish_command_idempotency/"
            "npi_ebom_publish_command_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertIn('extra_fields=("payload_hash",)', controller)
        self.assertIn('response.get("payloadHash")', controller)
        parent_filter = controller.split("request = require_exact_parent(", 1)[1].split(
            ")\n            response =", 1
        )[0]
        self.assertNotIn('"payload_hash": self.payload_hash', parent_filter)

    def test_receipt_seal_compares_frappe_datetime_by_utc_value(self) -> None:
        controller = (
            ROOT
            / "apps/npi_integration/npi_integration/npi_integration/doctype/"
            "npi_ebom_publish_command_idempotency/"
            "npi_ebom_publish_command_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'created_at = utc_datetime_text(self.created_at, _("Created At"))',
            controller,
        )
        self.assertIn(
            'before_created_at = utc_datetime_text(\n'
            '                before.created_at, _("Created At")\n'
            "            )",
            controller,
        )
        immutable = controller.split("immutable = (", 1)[1].split(")\n", 1)[0]
        self.assertNotIn('"created_at"', immutable)
        self.assertIn("before_created_at != created_at", controller)


if __name__ == "__main__":
    unittest.main()
