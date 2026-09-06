from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
NPI_APP = ROOT / "apps/npi_integration"
for path in (ERP_APP, NPI_APP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from npi_erpnext_connector.project_config import (  # noqa: E402
    SIGNING_SECRET_ENV,
    STATUS_TOKEN_ENV,
    load_project_sender_profile,
)
from npi_erpnext_connector.project_domain import (  # noqa: E402
    SourceProject,
    build_project_source_event,
    canonical_json,
)
from npi_erpnext_connector.project_transport import (  # noqa: E402
    get_project_receipt_status,
    submit_project_event,
)
from npi_integration.inbound_project.domain import (  # noqa: E402
    ProjectSourceObjectType,
    parse_project_source_event,
)
from npi_integration.inbound_project.signature import (  # noqa: E402
    SignatureHeaders,
    verify_request_signature,
)


NOW = datetime(2026, 9, 6, 1, 2, 3, tzinfo=UTC)
SECRET = "project-signing-secret-material-000000000001"
TOKEN = "token api-key:api-secret"


def configuration(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "npi_erp_project_sender_disabled": False,
        "npi_erp_project_target_base_url": "https://launchflow.example.invalid",
        "npi_erp_project_target_environment": "test",
        "npi_erp_project_service_actor_id": "erpnext-test-project-sender",
        "npi_erp_project_signing_key_id": "erpnext-test-project-v1",
    }
    values.update(changes)
    return values


def source() -> SourceProject:
    return SourceProject(
        source_project_id="PROJ-0027",
        title="Transparent Window Rev.B Industrialisation",
        status="Open",
        target_sop=date(2026, 9, 18),
        source_modified_at=NOW,
        source_owner_user_id="kaibo_wang@whjichen.cn",
    )


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self.body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.closed = False

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.body

    def close(self) -> None:
        self.closed = True


class ProjectSession:
    def __init__(self, project_global_id: UUID) -> None:
        self.project_global_id = project_global_id
        self.post_call: dict[str, object] | None = None
        self.get_call: dict[str, object] | None = None

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.post_call = {"url": url, **kwargs}
        event = json.loads(bytes(kwargs["data"]).decode("utf-8"))
        headers = kwargs["headers"]
        return FakeResponse(
            202,
            {
                "receiptId": str(UUID(int=701)),
                "eventId": event["event_id"],
                "state": "pending",
                "exactDuplicate": False,
                "requestId": headers["X-Request-ID"],
                "traceId": event["trace_id"],
            },
        )

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.get_call = {"url": url, **kwargs}
        return FakeResponse(
            200,
            {
                "receiptId": str(UUID(int=701)),
                "eventId": str(UUID(int=702)),
                "state": "succeeded",
                "terminal": True,
                "disposition": "project_created",
                "projectGlobalId": str(self.project_global_id),
                "errorCode": None,
                "traceId": "erp-project-00000000000000000000000000000000",
            },
        )


class ERPNextProjectConnectorTest(unittest.TestCase):
    def test_builds_receiver_compatible_project_created_event(self) -> None:
        first = build_project_source_event(
            source(),
            source_version=1,
            occurred_at=NOW,
            service_actor_id="erpnext-test-project-sender",
        )
        second = build_project_source_event(
            source(),
            source_version=1,
            occurred_at=NOW,
            service_actor_id="erpnext-test-project-sender",
        )
        self.assertEqual(first, second)
        parsed = parse_project_source_event(canonical_json(first.event).encode("utf-8"))
        self.assertEqual(parsed.object_type, ProjectSourceObjectType.PROJECT)
        self.assertEqual(parsed.source_object_id, "PROJ-0027")
        self.assertEqual(
            parsed.payload.source_owner_user_id,
            "kaibo_wang@whjichen.cn",
        )

    def test_transport_signature_and_result_poll_are_exactly_bound(self) -> None:
        profile = load_project_sender_profile(configuration())
        event = build_project_source_event(
            source(),
            source_version=1,
            occurred_at=NOW,
            service_actor_id=profile.service_actor_id,
        )
        project_global_id = UUID(int=703)
        session = ProjectSession(project_global_id)
        accepted = submit_project_event(
            profile,
            event,
            session=session,
            environment={SIGNING_SECRET_ENV: SECRET},
            clock=lambda: NOW.timestamp(),
        )
        self.assertEqual(accepted.receipt_id, UUID(int=701))
        assert session.post_call is not None
        headers = session.post_call["headers"]
        verify_request_signature(
            secret=SECRET.encode("utf-8"),
            method="POST",
            path="/api/npi/v1/integration/erpnext/project-source-events",
            headers=SignatureHeaders(
                request_id=headers["X-Request-ID"],
                key_id=headers["X-NPI-Key-ID"],
                timestamp=headers["X-NPI-Timestamp"],
                signature=headers["X-NPI-Signature"],
            ),
            raw_body=session.post_call["data"],
            now=NOW,
        )
        status = get_project_receipt_status(
            profile,
            accepted.receipt_id,
            session=session,
            environment={STATUS_TOKEN_ENV: TOKEN},
        )
        self.assertEqual(status.project_global_id, project_global_id)
        assert session.get_call is not None
        self.assertEqual(
            session.get_call["headers"]["Authorization"],
            TOKEN,
        )

    def test_profile_rejects_production_and_implicit_enablement(self) -> None:
        with self.assertRaisesRegex(ValueError, "disabled"):
            load_project_sender_profile(
                configuration(npi_erp_project_sender_disabled=True)
            )
        with self.assertRaisesRegex(ValueError, "non-production"):
            load_project_sender_profile(
                configuration(npi_erp_project_target_environment="production")
            )


if __name__ == "__main__":
    unittest.main()
