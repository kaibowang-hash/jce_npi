from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.engineering_change.adapters import (  # noqa: E402
    AdapterRegistration,
    AdapterRegistry,
    command_for,
)
from npi_integration.engineering_change.config import IntegrationProfile  # noqa: E402
from npi_integration.engineering_change.domain import (  # noqa: E402
    AdapterResponse,
    ChangeImplementationSummary,
    EngineeringChangeInboundEvent,
    EngineeringChangeIntegrationError,
    FaultKind,
    FormalChangeObservation,
    RetryDirective,
    SummaryRequest,
    SummaryState,
    TargetMode,
    canonical_hash,
    classify_adapter_response,
    parse_inbound_event,
    uncertain_result,
)


NOW = datetime(2026, 8, 31, 4, 5, 6, tzinfo=UTC)
PROJECT = UUID("00000000-0000-5000-8000-000000009101")
CHANGE = UUID("00000000-0000-4000-8000-000000009102")
REVISION = UUID("00000000-0000-4000-8000-000000009103")


def formal() -> FormalChangeObservation:
    return FormalChangeObservation(
        document_name="ECR-00042",
        raw_status="Open",
        source_version="17",
        source_modified_at=NOW,
        source_hash="a" * 64,
        observed_at=NOW,
    )


def inbound_event() -> EngineeringChangeInboundEvent:
    values = {
        "tenant_id": "tenant-p901",
        "project_global_id": PROJECT,
        "change_global_id": CHANGE,
        "observation": formal(),
    }
    return EngineeringChangeInboundEvent(
        event_id=UUID("00000000-0000-4000-8000-000000009104"),
        occurred_at=NOW,
        global_id=UUID("00000000-0000-4000-8000-000000009105"),
        source_object_id="ECR-00042",
        object_version=17,
        correlation_id=UUID("00000000-0000-4000-8000-000000009106"),
        trace_id="trace-p901-domain",
        actor_id="erp.integration@example.invalid",
        payload_hash=canonical_hash(
            {
                "tenantId": values["tenant_id"],
                "projectGlobalId": str(PROJECT),
                "changeGlobalId": str(CHANGE),
                "formalChange": values["observation"].payload(),
            }
        ),
        **values,
    )


def profile(mode: TargetMode = TargetMode.SYNTHETIC) -> IntegrationProfile:
    if mode is TargetMode.DISABLED:
        return IntegrationProfile(
            profile_id="p901-disabled",
            profile_version=1,
            tenant_id="tenant-p901",
            project_global_id=str(PROJECT),
            target_mode=mode,
            requester_user_ids=("operator@example.invalid",),
            service_actor_user_id="service@example.invalid",
        )
    return IntegrationProfile(
        profile_id="p901-synthetic",
        profile_version=2,
        tenant_id="tenant-p901",
        project_global_id=str(PROJECT),
        target_mode=mode,
        requester_user_ids=("operator@example.invalid",),
        service_actor_user_id="service@example.invalid",
        signing_key_ids=("key-2026-08",),
        adapter_resolver="npi_integration.engineering_change.runtime_fixture.synthetic_adapter",
        disposable_runtime_marker=True,
    )


def summary_request() -> SummaryRequest:
    summary = ChangeImplementationSummary(
        tenant_id="tenant-p901",
        project_global_id=PROJECT,
        change_global_id=CHANGE,
        revision_global_id=REVISION,
        revision_number=4,
        revision_snapshot_hash="b" * 64,
        formal_change=formal(),
        affected_versions_hash="c" * 64,
        effectivity_hash="d" * 64,
        disposition_hash="e" * 64,
        revalidation_hash="f" * 64,
        closure_evidence_hash="1" * 64,
    )
    return SummaryRequest(
        global_id=UUID("00000000-0000-4000-8000-000000009107"),
        summary=summary,
        profile=profile().reference,
        actor_user_id="operator@example.invalid",
        service_actor_user_id="service@example.invalid",
        request_id=UUID("00000000-0000-4000-8000-000000009108"),
        trace_id="trace-p901-summary",
        idempotency_key_hash="2" * 64,
        created_at=NOW,
    )


