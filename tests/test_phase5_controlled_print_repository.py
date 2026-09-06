from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (  # noqa: E402
    ControlledPrintContext,
    ControlledPrintRegistryVersion,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
)


PROJECT_ID = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
REGISTRY_ID = UUID("29e933a3-3954-4a96-9400-2be1987ae370")
MAPPING_ID = UUID("89953948-4178-46dc-b7ca-8b94f2ac4e36")
NOW = datetime(2026, 8, 7, 1, 0, tzinfo=UTC)


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


class Phase5ControlledPrintRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.documents.frappe_repository",
        "npi_core.controlled_print.frappe_validation",
        "npi_core.controlled_print.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.frappe = types.ModuleType("frappe")
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.documents: dict[tuple[str, str], object] = {}
        self.query_names: list[str] = []
        self.query: dict[str, object] | None = None

        def get_all(doctype: str, **values: Any):
            self.assertEqual(doctype, "NPI Controlled Print Registry Version")
            self.query = values
            return list(self.query_names)

        def get_doc(doctype: str, name: str):
            try:
                return self.documents[(doctype, name)]
            except KeyError as error:
                raise self.frappe.DoesNotExistError() from error

        self.frappe.get_all = get_all
        self.frappe.get_doc = get_doc
        sys.modules["frappe"] = self.frappe

        base = types.ModuleType("npi_core.documents.frappe_repository")

        class FrappeDocumentRepository:
            def __init__(self, **_values: object) -> None:
                self.project = None

            def _authorized_project(self, _project_id: UUID):
                return self.project

        base.FrappeDocumentRepository = FrappeDocumentRepository
        sys.modules["npi_core.documents.frappe_repository"] = base
        validation = types.ModuleType(
            "npi_core.controlled_print.frappe_validation"
        )

        @contextmanager
        def controlled_print_command_write():
            yield

        validation.controlled_print_command_write = controlled_print_command_write
        sys.modules["npi_core.controlled_print.frappe_validation"] = validation
        self.module = importlib.import_module(
            "npi_core.controlled_print.frappe_repository"
        )
        self.repository = self.module.FrappeControlledPrintRepository()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def context(*, gate_key: str | None = None) -> ControlledPrintContext:
        return ControlledPrintContext(
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            source_object_type="synthetic_print_source",
            project_type_key="new_tool",
            gate_key=gate_key,
            source_state="released",
            language="en",
            delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
            copy_state=PrintCopyState.NOT_NUMBERED,
        )

    @staticmethod
    def mapping(*, gate_key: str | None = None) -> ControlledPrintRegistryVersion:
        template = "<h1>{{ doc.title }}</h1>"
        return ControlledPrintRegistryVersion(
            global_id=MAPPING_ID,
            registry_global_id=REGISTRY_ID,
            tenant_id="TENANT-A",
            mapping_key="synthetic.release.en",
            mapping_version=1,
            title="Synthetic released source",
            state=PrintRegistryState.PUBLISHED,
            source_object_type="synthetic_print_source",
            project_type_key="new_tool",
            gate_key=gate_key,
            source_state="released",
            language="en",
            delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
            copy_state=PrintCopyState.NOT_NUMBERED,
            print_format_name="Synthetic Controlled Print",
            template_content=template,
            template_sha256=__import__("hashlib").sha256(template.encode()).hexdigest(),
            watermark_source="CONTROLLED",
            printer_user_ids=("printer@example.invalid",),
            effective_from=NOW,
            published_at=NOW,
        )

    def install_mapping(self, *, enabled: int = 1, gate_key: str | None = None):
        mapping = self.mapping(gate_key=gate_key)
        self.query_names = [str(MAPPING_ID)]
        self.documents[("NPI Controlled Print Registry Version", str(MAPPING_ID))] = (
            AttrDict(
                global_id=str(mapping.global_id),
                print_registry=str(mapping.registry_global_id),
                registry_global_id=str(mapping.registry_global_id),
                tenant_id=mapping.tenant_id,
                mapping_key=mapping.mapping_key,
                mapping_version=mapping.mapping_version,
                title=mapping.title,
                publication_state=mapping.state.value,
                source_object_type=mapping.source_object_type,
                project_type_key=mapping.project_type_key,
                gate_key=mapping.gate_key,
                source_state=mapping.source_state,
                language=mapping.language,
                delivery_mode=mapping.delivery_mode.value,
                copy_state=mapping.copy_state.value,
                print_format_name=mapping.print_format_name,
                template_content=mapping.template_content,
                template_sha256=mapping.template_sha256,
                watermark_source=mapping.watermark_source,
                printer_user_ids=json.dumps(list(mapping.printer_user_ids)),
                effective_from="2026-08-07 01:00:00",
                effective_to=None,
                published_at="2026-08-07T01:00:00Z",
                mapping_snapshot=json.dumps(mapping.snapshot_payload()),
                snapshot_hash=mapping.snapshot_hash,
            )
        )
        self.documents[("NPI Controlled Print Registry", str(REGISTRY_ID))] = AttrDict(
            global_id=str(REGISTRY_ID),
            tenant_id="TENANT-A",
            enabled=enabled,
        )
        return mapping

    def test_project_authorization_returns_only_opaque_exact_context(self) -> None:
        self.assertIsNone(self.repository.authorize_project(PROJECT_ID))
        self.repository.project = AttrDict(
            global_id=str(PROJECT_ID),
            tenant_id="TENANT-A",
            project_type="new_tool",
        )
        result = self.repository.authorize_project(PROJECT_ID)
        self.assertEqual(result.global_id, PROJECT_ID)
        self.assertEqual(result.tenant_id, "TENANT-A")
        self.assertEqual(result.project_type_key, "new_tool")

    def test_query_is_exact_bounded_and_rehydrates_frozen_snapshot(self) -> None:
        expected = self.install_mapping()
        result = self.repository.published_mapping_candidates(
            self.context(),
            at=NOW,
        )
        self.assertEqual(result, (expected,))
        self.assertEqual(
            self.query["limit_page_length"],
            self.module._MAX_MAPPING_CANDIDATES + 1,
        )
        filters = self.query["filters"]
        self.assertEqual(filters["tenant_id"], "TENANT-A")
        self.assertEqual(filters["publication_state"], "published")
        self.assertEqual(filters["source_object_type"], "synthetic_print_source")
        self.assertEqual(filters["language"], "en")

    def test_gate_mismatch_is_not_a_candidate(self) -> None:
        self.install_mapping(gate_key="G2")
        result = self.repository.published_mapping_candidates(
            self.context(gate_key="G3"),
            at=NOW,
        )
        self.assertEqual(result, ())

    def test_disabled_or_mismatched_registry_fails_closed(self) -> None:
        self.install_mapping(enabled=0)
        with self.assertRaisesRegex(RuntimeError, "registry is unavailable"):
            self.repository.published_mapping_candidates(self.context(), at=NOW)

    def test_snapshot_tampering_and_unbounded_rows_fail_closed(self) -> None:
        self.install_mapping()
        document = self.documents[
            ("NPI Controlled Print Registry Version", str(MAPPING_ID))
        ]
        document["mapping_snapshot"] = "{}"
        with self.assertRaisesRegex(RuntimeError, "snapshot does not match"):
            self.repository.published_mapping_candidates(self.context(), at=NOW)

        self.query_names = [
            str(MAPPING_ID)
            for _ in range(self.module._MAX_MAPPING_CANDIDATES + 1)
        ]
        with self.assertRaisesRegex(RuntimeError, "exceed their safe bound"):
            self.repository.published_mapping_candidates(self.context(), at=NOW)


if __name__ == "__main__":
    unittest.main()
