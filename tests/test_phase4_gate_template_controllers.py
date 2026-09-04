from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")


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


class GateTemplateControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "npi_core.project.frappe_validation",
        "npi_core.npi_core.doctype.npi_gate_template.npi_gate_template",
        (
            "npi_core.npi_core.doctype.npi_gate_template_version"
            ".npi_gate_template_version"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.flags = types.SimpleNamespace()
        self.version_rows: dict[str, AttrDict] = {}

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        frappe.throw = throw

        def get_value(
            doctype: str,
            name: object,
            fields: list[str],
            *,
            as_dict: bool,
        ) -> AttrDict | None:
            self.assertTrue(as_dict)
            if doctype == "NPI Gate Template":
                self.assertEqual(name, str(GATE_TEMPLATE_ID))
                self.assertEqual(fields, ["global_id", "template_code"])
                return AttrDict(
                    global_id=str(GATE_TEMPLATE_ID),
                    template_code="SYNTHETIC-G0",
                )
            self.assertEqual(doctype, "NPI Gate Template Version")
            if isinstance(name, dict):
                self.assertEqual(
                    name,
                    {"gate_template_global_id": str(GATE_TEMPLATE_ID)},
                )
                self.assertEqual(fields, ["name"])
                if not self.version_rows:
                    return None
                return AttrDict(name=next(iter(self.version_rows)))
            self.assertEqual(fields, ["publication_state"])
            return self.version_rows.get(str(name))

        frappe.db = types.SimpleNamespace(get_value=get_value)
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: datetime(2026, 7, 23, 16, 0, 0)
        frappe.model = model
        frappe.utils = utils

        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document
        sys.modules["frappe.utils"] = utils

        root_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_template.npi_gate_template"
        )
        version_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_template_version"
            ".npi_gate_template_version"
        )
        self.RootController = root_module.NPIGateTemplate
        self.VersionController = version_module.NPIGateTemplateVersion

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def version_document(
        self,
        *,
        publication_state: str = "published",
        gate_template_version: int = 1,
        global_id: object = None,
        requirements: list[AttrDict] | None = None,
        applicable_project_types: object = '["new_tool"]',
    ) -> StubDocument:
        document = self.VersionController(
            {
                "global_id": global_id,
                "gate_template": str(GATE_TEMPLATE_ID),
                "gate_template_global_id": None,
                "gate_template_code": None,
                "gate_template_version": gate_template_version,
                "version_key": None,
                "optimistic_version": 1,
                "title": "  Synthetic feasibility Gate  ",
                "publication_state": publication_state,
                "applicable_project_types": applicable_project_types,
                "requirements": (
                    requirements
                    if requirements is not None
                    else [
                        AttrDict(
                            requirement_key="  technical_input  ",
                            title="  Technical input  ",
                            classification="required",
                            priority="P0",
                            allowed_evidence_kinds=json.dumps(
                                ["wbs_item", "file_revision"]
                            ),
                        )
                    ]
                ),
                "snapshot_hash": None,
                "published_at": None,
            }
        )
        document.before_validate()
        return document

    def test_root_and_published_version_normalize_exact_identity_and_snapshot(
        self,
    ) -> None:
        root = self.RootController(
            {
                "global_id": str(GATE_TEMPLATE_ID),
                "template_code": "  SYNTHETIC-G0  ",
                "title": "Synthetic G0",
                "enabled": 1,
            }
        )
        root.validate()
        self.assertEqual(root.template_code, "SYNTHETIC-G0")

        version = self.version_document()
        version.validate()
        self.assertEqual(
            version.version_key,
            f"{GATE_TEMPLATE_ID}:1",
        )
        expected_version_global_id = str(
            __import__("uuid").uuid5(
                GATE_TEMPLATE_ID,
                "gate-template-version:1",
            )
        )
        self.assertEqual(version.global_id, expected_version_global_id)
        self.assertEqual(version.title, "Synthetic feasibility Gate")
        self.assertEqual(version.requirements[0].requirement_key, "technical_input")
        self.assertEqual(
            version.requirements[0].allowed_evidence_kinds,
            '["file_revision","wbs_item"]',
        )
        self.assertEqual(len(version.snapshot_hash), 64)
        self.assertEqual(
            version.published_at,
            datetime(2026, 7, 23, 16, 0, 0),
        )
        with self.assertRaises(self.ValidationError):
            self.version_document(
                global_id="00000000-0000-4000-8000-000000000001",
            )

    def test_published_version_is_immutable_and_draft_timestamp_is_empty(self) -> None:
        published = self.version_document()
        published._previous = AttrDict(publication_state="published")
        with self.assertRaises(self.ValidationError):
            published.validate()

        draft = self.version_document(publication_state="draft")
        draft.published_at = datetime(2000, 1, 1)
        draft.validate()
        self.assertIsNone(draft.published_at)

    def test_new_versions_are_contiguous_and_follow_a_published_version(
        self,
    ) -> None:
        with self.assertRaises(self.ValidationError):
            self.version_document(gate_template_version=2).validate()

        first_key = f"{GATE_TEMPLATE_ID}:1"
        self.version_rows[first_key] = AttrDict(publication_state="draft")
        with self.assertRaises(self.ValidationError):
            self.version_document(gate_template_version=2).validate()

        self.version_rows[first_key].publication_state = "published"
        second = self.version_document(
            publication_state="draft",
            gate_template_version=2,
        )
        second.validate()
        self.assertEqual(second.version_key, f"{GATE_TEMPLATE_ID}:2")

        with self.assertRaises(self.ValidationError):
            self.version_document(gate_template_version=1).validate()

    def test_invalid_requirement_and_project_type_shapes_fail_closed(self) -> None:
        invalid = (
            self.version_document(requirements=[]),
            self.version_document(applicable_project_types="[]"),
            self.version_document(applicable_project_types='["unsupported"]'),
            self.version_document(
                requirements=[
                    AttrDict(
                        requirement_key="input",
                        title="Input",
                        classification="required",
                        priority="P0",
                        allowed_evidence_kinds="[]",
                    )
                ]
            ),
            self.version_document(
                requirements=[
                    AttrDict(
                        requirement_key="input",
                        title="Input",
                        classification="mandatory",
                        priority="P0",
                        allowed_evidence_kinds='["wbs_item"]',
                    )
                ]
            ),
            self.version_document(
                requirements=[
                    AttrDict(
                        requirement_key="input",
                        title="Input",
                        classification="required",
                        priority="P0",
                        allowed_evidence_kinds='["unsupported"]',
                    )
                ]
            ),
            self.version_document(
                requirements=[
                    AttrDict(
                        requirement_key=f"requirement_{index}",
                        title=f"Requirement {index}",
                        classification="required",
                        priority="P0",
                        allowed_evidence_kinds='["wbs_item"]',
                    )
                    for index in range(501)
                ]
            ),
            self.version_document(
                requirements=[
                    AttrDict(
                        requirement_key="document",
                        title="Document",
                        classification="required",
                        priority="P0",
                        allowed_evidence_kinds='["document_revision"]',
                    )
                ]
            ),
        )
        for index, document in enumerate(invalid):
            with self.subTest(index=index):
                with self.assertRaises(self.ValidationError):
                    document.validate()


