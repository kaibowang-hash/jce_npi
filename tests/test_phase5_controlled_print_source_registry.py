from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from dataclasses import dataclass
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (
    ControlledPrintSourceReference,
    ControlledPrintStateConflict,
    ControlledPrintUnavailable,
    sha256_json,
)
from npi_core.controlled_print.source_registry import (
    ControlledPrintSourceRegistry,
    ResolvedControlledPrintSource,
    _disposable_runtime_source_global_id,
    default_controlled_print_source_registry,
)


PROJECT_ID = UUID("822ce4ac-0a90-5c0e-8c30-d791dc56e3a9")
OTHER_PROJECT_ID = UUID("48124772-9b21-5237-9564-36a9c955cc2c")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000623")
SOURCE_KIND = "synthetic_controlled_source"


@dataclass
class SyntheticAdapter:
    source: ResolvedControlledPrintSource | None
    source_object_type: str = SOURCE_KIND

    def resolve_exact(
        self,
        *,
        project_global_id: UUID,
        source_global_id: UUID,
    ) -> ResolvedControlledPrintSource | None:
        return self.source


def source(
    *,
    project_id: UUID = PROJECT_ID,
    source_id: UUID = SOURCE_ID,
    source_kind: str = SOURCE_KIND,
    source_version: int = 4,
) -> ResolvedControlledPrintSource:
    payload = {
        "globalId": str(source_id),
        "title": "Synthetic frozen source",
        "version": source_version,
    }
    return ResolvedControlledPrintSource(
        project_global_id=project_id,
        project_type_key="synthetic-project",
        gate_key="G3",
        reference=ControlledPrintSourceReference(
            source_kind,
            source_id,
            source_version,
            "released",
            sha256_json(payload),
        ),
        snapshot=payload,
    )


class Phase5ControlledPrintSourceRegistryTest(unittest.TestCase):
    def test_default_registry_has_no_enabled_source_or_production_fallback(
        self,
    ) -> None:
        registry = default_controlled_print_source_registry()

        self.assertEqual(registry.source_object_types, ())
        with self.assertRaises(ControlledPrintUnavailable):
            registry.resolve_exact(
                project_global_id=PROJECT_ID,
                source_object_type=SOURCE_KIND,
                source_global_id=SOURCE_ID,
                expected_source_version=4,
            )

    def test_synthetic_source_is_enabled_only_by_exact_disposable_site_marker(
        self,
    ) -> None:
        for marker, expected in (
            (None, ()),
            ("npi-one-local-runtime-disposable", ()),
            (
                "npi-one-local-runtime-disposable-v1",
                ("npi.synthetic_runtime_project",),
            ),
        ):
            with self.subTest(marker=marker):
                frappe = SimpleNamespace(
                    conf={"npi_runtime_disposable_marker": marker},
                )
                with patch.dict("sys.modules", {"frappe": frappe}):
                    registry = default_controlled_print_source_registry()
                self.assertEqual(registry.source_object_types, expected)

    def test_disposable_source_identity_is_server_owned_uuid4(self) -> None:
        source_id = _disposable_runtime_source_global_id(PROJECT_ID)

        self.assertEqual(source_id.version, 4)
        self.assertEqual(source_id, _disposable_runtime_source_global_id(PROJECT_ID))
        self.assertNotEqual(
            source_id,
            _disposable_runtime_source_global_id(OTHER_PROJECT_ID),
        )

    def test_exact_registered_source_resolves_and_snapshot_is_frozen(self) -> None:
        mutable = {
            "globalId": str(SOURCE_ID),
            "title": "Synthetic frozen source",
            "version": 4,
        }
        resolved = ResolvedControlledPrintSource(
            project_global_id=PROJECT_ID,
            project_type_key="synthetic-project",
            gate_key="G3",
            reference=ControlledPrintSourceReference(
                SOURCE_KIND,
                SOURCE_ID,
                4,
                "released",
                sha256_json(mutable),
            ),
            snapshot=mutable,
        )
        registry = ControlledPrintSourceRegistry((SyntheticAdapter(resolved),))

        result = registry.resolve_exact(
            project_global_id=PROJECT_ID,
            source_object_type=SOURCE_KIND,
            source_global_id=SOURCE_ID,
            expected_source_version=4,
        )
        mutable["title"] = "Changed live source"

        self.assertEqual(result.snapshot["title"], "Synthetic frozen source")
        self.assertEqual(registry.source_object_types, (SOURCE_KIND,))
        self.assertEqual(
            result.context(tenant_id="synthetic-tenant", language="zh").language,
            "zh",
        )

    def test_unknown_missing_and_stale_sources_fail_closed(self) -> None:
        registry = ControlledPrintSourceRegistry((SyntheticAdapter(source()),))
        for kind, expected_version in (("unknown", 4), (SOURCE_KIND, 3)):
            with self.subTest(kind=kind, expected_version=expected_version):
                expected = (
                    ControlledPrintUnavailable
                    if kind == "unknown"
                    else ControlledPrintStateConflict
                )
                with self.assertRaises(expected):
                    registry.resolve_exact(
                        project_global_id=PROJECT_ID,
                        source_object_type=kind,
                        source_global_id=SOURCE_ID,
                        expected_source_version=expected_version,
                    )

        missing = ControlledPrintSourceRegistry((SyntheticAdapter(None),))
        with self.assertRaises(ControlledPrintUnavailable):
            missing.resolve_exact(
                project_global_id=PROJECT_ID,
                source_object_type=SOURCE_KIND,
                source_global_id=SOURCE_ID,
                expected_source_version=4,
            )

    def test_adapter_scope_escape_and_snapshot_hash_mismatch_are_rejected(self) -> None:
        escaped = ControlledPrintSourceRegistry(
            (SyntheticAdapter(source(project_id=OTHER_PROJECT_ID)),)
        )
        with self.assertRaises(RuntimeError):
            escaped.resolve_exact(
                project_global_id=PROJECT_ID,
                source_object_type=SOURCE_KIND,
                source_global_id=SOURCE_ID,
                expected_source_version=4,
            )

        with self.assertRaises(RuntimeError):
            ResolvedControlledPrintSource(
                project_global_id=PROJECT_ID,
                project_type_key="synthetic-project",
                gate_key=None,
                reference=ControlledPrintSourceReference(
                    SOURCE_KIND,
                    SOURCE_ID,
                    4,
                    "released",
                    "a" * 64,
                ),
                snapshot={"globalId": str(SOURCE_ID), "version": 4},
            )

    def test_duplicate_or_invalid_adapter_types_cannot_open_registry(self) -> None:
        with self.assertRaises(ValueError):
            ControlledPrintSourceRegistry(
                (SyntheticAdapter(source()), SyntheticAdapter(source()))
            )
        invalid = SyntheticAdapter(source(), source_object_type="")
        with self.assertRaises(ValueError):
            ControlledPrintSourceRegistry((invalid,))


if __name__ == "__main__":
    unittest.main()
