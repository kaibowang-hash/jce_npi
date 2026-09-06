from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import frappe

from npi_core.foundation.errors import PermissionDenied, VersionConflict
from npi_core.foundation.security import Principal
from npi_core.grid_personalization.controller import PersonalPreferenceLoad
from npi_core.grid_personalization.domain import (
    GRID_ID,
    PROJECT_PERMISSION_BOUNDARY,
    TABLE_SCHEMA_VERSION,
    VIEW_IDS,
    GridPersonalizationValidationError,
    PersonalGridPreference,
    PublishedGridViewRevision,
    PublishedGridViewRoot,
    PublishedRevisionReference,
    canonical_hash,
    canonical_json,
    preference_key,
)
from npi_core.my_work.domain import MyWorkView


_PREFERENCE_DOCTYPE = "NPI My Work Grid Preference"
_PUBLISHED_VIEW_DOCTYPE = "NPI Published Grid View"
_PUBLISHED_REVISION_DOCTYPE = "NPI Published Grid View Revision"
_WRITE_FLAG = "npi_grid_personalization_write"
_REVISION_SNAPSHOT_FIELDS = frozenset(
    {
        "schemaVersion",
        "globalId",
        "publishedViewId",
        "tenantId",
        "projectId",
        "gridId",
        "tableSchemaVersion",
        "revisionNumber",
        "priorRevision",
        "restoredFromRevision",
        "name",
        "description",
        "permissionBoundary",
        "definition",
        "definitionHash",
        "publishedBy",
        "publishedAt",
        "authorityReasonCode",
        "authorityEvidence",
        "requestId",
        "traceId",
    }
)


class GridPreferenceStore(Protocol):
    def find(self, key_hash: str, *, for_update: bool) -> object | None: ...

    def has_obsolete(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
    ) -> bool: ...

    def create(self, values: Mapping[str, object]) -> object: ...


class FrappeGridPreferenceStore:
    def find(self, key_hash: str, *, for_update: bool) -> object | None:
        name = frappe.db.get_value(
            _PREFERENCE_DOCTYPE,
            {"preference_key_hash": key_hash},
            "name",
            for_update=for_update,
        )
        return None if name is None else frappe.get_doc(_PREFERENCE_DOCTYPE, name)

    def has_obsolete(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
    ) -> bool:
        name = frappe.db.get_value(
            _PREFERENCE_DOCTYPE,
            {
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "grid_id": GRID_ID,
                "table_schema_version": ["!=", TABLE_SCHEMA_VERSION],
            },
            "name",
        )
        return name is not None

    def create(self, values: Mapping[str, object]) -> object:
        return frappe.get_doc({"doctype": _PREFERENCE_DOCTYPE, **dict(values)})


class PublishedGridViewStore(Protocol):
    def find_root(self, global_id: UUID, *, for_update: bool) -> object | None: ...

    def find_revision(
        self,
        published_view_global_id: UUID,
        revision_number: int,
    ) -> object | None: ...

    def create_root(self, values: Mapping[str, object]) -> object: ...

    def create_revision(self, values: Mapping[str, object]) -> object: ...


class FrappePublishedGridViewStore:
    def find_root(self, global_id: UUID, *, for_update: bool) -> object | None:
        name = frappe.db.get_value(
            _PUBLISHED_VIEW_DOCTYPE,
            {"global_id": str(global_id)},
            "name",
            for_update=for_update,
        )
        return (
            None
            if name is None
            else frappe.get_doc(_PUBLISHED_VIEW_DOCTYPE, name)
        )

    def find_revision(
        self,
        published_view_global_id: UUID,
        revision_number: int,
    ) -> object | None:
        revision_key = f"{published_view_global_id}:{revision_number}"
        name = frappe.db.get_value(
            _PUBLISHED_REVISION_DOCTYPE,
            {"revision_key": revision_key},
            "name",
        )
        return (
            None
            if name is None
            else frappe.get_doc(_PUBLISHED_REVISION_DOCTYPE, name)
        )

    def create_root(self, values: Mapping[str, object]) -> object:
        return frappe.get_doc(
            {"doctype": _PUBLISHED_VIEW_DOCTYPE, **dict(values)}
        )

    def create_revision(self, values: Mapping[str, object]) -> object:
        return frappe.get_doc(
            {"doctype": _PUBLISHED_REVISION_DOCTYPE, **dict(values)}
        )


