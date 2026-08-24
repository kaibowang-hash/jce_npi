import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ErpProjectionsRequestCancelledError,
  type ErpProjectionCollectionViewModel,
  type ErpProjectionItemViewModel,
} from "../api/erp-projections-data-source";
import {
  confirmedToolAssetProjection,
  LiveToolingAcceptanceAssetDataSource,
  type ToolingAcceptanceAssetDataSource,
} from "../api/tooling-acceptance-asset-data-source";
import {
  confirmedToolAssetExecutionProjection,
  LiveToolAssetExecutionDataSource,
  type ToolAssetExecutionCollection,
  type ToolAssetExecutionContext,
  type ToolAssetExecutionDataSource,
  type ToolAssetExecutionDetail,
} from "../api/tool-asset-execution-data-source";
import {
  TOOL_ASSET_MOCK_ACKNOWLEDGEMENT,
  toolingAcceptanceCategories,
  type CreateToolAssetRequestCommand,
  type CreateToolingAcceptanceEvidenceRevisionCommand,
  type ToolingAcceptanceAssetContextViewModel,
  type ToolingAcceptanceCategory,
  type ToolingAcceptanceChecklistItemInputViewModel,
  type ToolingAcceptanceEvidenceRevisionViewModel,
  type ToolingCommandContext,
  type ToolingDataSource,
  type ToolingEvidenceDisposition,
  type ToolingMasterSummaryViewModel,
  type ToolingRevisionCollectionViewModel,
  type ToolingSetCollectionViewModel,
} from "../api/tooling-data-source";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import {
  formatDate,
  formatDateTime,
  formatDecimal,
  formatNumber,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: WorkspaceResources }
  | { kind: "failed"; failure: RequestFailure };
type AssetProjectionResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: ErpProjectionCollectionViewModel }
  | { kind: "failed"; failure: RequestFailure };
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface WorkspaceResources {
  acceptance: ToolingAcceptanceAssetContextViewModel;
  requests: Awaited<ReturnType<ToolingDataSource["loadToolAssetRequests"]>>;
  revisions: ToolingRevisionCollectionViewModel;
  sets: ToolingSetCollectionViewModel;
}

interface ChecklistDraft {
  category: ToolingAcceptanceCategory;
  disposition: ToolingEvidenceDisposition;
  evidence: ToolingAcceptanceChecklistItemInputViewModel["evidence"];
  fileRevisionGlobalId: string;
  fileOptimisticVersion: string;
  frappeContentHash: string;
  note: string;
  requirementKey: string;
  requirementStatement: string;
  sha256: string;
}

interface AcceptanceDraft {
  acceptanceGlobalId: string;
  expectedVersion: string;
  reason: string;
  setId: string;
  checklist: ChecklistDraft[];
}

type ExecutionResource =
  | { kind: "loading" }
  | {
      kind: "loaded";
      collection: ToolAssetExecutionCollection;
      detail: ToolAssetExecutionDetail | null;
    }
  | { kind: "failed"; failure: RequestFailure };

const liveToolAssetExecutionDataSource = new LiveToolAssetExecutionDataSource();

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function categorySource(category: ToolingAcceptanceCategory): string {
  switch (category) {
    case "technical":
      return "Technical requirements";
    case "quality":
      return "Quality requirements";
    case "cycle_capacity":
      return "Cycle and capacity requirements";
    case "spares_maintenance":
      return "Spares and maintenance requirements";
    case "documents":
      return "Controlled document requirements";
    case "warranty_responsibility":
      return "Warranty and responsibility requirements";
    case "cost":
      return "Cost requirements";
    case "safety_interface":
      return "Safety and interface requirements";
    case "asset_location":
      return "Asset and location requirements";
  }
}

function categoryLabel(
  t: ReturnType<typeof useI18n>["t"],
  category: ToolingAcceptanceCategory,
): string {
  switch (category) {
    case "technical":
      return t("Technical requirements");
    case "quality":
      return t("Quality requirements");
    case "cycle_capacity":
      return t("Cycle and capacity requirements");
    case "spares_maintenance":
      return t("Spares and maintenance requirements");
    case "documents":
      return t("Controlled document requirements");
    case "warranty_responsibility":
      return t("Warranty and responsibility requirements");
    case "cost":
      return t("Cost requirements");
    case "safety_interface":
      return t("Safety and interface requirements");
    case "asset_location":
      return t("Asset and location requirements");
  }
}

function dispositionLabel(
  t: ReturnType<typeof useI18n>["t"],
  disposition: ToolingEvidenceDisposition,
): string {
  switch (disposition) {
    case "evidence_recorded":
      return t("Evidence recorded");
    case "evidence_missing":
      return t("Evidence missing");
    case "not_applicable_asserted":
      return t("Not applicable with reason");
  }
}

function checklistDraft(
  predecessor: ToolingAcceptanceEvidenceRevisionViewModel | null,
): ChecklistDraft[] {
  return toolingAcceptanceCategories.map((category) => {
    const previous = predecessor?.checklist.find(
      (item) => item.category === category,
    );
    const evidence = previous?.evidence[0];
    return {
      category,
      disposition: previous?.disposition ?? "evidence_missing",
      evidence:
        previous?.evidence.map((item) => ({
          fileOptimisticVersion: item.fileOptimisticVersion,
          fileRevisionGlobalId: item.fileRevisionGlobalId,
          frappeContentHash: item.frappeContentHash,
          role: item.role,
          sha256: item.sha256,
        })) ?? [],
      fileOptimisticVersion: evidence
        ? String(evidence.fileOptimisticVersion)
        : "1",
      fileRevisionGlobalId: evidence?.fileRevisionGlobalId ?? "",
      frappeContentHash: evidence?.frappeContentHash ?? "",
      note: previous?.note ?? "",
      requirementKey: previous?.requirementKey ?? `acceptance.${category}`,
      requirementStatement:
        previous?.requirementStatement ?? categorySource(category),
      sha256: evidence?.sha256 ?? "",
    };
  });
}

function latestByAcceptance(
  values: readonly ToolingAcceptanceEvidenceRevisionViewModel[],
): readonly ToolingAcceptanceEvidenceRevisionViewModel[] {
  const latest = new Map<string, ToolingAcceptanceEvidenceRevisionViewModel>();
  for (const value of values) {
    const current = latest.get(value.acceptanceGlobalId);
    if (!current || current.acceptanceVersion < value.acceptanceVersion)
      latest.set(value.acceptanceGlobalId, value);
  }
  return [...latest.values()].sort((left, right) =>
    left.acceptanceGlobalId.localeCompare(right.acceptanceGlobalId),
  );
}

