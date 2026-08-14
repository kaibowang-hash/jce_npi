from __future__ import annotations

import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.production_transition.domain import (
    AcknowledgementDirection,
    AcknowledgementSlotDefinition,
    HandoverObjectRequirement,
    HandoverSourceKind,
    MANDATORY_OBSERVATION_PROVIDER_KINDS,
    MetricComparator,
    ObservationProviderKind,
    ObservationReferenceUsage,
    ObservationSourceRule,
    ProductionTransitionApplicability,
    ProductionTransitionPolicyVersion,
    ReceivingGroupDefinition,
    TechnicalDisposition,
)
from npi_core.production_transition.request_validation import (
    ExactSourceSelection,
    ManifestSourceSelection,
)
from npi_core.production_transition.source_resolver import (
    SOURCE_LOADER_SEAMS,
    ResolvedTransitionSource,
    SourceResolutionContext,
    TransitionSourceRepository,
    resolve_exact_source,
    resolve_manifest_sources,
    resolve_observation_sources,
)
from npi_core.project.domain import ProjectType


def uid(value: int) -> UUID:
    return UUID(int=value)


TENANT = "tenant-a"
PROJECT_ID = uid(1)
SOURCE_A = uid(101)
SOURCE_B = uid(102)
HASH_A = "a" * 64
HASH_B = "b" * 64
CONTEXT = SourceResolutionContext(TENANT, PROJECT_ID)
NOW = datetime(2026, 8, 14, 8, 30, tzinfo=UTC)


def source_rules() -> tuple[ObservationSourceRule, ...]:
    rules = []
    for kind in MANDATORY_OBSERVATION_PROVIDER_KINDS:
        if kind is ObservationProviderKind.ACTUAL_SOP:
            rules.append(
                ObservationSourceRule(
                    provider_kind=kind,
                    allowed_dispositions=(TechnicalDisposition.NOT_EVALUABLE,),
                )
            )
        else:
            rules.append(
                ObservationSourceRule(
                    provider_kind=kind,
                    unit="count",
                    comparator=MetricComparator.LESS_THAN_OR_EQUAL,
                    threshold=Decimal("1"),
                    allowed_dispositions=(
                        TechnicalDisposition.NOT_EVALUABLE,
                        TechnicalDisposition.WITHIN_RULE,
                        TechnicalDisposition.OUTSIDE_RULE,
                    ),
                )
            )
    return tuple(rules)


def published_policy() -> ProductionTransitionPolicyVersion:
    draft = ProductionTransitionPolicyVersion.create_draft(
        policy_global_id=uid(10),
        tenant_id=TENANT,
        policy_code="PROD-TRANSITION",
        title="Production transition source seam policy",
        applicability=ProductionTransitionApplicability((ProjectType.NEW_TOOL,)),
        receiving_groups=(
            ReceivingGroupDefinition("sender_group", "Sender group"),
            ReceivingGroupDefinition("receiver_group", "Receiver group"),
        ),
        acknowledgement_slots=(
            AcknowledgementSlotDefinition(
                "sender",
                "sender_group",
                AcknowledgementDirection.SENDER,
                ("npi_owner",),
            ),
            AcknowledgementSlotDefinition(
                "receiver",
                "receiver_group",
                AcknowledgementDirection.RECEIVER,
                ("production_receiver",),
            ),
        ),
        handover_requirements=(
            HandoverObjectRequirement(
                "primary_work",
                (
                    HandoverSourceKind.DOMAIN_WORK_ITEM,
                    HandoverSourceKind.RELEASED_DOCUMENT,
                ),
                "open_action",
            ),
            HandoverObjectRequirement(
                "secondary_work",
                (HandoverSourceKind.DOMAIN_WORK_ITEM,),
                "review_record",
            ),
        ),
        observation_source_rules=source_rules(),
        observation_window_days=30,
        changed_by_user_id="admin@example.invalid",
        changed_at=NOW,
        request_id=uid(11),
        trace_id="trace-p706-source-policy",
    )
    return draft.publish(
        expected_version=1,
        changed_by_user_id="publisher@example.invalid",
        changed_at=NOW,
        request_id=uid(12),
        trace_id="trace-p706-source-policy-publish",
    )


def exact_selection(
    global_id: UUID = SOURCE_A,
    *,
    kind: HandoverSourceKind = HandoverSourceKind.DOMAIN_WORK_ITEM,
    version: int = 4,
) -> ExactSourceSelection:
    return ExactSourceSelection(kind.value, global_id, version)


def manifest_selection(
    requirement_key: str,
    global_id: UUID,
    *,
    kind: HandoverSourceKind = HandoverSourceKind.DOMAIN_WORK_ITEM,
    version: int = 4,
) -> ManifestSourceSelection:
    return ManifestSourceSelection(
        requirement_key,
        kind.value,
        global_id,
        version,
    )


