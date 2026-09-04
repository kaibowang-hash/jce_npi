from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = "npi.localhost"
TENANT_ID = "runtime-tenant"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_controller_lifecycle() -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.grid_personalization.domain import (
        GridFilterSnapshot,
        GridLayout,
        PersonalGridPreference,
        PublicationAuthorityDecision,
        PublishedGridViewDefinition,
        PublishedGridViewRevision,
        PublishedGridViewRoot,
        rollback_as_new_revision,
    )
    from npi_core.grid_personalization.frappe_repository import (
        FrappeGridPersonalizationRepository,
        FrappePublishedGridViewRepository,
    )

    actor = "Administrator"
    project_id = uuid4()
    published_view_id = uuid4()
    started_at = datetime.now(UTC).replace(microsecond=0)
    authority = PublicationAuthorityDecision(
        allowed=True,
        reason_code="runtime_fixture_authorized",
        evidence={"fixture": "r1-04-controller-rollback"},
    )
    principal = Principal(
        user_id=actor,
        roles=frozenset({"System Manager"}),
        tenant_id=TENANT_ID,
    )
    personal_tenant_id = f"{TENANT_ID}-controller-{uuid4().hex[:8]}"
    personal_request_id = uuid4()
    personal_trace_id = f"trace-r104-controller-{uuid4().hex}"
    personal_repository = FrappeGridPersonalizationRepository(
        principal=Principal(
            user_id=actor,
            roles=frozenset({"System Manager"}),
            tenant_id=personal_tenant_id,
        ),
        request_id=str(personal_request_id),
        trace_id=personal_trace_id,
        accessible_project_loader=lambda: frozenset({project_id}),
        clock=lambda: started_at,
    )
    personal_preference = PersonalGridPreference.default().update(
        view_id="all",
        layout=GridLayout.default().canonical_dict(),
        filter_snapshot={
            "projectId": None,
            "priority": None,
            "search": "runtime",
        },
        save_filter=True,
        favorite_view_ids=["all"],
        recent_view_ids=["all"],
        default_project_id=None,
    )
    personal_repository.save(
        personal_preference,
        expected_version=0,
        changed_view_id="all",
    )
    personal_name = frappe.db.get_value(
        "NPI My Work Grid Preference",
        {"preference_key_hash": personal_repository.key_hash},
        "name",
    )
    require(
        isinstance(personal_name, str),
        "Personal grid controller did not persist its exact fixture",
    )
    personal_document = frappe.get_doc(
        "NPI My Work Grid Preference",
        personal_name,
    )
    require(
        int(personal_document.optimistic_version) == 1
        and isinstance(personal_document.last_changed_at, datetime),
        "Personal grid controller validation did not preserve its exact state",
    )
    frappe.db.set_value(
        "NPI My Work Grid Preference",
        personal_name,
        "optimistic_version",
        0,
        update_modified=False,
    )
    corrupt_load = personal_repository.load()
    require(
        corrupt_load.source == "default"
        and corrupt_load.reason_code == "stored_preference_invalid"
        and corrupt_load.preference.version == 0,
        "Personal grid controller did not fail safely on a corrupt version",
    )
    personal_repository.save(
        personal_preference,
        expected_version=0,
        changed_view_id="all",
    )
    repaired_load = personal_repository.load()
    require(
        repaired_load.source == "stored"
        and repaired_load.preference == personal_preference,
        "Personal grid controller did not repair a corrupt version safely",
    )
    personal_document = frappe.get_doc(
        "NPI My Work Grid Preference",
        personal_name,
    )

    def definition(search: str) -> PublishedGridViewDefinition:
        return PublishedGridViewDefinition(
            view_id="all",
            layout=GridLayout.default(),
            filter=GridFilterSnapshot(
                project_id=project_id,
                priority=None,
                search=search,
            ),
        )

    first_request_id = uuid4()
    first_trace_id = f"trace-r104-controller-{uuid4().hex}"
    first = PublishedGridViewRevision.create(
        global_id=uuid4(),
        published_view_global_id=published_view_id,
        tenant_id=TENANT_ID,
        project_global_id=project_id,
        revision_number=1,
        prior_revision=None,
        restored_from_revision=None,
        name="Runtime My Work view",
        description="First controlled runtime revision",
        definition=definition("first"),
        published_by=actor,
        published_at=started_at,
        authority=authority,
        request_id=first_request_id,
        trace_id=first_trace_id,
    )
    first_root = PublishedGridViewRoot.from_first_revision(first)
    FrappePublishedGridViewRepository(
        principal=principal,
        request_id=str(first_request_id),
        trace_id=first_trace_id,
    ).persist_first(root=first_root, revision=first)

    second_request_id = uuid4()
    second_trace_id = f"trace-r104-controller-{uuid4().hex}"
    second = PublishedGridViewRevision.create(
        global_id=uuid4(),
        published_view_global_id=published_view_id,
        tenant_id=TENANT_ID,
        project_global_id=project_id,
        revision_number=2,
        prior_revision=first.reference,
        restored_from_revision=None,
        name="Runtime My Work view v2",
        description="Second controlled runtime revision",
        definition=definition("second"),
        published_by=actor,
        published_at=started_at + timedelta(seconds=1),
        authority=authority,
        request_id=second_request_id,
        trace_id=second_trace_id,
    )
    second_root = first_root.advance(second)
    FrappePublishedGridViewRepository(
        principal=principal,
        request_id=str(second_request_id),
        trace_id=second_trace_id,
    ).append(
        root=second_root,
        revision=second,
        expected_version=1,
    )

    rollback_request_id = uuid4()
    rollback_trace_id = f"trace-r104-controller-{uuid4().hex}"
    restored = rollback_as_new_revision(
        root=second_root,
        current_revision=second,
        target_revision=first,
        published_by=actor,
        published_at=started_at + timedelta(seconds=2),
        authority=authority,
        request_id=rollback_request_id,
        trace_id=rollback_trace_id,
    )
    restored_root = second_root.advance(restored)
    FrappePublishedGridViewRepository(
        principal=principal,
        request_id=str(rollback_request_id),
        trace_id=rollback_trace_id,
    ).append(
        root=restored_root,
        revision=restored,
        expected_version=2,
    )

    root = frappe.get_doc("NPI Published Grid View", str(published_view_id))
    require(
        int(root.optimistic_version) == 3
        and int(root.current_revision_number) == 3
        and isinstance(root.created_at, datetime),
        "Published grid root did not survive real controller append validation",
    )
    revision = frappe.get_doc(
        "NPI Published Grid View Revision",
        restored.revision_key,
    )
    require(
        revision.restored_from_revision_global_id == str(first.global_id)
        and int(revision.restored_from_revision_number) == 1
        and revision.snapshot_hash == restored.snapshot_hash
        and isinstance(revision.published_at, datetime),
        "Published rollback revision did not preserve exact controller lineage",
    )

    denied_actions = 0

    def require_denied(action: Callable[[], object]) -> None:
        nonlocal denied_actions
        try:
            action()
        except (frappe.PermissionError, frappe.ValidationError):
            denied_actions += 1
            return
        raise RuntimeError("A generic grid personalization mutation was not denied")

    personal_document.optimistic_version = 99
    require_denied(personal_document.save)
    require_denied(
        lambda: frappe.get_doc(
            "NPI My Work Grid Preference",
            personal_name,
        ).delete()
    )
    root.optimistic_version = 99
    require_denied(root.save)
    require_denied(
        lambda: frappe.get_doc(
            "NPI Published Grid View",
            str(published_view_id),
        ).delete()
    )
    revision.description = "Unauthorized mutation"
    require_denied(revision.save)
    require_denied(
        lambda: frappe.get_doc(
            "NPI Published Grid View Revision",
            restored.revision_key,
        ).delete()
    )
    require(
        denied_actions == 6,
        "Grid personalization controller mutation denials drifted",
    )
    require(
        frappe.db.count(
            "NPI My Work Grid Preference",
            {"preference_key_hash": personal_repository.key_hash},
        )
        == 1
        and frappe.db.count(
            "NPI Published Grid View",
            {"global_id": str(published_view_id)},
        )
        == 1
        and frappe.db.count(
            "NPI Published Grid View Revision",
            {"published_view_global_id": str(published_view_id)},
        )
        == 3,
        "Published grid controller fixture did not stage exact history",
    )
    return {
        "controllerMutationDenials": denied_actions,
        "corruptVersionRepair": True,
        "personalPreferenceId": str(personal_document.global_id),
        "publishedRevisions": 3,
        "rollbackAsNewRevision": True,
        "timestampCoercion": True,
        "viewId": str(published_view_id),
    }


