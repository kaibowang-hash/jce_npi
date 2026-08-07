from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (
    ControlledPrintAuthorityUnavailable,
    ControlledPrintMappingUnavailable,
    ControlledPrintRegistryReference,
    ControlledPrintRegistryVersion,
    ControlledPrintSnapshot,
    ControlledPrintSourceReference,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    sha256_json,
)
from npi_core.controlled_print.rendering import render_controlled_print_pdf


NOW = datetime(2026, 8, 7, 2, 0, tzinfo=UTC)
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000641")
REGISTRY_ID = UUID("00000000-0000-4000-8000-000000000642")
MAPPING_ID = UUID("00000000-0000-4000-8000-000000000643")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000644")
SNAPSHOT_ID = UUID("00000000-0000-4000-8000-000000000645")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000646")
ACTOR = "engineer@example.invalid"


def mapping(**changes: object) -> ControlledPrintRegistryVersion:
    template = str(changes.pop("template_content", "<h1>{{ doc.title }}</h1>"))
    values: dict[str, object] = {
        "global_id": MAPPING_ID,
        "registry_global_id": REGISTRY_ID,
        "tenant_id": "synthetic-tenant",
        "mapping_key": "synthetic-output",
        "mapping_version": 1,
        "title": "Synthetic output",
        "state": PrintRegistryState.PUBLISHED,
        "source_object_type": "synthetic_controlled_source",
        "project_type_key": "synthetic-project",
        "gate_key": "G3",
        "source_state": "released",
        "language": "en",
        "delivery_mode": PrintDeliveryMode.CONTROLLED_PDF,
        "copy_state": PrintCopyState.NOT_NUMBERED,
        "print_format_name": "NPI Synthetic Controlled Output",
        "template_content": template,
        "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
        "watermark_source": "Controlled snapshot",
        "printer_user_ids": (ACTOR,),
        "effective_from": NOW - timedelta(days=1),
        "published_at": NOW - timedelta(days=1),
    }
    values.update(changes)
    return ControlledPrintRegistryVersion(**values)  # type: ignore[arg-type]


def snapshot(
    selected: ControlledPrintRegistryVersion,
    **changes: object,
) -> ControlledPrintSnapshot:
    source_payload = {
        "globalId": str(SOURCE_ID),
        "title": "Frozen source title",
        "version": 7,
    }
    values: dict[str, object] = {
        "global_id": SNAPSHOT_ID,
        "tenant_id": "synthetic-tenant",
        "project_global_id": PROJECT_ID,
        "project_type_key": "synthetic-project",
        "gate_key": "G3",
        "source": ControlledPrintSourceReference(
            "synthetic_controlled_source",
            SOURCE_ID,
            7,
            "released",
            sha256_json(source_payload),
        ),
        "registry": ControlledPrintRegistryReference.from_mapping(selected),
        "language": "en",
        "delivery_mode": PrintDeliveryMode.CONTROLLED_PDF,
        "copy_state": PrintCopyState.NOT_NUMBERED,
        "watermark_source": "Controlled snapshot",
        "source_snapshot": source_payload,
        "actor_user_id": ACTOR,
        "printed_at": NOW,
        "request_id": REQUEST_ID,
        "trace_id": "trace-p506-render-001",
    }
    values.update(changes)
    return ControlledPrintSnapshot(**values)  # type: ignore[arg-type]


class Phase5ControlledPrintRenderingTest(unittest.TestCase):
    def test_render_uses_only_frozen_source_and_server_controlled_shell(self) -> None:
        selected = mapping()
        frozen = snapshot(selected)
        seen: dict[str, object] = {}

        def render(template: str, context: object) -> str:
            seen["template"] = template
            seen["context"] = context
            return "<h1>Frozen source title</h1>"

        def convert(document: str) -> bytes:
            seen["document"] = document
            return b"%PDF-1.4\nsynthetic retained bytes"

        output = render_controlled_print_pdf(
            snapshot=frozen,
            mapping=selected,
            render_template=render,
            convert_pdf=convert,
            translate=lambda source, _language: source,
        )

        self.assertEqual(seen["template"], selected.template_content)
        self.assertEqual(
            seen["context"]["doc"]["title"],  # type: ignore[index]
            "Frozen source title",
        )
        document = str(seen["document"])
        self.assertIn("Controlled snapshot", document)
        self.assertIn(frozen.verification_payload, document)
        self.assertIn("data:image/svg+xml;base64,", document)
        self.assertIn(ACTOR, document)
        self.assertNotIn("Print Format", document)
        self.assertEqual(output.mime_type, "application/pdf")
        self.assertEqual(output.size_bytes, len(output.content))
        self.assertEqual(output.sha256, hashlib.sha256(output.content).hexdigest())

    def test_mapping_drift_or_missing_actor_authority_fails_closed(self) -> None:
        selected = mapping()
        frozen = snapshot(selected)
        converter = lambda _html: b"%PDF-1.4\nsynthetic"
        renderer = lambda _template, _context: "<p>body</p>"

        with self.assertRaises(ControlledPrintMappingUnavailable):
            render_controlled_print_pdf(
                snapshot=frozen,
                mapping=mapping(global_id=UUID("00000000-0000-4000-8000-000000000647")),
                render_template=renderer,
                convert_pdf=converter,
                translate=lambda source, _language: source,
            )
        with self.assertRaises(ControlledPrintAuthorityUnavailable):
            render_controlled_print_pdf(
                snapshot=replace(
                    frozen,
                    actor_user_id="other@example.invalid",
                    snapshot_hash="",
                    verification_payload="",
                ),
                mapping=selected,
                render_template=renderer,
                convert_pdf=converter,
                translate=lambda source, _language: source,
            )

    def test_remote_active_or_invalid_render_output_is_rejected(self) -> None:
        for template in (
            '<img src="https://example.invalid/image.png">',
            '<script>document.write("unsafe")</script>',
        ):
            selected = mapping(template_content=template)
            with self.subTest(template=template), self.assertRaises(RuntimeError):
                render_controlled_print_pdf(
                    snapshot=snapshot(selected),
                    mapping=selected,
                    render_template=lambda value, _context: value,
                    convert_pdf=lambda _html: b"%PDF-1.4\nunused",
                    translate=lambda source, _language: source,
                )

        selected = mapping()
        frozen = snapshot(selected)
        with self.assertRaises(RuntimeError):
            render_controlled_print_pdf(
                snapshot=frozen,
                mapping=selected,
                render_template=lambda _template, _context: '<img src="//host/path">',
                convert_pdf=lambda _html: b"%PDF-1.4\nunused",
                translate=lambda source, _language: source,
            )
        with self.assertRaises(RuntimeError):
            render_controlled_print_pdf(
                snapshot=frozen,
                mapping=selected,
                render_template=lambda _template, _context: "<p>body</p>",
                convert_pdf=lambda _html: b"not-a-pdf",
                translate=lambda source, _language: source,
            )


if __name__ == "__main__":
    unittest.main()