class FakeTransitionSourceRepository:
    def __init__(self) -> None:
        self.sources: dict[
            tuple[HandoverSourceKind, UUID], object
        ] = {}
        self.calls: list[
            tuple[str, SourceResolutionContext, UUID, bool]
        ] = []

    def put(
        self,
        kind: HandoverSourceKind,
        global_id: UUID,
        version: int,
        snapshot_hash: str,
    ) -> None:
        self.sources[(kind, global_id)] = ResolvedTransitionSource(
            kind,
            global_id,
            version,
            snapshot_hash,
        )

    def _load(
        self,
        kind: HandoverSourceKind,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        self.calls.append(
            (SOURCE_LOADER_SEAMS[kind], context, global_id, for_update)
        )
        value = self.sources.get((kind, global_id))
        return value  # type: ignore[return-value]

    def load_readiness_instance_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.READINESS_INSTANCE_REVISION,
            context,
            global_id,
            for_update=for_update,
        )

    def load_domain_work_item(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.DOMAIN_WORK_ITEM,
            context,
            global_id,
            for_update=for_update,
        )

    def load_released_document(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.RELEASED_DOCUMENT,
            context,
            global_id,
            for_update=for_update,
        )

    def load_release_baseline(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.RELEASE_BASELINE,
            context,
            global_id,
            for_update=for_update,
        )

    def load_file_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.FILE_REVISION,
            context,
            global_id,
            for_update=for_update,
        )

    def load_tooling_capacity_scenario(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.TOOLING_CAPACITY_SCENARIO,
            context,
            global_id,
            for_update=for_update,
        )

    def load_trial_defect_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.TRIAL_DEFECT_REVISION,
            context,
            global_id,
            for_update=for_update,
        )

    def load_trial_review_reference(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.TRIAL_REVIEW_REFERENCE,
            context,
            global_id,
            for_update=for_update,
        )

    def load_trial_conclusion(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None:
        return self._load(
            HandoverSourceKind.TRIAL_CONCLUSION,
            context,
            global_id,
            for_update=for_update,
        )


class Phase7ProductionTransitionSourceResolverTest(unittest.TestCase):
    def test_resolved_source_and_context_are_frozen(self) -> None:
        source = ResolvedTransitionSource(
            HandoverSourceKind.DOMAIN_WORK_ITEM,
            SOURCE_A,
            4,
            HASH_A,
        )

        with self.assertRaises(FrozenInstanceError):
            source.source_version = 5  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            CONTEXT.tenant_id = "tenant-b"  # type: ignore[misc]

    def test_closed_registry_names_all_nine_repository_seams_exactly(self) -> None:
        expected = {
            "readiness_instance_revision": "load_readiness_instance_revision",
            "domain_work_item": "load_domain_work_item",
            "released_document": "load_released_document",
            "release_baseline": "load_release_baseline",
            "file_revision": "load_file_revision",
            "tooling_capacity_scenario": "load_tooling_capacity_scenario",
            "trial_defect_revision": "load_trial_defect_revision",
            "trial_review_reference": "load_trial_review_reference",
            "trial_conclusion": "load_trial_conclusion",
        }

        self.assertEqual(
            {kind.value: name for kind, name in SOURCE_LOADER_SEAMS.items()},
            expected,
        )
        protocol_source = inspect.getsource(TransitionSourceRepository)
        for seam_name in expected.values():
            with self.subTest(seam_name=seam_name):
                self.assertIn(f"def {seam_name}(", protocol_source)

    def test_every_kind_dispatches_only_its_exact_read_only_seam(self) -> None:
        repository = FakeTransitionSourceRepository()
        for index, kind in enumerate(HandoverSourceKind, start=1):
            global_id = uid(200 + index)
            repository.put(kind, global_id, index, f"{index}" * 64)

            resolved = resolve_exact_source(
                exact_selection(global_id, kind=kind, version=index),
                context=CONTEXT,
                repository=repository,
                for_update=False,
            )

            self.assertIs(resolved.kind, kind)
            self.assertEqual(
                repository.calls[-1],
                (SOURCE_LOADER_SEAMS[kind], CONTEXT, global_id, False),
            )

    def test_manifest_allows_same_kind_for_distinct_requirements_and_injects_roles(self) -> None:
        repository = FakeTransitionSourceRepository()
        repository.put(HandoverSourceKind.DOMAIN_WORK_ITEM, SOURCE_A, 4, HASH_A)
        repository.put(HandoverSourceKind.DOMAIN_WORK_ITEM, SOURCE_B, 5, HASH_B)

        references = resolve_manifest_sources(
            (
                manifest_selection("primary_work", SOURCE_A),
                manifest_selection("secondary_work", SOURCE_B, version=5),
            ),
            policy=published_policy(),
            context=CONTEXT,
            repository=repository,
        )

        self.assertEqual([value.role for value in references], ["open_action", "review_record"])
        self.assertEqual(
            [value.requirement_key for value in references],
            ["primary_work", "secondary_work"],
        )
        self.assertEqual([value.snapshot_hash for value in references], [HASH_A, HASH_B])
        self.assertTrue(all(call[3] for call in repository.calls))

    def test_manifest_rejects_ambiguous_cross_requirement_identity_before_loading(self) -> None:
        repository = FakeTransitionSourceRepository()

        with self.assertRaises(RequestValidationFailed):
            resolve_manifest_sources(
                (
                    manifest_selection("primary_work", SOURCE_A),
                    manifest_selection("secondary_work", SOURCE_A),
                ),
                policy=published_policy(),
                context=CONTEXT,
                repository=repository,
            )

        self.assertEqual(repository.calls, [])

    def test_manifest_rejects_unknown_requirement_or_disallowed_kind_before_loading(self) -> None:
        invalid = (
            manifest_selection("unknown", SOURCE_A),
            manifest_selection(
                "primary_work",
                SOURCE_A,
                kind=HandoverSourceKind.FILE_REVISION,
            ),
        )
        for selection in invalid:
            with self.subTest(selection=selection):
                repository = FakeTransitionSourceRepository()
                with self.assertRaises(RequestValidationFailed):
                    resolve_manifest_sources(
                        (selection,),
                        policy=published_policy(),
                        context=CONTEXT,
                        repository=repository,
                    )
                self.assertEqual(repository.calls, [])

    def test_expected_version_is_compared_to_server_truth_without_caller_hash(self) -> None:
        repository = FakeTransitionSourceRepository()
        repository.put(HandoverSourceKind.DOMAIN_WORK_ITEM, SOURCE_A, 5, HASH_A)

        with self.assertRaises(RequestValidationFailed):
            resolve_exact_source(
                exact_selection(version=4),
                context=CONTEXT,
                repository=repository,
            )

        self.assertEqual(len(repository.calls), 1)

    def test_malformed_or_scope_escaped_repository_result_fails_closed(self) -> None:
        invalid = (
            None,
            {"source_version": 4},
            ResolvedTransitionSource(
                HandoverSourceKind.RELEASED_DOCUMENT,
                SOURCE_A,
                4,
                HASH_A,
            ),
            ResolvedTransitionSource(
                HandoverSourceKind.DOMAIN_WORK_ITEM,
                SOURCE_B,
                4,
                HASH_A,
            ),
            ResolvedTransitionSource(
                HandoverSourceKind.DOMAIN_WORK_ITEM,
                SOURCE_A,
                4,
                "not-a-hash",
            ),
        )
        for result in invalid:
            with self.subTest(result=result):
                repository = FakeTransitionSourceRepository()
                repository.sources[
                    (HandoverSourceKind.DOMAIN_WORK_ITEM, SOURCE_A)
                ] = result
                with self.assertRaises(RequestValidationFailed):
                    resolve_exact_source(
                        exact_selection(),
                        context=CONTEXT,
                        repository=repository,
                    )

    def test_observation_shared_identity_is_loaded_once_and_only_usage_differs(self) -> None:
        repository = FakeTransitionSourceRepository()
        repository.put(HandoverSourceKind.DOMAIN_WORK_ITEM, SOURCE_A, 4, HASH_A)
        selection = exact_selection()

        context_references, retrospective_references = resolve_observation_sources(
            (selection,),
            (selection,),
            context=CONTEXT,
            repository=repository,
        )

        self.assertEqual(len(repository.calls), 1)
        context_reference = context_references[0]
        retrospective_reference = retrospective_references[0]
        self.assertEqual(
            (
                context_reference.kind,
                context_reference.global_id,
                context_reference.source_version,
                context_reference.snapshot_hash,
            ),
            (
                retrospective_reference.kind,
                retrospective_reference.global_id,
                retrospective_reference.source_version,
                retrospective_reference.snapshot_hash,
            ),
        )
        self.assertIs(context_reference.usage, ObservationReferenceUsage.CONTEXT)
        self.assertIs(
            retrospective_reference.usage,
            ObservationReferenceUsage.RETROSPECTIVE,
        )

    def test_observation_version_conflict_or_same_list_duplicate_fails_before_loading(self) -> None:
        cases = (
            ((exact_selection(),), (exact_selection(version=5),)),
            ((exact_selection(), exact_selection()), ()),
        )
        for context_selections, retrospective_selections in cases:
            with self.subTest(
                context_selections=context_selections,
                retrospective_selections=retrospective_selections,
            ):
                repository = FakeTransitionSourceRepository()
                with self.assertRaises(RequestValidationFailed):
                    resolve_observation_sources(
                        context_selections,
                        retrospective_selections,
                        context=CONTEXT,
                        repository=repository,
                    )
                self.assertEqual(repository.calls, [])

    def test_resolver_has_no_frappe_sql_erp_or_network_dependency(self) -> None:
        source = Path(
            "apps/npi_core/npi_core/production_transition/source_resolver.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "frappe.db",
            "import requests",
            "from requests",
            "import urllib",
            "from urllib",
            "erpnext",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
