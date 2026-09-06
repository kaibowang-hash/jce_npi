from __future__ import annotations

import importlib
import types
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

from tests import test_erpnext_master_data_api as api_tests
from npi_core.foundation.erp_reference import erp_source_id
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed


class ERPMasterSelectionTest(api_tests.ERPNextMasterDataApiTest):
    def page(self, **changes):
        page = {
            "lastSynchronizedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "items": [{"sourceKey": "机台 550-02", "enabled": True}],
        }
        page.update(changes)
        return page

    def test_exact_unicode_identity_and_controls(self):
        self.assertEqual(erp_source_id("机台 550-02", "sourceObjectId"), "机台 550-02")
        for value in ("", " x", "x\nx", "x" * 129, None):
            with self.subTest(value=value), self.assertRaises(RequestValidationFailed):
                erp_source_id(value, "sourceObjectId")

    def test_choice_validation_is_exact_current_enabled_and_permission_scoped(self):
        module = importlib.import_module("npi_integration.master_data.selection")
        principal = self.module.authenticated_principal()
        with patch.object(module, "catalog_collection", return_value=self.page()) as collection:
            record = module.require_catalog_choice(principal, "machine", "机台 550-02", "resources.sourceObjectId")
        self.assertEqual(record["sourceKey"], "机台 550-02")
        self.assertEqual(collection.call_args.kwargs["allowed_source_keys"], frozenset({"机台 550-02"}))
        expired = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for page in (self.page(lastSynchronizedAt=None), self.page(lastSynchronizedAt=expired), self.page(items=[]), self.page(items=[{"sourceKey": "机台 550-02", "enabled": False}]), self.page(items=[{"sourceKey": "different", "enabled": True}])):
            with self.subTest(page=page), patch.object(module, "catalog_collection", return_value=page), self.assertRaises(RequestValidationFailed):
                module.require_catalog_choice(principal, "machine", "机台 550-02", "resources.sourceObjectId")
        with patch.object(module, "catalog_collection", return_value=self.page(items=[])) as collection, self.assertRaises(RequestValidationFailed):
            module.require_catalog_choice(principal, "customer", "other-customer", "customer")
        self.assertEqual(collection.call_args.kwargs["allowed_source_keys"], frozenset())
        principal.is_external = True
        with self.assertRaises(PermissionDenied):
            module.require_catalog_choice(principal, "machine", "机台 550-02", "resources.sourceObjectId")

    def test_project_customer_query_intersects_the_existing_project_references(self):
        from npi_core.project.frappe_repository import FrappeProjectRepository
        from npi_integration.master_data.domain import MasterCatalogKind

        principal = types.SimpleNamespace(user_id="test@example.invalid", is_external=False, tenant_id="tenant-master-api", roles=frozenset({"System Manager"}))
        project_id = str(UUID(int=1001))
        with patch.object(FrappeProjectRepository, "project_cockpit", return_value={"references": [
            {"type": "customer", "sourceSystem": "ERPNEXT", "sourceObjectId": "客户 A"},
            {"type": "customer", "sourceSystem": "NPI_ONE", "sourceObjectId": "other"},
        ]}):
            self.assertEqual(self.module._project_source_keys(principal, MasterCatalogKind.CUSTOMER, project_id), frozenset({"客户 A"}))
        with patch.object(FrappeProjectRepository, "project_cockpit", return_value=None), self.assertRaises(importlib.import_module("npi_core.project_api").ProjectUnavailable):
            self.module._project_source_keys(principal, MasterCatalogKind.CUSTOMER, project_id)
        with self.assertRaises(RequestValidationFailed):
            self.module._project_source_keys(principal, MasterCatalogKind.CUSTOMER, "not-an-id")

    def test_unicode_source_names_round_trip_through_project_and_trial_domains(self):
        from npi_core.project.domain import TypedReference, ProjectReferenceType, ReferenceSourceSystem
        from npi_core.trial.domain import TrialResourceProposal, TrialResourceKind, TrialResourceSource
        reference = TypedReference(ProjectReferenceType.CUSTOMER, ReferenceSourceSystem.ERPNEXT, "客户 A")
        self.assertEqual(reference.canonical_dict()["sourceObjectId"], "客户 A")
        machine = TrialResourceProposal(global_id=UUID(int=1002), kind=TrialResourceKind.MACHINE, source_system=TrialResourceSource.ERPNEXT, source_object_id="机台 550-02", label="机台 550-02", quantity=None, unit=None)
        self.assertEqual(machine.source_object_id, "机台 550-02")
