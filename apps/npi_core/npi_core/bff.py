from __future__ import annotations

import json
import re

import frappe

from .api import frappe_domain_call
from .foundation.errors import (
    ApiRouteNotFound,
    CsrfTokenInvalid,
    ControlledPrintRoutesDisabled,
    DocumentBaselineRoutesDisabled,
    DocumentReleaseRoutesDisabled,
    DocumentRoutesDisabled,
    EngineeringBomRoutesDisabled,
    MalformedRequest,
    PublishRequestRoutesDisabled,
    ProjectCollaborationRoutesDisabled,
    ReportingRoutesDisabled,
    TrialRoutesDisabled,
    ToolingEngineeringControlsRoutesDisabled,
    ToolingAcceptanceAssetsRoutesDisabled,
    ToolingImportRoutesDisabled,
    ToolingExportRoutesDisabled,
    ToolingRoutesDisabled,
    ToolingManufacturingRoutesDisabled,
    ToolingRevisionRoutesDisabled,
    ToolingSetRoutesDisabled,
)
from .foundation.tracing import resolve_trace_id
from .request_security import (
    controlled_print_routes_are_disabled,
    document_baseline_routes_are_disabled,
    document_release_routes_are_disabled,
    document_routes_are_disabled,
    engineering_bom_routes_are_disabled,
    publish_request_routes_are_disabled,
    project_collaboration_routes_are_disabled,
    reporting_routes_are_disabled,
    response_request_id,
    tooling_engineering_controls_routes_are_disabled,
    tooling_acceptance_assets_routes_are_disabled,
    tooling_import_routes_are_disabled,
    tooling_export_routes_are_disabled,
    tooling_set_routes_are_disabled,
    tooling_manufacturing_routes_are_disabled,
    tooling_revision_routes_are_disabled,
    tooling_routes_are_disabled,
    trial_routes_are_disabled,
)

_INBOUND_PROJECT_SOURCE_EVENT_PATH = (
    "/api/npi/v1/integration/erpnext/project-source-events"
)
_INBOUND_ENGINEERING_CHANGE_EVENT_PATH = (
    "/api/npi/v1/integration/erpnext/engineering-change-events"
)

_ROUTES = {
    ("GET", "/api/npi/v1/session/bootstrap"): (
        "npi_core.localization_api.get_session_bootstrap"
    ),
    ("PUT", "/api/npi/v1/session/language"): (
        "npi_core.localization_api.set_current_user_language"
    ),
    ("PUT", "/api/npi/v1/session/preferences/navigation"): (
        "npi_core.localization_api.set_current_user_navigation_preference"
    ),
    ("POST", "/api/npi/v1/projects"): "npi_core.project_api.create_project",
    ("GET", "/api/npi/v1/me/work"): "npi_core.my_work_api.get_my_work",
    ("GET", "/api/npi/v1/me/preferences/my-work-grid"): (
        "npi_core.grid_personalization_api.get_my_work_grid_preferences"
    ),
    ("PUT", "/api/npi/v1/me/preferences/my-work-grid"): (
        "npi_core.grid_personalization_api.set_my_work_grid_preferences"
    ),
    ("GET", "/api/npi/v1/me/preferences/my-work-inspector"): (
        "npi_core.inspector_preferences_api.get_my_work_inspector_preference"
    ),
    ("PUT", "/api/npi/v1/me/preferences/my-work-inspector"): (
        "npi_core.inspector_preferences_api.set_my_work_inspector_preference"
    ),
    ("GET", "/api/npi/v1/learning"): (
        "npi_core.project_controls_api.search_project_learning"
    ),
    ("GET", "/api/npi/v1/search"): "npi_core.reporting_api.search",
    ("GET", "/api/npi/v1/portfolio/projects"): (
        "npi_core.reporting_api.get_project_portfolio"
    ),
    ("GET", "/api/npi/v1/reports/kpis"): "npi_core.reporting_api.get_kpi_trends",
    ("GET", "/api/npi/v1/administration/capabilities"): (
        "npi_core.reporting_api.get_configuration_catalog"
    ),
    ("GET", "/api/npi/v1/notifications"): (
        "npi_core.collaboration_api.get_notifications"
    ),
    ("GET", "/api/npi/v1/me/preferences/notifications"): (
        "npi_core.collaboration_api.get_notification_preference"
    ),
    ("PUT", "/api/npi/v1/me/preferences/notifications"): (
        "npi_core.collaboration_api.set_notification_preference"
    ),
    ("GET", "/api/npi/v1/npi-readiness/templates"): (
        "npi_core.readiness_api.get_readiness_templates"
    ),
    ("POST", "/api/npi/v1/npi-readiness/templates"): (
        "npi_core.readiness_api.create_readiness_template"
    ),
    ("GET", "/api/npi/v1/production-transition/policies"): (
        "npi_core.production_transition_api.list_eligible_production_transition_policies"
    ),
    ("POST", "/api/npi/v1/production-transition/policies"): (
        "npi_core.production_transition_api.create_production_transition_policy_draft"
    ),
}

