from __future__ import annotations

import sys
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import VersionConflict  # noqa: E402
from npi_core.grid_personalization.controller import (  # noqa: E402
    GridPersonalizationController,
    PersonalPreferenceLoad,
)
from npi_core.grid_personalization.domain import (  # noqa: E402
    CAPABILITIES,
    COLUMN_IDS,
    COLUMN_WIDTH_SPECS,
    MAX_FIXED_COLUMN_COUNT,
    PUBLISHER_AUTHORITY_REASON,
    TABLE_SCHEMA_VERSION,
    VIEW_IDS,
    FailClosedPublishedViewAuthorizer,
    GridFilterSnapshot,
    GridLayout,
    GridPersonalizationValidationError,
    PersonalGridPreference,
    PublicationAuthorityDecision,
    PublishedGridViewDefinition,
    PublishedGridViewRevision,
    PublishedGridViewRoot,
    rollback_as_new_revision,
)


PROJECT_ID = UUID("263881ed-8fc2-463b-acd8-e519171578fc")
OTHER_PROJECT_ID = UUID("f4496564-29d5-4e38-a514-7e946d85c5a3")
PUBLISHED_VIEW_ID = UUID("d6d1c05b-f5b7-4581-af57-a3a593399abe")
FIRST_REVISION_ID = UUID("fd8d8600-014b-4896-9347-475415364fad")
SECOND_REVISION_ID = UUID("2f2d13d3-b6fc-46e2-84d7-6df070485366")
FIRST_REQUEST_ID = UUID("c52c33c1-5e30-4217-91bb-3565a48283df")
SECOND_REQUEST_ID = UUID("20af16fa-4054-433c-a670-4a147fdba337")
ROLLBACK_REQUEST_ID = UUID("237357be-63e1-4318-89af-d91eecf35372")
PUBLISHED_AT = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)


def default_layout() -> dict[str, object]:
    return GridLayout.default().canonical_dict()


def filter_snapshot(
    *,
    project_id: UUID | None = None,
    priority: dict[str, str] | None = None,
    search: str = "",
) -> dict[str, object]:
    return {
        "projectId": None if project_id is None else str(project_id),
        "priority": priority,
        "search": search,
    }


def preference_with_project(project_id: UUID) -> PersonalGridPreference:
    return PersonalGridPreference.default().update(
        view_id="all",
        layout=default_layout(),
        filter_snapshot=filter_snapshot(
            project_id=project_id,
            priority={"scheme": "domain_severity", "value": "high"},
            search="  drawing review  ",
        ),
        save_filter=True,
        favorite_view_ids=["all"],
        recent_view_ids=["all"],
        default_project_id=str(project_id),
    )


class InMemoryPreferenceRepository:
    def __init__(
        self,
        *,
        preference: PersonalGridPreference | None = None,
        accessible_project_ids: frozenset[UUID] = frozenset(),
    ) -> None:
        self.preference = preference or PersonalGridPreference.default()
        self.project_ids = accessible_project_ids
        self.save_calls: list[dict[str, Any]] = []

    def load(self) -> PersonalPreferenceLoad:
        return PersonalPreferenceLoad(
            preference=self.preference,
            source=("stored" if self.preference.version else "default"),
        )

    def accessible_project_ids(self) -> frozenset[UUID]:
        return self.project_ids

    def save(
        self,
        preference: PersonalGridPreference,
        *,
        expected_version: int,
        changed_view_id: str,
    ) -> PersonalGridPreference:
        if self.preference.version != expected_version:
            raise VersionConflict()
        self.save_calls.append(
            {
                "preference": preference,
                "expectedVersion": expected_version,
                "changedViewId": changed_view_id,
            }
        )
        self.preference = preference
        return preference


def published_definition(
    *,
    view_id: str = "all",
    project_id: UUID | None = PROJECT_ID,
    search: str = "",
) -> PublishedGridViewDefinition:
    return PublishedGridViewDefinition.parse(
        {
            "viewId": view_id,
            "layout": default_layout(),
            "filter": filter_snapshot(project_id=project_id, search=search),
        }
    )