class FrappeGridPersonalizationRepository:
    """Persist one fixed My Work preference for the authenticated Site actor."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        store: GridPreferenceStore | None = None,
        accessible_project_loader: Callable[[], frozenset[UUID]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if (
            principal.is_external
            or not principal.user_id
            or principal.user_id == "Guest"
            or not principal.tenant_id
        ):
            raise PermissionDenied()
        parsed_request_id = _canonical_uuid(request_id)
        self.principal = principal
        self.actor = principal.user_id
        self.tenant_id = principal.tenant_id
        self.request_id = str(parsed_request_id)
        self.trace_id = trace_id
        self.store = store or FrappeGridPreferenceStore()
        self.clock = clock or (lambda: datetime.now(UTC))
        self._accessible_project_loader = (
            accessible_project_loader or self._load_accessible_project_ids
        )
        self.key_hash = preference_key(self.tenant_id, self.actor)

    def load(self) -> PersonalPreferenceLoad:
        document = self.store.find(self.key_hash, for_update=False)
        if document is None:
            obsolete = self.store.has_obsolete(
                tenant_id=self.tenant_id,
                actor_user_id=self.actor,
            )
            if type(obsolete) is not bool:
                raise RuntimeError(
                    "The obsolete grid preference lookup is invalid."
                )
            return PersonalPreferenceLoad(
                preference=PersonalGridPreference.default(),
                source="default",
                reason_code=(
                    "stored_preference_invalid" if obsolete else None
                ),
            )
        self._assert_identity(document)
        fallback_version = 0
        try:
            version = _stored_version(_value(document, "optimistic_version"))
            fallback_version = version
            snapshot = _json_value(_value(document, "preference_snapshot"))
            preference = PersonalGridPreference.from_storage(
                version=version,
                value=snapshot,
            )
            supplied_hash = _value(document, "snapshot_hash")
            if supplied_hash != canonical_hash(preference.storage_dict()):
                raise GridPersonalizationValidationError(
                    "snapshotHash",
                    "The stored preference snapshot is invalid.",
                )
        except (
            GridPersonalizationValidationError,
            RuntimeError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return PersonalPreferenceLoad(
                preference=PersonalGridPreference.default(
                    version=fallback_version
                ),
                source="default",
                reason_code="stored_preference_invalid",
            )
        return PersonalPreferenceLoad(preference=preference, source="stored")

    def accessible_project_ids(self) -> frozenset[UUID]:
        values = self._accessible_project_loader()
        if not isinstance(values, frozenset) or any(
            not isinstance(value, UUID) or value.int == 0 for value in values
        ):
            raise RuntimeError("The My Work Project access projection is invalid.")
        return values

    def save(
        self,
        preference: PersonalGridPreference,
        *,
        expected_version: int,
        changed_view_id: str,
    ) -> PersonalGridPreference:
        if (
            changed_view_id not in VIEW_IDS
            or preference.version != expected_version + 1
        ):
            raise RuntimeError("The personal grid preference command is inconsistent.")
        document = self.store.find(self.key_hash, for_update=True)
        if expected_version == 0:
            if document is None:
                document = self.store.create(
                    self._document_values(preference, global_id=uuid4())
                )
                try:
                    with _controlled_write():
                        document.insert()
                except frappe.DuplicateEntryError as error:
                    raise VersionConflict() from error
            else:
                self._assert_identity(document)
                try:
                    _stored_version(_value(document, "optimistic_version"))
                except RuntimeError:
                    for fieldname, value in self._document_values(
                        preference,
                        global_id=_canonical_uuid(
                            _value(document, "global_id")
                        ),
                    ).items():
                        document.set(fieldname, value)
                    with _controlled_write():
                        document.save()
                else:
                    raise VersionConflict()
        else:
            if document is None:
                raise VersionConflict()
            self._assert_identity(document)
            if _stored_version(_value(document, "optimistic_version")) != (
                expected_version
            ):
                raise VersionConflict()
            for fieldname, value in self._document_values(
                preference,
                global_id=_canonical_uuid(_value(document, "global_id")),
            ).items():
                document.set(fieldname, value)
            with _controlled_write():
                document.save()
        return preference

    def _document_values(
        self,
        preference: PersonalGridPreference,
        *,
        global_id: UUID,
    ) -> dict[str, object]:
        snapshot = preference.storage_dict()
        changed_at = self.clock()
        if (
            not isinstance(changed_at, datetime)
            or changed_at.tzinfo is None
            or changed_at.utcoffset() is None
        ):
            raise RuntimeError("The personal grid preference clock is invalid.")
        return {
            "global_id": str(global_id),
            "preference_key_hash": self.key_hash,
            "tenant_id": self.tenant_id,
            "actor_user_id": self.actor,
            "grid_id": GRID_ID,
            "table_schema_version": TABLE_SCHEMA_VERSION,
            "optimistic_version": preference.version,
            "preference_snapshot": canonical_json(snapshot),
            "snapshot_hash": canonical_hash(snapshot),
            "last_changed_by": self.actor,
            "last_changed_at": changed_at.astimezone(UTC),
            "request_id": self.request_id,
            "trace_id": self.trace_id,
        }

    def _assert_identity(self, document: object) -> None:
        if (
            _value(document, "preference_key_hash") != self.key_hash
            or _value(document, "tenant_id") != self.tenant_id
            or _value(document, "actor_user_id") != self.actor
            or _value(document, "grid_id") != GRID_ID
            or _value(document, "table_schema_version") != TABLE_SCHEMA_VERSION
        ):
            raise RuntimeError("The stored personal grid preference identity is invalid.")

    def _load_accessible_project_ids(self) -> frozenset[UUID]:
        from npi_core.my_work.frappe_repository import FrappeMyWorkRepository

        response = FrappeMyWorkRepository(
            principal=self.principal,
            request_id=self.request_id,
            trace_id=self.trace_id,
        ).query(
            view=MyWorkView.ALL,
            project_global_id=None,
            priority=None,
            search=None,
            cursor=None,
            limit=1,
        )
        options = response.get("projectOptions")
        if not isinstance(options, list):
            raise RuntimeError("The My Work Project options are invalid.")
        project_ids: set[UUID] = set()
        for option in options:
            if not isinstance(option, Mapping):
                raise RuntimeError("The My Work Project option is invalid.")
            project_ids.add(_canonical_uuid(option.get("globalId")))
        return frozenset(project_ids)


class FrappePublishedGridViewRepository:
    """Persist validated immutable revisions without exposing a live command."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        store: PublishedGridViewStore | None = None,
    ) -> None:
        if (
            principal.is_external
            or not principal.user_id
            or principal.user_id == "Guest"
            or not principal.tenant_id
        ):
            raise PermissionDenied()
        self.actor = principal.user_id
        self.tenant_id = principal.tenant_id
        self.request_id = _canonical_uuid(request_id)
        self.trace_id = trace_id
        self.store = store or FrappePublishedGridViewStore()

    def persist_first(
        self,
        *,
        root: PublishedGridViewRoot,
        revision: PublishedGridViewRevision,
    ) -> PublishedGridViewRoot:
        expected_root = PublishedGridViewRoot.from_first_revision(revision)
        if root != expected_root:
            raise RuntimeError("The first published grid view root is inconsistent.")
        self._assert_command_identity(root, revision)
        if self.store.find_root(root.global_id, for_update=True) is not None:
            raise VersionConflict()
        if (
            self.store.find_revision(root.global_id, revision.revision_number)
            is not None
        ):
            raise VersionConflict()
        revision_document = self.store.create_revision(
            _revision_document_values(revision)
        )
        root_document = self.store.create_root(_root_document_values(root))
        try:
            with _controlled_write():
                root_document.insert()
                revision_document.insert()
        except frappe.DuplicateEntryError as error:
            raise VersionConflict() from error
        return root

    def append(
        self,
        *,
        root: PublishedGridViewRoot,
        revision: PublishedGridViewRevision,
        expected_version: int,
    ) -> PublishedGridViewRoot:
        document = self.store.find_root(root.global_id, for_update=True)
        if document is None:
            raise VersionConflict()
        stored_root = _published_root_from_document(document)
        if stored_root.optimistic_version != expected_version:
            raise VersionConflict()
        self._assert_command_identity(root, revision)
        _assert_stored_revision_reference(
            self.store,
            stored_root.global_id,
            stored_root.tenant_id,
            stored_root.project_global_id,
            stored_root.current_revision,
        )
        if revision.prior_revision != stored_root.current_revision:
            raise RuntimeError("The published grid view prior revision is invalid.")
        if revision.restored_from_revision is not None:
            restored_snapshot = _assert_stored_revision_reference(
                self.store,
                stored_root.global_id,
                stored_root.tenant_id,
                stored_root.project_global_id,
                revision.restored_from_revision,
            )
            _assert_exact_restored_content(revision, restored_snapshot)
        expected_root = stored_root.advance(revision)
        if root != expected_root:
            raise RuntimeError("The published grid view successor is inconsistent.")
        if (
            self.store.find_revision(root.global_id, revision.revision_number)
            is not None
        ):
            raise VersionConflict()
        revision_document = self.store.create_revision(
            _revision_document_values(revision)
        )
        values = _root_document_values(root)
        try:
            with _controlled_write():
                revision_document.insert()
                for fieldname, value in values.items():
                    document.set(fieldname, value)
                document.save()
        except frappe.DuplicateEntryError as error:
            raise VersionConflict() from error
        return root

    def _assert_command_identity(
        self,
        root: PublishedGridViewRoot,
        revision: PublishedGridViewRevision,
    ) -> None:
        if (
            root.tenant_id != self.tenant_id
            or revision.tenant_id != self.tenant_id
            or revision.published_by != self.actor
            or revision.request_id != self.request_id
            or revision.trace_id != self.trace_id
            or root.request_id != self.request_id
            or root.trace_id != self.trace_id
        ):
            raise PermissionDenied()