_PROJECT_COCKPIT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/cockpit$"
)
_PROJECT_ERP_PROJECTIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/erp-projections$"
)
_PROJECT_FORMAL_QUALITY_LINKS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/formal-quality-links$"
)
_PROJECT_FORMAL_QUALITY_LINK_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/formal-quality-links/"
    r"(?P<formal_quality_link_id>[^/:]+)$"
)
_PROJECT_FORMAL_QUALITY_LINK_COMMAND_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/"
    r"formal-quality-links:link-observed-reference$"
)
_PROJECT_INTEGRATION_OPERATIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/integration-operations$"
)
_PROJECT_INTEGRATION_OPERATION_DLQ_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/integration-operations/dlq$"
)
_PROJECT_INTEGRATION_OPERATION_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/integration-operations/"
    r"(?P<operation_kind>receive_project_submission|publish_item|publish_mbom|"
    r"create_tool_asset|update_tool_asset|receive_engineering_change_event|"
    r"publish_change_implementation_summary)/"
    r"(?P<integration_operation_id>[^/:]+)$"
)
_PROJECT_INTEGRATION_OPERATION_COMMAND_ROUTES = tuple(
    (
        re.compile(
            rf"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/"
            rf"integration-operations/{slug}/"
            rf"(?P<integration_operation_id>[^/:]+):{action}$"
        ),
        f"npi_integration.integration_operations.api.{command}",
    )
    for slug, action, command in (
        (
            "receive-project-submissions",
            "replay",
            "replay_receive_project_submission",
        ),
        (
            "receive-project-submissions",
            "request-reconciliation",
            "request_reconciliation_receive_project_submission",
        ),
        ("item-publishes", "replay", "replay_publish_item"),
        (
            "item-publishes",
            "request-reconciliation",
            "request_reconciliation_publish_item",
        ),
        ("mbom-publishes", "replay", "replay_publish_mbom"),
        (
            "mbom-publishes",
            "request-reconciliation",
            "request_reconciliation_publish_mbom",
        ),
        ("tool-asset-creates", "replay", "replay_create_tool_asset"),
        (
            "tool-asset-creates",
            "request-reconciliation",
            "request_reconciliation_create_tool_asset",
        ),
        ("tool-asset-updates", "replay", "replay_update_tool_asset"),
        (
            "tool-asset-updates",
            "request-reconciliation",
            "request_reconciliation_update_tool_asset",
        ),
    )
)
_PROJECT_TRIALS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trials$"
)
_READINESS_TEMPLATE_VERSION_ROUTE = re.compile(
    r"^/api/npi/v1/npi-readiness/templates/(?P<template_id>[^/:]+)/versions/"
    r"(?P<template_version>[^/:]+)$"
)
_READINESS_TEMPLATE_PUBLISH_ROUTE = re.compile(
    r"^/api/npi/v1/npi-readiness/templates/(?P<template_id>[^/:]+)/versions/"
    r"(?P<template_version>[^/:]+):publish$"
)
_PROJECT_READINESS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/npi-readiness$"
)
_PROJECT_READINESS_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/npi-readiness/"
    r"(?P<instance_id>[^/:]+)/revisions$"
)
_PROJECT_ENGINEERING_CHANGES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/engineering-changes$"
)
_PROJECT_ENGINEERING_CHANGE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/engineering-changes/"
    r"(?P<change_id>[^/:]+)$"
)
_PROJECT_ENGINEERING_CHANGE_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/engineering-changes/"
    r"(?P<change_id>[^/:]+)/revisions$"
)
_PROJECT_ENGINEERING_CHANGE_OBSERVATION_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/engineering-changes/"
    r"(?P<change_id>[^/:]+):link-formal-observation$"
)
_PROJECT_ENGINEERING_CHANGE_CLOSE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/engineering-changes/"
    r"(?P<change_id>[^/:]+):close$"
)
_PROJECT_ENGINEERING_CHANGE_SUMMARY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/engineering-changes/"
    r"(?P<change_id>[^/:]+):request-implementation-summary$"
)
_PRODUCTION_TRANSITION_POLICY_VERSION_ROUTE = re.compile(
    r"^/api/npi/v1/production-transition/policies/(?P<policy_id>[^/:]+)/versions/"
    r"(?P<policy_version>[^/:]+)$"
)
_PRODUCTION_TRANSITION_POLICY_PUBLISH_ROUTE = re.compile(
    r"^/api/npi/v1/production-transition/policies/(?P<policy_id>[^/:]+)/versions/"
    r"(?P<policy_version>[^/:]+):publish$"
)
_PRODUCTION_TRANSITION_POLICY_VERSIONS_ROUTE = re.compile(
    r"^/api/npi/v1/production-transition/policies/(?P<policy_id>[^/:]+)/versions$"
)
_PROJECT_PRODUCTION_TRANSITION_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/production-transition$"
)
_PROJECT_PRODUCTION_HANDOVER_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/production-handover$"
)
_PROJECT_PRODUCTION_HANDOVER_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/production-handover/"
    r"(?P<handover_id>[^/:]+)/revisions$"
)
_PROJECT_PRODUCTION_HANDOVER_ACKNOWLEDGEMENTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/production-handover/"
    r"(?P<handover_id>[^/:]+)/revisions/(?P<handover_version>[^/:]+)/"
    r"acknowledgements$"
)
_PROJECT_OBSERVATION_PERIODS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/observation-periods$"
)
_PROJECT_OBSERVATION_PERIOD_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/observation-periods/"
    r"(?P<observation_id>[^/:]+)/revisions$"
)
_PROJECT_TRIAL_PLAN_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-plans/"
    r"(?P<trial_plan_id>[^/:]+)$"
)
_PROJECT_TRIAL_PLAN_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-plans/"
    r"(?P<trial_plan_id>[^/:]+)/revisions$"
)
_PROJECT_TRIAL_PLAN_ROUNDS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-plans/"
    r"(?P<trial_plan_id>[^/:]+)/rounds$"
)
_PROJECT_TRIAL_PLAN_ACTIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-plans/"
    r"(?P<trial_plan_id>[^/:]+)/actions:generate$"
)
_PROJECT_TRIAL_EXECUTION_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/execution$"
)
_PROJECT_TRIAL_PREPARE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+):prepare$"
)
_PROJECT_TRIAL_START_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+):start$"
)
_PROJECT_TRIAL_ACTUAL_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/actual-revisions$"
)
_PROJECT_TRIAL_SAMPLE_BATCHES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/sample-batches$"
)
_PROJECT_TRIAL_SAMPLE_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/sample-batches/"
    r"(?P<sample_batch_id>[^/:]+)/revisions$"
)
_PROJECT_TRIAL_FILES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/files$"
)
_PROJECT_TRIAL_EVIDENCE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/evidence$"
)
_PROJECT_TRIAL_EVIDENCE_CONTENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/evidence/(?P<evidence_id>[^/:]+):content$"
)
_PROJECT_TRIAL_QUALITY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/quality$"
)
_PROJECT_TRIAL_CAVITY_RESULTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/cavity-results$"
)
_PROJECT_TRIAL_CAVITY_RESULT_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/cavity-results/"
    r"(?P<cavity_result_id>[^/:]+)/revisions$"
)
_PROJECT_TRIAL_DEFECTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/defects$"
)
_PROJECT_TRIAL_DEFECT_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/defects/(?P<defect_id>[^/:]+)/revisions$"
)
_PROJECT_TRIAL_DEFECT_VERIFICATIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/defects/(?P<defect_id>[^/:]+)/verifications$"
)
_PROJECT_TRIAL_REVIEW_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/review$"
)
_PROJECT_TRIAL_BEGIN_ANALYSIS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+):begin-analysis$"
)
_PROJECT_TRIAL_COMPARISONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/comparisons$"
)
_PROJECT_TRIAL_REVIEW_REFERENCES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/review-references$"
)
_PROJECT_TRIAL_CONCLUSIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/conclusions$"
)
_PROJECT_TRIAL_CONCLUSION_DECIDE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/conclusions/(?P<conclusion_id>[^/:]+):decide$"
)
_PROJECT_TRIAL_REOPEN_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+):reopen$"
)
_PROJECT_RELEASED_TRIAL_SUMMARIES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/released-trial-summaries$"
)
_PROJECT_RELEASED_TRIAL_SUMMARY_REVISE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/trial-rounds/"
    r"(?P<trial_round_id>[^/:]+)/released-trial-summaries/"
    r"(?P<summary_id>[^/:]+):revise$"
)
_PROJECT_TOOLING_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling$"
)
_PROJECT_TOOLING_MASTER_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)$"
)
_PROJECT_TOOLING_SETS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets$"
)
_PROJECT_TOOLING_SET_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)$"
)
_PROJECT_TOOLING_SET_INTAKES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/intakes$"
)
_PROJECT_TOOLING_INTAKE_EVIDENCE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/intakes/"
    r"(?P<intake_id>[^/:]+)/evidence$"
)
_PROJECT_TOOLING_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/revisions$"
)
_PROJECT_TOOLING_REVISION_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/revisions/(?P<tooling_revision_id>[^/:]+)$"
)
_PROJECT_TOOLING_MANUFACTURING_PLANS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/manufacturing-plans$"
)
_PROJECT_TOOLING_MANUFACTURING_PLAN_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/manufacturing-plans/"
    r"(?P<manufacturing_plan_revision_id>[^/:]+)$"
)
_PROJECT_TOOLING_MANUFACTURING_OBSERVATIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/manufacturing-plans/"
    r"(?P<manufacturing_plan_revision_id>[^/:]+)/milestones/"
    r"(?P<milestone_id>[^/:]+)/observations$"
)
_PROJECT_TOOLING_ENGINEERING_CONTROLS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/engineering-controls$"
)
_PROJECT_TOOLING_DEFECT_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/defect-revisions$"
)
_PROJECT_TOOLING_PROCESS_PROFILE_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/process-profile-revisions$"
)
_PROJECT_TOOLING_CAPACITY_SCENARIO_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/capacity-scenario-revisions$"
)
_PROJECT_TOOLING_ACCEPTANCE_ASSETS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/acceptance-assets$"
)
_PROJECT_TOOLING_ACCEPTANCE_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/acceptance-revisions$"
)
_PROJECT_TOOLING_ASSET_REQUESTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/asset-requests$"
)
_PROJECT_TOOLING_SET_ASSET_REQUESTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/"
    r"asset-requests$"
)
_PROJECT_TOOLING_ASSET_REQUEST_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/asset-requests/"
    r"(?P<asset_request_id>[^/:]+)$"
)
_PROJECT_TOOL_ASSET_EXECUTION_REQUESTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/"
    r"asset-execution-requests$"
)
_PROJECT_TOOL_ASSET_EXECUTION_REQUEST_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/"
    r"asset-execution-requests/(?P<tool_asset_execution_request_id>[^/:]+)$"
)
_PROJECT_TOOL_ASSET_EXECUTION_CREATE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/"
    r"asset-execution-requests:create$"
)
_PROJECT_TOOL_ASSET_EXECUTION_UPDATE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/"
    r"asset-execution-requests:update$"
)
_PROJECT_TOOLING_IMPORTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports$"
)
_PROJECT_TOOLING_IMPORT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)$"
)
_PROJECT_TOOLING_IMPORT_INSPECTIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/inspections$"
)
_PROJECT_TOOLING_IMPORT_MAPPINGS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/mapping-proposals$"
)
_PROJECT_TOOLING_IMPORT_PREVIEWS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/previews$"
)
_PROJECT_TOOLING_IMPORT_CONFIRMATIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/previews/(?P<preview_id>[^/:]+)/confirmations$"
)
_PROJECT_TOOLING_IMPORT_EXECUTE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/previews/(?P<preview_id>[^/:]+):execute$"
)
_PROJECT_TOOLING_IMPORT_JOBS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs$"
)
_PROJECT_TOOLING_IMPORT_JOB_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+)$"
)
_PROJECT_TOOLING_IMPORT_JOB_RETRY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+):retry$"
)
_PROJECT_TOOLING_IMPORT_CORRECTIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+)/correction-artifacts$"
)
_PROJECT_TOOLING_IMPORT_CORRECTION_CONTENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+)/correction-artifacts/"
    r"(?P<artifact_id>[^/:]+):content$"
)
_PROJECT_TOOLING_IMPORT_RECONCILE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+):reconcile$"
)
_PROJECT_TOOLING_IMPORT_ROLLBACK_ELIGIBILITY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+):evaluate-rollback$"
)
_PROJECT_TOOLING_IMPORT_ROLLBACK_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-imports/"
    r"(?P<batch_id>[^/:]+)/jobs/(?P<job_id>[^/:]+):rollback$"
)
_PROJECT_TOOLING_LIST_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-list$"
)
_PROJECT_TOOLING_LIST_PREFERENCE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-list/preferences/"
    r"(?P<view_id>[^/:]+)$"
)
_PROJECT_TOOLING_EXPORTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-exports$"
)
_PROJECT_TOOLING_EXPORT_CONTENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-exports/"
    r"(?P<package_id>[^/:]+):content$"
)
_PROJECT_PART_CONTROLLED_SPECIFICATION_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/parts/"
    r"(?P<part_id>[^/:]+)/revisions/(?P<part_revision_id>[^/:]+)/"
    r"controlled-specification$"
)
_PROJECT_TOOLING_PROCESS_CHAINS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-process-chains$"
)
_PROJECT_TOOLING_PROCESS_CHAIN_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-process-chains/"
    r"(?P<process_chain_revision_id>[^/:]+)$"
)
_PROJECT_TOOLING_SET_REVISION_BINDING_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling/"
    r"(?P<tooling_master_id>[^/:]+)/sets/(?P<tooling_set_id>[^/:]+)/"
    r"revision-binding$"
)
_PROJECT_PARTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/parts$"
)
_PROJECT_PART_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/parts/"
    r"(?P<part_id>[^/:]+)/revisions$"
)
_PROJECT_TOOLING_REQUIREMENTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-requirements$"
)
_PROJECT_TOOLING_MASTERS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-masters$"
)
_PROJECT_TOOLING_APPLICABILITIES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/tooling-applicabilities$"
)
_PROJECT_WORK_CONTEXT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/work-context$"
)
_PROJECT_DOMAIN_WORK_ITEMS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/domain-work-items$"
)
_PROJECT_MEETINGS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/meetings$"
)
_NOTIFICATION_MARK_READ_ROUTE = re.compile(
    r"^/api/npi/v1/notifications/(?P<notification_id>[^/:]+):mark-read$"
)
_PROJECT_CONTROLS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/controls$"
)
_PROJECT_ACTIVITY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/activity$"
)
_PROJECT_COMMENTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/comments$"
)
_PROJECT_LEARNING_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/learning$"
)
_PROJECT_DOCUMENTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents$"
)
_PROJECT_DOCUMENT_BASELINES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/document-baselines$"
)
_PROJECT_DOCUMENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)$"
)
_PROJECT_EBOMS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms$"
)
_CONTROLLED_PRINT_CAPABILITY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/controlled-print/capability$"
)
_PROJECT_CONTROLLED_PRINTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/controlled-prints$"
)
_PROJECT_CONTROLLED_PRINT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/controlled-prints/"
    r"(?P<controlled_print_id>[^/:]+)$"
)
_PROJECT_CONTROLLED_PRINT_CONTENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/controlled-prints/"
    r"(?P<controlled_print_id>[^/:]+)/content$"
)
_PROJECT_EBOM_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/(?P<ebom_id>[^/:]+)$"
)
_EBOM_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
    r"(?P<ebom_id>[^/:]+)/revisions$"
)
_EBOM_COMPARE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
    r"(?P<ebom_id>[^/:]+)/compare$"
)
_EBOM_PUBLISH_REQUESTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
    r"(?P<ebom_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)/publish-requests$"
)
_EBOM_PUBLISH_REQUEST_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
    r"(?P<ebom_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)/publish-requests/"
    r"(?P<publish_request_id>[^/:]+)$"
)
_PROJECT_ITEM_PUBLISH_REQUESTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/item-publish-requests$"
)
_PROJECT_ITEM_PUBLISH_REQUEST_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/item-publish-requests/"
    r"(?P<item_publish_request_id>[^/:]+)$"
)
_PROJECT_MBOM_PUBLISH_REQUESTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/mbom-publish-requests$"
)
_PROJECT_MBOM_PUBLISH_REQUEST_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/mbom-publish-requests/"
    r"(?P<mbom_publish_request_id>[^/:]+)$"
)
_EBOM_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
            r"(?P<ebom_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+):submit-review$"
        ),
        "npi_core.ebom_api.submit_ebom_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
            r"(?P<ebom_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+):review$"
        ),
        "npi_core.ebom_api.review_ebom_revision",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/eboms/"
            r"(?P<ebom_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+):release$"
        ),
        "npi_core.ebom_api.release_ebom_revision",
    ),
)
_DOCUMENT_CHECK_OUT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+):check-out$"
)
_DOCUMENT_CHECK_IN_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+):check-in$"
)
_DOCUMENT_RECOVER_LOCK_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+):recover-lock$"
)
_DOCUMENT_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)/revisions$"
)
_DOCUMENT_RELEASE_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":submit-review$"
        ),
        "npi_core.document_api.submit_document_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":review$"
        ),
        "npi_core.document_api.confirm_document_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":resubmit-review$"
        ),
        "npi_core.document_api.resubmit_document_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":release$"
        ),
        "npi_core.document_api.release_document_revision",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":supersede$"
        ),
        "npi_core.document_api.supersede_document_revision",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":obsolete$"
        ),
        "npi_core.document_api.obsolete_document_revision",
    ),
)
_DOCUMENT_FILE_CAPABILITIES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)/files/"
    r"(?P<file_revision_id>[^/:]+)/capabilities$"
)
_DOCUMENT_FILE_CONTENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)/files/"
    r"(?P<file_revision_id>[^/:]+):content$"
)
_GATE_EVIDENCE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+)/evidence$"
)
_GATE_REQUIREMENT_FREEZE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+):freeze-requirements$"
)
_GATE_EVIDENCE_ATTACH_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+)/requirements/(?P<requirement_key>[^/]+)/evidence$"
)
_GATE_REVIEW_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/" r"(?P<gate_id>[^/:]+)/review$"
)
_GATE_REVIEW_COMMAND_RECEIPT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+)/review-command-receipts/(?P<operation>[^/]+)$"
)
_GATE_REVIEW_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+):start-review$"
        ),
        "npi_core.gate_review_api.start_gate_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+)/review-cycles/(?P<cycle_id>[^/:]+)/reviews$"
        ),
        "npi_core.gate_review_api.submit_gate_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+)/review-cycles/(?P<cycle_id>[^/:]+)/exceptions$"
        ),
        "npi_core.gate_review_api.request_gate_review_exception",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+)/review-cycles/(?P<cycle_id>[^/:]+)/"
            r"exceptions/(?P<exception_id>[^/:]+):decide$"
        ),
        "npi_core.gate_review_api.decide_gate_review_exception",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+):decide$"
        ),
        "npi_core.gate_review_api.decide_gate",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+):reopen$"
        ),
        "npi_core.gate_review_api.reopen_gate",
    ),
)
_PROJECT_WORK_COMMAND_ROUTES = (
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):configure-team$"),
        "npi_core.project_work_api.configure_project_team",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):apply-work-plan$"),
        "npi_core.project_work_api.apply_project_work_plan",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):capture-plan-baseline$"
        ),
        "npi_core.project_work_api.capture_project_plan_baseline",
    ),
)
_PROJECT_CONTROL_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/" r"(?P<project_id>[^/:]+):bind-control-policy$"
        ),
        "npi_core.project_controls_api.bind_project_control_policy",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/" r"(?P<project_id>[^/:]+):assess-health$"),
        "npi_core.project_controls_api.assess_project_health",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):transition$"),
        "npi_core.project_controls_api.transition_project",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):follow$"),
        "npi_core.project_controls_api.follow_project",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):unfollow$"),
        "npi_core.project_controls_api.unfollow_project",
    ),
)


