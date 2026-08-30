from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.trial.released_summary_domain import (
    RELEASED_TRIAL_SUMMARY_PROJECTION_SCHEMA_VERSION,
    RELEASED_TRIAL_SUMMARY_REDACTION_SCHEMA_VERSION,
    RELEASED_TRIAL_SUMMARY_SCHEMA_VERSION,
)
from npi_integration.released_summary_projection import (
    RELEASED_SUMMARY_PRESENTATION_SCHEMA_VERSION,
    RELEASED_SUMMARY_REDACTION_SCHEMA_VERSION,
    RELEASED_SUMMARY_SCHEMA_VERSION,
    ContractHeldReleasedSummaryProjectionAdapter,
    ExternalProjectionState,
    ReleasedSummaryProjectionConfiguration,
    ReleasedSummaryProjectionConfigurationState,
    ReleasedSummaryProjectionContractError,
    ReleasedSummaryProjectionResult,
    ReleasedSummarySourceDescriptor,
    ReleasedSummarySourceState,
    UnavailableReason,
)


MODULE_ROOT = (
    ROOT
    / "apps/npi_integration/npi_integration/released_summary_projection"
)


def uid(value: int) -> UUID:
    return UUID(int=value)


def descriptor(**overrides: object) -> ReleasedSummarySourceDescriptor:
    values: dict[str, object] = {
        "project_global_id": uid(1),
        "summary_revision_global_id": uid(2),
        "summary_global_id": uid(3),
        "trial_round_global_id": uid(4),
        "summary_version": 2,
        "snapshot_hash": "1" * 64,
        "source_manifest_hash": "2" * 64,
        "presentation_projection_hash": "3" * 64,
        "redaction_manifest_hash": "4" * 64,
    }
    values.update(overrides)
    return ReleasedSummarySourceDescriptor(**values)


