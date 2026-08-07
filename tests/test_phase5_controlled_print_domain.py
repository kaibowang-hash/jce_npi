from __future__ import annotations

import hashlib
import math
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (
    ControlledPrintAccessEvent,
    ControlledPrintContext,
    ControlledPrintMappingAmbiguous,
    ControlledPrintMappingUnavailable,
    ControlledPrintOutput,
    ControlledPrintRegistryReference,
    ControlledPrintRegistryVersion,
    ControlledPrintSnapshot,
    ControlledPrintSourceReference,
    PrintAccessEventType,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    controlled_print_command_payload_hash,
    controlled_print_receipt_key,
    resolve_controlled_print_mapping,
    sha256_json,
)
from npi_core.foundation.errors import RequestValidationFailed


NOW = datetime(2026, 8, 7, 1, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


class Phase5ControlledPrintDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = UUID("822ce4ac-0a90-5c0e-8c30-d791dc56e3a9")
        self.registry_id = UUID("00000000-0000-4000-8000-000000000602")
        self.mapping_id = UUID("00000000-0000-4000-8000-000000000603")
        self.source_id = UUID("00000000-0000-4000-8000-000000000604")
        self.snapshot_id = UUID("00000000-0000-4000-8000-000000000605")
        self.output_id = UUID("00000000-0000-4000-8000-000000000606")
        self.request_id = UUID("9321128c-675d-5b41-b1e6-9d7519fc5d81")
        self.template = "<section>{{ doc.title }}</section>"
        self.source_snapshot = {
            "globalId": str(self.source_id),
            "title": "Synthetic controlled source",
            "version": 3,
        }

    def context(self, **changes: object) -> ControlledPrintContext:
        values: dict[str, object] = {
            "tenant_id": "synthetic-tenant",
            "project_global_id": self.project_id,
            "source_object_type": "synthetic_document_baseline",
            "project_type_key": "synthetic-project",
            "gate_key": "G3",
            "source_state": "released",
            "language": "en",
        }
        values.update(changes)
        return ControlledPrintContext(**values)  # type: ignore[arg-type]

    def mapping(self, **changes: object) -> ControlledPrintRegistryVersion:
        values: dict[str, object] = {
            "global_id": self.mapping_id,
            "registry_global_id": self.registry_id,
            "tenant_id": "synthetic-tenant",
            "mapping_key": "synthetic-controlled-output",
            "mapping_version": 1,
            "title": "Synthetic controlled output",
            "state": PrintRegistryState.PUBLISHED,
            "source_object_type": "synthetic_document_baseline",
            "project_type_key": "synthetic-project",
            "gate_key": "G3",
            "source_state": "released",
            "language": "en",
            "delivery_mode": PrintDeliveryMode.CONTROLLED_PDF,
            "copy_state": PrintCopyState.NOT_NUMBERED,
            "print_format_name": "NPI Synthetic Controlled Output",
            "template_content": self.template,
            "template_sha256": hashlib.sha256(self.template.encode()).hexdigest(),
            "watermark_source": "Controlled snapshot",
            "printer_user_ids": ("engineer@example.invalid",),
            "effective_from": NOW - timedelta(days=1),
            "published_at": NOW - timedelta(days=1),
        }
        values.update(changes)
        return ControlledPrintRegistryVersion(**values)  # type: ignore[arg-type]

    def snapshot(self, **changes: object) -> ControlledPrintSnapshot:
        source = ControlledPrintSourceReference(
            source_object_type="synthetic_document_baseline",
            source_global_id=self.source_id,
            source_version=3,
            source_state="released",
            source_snapshot_hash=sha256_json(self.source_snapshot),
        )
        values: dict[str, object] = {
            "global_id": self.snapshot_id,
            "tenant_id": "synthetic-tenant",
            "project_global_id": self.project_id,
            "project_type_key": "synthetic-project",
            "gate_key": "G3",
            "source": source,
            "registry": ControlledPrintRegistryReference.from_mapping(self.mapping()),
            "language": "en",
            "delivery_mode": PrintDeliveryMode.CONTROLLED_PDF,
            "copy_state": PrintCopyState.NOT_NUMBERED,
            "watermark_source": "Controlled snapshot",
            "source_snapshot": self.source_snapshot,
            "actor_user_id": "engineer@example.invalid",
            "printed_at": NOW,
            "request_id": self.request_id,
            "trace_id": "trace-p506-domain-001",
        }
        values.update(changes)
        return ControlledPrintSnapshot(**values)  # type: ignore[arg-type]

    def output(self, **changes: object) -> ControlledPrintOutput:
        values: dict[str, object] = {
            "global_id": self.output_id,
            "tenant_id": "synthetic-tenant",
            "project_global_id": self.project_id,
            "snapshot_global_id": self.snapshot_id,
            "frappe_file_id": "synthetic-private-file-id",
            "file_name": "synthetic-controlled-output.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 512,
            "frappe_content_hash": "c" * 32,
            "sha256": HASH_A,
            "created_by_user_id": "engineer@example.invalid",
            "created_at": NOW,
        }
        values.update(changes)
        return ControlledPrintOutput(**values)  # type: ignore[arg-type]

    def test_exact_published_mapping_resolves_and_hides_template_identity(self) -> None:
        mapping = resolve_controlled_print_mapping(
            (self.mapping(),),
            self.context(),
            at=NOW,
        )

        self.assertTrue(mapping.authorizes("engineer@example.invalid"))
        self.assertFalse(mapping.authorizes("other@example.invalid"))
        reference = mapping.public_reference()
        self.assertNotIn("printFormatName", reference)
        self.assertNotIn("templateContent", reference)
        self.assertEqual(reference["deliveryMode"], "controlled_pdf")
        self.assertEqual(reference["copyState"], "not_numbered")

    def test_missing_draft_expired_and_mismatched_mappings_fail_closed(self) -> None:
        candidates = (
            self.mapping(state=PrintRegistryState.DRAFT, published_at=None),
            self.mapping(
                global_id=uuid4(),
                effective_to=NOW - timedelta(seconds=1),
            ),
            self.mapping(global_id=uuid4(), language="zh"),
        )
        with self.assertRaises(ControlledPrintMappingUnavailable):
            resolve_controlled_print_mapping(candidates, self.context(), at=NOW)

    def test_ambiguous_exact_mapping_fails_closed(self) -> None:
        with self.assertRaises(ControlledPrintMappingAmbiguous):
            resolve_controlled_print_mapping(
                (self.mapping(), self.mapping(global_id=uuid4(), mapping_version=2)),
                self.context(),
                at=NOW,
            )

    def test_template_and_mapping_snapshot_hashes_detect_tampering(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.mapping(template_sha256=HASH_B)
        with self.assertRaises(RequestValidationFailed):
            self.mapping(snapshot_hash=HASH_B)
        draft = self.mapping(state=PrintRegistryState.DRAFT, published_at=None)
        with self.assertRaises(RequestValidationFailed):
            replace(draft, published_at=NOW)
        multiline = "<section>\n  {{ doc.title }}\n</section>"
        mapping = self.mapping(
            template_content=multiline,
            template_sha256=hashlib.sha256(multiline.encode()).hexdigest(),
        )
        self.assertEqual(mapping.template_content, multiline)

    def test_snapshot_freezes_source_and_derives_non_circular_verification(self) -> None:
        snapshot = self.snapshot()
        self.source_snapshot["title"] = "Changed live source"

        self.assertEqual(
            snapshot.snapshot_payload()["sourceSnapshot"]["title"],  # type: ignore[index]
            "Synthetic controlled source",
        )
        self.assertEqual(snapshot.snapshot_hash, sha256_json(snapshot.snapshot_payload()))
        self.assertEqual(
            snapshot.verification_payload,
            f"urn:npi:controlled-print:{self.snapshot_id}:{snapshot.snapshot_hash}",
        )
        public = snapshot.public_dict(output=self.output())
        self.assertIn("sourceKind", public["source"])  # type: ignore[operator]
        self.assertNotIn("sourceObjectType", public["source"])  # type: ignore[operator]
        self.assertIn("globalId", public["registry"])  # type: ignore[operator]
        self.assertNotIn("mappingGlobalId", public["registry"])  # type: ignore[operator]
        self.assertNotIn("sourceSnapshot", public)
        self.assertNotIn("frappeFileId", str(public))
        self.assertNotIn("/private/files", str(public))

    def test_snapshot_rejects_source_hash_and_verification_tampering(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.snapshot(
                source=ControlledPrintSourceReference(
                    "synthetic_document_baseline",
                    self.source_id,
                    3,
                    "released",
                    HASH_B,
                )
            )
        with self.assertRaises(RequestValidationFailed):
            self.snapshot(verification_payload="https://example.invalid/verify")
        with self.assertRaises(RequestValidationFailed):
            self.snapshot(snapshot_hash=HASH_B)

    def test_output_is_pdf_only_and_has_independent_record_hash(self) -> None:
        output = self.output()
        self.assertEqual(output.record_hash, sha256_json(output.record_payload()))
        self.assertEqual(
            set(output.public_dict()),
            {"globalId", "fileName", "mimeType", "sizeBytes", "sha256", "recordHash"},
        )
        for changes in (
            {"mime_type": "text/html"},
            {"file_name": "../output.pdf"},
            {"file_name": "output.txt"},
            {"frappe_content_hash": "z" * 32},
            {"record_hash": HASH_B},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                RequestValidationFailed
            ):
                self.output(**changes)

    def test_access_event_is_append_only_hashable_truth(self) -> None:
        event = ControlledPrintAccessEvent(
            global_id=uuid4(),
            tenant_id="synthetic-tenant",
            project_global_id=self.project_id,
            snapshot_global_id=self.snapshot_id,
            output_global_id=self.output_id,
            event_type=PrintAccessEventType.DOWNLOADED,
            actor_user_id="engineer@example.invalid",
            occurred_at=NOW,
            trace_id="trace-p506-download-001",
        )
        self.assertEqual(event.event_hash, sha256_json(event.event_payload()))
        with self.assertRaises(RequestValidationFailed):
            replace(event, actor_user_id="invalid user", event_hash="")

    def test_command_and_receipt_hashes_bind_actor_project_and_exact_payload(self) -> None:
        payload = controlled_print_command_payload_hash(
            actor_user_id="engineer@example.invalid",
            tenant_id="synthetic-tenant",
            project_global_id=self.project_id,
            source_object_type="synthetic_document_baseline",
            source_global_id=self.source_id,
            source_version=3,
            language="en",
        )
        changed = controlled_print_command_payload_hash(
            actor_user_id="engineer@example.invalid",
            tenant_id="synthetic-tenant",
            project_global_id=self.project_id,
            source_object_type="synthetic_document_baseline",
            source_global_id=self.source_id,
            source_version=4,
            language="en",
        )
        self.assertNotEqual(payload, changed)
        self.assertRegex(payload, r"^[a-f0-9]{64}$")

        first = controlled_print_receipt_key(
            actor_user_id="engineer@example.invalid",
            tenant_id="synthetic-tenant",
            project_global_id=self.project_id,
            idempotency_key_hash=HASH_A,
        )
        second = controlled_print_receipt_key(
            actor_user_id="other@example.invalid",
            tenant_id="synthetic-tenant",
            project_global_id=self.project_id,
            idempotency_key_hash=HASH_A,
        )
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^[a-f0-9]{64}$")

    def test_context_rejects_unknown_language_delivery_and_copy_semantics(self) -> None:
        with self.assertRaises(RequestValidationFailed) as captured:
            self.context(language="fr")
        self.assertEqual(
            captured.exception.field_errors,
            [{"path": "language", "message": "Select a supported language."}],
        )
        with self.assertRaises(ValueError):
            PrintDeliveryMode("browser_print")
        with self.assertRaises(ValueError):
            PrintCopyState("copy_1")
        with self.assertRaises(RequestValidationFailed):
            ControlledPrintSourceReference(
                "synthetic_document_baseline",
                self.source_id,
                1.0,  # type: ignore[arg-type]
                "released",
                HASH_A,
            )
        with self.assertRaises(RequestValidationFailed):
            sha256_json({"invalid": math.nan})


if __name__ == "__main__":
    unittest.main()