function newAcceptanceDraft(
  setId: string,
  predecessor: ToolingAcceptanceEvidenceRevisionViewModel | null,
): AcceptanceDraft {
  return {
    acceptanceGlobalId: predecessor?.acceptanceGlobalId ?? "",
    checklist: checklistDraft(predecessor),
    expectedVersion: predecessor ? String(predecessor.acceptanceVersion) : "",
    reason: "",
    setId,
  };
}

const liveAssetProjectionDataSource =
  new LiveToolingAcceptanceAssetDataSource();

function assetObservationStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  item: ErpProjectionItemViewModel,
): string {
  if (item.availability === "unavailable") return t("Unavailable observation");
  if (item.availability === "synthetic") return t("Synthetic observation");
  if (item.freshness === "stale") return t("Stale observation");
  if (item.freshness === "unknown") return t("Unknown freshness");
  switch (item.disposition) {
    case "applied_current":
      return t("Current observation");
    case "unavailable_current":
      return t("Unavailable observation");
    case "superseded":
      return t("Superseded observation");
    case "duplicate_exact":
      return t("Exact duplicate");
    case "conflicted":
      return t("Conflicted observation");
    case "synthetic_retained":
      return t("Synthetic observation");
  }
}

function assetMovementLabel(
  t: ReturnType<typeof useI18n>["t"],
  action: "move" | "loan" | "return" | "archive" | "scrap",
): string {
  switch (action) {
    case "move":
      return t("Move");
    case "loan":
      return t("Loan");
    case "return":
      return t("Return");
    case "archive":
      return t("Archive");
    case "scrap":
      return t("Scrap");
  }
}