class Phase9ChangeIntegrationDomainTest(unittest.TestCase):
    def test_inbound_envelope_round_trips_and_rejects_shape_identity_or_duplicate_keys(self) -> None:
        event = inbound_event()
        encoded = json.dumps(
            event.envelope(), separators=(",", ":"), sort_keys=True
        ).encode()
        self.assertEqual(parse_inbound_event(encoded), event)
        changed = event.envelope()
        changed["payload"]["unexpected"] = True
        with self.assertRaises(EngineeringChangeIntegrationError):
            parse_inbound_event(json.dumps(changed).encode())
        with self.assertRaises(EngineeringChangeIntegrationError):
            parse_inbound_event(b'{"event_id":"one","event_id":"two"}')
        with self.assertRaises(EngineeringChangeIntegrationError):
            replace(event, payload_hash="3" * 64)

    def test_profiles_are_exact_default_disabled_and_synthetic_is_disposable_only(self) -> None:
        disabled = profile(TargetMode.DISABLED)
        self.assertEqual(disabled.snapshot["allowedOperations"], [])
        self.assertFalse(disabled.permits("wrong@example.invalid"))
        synthetic = profile()
        self.assertEqual(
            synthetic.snapshot["allowedOperations"],
            ["record_change_implementation_summary"],
        )
        self.assertTrue(synthetic.permits("OPERATOR@example.invalid"))
        for mutation in (
            {"disposable_runtime_marker": False},
            {"base_url": "https://production.example.invalid"},
            {"requester_user_ids": ("Administrator",)},
        ):
            values = synthetic.__dict__ if hasattr(synthetic, "__dict__") else {
                field: getattr(synthetic, field)
                for field in synthetic.__dataclass_fields__
            }
            with self.subTest(mutation=mutation), self.assertRaises(
                EngineeringChangeIntegrationError
            ):
                IntegrationProfile(**{**values, **mutation})

    def test_adapter_classification_closes_normal_fault_partial_and_uncertain_boundaries(self) -> None:
        cases = (
            (AdapterResponse(200, "1" * 64, True, True), SummaryState.SUCCEEDED, FaultKind.NONE, RetryDirective.NONE),
            (AdapterResponse(429, "2" * 64, True, True, retry_after_seconds=30), SummaryState.FAILED_RETRYABLE, FaultKind.RATE_LIMITED, RetryDirective.RETRY_AFTER),
            (AdapterResponse(503, "3" * 64, True, True), SummaryState.FAILED_RETRYABLE, FaultKind.TARGET_SERVER_ERROR, RetryDirective.RETRY_SAME_IDEMPOTENCY),
            (AdapterResponse(200, "4" * 64, True, True, partial=True), SummaryState.PARTIALLY_SUCCEEDED, FaultKind.PARTIAL_RESULT, RetryDirective.RECONCILE_BEFORE_RETRY),
            (AdapterResponse(409, "5" * 64, True, True), SummaryState.IDENTITY_CONFLICT, FaultKind.IDENTITY_CONFLICT, RetryDirective.MANUAL_CORRECTION),
            (AdapterResponse(200, "6" * 64, False, True), SummaryState.FAILED_FINAL, FaultKind.RESPONSE_AUTHENTICATION_INVALID, RetryDirective.MANUAL_CORRECTION),
            (AdapterResponse(200, "7" * 64, True, False), SummaryState.FAILED_FINAL, FaultKind.RESPONSE_CONTRACT_INVALID, RetryDirective.MANUAL_CORRECTION),
        )
        for response, state, fault, retry in cases:
            with self.subTest(state=state):
                result = classify_adapter_response(response, observed_at=NOW)
                self.assertEqual((result.state, result.fault, result.retry), (state, fault, retry))
                self.assertEqual(
                    (result.response_authenticated, result.response_contract_valid),
                    (response.authenticated, response.contract_valid),
                )
        uncertain = uncertain_result(response_hash="8" * 64, observed_at=NOW)
        self.assertEqual(uncertain.state, SummaryState.UNCERTAIN_AFTER_TIMEOUT)
        self.assertEqual(uncertain.retry, RetryDirective.RECONCILE_BEFORE_RETRY)
        self.assertFalse(uncertain.response_authenticated)
        self.assertFalse(uncertain.response_contract_valid)

    def test_summary_command_is_source_bound_and_registry_is_operation_specific(self) -> None:
        request = summary_request()
        adapter = lambda _command: AdapterResponse(200, "9" * 64, True, True)
        registry = AdapterRegistry(
            (
                AdapterRegistration(
                    request.profile.profile_id.replace("p901-synthetic", "npi_integration.engineering_change.runtime_fixture.synthetic_adapter"),
                    TargetMode.SYNTHETIC,
                    "record_change_implementation_summary",
                    adapter,
                ),
            )
        )
        command = command_for(
            request,
            attempt_global_id=UUID("00000000-0000-4000-8000-000000009109"),
            attempt_number=1,
        )
        self.assertEqual(command.source_hash, request.summary.source_hash)
        self.assertEqual(command.payload["source_hash"], command.source_hash)
        self.assertIs(registry.resolve(profile()), adapter)
        self.assertIsNone(registry.resolve(profile(TargetMode.DISABLED)))


if __name__ == "__main__":
    unittest.main()
