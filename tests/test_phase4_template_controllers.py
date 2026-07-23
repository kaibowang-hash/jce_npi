from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

TEMPLATE_ID = UUID("2f4d63bf-4d51-4a17-aeb1-08116cb129fa")


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> Any:
        return self._previous


class Phase4TemplateControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "npi_core.project.frappe_validation",
        "npi_core.npi_core.doctype.npi_project_template.npi_project_template",
        (
            "npi_core.npi_core.doctype.npi_project_template_version"
            ".npi_project_template_version"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.template_code = "SYNTHETIC-P4-TEST"
        self.ValidationError = type("ValidationError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.flags = types.SimpleNamespace()

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        frappe.throw = throw

        def get_value(
            doctype: str,
            name: str,
            fields: list[str],
            *,
            as_dict: bool,
        ) -> AttrDict | None:
            self.assertEqual(doctype, "NPI Project Template")
            self.assertEqual(name, str(TEMPLATE_ID))
            self.assertEqual(fields, ["global_id", "template_code"])
            self.assertTrue(as_dict)
            return AttrDict(
                global_id=str(TEMPLATE_ID),
                template_code=self.template_code,
            )

        frappe.db = types.SimpleNamespace(get_value=get_value)

        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: datetime(2026, 7, 23, 12, 0, 0)
        frappe.model = model
        frappe.utils = utils

        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document
        sys.modules["frappe.utils"] = utils

        root_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_project_template.npi_project_template"
        )
        version_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_project_template_version"
            ".npi_project_template_version"
        )
        self.RootController = root_module.NPIProjectTemplate
        self.VersionController = version_module.NPIProjectTemplateVersion

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def root_document(self, *, template_code: object) -> StubDocument:
        return self.RootController(
            {
                "global_id": str(TEMPLATE_ID),
                "template_code": template_code,
                "title": "Synthetic Template",
            }
        )

    def version_document(
        self,
        *,
        title: object = "Synthetic Template Version",
        publication_state: object = "published",
        applicable_project_types: object = '["new_tool"]',
        reference_rules: list[AttrDict] | None = None,
        gates: list[AttrDict] | None = None,
        template_version: object = 1,
        published_at: object = None,
    ) -> StubDocument:
        document = self.VersionController(
            {
                "global_id": None,
                "project_template": str(TEMPLATE_ID),
                "template_global_id": None,
                "template_code": None,
                "template_version": template_version,
                "version_key": None,
                "optimistic_version": 1,
                "title": title,
                "publication_state": publication_state,
                "applicable_project_types": applicable_project_types,
                "reference_rules": reference_rules or [],
                "gates": gates
                if gates is not None
                else [AttrDict(gate_key="G0", title="Feasibility", sequence=1)],
                "snapshot_hash": None,
                "published_at": published_at,
            }
        )
        document.before_validate()
        return document

    def assert_controller_rejects(self, document: StubDocument) -> None:
        with self.assertRaises(self.ValidationError):
            document.validate()

    def test_root_template_code_reuses_domain_validation_and_normalization(
        self,
    ) -> None:
        document = self.root_document(template_code="  SYNTHETIC-P4/TEST  ")
        document.validate()
        self.assertEqual(document.template_code, "SYNTHETIC-P4/TEST")

        for invalid in (None, "", "bad code", "-BAD", "A" * 65):
            with self.subTest(invalid=invalid):
                self.assert_controller_rejects(
                    self.root_document(template_code=invalid)
                )

    def test_valid_version_is_canonical_and_hashes_the_domain_aggregate(self) -> None:
        document = self.version_document(
            title="  Synthetic Template Version  ",
            gates=[
                AttrDict(
                    gate_key="  G0  ",
                    title="  Feasibility  ",
                    sequence=1,
                )
            ],
        )
        document.validate()

        self.assertEqual(document.title, "Synthetic Template Version")
        self.assertEqual(document.gates[0].gate_key, "G0")
        self.assertEqual(document.gates[0].title, "Feasibility")
        self.assertEqual(len(document.snapshot_hash), 64)
        self.assertEqual(document.optimistic_version, 1)
        self.assertIsNotNone(document.published_at)

    def test_publication_timestamp_is_always_server_owned(self) -> None:
        forged = datetime(2000, 1, 1, 0, 0, 0)
        published = self.version_document(published_at=forged)
        published.validate()
        self.assertEqual(published.published_at, datetime(2026, 7, 23, 12, 0, 0))

        draft = self.version_document(
            publication_state="draft",
            published_at=forged,
        )
        draft.validate()
        self.assertIsNone(draft.published_at)

    def test_version_rejects_every_text_shape_that_repository_cannot_load(self) -> None:
        invalid_documents = (
            self.version_document(title="   "),
            self.version_document(title="T" * 141),
            self.version_document(
                gates=[AttrDict(gate_key="bad key", title="Feasibility", sequence=1)]
            ),
            self.version_document(
                gates=[AttrDict(gate_key="G0", title="   ", sequence=1)]
            ),
            self.version_document(
                gates=[AttrDict(gate_key="G0", title="T" * 141, sequence=1)]
            ),
        )
        for index, document in enumerate(invalid_documents):
            with self.subTest(index=index):
                self.assert_controller_rejects(document)

    def test_version_rejects_invalid_domain_collections_and_publish_state(self) -> None:
        invalid_documents = (
            self.version_document(
                gates=[AttrDict(gate_key="G0", title="Feasibility", sequence=0)]
            ),
            self.version_document(
                gates=[
                    AttrDict(gate_key="G0", title="Feasibility", sequence=1),
                    AttrDict(gate_key="g0", title="Duplicate", sequence=2),
                ]
            ),
            self.version_document(
                gates=[
                    AttrDict(gate_key="G0", title="Feasibility", sequence=1),
                    AttrDict(gate_key="G1", title="Authorization", sequence=1),
                ]
            ),
            self.version_document(
                reference_rules=[
                    AttrDict(
                        reference_type="unsupported",
                        required=0,
                        allow_multiple=0,
                    )
                ]
            ),
            self.version_document(
                reference_rules=[
                    AttrDict(
                        reference_type="customer",
                        required=1,
                        allow_multiple=0,
                    ),
                    AttrDict(
                        reference_type="customer",
                        required=0,
                        allow_multiple=1,
                    ),
                ]
            ),
            self.version_document(applicable_project_types="[]"),
            self.version_document(applicable_project_types='["unsupported"]'),
            self.version_document(
                applicable_project_types='["new_tool","new_tool"]'
            ),
            self.version_document(applicable_project_types='{"new_tool":true}'),
            self.version_document(publication_state="retired"),
            self.version_document(gates=[]),
            self.version_document(template_version=True),
        )
        for index, document in enumerate(invalid_documents):
            with self.subTest(index=index):
                self.assert_controller_rejects(document)

    def test_invalid_root_code_cannot_be_published_through_a_version(self) -> None:
        self.template_code = "bad code"
        document = self.version_document()
        self.assert_controller_rejects(document)


if __name__ == "__main__":
    unittest.main()
