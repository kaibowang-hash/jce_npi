from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp/frappe-bench"
SITE_NAME = os.environ.get("NPI_ERP_SENDER_RUNTIME_SITE", "")
FIXTURE_RUN_ID = os.environ.get("NPI_ERP_SENDER_RUNTIME_RUN_ID", "")
RUN_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_runtime() -> dict[str, object]:
    import frappe

    from npi_erpnext_connector import frappe_repository, worker
    from npi_erpnext_connector.config import (
        BASE_URL_KEY,
        DISABLED_KEY,
        PROJECT_ACCESS_KEY,
        PROJECT_MAP_KEY,
        ROLE_MAP_KEY,
        TTL_KEY,
    )
    from npi_erpnext_connector.transport import (
        DeliveryReceipt,
        RetryableDeliveryError,
    )

    require(
        "npi_erpnext_connector" in frappe.get_installed_apps(),
        "ERP authorization sender app is not installed",
    )
    require(
        frappe_repository.enqueue_user_authorization(
            f"pa07-disabled-{FIXTURE_RUN_ID}@example.invalid"
        )
        is None,
        "ERP authorization sender is not default disabled",
    )
    user_id = f"pa07-{FIXTURE_RUN_ID}@example.invalid"
    require(not frappe.db.exists("User", user_id), "PA-07 fixture User already exists")
    original_frappe_enqueue = frappe.enqueue
    frappe.enqueue = lambda *args, **kwargs: None
    try:
        frappe.get_doc(
            {
                "doctype": "User",
                "email": user_id,
                "first_name": "PA07",
                "last_name": "Runtime",
                "enabled": 1,
                "user_type": "System User",
                "send_welcome_email": 0,
                "roles": [{"role": "Desk User"}],
            }
        ).insert()
    finally:
        frappe.enqueue = original_frappe_enqueue

    frappe.conf[DISABLED_KEY] = False
    frappe.conf[BASE_URL_KEY] = "https://launchflow.invalid"
    frappe.conf[ROLE_MAP_KEY] = {"Desk User": "NPI Engineer"}
    frappe.conf[PROJECT_MAP_KEY] = {}
    frappe.conf[PROJECT_ACCESS_KEY] = {}
    frappe.conf[TTL_KEY] = 3600

    queued: list[str] = []
    original_enqueue = frappe_repository._enqueue_delivery
    original_recovery_enqueue = worker._enqueue_delivery
    original_deliver = worker.deliver
    frappe_repository._enqueue_delivery = queued.append
    receipts: list[str] = []

    def success(profile: object, event: object) -> DeliveryReceipt:
        del profile
        receipts.append(event.event_hash)
        return DeliveryReceipt(
            projection_hash="a" * 64,
            state="enabled" if event.event["enabled"] else "disabled",
            local_user_state="enabled" if event.event["enabled"] else "disabled",
            local_user_disposition=("created" if event.event["enabled"] else "disabled"),
            exact_replay=False,
        )

    try:
        worker.deliver = success
        first_id = frappe_repository.enqueue_user_authorization(user_id)
        require(first_id and queued == [first_id], "Initial delivery was not queued once")
        recovery_queued: list[str] = []
        worker._enqueue_delivery = recovery_queued.append
        worker.recover_pending_deliveries()
        require(
            recovery_queued == [first_id],
            "Recovery did not select the exact due delivery",
        )
        worker._enqueue_delivery = original_recovery_enqueue
        first_document = frappe.get_doc(frappe_repository.DOCTYPE, first_id)
        first_event_json = first_document.event_json
        worker.deliver_pending(first_id)
        delivered = frappe.get_doc(frappe_repository.DOCTYPE, first_id)
        require(
            delivered.status == "delivered"
            and int(delivered.source_version) == 1
            and int(delivered.attempt_count) == 1
            and delivered.response_projection_hash == "a" * 64,
            "Initial authorization delivery truth drifted",
        )

        reused_id = frappe_repository.enqueue_user_authorization(user_id)
        require(
            reused_id == first_id
            and frappe.db.count(
                frappe_repository.DOCTYPE,
                {"target_user_id": user_id},
            )
            == 1,
            "Unchanged current authorization was not reused",
        )

        frappe.db.set_value("User", user_id, "enabled", 0, update_modified=True)
        second_id = frappe_repository.enqueue_user_authorization(user_id)
        require(second_id and second_id != first_id, "Revocation delivery was not created")
        worker.deliver_pending(second_id)
        revoked = frappe.get_doc(frappe_repository.DOCTYPE, second_id)
        require(
            int(revoked.source_version) == 2
            and revoked.status == "delivered"
            and json.loads(revoked.event_json)["enabled"] is False
            and json.loads(revoked.event_json)["roles"] == [],
            "Disabled User did not produce a complete revocation",
        )

        frappe.db.set_value("User", user_id, "enabled", 1, update_modified=True)
        third_id = frappe_repository.enqueue_user_authorization(user_id)
        require(third_id and third_id != second_id, "Re-enable delivery was not created")

        def timeout_after_commit(profile: object, event: object) -> DeliveryReceipt:
            del profile
            receipts.append(event.event_hash)
            raise RetryableDeliveryError("NETWORK_OR_TIMEOUT")

        worker.deliver = timeout_after_commit
        worker.deliver_pending(third_id)
        retry = frappe.get_doc(frappe_repository.DOCTYPE, third_id)
        retry_event_json = retry.event_json
        require(
            retry.status == "retry"
            and int(retry.attempt_count) == 1
            and retry.last_error_code == "NETWORK_OR_TIMEOUT",
            "Timeout did not retain a retryable delivery",
        )
        retry.next_attempt_at = None
        worker._save(retry)
        worker.deliver = success
        worker.deliver_pending(third_id)
        recovered = frappe.get_doc(frappe_repository.DOCTYPE, third_id)
        require(
            recovered.status == "delivered"
            and int(recovered.attempt_count) == 2
            and recovered.event_json == retry_event_json
            and first_event_json != retry_event_json
            and receipts[-1] == receipts[-2],
            "Timeout recovery did not replay the exact immutable event",
        )
        frappe.db.set_value(
            "User",
            user_id,
            "user_type",
            "Website User",
            update_modified=True,
        )
        require(
            user_id in frappe_repository.list_reconciliation_users(),
            "Historical projected identity disappeared from reconciliation",
        )
    finally:
        frappe_repository._enqueue_delivery = original_enqueue
        worker._enqueue_delivery = original_recovery_enqueue
        worker.deliver = original_deliver

    delivery_count = frappe.db.count(
        frappe_repository.DOCTYPE,
        {"target_user_id": user_id},
    )
    evidence = {
        "defaultDisabled": True,
        "deliveryCount": delivery_count,
        "exactCurrentReuse": reused_id == first_id,
        "historicalIdentityReconciled": True,
        "recoverySelectedDue": recovery_queued == [first_id],
        "revocationDelivered": revoked.status == "delivered",
        "runtimeTransportContact": False,
        "timeoutExactReplay": recovered.event_json == retry_event_json,
    }
    return {
        **evidence,
        "evidenceChecksum": hashlib.sha256(
            json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest(),
    }


def run_bench_fixture() -> None:
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = verify_runtime()
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    finally:
        frappe.db.rollback()
        frappe.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-fixture", action="store_true")
    arguments = parser.parse_args()
    require(SITE_NAME == "pa07.localhost", "PA-07 runtime Site is not disposable")
    require(
        RUN_ID_PATTERN.fullmatch(FIXTURE_RUN_ID) is not None,
        "PA-07 runtime namespace is invalid",
    )
    require(arguments.bench_fixture, "PA-07 verifier requires the Bench fixture mode")
    run_bench_fixture()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