def route_request() -> None:
    """Map the fixed NPI BFF surface before Frappe's generic API router runs."""
    request = frappe.local.request
    raw_path = request.path or "/"
    if (
        request.method == "POST"
        and raw_path
        in {
            _INBOUND_PROJECT_SOURCE_EVENT_PATH,
            _INBOUND_ENGINEERING_CHANGE_EVENT_PATH,
        }
    ):
        frappe.local.form_dict.cmd = {
            _INBOUND_PROJECT_SOURCE_EVENT_PATH: (
                "npi_integration.inbound_project_api.accept_project_source_event"
            ),
            _INBOUND_ENGINEERING_CHANGE_EVENT_PATH: (
                "npi_integration.engineering_change_api.receive_engineering_change_event"
            ),
        }[raw_path]
        frappe.flags.npi_bff_request = True
        frappe.flags.npi_route_params = {}
        return
    path = raw_path.rstrip("/") or "/"
    if not _is_npi_api_path(path) or request.method == "OPTIONS":
        return

    command = _ROUTES.get((request.method, path))
    route_params: dict[str, str] = {}
    if command is None and request.method == "GET":
        match = _PROJECT_ERP_PROJECTIONS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_integration.projection_api.get_erp_projections"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        for route, candidate in (
            (
                _PROJECT_INTEGRATION_OPERATIONS_ROUTE,
                "npi_integration.integration_operations.api.get_integration_operations",
            ),
            (
                _PROJECT_INTEGRATION_OPERATION_DLQ_ROUTE,
                "npi_integration.integration_operations.api.get_integration_operation_dlq",
            ),
            (
                _PROJECT_INTEGRATION_OPERATION_ROUTE,
                "npi_integration.integration_operations.api.get_integration_operation",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        for route, candidate in (
            (
                _PROJECT_FORMAL_QUALITY_LINKS_ROUTE,
                "npi_integration.quality_link_api.get_formal_quality_links",
            ),
            (
                _PROJECT_FORMAL_QUALITY_LINK_ROUTE,
                "npi_integration.quality_link_api.get_formal_quality_link",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        for route, candidate in (
            (
                _PROJECT_TRIALS_ROUTE,
                "npi_core.trial_api.get_trial_planning_workspace",
            ),
            (_PROJECT_TRIAL_PLAN_ROUTE, "npi_core.trial_api.get_trial_plan"),
            (
                _PROJECT_TRIAL_EXECUTION_ROUTE,
                "npi_core.trial_api.get_trial_round_execution",
            ),
            (
                _PROJECT_TRIAL_QUALITY_ROUTE,
                "npi_core.trial_api.get_trial_quality_workspace",
            ),
            (
                _PROJECT_TRIAL_REVIEW_ROUTE,
                "npi_core.trial_api.get_trial_review_workspace",
            ),
            (
                _PROJECT_RELEASED_TRIAL_SUMMARIES_ROUTE,
                "npi_core.released_summary_api.get_released_trial_summaries",
            ),
            (
                _PROJECT_READINESS_ROUTE,
                "npi_core.readiness_api.get_project_readiness",
            ),
            (
                _PROJECT_ENGINEERING_CHANGES_ROUTE,
                "npi_core.change_control_api.get_engineering_changes",
            ),
            (
                _PROJECT_ENGINEERING_CHANGE_ROUTE,
                "npi_core.change_control_api.get_engineering_change",
            ),
            (
                _PROJECT_PRODUCTION_TRANSITION_ROUTE,
                "npi_core.production_transition_api.get_project_production_transition_workspace",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        for route, candidate in _PROJECT_INTEGRATION_OPERATION_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        match = _PROJECT_FORMAL_QUALITY_LINK_COMMAND_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_integration.quality_link_api.link_observed_formal_quality_reference"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _PROJECT_ENGINEERING_CHANGE_SUMMARY_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_integration.engineering_change_api."
                "request_change_implementation_summary"
            )
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in (
            (_PROJECT_TRIALS_ROUTE, "npi_core.trial_api.create_trial_plan"),
            (
                _PROJECT_TRIAL_PLAN_REVISIONS_ROUTE,
                "npi_core.trial_api.create_trial_plan_revision",
            ),
            (
                _PROJECT_TRIAL_PLAN_ROUNDS_ROUTE,
                "npi_core.trial_api.create_planned_trial_round",
            ),
            (
                _PROJECT_TRIAL_PLAN_ACTIONS_ROUTE,
                "npi_core.trial_api.generate_trial_plan_actions",
            ),
            (
                _PROJECT_TRIAL_PREPARE_ROUTE,
                "npi_core.trial_api.prepare_trial_round",
            ),
            (
                _PROJECT_TRIAL_START_ROUTE,
                "npi_core.trial_api.start_trial_round",
            ),
            (
                _PROJECT_TRIAL_ACTUAL_REVISIONS_ROUTE,
                "npi_core.trial_api.append_trial_actual_revision",
            ),
            (
                _PROJECT_TRIAL_SAMPLE_BATCHES_ROUTE,
                "npi_core.trial_api.create_trial_sample_batch",
            ),
            (
                _PROJECT_TRIAL_SAMPLE_REVISIONS_ROUTE,
                "npi_core.trial_api.append_trial_sample_batch_revision",
            ),
            (
                _PROJECT_TRIAL_FILES_ROUTE,
                "npi_core.trial_api.upload_trial_evidence_file",
            ),
            (
                _PROJECT_TRIAL_EVIDENCE_ROUTE,
                "npi_core.trial_api.bind_trial_evidence",
            ),
            (
                _PROJECT_TRIAL_EVIDENCE_CONTENT_ROUTE,
                "npi_core.trial_api.read_trial_evidence_content",
            ),
            (
                _PROJECT_TRIAL_CAVITY_RESULTS_ROUTE,
                "npi_core.trial_api.create_trial_cavity_result",
            ),
            (
                _PROJECT_TRIAL_CAVITY_RESULT_REVISIONS_ROUTE,
                "npi_core.trial_api.revise_trial_cavity_result",
            ),
            (
                _PROJECT_TRIAL_DEFECTS_ROUTE,
                "npi_core.trial_api.create_trial_defect",
            ),
            (
                _PROJECT_TRIAL_DEFECT_REVISIONS_ROUTE,
                "npi_core.trial_api.revise_trial_defect",
            ),
            (
                _PROJECT_TRIAL_DEFECT_VERIFICATIONS_ROUTE,
                "npi_core.trial_api.verify_trial_defect",
            ),
            (
                _PROJECT_TRIAL_BEGIN_ANALYSIS_ROUTE,
                "npi_core.trial_api.begin_trial_analysis",
            ),
            (
                _PROJECT_TRIAL_COMPARISONS_ROUTE,
                "npi_core.trial_api.create_trial_comparison",
            ),
            (
                _PROJECT_TRIAL_REVIEW_REFERENCES_ROUTE,
                "npi_core.trial_api.create_trial_review_reference",
            ),
            (
                _PROJECT_TRIAL_CONCLUSIONS_ROUTE,
                "npi_core.trial_api.submit_trial_conclusion",
            ),
            (
                _PROJECT_TRIAL_CONCLUSION_DECIDE_ROUTE,
                "npi_core.trial_api.decide_trial_conclusion",
            ),
            (
                _PROJECT_TRIAL_REOPEN_ROUTE,
                "npi_core.trial_api.reopen_trial_conclusion",
            ),
            (
                _PROJECT_RELEASED_TRIAL_SUMMARIES_ROUTE,
                "npi_core.released_summary_api.retain_released_trial_summary",
            ),
            (
                _PROJECT_RELEASED_TRIAL_SUMMARY_REVISE_ROUTE,
                "npi_core.released_summary_api.revise_released_trial_summary",
            ),
            (
                _READINESS_TEMPLATE_PUBLISH_ROUTE,
                "npi_core.readiness_api.publish_readiness_template",
            ),
            (
                _PROJECT_READINESS_ROUTE,
                "npi_core.readiness_api.initialize_project_readiness",
            ),
            (
                _PROJECT_READINESS_REVISIONS_ROUTE,
                "npi_core.readiness_api.revise_project_readiness",
            ),
            (
                _PROJECT_ENGINEERING_CHANGES_ROUTE,
                "npi_core.change_control_api.create_engineering_change",
            ),
            (
                _PROJECT_ENGINEERING_CHANGE_REVISIONS_ROUTE,
                "npi_core.change_control_api.revise_engineering_change",
            ),
            (
                _PROJECT_ENGINEERING_CHANGE_OBSERVATION_ROUTE,
                "npi_core.change_control_api.link_engineering_change_formal_observation",
            ),
            (
                _PROJECT_ENGINEERING_CHANGE_CLOSE_ROUTE,
                "npi_core.change_control_api.close_engineering_change",
            ),
            (
                _PRODUCTION_TRANSITION_POLICY_PUBLISH_ROUTE,
                "npi_core.production_transition_api.publish_production_transition_policy_version",
            ),
            (
                _PRODUCTION_TRANSITION_POLICY_VERSIONS_ROUTE,
                "npi_core.production_transition_api.create_next_production_transition_policy_version",
            ),
            (
                _PROJECT_PRODUCTION_HANDOVER_ROUTE,
                "npi_core.production_transition_api.create_production_handover_package",
            ),
            (
                _PROJECT_PRODUCTION_HANDOVER_REVISIONS_ROUTE,
                "npi_core.production_transition_api.revise_production_handover_package",
            ),
            (
                _PROJECT_PRODUCTION_HANDOVER_ACKNOWLEDGEMENTS_ROUTE,
                "npi_core.production_transition_api.acknowledge_production_handover_slot",
            ),
            (
                _PROJECT_OBSERVATION_PERIODS_ROUTE,
                "npi_core.production_transition_api.create_observation_period",
            ),
            (
                _PROJECT_OBSERVATION_PERIOD_REVISIONS_ROUTE,
                "npi_core.production_transition_api.revise_observation_period",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "PUT":
        match = _READINESS_TEMPLATE_VERSION_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.readiness_api.edit_readiness_template"
            route_params = match.groupdict()
    if command is None and request.method == "PUT":
        match = _PRODUCTION_TRANSITION_POLICY_VERSION_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.production_transition_api."
                "edit_production_transition_policy_draft"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        for route, candidate in (
            (_PROJECT_TOOLING_LIST_ROUTE, "npi_core.tooling_export_api.get_tooling_list"),
            (
                _PROJECT_TOOLING_LIST_PREFERENCE_ROUTE,
                "npi_core.tooling_export_api.get_tooling_list_preference",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "PUT":
        match = _PROJECT_TOOLING_LIST_PREFERENCE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.tooling_export_api.set_tooling_list_preference"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in (
            (
                _PROJECT_TOOLING_EXPORTS_ROUTE,
                "npi_core.tooling_export_api.create_tooling_export_package",
            ),
            (
                _PROJECT_TOOLING_EXPORT_CONTENT_ROUTE,
                "npi_core.tooling_export_api.download_tooling_export_package",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        for route, candidate in (
            (
                _PROJECT_TOOLING_IMPORTS_ROUTE,
                "npi_core.tooling_import_api.get_tooling_import_batches",
            ),
            (
                _PROJECT_TOOLING_IMPORT_ROUTE,
                "npi_core.tooling_import_api.get_tooling_import_batch",
            ),
            (
                _PROJECT_TOOLING_IMPORT_JOBS_ROUTE,
                "npi_core.tooling_import_api.get_tooling_import_jobs",
            ),
            (
                _PROJECT_TOOLING_IMPORT_JOB_ROUTE,
                "npi_core.tooling_import_api.get_tooling_import_job",
            ),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        match = _PROJECT_COCKPIT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_api.get_project_cockpit"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_TOOLING_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.tooling_api.get_tooling_cockpit"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_TOOLING_ENGINEERING_CONTROLS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.tooling_api.get_tooling_engineering_controls"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        acceptance_asset_queries = (
            (
                _PROJECT_TOOLING_ACCEPTANCE_ASSETS_ROUTE,
                "npi_integration.tool_asset_request_api.get_tooling_acceptance_assets",
            ),
            (
                _PROJECT_TOOLING_ASSET_REQUESTS_ROUTE,
                "npi_integration.tool_asset_request_api.get_tool_asset_requests",
            ),
            (
                _PROJECT_TOOLING_ASSET_REQUEST_ROUTE,
                "npi_integration.tool_asset_request_api.get_tool_asset_request",
            ),
            (
                _PROJECT_TOOL_ASSET_EXECUTION_REQUESTS_ROUTE,
                "npi_integration.tool_asset_request_api.get_tool_asset_execution_requests",
            ),
            (
                _PROJECT_TOOL_ASSET_EXECUTION_REQUEST_ROUTE,
                "npi_integration.tool_asset_request_api.get_tool_asset_execution_request",
            ),
        )
        for route, candidate in acceptance_asset_queries:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        manufacturing_queries = (
            (
                _PROJECT_TOOLING_MANUFACTURING_PLANS_ROUTE,
                "npi_core.tooling_api.get_tooling_manufacturing_plans",
            ),
            (
                _PROJECT_TOOLING_MANUFACTURING_PLAN_ROUTE,
                "npi_core.tooling_api.get_tooling_manufacturing_plan",
            ),
        )
        for route, candidate in manufacturing_queries:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        revision_queries = (
            (
                _PROJECT_TOOLING_REVISIONS_ROUTE,
                "npi_core.tooling_api.get_tooling_revisions",
            ),
            (
                _PROJECT_TOOLING_REVISION_ROUTE,
                "npi_core.tooling_api.get_tooling_revision",
            ),
            (
                _PROJECT_PART_CONTROLLED_SPECIFICATION_ROUTE,
                "npi_core.tooling_api.get_part_controlled_specification",
            ),
            (
                _PROJECT_TOOLING_PROCESS_CHAINS_ROUTE,
                "npi_core.tooling_api.get_tooling_process_chains",
            ),
            (
                _PROJECT_TOOLING_PROCESS_CHAIN_ROUTE,
                "npi_core.tooling_api.get_tooling_process_chain",
            ),
        )
        for route, candidate in revision_queries:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        for route, candidate in (
            (_PROJECT_TOOLING_SETS_ROUTE, "npi_core.tooling_api.get_tooling_sets"),
            (_PROJECT_TOOLING_SET_ROUTE, "npi_core.tooling_api.get_tooling_set"),
        ):
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        match = _PROJECT_TOOLING_MASTER_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.tooling_api.get_tooling_master"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        import_commands = (
            (
                _PROJECT_TOOLING_IMPORTS_ROUTE,
                "npi_core.tooling_import_api.create_tooling_import_batch",
            ),
            (
                _PROJECT_TOOLING_IMPORT_INSPECTIONS_ROUTE,
                "npi_core.tooling_import_api.create_tooling_import_inspection",
            ),
            (
                _PROJECT_TOOLING_IMPORT_MAPPINGS_ROUTE,
                "npi_core.tooling_import_api.create_tooling_import_mapping_proposal",
            ),
            (
                _PROJECT_TOOLING_IMPORT_PREVIEWS_ROUTE,
                "npi_core.tooling_import_api.create_tooling_import_preview",
            ),
            (
                _PROJECT_TOOLING_IMPORT_CONFIRMATIONS_ROUTE,
                "npi_core.tooling_import_api.create_tooling_import_confirmation",
            ),
            (
                _PROJECT_TOOLING_IMPORT_EXECUTE_ROUTE,
                "npi_core.tooling_import_api.execute_tooling_import_preview",
            ),
            (
                _PROJECT_TOOLING_IMPORT_JOB_RETRY_ROUTE,
                "npi_core.tooling_import_api.retry_tooling_import_job",
            ),
            (
                _PROJECT_TOOLING_IMPORT_CORRECTIONS_ROUTE,
                "npi_core.tooling_import_api.create_tooling_import_correction_artifact",
            ),
            (
                _PROJECT_TOOLING_IMPORT_CORRECTION_CONTENT_ROUTE,
                "npi_core.tooling_import_api.download_tooling_import_correction_artifact",
            ),
            (
                _PROJECT_TOOLING_IMPORT_RECONCILE_ROUTE,
                "npi_core.tooling_import_api.reconcile_tooling_import_job",
            ),
            (
                _PROJECT_TOOLING_IMPORT_ROLLBACK_ELIGIBILITY_ROUTE,
                "npi_core.tooling_import_api.evaluate_tooling_import_rollback",
            ),
            (
                _PROJECT_TOOLING_IMPORT_ROLLBACK_ROUTE,
                "npi_core.tooling_import_api.rollback_tooling_import_job",
            ),
        )
        for route, candidate in import_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        acceptance_asset_commands = (
            (
                _PROJECT_TOOLING_ACCEPTANCE_REVISIONS_ROUTE,
                "npi_core.tooling_api.create_tooling_acceptance_evidence_revision",
            ),
            (
                _PROJECT_TOOLING_SET_ASSET_REQUESTS_ROUTE,
                "npi_integration.tool_asset_request_api.create_tool_asset_request",
            ),
            (
                _PROJECT_TOOL_ASSET_EXECUTION_CREATE_ROUTE,
                "npi_integration.tool_asset_request_api.create_tool_asset_execution_request",
            ),
            (
                _PROJECT_TOOL_ASSET_EXECUTION_UPDATE_ROUTE,
                "npi_integration.tool_asset_request_api.update_tool_asset_execution_request",
            ),
        )
        for route, candidate in acceptance_asset_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        engineering_control_commands = (
            (
                _PROJECT_TOOLING_DEFECT_REVISIONS_ROUTE,
                "npi_core.tooling_api.create_tooling_defect_revision",
            ),
            (
                _PROJECT_TOOLING_PROCESS_PROFILE_REVISIONS_ROUTE,
                "npi_core.tooling_api.create_tooling_process_profile_revision",
            ),
            (
                _PROJECT_TOOLING_CAPACITY_SCENARIO_REVISIONS_ROUTE,
                "npi_core.tooling_api.create_tooling_capacity_scenario_revision",
            ),
        )
        for route, candidate in engineering_control_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        manufacturing_commands = (
            (
                _PROJECT_TOOLING_MANUFACTURING_PLANS_ROUTE,
                "npi_core.tooling_api.create_tooling_manufacturing_plan",
            ),
            (
                _PROJECT_TOOLING_MANUFACTURING_OBSERVATIONS_ROUTE,
                "npi_core.tooling_api.create_tooling_manufacturing_milestone_observation",
            ),
        )
        for route, candidate in manufacturing_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        revision_commands = (
            (
                _PROJECT_TOOLING_REVISIONS_ROUTE,
                "npi_core.tooling_api.create_tooling_revision",
            ),
            (
                _PROJECT_PART_CONTROLLED_SPECIFICATION_ROUTE,
                "npi_core.tooling_api.create_part_controlled_specification",
            ),
            (
                _PROJECT_TOOLING_PROCESS_CHAINS_ROUTE,
                "npi_core.tooling_api.create_tooling_process_chain_revision",
            ),
            (
                _PROJECT_TOOLING_SET_REVISION_BINDING_ROUTE,
                "npi_core.tooling_api.create_tooling_set_revision_binding",
            ),
        )
        for route, candidate in revision_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        tooling_set_commands = (
            (_PROJECT_TOOLING_SETS_ROUTE, "npi_core.tooling_api.create_tooling_set"),
            (
                _PROJECT_TOOLING_SET_INTAKES_ROUTE,
                "npi_core.tooling_api.create_tooling_intake",
            ),
            (
                _PROJECT_TOOLING_INTAKE_EVIDENCE_ROUTE,
                "npi_core.tooling_api.create_tooling_intake_evidence_reference",
            ),
        )
        for route, candidate in tooling_set_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        tooling_commands = (
            (_PROJECT_PARTS_ROUTE, "npi_core.tooling_api.create_engineering_part"),
            (
                _PROJECT_PART_REVISIONS_ROUTE,
                "npi_core.tooling_api.create_engineering_part_revision",
            ),
            (
                _PROJECT_TOOLING_REQUIREMENTS_ROUTE,
                "npi_core.tooling_api.create_tooling_requirement",
            ),
            (
                _PROJECT_TOOLING_MASTERS_ROUTE,
                "npi_core.tooling_api.create_tooling_master",
            ),
            (
                _PROJECT_TOOLING_APPLICABILITIES_ROUTE,
                "npi_core.tooling_api.create_tooling_applicability",
            ),
        )
        for route, candidate in tooling_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        match = _PROJECT_CONTROLLED_PRINTS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.controlled_print_api.create_controlled_print_snapshot"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_CONTROLLED_PRINT_CONTENT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.controlled_print_api.download_controlled_print_output"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_CONTROLLED_PRINT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.controlled_print_api.get_controlled_print_snapshot"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_WORK_CONTEXT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_work_api.get_project_work_context"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_DOMAIN_WORK_ITEMS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.project_work_api.get_project_domain_work_items"
                if request.method == "GET"
                else "npi_core.project_work_api.create_project_domain_work_item"
            )
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_MEETINGS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.collaboration_api.get_project_meetings"
                if request.method == "GET"
                else "npi_core.collaboration_api.create_project_meeting"
            )
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _NOTIFICATION_MARK_READ_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.collaboration_api.mark_notification_read"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _CONTROLLED_PRINT_CAPABILITY_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.controlled_print_api.get_controlled_print_capability"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_CONTROLS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_controls_api.get_project_controls"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_ACTIVITY_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_controls_api.get_project_activity"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _PROJECT_COMMENTS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_controls_api.add_project_comment"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_LEARNING_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.project_controls_api.get_project_learning"
                if request.method == "GET"
                else "npi_core.project_controls_api.create_project_learning"
            )
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_DOCUMENT_BASELINES_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.document_api.get_document_baselines"
                if request.method == "GET"
                else "npi_core.document_api.create_document_baseline"
            )
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_DOCUMENTS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.document_api.get_documents"
                if request.method == "GET"
                else "npi_core.document_api.create_document"
            )
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_EBOMS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.ebom_api.get_eboms"
                if request.method == "GET"
                else "npi_core.ebom_api.create_ebom"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _EBOM_COMPARE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.ebom_api.compare_ebom_revisions"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _EBOM_PUBLISH_REQUESTS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_integration.publish_request_api.get_publish_requests"
                if request.method == "GET"
                else "npi_integration.publish_request_api.create_publish_request"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _EBOM_PUBLISH_REQUEST_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_integration.publish_request_api.get_publish_request"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_ITEM_PUBLISH_REQUESTS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_integration.item_publish_api.get_item_publish_requests"
                if request.method == "GET"
                else "npi_integration.item_publish_api.create_item_publish_request"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_ITEM_PUBLISH_REQUEST_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_integration.item_publish_api.get_item_publish_request"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_MBOM_PUBLISH_REQUESTS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_integration.mbom_publish_api.get_mbom_publish_requests"
                if request.method == "GET"
                else "npi_integration.mbom_publish_api.create_mbom_publish_request"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_MBOM_PUBLISH_REQUEST_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_integration.mbom_publish_api.get_mbom_publish_request"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _EBOM_REVISIONS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.ebom_api.create_ebom_revision"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in _EBOM_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        match = _PROJECT_EBOM_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.ebom_api.get_ebom"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _DOCUMENT_FILE_CAPABILITIES_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.get_file_capabilities"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _DOCUMENT_FILE_CONTENT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.get_file_content"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _DOCUMENT_REVISIONS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.create_document_revision"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in _DOCUMENT_RELEASE_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        document_commands = (
            (_DOCUMENT_CHECK_OUT_ROUTE, "npi_core.document_api.check_out_document"),
            (_DOCUMENT_CHECK_IN_ROUTE, "npi_core.document_api.check_in_document"),
            (
                _DOCUMENT_RECOVER_LOCK_ROUTE,
                "npi_core.document_api.recover_document_lock",
            ),
        )
        for route, candidate in document_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        match = _PROJECT_DOCUMENT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.get_document"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_EVIDENCE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.get_gate_evidence_workspace"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_REVIEW_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_review_api.get_gate_review"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_REVIEW_COMMAND_RECEIPT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_review_api.get_gate_review_command_receipt"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _GATE_REQUIREMENT_FREEZE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.freeze_gate_requirements"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _GATE_EVIDENCE_ATTACH_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.attach_gate_evidence"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in _GATE_REVIEW_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        for route, candidate in _PROJECT_WORK_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        for route, candidate in _PROJECT_CONTROL_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if _p4_05_routes_disabled(command):
        command = "npi_core.bff.project_collaboration_routes_disabled"
        route_params = {}
    if _p5_01_routes_disabled(command):
        command = "npi_core.bff.document_routes_disabled"
        route_params = {}
    if _p5_02_routes_disabled(command):
        command = "npi_core.bff.document_release_routes_disabled"
        route_params = {}
    if _p5_03_routes_disabled(command):
        command = "npi_core.bff.document_baseline_routes_disabled"
        route_params = {}
    if _p5_04_routes_disabled(command):
        command = "npi_core.bff.engineering_bom_routes_disabled"
        route_params = {}
    if _p5_05_routes_disabled(command):
        command = "npi_core.bff.publish_request_routes_disabled"
        route_params = {}
    if _p5_06_routes_disabled(command):
        command = "npi_core.bff.controlled_print_routes_disabled"
        route_params = {}
    if _p6_01_routes_disabled(command):
        command = "npi_core.bff.tooling_routes_disabled"
        route_params = {}
    if _p6_02_routes_disabled(command):
        command = "npi_core.bff.tooling_set_routes_disabled"
        route_params = {}
    if _p6_03_routes_disabled(command):
        command = "npi_core.bff.tooling_revision_routes_disabled"
        route_params = {}
    if _p6_04_routes_disabled(command):
        command = "npi_core.bff.tooling_manufacturing_routes_disabled"
        route_params = {}
    if _p6_05_routes_disabled(command):
        command = "npi_core.bff.tooling_engineering_controls_routes_disabled"
        route_params = {}
    if _p6_06_routes_disabled(command):
        command = "npi_core.bff.tooling_acceptance_assets_routes_disabled"
        route_params = {}
    if _p6_07_routes_disabled(command):
        command = "npi_core.bff.tooling_import_routes_disabled"
        route_params = {}
    if _p6_08_routes_disabled(command):
        command = "npi_core.bff.tooling_export_routes_disabled"
        route_params = {}
    if _p7_01_routes_disabled(command):
        command = "npi_core.bff.trial_routes_disabled"
        route_params = {}
    if _p7_02_routes_disabled(command):
        command = "npi_core.trial_api.trial_execution_routes_disabled"
        route_params = {}
    if _p7_03_routes_disabled(command):
        command = "npi_core.trial_api.trial_quality_routes_disabled"
        route_params = {}
    if _p7_04_routes_disabled(command):
        command = "npi_core.trial_api.trial_review_routes_disabled"
        route_params = {}
    if _p7_05_routes_disabled(command):
        command = "npi_core.readiness_api.readiness_routes_disabled"
        route_params = {}
    if _p7_06_routes_disabled(command):
        command = "npi_core.production_transition_api.production_transition_routes_disabled"
        route_params = {}
    if _p7_07_routes_disabled(command):
        command = "npi_core.released_summary_api.released_trial_summary_routes_disabled"
        route_params = {}
    if _p9_01_routes_disabled(command):
        command = "npi_core.change_control_api.engineering_change_routes_disabled"
        route_params = {}
    if _p9_02_routes_disabled(command):
        command = "npi_core.bff.reporting_routes_disabled"
        route_params = {}
    frappe.local.form_dict.cmd = command or "npi_core.bff.route_not_found"
    frappe.flags.npi_bff_request = True
    frappe.flags.npi_route_params = route_params


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def route_not_found() -> dict[str, object] | None:
    """Return the NPI problem contract instead of leaking Frappe routing errors."""

    def raise_not_found() -> dict[str, object]:
        raise ApiRouteNotFound()

    return frappe_domain_call(raise_not_found)


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST", "PUT"],
)
def project_collaboration_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P4-05 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise ProjectCollaborationRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(allow_guest=True, methods=["GET", "POST", "PUT"])
def reporting_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P9-02 reporting/collaboration routes."""

    def raise_disabled() -> dict[str, object]:
        raise ReportingRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def document_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P5-01 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise DocumentRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["POST"],
)
def document_release_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P5-02 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise DocumentReleaseRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def document_baseline_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P5-03 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise DocumentBaselineRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def engineering_bom_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P5-04 while retaining earlier Phase 5 routes."""

    def raise_disabled() -> dict[str, object]:
        raise EngineeringBomRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def publish_request_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P5-05 while retaining P5-04 EBOM routes."""

    def raise_disabled() -> dict[str, object]:
        raise PublishRequestRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def controlled_print_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P5-06 while retaining prior Phase 5 routes."""

    def raise_disabled() -> dict[str, object]:
        raise ControlledPrintRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_routes_disabled() -> dict[str, object] | None:
    """Fail closed for the P6-01 slice until the Site explicitly enables it."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_set_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-02 while retaining P6-01 Tooling routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingSetRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_revision_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-03 while retaining P6-01/P6-02 routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingRevisionRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_manufacturing_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-04 while retaining earlier Tooling routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingManufacturingRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_engineering_controls_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-05 while retaining earlier Tooling routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingEngineeringControlsRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_acceptance_assets_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-06 while retaining earlier Tooling routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingAcceptanceAssetsRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def tooling_import_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-07 while retaining prior Tooling routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingImportRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "PUT", "POST"],
)
def tooling_export_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P6-08 while retaining prior Tooling routes."""

    def raise_disabled() -> dict[str, object]:
        raise ToolingExportRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def trial_routes_disabled() -> dict[str, object] | None:
    """Fail closed only for P7-01 while retaining all earlier routes."""

    def raise_disabled() -> dict[str, object]:
        raise TrialRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


def _p4_05_routes_disabled(command: str | None) -> bool:
    return project_collaboration_routes_are_disabled() and (
        command == "npi_core.my_work_api.get_my_work"
        or (
            isinstance(command, str)
            and command.startswith("npi_core.inspector_preferences_api.")
        )
        or (
            isinstance(command, str)
            and command.startswith("npi_core.project_controls_api.")
        )
    )


def _p9_02_routes_disabled(command: str | None) -> bool:
    return reporting_routes_are_disabled() and (
        isinstance(command, str)
        and command.startswith(("npi_core.reporting_api.", "npi_core.collaboration_api."))
    )


def _p5_02_routes_disabled(command: str | None) -> bool:
    release_commands = frozenset(
        candidate for _route, candidate in _DOCUMENT_RELEASE_COMMAND_ROUTES
    )
    return document_release_routes_are_disabled() and command in release_commands


def _p5_03_routes_disabled(command: str | None) -> bool:
    return document_baseline_routes_are_disabled() and command in {
        "npi_core.document_api.get_document_baselines",
        "npi_core.document_api.create_document_baseline",
    }


def _p5_04_routes_disabled(command: str | None) -> bool:
    return engineering_bom_routes_are_disabled() and (
        isinstance(command, str) and command.startswith("npi_core.ebom_api.")
    )


def _p5_05_routes_disabled(command: str | None) -> bool:
    return publish_request_routes_are_disabled() and (
        isinstance(command, str)
        and command.startswith("npi_integration.publish_request_api.")
    )


def _p5_06_routes_disabled(command: str | None) -> bool:
    return controlled_print_routes_are_disabled() and (
        isinstance(command, str)
        and command.startswith("npi_core.controlled_print_api.")
    )


def _p6_01_routes_disabled(command: str | None) -> bool:
    return tooling_routes_are_disabled() and command in {
        "npi_core.tooling_api.get_tooling_cockpit",
        "npi_core.tooling_api.get_tooling_master",
        "npi_core.tooling_api.create_engineering_part",
        "npi_core.tooling_api.create_engineering_part_revision",
        "npi_core.tooling_api.create_tooling_requirement",
        "npi_core.tooling_api.create_tooling_master",
        "npi_core.tooling_api.create_tooling_applicability",
    }


def _p6_02_routes_disabled(command: str | None) -> bool:
    return tooling_set_routes_are_disabled() and command in {
        "npi_core.tooling_api.get_tooling_sets",
        "npi_core.tooling_api.get_tooling_set",
        "npi_core.tooling_api.create_tooling_set",
        "npi_core.tooling_api.create_tooling_intake",
        "npi_core.tooling_api.create_tooling_intake_evidence_reference",
    }


def _p6_03_routes_disabled(command: str | None) -> bool:
    return tooling_revision_routes_are_disabled() and command in {
        "npi_core.tooling_api.get_tooling_revisions",
        "npi_core.tooling_api.get_tooling_revision",
        "npi_core.tooling_api.create_tooling_revision",
        "npi_core.tooling_api.get_part_controlled_specification",
        "npi_core.tooling_api.create_part_controlled_specification",
        "npi_core.tooling_api.get_tooling_process_chains",
        "npi_core.tooling_api.get_tooling_process_chain",
        "npi_core.tooling_api.create_tooling_process_chain_revision",
        "npi_core.tooling_api.create_tooling_set_revision_binding",
    }


def _p6_04_routes_disabled(command: str | None) -> bool:
    return tooling_manufacturing_routes_are_disabled() and command in {
        "npi_core.tooling_api.get_tooling_manufacturing_plans",
        "npi_core.tooling_api.get_tooling_manufacturing_plan",
        "npi_core.tooling_api.create_tooling_manufacturing_plan",
        "npi_core.tooling_api.create_tooling_manufacturing_milestone_observation",
    }


def _p6_05_routes_disabled(command: str | None) -> bool:
    return tooling_engineering_controls_routes_are_disabled() and command in {
        "npi_core.tooling_api.get_tooling_engineering_controls",
        "npi_core.tooling_api.create_tooling_defect_revision",
        "npi_core.tooling_api.create_tooling_process_profile_revision",
        "npi_core.tooling_api.create_tooling_capacity_scenario_revision",
    }


def _p6_06_routes_disabled(command: str | None) -> bool:
    return tooling_acceptance_assets_routes_are_disabled() and command in {
        "npi_core.tooling_api.create_tooling_acceptance_evidence_revision",
        "npi_integration.tool_asset_request_api.get_tooling_acceptance_assets",
        "npi_integration.tool_asset_request_api.get_tool_asset_requests",
        "npi_integration.tool_asset_request_api.get_tool_asset_request",
        "npi_integration.tool_asset_request_api.create_tool_asset_request",
        "npi_integration.tool_asset_request_api.get_tool_asset_execution_requests",
        "npi_integration.tool_asset_request_api.get_tool_asset_execution_request",
        "npi_integration.tool_asset_request_api.create_tool_asset_execution_request",
        "npi_integration.tool_asset_request_api.update_tool_asset_execution_request",
    }


def _p6_07_routes_disabled(command: str | None) -> bool:
    return tooling_import_routes_are_disabled() and (
        isinstance(command, str)
        and command.startswith("npi_core.tooling_import_api.")
    )


def _p6_08_routes_disabled(command: str | None) -> bool:
    return tooling_export_routes_are_disabled() and (
        isinstance(command, str)
        and command.startswith("npi_core.tooling_export_api.")
    )


def _p7_01_routes_disabled(command: str | None) -> bool:
    return trial_routes_are_disabled() and command in {
        "npi_core.trial_api.get_trial_planning_workspace",
        "npi_core.trial_api.get_trial_plan",
        "npi_core.trial_api.create_trial_plan",
        "npi_core.trial_api.create_trial_plan_revision",
        "npi_core.trial_api.create_planned_trial_round",
        "npi_core.trial_api.generate_trial_plan_actions",
    }


def _p7_02_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_02_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and command in {
        "npi_core.trial_api.get_trial_round_execution",
        "npi_core.trial_api.prepare_trial_round",
        "npi_core.trial_api.start_trial_round",
        "npi_core.trial_api.append_trial_actual_revision",
        "npi_core.trial_api.create_trial_sample_batch",
        "npi_core.trial_api.append_trial_sample_batch_revision",
        "npi_core.trial_api.upload_trial_evidence_file",
        "npi_core.trial_api.bind_trial_evidence",
        "npi_core.trial_api.read_trial_evidence_content",
    }


def _p7_03_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_03_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and command in {
        "npi_core.trial_api.get_trial_quality_workspace",
        "npi_core.trial_api.create_trial_cavity_result",
        "npi_core.trial_api.revise_trial_cavity_result",
        "npi_core.trial_api.create_trial_defect",
        "npi_core.trial_api.revise_trial_defect",
        "npi_core.trial_api.verify_trial_defect",
    }


def _p7_04_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_04_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and command in {
        "npi_core.trial_api.get_trial_review_workspace",
        "npi_core.trial_api.begin_trial_analysis",
        "npi_core.trial_api.create_trial_comparison",
        "npi_core.trial_api.create_trial_review_reference",
        "npi_core.trial_api.submit_trial_conclusion",
        "npi_core.trial_api.decide_trial_conclusion",
        "npi_core.trial_api.reopen_trial_conclusion",
    }


def _p7_05_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_05_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and command in {
        "npi_core.readiness_api.get_readiness_templates",
        "npi_core.readiness_api.create_readiness_template",
        "npi_core.readiness_api.edit_readiness_template",
        "npi_core.readiness_api.publish_readiness_template",
        "npi_core.readiness_api.get_project_readiness",
        "npi_core.readiness_api.initialize_project_readiness",
        "npi_core.readiness_api.revise_project_readiness",
    }


def _p7_06_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_06_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and (
        isinstance(command, str)
        and command.startswith("npi_core.production_transition_api.")
        and command
        != "npi_core.production_transition_api.production_transition_routes_disabled"
    )


def _p7_07_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_07_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and command in {
        "npi_core.released_summary_api.get_released_trial_summaries",
        "npi_core.released_summary_api.retain_released_trial_summary",
        "npi_core.released_summary_api.revise_released_trial_summary",
    }


def _p9_01_routes_disabled(command: str | None) -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p9_01_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False and command in {
        "npi_core.change_control_api.get_engineering_changes",
        "npi_core.change_control_api.get_engineering_change",
        "npi_core.change_control_api.create_engineering_change",
        "npi_core.change_control_api.revise_engineering_change",
        "npi_core.change_control_api.link_engineering_change_formal_observation",
        "npi_core.change_control_api.close_engineering_change",
    }


def _p5_01_routes_disabled(command: str | None) -> bool:
    return document_routes_are_disabled() and (
        isinstance(command, str) and command.startswith("npi_core.document_api.")
    )


def _is_npi_api_path(path: str) -> bool:
    normalized_path = path.rstrip("/") or "/"
    return normalized_path == "/api/npi/v1" or normalized_path.startswith(
        "/api/npi/v1/"
    )


def _normalize_pre_handler_problem(response, request) -> bool:
    """Normalize narrowly identified failures raised before the BFF route hook."""
    request = request or getattr(getattr(frappe, "local", None), "request", None)
    if not request or not _is_npi_api_path(getattr(request, "path", "")):
        return False

    flags = getattr(frappe, "flags", None)
    if (
        getattr(flags, "npi_response_headers", None)
        or getattr(flags, "npi_response_body", None) is not None
    ):
        return False

    response_metadata = getattr(getattr(frappe, "local", None), "response", None)
    exception_type = (
        response_metadata.get("exc_type") if hasattr(response_metadata, "get") else None
    )
    response_status = getattr(response, "status_code", None)
    if exception_type == "CSRFTokenError" and response_status in {400, 403}:
        problem_error = CsrfTokenInvalid()
    elif (
        exception_type in {"JSONDecodeError", "ValidationError"}
        and isinstance(response_status, int)
        and response_status >= 400
    ):
        problem_error = MalformedRequest()
    else:
        return False

    trace_id = resolve_trace_id(frappe.get_request_header("X-Trace-ID"))
    problem = problem_error.as_dict(trace_id)
    headers = {
        "Cache-Control": "private, no-store",
        "Content-Type": "application/problem+json",
        "X-Trace-ID": trace_id,
    }
    if _requires_project_request_id(request.method, request.path.rstrip("/")):
        headers["X-Request-ID"] = response_request_id()
    frappe.flags.npi_response_body = problem
    frappe.flags.npi_response_headers = headers
    response.status_code = problem["status"]
    response.set_data(json.dumps(problem, ensure_ascii=False, separators=(",", ":")))
    for name, value in headers.items():
        response.headers[name] = value
    return True


def _requires_project_request_id(method: str, path: str) -> bool:
    if method == "POST" and path == "/api/npi/v1/projects":
        return True
    if _is_p7_06_request(method, path):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_RELEASED_TRIAL_SUMMARIES_ROUTE.fullmatch(path) is not None
        or _PROJECT_RELEASED_TRIAL_SUMMARY_REVISE_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and path == "/api/npi/v1/me/work":
        return True
    if (
        method in {"GET", "POST"}
        and path == "/api/npi/v1/npi-readiness/templates"
    ):
        return True
    if (
        (method == "PUT" and _READINESS_TEMPLATE_VERSION_ROUTE.fullmatch(path))
        or (
            method == "POST"
            and _READINESS_TEMPLATE_PUBLISH_ROUTE.fullmatch(path)
        )
        or (
            method in {"GET", "POST"}
            and _PROJECT_READINESS_ROUTE.fullmatch(path)
        )
        or (
            method == "POST"
            and _PROJECT_READINESS_REVISIONS_ROUTE.fullmatch(path)
        )
    ):
        return True
    if method in {"GET", "POST"} and any(
        route.fullmatch(path) is not None
        for route in (
            _PROJECT_ENGINEERING_CHANGES_ROUTE,
            _PROJECT_ENGINEERING_CHANGE_ROUTE,
            _PROJECT_ENGINEERING_CHANGE_REVISIONS_ROUTE,
            _PROJECT_ENGINEERING_CHANGE_OBSERVATION_ROUTE,
            _PROJECT_ENGINEERING_CHANGE_CLOSE_ROUTE,
        )
    ):
        return True
    if (
        method in {"GET", "PUT"}
        and path == "/api/npi/v1/me/preferences/my-work-grid"
    ):
        return True
    if (
        method in {"GET", "PUT"}
        and path == "/api/npi/v1/me/preferences/my-work-inspector"
    ):
        return True
    if method == "GET" and (
        _PROJECT_COCKPIT_ROUTE.fullmatch(path) is not None
        or _PROJECT_WORK_CONTEXT_ROUTE.fullmatch(path) is not None
        or _PROJECT_ERP_PROJECTIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_FORMAL_QUALITY_LINKS_ROUTE.fullmatch(path) is not None
        or _PROJECT_FORMAL_QUALITY_LINK_ROUTE.fullmatch(path) is not None
        or _PROJECT_INTEGRATION_OPERATIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_INTEGRATION_OPERATION_DLQ_ROUTE.fullmatch(path) is not None
        or _PROJECT_INTEGRATION_OPERATION_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _PROJECT_INTEGRATION_OPERATION_COMMAND_ROUTES
    ):
        return True
    if method == "POST" and (
        _PROJECT_FORMAL_QUALITY_LINK_COMMAND_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_DOMAIN_WORK_ITEMS_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and _PROJECT_MEETINGS_ROUTE.fullmatch(path) is not None:
        return True
    if method == "POST" and _NOTIFICATION_MARK_READ_ROUTE.fullmatch(path) is not None:
        return True
    if method in {"GET", "PUT"} and path == "/api/npi/v1/me/preferences/notifications":
        return True
    if method == "GET" and path == "/api/npi/v1/notifications":
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_TRIALS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_PLAN_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_PLAN_REVISIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_PLAN_ROUNDS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_PLAN_ACTIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_EXECUTION_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_PREPARE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_START_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_ACTUAL_REVISIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_SAMPLE_BATCHES_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_SAMPLE_REVISIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_FILES_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_EVIDENCE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_EVIDENCE_CONTENT_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_QUALITY_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_CAVITY_RESULTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_CAVITY_RESULT_REVISIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_DEFECTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_DEFECT_REVISIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TRIAL_DEFECT_VERIFICATIONS_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_TOOLING_IMPORTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_INSPECTIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_MAPPINGS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_PREVIEWS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_CONFIRMATIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_EXECUTE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_JOBS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_JOB_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_JOB_RETRY_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_CORRECTIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_CORRECTION_CONTENT_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_RECONCILE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_ROLLBACK_ELIGIBILITY_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_IMPORT_ROLLBACK_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "PUT", "POST"} and (
        _PROJECT_TOOLING_LIST_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_LIST_PREFERENCE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_EXPORTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_EXPORT_CONTENT_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_TOOLING_SETS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_SET_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_SET_INTAKES_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_INTAKE_EVIDENCE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_REVISIONS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_REVISION_ROUTE.fullmatch(path) is not None
        or _PROJECT_PART_CONTROLLED_SPECIFICATION_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_PROCESS_CHAINS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_PROCESS_CHAIN_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_SET_REVISION_BINDING_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_MANUFACTURING_PLANS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_MANUFACTURING_PLAN_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOLING_MANUFACTURING_OBSERVATIONS_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and (
        _PROJECT_TOOL_ASSET_EXECUTION_REQUESTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOL_ASSET_EXECUTION_REQUEST_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and (
        _PROJECT_TOOL_ASSET_EXECUTION_CREATE_ROUTE.fullmatch(path) is not None
        or _PROJECT_TOOL_ASSET_EXECUTION_UPDATE_ROUTE.fullmatch(path) is not None
    ):
        return True
    if (
        (method == "GET" and _CONTROLLED_PRINT_CAPABILITY_ROUTE.fullmatch(path))
        or (method == "POST" and _PROJECT_CONTROLLED_PRINTS_ROUTE.fullmatch(path))
        or (method == "GET" and _PROJECT_CONTROLLED_PRINT_ROUTE.fullmatch(path))
        or (
            method == "GET"
            and _PROJECT_CONTROLLED_PRINT_CONTENT_ROUTE.fullmatch(path)
        )
    ):
        return True
    if method == "GET" and (
        path == "/api/npi/v1/learning"
        or _PROJECT_CONTROLS_ROUTE.fullmatch(path) is not None
        or _PROJECT_ACTIVITY_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and _PROJECT_COMMENTS_ROUTE.fullmatch(path) is not None:
        return True
    if (
        method in {"GET", "POST"}
        and _PROJECT_LEARNING_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and _GATE_EVIDENCE_ROUTE.fullmatch(path) is not None:
        return True
    if method == "GET" and _GATE_REVIEW_ROUTE.fullmatch(path) is not None:
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_DOCUMENTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_DOCUMENT_BASELINES_ROUTE.fullmatch(path) is not None
        or _PROJECT_EBOMS_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and (
        _PROJECT_EBOM_ROUTE.fullmatch(path) is not None
        or _EBOM_COMPARE_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _EBOM_PUBLISH_REQUESTS_ROUTE.fullmatch(path) is not None
        or _EBOM_PUBLISH_REQUEST_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_ITEM_PUBLISH_REQUESTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_ITEM_PUBLISH_REQUEST_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_MBOM_PUBLISH_REQUESTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_MBOM_PUBLISH_REQUEST_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and (
        _PROJECT_DOCUMENT_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_FILE_CAPABILITIES_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and (
        _DOCUMENT_CHECK_OUT_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_CHECK_IN_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_RECOVER_LOCK_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_REVISIONS_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_FILE_CONTENT_ROUTE.fullmatch(path) is not None
        or any(
            route.fullmatch(path) is not None
            for route, _command in _DOCUMENT_RELEASE_COMMAND_ROUTES
        )
    ):
        return True
    if method == "POST" and (
        _EBOM_REVISIONS_ROUTE.fullmatch(path) is not None
        or any(
            route.fullmatch(path) is not None
            for route, _command in _EBOM_COMMAND_ROUTES
        )
    ):
        return True
    if (
        method == "GET"
        and _GATE_REVIEW_COMMAND_RECEIPT_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and (
        _GATE_REQUIREMENT_FREEZE_ROUTE.fullmatch(path) is not None
        or _GATE_EVIDENCE_ATTACH_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _GATE_REVIEW_COMMAND_ROUTES
    ):
        return True
    if method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _PROJECT_WORK_COMMAND_ROUTES
    ):
        return True
    return method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _PROJECT_CONTROL_COMMAND_ROUTES
    )


def _is_p7_06_request(method: str, path: str) -> bool:
    if path == "/api/npi/v1/production-transition/policies":
        return method in {"GET", "POST"}
    if method == "PUT" and _PRODUCTION_TRANSITION_POLICY_VERSION_ROUTE.fullmatch(path):
        return True
    if method == "POST" and (
        _PRODUCTION_TRANSITION_POLICY_PUBLISH_ROUTE.fullmatch(path)
        or _PRODUCTION_TRANSITION_POLICY_VERSIONS_ROUTE.fullmatch(path)
        or _PROJECT_PRODUCTION_HANDOVER_ROUTE.fullmatch(path)
        or _PROJECT_PRODUCTION_HANDOVER_REVISIONS_ROUTE.fullmatch(path)
        or _PROJECT_PRODUCTION_HANDOVER_ACKNOWLEDGEMENTS_ROUTE.fullmatch(path)
        or _PROJECT_OBSERVATION_PERIODS_ROUTE.fullmatch(path)
        or _PROJECT_OBSERVATION_PERIOD_REVISIONS_ROUTE.fullmatch(path)
    ):
        return True
    return (
        method == "GET"
        and _PROJECT_PRODUCTION_TRANSITION_ROUTE.fullmatch(path) is not None
    )


def attach_response_headers(response=None, request=None) -> None:
    """Replace Frappe's RPC envelope and attach real NPI HTTP headers."""
    if response is None:
        return
    if _normalize_pre_handler_problem(response, request):
        return
    flags = getattr(frappe, "flags", None)
    body = getattr(flags, "npi_response_body", None)
    headers = getattr(flags, "npi_response_headers", None)
    if body is not None:
        response.set_data(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
        body_status = body.get("status") if isinstance(body, dict) else None
        body_type = body.get("type") if isinstance(body, dict) else None
        if (
            isinstance(headers, dict)
            and headers.get("Content-Type") == "application/problem+json"
            and type(body_status) is int
            and 400 <= body_status <= 599
            and isinstance(body_type, str)
            and body_type.startswith("urn:npi:problem:")
        ):
            response.status_code = body_status
    if not headers:
        return
    for name, value in headers.items():
        response.headers[name] = value