function AssetProjectionPanel({
  preferredSetId,
  resource,
  retry,
  setIds,
}: {
  preferredSetId: string | undefined;
  resource: AssetProjectionResourceState;
  retry: () => void;
  setIds: ReadonlySet<string>;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (resource.kind === "loading") {
    return (
      <div
        aria-busy="true"
        aria-label={t("Loading ERPNext Asset projection")}
        className="workspace-resource-state workspace-resource-state--loading"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <span className="visually-hidden">
          {t("Loading ERPNext Asset projection")}
        </span>
      </div>
    );
  }
  if (resource.kind === "failed") {
    const denied =
      resource.failure.problem?.status === 401 ||
      resource.failure.problem?.status === 403;
    return (
      <div className="tooling-acceptance__projection-unavailable" role="alert">
        <SemanticStatus
          label={denied ? t("No permission") : t("Error")}
          tone="danger"
        />
        <strong>
          {denied
            ? t("ERPNext Asset projection access is not available.")
            : t("ERPNext Asset projection could not be used safely.")}
        </strong>
        <span className="tooling-acceptance__projection-detail">
          {t("No protected formal Asset values were displayed.")}
        </span>
        <RequestFailurePanel failure={resource.failure} />
        {canRetry(resource.failure) ? (
          <Button icon="refresh" onClick={retry}>
            {t("Retry")}
          </Button>
        ) : null}
      </div>
    );
  }
  if (resource.value.accessState === "redacted") {
    return (
      <div className="tooling-acceptance__projection-unavailable" role="status">
        <SemanticStatus label={t("No permission")} tone="warning" />
        <strong>
          {t("ERPNext Asset projection access is not available.")}
        </strong>
        <span className="tooling-acceptance__projection-detail">
          {t("No protected formal Asset values were displayed.")}
        </span>
      </div>
    );
  }
  const scopedItems = resource.value.items.filter(
    (item) =>
      item.projectionKind === "tool_asset_status" &&
      item.scopeKind === "tooling_set" &&
      setIds.has(item.scopeGlobalId),
  );
  const item =
    scopedItems.find(
      (candidate) => candidate.scopeGlobalId === preferredSetId,
    ) ?? scopedItems[0];
  if (!item) {
    return (
      <div className="tooling-acceptance__projection-unavailable" role="status">
        <SemanticStatus label={t("Unavailable")} tone="warning" />
        <strong>
          {t("Formal Asset mapping has not been observed from ERPNext.")}
        </strong>
        <span className="tooling-acceptance__projection-detail">
          {t(
            "Mapping cardinality is zero or one formal Asset per physical Set.",
          )}
        </span>
        <span className="tooling-acceptance__projection-detail">
          {t(
            "ERPNext remains the only editable system for Asset and location truth.",
          )}
        </span>
      </div>
    );
  }
  const confirmed = confirmedToolAssetProjection(item);
  if (!confirmed) {
    return (
      <div className="tooling-acceptance__projection-unavailable" role="status">
        <SemanticStatus
          label={assetObservationStateLabel(t, item)}
          tone={item.disposition === "conflicted" ? "danger" : "warning"}
        />
        <strong>{t("Formal Asset value withheld")}</strong>
        <span className="tooling-acceptance__projection-detail">
          {t(
            "Only a fresh, confirmed current observation can display formal Asset truth.",
          )}
        </span>
        {item.unavailableReasonCode ? (
          <span className="tooling-acceptance__projection-detail">
            {t("Reason code")}:{" "}
            <span data-language-exempt="identifier">
              {item.unavailableReasonCode}
            </span>
          </span>
        ) : null}
      </div>
    );
  }
  const asset = confirmed.values;
  return (
    <div className="tooling-acceptance__formal-asset">
      <div className="scenario-banner" role="status">
        <SemanticStatus label={t("Confirmed current")} tone="success" />
        <span>
          {t("This formal Asset projection is read only and owned by ERPNext.")}
        </span>
      </div>
      <DefinitionList
        rows={[
          {
            label: t("Physical Set ID"),
            value: asset.toolingSetGlobalId,
            exempt: "identifier",
          },
          {
            label: t("Formal Asset ID"),
            value: asset.formalAssetId,
            exempt: "identifier",
          },
          {
            label: t("Asset state"),
            value: asset.assetState,
            exempt: "identifier",
          },
          {
            label: t("Current location"),
            value: asset.currentLocation,
            exempt: "business-data",
          },
          {
            label: t("Shot count"),
            value: formatNumber(locale, asset.shotCount, 0),
          },
          {
            label: t("Expected life shots"),
            value:
              asset.expectedLifeShots === null
                ? t("Not provided")
                : formatNumber(locale, asset.expectedLifeShots, 0),
          },
          {
            label: t("Maintenance due"),
            value:
              asset.maintenanceDue === null
                ? t("Not provided")
                : formatDate(locale, asset.maintenanceDue),
          },
          {
            label: t("Target version"),
            value: asset.targetVersion,
            exempt: "identifier",
          },
          {
            label: t("Source modified at"),
            value: formatDateTime(
              locale,
              confirmed.item.sourceModifiedAt ?? "",
            ),
          },
          {
            label: t("Received at"),
            value: formatDateTime(locale, confirmed.item.receivedAt),
          },
        ]}
      />
      {asset.movements.length ? (
        <div className="table-scroll" tabIndex={0}>
          <table className="data-table data-table--compact">
            <caption>{t("Asset movements")}</caption>
            <thead>
              <tr>
                <th>{t("Action")}</th>
                <th>{t("From location")}</th>
                <th>{t("To location")}</th>
                <th>{t("Occurred at")}</th>
              </tr>
            </thead>
            <tbody>
              {asset.movements.map((movement) => (
                <tr key={movement.globalId}>
                  <td>{assetMovementLabel(t, movement.actionKind)}</td>
                  <td data-language-exempt="business-data">
                    {movement.fromLocation ?? t("Not provided")}
                  </td>
                  <td data-language-exempt="business-data">
                    {movement.toLocation ?? t("Not provided")}
                  </td>
                  <td>{formatDateTime(locale, movement.occurredAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {asset.repairs.length ? (
        <div className="table-scroll" tabIndex={0}>
          <table className="data-table data-table--compact">
            <caption>{t("Asset repairs")}</caption>
            <thead>
              <tr>
                <th>{t("Summary")}</th>
                <th>{t("Downtime hours")}</th>
                <th>{t("Completed at")}</th>
              </tr>
            </thead>
            <tbody>
              {asset.repairs.map((repair) => (
                <tr key={repair.globalId}>
                  <td data-language-exempt="business-data">{repair.summary}</td>
                  <td>{formatDecimal(locale, repair.downtimeHours)}</td>
                  <td>{formatDateTime(locale, repair.completedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {asset.spares.length ? (
        <div className="table-scroll" tabIndex={0}>
          <table className="data-table data-table--compact">
            <caption>{t("Asset spares")}</caption>
            <thead>
              <tr>
                <th>{t("Formal Item ID")}</th>
                <th>{t("Description")}</th>
                <th>{t("Stock on hand")}</th>
                <th>{t("Minimum stock")}</th>
              </tr>
            </thead>
            <tbody>
              {asset.spares.map((spare) => (
                <tr key={spare.formalItemId}>
                  <td data-language-exempt="identifier">
                    {spare.formalItemId}
                  </td>
                  <td data-language-exempt="business-data">
                    {spare.description}
                  </td>
                  <td>
                    {formatDecimal(locale, spare.stockOnHand)}{" "}
                    <span data-language-exempt="unit">{spare.unit}</span>
                  </td>
                  <td>
                    {formatDecimal(locale, spare.minimumStock)}{" "}
                    <span data-language-exempt="unit">{spare.unit}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function executionStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ToolAssetExecutionDetail["request"]["state"],
): string {
  switch (state) {
    case "failed_final":
      return t("Failed final");
    case "failed_retryable":
      return t("Failed retryable");
    case "mapping_conflict":
      return t("Mapping conflict");
    case "partially_succeeded":
      return t("Partially succeeded");
    case "processing":
      return t("Processing");
    case "queued":
      return t("Queued");
    case "succeeded":
      return t("Succeeded");
    case "synthetic_verified":
      return t("Synthetic verified");
    case "uncertain_after_timeout":
      return t("Uncertain after timeout");
    case "validated_mock":
      return t("Validated Mock");
  }
}

function executionOperationLabel(
  t: ReturnType<typeof useI18n>["t"],
  operation: "create_tool_asset" | "update_tool_asset",
): string {
  return operation === "create_tool_asset"
    ? t("Create formal Asset")
    : t("Update formal Asset");
}

function executionProfileLabel(
  t: ReturnType<typeof useI18n>["t"],
  mode: "mock" | "synthetic" | "sandbox",
): string {
  if (mode === "sandbox") return t("Sandbox");
  if (mode === "synthetic") return t("Synthetic");
  return t("Mock");
}

function fieldCodeLabel(
  t: ReturnType<typeof useI18n>["t"],
  code: string,
): string {
  if (code === "tooling_master_title") return t("Tooling Master title");
  if (code === "physical_set_serial") return t("Physical Set serial");
  if (code === "tooling_requirement_kind") return t("Tooling requirement kind");
  if (code === "source_tooling_revision") return t("Source Tooling Revision");
  return t("Acceptance evidence reference");
}

function fieldStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: string,
): string {
  if (state === "succeeded_authoritative") return t("Succeeded authoritative");
  if (state === "synthetic_verified") return t("Synthetic verified");
  if (state === "uncertain_after_timeout") return t("Uncertain after timeout");
  if (state === "observed_conflict") return t("Observed conflict");
  if (state === "failed_retryable") return t("Failed retryable");
  return t("Failed final");
}

function authorityLabel(
  t: ReturnType<typeof useI18n>["t"],
  authority: "none" | "synthetic" | "authoritative_sandbox",
): string {
  if (authority === "authoritative_sandbox") return t("Authoritative Sandbox");
  if (authority === "synthetic") return t("Synthetic");
  return t("No target authority");
}

function ToolAssetExecutionInspector({
  acceptanceId,
  assetProjectionResource,
  dataSource,
  masterId,
  projectId,
  sessionCommandContext,
  setId,
}: {
  acceptanceId: string;
  assetProjectionResource: AssetProjectionResourceState;
  dataSource: ToolAssetExecutionDataSource;
  masterId: string;
  projectId: string;
  sessionCommandContext: ReturnType<typeof useI18n>["sessionCommandContext"];
  setId: string;
}): React.JSX.Element {
  const { t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ExecutionResource>({
    kind: "loading",
  });
  const [review, setReview] = useState<ToolAssetExecutionContext | null>(null);
  const [commandFailure, setCommandFailure] = useState<RequestFailure | null>(
    null,
  );
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadRequests(projectId, masterId, setId, acceptanceId, controller.signal)
      .then(async (collection) => {
        const latest = collection.items[0] ?? null;
        const detail = latest
          ? await dataSource.loadRequest(
              projectId,
              masterId,
              setId,
              latest.requestGlobalId,
              controller.signal,
            )
          : null;
        if (!controller.signal.aborted)
          setResource({ kind: "loaded", collection, detail });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [acceptanceId, attempt, dataSource, masterId, projectId, setId]);

  if (resource.kind === "loading") {
    return (
      <div
        aria-busy="true"
        className="tool-asset-execution__state"
        role="status"
      >
        {t("Loading Tool Asset execution truth")}
      </div>
    );
  }
  if (resource.kind === "failed") {
    return (
      <div className="tool-asset-execution__state">
        <SemanticStatus
          label={
            resource.failure.problem?.status === 403
              ? t("No permission")
              : t("Tool Asset execution unavailable")
          }
          tone="warning"
        />
        <RequestFailurePanel failure={resource.failure} />
      </div>
    );
  }
  const { collection, detail } = resource;
  const contexts = collection.commandContexts
    ? Object.values(collection.commandContexts).filter(
        (value): value is ToolAssetExecutionContext => Boolean(value),
      )
    : [];
  const context = contexts.length === 1 ? (contexts[0] ?? null) : null;
  const permitted =
    context?.operation === "create_tool_asset"
      ? collection.permissions.canCreate
      : context?.operation === "update_tool_asset"
        ? collection.permissions.canUpdate
        : false;
  const blockReason = !sessionCommandContext
    ? t("A signed-in command session is required.")
    : collection.businessApproval.state !== "verified"
      ? t("Separate ERP business approval is unavailable.")
      : collection.executionProfile === null
        ? t("The Tool Asset execution profile is unavailable.")
        : contexts.length > 1
          ? t("Create and update authority conflict; no request is permitted.")
          : !context
            ? t("No exact create or update mapping context is available.")
            : !permitted
              ? t("You do not have permission to request this operation.")
              : null;
  const projectionItem =
    assetProjectionResource.kind === "loaded"
      ? (assetProjectionResource.value.items.find(
          (item) => item.scopeGlobalId === setId,
        ) ?? null)
      : null;
  const confirmedProjection = projectionItem
    ? confirmedToolAssetProjection(projectionItem)
    : null;
  const currentMapping = detail
    ? confirmedToolAssetExecutionProjection(detail, confirmedProjection)
    : null;
  const submit = (): void => {
    if (!review || !sessionCommandContext) return;
    setReview(null);
    setProcessing(true);
    setCommandFailure(null);
    const controller = new AbortController();
    void dataSource
      .createRequest(projectId, masterId, setId, review, {
        ...sessionCommandContext,
        idempotencyKey: `tool-asset-${globalThis.crypto.randomUUID()}`,
        signal: controller.signal,
      })
      .then(() => {
        setProcessing(false);
        setResource({ kind: "loading" });
        setAttempt((value) => value + 1);
      })
      .catch((error: unknown) => {
        setProcessing(false);
        setCommandFailure(toRequestFailure(error));
      });
  };
  return (
    <div
      className="tool-asset-execution"
      data-tool-asset-execution-state={detail?.request.state ?? "empty"}
    >
      <div className="tool-asset-execution__summary">
        <div className="tool-asset-execution__summary-item">
          <span className="tool-asset-execution__summary-label">
            {t("Execution truth")}
          </span>
          <SemanticStatus
            label={
              detail
                ? executionStateLabel(t, detail.request.state)
                : t("No request recorded")
            }
            tone={
              detail?.request.state === "succeeded"
                ? "success"
                : detail?.request.state.startsWith("failed")
                  ? "danger"
                  : "neutral"
            }
          />
        </div>
        <div className="tool-asset-execution__summary-item">
          <span className="tool-asset-execution__summary-label">
            {t("Operation")}
          </span>
          <strong className="tool-asset-execution__summary-value">
            {detail
              ? executionOperationLabel(t, detail.request.operation)
              : t("Not requested")}
          </strong>
        </div>
        <div className="tool-asset-execution__summary-item">
          <span className="tool-asset-execution__summary-label">
            {t("Acceptance evidence")}
          </span>
          <strong className="tool-asset-execution__summary-value">
            {t("Recorded in NPI One")}
          </strong>
        </div>
        <div className="tool-asset-execution__summary-item">
          <span className="tool-asset-execution__summary-label">
            {t("ERP business approval")}
          </span>
          <strong className="tool-asset-execution__summary-value">
            {collection.businessApproval.state === "verified"
              ? t("Verified")
              : t("Unavailable")}
          </strong>
        </div>
        <div className="tool-asset-execution__summary-item">
          <span className="tool-asset-execution__summary-label">
            {t("Execution profile")}
          </span>
          <strong className="tool-asset-execution__summary-value">
            {collection.executionProfile
              ? executionProfileLabel(t, collection.executionProfile.targetMode)
              : t("Unavailable")}
          </strong>
        </div>
        <div className="tool-asset-execution__summary-item">
          <span className="tool-asset-execution__summary-label">
            {t("Formal Asset mapping")}
          </span>
          <strong
            className="tool-asset-execution__summary-value"
            data-language-exempt={currentMapping ? "identifier" : undefined}
          >
            {currentMapping?.formalAssetId ??
              t("Withheld until authoritative current truth")}
          </strong>
        </div>
      </div>
      {detail?.fieldResults.length ? (
        <div
          aria-label={t("Per-field execution results")}
          className="table-scroll"
          tabIndex={0}
        >
          <table className="data-table tool-asset-execution__table">
            <thead>
              <tr>
                <th className="tool-asset-execution__cell">
                  {t("Owned field")}
                </th>
                <th className="tool-asset-execution__cell">
                  {t("Execution result")}
                </th>
                <th className="tool-asset-execution__cell">{t("Authority")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.fieldResults.map((field) => (
                <tr key={field.fieldCode}>
                  <td className="tool-asset-execution__cell">
                    {fieldCodeLabel(t, field.fieldCode)}
                  </td>
                  <td className="tool-asset-execution__cell">
                    <SemanticStatus
                      label={fieldStateLabel(t, field.state)}
                      tone={
                        field.state === "succeeded_authoritative"
                          ? "success"
                          : field.state.startsWith("failed")
                            ? "danger"
                            : "warning"
                      }
                    />
                  </td>
                  <td className="tool-asset-execution__cell">
                    {authorityLabel(t, field.authority)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>{t("No per-field execution result is available.")}</p>
      )}
      <div className="tool-asset-execution__action">
        <div>
          <strong>{t("Request exact Tool Asset execution")}</strong>
          <p>
            {t(
              "Impact: commits one immutable create or update request and, outside Mock, one recoverable Outbox event. It does not approve, move or maintain an Asset.",
            )}
          </p>
          {blockReason ? <small>{blockReason}</small> : null}
        </div>
        <Button
          data-tool-asset-request-action="true"
          disabled={Boolean(blockReason) || processing}
          onClick={() => {
            if (context) setReview(context);
          }}
          visual="primary"
        >
          {t("Review Tool Asset request")}
        </Button>
      </div>
      {commandFailure ? (
        <div role="alert">
          <SemanticStatus label={t("Command failed")} tone="danger" />
          <RequestFailurePanel failure={commandFailure} />
        </div>
      ) : null}
      {review ? (
        <ImpactReview
          title={t("Review exact Tool Asset request")}
          confirmLabel={t("Request Tool Asset execution")}
          reasonRequired={false}
          returnFocusTarget={() =>
            document.querySelector<HTMLElement>(
              '[data-tool-asset-request-action="true"]',
            )
          }
          onCancel={() => {
            setReview(null);
          }}
          onConfirm={submit}
          details={{
            objectIdentity: t("Exact physical Tooling Set"),
            version: review.expectedSourceHash,
            impact: t(
              "Commit one immutable operation-specific request and one recoverable Outbox event when execution is enabled.",
            ),
            permission: t(
              "Project membership, separate business approval and exact profile requester authority are required.",
            ),
            irreversible: t(
              "The request, audit, observed field truth and mapping evidence remain immutable.",
            ),
            failureHandling: t(
              "Partial, failed and uncertain truth remains visible. No retry or reconcile command is available here.",
            ),
            audit: t(
              "Actor, trace, idempotency, source and mapping expectation hashes are recorded.",
            ),
          }}
          contextRows={[
            {
              label: t("Operation"),
              value: executionOperationLabel(t, review.operation),
            },
            { label: t("Physical Set"), value: setId, exempt: "identifier" },
          ]}
        />
      ) : null}
    </div>
  );
}

export default function ToolingAcceptanceAssetWorkspace({
  assetProjectionDataSource = liveAssetProjectionDataSource,
  executionDataSource = liveToolAssetExecutionDataSource,
  dataSource,
  master,
  projectId,
  reportWorkspaceDirty,
}: {
  assetProjectionDataSource?: ToolingAcceptanceAssetDataSource | undefined;
  executionDataSource?: ToolAssetExecutionDataSource | undefined;
  dataSource: ToolingDataSource;
  master: ToolingMasterSummaryViewModel;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [assetProjectionAttempt, setAssetProjectionAttempt] = useState(0);
  const [assetProjectionResource, setAssetProjectionResource] =
    useState<AssetProjectionResourceState>({ kind: "loading" });
  const [draft, setDraft] = useState<AcceptanceDraft | null>(null);
  const [selectedAcceptanceId, setSelectedAcceptanceId] = useState<string>("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const retryCommand = useRef<(() => void) | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      dataSource.loadAcceptanceAssets(
        projectId,
        master.globalId,
        controller.signal,
      ),
      dataSource.loadToolAssetRequests(
        projectId,
        master.globalId,
        controller.signal,
      ),
      dataSource.loadSets(projectId, master.globalId, controller.signal),
      dataSource.loadToolingRevisions(
        projectId,
        master.globalId,
        controller.signal,
      ),
    ])
      .then(([acceptance, requests, sets, revisions]) => {
        if (controller.signal.aborted) return;
        setResource({
          kind: "loaded",
          value: { acceptance, requests, revisions, sets },
        });
        setSelectedAcceptanceId((current) =>
          current !== ""
            ? current
            : (latestByAcceptance(acceptance.acceptanceRevisions).at(-1)
                ?.globalId ?? ""),
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, master.globalId, projectId]);

  useEffect(() => {
    const controller = new AbortController();
    void assetProjectionDataSource
      .loadAssetProjections(projectId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted)
          setAssetProjectionResource({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ErpProjectionsRequestCancelledError
        )
          return;
        setAssetProjectionResource({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      });
    return () => {
      controller.abort();
    };
  }, [assetProjectionAttempt, assetProjectionDataSource, projectId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!draft) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: `${master.globalId}:acceptance-assets`,
      returnFocusTarget: () => editorTrigger.current,
      version: "unsaved-tooling-acceptance-evidence",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [draft, master.globalId, reportWorkspaceDirty]);

  const loaded = resource.kind === "loaded" ? resource.value : null;
  const latestAcceptances = useMemo(
    () => latestByAcceptance(loaded?.acceptance.acceptanceRevisions ?? []),
    [loaded?.acceptance.acceptanceRevisions],
  );
  const selectedAcceptance =
    latestAcceptances.find((item) => item.globalId === selectedAcceptanceId) ??
    latestAcceptances.at(-1) ??
    null;
  const selectedSet = loaded?.sets.items.find(
    (item) => item.globalId === selectedAcceptance?.toolingSetGlobalId,
  );
  const processing = command.kind === "processing";
  const canRecord = Boolean(
    loaded?.acceptance.permissions.recordEvidence && sessionCommandContext,
  );
  const canPrepareMock = Boolean(
    loaded?.acceptance.permissions.prepareMockAssetRequest &&
    sessionCommandContext &&
    selectedAcceptance,
  );

  const reload = useCallback(() => {
    setResource({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, []);

  const runCommand = useCallback(
    <T,>(
      label: string,
      prefix: string,
      operation: (context: ToolingCommandContext) => Promise<T>,
      after: (value: T) => void = () => undefined,
    ): void => {
      if (!sessionCommandContext) return;
      const idempotencyKey = `${prefix}-${globalThis.crypto.randomUUID()}`;
      const execute = (): void => {
        const controller = new AbortController();
        setCommand({ kind: "processing", label });
        void operation({
          ...sessionCommandContext,
          idempotencyKey,
          signal: controller.signal,
        })
          .then((value) => {
            after(value);
            setDraft(null);
            setFormError(null);
            setAcknowledged(false);
            setCommand({ kind: "idle" });
            reload();
          })
          .catch((error: unknown) => {
            if (
              !controller.signal.aborted &&
              !(error instanceof ToolingRequestCancelledError)
            )
              setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      retryCommand.current = execute;
      execute();
    },
    [reload, sessionCommandContext],
  );

  const openAcceptance = (
    trigger: HTMLElement,
    setId: string,
    predecessor: ToolingAcceptanceEvidenceRevisionViewModel | null,
  ): void => {
    editorTrigger.current = trigger;
    setDraft(newAcceptanceDraft(setId, predecessor));
    setFormError(null);
  };

  const submitAcceptance = (): void => {
    if (!loaded || !draft || !sessionCommandContext) return;
    const toolingSet = loaded.sets.items.find(
      (item) => item.globalId === draft.setId,
    );
    if (!toolingSet || "state" in toolingSet.sourceRevision) {
      setFormError(
        t(
          "Select a physical Tooling Set with an exact Tooling Revision binding.",
        ),
      );
      return;
    }
    const binding = toolingSet.sourceRevision;
    const revision = loaded.revisions.items.find(
      (item) => item.globalId === binding.toolingRevisionGlobalId,
    );
    const invalidItem = draft.checklist.some((item) => {
      if (item.disposition === "evidence_recorded") {
        return (
          !item.fileRevisionGlobalId.trim() ||
          !Number.isInteger(Number(item.fileOptimisticVersion)) ||
          Number(item.fileOptimisticVersion) < 1 ||
          !item.frappeContentHash.trim() ||
          !item.sha256.trim()
        );
      }
      if (item.disposition === "not_applicable_asserted")
        return !item.note.trim();
      return false;
    });
    if (!revision || !draft.reason.trim() || invalidItem) {
      setFormError(
        t("Complete the exact acceptance evidence fields and append reason."),
      );
      return;
    }
    const checklist: ToolingAcceptanceChecklistItemInputViewModel[] =
      draft.checklist.map((item) => ({
        category: item.category,
        disposition: item.disposition,
        evidence:
          item.disposition === "evidence_recorded"
            ? [
                {
                  fileOptimisticVersion: Number(item.fileOptimisticVersion),
                  fileRevisionGlobalId: item.fileRevisionGlobalId.trim(),
                  frappeContentHash: item.frappeContentHash.trim(),
                  role: "checklist",
                  sha256: item.sha256.trim(),
                },
                ...item.evidence.slice(1),
              ]
            : [],
        note: item.note.trim() || null,
        requirementKey: item.requirementKey,
        requirementStatement: item.requirementStatement,
        responsibleMember: null,
      }));
    const commandValue: CreateToolingAcceptanceEvidenceRevisionCommand = {
      ...(draft.acceptanceGlobalId
        ? {
            acceptanceGlobalId: draft.acceptanceGlobalId,
            expectedVersion: Number(draft.expectedVersion),
          }
        : {}),
      assetActions: [],
      checklist,
      reason: draft.reason.trim(),
      repairs: [],
      setRevisionBindingGlobalId: binding.globalId,
      setRevisionBindingSnapshotHash: binding.snapshotHash,
      spareRecommendations: [],
      toolingRevisionGlobalId: revision.globalId,
      toolingRevisionNumber: revision.revisionNumber,
      toolingRevisionSnapshotHash: revision.snapshotHash,
      toolingSetGlobalId: toolingSet.globalId,
      toolingSetSnapshotHash: toolingSet.snapshotHash,
    };
    runCommand(
      t("Appending immutable acceptance evidence Revision"),
      "tooling-acceptance",
      (context) =>
        dataSource.createToolingAcceptanceRevision(
          projectId,
          master.globalId,
          commandValue,
          context,
        ),
      (created) => {
        setSelectedAcceptanceId(created.globalId);
      },
    );
  };

  const submitMockRequest = (): void => {
    if (
      !loaded ||
      !selectedAcceptance ||
      !selectedSet ||
      !sessionCommandContext ||
      !acknowledged
    ) {
      setFormError(
        t(
          "Confirm the Mock-only acknowledgement before preparing the request.",
        ),
      );
      return;
    }
    if ("state" in selectedSet.sourceRevision) {
      setFormError(
        t(
          "The selected acceptance evidence no longer has an exact Set binding.",
        ),
      );
      return;
    }
    const commandValue: CreateToolAssetRequestCommand = {
      acceptanceRevisionGlobalId: selectedAcceptance.globalId,
      acceptanceSnapshotHash: selectedAcceptance.snapshotHash,
      acceptanceVersion: selectedAcceptance.acceptanceVersion,
      acknowledgement: TOOL_ASSET_MOCK_ACKNOWLEDGEMENT,
      expectedBindingSnapshotHash:
        selectedAcceptance.setRevisionBindingSnapshotHash,
      expectedToolingMasterSnapshotHash: master.snapshotHash,
      expectedToolingRevisionNumber: selectedAcceptance.toolingRevisionNumber,
      expectedToolingRevisionSnapshotHash:
        selectedAcceptance.toolingRevisionSnapshotHash,
      expectedToolingSetSnapshotHash: selectedAcceptance.toolingSetSnapshotHash,
      targetMode: "mock",
    };
    runCommand(
      t("Preparing local Mock Asset request"),
      "tooling-asset-mock",
      (context) =>
        dataSource.createToolAssetRequest(
          projectId,
          master.globalId,
          selectedSet.globalId,
          commandValue,
          context,
        ),
    );
  };

  if (resource.kind === "loading") {
    return (
      <section
        aria-busy="true"
        aria-label={t("Loading acceptance and Asset workspace")}
        className="workspace-resource-state workspace-resource-state--loading"
        id="tooling-acceptance-asset-workspace"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <span className="visually-hidden">
          {t("Loading acceptance and Asset workspace")}
        </span>
      </section>
    );
  }

  if (resource.kind === "failed") {
    return (
      <section id="tooling-acceptance-asset-workspace">
        <RequestFailurePanel failure={resource.failure} />
        <Button onClick={reload}>
          {t("Retry acceptance and Asset workspace")}
        </Button>
      </section>
    );
  }

  const value = resource.value;
  const boundSets = value.sets.items.filter(
    (item) => !("state" in item.sourceRevision),
  );

  return (
    <section
      aria-label={t("Acceptance evidence and Asset preparation")}
      className="tooling-acceptance"
      id="tooling-acceptance-asset-workspace"
    >
      <header className="tooling-acceptance__header">
        <div>
          <span className="eyebrow">{t("Tooling assurance")}</span>
          <h2>{t("Acceptance evidence and Asset preparation")}</h2>
          <p>
            {t(
              "Record immutable evidence by physical Set, then validate a local Mock request without inferring approval or ERPNext execution.",
            )}
          </p>
        </div>
        <div className="tooling-acceptance__status-strip">
          <SemanticStatus label={t("Approval unavailable")} tone="warning" />
          <SemanticStatus label={t("Mock validation only")} tone="info" />
          <SemanticStatus label={t("Dispatch prohibited")} tone="neutral" />
        </div>
      </header>

      {!sessionCommandContext &&
      (value.acceptance.permissions.recordEvidence ||
        value.acceptance.permissions.prepareMockAssetRequest) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Acceptance and Asset commands are read only in this session.")}
          </span>
          <span>
            {t(
              "Session verification is required before a command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {!value.acceptance.permissions.recordEvidence &&
      !value.acceptance.permissions.prepareMockAssetRequest ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Acceptance and Asset evidence is read only for this user.")}
          </span>
          <span>
            {t("The server controls evidence and Mock-request permissions.")}
          </span>
        </div>
      ) : null}
      {command.kind === "processing" ? (
        <div
          aria-busy="true"
          className="scenario-banner scenario-banner--processing"
          role="status"
        >
          <span>{command.label}</span>
          <span>
            {t("The command is processing. Keep this workspace open.")}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <div className="tooling-command-failure">
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button
              disabled={processing}
              onClick={() => retryCommand.current?.()}
            >
              {t("Retry exact command")}
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="tooling-acceptance__truth-grid">
        <Panel title={t("Acceptance evidence lineage")}>
          {latestAcceptances.length ? (
            <div
              aria-label={t("Acceptance evidence lineage")}
              className="table-scroll"
              tabIndex={0}
            >
              <table className="data-table tooling-acceptance__lineage-table">
                <thead>
                  <tr>
                    <th>{t("Physical Set")}</th>
                    <th>{t("Evidence Revision")}</th>
                    <th>{t("Recorded")}</th>
                    <th>{t("Missing")}</th>
                    <th>{t("Not applicable")}</th>
                    <th>{t("Actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {latestAcceptances.map((item) => {
                    const set = value.sets.items.find(
                      (candidate) =>
                        candidate.globalId === item.toolingSetGlobalId,
                    );
                    const recorded = item.categoryCoverage.reduce(
                      (total, category) => total + category.recordedCount,
                      0,
                    );
                    const missing = item.categoryCoverage.reduce(
                      (total, category) => total + category.missingCount,
                      0,
                    );
                    const notApplicable = item.categoryCoverage.reduce(
                      (total, category) => total + category.notApplicableCount,
                      0,
                    );
                    return (
                      <tr
                        aria-selected={
                          selectedAcceptance?.globalId === item.globalId
                        }
                        className="tooling-acceptance__lineage-row"
                        key={item.globalId}
                      >
                        <td data-language-exempt="business-data">
                          {set?.physicalSerial ?? item.toolingSetGlobalId}
                        </td>
                        <td data-language-exempt="identifier">
                          {t("Revision {{version}}", {
                            version: formatNumber(
                              locale,
                              item.acceptanceVersion,
                              0,
                            ),
                          })}
                        </td>
                        <td>{formatNumber(locale, recorded, 0)}</td>
                        <td>{formatNumber(locale, missing, 0)}</td>
                        <td>{formatNumber(locale, notApplicable, 0)}</td>
                        <td>
                          <div className="table-actions">
                            <Button
                              disabled={processing}
                              onClick={() => {
                                setSelectedAcceptanceId(item.globalId);
                              }}
                              visual="secondary"
                            >
                              {t("Inspect")}
                            </Button>
                            <Button
                              disabled={!canRecord || processing}
                              onClick={(event) => {
                                openAcceptance(
                                  event.currentTarget,
                                  item.toolingSetGlobalId,
                                  item,
                                );
                              }}
                              visual="secondary"
                            >
                              {t("Append Revision")}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state" role="status">
              <strong>
                {t("No acceptance evidence Revision has been recorded.")}
              </strong>
              <span>
                {t(
                  "Start with a physical Set that has an exact Tooling Revision binding.",
                )}
              </span>
            </div>
          )}
          {boundSets.length ? (
            <div className="tooling-acceptance__start-actions">
              {boundSets.map((item) => (
                <Button
                  disabled={!canRecord || processing}
                  key={item.globalId}
                  onClick={(event) => {
                    openAcceptance(event.currentTarget, item.globalId, null);
                  }}
                  visual="secondary"
                >
                  {t("Record evidence for {{serial}}", {
                    serial: item.physicalSerial,
                  })}
                </Button>
              ))}
            </div>
          ) : (
            <p>
              {t("No physical Set has an exact Tooling Revision binding yet.")}
            </p>
          )}
        </Panel>

        <Panel title={t("Acceptance truth inspector")}>
          <div
            aria-label={t("Acceptance truth inspector")}
            className="tooling-acceptance__inspector-scroll"
            tabIndex={0}
          >
            {selectedAcceptance ? (
              <>
                <DefinitionList
                  rows={[
                    {
                      label: t("Stable acceptance identity"),
                      value: selectedAcceptance.acceptanceGlobalId,
                      exempt: "identifier",
                    },
                    {
                      label: t("Evidence Revision"),
                      value: formatNumber(
                        locale,
                        selectedAcceptance.acceptanceVersion,
                        0,
                      ),
                    },
                    {
                      label: t("Tooling Revision"),
                      value: formatNumber(
                        locale,
                        selectedAcceptance.toolingRevisionNumber,
                        0,
                      ),
                    },
                    {
                      label: t("Recorded by"),
                      value: selectedAcceptance.createdByUserId,
                      exempt: "business-data",
                    },
                    {
                      label: t("Recorded at"),
                      value: formatDateTime(
                        locale,
                        selectedAcceptance.createdAt,
                      ),
                    },
                    {
                      label: t("Snapshot hash"),
                      value: selectedAcceptance.snapshotHash,
                      exempt: "identifier",
                    },
                  ]}
                />
                <div className="tooling-acceptance__coverage">
                  {selectedAcceptance.categoryCoverage.map((item) => (
                    <div
                      className="tooling-acceptance__coverage-row"
                      key={item.category}
                    >
                      <strong>{categoryLabel(t, item.category)}</strong>
                      <span className="tooling-acceptance__coverage-summary">
                        {t(
                          "{{recorded}} recorded · {{missing}} missing · {{notApplicable}} not applicable",
                          {
                            missing: formatNumber(locale, item.missingCount, 0),
                            notApplicable: formatNumber(
                              locale,
                              item.notApplicableCount,
                              0,
                            ),
                            recorded: formatNumber(
                              locale,
                              item.recordedCount,
                              0,
                            ),
                          },
                        )}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="tooling-acceptance__related-counts">
                  <span>
                    {t("Asset actions: {{count}}", {
                      count: formatNumber(
                        locale,
                        selectedAcceptance.assetActions.length,
                        0,
                      ),
                    })}
                  </span>
                  <span>
                    {t("Spare recommendations: {{count}}", {
                      count: formatNumber(
                        locale,
                        selectedAcceptance.spareRecommendations.length,
                        0,
                      ),
                    })}
                  </span>
                  <span>
                    {t("Repair records: {{count}}", {
                      count: formatNumber(
                        locale,
                        selectedAcceptance.repairs.length,
                        0,
                      ),
                    })}
                  </span>
                </div>
              </>
            ) : (
              <p>
                {t(
                  "Select an acceptance evidence Revision to inspect exact provenance.",
                )}
              </p>
            )}
          </div>
        </Panel>
      </div>

      <div className="tooling-acceptance__asset-grid">
        <Panel title={t("Mock Asset request preparation")}>
          <div className="tooling-acceptance__axis-grid">
            {(
              [
                [t("Target mode"), t("Mock")],
                [t("Request state"), t("Draft")],
                [t("Input validation"), t("Validated Mock")],
                [t("Business approval"), t("Unavailable")],
                [t("Dispatch"), t("Prohibited")],
                [t("Target result"), t("Not requested")],
              ] as const
            ).map(([label, state]) => (
              <div className="tooling-acceptance__axis" key={label}>
                <span className="tooling-acceptance__axis-label">{label}</span>
                <strong>{state}</strong>
              </div>
            ))}
          </div>
          {latestAcceptances.length ? (
            <label>
              <span>{t("Acceptance evidence Revision")}</span>
              <Select
                disabled={processing}
                onChange={(event) => {
                  setSelectedAcceptanceId(event.currentTarget.value);
                  setAcknowledged(false);
                }}
                value={selectedAcceptance?.globalId ?? ""}
              >
                {latestAcceptances.map((item) => {
                  const set = value.sets.items.find(
                    (candidate) =>
                      candidate.globalId === item.toolingSetGlobalId,
                  );
                  return (
                    <option key={item.globalId} value={item.globalId}>
                      {set?.physicalSerial} ·{" "}
                      {t("Revision {{version}}", {
                        version: formatNumber(
                          locale,
                          item.acceptanceVersion,
                          0,
                        ),
                      })}
                    </option>
                  );
                })}
              </Select>
            </label>
          ) : null}
          <label className="tooling-acceptance__acknowledgement">
            <input
              checked={acknowledged}
              disabled={!canPrepareMock || processing}
              onChange={(event) => {
                setAcknowledged(event.currentTarget.checked);
              }}
              type="checkbox"
            />
            <span>
              {t(
                "I confirm this only validates a local Mock draft. It does not approve Tooling, contact ERPNext or create an Asset.",
              )}
            </span>
          </label>
          <Button
            disabled={!canPrepareMock || !acknowledged || processing}
            onClick={submitMockRequest}
            visual="secondary"
          >
            {t("Prepare Mock Asset request")}
          </Button>
          <small className="tooling-acceptance__note">
            {t(
              "This command cannot approve Tooling, dispatch a request, contact ERPNext or create a formal Asset.",
            )}
          </small>
        </Panel>

        <Panel title={t("Tool Asset execution inspector")}>
          {selectedAcceptance && selectedSet ? (
            <ToolAssetExecutionInspector
              acceptanceId={selectedAcceptance.globalId}
              assetProjectionResource={assetProjectionResource}
              dataSource={executionDataSource}
              masterId={master.globalId}
              projectId={projectId}
              sessionCommandContext={sessionCommandContext}
              setId={selectedSet.globalId}
            />
          ) : (
            <p>
              {t(
                "Select exact acceptance evidence and a physical Tooling Set to inspect execution truth.",
              )}
            </p>
          )}
        </Panel>

        <Panel title={t("ERPNext Asset projection")}>
          <AssetProjectionPanel
            preferredSetId={selectedSet?.globalId}
            resource={assetProjectionResource}
            retry={() => {
              setAssetProjectionResource({ kind: "loading" });
              setAssetProjectionAttempt((current) => current + 1);
            }}
            setIds={new Set(value.sets.items.map((item) => item.globalId))}
          />
        </Panel>
      </div>

      <Panel title={t("Prepared Mock request audit")}>
        {value.requests.items.length ? (
          <div
            aria-label={t("Prepared Mock request audit")}
            className="table-scroll"
            tabIndex={0}
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Request")}</th>
                  <th>{t("Physical Set")}</th>
                  <th>{t("Validation")}</th>
                  <th>{t("Dispatch")}</th>
                  <th>{t("Created at")}</th>
                </tr>
              </thead>
              <tbody>
                {value.requests.items.map((item) => (
                  <tr key={item.globalId}>
                    <td data-language-exempt="identifier">{item.globalId}</td>
                    <td data-language-exempt="business-data">
                      {item.requestInput.toolingSetPhysicalSerial}
                    </td>
                    <td>{t("Validated Mock")}</td>
                    <td>{t("Prohibited")}</td>
                    <td>{formatDateTime(locale, item.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>{t("No local Mock Asset request has been prepared.")}</p>
        )}
      </Panel>

      {draft ? (
        <Panel
          title={
            draft.acceptanceGlobalId
              ? t("Append acceptance evidence Revision")
              : t("Record acceptance evidence")
          }
        >
          <form
            className="tooling-acceptance__editor"
            onSubmit={(event) => {
              event.preventDefault();
              submitAcceptance();
            }}
          >
            <div className="tooling-acceptance__editor-meta">
              <label>
                <span>{t("Physical Tooling Set")}</span>
                <Select disabled value={draft.setId}>
                  {value.sets.items.map((item) => (
                    <option key={item.globalId} value={item.globalId}>
                      {item.physicalSerial}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                <span>{t("Append reason")}</span>
                <TextInput
                  disabled={processing}
                  onChange={(event) => {
                    setDraft({ ...draft, reason: event.currentTarget.value });
                  }}
                  value={draft.reason}
                />
              </label>
            </div>
            <div className="tooling-acceptance__checklist">
              {draft.checklist.map((item, index) => (
                <fieldset key={item.category}>
                  <legend>{categoryLabel(t, item.category)}</legend>
                  <label>
                    <span>{t("Evidence disposition")}</span>
                    <Select
                      disabled={processing}
                      onChange={(event) => {
                        const checklist = [...draft.checklist];
                        checklist[index] = {
                          ...item,
                          disposition: event.currentTarget
                            .value as ToolingEvidenceDisposition,
                        };
                        setDraft({ ...draft, checklist });
                      }}
                      value={item.disposition}
                    >
                      {(
                        [
                          "evidence_recorded",
                          "evidence_missing",
                          "not_applicable_asserted",
                        ] as const
                      ).map((disposition) => (
                        <option key={disposition} value={disposition}>
                          {dispositionLabel(t, disposition)}
                        </option>
                      ))}
                    </Select>
                  </label>
                  {item.disposition === "evidence_recorded" ? (
                    <div className="tooling-acceptance__file-grid">
                      {(
                        [
                          ["fileRevisionGlobalId", t("File Revision identity")],
                          [
                            "fileOptimisticVersion",
                            t("File optimistic version"),
                          ],
                          ["frappeContentHash", t("Frappe content hash")],
                          ["sha256", t("SHA-256")],
                        ] as const
                      ).map(([field, label]) => (
                        <label key={field}>
                          <span>{label}</span>
                          <TextInput
                            disabled={processing}
                            onChange={(event) => {
                              const checklist = [...draft.checklist];
                              checklist[index] = {
                                ...item,
                                [field]: event.currentTarget.value,
                              };
                              setDraft({ ...draft, checklist });
                            }}
                            value={item[field]}
                          />
                        </label>
                      ))}
                    </div>
                  ) : null}
                  {item.disposition === "not_applicable_asserted" ? (
                    <label>
                      <span>{t("Exact not-applicable reason")}</span>
                      <TextInput
                        disabled={processing}
                        onChange={(event) => {
                          const checklist = [...draft.checklist];
                          checklist[index] = {
                            ...item,
                            note: event.currentTarget.value,
                          };
                          setDraft({ ...draft, checklist });
                        }}
                        value={item.note}
                      />
                    </label>
                  ) : null}
                </fieldset>
              ))}
            </div>
            {formError ? (
              <p className="form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="form-actions">
              <Button disabled={!canRecord || processing} type="submit">
                {draft.acceptanceGlobalId
                  ? t("Append evidence Revision")
                  : t("Record evidence Revision")}
              </Button>
              <Button
                disabled={processing}
                onClick={() => {
                  setDraft(null);
                  setFormError(null);
                  editorTrigger.current?.focus();
                }}
                type="button"
                visual="secondary"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
    </section>
  );
}
