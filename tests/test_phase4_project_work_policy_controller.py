from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import datetime
from typing import Any
from unittest import mock
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

POLICY_ID = UUID("a4d469a9-bc68-4581-8c64-325fbcbcf716")


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> Any:
        return self._previous


class ProjectWorkPolicyControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "npi_core.project.frappe_validation",
        (
            "npi_core.npi_core.doctype.npi_project_work_policy_version"
            ".npi_project_work_policy_version"
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
        frappe.get_app_path = lambda *_parts: (
            "apps/npi_core/npi_core/translations"
        )

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        frappe.throw = throw

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

        self.module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_project_work_policy_version"
            ".npi_project_work_policy_version"
        )
        self.Controller = self.module.NPIProjectWorkPolicyVersion

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def policy_document(self) -> StubDocument:
        lifecycle = {
            "initialStateKey": "draft",
            "states": [
                {
                    "key": "draft",
                    "labelSource": "Draft",
                    "terminal": False,
                }
            ],
        }
        work_item_lifecycles = [
            {
                "kind": kind,
                **lifecycle,
            }
            for kind in ("risk", "issue", "action", "decision_request")
        ]
        return self.Controller(
            {
                "global_id": None,
                "policy_global_id": str(POLICY_ID),
                "policy_key": "synthetic_policy",
                "policy_version": 1,
                "version_key": None,
                "optimistic_version": 1,
                "title": "Synthetic Project Work Policy",
                "publication_state": "published",
                "role_keys": json.dumps(["project_manager"]),
                "wbs_states": json.dumps(lifecycle),
                "work_item_lifecycles": json.dumps(work_item_lifecycles),
                "snapshot_hash": None,
                "published_at": None,
            }
        )

    def test_publication_accepts_registered_draft_with_both_chinese_catalogs(
        self,
    ) -> None:
        with mock.patch.object(
            self.module,
            "load_runtime_catalog",
            wraps=self.module.load_runtime_catalog,
        ) as load_catalog:
            document = self.policy_document()
            document.validate()

        loaded_languages = [
            call.args[0].stem for call in load_catalog.call_args_list
        ]
        self.assertEqual(loaded_languages, ["zh", "zh-TW"])
        self.assertEqual(document.publication_state, "published")
        self.assertIsNotNone(document.published_at)

    def test_publication_requires_each_registered_label_in_each_chinese_catalog(
        self,
    ) -> None:
        for missing_language in ("zh", "zh-TW"):
            with self.subTest(missing_language=missing_language):
                catalogs = {
                    language: {
                        source: object()
                        for source in self.module.POLICY_LABEL_SOURCES
                    }
                    for language in ("zh", "zh-TW")
                }
                catalogs[missing_language].pop("Draft")

                def load_catalog(path):
                    return catalogs[path.stem]

                with mock.patch.object(
                    self.module,
                    "load_runtime_catalog",
                    side_effect=load_catalog,
                ):
                    with self.assertRaises(self.ValidationError):
                        self.policy_document().validate()


if __name__ == "__main__":
    unittest.main()