class Phase8ReleasedTrialSummaryProjectionDomainTest(unittest.TestCase):
    def test_schema_constants_reuse_the_exact_p7_07_contracts(self) -> None:
        self.assertEqual(
            (
                RELEASED_SUMMARY_SCHEMA_VERSION,
                RELEASED_SUMMARY_PRESENTATION_SCHEMA_VERSION,
                RELEASED_SUMMARY_REDACTION_SCHEMA_VERSION,
            ),
            (
                RELEASED_TRIAL_SUMMARY_SCHEMA_VERSION,
                RELEASED_TRIAL_SUMMARY_PROJECTION_SCHEMA_VERSION,
                RELEASED_TRIAL_SUMMARY_REDACTION_SCHEMA_VERSION,
            ),
        )

    def test_source_descriptor_is_exact_immutable_and_deterministically_hashed(self) -> None:
        source = descriptor()
        self.assertEqual(source, descriptor())
        self.assertEqual(len(source.fingerprint), 64)
        self.assertNotEqual(
            source.fingerprint,
            replace(source, summary_version=3).fingerprint,
        )
        with self.assertRaises(AttributeError):
            source.summary_version = 3  # type: ignore[misc]

    def test_source_descriptor_rejects_schema_uuid_version_and_hash_drift(self) -> None:
        invalid = (
            {"project_global_id": str(uid(1))},
            {"summary_version": True},
            {"summary_version": 0},
            {"snapshot_hash": "A" * 64},
            {"source_manifest_hash": "1" * 63},
            {"schema_version": "npi.released_trial_summary.v2"},
            {"presentation_schema_version": "unapproved"},
            {"redaction_schema_version": "unapproved"},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                ReleasedSummaryProjectionContractError
            ):
                descriptor(**values)

    def test_configuration_is_only_disabled_contract_held(self) -> None:
        configuration = ReleasedSummaryProjectionConfiguration()
        self.assertEqual(
            configuration.state,
            ReleasedSummaryProjectionConfigurationState.DISABLED_CONTRACT_HELD,
        )
        for values in (
            {"enabled": True},
            {"enabled": 0},
            {"external_contract_approved": True},
            {"profile_reference": "unapproved-profile"},
        ):
            with self.subTest(values=values), self.assertRaises(
                ReleasedSummaryProjectionContractError
            ):
                ReleasedSummaryProjectionConfiguration(**values)

    def test_current_source_remains_separate_from_external_unavailable_truth(self) -> None:
        source = descriptor()
        result = ContractHeldReleasedSummaryProjectionAdapter().project(
            source,
            trace_id="trace-p808-current",
        )
        self.assertEqual(result.source_state, ReleasedSummarySourceState.CURRENT)
        self.assertEqual(
            result.external_projection_state,
            ExternalProjectionState.UNAVAILABLE,
        )
        self.assertEqual(
            result.unavailable_reason,
            UnavailableReason.EXTERNAL_CONTRACT_HELD,
        )
        self.assertEqual(
            result.safe_status(),
            {
                "sourceState": "current",
                "sourceFingerprint": source.fingerprint,
                "externalProjection": "unavailable",
                "unavailableReasonCode": "external_contract_held",
                "traceId": "trace-p808-current",
            },
        )

    def test_unavailable_and_conflict_are_closed_without_source_or_success(self) -> None:
        adapter = ContractHeldReleasedSummaryProjectionAdapter()
        unavailable = adapter.source_unavailable(trace_id="trace-p808-unavailable")
        conflict = adapter.source_conflict(trace_id="trace-p808-conflict")
        self.assertEqual(unavailable.source_state, ReleasedSummarySourceState.UNAVAILABLE)
        self.assertEqual(unavailable.unavailable_reason, UnavailableReason.SOURCE_UNAVAILABLE)
        self.assertEqual(conflict.source_state, ReleasedSummarySourceState.CONFLICT)
        self.assertEqual(conflict.unavailable_reason, UnavailableReason.SOURCE_CONFLICT)
        for result in (unavailable, conflict):
            self.assertIsNone(result.source)
            self.assertEqual(
                result.external_projection_state,
                ExternalProjectionState.UNAVAILABLE,
            )
            self.assertIsNone(result.safe_status()["sourceFingerprint"])

    def test_result_rejects_state_reason_source_and_trace_mismatch(self) -> None:
        base = {
            "source_state": ReleasedSummarySourceState.CURRENT,
            "external_projection_state": ExternalProjectionState.UNAVAILABLE,
            "unavailable_reason": UnavailableReason.EXTERNAL_CONTRACT_HELD,
            "trace_id": "trace-p808-valid",
            "source": descriptor(),
        }
        for values in (
            {"source": None},
            {"unavailable_reason": UnavailableReason.SOURCE_CONFLICT},
            {"trace_id": "https://private.invalid"},
            {"trace_id": "Bearer secret"},
            {
                "source_state": ReleasedSummarySourceState.UNAVAILABLE,
                "unavailable_reason": UnavailableReason.SOURCE_UNAVAILABLE,
            },
        ):
            with self.subTest(values=values), self.assertRaises(
                ReleasedSummaryProjectionContractError
            ):
                ReleasedSummaryProjectionResult(**(base | values))

    def test_checkpoint_one_has_no_frappe_network_persistence_or_event_import(self) -> None:
        modules = tuple(MODULE_ROOT.glob("*.py"))
        imported_roots: set[str] = set()
        combined = ""
        for path in modules:
            source = path.read_text(encoding="utf-8")
            combined += source
            for node in ast.walk(ast.parse(source, filename=str(path))):
                if isinstance(node, ast.Import):
                    imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue({"dataclasses", "enum", "typing", "uuid"} <= imported_roots)
        self.assertFalse(
            imported_roots
            & {"frappe", "httpx", "requests", "socket", "urllib", "redis", "rq"}
        )
        for forbidden in (
            ".insert(",
            ".save(",
            ".submit(",
            "enqueue(",
            "event_type",
            "base_url",
            "target_method",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
