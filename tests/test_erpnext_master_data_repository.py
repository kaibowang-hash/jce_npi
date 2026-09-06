from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_core.foundation.errors import VersionConflict
from npi_integration.master_data.domain import (
    MasterCatalogKind,
    MasterSnapshotEvent,
    canonical_hash,
)


NOW = datetime(2026, 9, 6, 2, 0, tzinfo=UTC)
ACTOR = "erp-master-service@example.invalid"
TENANT = "tenant-master-test"


def event(version: int, event_number: int, keys: tuple[str, ...]) -> MasterSnapshotEvent:
    records = [
        {
            "sourceKey": key,
            "displayName": f"Item {key}",
            "enabled": True,
            "groupKey": "Products",
            "stockUom": "Nos",
            "isStockItem": True,
            "sourceModifiedAt": "2026-09-06T01:00:00Z",
        }
        for key in keys
    ]
    payload = {
        "catalogKind": "item",
        "sourceEnvironment": "test",
        "sourceVersion": version,
        "sourceModifiedAt": "2026-09-06T01:00:00Z",
        "records": records,
    }
    return MasterSnapshotEvent.from_mapping(
        {
            "schemaVersion": 1,
            "operation": "replace_master_catalog",
            "sourceSystem": "ERPNEXT",
            "targetSystem": "NPI_ONE",
            "eventId": str(UUID(int=event_number)),
            **payload,
            "issuedAt": "2026-09-06T01:59:00Z",
            "traceId": f"trace-master-{event_number}",
            "payloadHash": canonical_hash(payload),
        }
    )


class AttrDict(dict):
    __setattr__ = dict.__setitem__

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


class FakeDocument(AttrDict):
    def __init__(self, owner: "MasterDataRepositoryTest", values: dict[str, object]):
        super().__init__(values)
        self.owner = owner
        self.flags = types.SimpleNamespace()

    def insert(self, *, ignore_permissions: bool = False):
        if not ignore_permissions:
            raise AssertionError("Controlled insert expected.")
        if self.doctype == "NPI Audit Event":
            self.owner.audits.append(self)
            return self
        self.name = self.global_id
        store = self.owner.documents[self.doctype]
        if self.name in store:
            raise self.owner.frappe.DuplicateEntryError()
        store[self.name] = self
        return self

    def save(self, *, ignore_permissions: bool = False):
        if not ignore_permissions:
            raise AssertionError("Controlled save expected.")
        self.owner.documents[self.doctype][self.name] = self
        return self

    def update(self, values: dict[str, object]) -> None:
        dict.update(self, values)


class FakeDatabase:
    def __init__(self, owner: "MasterDataRepositoryTest") -> None:
        self.owner = owner

    def exists(self, doctype: str, name: str) -> bool:
        return name in self.owner.documents.get(doctype, {})

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fields: object,
        *,
        as_dict: bool = False,
        for_update: bool = False,
    ):
        if doctype == "User":
            self.owner.assertEqual(name_or_filters, ACTOR)
            self.owner.assertEqual(fields, ["enabled", "user_type"])
            self.owner.assertTrue(as_dict)
            return {"enabled": 1, "user_type": "System User"}
        store = self.owner.documents[doctype]
        if isinstance(name_or_filters, dict):
            document = next(
                (
                    value
                    for value in store.values()
                    if all(value.get(key) == item for key, item in name_or_filters.items())
                ),
                None,
            )
        else:
            document = store.get(str(name_or_filters))
        if document is None:
            return None
        if fields == "name":
            self.owner.assertTrue(for_update)
            return document.name
        if isinstance(fields, list) and as_dict:
            return {field: document.get(field) for field in fields}
        raise AssertionError((doctype, name_or_filters, fields, as_dict, for_update))


class MasterDataRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.authorization_projection.frappe_validation",
        "npi_integration.master_data.frappe_validation",
        "npi_integration.master_data.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[str, dict[str, FakeDocument]] = {
            "NPI ERP Master Catalog Head": {},
            "NPI ERP Master Catalog Entry": {},
            "NPI ERP Master Snapshot": {},
        }
        self.audits: list[FakeDocument] = []
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user=ACTOR)
        frappe.get_roles = lambda user: ["NPI API User"] if user == ACTOR else []
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.throw = lambda message, exception: (_ for _ in ()).throw(exception(message))
        frappe.db = FakeDatabase(self)
        frappe.get_doc = self.get_doc
        frappe.get_all = self.get_all
        self.frappe = frappe
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module(
            "npi_integration.master_data.frappe_repository"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def get_doc(self, *args: object):
        if len(args) == 1 and isinstance(args[0], dict):
            return FakeDocument(self, dict(args[0]))
        if len(args) == 2:
            doctype, name = str(args[0]), str(args[1])
            document = self.documents[doctype].get(name)
            if document is None:
                raise AssertionError((doctype, name))
            return document
        raise AssertionError(args)

    def get_all(self, doctype: str, **kwargs: object) -> list[dict[str, object]]:
        self.assertEqual(doctype, "NPI ERP Master Catalog Entry")
        rows = list(self.documents[doctype].values())
        filters = kwargs.get("filters") or {}
        def matches(row: FakeDocument, key: str, expected: object) -> bool:
            if (
                isinstance(expected, (list, tuple))
                and len(expected) == 2
                and expected[0] == "in"
            ):
                return row.get(key) in expected[1]
            return row.get(key) == expected

        rows = [
            row
            for row in rows
            if all(matches(row, key, value) for key, value in filters.items())
        ]
        query_filters = kwargs.get("or_filters")
        if query_filters:
            patterns = [str(value[1]).strip("%").casefold() for value in query_filters.values()]
            rows = [
                row
                for row in rows
                if any(
                    pattern in str(row.get(field, "")).casefold()
                    for field, pattern in zip(query_filters, patterns, strict=True)
                )
            ]
        rows.sort(key=lambda row: str(row.get("source_key") or row.get("name")))
        start = int(kwargs.get("start") or 0)
        length = int(kwargs.get("page_length") or len(rows))
        fields = kwargs.get("fields") or []
        return [
            {field: row.get(field) for field in fields}
            for row in rows[start : start + length]
        ]

    def apply(self, snapshot: MasterSnapshotEvent):
        return self.module.apply_snapshot(
            snapshot,
            actor=ACTOR,
            tenant_id=TENANT,
            request_id=UUID(int=990),
            now=NOW,
        )

    def test_replace_replay_tombstone_conflict_and_query_are_atomic(self) -> None:
        first_event = event(1, 980, ("ITEM-A", "ITEM-B"))
        first = self.apply(first_event)
        replay = self.apply(first_event)
        second = self.apply(event(2, 981, ("ITEM-A",)))

        self.assertFalse(first.exact_replay)
        self.assertTrue(replay.exact_replay)
        self.assertEqual(second.source_version, 2)
        entries = self.documents["NPI ERP Master Catalog Entry"]
        by_key = {entry.source_key: entry for entry in entries.values()}
        self.assertEqual(by_key["ITEM-A"].present_in_source, 1)
        self.assertEqual(by_key["ITEM-A"].source_version, 2)
        self.assertEqual(by_key["ITEM-B"].present_in_source, 0)
        self.assertEqual(by_key["ITEM-B"].enabled, 0)
        self.assertEqual(len(self.audits), 2)

        collection = self.module.catalog_collection(
            tenant_id=TENANT,
            kind=MasterCatalogKind.ITEM,
            query="item-a",
            limit=20,
            offset=0,
            allowed_source_keys=None,
        )
        self.assertEqual(collection["sourceVersion"], 2)
        self.assertEqual(collection["total"], 1)
        self.assertEqual([item["sourceKey"] for item in collection["items"]], ["ITEM-A"])

        with self.assertRaises(VersionConflict):
            self.apply(event(1, 982, ("ITEM-A",)))


if __name__ == "__main__":
    unittest.main()
