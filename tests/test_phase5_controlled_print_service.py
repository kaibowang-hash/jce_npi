from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (
    ControlledPrintContext,
    ControlledPrintMappingAmbiguous,
    ControlledPrintRegistryVersion,
    ControlledPrintSourceReference,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    sha256_json,
)
from npi_core.controlled_print.service import (
    AuthorizedControlledPrintProject,
    ControlledPrintCapabilityService,
)
from npi_core.controlled_print.source_registry import (
    ControlledPrintSourceRegistry,
    ResolvedControlledPrintSource,
)


NOW = datetime(2026, 8, 7, 3, 0, tzinfo=UTC)
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000661")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000662")
REGISTRY_ID = UUID("00000000-0000-4000-8000-000000000663")
MAPPING_ID = UUID("00000000-0000-4000-8000-000000000664")
SOURCE_KIND = "synthetic_controlled_source"
ACTOR = "engineer@example.invalid"


@dataclass
class Adapter:
    source_object_type: str = SOURCE_KIND

    def resolve_exact(
        self,
        *,
        project_global_id: UUID,
        source_global_id: UUID,
    ) -> ResolvedControlledPrintSource | None:
        payload = {
            "globalId": str(source_global_id),
            "title": "Frozen source",
            "version": 5,
        }
        return ResolvedControlledPrintSource(
            project_global_id=project_global_id,
            project_type_key="new_tool",
            gate_key="G3",
            reference=ControlledPrintSourceReference(
                SOURCE_KIND,
                source_global_id,
                5,
                "released",
                sha256_json(payload),
            ),
            snapshot=payload,
        )


@dataclass
class Repository:
    mappings: tuple[ControlledPrintRegistryVersion, ...]
    authorized: bool = True
    project_type_key: str = "new_tool"
    calls: list[str] = field(default_factory=list)

    def authorize_project(
        self,
        project_global_id: UUID,
    ) -> AuthorizedControlledPrintProject | None:
        self.calls.append("authorize")
        if not self.authorized:
            return None
        return AuthorizedControlledPrintProject(
            project_global_id,
            "synthetic-tenant",
            self.project_type_key,
        )

    def published_mapping_candidates(
        self,
        context: ControlledPrintContext,
        *,
        at: datetime,
    ) -> tuple[ControlledPrintRegistryVersion, ...]:
        self.calls.append("mappings")
        return self.mappings


def mapping(**changes: object) -> ControlledPrintRegistryVersion:
    template = "<h1>{{ doc.title }}</h1>"
    values: dict[str, object] = {
        "global_id": MAPPING_ID,
        "registry_global_id": REGISTRY_ID,
        "tenant_id": "synthetic-tenant",
        "mapping_key": "synthetic-output",
        "mapping_version": 1,
        "title": "Synthetic output",
        "state": PrintRegistryState.PUBLISHED,
        "source_object_type": SOURCE_KIND,
        "project_type_key": "new_tool",
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


class Phase5ControlledPrintServiceTest(unittest.TestCase):
    def service(self, repository: Repository, *, actor: str = ACTOR):
        return ControlledPrintCapabilityService(
            repository=repository,
            source_registry=ControlledPrintSourceRegistry((Adapter(),)),
            actor_user_id=actor,
        )

    def request(self, service: ControlledPrintCapabilityService):
        return service.capability(
            project_global_id=PROJECT_ID,
            source_object_type=SOURCE_KIND,
            source_global_id=SOURCE_ID,
            expected_source_version=5,
            language="en",
            at=NOW,
        )

    def test_exact_mapping_and_actor_authority_open_capability(self) -> None:
        repository = Repository((mapping(),))
        result = self.request(self.service(repository))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["available"])
        self.assertEqual(result["deliveryMode"], "controlled_pdf")
        self.assertEqual(result["copyState"], "not_numbered")
        self.assertEqual(result["permissions"], {"create": True, "download": True})
        self.assertNotIn("printFormatName", str(result))
        self.assertNotIn("template", str(result).casefold())
        self.assertEqual(repository.calls, ["authorize", "mappings"])

    def test_project_authorization_precedes_source_and_mapping_resolution(self) -> None:
        repository = Repository((mapping(),), authorized=False)
        result = self.request(self.service(repository))

        self.assertIsNone(result)
        self.assertEqual(repository.calls, ["authorize"])

    def test_missing_mapping_or_actor_authority_returns_closed_truth(self) -> None:
        for repository, actor in (
            (Repository(()), ACTOR),
            (Repository((mapping(),)), "other@example.invalid"),
        ):
            with self.subTest(actor=actor):
                result = self.request(self.service(repository, actor=actor))
                self.assertIsNotNone(result)
                assert result is not None
                self.assertFalse(result["available"])
                self.assertIsNone(result["registry"])
                self.assertEqual(
                    result["permissions"],
                    {"create": False, "download": False},
                )

    def test_ambiguous_mapping_and_project_type_drift_fail_closed(self) -> None:
        with self.assertRaises(ControlledPrintMappingAmbiguous):
            self.request(
                self.service(
                    Repository(
                        (
                            mapping(),
                            mapping(
                                global_id=UUID(
                                    "00000000-0000-4000-8000-000000000665"
                                ),
                                mapping_version=2,
                            ),
                        )
                    )
                )
            )
        with self.assertRaises(RuntimeError):
            self.request(
                self.service(
                    Repository((mapping(),), project_type_key="tool_change")
                )
            )


if __name__ == "__main__":
    unittest.main()
