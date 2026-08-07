from __future__ import annotations

import hashlib
import importlib
import json
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (  # noqa: E402
    ControlledPrintIdempotencyConflict,
    ControlledPrintRegistryVersion,
    ControlledPrintSourceReference,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    sha256_json,
)
from npi_core.controlled_print.source_registry import (  # noqa: E402
    ControlledPrintSourceRegistry,
    ResolvedControlledPrintSource,
)


PROJECT_ID = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
SOURCE_ID = UUID("0878087f-6192-4e40-862d-05e0a5927638")
REGISTRY_ID = UUID("29e933a3-3954-4a96-9400-2be1987ae370")
MAPPING_ID = UUID("89953948-4178-46dc-b7ca-8b94f2ac4e36")
REQUEST_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"
NOW = datetime(2026, 8, 7, 1, 0, tzinfo=UTC)
KEY_HASH = "9" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class CallbackList:
    def __init__(self) -> None:
        self.values: list[object] = []

    def add(self, value: object) -> None:
        self.values.append(value)


class FakeDocument(AttrDict):
    def __init__(self, owner: "Phase5ControlledPrintTransactionTest", values):
        super().__init__(values)
        self.owner = owner

    def insert(self):
        identity = str(self.get("global_id") or self.get("event_id"))
        self.name = identity
        self.owner.documents[(str(self.doctype), identity)] = self
        self.owner.writes.append(("insert", str(self.doctype)))
        return self

    def save(self):
        self.owner.writes.append(("save", str(self.doctype)))
        return self


class FakeFile(FakeDocument):
    def __init__(self, owner, values, content: bytes):
        super().__init__(owner, values)
        self._content = content

    def get_content(self):
        return self._content


class FakeDatabase:
    def __init__(self, owner: "Phase5ControlledPrintTransactionTest") -> None:
        self.owner = owner
        self.after_rollback = CallbackList()

    def get_value(
        self,
        doctype: str,
        filters: object,
        fields: object,
        **_values: object,
    ):
        documents = [
            document
            for (candidate, _name), document in self.owner.documents.items()
            if candidate == doctype and self._matches(document, filters)
        ]
        if not documents:
            return None
        if len(documents) != 1:
            raise AssertionError((doctype, filters, len(documents)))
        document = documents[0]
        if isinstance(fields, list):
            return AttrDict({field: document.get(field) for field in fields})
        return document.get(str(fields))

    @staticmethod
    def _matches(document: AttrDict, filters: object) -> bool:
        if not isinstance(filters, dict):
            return str(document.name) == str(filters)
        return all(str(document.get(key)) == str(value) for key, value in filters.items())


class FakeAdapter:
    source_object_type = "synthetic_print_source"

    def __init__(self) -> None:
        self.resolutions = 0

    def resolve_exact(self, *, project_global_id: UUID, source_global_id: UUID):
        self.resolutions += 1
        snapshot = {"title": "Frozen source", "version": 3}
        return ResolvedControlledPrintSource(
            project_global_id=project_global_id,
            project_type_key="new_tool",
            gate_key=None,
            reference=ControlledPrintSourceReference(
                source_object_type=self.source_object_type,
                source_global_id=source_global_id,
                source_version=3,
                source_state="released",
                source_snapshot_hash=sha256_json(snapshot),
            ),
            snapshot=snapshot,
        )