def main() -> None:
    expected_bench = ROOT / "tmp" / "frappe-bench"
    require(
        BENCH_PATH == expected_bench
        and BENCH_PATH.is_dir()
        and not BENCH_PATH.is_symlink()
        and BENCH_PATH.resolve(strict=True) == expected_bench,
        "Grid controller runtime verification requires the fixed local Bench",
    )

    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    result: dict[str, object] | None = None
    try:
        require(
            frappe.conf.get("npi_runtime_disposable_marker")
            == "npi-one-local-runtime-disposable-v1"
            and frappe.conf.get("npi_tenant_id") == TENANT_ID,
            "Grid controller runtime verification requires the disposable Site",
        )
        frappe.set_user("Administrator")
        result = verify_controller_lifecycle()
        frappe.db.rollback()
        require(
            not frappe.db.exists(
                "NPI My Work Grid Preference",
                {"global_id": result["personalPreferenceId"]},
            )
            and not frappe.db.exists(
                "NPI Published Grid View",
                {"global_id": result["viewId"]},
            )
            and not frappe.db.exists(
                "NPI Published Grid View Revision",
                {"published_view_global_id": result["viewId"]},
            ),
            "Grid controller runtime rollback left fixture records",
        )
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()
    require(result is not None, "Grid controller runtime result is missing")
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    print("local Frappe grid controller runtime verification passed")


if __name__ == "__main__":
    main()
