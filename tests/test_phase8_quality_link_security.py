from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apps/npi_integration/npi_integration/quality_link"
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"


def is_direct_sql(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "sql" and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "db" and isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == "frappe"


class Phase8QualityLinkSecurityTest(unittest.TestCase):
    def test_write_capability_is_exact_and_restores_flags_after_exception(self) -> None:
        frappe = types.ModuleType("frappe")
        frappe.flags = types.SimpleNamespace(existing="kept")
        frappe.session = types.SimpleNamespace(user="quality@example.invalid")
        frappe.get_roles = lambda _actor: ["NPI API User", "System Manager"]
        frappe.PermissionError = type("PinnedPermissionError", (RuntimeError,), {})
        frappe._ = lambda value: value
        frappe.throw = lambda message, error: (_ for _ in ()).throw(error(message))
        path = MODULE / "frappe_validation.py"
        spec = importlib.util.spec_from_file_location("quality_link_guard_test", path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frappe": frappe, spec.name: module}):
            assert spec.loader is not None
            spec.loader.exec_module(module)
            calls: list[tuple[str, str, bool]] = []

            class Document:
                def __init__(self, doctype: str) -> None:
                    self.doctype = doctype

                def insert(self, *, ignore_permissions: bool = False):
                    calls.append(("insert", self.doctype, ignore_permissions))
                    return self

                def save(self, *, ignore_permissions: bool = False):
                    calls.append(("save", self.doctype, ignore_permissions))
                    return self

            revision = Document("NPI Formal Quality Link Revision")
            head = Document("NPI Formal Quality Link Head")
            receipt = Document("NPI Formal Quality Link Command Idempotency")
            audit = Document("NPI Audit Event")
            with self.assertRaisesRegex(RuntimeError, "synthetic boundary"):
                with module.quality_link_command_write(
                    service_actor_user_id="quality@example.invalid",
                    scope="test",
                ) as capability:
                    module.require_quality_link_write("NPI Formal Quality Link Revision", "insert")
                    module.insert_quality_link_support_document(
                        revision,
                        capability=capability,
                    )
                    module.insert_quality_link_support_document(
                        head,
                        capability=capability,
                    )
                    module.save_quality_link_support_document(
                        head,
                        capability=capability,
                    )
                    module.insert_quality_link_support_document(
                        receipt,
                        capability=capability,
                    )
                    module.save_quality_link_support_document(
                        receipt,
                        capability=capability,
                    )
                    self.assertTrue(
                        getattr(frappe.flags, module.AUDIT_APPEND_FLAG, False)
                    )
                    with self.assertRaises(frappe.PermissionError):
                        module.insert_quality_link_support_document(
                            audit,
                            capability=capability,
                        )
                    with self.assertRaises(frappe.PermissionError):
                        module.save_quality_link_support_document(
                            revision,
                            capability=capability,
                        )
                    forged = module.QualityLinkWriteCapability(
                        actor="quality@example.invalid",
                        scope="test",
                        allowed=module.QUALITY_LINK_COMMAND_WRITES,
                    )
                    with self.assertRaises(frappe.PermissionError):
                        module.insert_quality_link_support_document(
                            revision,
                            capability=forged,
                        )
                    frappe.session.user = "other@example.invalid"
                    with self.assertRaises(frappe.PermissionError):
                        module.save_quality_link_support_document(
                            head,
                            capability=capability,
                        )
                    frappe.session.user = "quality@example.invalid"
                    raise RuntimeError("synthetic boundary")
            self.assertEqual(frappe.flags.existing, "kept")
            for flag in (
                module.QUALITY_LINK_REVISION_WRITE_FLAG,
                module.QUALITY_LINK_HEAD_WRITE_FLAG,
                module.QUALITY_LINK_RECEIPT_WRITE_FLAG,
                module.AUDIT_APPEND_FLAG,
            ):
                self.assertFalse(hasattr(frappe.flags, flag))
            self.assertIsNone(module._CURRENT.get())
            with self.assertRaises(frappe.PermissionError):
                module.insert_quality_link_support_document(
                    revision,
                    capability=capability,
                )
            self.assertEqual(
                calls,
                [
                    ("insert", "NPI Formal Quality Link Revision", True),
                    ("insert", "NPI Formal Quality Link Head", True),
                    ("save", "NPI Formal Quality Link Head", True),
                    (
                        "insert",
                        "NPI Formal Quality Link Command Idempotency",
                        True,
                    ),
                    (
                        "save",
                        "NPI Formal Quality Link Command Idempotency",
                        True,
                    ),
                ],
            )

            for actor in ("Guest", "Administrator", " quality@example.invalid "):
                with self.subTest(actor=actor), self.assertRaises(
                    frappe.PermissionError
                ):
                    frappe.session.user = actor
                    module.quality_link_command_write(
                        service_actor_user_id=actor,
                        scope="test",
                    ).__enter__()
            frappe.session.user = "quality@example.invalid"
            frappe.get_roles = lambda _actor: ["System Manager"]
            with self.assertRaises(frappe.PermissionError):
                module.quality_link_command_write(
                    service_actor_user_id="quality@example.invalid",
                    scope="test",
                ).__enter__()
            frappe.get_roles = lambda _actor: ["NPI API User"]
            with self.assertRaises(frappe.PermissionError):
                with module.quality_link_write_capability(
                    service_actor_user_id="quality@example.invalid",
                    scope="test",
                    allowed=frozenset(
                        {("NPI Formal Quality Link Revision", "insert")}
                    ),
                ) as narrow_capability:
                    module.insert_quality_link_support_document(
                        head,
                        capability=narrow_capability,
                    )
            self.assertEqual(len(calls), 5)

    def test_checkpoint_two_is_target_worker_adapter_network_and_direct_sql_free(self) -> None:
        paths = list(MODULE.glob("*.py"))
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        non_validation = "\n".join(
            path.read_text(encoding="utf-8")
            for path in paths
            if path.name != "frappe_validation.py"
        )
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
            self.assertFalse({"requests", "httpx", "socket", "urllib.request"} & imports)
            self.assertFalse(any(is_direct_sql(node) for node in ast.walk(tree)))
        for forbidden in ("enqueue(", "scheduler_events", "adapter_registry", "outbox"):
            self.assertNotIn(forbidden, combined.casefold())
        self.assertNotIn("ignore_permissions", non_validation)

    def test_public_surface_is_exact_internal_project_first_and_no_raw_crud(self) -> None:
        api = (ROOT / "apps/npi_integration/npi_integration/quality_link_api.py").read_text(encoding="utf-8")
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        self.assertEqual(api.count("@frappe.whitelist"), 3)
        self.assertEqual(api.count("authenticated_user()"), 1)
        self.assertIn("if principal.is_external:", api)
        self.assertIn("if not repository.authorize_scope(project_id):", api)
        self.assertIn("require_csrf_token()", api)
        self.assertIn("actor_idempotency_key_hash", api)
        self.assertIn("frappe.db.commit()", api)
        self.assertIn("frappe.db.rollback()", api)
        for forbidden in ("ignore_permissions", "frappe.db." "sql", "enqueue(", "requests.", "httpx."):
            self.assertNotIn(forbidden, api)
        for marker in (
            "formal-quality-links$",
            "formal-quality-links/",
            "formal-quality-links:link-observed-reference$",
        ):
            self.assertIn(marker, bff)

    def test_capability_is_request_local_exact_and_finally_restored(self) -> None:
        source = (MODULE / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in (
            "ContextVar",
            "actor: str",
            "allowed: frozenset[tuple[str, str]]",
            "service_actor_user_id.casefold()",
            '"NPI API User" not in set(get_roles(service_actor_user_id) or ())',
            "try:",
            "finally:",
            "_CURRENT.reset(token)",
            "AUDIT_APPEND_FLAG",
        ):
            self.assertIn(marker, source)
        tree = ast.parse(source)
        permission_bypasses = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr in {"insert", "save"}
                    and any(
                        keyword.arg == "ignore_permissions"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in call.keywords
                    )
                ):
                    permission_bypasses.append((node.name, call.func.attr))
        self.assertEqual(
            permission_bypasses,
            [
                ("insert_quality_link_support_document", "insert"),
                ("save_quality_link_support_document", "save"),
            ],
        )
        self.assertIn("QUALITY_LINK_COMMAND_WRITES", source)
        self.assertIn("quality_link_command_write", source)

    def test_metadata_has_no_rows_permissions_or_formal_pass_field(self) -> None:
        for folder in DOCTYPE_ROOT.glob("npi_formal_quality_link_*"):
            metadata = json.loads((folder / f"{folder.name}.json").read_text(encoding="utf-8"))
            self.assertNotIn("fixtures", metadata)
            self.assertNotIn("records", metadata)
            self.assertNotIn("passed", {field["fieldname"] for field in metadata["fields"]})
            self.assertTrue(all(not permission.get("write", 0) and not permission.get("create", 0) for permission in metadata["permissions"]))

    def test_checkpoint_three_reconciliation_is_read_only_and_identity_safe(self) -> None:
        source = (MODULE / "frappe_repository.py").read_text(encoding="utf-8")
        start = source.index("    def _link_reconciliation(")
        end = source.index("    @staticmethod\n    def _head_matches_project", start)
        reconciliation = source[start:end]
        for forbidden in (
            ".insert(",
            ".save(",
            "frappe.db.commit",
            "frappe.db.rollback",
            "ignore_permissions",
            "enqueue(",
            "create_audit_event",
        ):
            self.assertNotIn(forbidden, reconciliation)
        for marker in (
            '"tenant_id": str(project.tenant_id)',
            '"project_global_id": str(project.global_id)',
            '"projection_kind": "formal_quality_status"',
            'limit_page_length=2',
            'order_by="global_id asc"',
            "current.project.global_id != source.project_global_id",
            "current.trial_round_global_id != observation.scope_global_id",
        ):
            self.assertIn(marker, reconciliation)
        self.assertNotIn("latest", reconciliation.casefold())
        api = (ROOT / "apps/npi_integration/npi_integration/quality_link_api.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(api.count("@frappe.whitelist"), 3)
        self.assertIn("_query_response(", api)
        self.assertNotIn("currentGlobalId", api)

    def test_checkpoint_four_capability_and_projection_identity_are_server_authoritative(self) -> None:
        repository = (MODULE / "frappe_repository.py").read_text(encoding="utf-8")
        api = (ROOT / "apps/npi_integration/npi_integration/quality_link_api.py").read_text(encoding="utf-8")
        projection = (
            ROOT / "apps/npi_integration/npi_integration/projections/frappe_repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn("self._can_administer_project(project, project_id)", repository)
        self.assertIn('set(permissions) != {"view", "link"}', api)
        self.assertIn('type(permissions["link"]) is not bool', api)
        for marker in (
            '"headGlobalId": str(head.global_id)',
            '"headOptimisticVersion": int(head.optimistic_version)',
            '"headHash": str(head.head_hash)',
        ):
            self.assertIn(marker, projection)
        for source in (repository, api, projection):
            self.assertNotIn("ignore_permissions", source)


if __name__ == "__main__":
    unittest.main()