class Phase5ControlledPrintTransactionTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.utils",
        "frappe.utils.file_manager",
        "npi_core.documents.frappe_repository",
        "npi_core.controlled_print.frappe_validation",
        "npi_core.controlled_print.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[tuple[str, str], FakeDocument] = {}
        self.writes: list[tuple[str, str]] = []
        self.adapter = FakeAdapter()
        self.render_count = 0
        self.current_time = NOW
        self.uuid_values = iter(
            UUID(value)
            for value in (
                "10000000-0000-4000-8000-000000000001",
                "10000000-0000-4000-8000-000000000002",
                "10000000-0000-4000-8000-000000000003",
                "10000000-0000-4000-8000-000000000004",
                "10000000-0000-4000-8000-000000000005",
                "10000000-0000-4000-8000-000000000006",
            )
        )
        self.frappe = types.ModuleType("frappe")
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.db = FakeDatabase(self)
        self.frappe.get_site_path = lambda *_parts: "/private/tmp/npi-print-test"
        self.frappe.get_all = self.get_all
        self.frappe.get_doc = self.get_doc
        sys.modules["frappe"] = self.frappe

        utils = types.ModuleType("frappe.utils")
        file_manager = types.ModuleType("frappe.utils.file_manager")
        file_manager.save_file = self.save_file
        sys.modules["frappe.utils"] = utils
        sys.modules["frappe.utils.file_manager"] = file_manager

        base = types.ModuleType("npi_core.documents.frappe_repository")

        class FrappeDocumentRepository:
            def __init__(repository, **values: object) -> None:
                principal = values["principal"]
                repository.principal = principal
                repository.actor = principal.user_id
                repository.request_id = str(values["request_id"])
                repository.trace_id = str(values["trace_id"])

            def _authorized_project(repository, project_id: UUID):
                project = self.documents.get(
                    ("NPI Engineering Project", str(project_id))
                )
                return (
                    project
                    if project is not None
                    and repository._can_view_project(project, project_id)
                    else None
                )

            def _can_view_project(repository, project, project_id: UUID) -> bool:
                return bool(
                    str(project.global_id) == str(project_id)
                    and str(project.tenant_id) == repository.principal.tenant_id
                    and not repository.principal.is_external
                )

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
        self.install_fixtures()
        principal = types.SimpleNamespace(
            user_id="printer@example.invalid",
            tenant_id="TENANT-A",
            is_external=False,
        )
        self.repository = self.module.FrappeControlledPrintRepository(
            principal=principal,
            request_id=REQUEST_ID,
            trace_id="trace-controlled-print-transaction",
            source_registry=ControlledPrintSourceRegistry((self.adapter,)),
            render_template=lambda template, context: template.replace(
                "{{ doc.title }}", str(context["doc"]["title"])
            ),
            convert_pdf=self.convert_pdf,
            translate=lambda source, _language: source,
            clock=lambda: self.current_time,
            uuid_factory=lambda: next(self.uuid_values),
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def install_fixtures(self) -> None:
        project = FakeDocument(
            self,
            {
                "doctype": "NPI Engineering Project",
                "global_id": str(PROJECT_ID),
                "tenant_id": "TENANT-A",
                "project_type": "new_tool",
            },
        )
        project.name = str(PROJECT_ID)
        self.documents[(project.doctype, project.name)] = project
        root = FakeDocument(
            self,
            {
                "doctype": "NPI Controlled Print Registry",
                "global_id": str(REGISTRY_ID),
                "tenant_id": "TENANT-A",
                "enabled": 1,
            },
        )
        root.name = str(REGISTRY_ID)
        self.documents[(root.doctype, root.name)] = root
        template = "<h1>{{ doc.title }}</h1>"
        mapping = ControlledPrintRegistryVersion(
            global_id=MAPPING_ID,
            registry_global_id=REGISTRY_ID,
            tenant_id="TENANT-A",
            mapping_key="synthetic.release.en",
            mapping_version=1,
            title="Synthetic released source",
            state=PrintRegistryState.PUBLISHED,
            source_object_type=self.adapter.source_object_type,
            project_type_key="new_tool",
            gate_key=None,
            source_state="released",
            language="en",
            delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
            copy_state=PrintCopyState.NOT_NUMBERED,
            print_format_name="Synthetic Controlled Print",
            template_content=template,
            template_sha256=hashlib.sha256(template.encode()).hexdigest(),
            watermark_source="CONTROLLED",
            printer_user_ids=("printer@example.invalid",),
            effective_from=NOW,
            published_at=NOW,
        )
        document = FakeDocument(
            self,
            {
                "doctype": "NPI Controlled Print Registry Version",
                "global_id": str(mapping.global_id),
                "print_registry": str(mapping.registry_global_id),
                "registry_global_id": str(mapping.registry_global_id),
                "tenant_id": mapping.tenant_id,
                "mapping_key": mapping.mapping_key,
                "mapping_version": mapping.mapping_version,
                "title": mapping.title,
                "publication_state": mapping.state.value,
                "source_object_type": mapping.source_object_type,
                "project_type_key": mapping.project_type_key,
                "gate_key": mapping.gate_key,
                "source_state": mapping.source_state,
                "language": mapping.language,
                "delivery_mode": mapping.delivery_mode.value,
                "copy_state": mapping.copy_state.value,
                "print_format_name": mapping.print_format_name,
                "template_content": mapping.template_content,
                "template_sha256": mapping.template_sha256,
                "watermark_source": mapping.watermark_source,
                "printer_user_ids": json.dumps(list(mapping.printer_user_ids)),
                "effective_from": "2026-08-07 01:00:00",
                "effective_to": None,
                "published_at": "2026-08-07T01:00:00Z",
                "mapping_snapshot": json.dumps(mapping.snapshot_payload()),
                "snapshot_hash": mapping.snapshot_hash,
            },
        )
        document.name = str(MAPPING_ID)
        self.documents[(document.doctype, document.name)] = document

    def get_all(self, doctype: str, **_values: object):
        return [
            name
            for (candidate, name) in self.documents
            if candidate == doctype
        ]

    def get_doc(self, doctype: object, name: object = None, **_values: object):
        if isinstance(doctype, dict):
            return FakeDocument(self, doctype)
        try:
            return self.documents[(str(doctype), str(name))]
        except KeyError as error:
            raise self.frappe.DoesNotExistError() from error

    def save_file(
        self,
        file_name: str,
        content: bytes,
        attached_to_doctype: str,
        attached_to_name: str,
        *,
        is_private: int,
    ):
        document = FakeFile(
            self,
            {
                "doctype": "File",
                "name": "controlled-print-file-1",
                "file_name": file_name,
                "file_size": len(content),
                "content_hash": hashlib.md5(
                    content,
                    usedforsecurity=False,
                ).hexdigest(),
                "file_url": f"/private/files/{file_name}",
                "is_private": is_private,
                "is_remote_file": 0,
                "attached_to_doctype": attached_to_doctype,
                "attached_to_name": attached_to_name,
            },
            content,
        )
        self.documents[("File", document.name)] = document
        self.writes.append(("insert", "File"))
        return document

    def convert_pdf(self, _html: str) -> bytes:
        self.render_count += 1
        return b"%PDF-1.7\nretained controlled print\n"

    def create(self, *, source_version: int = 3):
        return self.repository.create_snapshot(
            PROJECT_ID,
            source_object_type=self.adapter.source_object_type,
            source_global_id=SOURCE_ID,
            expected_source_version=source_version,
            language="en",
            idempotency_key_hash=KEY_HASH,
        )

    def test_create_persists_one_atomic_bundle_in_frozen_order(self) -> None:
        outcome = self.create()
        self.assertFalse(outcome.replayed)
        self.assertEqual(outcome.response["source"]["sourceVersion"], 3)
        self.assertEqual(outcome.response["output"]["mimeType"], "application/pdf")
        self.assertEqual(
            self.writes,
            [
                ("insert", "NPI Controlled Print Command Idempotency"),
                ("insert", "NPI Controlled Print Snapshot"),
                ("insert", "File"),
                ("insert", "NPI Controlled Print Output"),
                ("insert", "NPI Controlled Print Access Event"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Controlled Print Command Idempotency"),
            ],
        )
        self.assertEqual(self.adapter.resolutions, 1)
        self.assertEqual(self.render_count, 1)
        self.assertTrue(self.frappe.db.after_rollback.values)

    def test_replay_returns_sealed_response_without_source_or_render_reuse(self) -> None:
        first = self.create()
        write_count = len(self.writes)
        second = self.create()
        self.assertTrue(second.replayed)
        self.assertEqual(second.response, first.response)
        self.assertEqual(len(self.writes), write_count)
        self.assertEqual(self.adapter.resolutions, 1)
        self.assertEqual(self.render_count, 1)

        with self.assertRaises(ControlledPrintIdempotencyConflict):
            self.create(source_version=4)
        self.assertEqual(self.adapter.resolutions, 1)

    def test_detail_and_download_reuse_retained_bytes_without_rerendering(self) -> None:
        created = self.create()
        snapshot_id = UUID(created.response["globalId"])
        detail = self.repository.snapshot_detail(PROJECT_ID, snapshot_id)
        self.assertEqual(detail, created.response)
        self.current_time = NOW + timedelta(minutes=1)
        content = self.repository.content(PROJECT_ID, snapshot_id)
        self.assertEqual(content.content, b"%PDF-1.7\nretained controlled print\n")
        self.assertEqual(content.output_hash, created.response["output"]["sha256"])
        self.assertEqual(self.adapter.resolutions, 1)
        self.assertEqual(self.render_count, 1)
        self.assertEqual(
            self.writes[-2:],
            [
                ("insert", "NPI Controlled Print Access Event"),
                ("insert", "NPI Audit Event"),
            ],
        )

    def test_private_file_or_registry_drift_fails_closed(self) -> None:
        created = self.create()
        snapshot_id = UUID(created.response["globalId"])
        file_document = self.documents[("File", "controlled-print-file-1")]
        file_document._content = b"%PDF-1.7\ntampered\n"
        with self.assertRaisesRegex(RuntimeError, "integrity drifted"):
            self.repository.content(PROJECT_ID, snapshot_id)

        root = self.documents[("NPI Controlled Print Registry", str(REGISTRY_ID))]
        root.enabled = 0
        self.assertIsNone(self.repository.snapshot_detail(PROJECT_ID, snapshot_id))


if __name__ == "__main__":
    unittest.main()