def _root_document_values(root: PublishedGridViewRoot) -> dict[str, object]:
    return {
        "global_id": str(root.global_id),
        "tenant_id": root.tenant_id,
        "project_global_id": str(root.project_global_id),
        "grid_id": GRID_ID,
        "table_schema_version": TABLE_SCHEMA_VERSION,
        "optimistic_version": root.optimistic_version,
        "current_revision_global_id": str(root.current_revision.global_id),
        "current_revision_number": root.current_revision.revision_number,
        "current_revision_snapshot_hash": root.current_revision.snapshot_hash,
        "created_by": root.created_by,
        "created_at": root.created_at,
        "request_id": str(root.request_id),
        "trace_id": root.trace_id,
    }


def _revision_document_values(
    revision: PublishedGridViewRevision,
) -> dict[str, object]:
    prior = revision.prior_revision
    restored = revision.restored_from_revision
    snapshot = revision.snapshot_dict()
    return {
        "global_id": str(revision.global_id),
        "revision_key": revision.revision_key,
        "published_view_global_id": str(revision.published_view_global_id),
        "tenant_id": revision.tenant_id,
        "project_global_id": str(revision.project_global_id),
        "grid_id": GRID_ID,
        "table_schema_version": TABLE_SCHEMA_VERSION,
        "revision_number": revision.revision_number,
        "prior_revision_global_id": (
            None if prior is None else str(prior.global_id)
        ),
        "prior_revision_number": (
            None if prior is None else prior.revision_number
        ),
        "prior_revision_snapshot_hash": (
            None if prior is None else prior.snapshot_hash
        ),
        "restored_from_revision_global_id": (
            None if restored is None else str(restored.global_id)
        ),
        "restored_from_revision_number": (
            None if restored is None else restored.revision_number
        ),
        "restored_from_revision_snapshot_hash": (
            None if restored is None else restored.snapshot_hash
        ),
        "view_name": revision.name,
        "description": revision.description,
        "permission_boundary": PROJECT_PERMISSION_BOUNDARY,
        "definition_snapshot": canonical_json(
            revision.definition.canonical_dict()
        ),
        "definition_hash": revision.definition_hash,
        "published_by": revision.published_by,
        "published_at": revision.published_at,
        "authority_reason_code": revision.authority_reason_code,
        "authority_evidence": canonical_json(dict(revision.authority_evidence)),
        "request_id": str(revision.request_id),
        "trace_id": revision.trace_id,
        "revision_snapshot": canonical_json(snapshot),
        "snapshot_hash": revision.snapshot_hash,
    }


