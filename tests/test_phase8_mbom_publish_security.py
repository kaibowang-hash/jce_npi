from __future__ import annotations

import importlib
import sys
import types
import unittest


sys.path.insert(0, "apps/npi_core")
sys.path.insert(0, "apps/npi_integration")


class StubDocument:
    doctype = "NPI MBOM Publish Request"

    def __init__(self) -> None:
        self._previous = None
        self.flags = types.SimpleNamespace(in_insert=False)

    def get_doc_before_save(self) -> object | None:
        return self._previous


class Phase8MbomPublishSecurityTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.documents.frappe_validation",
        "npi_integration.mbom_publish.frappe_validation",
        "npi_integration.mbom_publish.doctype_base",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.PermissionError = type("PermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.PermissionError = self.PermissionError
        frappe.flags = types.SimpleNamespace()

        def throw(message: str, error_type: type[Exception]) -> None:
            raise error_type(message)

        frappe.throw = throw
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = StubDocument
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = frappe_model
        sys.modules["frappe.model.document"] = frappe_document

        core_validation = types.ModuleType("npi_core.documents.frappe_validation")
        core_validation.actor_text = lambda value, label: value
        core_validation.assert_immutable_fields = lambda *args: None
        core_validation.canonical_uuid = lambda value, label: value
        core_validation.lowercase_sha256 = lambda value, label: value
        core_validation.nonnegative_integer = lambda value, label: value
        core_validation.positive_integer = lambda value, label: value
        core_validation.required_text = lambda value, label, maximum: value
        core_validation.tenant_text = lambda value: value
        sys.modules["npi_core.documents.frappe_validation"] = core_validation

        self.frappe = frappe
        self.helper = importlib.import_module(
            "npi_integration.mbom_publish.frappe_validation"
        )
        self.base = importlib.import_module("npi_integration.mbom_publish.doctype_base")

    def tearDown(self) -> None:
        for name in self.MODULES:
            previous = self.saved_modules.get(name)
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def test_write_scopes_are_actor_bound_independent_and_restore_flags(self) -> None:
        for guard in (
            self.helper.require_mbom_request_write,
            self.helper.require_mbom_node_write,
            self.helper.require_mbom_mapping_write,
            self.helper.require_mbom_outbox_write,
        ):
            with self.subTest(guard=guard.__name__), self.assertRaises(
                self.PermissionError
            ):
                guard()

        self.frappe.flags.npi_mbom_publish_request_write = "prior"
        with self.helper.mbom_request_transaction_write(
            "engineer@example.invalid"
        ) as capability:
            self.assertEqual(capability.scope, "request")
            self.helper.require_mbom_request_write()
            self.helper.require_mbom_node_write()
            self.helper.require_mbom_outbox_write()
            self.helper.require_mbom_capability(
                "NPI MBOM Publish Request", "insert"
            )
            with self.assertRaises(self.PermissionError):
                self.helper.require_mbom_mapping_write()
            with self.assertRaises(self.PermissionError):
                self.helper.require_mbom_capability("NPI MBOM Mapping Head", "save")
        self.assertEqual(
            self.frappe.flags.npi_mbom_publish_request_write,
            "prior",
        )
        for flag in (
            "npi_mbom_publish_node_write",
            "npi_mbom_publish_idempotency_write",
            "npi_mbom_publish_stream_guard_write",
            "npi_mbom_outbox_write",
            "npi_audit_append",
        ):
            self.assertFalse(hasattr(self.frappe.flags, flag))
        with self.assertRaises(self.PermissionError):
            self.helper.require_mbom_capability("NPI MBOM Publish Request", "insert")

    def test_invalid_or_privileged_capability_actors_fail_closed(self) -> None:
        for actor in ("", " engineer@example.invalid", "Guest", "guest", "Administrator"):
            with self.subTest(actor=actor), self.assertRaises(self.PermissionError):
                with self.helper.mbom_request_transaction_write(actor):
                    self.fail("invalid actor entered a write scope")

    def test_support_document_matches_frappe_insert_then_before_save_lifecycle(self) -> None:
        helper = self.helper

        class RequestDocument(self.base.MbomSupportDocument):
            write_guard = staticmethod(helper.require_mbom_request_write)

        document = RequestDocument()
        with self.assertRaises(self.PermissionError):
            document.before_insert()
        with helper.mbom_request_transaction_write("engineer@example.invalid"):
            document.before_insert()
            document.flags.in_insert = True
            document.before_save()
            document.flags.in_insert = False
            with self.assertRaises(self.PermissionError):
                document.before_save()
            with self.assertRaises(self.PermissionError):
                document.on_trash()
        document.flags.in_insert = True
        with self.assertRaises(self.PermissionError):
            document.before_save()

    def test_stream_guard_and_mapping_head_use_real_save_capabilities(self) -> None:
        helper = self.helper

        class StreamGuardDocument(self.base.MbomSupportDocument):
            doctype = "NPI MBOM Publish Stream Guard"
            append_only = False
            write_guard = staticmethod(helper.require_mbom_stream_guard_write)

        class MappingHeadDocument(self.base.MbomSupportDocument):
            doctype = "NPI MBOM Mapping Head"
            append_only = False
            write_guard = staticmethod(helper.require_mbom_mapping_write)

        stream = StreamGuardDocument()
        stream._previous = object()
        with helper.mbom_request_transaction_write("engineer@example.invalid"):
            stream.before_save()
        with self.assertRaises(self.PermissionError):
            stream.before_save()

        head = MappingHeadDocument()
        head._previous = object()
        with helper.mbom_result_transaction_write("worker@example.invalid"):
            head.before_save()
        with self.assertRaises(self.PermissionError):
            head.before_save()


if __name__ == "__main__":
    unittest.main()
