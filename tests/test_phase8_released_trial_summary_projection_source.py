from __future__ import annotations

import ast
import copy
import inspect
import sys
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_integration.released_summary_projection import (
    ReleasedSummaryProjectionContractError,
    ReleasedSummarySourceReader,
)
from npi_integration.released_summary_projection.source import (
    ProjectFirstReleasedSummarySourceReader,
    ReleasedSummarySourceConflict,
)
from tests.test_phase7_released_trial_summary_domain import (
    PROJECT,
    ROUND,
    summary,
    uid,
)


SOURCE = (
    ROOT
    / "apps/npi_integration/npi_integration/released_summary_projection/source.py"
)


class FakeRepository:
    def __init__(self, workspace: dict[str, object] | None) -> None:
        self.workspace = workspace
        self.calls: list[tuple[UUID, UUID]] = []

    def summary_workspace(
        self,
        project_id: UUID,
        round_id: UUID,
    ) -> dict[str, object] | None:
        self.calls.append((project_id, round_id))
        return copy.deepcopy(self.workspace)


def workspace(*revisions) -> dict[str, object]:
    current = revisions[-1] if revisions else None
    return {
        "projectGlobalId": str(PROJECT),
        "trialRound": {"globalId": str(ROUND)},
        "summaryRevisions": [
            value.snapshot_payload() | {"snapshotHash": value.snapshot_hash}
            for value in revisions
        ],
        "currentSummaryRevisionGlobalId": str(current.global_id) if current else None,
        "currentDecidedConclusion": None,
        "permissions": {},
        "controlledOutput": {},
        "holds": {},
    }


class Phase8ReleasedTrialSummaryProjectionSourceTest(unittest.TestCase):
    def test_reader_protocol_requires_project_round_then_summary_revision(self) -> None:
        parameters = inspect.signature(
            ReleasedSummarySourceReader.read_current_source
        ).parameters
        self.assertEqual(
            tuple(parameters),
            (
                "self",
                "project_global_id",
                "trial_round_global_id",
                "summary_revision_global_id",
            ),
        )

    def test_exact_current_source_reuses_p7_07_identity_and_hashes(self) -> None:
        current = summary()
        repository = FakeRepository(workspace(current))
        result = ProjectFirstReleasedSummarySourceReader(
            repository
        ).read_current_source(
            project_global_id=PROJECT,
            trial_round_global_id=ROUND,
            summary_revision_global_id=current.global_id,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(repository.calls, [(PROJECT, ROUND)])
        self.assertEqual(result.project_global_id, current.project_global_id)
        self.assertEqual(result.trial_round_global_id, current.trial_round_global_id)
        self.assertEqual(result.summary_revision_global_id, current.global_id)
        self.assertEqual(result.summary_global_id, current.summary_global_id)
        self.assertEqual(result.summary_version, current.summary_version)
        self.assertEqual(result.snapshot_hash, current.snapshot_hash)
        self.assertEqual(result.source_manifest_hash, current.source_manifest_hash)
        self.assertEqual(
            result.presentation_projection_hash,
            current.presentation_projection_hash,
        )
        self.assertEqual(result.redaction_manifest_hash, current.redaction_manifest_hash)

    def test_permission_safe_or_empty_workspace_is_unavailable(self) -> None:
        for value in (None, workspace()):
            with self.subTest(value=value):
                repository = FakeRepository(value)
                result = ProjectFirstReleasedSummarySourceReader(
                    repository
                ).read_current_source(
                    project_global_id=PROJECT,
                    trial_round_global_id=ROUND,
                    summary_revision_global_id=uid(900),
                )
                self.assertIsNone(result)
                self.assertEqual(repository.calls, [(PROJECT, ROUND)])

    def test_stale_foreign_duplicate_and_tampered_source_fail_closed(self) -> None:
        current = summary()
        foreign_project = workspace(current)
        foreign_project["projectGlobalId"] = str(uid(901))
        foreign_round = workspace(current)
        foreign_round["trialRound"] = {"globalId": str(uid(902))}
        duplicate = workspace(current, current)
        tampered = workspace(current)
        tampered_revisions = tampered["summaryRevisions"]
        assert isinstance(tampered_revisions, list)
        tampered_revisions[0]["snapshotHash"] = "0" * 64
        cases = (
            (workspace(current), uid(903)),
            (foreign_project, current.global_id),
            (foreign_round, current.global_id),
            (duplicate, current.global_id),
            (tampered, current.global_id),
        )
        for value, requested in cases:
            with self.subTest(requested=requested), self.assertRaises(
                ReleasedSummarySourceConflict
            ) as raised:
                ProjectFirstReleasedSummarySourceReader(
                    FakeRepository(value)
                ).read_current_source(
                    project_global_id=PROJECT,
                    trial_round_global_id=ROUND,
                    summary_revision_global_id=requested,
                )
            self.assertNotIn(str(PROJECT), str(raised.exception))
            self.assertNotIn(str(requested), str(raised.exception))

    def test_valid_successor_stream_resolves_only_its_exact_current_tip(self) -> None:
        first = summary()
        second = summary(
            global_id=21,
            summary_version=2,
            predecessor=first,
            conclusion_id=17,
            conclusion_version=5,
            conclusion_marker="e",
        )
        repository = FakeRepository(workspace(first, second))
        reader = ProjectFirstReleasedSummarySourceReader(repository)
        result = reader.read_current_source(
            project_global_id=PROJECT,
            trial_round_global_id=ROUND,
            summary_revision_global_id=second.global_id,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.summary_version, 2)
        with self.assertRaises(ReleasedSummarySourceConflict):
            reader.read_current_source(
                project_global_id=PROJECT,
                trial_round_global_id=ROUND,
                summary_revision_global_id=first.global_id,
            )

    def test_invalid_inputs_and_repository_fail_before_any_source_read(self) -> None:
        with self.assertRaises(ReleasedSummaryProjectionContractError):
            ProjectFirstReleasedSummarySourceReader(object())
        repository = FakeRepository(workspace(summary()))
        with self.assertRaises(ReleasedSummaryProjectionContractError):
            ProjectFirstReleasedSummarySourceReader(repository).read_current_source(
                project_global_id=str(PROJECT),  # type: ignore[arg-type]
                trial_round_global_id=ROUND,
                summary_revision_global_id=uid(904),
            )
        self.assertEqual(repository.calls, [])

    def test_source_adapter_has_no_frappe_network_write_or_external_success(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        imported_roots: set[str] = set()
        for node in ast.walk(ast.parse(source, filename=str(SOURCE))):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertFalse(
            imported_roots
            & {"frappe", "httpx", "requests", "socket", "urllib", "redis", "rq"}
        )
        for forbidden in (
            ".insert(",
            ".save(",
            ".submit(",
            "enqueue(",
            "base_url",
            "target_method",
            "external_success",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