def _published_root_from_document(document: object) -> PublishedGridViewRoot:
    if (
        _value(document, "grid_id") != GRID_ID
        or _value(document, "table_schema_version") != TABLE_SCHEMA_VERSION
    ):
        raise RuntimeError("The published grid view schema identity is invalid.")
    return PublishedGridViewRoot(
        global_id=_canonical_uuid(_value(document, "global_id")),
        tenant_id=str(_value(document, "tenant_id")),
        project_global_id=_canonical_uuid(
            _value(document, "project_global_id")
        ),
        optimistic_version=_stored_version(
            _value(document, "optimistic_version")
        ),
        current_revision=PublishedRevisionReference(
            global_id=_canonical_uuid(
                _value(document, "current_revision_global_id")
            ),
            revision_number=_positive_stored_integer(
                _value(document, "current_revision_number")
            ),
            snapshot_hash=str(
                _value(document, "current_revision_snapshot_hash")
            ),
        ),
        created_by=str(_value(document, "created_by")),
        created_at=_stored_utc_datetime(_value(document, "created_at")),
        request_id=_canonical_uuid(_value(document, "request_id")),
        trace_id=str(_value(document, "trace_id")),
    )


def _assert_stored_revision_reference(
    store: PublishedGridViewStore,
    published_view_global_id: UUID,
    tenant_id: str,
    project_global_id: UUID,
    reference: PublishedRevisionReference,
) -> dict[str, object]:
    document = store.find_revision(
        published_view_global_id,
        reference.revision_number,
    )
    if document is None:
        raise RuntimeError("The published grid view revision is missing.")
    try:
        snapshot = _json_value(_value(document, "revision_snapshot"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "The published grid view revision snapshot is invalid."
        ) from error
    if (
        not isinstance(snapshot, Mapping)
        or set(snapshot) != _REVISION_SNAPSHOT_FIELDS
        or _canonical_uuid(_value(document, "global_id")) != reference.global_id
        or _canonical_uuid(_value(document, "published_view_global_id"))
        != published_view_global_id
        or _value(document, "tenant_id") != tenant_id
        or _canonical_uuid(_value(document, "project_global_id"))
        != project_global_id
        or _positive_stored_integer(_value(document, "revision_number"))
        != reference.revision_number
        or _value(document, "snapshot_hash") != reference.snapshot_hash
        or canonical_hash(snapshot) != reference.snapshot_hash
        or snapshot.get("schemaVersion") != 1
        or snapshot.get("globalId") != str(reference.global_id)
        or snapshot.get("publishedViewId") != str(published_view_global_id)
        or snapshot.get("tenantId") != tenant_id
        or snapshot.get("projectId") != str(project_global_id)
        or snapshot.get("gridId") != GRID_ID
        or snapshot.get("tableSchemaVersion") != TABLE_SCHEMA_VERSION
        or snapshot.get("revisionNumber") != reference.revision_number
        or snapshot.get("permissionBoundary") != PROJECT_PERMISSION_BOUNDARY
    ):
        raise RuntimeError("The published grid view revision lineage is invalid.")
    return dict(snapshot)


def _assert_exact_restored_content(
    revision: PublishedGridViewRevision,
    restored_snapshot: Mapping[str, object],
) -> None:
    if (
        restored_snapshot.get("name") != revision.name
        or restored_snapshot.get("description") != revision.description
        or restored_snapshot.get("definition")
        != revision.definition.canonical_dict()
        or restored_snapshot.get("definitionHash") != revision.definition_hash
    ):
        raise RuntimeError(
            "The published grid view rollback content does not match its target."
        )


def _value(document: object, fieldname: str) -> object:
    if isinstance(document, Mapping):
        return document.get(fieldname)
    getter = getattr(document, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(document, fieldname, None)


def _stored_version(value: object) -> int:
    if type(value) is not int or value < 1:
        raise RuntimeError("The stored personal grid preference version is invalid.")
    return value


def _positive_stored_integer(value: object) -> int:
    if type(value) is not int or value < 1:
        raise RuntimeError("A stored positive integer is invalid.")
    return value


def _stored_utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise RuntimeError("A stored date and time is invalid.") from error
    else:
        raise RuntimeError("A stored date and time is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def _canonical_uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise RuntimeError("A canonical persistence identity is required.")
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise RuntimeError("A canonical persistence identity is required.") from error
    if parsed.int == 0 or str(parsed) != value:
        raise RuntimeError("A canonical persistence identity is required.")
    return parsed


@contextmanager
def _controlled_write():
    flags = frappe.flags
    missing = object()
    previous = getattr(flags, _WRITE_FLAG, missing)
    setattr(flags, _WRITE_FLAG, True)
    try:
        yield
    finally:
        if previous is missing:
            delattr(flags, _WRITE_FLAG)
        else:
            setattr(flags, _WRITE_FLAG, previous)