def allowed_authority() -> PublicationAuthorityDecision:
    return PublicationAuthorityDecision(
        allowed=True,
        reason_code="verified_test_fixture",
        evidence={"policyVersion": 1},
    )


def published_revision(
    *,
    revision_number: int,
    global_id: UUID,
    request_id: UUID,
    definition: PublishedGridViewDefinition,
    prior_revision=None,
    authority: PublicationAuthorityDecision | None = None,
) -> PublishedGridViewRevision:
    return PublishedGridViewRevision.create(
        global_id=global_id,
        published_view_global_id=PUBLISHED_VIEW_ID,
        tenant_id="TENANT-A",
        project_global_id=PROJECT_ID,
        revision_number=revision_number,
        prior_revision=prior_revision,
        restored_from_revision=None,
        name=f"Published My Work {revision_number}",
        description=f"Controlled revision {revision_number}",
        definition=definition,
        published_by="publisher@example.invalid",
        published_at=PUBLISHED_AT + timedelta(minutes=revision_number),
        authority=authority or allowed_authority(),
        request_id=request_id,
        trace_id=f"trace-r104-{revision_number:04d}",
    )


class GridPersonalizationPreferenceDomainTest(unittest.TestCase):
    def test_defaults_are_closed_complete_and_fail_closed(self) -> None:
        preference = PersonalGridPreference.default()
        response = preference.response_dict()

        self.assertEqual(response["gridId"], "my-work")
        self.assertEqual(response["tableSchemaVersion"], TABLE_SCHEMA_VERSION)
        self.assertEqual(response["version"], 0)
        self.assertEqual(
            [value["viewId"] for value in response["viewLayouts"]],
            list(VIEW_IDS),
        )
        for value in response["viewLayouts"]:
            self.assertEqual(value["layout"], default_layout())
            self.assertEqual(value["filter"], filter_snapshot())
            self.assertIs(value["hasSavedFilter"], False)
        self.assertEqual(response["favoriteViewIds"], [])
        self.assertEqual(response["recentViewIds"], [])
        self.assertIsNone(response["defaultProjectId"])
        self.assertIsNone(response["recoveryReason"])
        self.assertEqual(response["capabilities"], dict(CAPABILITIES))
        self.assertTrue(
            all(
                response["capabilities"][capability] is False
                for capability in (
                    "canPublishSharedView",
                    "canRollbackSharedView",
                    "canExport",
                    "canRunBulkActions",
                )
            )
        )

    def test_response_recovery_reason_is_closed(self) -> None:
        preference = PersonalGridPreference.default()
        self.assertEqual(
            preference.response_dict(
                recovery_reason="stored_preference_invalid"
            )["recoveryReason"],
            "stored_preference_invalid",
        )
        with self.assertRaises(ValueError):
            preference.response_dict(recovery_reason="unknown_recovery")

    def test_layout_contract_rejects_partial_duplicate_and_out_of_range_values(
        self,
    ) -> None:
        valid = default_layout()
        cases = {
            "extra field": {**valid, "sort": []},
            "partial order": {
                **valid,
                "columnOrder": list(COLUMN_IDS[:-1]),
            },
            "duplicate order": {
                **valid,
                "columnOrder": [*COLUMN_IDS[:-1], COLUMN_IDS[0]],
            },
            "boolean width": {
                **valid,
                "widths": {**valid["widths"], "type": True},
            },
            "below minimum": {
                **valid,
                "widths": {
                    **valid["widths"],
                    "item": COLUMN_WIDTH_SPECS["item"].minimum - 1,
                },
            },
            "above maximum": {
                **valid,
                "widths": {
                    **valid["widths"],
                    "item": COLUMN_WIDTH_SPECS["item"].maximum + 1,
                },
            },
            "required hidden": {
                **valid,
                "hiddenColumnIds": ["item"],
            },
            "too many fixed": {
                **valid,
                "fixedColumnCount": MAX_FIXED_COLUMN_COUNT + 1,
            },
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(GridPersonalizationValidationError):
                    GridLayout.parse(value)

    def test_filter_contract_is_exact_bounded_and_uses_closed_priority_pairs(
        self,
    ) -> None:
        parsed = GridFilterSnapshot.parse(
            filter_snapshot(
                project_id=PROJECT_ID,
                priority={"scheme": "domain_severity", "value": "critical"},
                search="  drawing review  ",
            )
        )
        self.assertEqual(parsed.project_id, PROJECT_ID)
        self.assertEqual(parsed.search, "drawing review")

        invalid_cases = {
            "extra field": {**filter_snapshot(), "owner": "user"},
            "noncanonical project": {
                **filter_snapshot(),
                "projectId": str(PROJECT_ID).upper(),
            },
            "cross-scheme priority": {
                **filter_snapshot(),
                "priority": {
                    "scheme": "domain_severity",
                    "value": "P0",
                },
            },
            "search too long": filter_snapshot(search="x" * 141),
            "control character": filter_snapshot(search="drawing\nreview"),
        }
        for name, value in invalid_cases.items():
            with self.subTest(name=name):
                with self.assertRaises(GridPersonalizationValidationError):
                    GridFilterSnapshot.parse(value)

    def test_access_loss_sanitizes_response_without_rewriting_history(self) -> None:
        stored = preference_with_project(PROJECT_ID)
        repository = InMemoryPreferenceRepository(preference=stored)
        response = GridPersonalizationController(repository).get()

        self.assertEqual(response["version"], stored.version)
        self.assertIsNone(response["defaultProjectId"])
        self.assertIsNone(response["viewLayouts"][0]["filter"]["projectId"])
        self.assertEqual(
            response["viewLayouts"][0]["filter"]["search"],
            "drawing review",
        )
        self.assertEqual(repository.preference, stored)
        self.assertEqual(repository.save_calls, [])

    def test_metadata_only_put_succeeds_once_and_exact_retry_is_not_duplicated(
        self,
    ) -> None:
        repository = InMemoryPreferenceRepository(
            accessible_project_ids=frozenset({PROJECT_ID})
        )
        controller = GridPersonalizationController(repository)
        command = {
            "expected_preference_version": 0,
            "table_schema_version": TABLE_SCHEMA_VERSION,
            "view_id": "all",
            "layout": default_layout(),
            "filter_snapshot": filter_snapshot(),
            "save_filter": False,
            "favorite_view_ids": ["today"],
            "recent_view_ids": ["today"],
            "default_project_id": str(PROJECT_ID),
        }

        response = controller.put(**command)

        self.assertEqual(response["version"], 1)
        self.assertEqual(response["favoriteViewIds"], ["today"])
        self.assertEqual(response["recentViewIds"], ["today"])
        self.assertEqual(response["defaultProjectId"], str(PROJECT_ID))
        self.assertIs(response["viewLayouts"][0]["hasSavedFilter"], False)
        self.assertEqual(len(repository.save_calls), 1)
        self.assertEqual(repository.save_calls[0]["changedViewId"], "all")

        with self.assertRaises(VersionConflict):
            controller.put(**command)
        self.assertEqual(repository.preference.version, 1)
        self.assertEqual(len(repository.save_calls), 1)

    def test_explicit_all_projects_filter_is_saved_and_round_trips(self) -> None:
        saved = PersonalGridPreference.default().update(
            view_id="today",
            layout=default_layout(),
            filter_snapshot=filter_snapshot(),
            save_filter=True,
            favorite_view_ids=[],
            recent_view_ids=["today"],
            default_project_id=str(PROJECT_ID),
        )
        today = saved.response_dict()["viewLayouts"][1]
        self.assertIs(today["hasSavedFilter"], True)
        self.assertIsNone(today["filter"]["projectId"])
        self.assertEqual(
            PersonalGridPreference.from_storage(
                version=saved.version,
                value=saved.storage_dict(),
            ),
            saved,
        )

        metadata_only = saved.update(
            view_id="today",
            layout=default_layout(),
            filter_snapshot=filter_snapshot(
                project_id=OTHER_PROJECT_ID,
                search="not committed",
            ),
            save_filter=False,
            favorite_view_ids=["today"],
            recent_view_ids=["today"],
            default_project_id=str(PROJECT_ID),
        )
        today_after_metadata = metadata_only.response_dict()["viewLayouts"][1]
        self.assertIs(today_after_metadata["hasSavedFilter"], True)
        self.assertEqual(today_after_metadata["filter"], filter_snapshot())

    def test_stale_expected_version_fails_before_save(self) -> None:
        repository = InMemoryPreferenceRepository(
            preference=PersonalGridPreference.default(version=4)
        )
        controller = GridPersonalizationController(repository)

        with self.assertRaises(VersionConflict):
            controller.put(
                expected_preference_version=3,
                table_schema_version=TABLE_SCHEMA_VERSION,
                view_id="all",
                layout=default_layout(),
                filter_snapshot=filter_snapshot(),
                save_filter=False,
                favorite_view_ids=[],
                recent_view_ids=[],
                default_project_id=None,
            )
        self.assertEqual(repository.save_calls, [])

    def test_put_rejects_inaccessible_filter_and_default_projects(self) -> None:
        cases = (
            ("filter.projectId", str(OTHER_PROJECT_ID), False, None),
            ("filter.projectId", str(OTHER_PROJECT_ID), True, None),
            ("defaultProjectId", None, False, str(OTHER_PROJECT_ID)),
        )
        for (
            expected_path,
            filter_project_id,
            save_filter,
            default_project_id,
        ) in cases:
            with self.subTest(path=expected_path, save_filter=save_filter):
                repository = InMemoryPreferenceRepository(
                    accessible_project_ids=frozenset({PROJECT_ID})
                )
                with self.assertRaises(
                    GridPersonalizationValidationError
                ) as raised:
                    GridPersonalizationController(repository).put(
                        expected_preference_version=0,
                        table_schema_version=TABLE_SCHEMA_VERSION,
                        view_id="all",
                        layout=default_layout(),
                        filter_snapshot={
                            **filter_snapshot(),
                            "projectId": filter_project_id,
                        },
                        save_filter=save_filter,
                        favorite_view_ids=[],
                        recent_view_ids=[],
                        default_project_id=default_project_id,
                    )
                self.assertEqual(raised.exception.path, expected_path)
                self.assertEqual(repository.save_calls, [])


class PublishedGridViewDomainTest(unittest.TestCase):
    def test_publication_authority_rejects_cyclic_evidence_cleanly(
        self,
    ) -> None:
        cyclic_mapping: dict[str, object] = {}
        cyclic_mapping["self"] = cyclic_mapping
        cyclic_list: list[object] = []
        cyclic_list.append(cyclic_list)

        for evidence in (
            cyclic_mapping,
            {"nested": cyclic_list},
        ):
            with self.subTest(evidence_type=type(evidence).__name__):
                with self.assertRaisesRegex(
                    ValueError,
                    "The publication authority evidence is invalid.",
                ):
                    PublicationAuthorityDecision(
                        allowed=True,
                        reason_code="verified_test_fixture",
                        evidence=evidence,
                    )

        shared = {"version": 1}
        repeated_alias = PublicationAuthorityDecision(
            allowed=True,
            reason_code="verified_test_fixture",
            evidence={"left": shared, "right": shared},
        )
        self.assertEqual(
            repeated_alias.evidence["left"],
            repeated_alias.evidence["right"],
        )

    def test_unresolved_publisher_authority_is_fail_closed(self) -> None:
        decision = FailClosedPublishedViewAuthorizer().decide(
            operation="publish",
            tenant_id="TENANT-A",
            project_id=PROJECT_ID,
            actor_user_id="project-lead@example.invalid",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, PUBLISHER_AUTHORITY_REASON)
        self.assertEqual(dict(decision.evidence), {})

        with self.assertRaisesRegex(PermissionError, PUBLISHER_AUTHORITY_REASON):
            PublishedGridViewRevision.create(
                global_id=FIRST_REVISION_ID,
                published_view_global_id=PUBLISHED_VIEW_ID,
                tenant_id="TENANT-A",
                project_global_id=PROJECT_ID,
                revision_number=1,
                prior_revision=None,
                restored_from_revision=None,
                name="My Work view",
                description="",
                definition=published_definition(),
                published_by="project-lead@example.invalid",
                published_at=PUBLISHED_AT,
                authority=decision,
                request_id=FIRST_REQUEST_ID,
                trace_id="trace-r104-denied",
            )

    def test_published_definition_cannot_cross_project_boundary(self) -> None:
        with self.assertRaises(
            GridPersonalizationValidationError
        ) as raised:
            PublishedGridViewRevision.create(
                global_id=FIRST_REVISION_ID,
                published_view_global_id=PUBLISHED_VIEW_ID,
                tenant_id="TENANT-A",
                project_global_id=PROJECT_ID,
                revision_number=1,
                prior_revision=None,
                restored_from_revision=None,
                name="Cross-Project view",
                description="",
                definition=published_definition(project_id=OTHER_PROJECT_ID),
                published_by="publisher@example.invalid",
                published_at=PUBLISHED_AT,
                authority=allowed_authority(),
                request_id=FIRST_REQUEST_ID,
                trace_id="trace-r104-cross-project",
            )
        self.assertEqual(
            raised.exception.path,
            "definition.filter.projectId",
        )

    def test_revision_authority_evidence_is_a_stable_immutable_snapshot(
        self,
    ) -> None:
        source_evidence: dict[str, object] = {
            "policy": {
                "scopes": ["publish"],
                "version": 3,
            },
            "projectIds": [str(PROJECT_ID)],
        }
        authority = PublicationAuthorityDecision(
            allowed=True,
            reason_code="verified_test_fixture",
            evidence=source_evidence,
        )
        revision = published_revision(
            revision_number=1,
            global_id=FIRST_REVISION_ID,
            request_id=FIRST_REQUEST_ID,
            definition=published_definition(),
            authority=authority,
        )
        original_hash = revision.snapshot_hash
        original_reference = revision.reference
        original_snapshot = revision.snapshot_dict()
        root = PublishedGridViewRoot.from_first_revision(revision)

        source_policy = source_evidence["policy"]
        self.assertIsInstance(source_policy, dict)
        assert isinstance(source_policy, dict)
        source_policy["version"] = 4
        source_scopes = source_policy["scopes"]
        self.assertIsInstance(source_scopes, list)
        assert isinstance(source_scopes, list)
        source_scopes.append("rollback")
        source_projects = source_evidence["projectIds"]
        self.assertIsInstance(source_projects, list)
        assert isinstance(source_projects, list)
        source_projects.append(str(OTHER_PROJECT_ID))

        self.assertEqual(revision.snapshot_hash, original_hash)
        self.assertEqual(revision.reference, original_reference)
        self.assertEqual(root.current_revision, original_reference)
        self.assertEqual(revision.snapshot_dict(), original_snapshot)
        snapshot_evidence = original_snapshot["authorityEvidence"]
        self.assertIsInstance(snapshot_evidence, dict)
        assert isinstance(snapshot_evidence, dict)
        self.assertIsInstance(snapshot_evidence["projectIds"], list)
        frozen_policy = revision.authority_evidence["policy"]
        self.assertIsInstance(frozen_policy, Mapping)
        assert isinstance(frozen_policy, Mapping)
        decision_policy = authority.evidence["policy"]
        self.assertIsInstance(decision_policy, Mapping)
        assert isinstance(decision_policy, Mapping)
        self.assertIsNot(decision_policy, frozen_policy)
        with self.assertRaises(TypeError):
            frozen_policy["version"] = 5
        with self.assertRaises(TypeError):
            decision_policy["version"] = 5
        frozen_scopes = frozen_policy["scopes"]
        self.assertIsInstance(frozen_scopes, tuple)
        with self.assertRaises(AttributeError):
            getattr(frozen_scopes, "append")("restore")
        self.assertIsInstance(revision.authority_evidence["projectIds"], tuple)

        fresh_snapshot = revision.snapshot_dict()
        snapshot_policy = snapshot_evidence["policy"]
        self.assertIsInstance(snapshot_policy, dict)
        assert isinstance(snapshot_policy, dict)
        snapshot_policy["version"] = 99
        snapshot_projects = snapshot_evidence["projectIds"]
        self.assertIsInstance(snapshot_projects, list)
        assert isinstance(snapshot_projects, list)
        snapshot_projects.append(str(OTHER_PROJECT_ID))
        self.assertEqual(revision.snapshot_hash, original_hash)
        self.assertEqual(revision.snapshot_dict(), fresh_snapshot)

    def test_root_advances_only_with_exact_successor(self) -> None:
        first = published_revision(
            revision_number=1,
            global_id=FIRST_REVISION_ID,
            request_id=FIRST_REQUEST_ID,
            definition=published_definition(search="first"),
        )
        root = PublishedGridViewRoot.from_first_revision(first)
        second = published_revision(
            revision_number=2,
            global_id=SECOND_REVISION_ID,
            request_id=SECOND_REQUEST_ID,
            definition=published_definition(view_id="today", search="second"),
            prior_revision=first.reference,
        )

        advanced = root.advance(second)

        self.assertEqual(root.optimistic_version, 1)
        self.assertEqual(root.current_revision, first.reference)
        self.assertEqual(advanced.optimistic_version, 2)
        self.assertEqual(advanced.current_revision, second.reference)
        self.assertEqual(advanced.request_id, SECOND_REQUEST_ID)

        wrong_project = PublishedGridViewRoot(
            global_id=root.global_id,
            tenant_id=root.tenant_id,
            project_global_id=OTHER_PROJECT_ID,
            optimistic_version=root.optimistic_version,
            current_revision=root.current_revision,
            created_by=root.created_by,
            created_at=root.created_at,
            request_id=root.request_id,
            trace_id=root.trace_id,
        )
        with self.assertRaises(ValueError):
            wrong_project.advance(second)

    def test_rollback_appends_a_revision_and_preserves_both_prior_snapshots(
        self,
    ) -> None:
        first = published_revision(
            revision_number=1,
            global_id=FIRST_REVISION_ID,
            request_id=FIRST_REQUEST_ID,
            definition=published_definition(search="first"),
        )
        first_root = PublishedGridViewRoot.from_first_revision(first)
        second = published_revision(
            revision_number=2,
            global_id=SECOND_REVISION_ID,
            request_id=SECOND_REQUEST_ID,
            definition=published_definition(view_id="today", search="second"),
            prior_revision=first.reference,
        )
        current_root = first_root.advance(second)

        restored = rollback_as_new_revision(
            root=current_root,
            current_revision=second,
            target_revision=first,
            published_by="publisher@example.invalid",
            published_at=PUBLISHED_AT + timedelta(minutes=3),
            authority=allowed_authority(),
            request_id=ROLLBACK_REQUEST_ID,
            trace_id="trace-r104-rollback",
        )
        restored_root = current_root.advance(restored)

        self.assertEqual(restored.revision_number, 3)
        self.assertEqual(restored.prior_revision, second.reference)
        self.assertEqual(restored.restored_from_revision, first.reference)
        self.assertEqual(restored.definition, first.definition)
        self.assertEqual(restored.name, first.name)
        self.assertEqual(restored.description, first.description)
        self.assertNotEqual(restored.global_id, first.global_id)
        self.assertEqual(first.revision_number, 1)
        self.assertEqual(second.revision_number, 2)
        self.assertEqual(current_root.current_revision, second.reference)
        self.assertEqual(restored_root.current_revision, restored.reference)
        self.assertEqual(restored_root.optimistic_version, 3)


if __name__ == "__main__":
    unittest.main()