class GateTemplateMetadataTest(unittest.TestCase):
    def load(self, folder: str) -> dict[str, Any]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_gate_template_metadata_is_additive_versioned_and_admin_only(
        self,
    ) -> None:
        root = self.load("npi_gate_template")
        version = self.load("npi_gate_template_version")
        requirement = self.load("npi_gate_requirement_definition")
        root_fields = {value["fieldname"]: value for value in root["fields"]}
        version_fields = {value["fieldname"]: value for value in version["fields"]}
        requirement_fields = {
            value["fieldname"]: value for value in requirement["fields"]
        }

        self.assertEqual(root["autoname"], "field:global_id")
        self.assertEqual(root_fields["global_id"]["unique"], 1)
        self.assertEqual(root_fields["template_code"]["unique"], 1)
        self.assertEqual(version["autoname"], "field:version_key")
        self.assertEqual(version_fields["global_id"]["unique"], 1)
        self.assertEqual(version_fields["version_key"]["unique"], 1)
        self.assertEqual(
            version_fields["requirements"]["options"],
            ("NPI Gate Requirement Definition"),
        )
        self.assertEqual(version_fields["snapshot_hash"]["read_only"], 1)
        self.assertTrue(requirement["istable"])
        self.assertEqual(
            requirement_fields["classification"]["options"],
            "required\noptional",
        )
        self.assertEqual(
            {value["role"] for value in root["permissions"]},
            {"System Manager"},
        )
        self.assertEqual(
            {value["role"] for value in version["permissions"]},
            {"System Manager"},
        )

    def test_requirement_child_and_published_history_have_controller_guards(
        self,
    ) -> None:
        child_source = (
            DOCTYPE_ROOT
            / "npi_gate_requirement_definition"
            / "npi_gate_requirement_definition.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(child_source.count("deny_standalone_child_write()"), 3)

        version_source = (
            DOCTYPE_ROOT / "npi_gate_template_version" / "npi_gate_template_version.py"
        ).read_text(encoding="utf-8")
        self.assertIn('previous.publication_state == "published"', version_source)
        self.assertIn("deny_controlled_history_delete()", version_source)


if __name__ == "__main__":
    unittest.main()
