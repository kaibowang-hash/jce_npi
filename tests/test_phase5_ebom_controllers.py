from __future__ import annotations

import importlib
import sys
import types
import unittest
from typing import Any
from unittest.mock import patch


sys.path.insert(0, "apps/npi_core")


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> Any:
        return self._previous

    def is_new(self) -> bool:
        return self._previous is None


class Phase5EngineeringBomControllerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.documents.frappe_validation",
        "npi_core.ebom.frappe_validation",
        "npi_core.npi_core.doctype.npi_ebom_policy.npi_ebom_policy",
        (
            "npi_core.npi_core.doctype.npi_ebom_policy_version"
            ".npi_ebom_policy_version"
        ),
        "npi_core.npi_core.doctype.npi_engineering_bom.npi_engineering_bom",
        (
            "npi_core.npi_core.doctype.npi_engineering_bom_revision"
            ".npi_engineering_bom_revision"
        ),
        (
            "npi_core.npi_core.doctype.npi_engineering_bom_line"
            ".npi_engineering_bom_line"
        ),
        (
            "npi_core.npi_core.doctype.npi_ebom_revision_lifecycle"
            ".npi_ebom_revision_lifecycle"
        ),
        (
            "npi_core.npi_core.doctype.npi_ebom_lifecycle_event"
            ".npi_ebom_lifecycle_event"
        ),
        (
            "npi_core.npi_core.doctype.npi_ebom_command_idempotency"
            ".npi_ebom_command_idempotency"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        self.PermissionError = type("PermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = self.PermissionError
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user="engineer@example.invalid")
        frappe.get_request_header = lambda name: (
            "trace-ebom-delete" if name == "X-Trace-ID" else None
        )
        self.after_rollback: list[Any] = []
        self.audit_inserts: list[dict[str, Any]] = []
        self.user_rows: dict[str, dict[str, object]] = {}

        class CallbackQueue:
            def add(queue_self, callback: Any) -> None:
                self.after_rollback.append(callback)

        class StubDatabase:
            after_rollback = CallbackQueue()

            def get_value(
                database_self,
                doctype: str,
                name: str,
                fields: list[str],
                *,
                as_dict: bool = False,
            ) -> dict[str, object] | None:
                if doctype == "User" and as_dict:
                    return self.user_rows.get(name)
                return None

            def commit(database_self) -> None:
                return None

            def rollback(database_self) -> None:
                return None

        class AuditDocument:
            def __init__(audit_self, values: dict[str, Any]) -> None:
                audit_self.values = values

            def insert(audit_self) -> "AuditDocument":
                self.audit_inserts.append(dict(audit_self.values))
                return audit_self

        frappe.db = StubDatabase()
        frappe.get_doc = lambda values: AuditDocument(values)

        def throw(message: str, error_type: type[Exception]) -> None:
            raise error_type(message)

        frappe.throw = throw
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = StubDocument
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = frappe_model
        sys.modules["frappe.model.document"] = frappe_document

        self.frappe = frappe
        self.helper = importlib.import_module("npi_core.ebom.frappe_validation")
        self.policy_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_ebom_policy.npi_ebom_policy"
        )
        self.policy_version_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_ebom_policy_version"
            ".npi_ebom_policy_version"
        )
        self.root_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_engineering_bom.npi_engineering_bom"
        )
        self.revision_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_engineering_bom_revision"
            ".npi_engineering_bom_revision"
        )
        self.line_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_engineering_bom_line"
            ".npi_engineering_bom_line"
        )
        self.lifecycle_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_ebom_revision_lifecycle"
            ".npi_ebom_revision_lifecycle"
        )
        self.event_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_ebom_lifecycle_event"
            ".npi_ebom_lifecycle_event"
        )
        self.receipt_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_ebom_command_idempotency"
            ".npi_ebom_command_idempotency"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            previous = self.saved_modules.get(name)
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def test_write_scopes_are_independent_and_restore_prior_flags(self) -> None:
        with self.assertRaises(self.PermissionError):
            self.helper.require_ebom_policy_write()
        with self.assertRaises(self.PermissionError):
            self.helper.require_ebom_command_write()
        with self.assertRaises(self.PermissionError):
            self.helper.require_ebom_lifecycle_write()

        self.frappe.flags.npi_ebom_command_write = "prior"
        with self.helper.ebom_command_write():
            self.helper.require_ebom_command_write()
            self.assertTrue(self.frappe.flags.npi_ebom_command_write)
            with self.assertRaises(self.PermissionError):
                self.helper.require_ebom_policy_write()
            with self.assertRaises(self.PermissionError):
                self.helper.require_ebom_lifecycle_write()
        self.assertEqual(self.frappe.flags.npi_ebom_command_write, "prior")

    def test_policy_and_content_controllers_reject_generic_writes(self) -> None:
        for controller in (
            self.policy_module.NPIEBOMPolicy(),
            self.policy_version_module.NPIEBOMPolicyVersion(),
            self.root_module.NPIEngineeringBOM(),
            self.revision_module.NPIEngineeringBOMRevision(),
            self.line_module.NPIEngineeringBOMLine(),
        ):
            with self.subTest(controller=type(controller).__name__), self.assertRaises(
                self.PermissionError
            ):
                controller.before_insert()

    def test_policy_publish_uses_only_exact_prior_draft_hash_as_server_owned(
        self,
    ) -> None:
        draft_hash = "a" * 64
        prior_draft = StubDocument(
            {
                "publication_state": "draft",
                "snapshot_hash": draft_hash,
            }
        )
        current = StubDocument({"snapshot_hash": draft_hash})

        self.assertEqual(
            self.policy_version_module._domain_snapshot_hash(
                current,
                prior_draft,
                self.policy_version_module.EngineeringBomPolicyState.PUBLISHED,
            ),
            "",
        )

        current.snapshot_hash = "b" * 64
        self.assertEqual(
            self.policy_version_module._domain_snapshot_hash(
                current,
                prior_draft,
                self.policy_version_module.EngineeringBomPolicyState.PUBLISHED,
            ),
            "b" * 64,
        )

        current.snapshot_hash = draft_hash
        prior_draft.publication_state = "published"
        self.assertEqual(
            self.policy_version_module._domain_snapshot_hash(
                current,
                prior_draft,
                self.policy_version_module.EngineeringBomPolicyState.PUBLISHED,
            ),
            draft_hash,
        )
        prior_draft.publication_state = "draft"
        self.assertEqual(
            self.policy_version_module._domain_snapshot_hash(
                current,
                prior_draft,
                self.policy_version_module.EngineeringBomPolicyState.DRAFT,
            ),
            draft_hash,
        )

    def test_lifecycle_event_and_receipt_use_operation_specific_scopes(self) -> None:
        lifecycle = self.lifecycle_module.NPIEBOMRevisionLifecycle()
        event = self.event_module.NPIEBOMLifecycleEvent()
        receipt = self.receipt_module.NPIEBOMCommandIdempotency(
            {"operation": "ebom.create"}
        )
        for controller in (lifecycle, event, receipt):
            with self.subTest(controller=type(controller).__name__), self.assertRaises(
                self.PermissionError
            ):
                controller.before_insert()

        with self.helper.ebom_lifecycle_write():
            lifecycle.before_insert()
            event.before_insert()
            lifecycle_receipt = self.receipt_module.NPIEBOMCommandIdempotency(
                {"operation": "ebom.release"}
            )
            lifecycle_receipt.before_insert()
        with self.helper.ebom_command_write():
            receipt.before_insert()

    def test_immutable_history_rejects_update_and_delete_inside_write_scope(self) -> None:
        revision = self.revision_module.NPIEngineeringBOMRevision()
        revision._previous = StubDocument()
        with self.helper.ebom_command_write(), self.assertRaises(self.PermissionError):
            revision.before_save()

        event = self.event_module.NPIEBOMLifecycleEvent()
        event._previous = StubDocument()
        with self.helper.ebom_lifecycle_write(), self.assertRaises(
            self.PermissionError
        ):
            event.before_save()

        for controller in (
            revision,
            event,
            self.root_module.NPIEngineeringBOM(),
        ):
            with self.subTest(controller=type(controller).__name__), self.assertRaises(
                self.PermissionError
            ):
                controller.on_trash()

    def test_delete_denial_queues_sanitized_audit_after_rollback(self) -> None:
        revision = self.revision_module.NPIEngineeringBOMRevision(
            {
                "doctype": "NPI Engineering BOM Revision",
                "global_id": "c2f4a4a5-57ba-44ea-abba-6d906d0922d1",
                "revision_number": 3,
            }
        )
        with self.assertRaises(self.PermissionError):
            revision.on_trash()

        self.assertEqual(len(self.after_rollback), 1)
        self.after_rollback.pop(0)()
        self.assertEqual(len(self.audit_inserts), 1)
        audit = self.audit_inserts[0]
        self.assertEqual(audit["operation"], "ebom.history.delete_attempt")
        self.assertEqual(audit["result"], "denied")
        self.assertEqual(audit["object_version"], 3)
        self.assertEqual(audit["trace_id"], "trace-ebom-delete")
        self.assertEqual(
            audit["input_summary"],
            {"doctype": "NPI Engineering BOM Revision"},
        )

    def test_policy_user_validation_fails_closed_without_raw_conversion_error(self) -> None:
        self.user_rows["reviewer@example.invalid"] = {
            "name": "reviewer@example.invalid",
            "enabled": 1,
            "user_type": "System User",
        }
        self.helper.validate_internal_ebom_policy_users(
            ("reviewer@example.invalid",)
        )

        self.user_rows["reviewer@example.invalid"]["enabled"] = "invalid"
        with self.assertRaises(self.ValidationError):
            self.helper.validate_internal_ebom_policy_users(
                ("reviewer@example.invalid",)
            )

    def test_revision_policy_hydration_selects_exact_policy_identity(self) -> None:
        class StopAfterPolicyProjection(Exception):
            pass

        calls: list[tuple[Any, ...]] = []

        def require_exact_parent(*args: Any, **kwargs: Any) -> dict[str, object]:
            calls.append((*args, kwargs))
            return {}

        ebom_id = "c2f4a4a5-57ba-44ea-abba-6d906d0922d1"
        project_id = "2b47c9da-9f8c-4d98-bf45-42985cd26a60"
        policy_id = "ed80d97e-42fe-4db0-9703-bbed01150908"
        revision = self.revision_module.NPIEngineeringBOMRevision(
            {
                "engineering_bom": ebom_id,
                "ebom_global_id": ebom_id,
                "tenant_id": "tenant-local",
                "project_global_id": project_id,
                "engineering_bom_key": "synthetic_ebom-controller",
                "policy_global_id": policy_id,
                "policy_version": 1,
                "policy_snapshot_hash": "a" * 64,
                "revision_snapshot": {},
            }
        )
        with patch.object(
            self.revision_module,
            "require_exact_parent",
            side_effect=require_exact_parent,
        ), patch.object(
            self.revision_module,
            "json_object",
            side_effect=StopAfterPolicyProjection,
        ), self.assertRaises(StopAfterPolicyProjection):
            revision.validate()

        self.assertEqual(len(calls), 2)
        policy_call = calls[1]
        self.assertEqual(policy_call[0], "NPI EBOM Policy Version")
        self.assertEqual(
            policy_call[1],
            {"policy_global_id": policy_id, "policy_version": 1},
        )
        selected = set(policy_call[-1]["extra_fields"])
        self.assertTrue(
            {
                "global_id",
                "policy_global_id",
                "policy_key",
                "policy_version",
                "title",
                "synthetic_namespace",
                "line_identity_mode",
                "quantity_scale",
                "maximum_nodes",
                "engineering_uoms",
                "attribute_keys",
                "creator_user_ids",
                "review_submitter_user_ids",
                "reviewer_user_ids",
                "release_authority_user_ids",
                "require_acyclic_graph",
                "require_closed_alternates",
                "require_effectivity_order",
            }.issubset(selected)
        )

    def test_initial_lifecycle_converts_canonical_revision_id_for_domain(self) -> None:
        revision_id = "c2f4a4a5-57ba-44ea-abba-6d906d0922d1"
        ebom_id = "ed80d97e-42fe-4db0-9703-bbed01150908"
        project_id = "2b47c9da-9f8c-4d98-bf45-42985cd26a60"
        lifecycle = self.lifecycle_module.NPIEBOMRevisionLifecycle(
            {
                "global_id": revision_id,
                "tenant_id": "tenant-local",
                "project_global_id": project_id,
                "engineering_bom": ebom_id,
                "ebom_global_id": ebom_id,
                "engineering_bom_revision": revision_id,
                "revision_global_id": revision_id,
                "revision_snapshot_hash": "a" * 64,
                "current_state": "draft",
                "lifecycle_version": 1,
                "last_event_global_id": None,
                "updated_by_user_id": "engineer@example.invalid",
                "updated_at": "2026-08-06 00:00:00.000000",
                "request_id": "request-lifecycle-create",
                "trace_id": "trace-lifecycle-create",
            }
        )

        with patch.object(
            self.lifecycle_module,
            "require_exact_parent",
            return_value={"global_id": revision_id},
        ):
            lifecycle.before_validate()
            lifecycle.validate()

        self.assertEqual(lifecycle.revision_global_id, revision_id)
        self.assertEqual(lifecycle.current_state, "draft")
        self.assertEqual(lifecycle.lifecycle_version, 1)


if __name__ == "__main__":
    unittest.main()
