from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import date
from typing import Any
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.security import Principal
from npi_core.gate_template.domain import (
    EvidenceKind,
    GateRequirementClassification,
    GateRequirementDefinition,
    GateRequirementPriority,
    GateTemplateVersion,
)
from npi_core.project.domain import (
    CreateProjectCommand,
    GateDefinition,
    IdempotencyRecord,
    InMemoryProjectStore,
    ProjectInstantiationService,
    ProjectTemplateVersion,
    ProjectType,
)


GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")
PROJECT_TEMPLATE_ID = UUID("2f4d63bf-4d51-4a17-aeb1-08116cb129fa")


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


def _as_document(value: dict[str, Any]) -> AttrDict:
    return AttrDict(
        {
            key: (
                [
                    _as_document(item) if isinstance(item, dict) else item
                    for item in item_value
                ]
                if isinstance(item_value, list)
                else item_value
            )
            for key, item_value in value.items()
        }
    )


def _published_gate_template() -> GateTemplateVersion:
    return GateTemplateVersion.create_draft(
        gate_template_global_id=GATE_TEMPLATE_ID,
        gate_template_code="SYNTHETIC-G0",
        gate_template_version=1,
        title="Synthetic feasibility Gate",
        applicable_project_types=(ProjectType.NEW_TOOL,),
        requirements=(
            GateRequirementDefinition(
                key="technical_input",
                title="Technical input",
                classification=GateRequirementClassification.REQUIRED,
                priority=GateRequirementPriority.P0,
                allowed_evidence_kinds=(
                    EvidenceKind.FILE_REVISION,
                    EvidenceKind.WBS_ITEM,
                ),
            ),
        ),
    ).publish(expected_version=1)


def _published_project_template(
    *,
    gate_template_hash: str | None,
) -> ProjectTemplateVersion:
    gate = GateDefinition(
        "G0",
        "Feasibility",
        1,
        gate_template_global_id=(
            GATE_TEMPLATE_ID if gate_template_hash is not None else None
        ),
        gate_template_version=1 if gate_template_hash is not None else None,
        gate_template_snapshot_hash=gate_template_hash,
    )
    return ProjectTemplateVersion.create_draft(
        template_global_id=PROJECT_TEMPLATE_ID,
        template_code="SYNTHETIC-P403",
        template_version=1,
        title="Synthetic P4-03 Project Template",
        applicable_project_types=(ProjectType.NEW_TOOL,),
        gates=(gate,),
    ).publish(expected_version=1)


def _instantiate(template: ProjectTemplateVersion, suffix: str):
    store = InMemoryProjectStore()
    store.add_template_version(template)
    command = CreateProjectCommand(
        idempotency_key=f"p403-repository-{suffix}",
        tenant_id="TENANT-A",
        business_code=f"P403-{suffix}",
        title="Synthetic P4-03 Project",
        project_type=ProjectType.NEW_TOOL,
        owner_user_id="owner@example.invalid",
        target_sop=date(2027, 6, 30),
        template_global_id=template.template_global_id,
        template_version=template.template_version,
        expected_version=template.version,
        references=(),
    )
    return ProjectInstantiationService(store).instantiate(command), command


class GateTemplateRepositoryTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "npi_core.gate_template.frappe_repository",
        "npi_core.project.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.records: list[dict[str, Any]] = []
        self.registry: dict[tuple[str, str], AttrDict] = {}
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.UniqueValidationError = type(
            "UniqueValidationError",
            (Exception,),
            {},
        )
        frappe.DuplicateEntryError = type(
            "DuplicateEntryError",
            (Exception,),
            {},
        )

        class Insertable:
            def __init__(inner_self, payload: dict[str, Any]) -> None:
                inner_self.payload = payload

            def insert(inner_self):
                self.records.append(inner_self.payload)
                return inner_self

        def get_doc(value: object, name: object = None):
            if isinstance(value, dict):
                return Insertable(value)
            try:
                return self.registry[(str(value), str(name))]
            except KeyError as error:
                raise frappe.DoesNotExistError() from error

        frappe.get_doc = get_doc
        frappe.db = types.SimpleNamespace()
        sys.modules["frappe"] = frappe
        self.frappe = frappe

        self.gate_repository = importlib.import_module(
            "npi_core.gate_template.frappe_repository"
        )
        self.project_repository = importlib.import_module(
            "npi_core.project.frappe_repository"
        )

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def test_exact_published_gate_template_snapshot_is_verified_and_ordered(
        self,
    ) -> None:
        template = _published_gate_template()
        version = AttrDict(
            gate_template=str(GATE_TEMPLATE_ID),
            global_id=str(template.global_id),
            gate_template_global_id=str(GATE_TEMPLATE_ID),
            gate_template_code=template.gate_template_code,
            gate_template_version=1,
            version_key=f"{GATE_TEMPLATE_ID}:1",
            optimistic_version=template.version,
            title=template.title,
            publication_state=template.publication_state.value,
            applicable_project_types='["new_tool"]',
            requirements=[
                AttrDict(
                    requirement_key="technical_input",
                    title="Technical input",
                    classification="required",
                    priority="P0",
                    allowed_evidence_kinds='["file_revision","wbs_item"]',
                )
            ],
            snapshot_hash=template.snapshot_hash,
        )
        root = AttrDict(
            enabled=1,
            global_id=str(GATE_TEMPLATE_ID),
            template_code=template.gate_template_code,
        )
        self.registry[("NPI Gate Template Version", f"{GATE_TEMPLATE_ID}:1")] = version
        self.registry[("NPI Gate Template", str(GATE_TEMPLATE_ID))] = root

        snapshot = self.gate_repository.load_exact_gate_template_snapshot(
            GATE_TEMPLATE_ID,
            1,
            template.snapshot_hash,
        )

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.snapshot_hash, template.snapshot_hash)
        self.assertEqual(snapshot.requirements[0].key, "technical_input")
        self.assertEqual(
            snapshot.requirements[0].allowed_evidence_kinds,
            (EvidenceKind.FILE_REVISION, EvidenceKind.WBS_ITEM),
        )
        root.enabled = 0
        historical = self.gate_repository.load_exact_gate_template_snapshot(
            GATE_TEMPLATE_ID,
            1,
            template.snapshot_hash,
        )
        self.assertIsNotNone(historical)
        self.assertIsNone(
            self.gate_repository.load_available_gate_template_snapshot(
                GATE_TEMPLATE_ID,
                1,
                template.snapshot_hash,
            )
        )
        with self.assertRaises(ValueError):
            self.gate_repository.load_exact_gate_template_snapshot(
                GATE_TEMPLATE_ID,
                1,
                "f" * 64,
            )

    def test_gate_shell_persistence_round_trip_preserves_configured_and_legacy_shape(
        self,
    ) -> None:
        gate_template = _published_gate_template()
        cases = (
            ("CONFIGURED", gate_template.snapshot_hash, True),
            ("LEGACY", None, False),
        )
        for suffix, snapshot_hash, configured in cases:
            with self.subTest(suffix=suffix):
                self.records.clear()
                self.registry.clear()
                template = _published_project_template(
                    gate_template_hash=snapshot_hash,
                )
                result, command = _instantiate(template, suffix)
                repository = self.project_repository.FrappeProjectRepository(
                    principal=Principal(
                        user_id="Administrator",
                        roles=frozenset({"System Manager"}),
                        tenant_id="TENANT-A",
                    ),
                    request_id=f"request-{suffix.lower()}",
                    trace_id=f"trace-{suffix.lower()}",
                )
                repository.save_atomic(
                    result,
                    IdempotencyRecord(
                        key=command.idempotency_key,
                        payload_hash=command.payload_hash,
                        result=result,
                    ),
                )

                project_payload = next(
                    item
                    for item in self.records
                    if item["doctype"] == "NPI Engineering Project"
                )
                gate_payload = next(
                    item for item in self.records if item["doctype"] == "NPI Gate Shell"
                )
                self.registry[
                    ("NPI Engineering Project", str(result.project.global_id))
                ] = _as_document(project_payload)
                self.registry[("NPI Gate Shell", str(result.gates[0].global_id))] = (
                    _as_document(gate_payload)
                )

                reloaded = repository._load_instantiation(result.project.global_id)
                self.assertEqual(reloaded, result)
                frozen_gate = json.loads(gate_payload["template_gate_snapshot"])
                self.assertEqual(
                    frozen_gate,
                    result.gates[0].template_gate_definition.canonical_dict(),
                )
                if configured:
                    self.assertEqual(
                        gate_payload["gate_template_global_id"],
                        str(GATE_TEMPLATE_ID),
                    )
                    self.assertEqual(
                        frozen_gate["gateTemplateRef"]["snapshotHash"],
                        gate_template.snapshot_hash,
                    )
                else:
                    self.assertIsNone(gate_payload["gate_template_global_id"])
                    self.assertNotIn("gateTemplateRef", frozen_gate)

                corrupt_gate = dict(gate_payload)
                corrupt_gate["template_gate_snapshot"] = json.dumps(
                    {"key": "G0", "sequence": 1, "title": "Changed"}
                )
                self.registry[("NPI Gate Shell", str(result.gates[0].global_id))] = (
                    _as_document(corrupt_gate)
                )
                with self.assertRaises(ValueError):
                    repository._load_instantiation(result.project.global_id)


if __name__ == "__main__":
    unittest.main()
