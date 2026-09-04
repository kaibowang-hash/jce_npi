import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentWorkspaceViewModel,
  DocumentDataSource,
} from "../api/document-data-source";
import type {
  CreateToolingIntakeCommand,
  ToolingCommandContext,
  ToolingDataSource,
  ToolingIntakeEvidenceRole,
  ToolingIntakeInspectionCategory,
  ToolingIntakeSummaryViewModel,
  ToolingRequirementSummaryViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingSetCollectionViewModel,
  ToolingSetDetailViewModel,
} from "../api/tooling-data-source";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "idle" | "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };
type EditorKind = "set" | "intake" | "evidence" | "binding";
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface AccessoryDraft {
  globalId: string;
  description: string;
  declaredQuantity: string;
  receivedQuantity: string;
  unit: string;
}

interface InspectionDraft {
  globalId: string;
  category: ToolingIntakeInspectionCategory;
  observation: string;
  differenceObserved: boolean;
  customerConfirmationRequired: boolean;
}

interface SetEditorState {
  kind: "set";
  toolingRequirementGlobalId: string;
  physicalSerial: string;
  customerSourceSystem: "" | "NPI_ONE" | "ERPNEXT";
  customerSourceObjectId: string;
  custodyResponsibility: string;
  repairAuthorizationReference: string;
  returnConditions: string;
}

interface IntakeEditorState {
  kind: "intake";
  transportProvider: string;
  transportReference: string;
  arrivedAt: string;
  custodyHandover: string;
  accessories: readonly AccessoryDraft[];
  inspections: readonly InspectionDraft[];
}

interface EvidenceEditorState {
  kind: "evidence";
  intakeGlobalId: string;
  evidenceRole: ToolingIntakeEvidenceRole;
  differenceGlobalIds: readonly string[];
  documentGlobalId: string;
  fileRevisionGlobalId: string;
}

interface BindingEditorState {
  kind: "binding";
  toolingRevisionGlobalId: string;
  reason: string;
}

type EditorState =
  | SetEditorState
  | IntakeEditorState
  | EvidenceEditorState
  | BindingEditorState;

const inspectionCategoryOrder = [
  "appearance",
  "water_circuit",
  "hot_runner",
  "electrical",
  "safety",
] as const;

function localDateTime(): string {
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000);
  return now.toISOString().slice(0, 16);
}

function newEditor(
  kind: EditorKind,
  requirements: readonly ToolingRequirementSummaryViewModel[],
  latestIntake: ToolingIntakeSummaryViewModel | null,
  revisions: ToolingRevisionCollectionViewModel | null,
): EditorState {
  if (kind === "set") {
    return {
      kind,
      toolingRequirementGlobalId: requirements[0]?.globalId ?? "",
      physicalSerial: "",
      customerSourceSystem: "",
      customerSourceObjectId: "",
      custodyResponsibility: "",
      repairAuthorizationReference: "",
      returnConditions: "",
    };
  }
  if (kind === "intake") {
    return {
      kind,
      transportProvider: "",
      transportReference: "",
      arrivedAt: localDateTime(),
      custodyHandover: "",
      accessories: [],
      inspections: inspectionCategoryOrder.map((category) => ({
        category,
        customerConfirmationRequired: false,
        differenceObserved: false,
        globalId: globalThis.crypto.randomUUID(),
        observation: "",
      })),
    };
  }
  if (kind === "binding") {
    return {
      kind,
      reason: "",
      toolingRevisionGlobalId: revisions?.items.at(-1)?.globalId ?? "",
    };
  }
  return {
    kind,
    intakeGlobalId: latestIntake?.globalId ?? "",
    evidenceRole: "arrival_photo",
    differenceGlobalIds: [],
    documentGlobalId: "",
    fileRevisionGlobalId: "",
  };
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function inspectionLabel(
  t: ReturnType<typeof useI18n>["t"],
  category: ToolingIntakeInspectionCategory,
): string {
  switch (category) {
    case "appearance":
      return t("Appearance");
    case "water_circuit":
      return t("Water circuit");
    case "hot_runner":
      return t("Hot runner");
    case "electrical":
      return t("Electrical");
    case "safety":
      return t("Safety");
  }
}

function evidenceRoleLabel(
  t: ReturnType<typeof useI18n>["t"],
  role: ToolingIntakeEvidenceRole,
): string {
  switch (role) {
    case "arrival_photo":
      return t("Arrival photo");
    case "transport_document":
      return t("Transport document");
    case "accessory_document":
      return t("Accessory document");
    case "inspection_evidence":
      return t("Inspection evidence");
    case "customer_confirmation":
      return t("Customer confirmation");
  }
}

function unavailableLabel(
  t: ReturnType<typeof useI18n>["t"],
  reason: string,
): string {
  switch (reason) {
    case "tooling_revision_not_delivered":
      return t("Tooling Revision is not delivered yet.");
    case "formal_supplier_unavailable":
      return t("Formal Supplier is not delivered yet.");
    case "lifecycle_policy_unavailable":
      return t("Lifecycle policy is not approved.");
    default:
      return t("ERPNext location and Asset projection are unavailable.");
  }
}

export default function ToolingSetWorkspace({
  dataSource,
  documentDataSource,
  masterId,
  projectId,
  revisionCapabilityAvailable = false,
  reportWorkspaceDirty,
  requirements,
}: {
  dataSource: ToolingDataSource;
  documentDataSource?:
    | Pick<DocumentDataSource, "loadDocuments" | "loadDocument">
    | undefined;
  masterId: string;
  projectId: string;
  revisionCapabilityAvailable?: boolean | undefined;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  requirements: readonly ToolingRequirementSummaryViewModel[];
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const eligibleRequirements = useMemo(
    () =>
      requirements.filter(
        (item) =>
          item.kind === "customer_owned_intake" ||
          item.kind === "copy_or_additional_set",
      ),
    [requirements],
  );
  const [attempt, setAttempt] = useState(0);
  const [collection, setCollection] = useState<
    ResourceState<ToolingSetCollectionViewModel>
  >({ kind: "loading" });
  const [selectedSetId, setSelectedSetId] = useState<string | null>(null);
  const [detail, setDetail] = useState<
    ResourceState<ToolingSetDetailViewModel>
  >({ kind: "idle" });
  const [revisionCollection, setRevisionCollection] = useState<
    ResourceState<ToolingRevisionCollectionViewModel>
  >(revisionCapabilityAvailable ? { kind: "loading" } : { kind: "idle" });
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const [documents, setDocuments] = useState<
    ResourceState<ControlledDocumentPageViewModel>
  >({ kind: "idle" });
  const [documentDetail, setDocumentDetail] = useState<
    ResourceState<ControlledDocumentWorkspaceViewModel>
  >({ kind: "idle" });
  const latestCommand = useRef<(() => void) | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);
  const loadedCollection =
    collection.kind === "loaded" ? collection.value : null;
  const loadedDetail = detail.kind === "loaded" ? detail.value : null;
  const selectedSet =
    loadedCollection?.items.find((item) => item.globalId === selectedSetId) ??
    loadedCollection?.items[0] ??
    null;
  const latestIntake = useMemo(
    () =>
      loadedDetail?.intakes
        .slice()
        .sort((left, right) => right.version - left.version)[0] ?? null,
    [loadedDetail?.intakes],
  );

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadSets(projectId, masterId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setCollection({ kind: "loaded", value });
        const firstSetId = value.items[0]?.globalId ?? null;
        setDetail(firstSetId ? { kind: "loading" } : { kind: "idle" });
        setSelectedSetId(firstSetId);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        ) {
          return;
        }
        setCollection({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, masterId, projectId]);

  useEffect(() => {
    if (!revisionCapabilityAvailable) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadToolingRevisions(projectId, masterId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted)
          setRevisionCollection({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ToolingRequestCancelledError)
        )
          setRevisionCollection({
            kind: "failed",
            failure: toRequestFailure(error),
          });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, masterId, projectId, revisionCapabilityAvailable]);

  useEffect(() => {
    if (!selectedSetId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadSet(projectId, masterId, selectedSetId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setDetail({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        ) {
          return;
        }
        setDetail({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, masterId, projectId, selectedSetId]);

  useEffect(() => {
    if (editor?.kind !== "evidence" || !documentDataSource) return undefined;
    const controller = new AbortController();
    void documentDataSource
      .loadDocuments(projectId, controller.signal, { limit: 100 })
      .then((value) => {
        if (!controller.signal.aborted) setDocuments({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setDocuments({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [documentDataSource, editor?.kind, projectId]);

  useEffect(() => {
    if (
      editor?.kind !== "evidence" ||
      !editor.documentGlobalId ||
      !documentDataSource
    )
      return undefined;
    const controller = new AbortController();
    void documentDataSource
      .loadDocument(projectId, editor.documentGlobalId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted)
          setDocumentDetail({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setDocumentDetail({
            kind: "failed",
            failure: toRequestFailure(error),
          });
      });
    return () => {
      controller.abort();
    };
  }, [documentDataSource, editor, projectId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: selectedSet?.globalId ?? `${masterId}:new-tooling-set`,
      returnFocusTarget: () => editorTrigger.current,
      version: "unsaved-tooling-set-context",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, masterId, reportWorkspaceDirty, selectedSet?.globalId]);

  const closeEditor = useCallback((): void => {
    setEditor(null);
    setFormError(null);
    setCommand({ kind: "idle" });
    globalThis.queueMicrotask(() => editorTrigger.current?.focus());
  }, []);

  const openEditor = (kind: EditorKind, trigger: HTMLElement): void => {
    editorTrigger.current = trigger;
    setEditor(
      newEditor(
        kind,
        eligibleRequirements,
        latestIntake,
        revisionCollection.kind === "loaded" ? revisionCollection.value : null,
      ),
    );
    setFormError(null);
    setCommand({ kind: "idle" });
    setDocuments(
      kind === "evidence" && documentDataSource
        ? { kind: "loading" }
        : { kind: "idle" },
    );
    setDocumentDetail({ kind: "idle" });
  };

  const commandContext = (
    prefix: string,
    session: { csrfToken: string },
  ): ((signal: AbortSignal) => ToolingCommandContext) => {
    const idempotencyKey = `${prefix}-${globalThis.crypto.randomUUID()}`;
    return (signal) => ({
      ...session,
      idempotencyKey,
      signal,
    });
  };

  const runCommand = useCallback(
    <T,>(
      label: string,
      operation: (signal: AbortSignal) => Promise<T>,
      accept: (value: T) => void,
    ): void => {
      const execute = (): void => {
        const controller = new AbortController();
        setCommand({ kind: "processing", label });
        void operation(controller.signal)
          .then((value) => {
            accept(value);
            setEditor(null);
            setFormError(null);
            setCommand({ kind: "idle" });
            globalThis.queueMicrotask(() => editorTrigger.current?.focus());
          })
          .catch((error: unknown) => {
            if (
              controller.signal.aborted ||
              error instanceof ToolingRequestCancelledError
            ) {
              return;
            }
            setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      latestCommand.current = execute;
      execute();
    },
    [],
  );

  const submit = (): void => {
    if (!editor || !sessionCommandContext) return;
    if (editor.kind === "set") {
      if (
        !editor.toolingRequirementGlobalId ||
        !editor.physicalSerial.trim() ||
        !editor.custodyResponsibility.trim() ||
        !editor.repairAuthorizationReference.trim() ||
        !editor.returnConditions.trim() ||
        (editor.customerSourceSystem && !editor.customerSourceObjectId.trim())
      ) {
        setFormError(t("Complete every required physical Set field."));
        return;
      }
      const context = commandContext("tooling-set", sessionCommandContext);
      const beforeIds = new Set(
        loadedCollection?.items.map((item) => item.globalId),
      );
      runCommand(
        t("Creating physical Tooling Set"),
        (signal) =>
          dataSource.createSet(
            projectId,
            masterId,
            {
              toolingRequirementGlobalId: editor.toolingRequirementGlobalId,
              physicalSerial: editor.physicalSerial.trim(),
              custodyResponsibility: editor.custodyResponsibility.trim(),
              repairAuthorizationReference:
                editor.repairAuthorizationReference.trim(),
              returnConditions: editor.returnConditions.trim(),
              ...(editor.customerSourceSystem
                ? {
                    customer: {
                      sourceObjectId: editor.customerSourceObjectId.trim(),
                      sourceSystem: editor.customerSourceSystem,
                    },
                  }
                : {}),
            },
            context(signal),
          ),
        (value) => {
          setCollection({ kind: "loaded", value });
          const createdSetId =
            value.items.find((item) => !beforeIds.has(item.globalId))
              ?.globalId ??
            value.items.at(-1)?.globalId ??
            null;
          setDetail(createdSetId ? { kind: "loading" } : { kind: "idle" });
          setSelectedSetId(createdSetId);
        },
      );
      return;
    }
    if (editor.kind === "intake") {
      if (
        !selectedSet ||
        !editor.transportProvider.trim() ||
        !editor.transportReference.trim() ||
        !editor.arrivedAt ||
        !editor.custodyHandover.trim() ||
        editor.inspections.some((item) => !item.observation.trim())
      ) {
        setFormError(
          t("Complete transport, handover and all five inspections."),
        );
        return;
      }
      const accessories = editor.accessories.map((item) => ({
        globalId: item.globalId,
        description: item.description.trim(),
        declaredQuantity: Number(item.declaredQuantity),
        receivedQuantity: Number(item.receivedQuantity),
        unit: item.unit.trim(),
      }));
      if (
        accessories.some(
          (item) =>
            !item.description ||
            !item.unit ||
            !Number.isInteger(item.declaredQuantity) ||
            item.declaredQuantity < 0 ||
            !Number.isInteger(item.receivedQuantity) ||
            item.receivedQuantity < 0,
        )
      ) {
        setFormError(t("Complete each accessory with nonnegative quantities."));
        return;
      }
      const inspections = editor.inspections.map((item) => ({
        category: item.category,
        differenceObserved: item.differenceObserved,
        globalId: item.globalId,
        observation: item.observation.trim(),
      }));
      const differences = editor.inspections
        .filter((item) => item.differenceObserved)
        .map((item) => ({
          customerConfirmationRequired: item.customerConfirmationRequired,
          description: item.observation.trim(),
          globalId: globalThis.crypto.randomUUID(),
          sourceGlobalId: item.globalId,
          sourceKind: "inspection" as const,
        }));
      const payload: CreateToolingIntakeCommand = {
        transportProvider: editor.transportProvider.trim(),
        transportReference: editor.transportReference.trim(),
        arrivedAt: new Date(editor.arrivedAt).toISOString(),
        custodyHandover: editor.custodyHandover.trim(),
        accessories,
        inspections,
        differences,
        ...(latestIntake ? { expectedVersion: latestIntake.version } : {}),
      };
      const context = commandContext("tooling-intake", sessionCommandContext);
      runCommand(
        t("Recording Tooling intake"),
        (signal) =>
          dataSource.createIntake(
            projectId,
            masterId,
            selectedSet.globalId,
            payload,
            context(signal),
          ),
        (value) => {
          setDetail({ kind: "loaded", value });
        },
      );
      return;
    }
    if (editor.kind === "binding") {
      if (
        !selectedSet ||
        !editor.toolingRevisionGlobalId ||
        !editor.reason.trim()
      ) {
        setFormError(
          t("Select one exact Tooling Revision and enter a reason."),
        );
        return;
      }
      const context = commandContext(
        "tooling-set-revision-binding",
        sessionCommandContext,
      );
      runCommand(
        t("Binding exact source Tooling Revision"),
        (signal) =>
          dataSource.createToolingSetRevisionBinding(
            projectId,
            masterId,
            selectedSet.globalId,
            {
              reason: editor.reason.trim(),
              toolingRevisionGlobalId: editor.toolingRevisionGlobalId,
            },
            context(signal),
          ),
        (value) => {
          setDetail({ kind: "loaded", value });
          setCollection((current) =>
            current.kind === "loaded"
              ? {
                  kind: "loaded",
                  value: {
                    ...current.value,
                    items: current.value.items.map((item) =>
                      item.globalId === value.toolingSet.globalId
                        ? value.toolingSet
                        : item,
                    ),
                  },
                }
              : current,
          );
        },
      );
      return;
    }
    const fileOptions =
      documentDetail.kind === "loaded"
        ? documentDetail.value.revisions.flatMap((revision) =>
            revision.files.filter(
              (file) =>
                file.scanState === "clean" &&
                file.capabilities.integrity.state === "available",
            ),
          )
        : [];
    const selectedFile = fileOptions.find(
      (file) => file.globalId === editor.fileRevisionGlobalId,
    );
    if (!selectedSet || !editor.intakeGlobalId || !selectedFile) {
      setFormError(t("Select one intake and one clean exact File Revision."));
      return;
    }
    const context = commandContext(
      "tooling-intake-evidence",
      sessionCommandContext,
    );
    runCommand(
      t("Attaching governed intake evidence"),
      (signal) =>
        dataSource.attachIntakeEvidence(
          projectId,
          masterId,
          selectedSet.globalId,
          editor.intakeGlobalId,
          {
            differenceGlobalIds: editor.differenceGlobalIds,
            evidenceRole: editor.evidenceRole,
            fileRevisionGlobalId: selectedFile.globalId,
          },
          context(signal),
        ),
      (value) => {
        setDetail({ kind: "loaded", value });
      },
    );
  };

  if (collection.kind !== "loaded") {
    if (collection.kind === "failed") {
      return (
        <Panel
          id="tooling-live-sets"
          title={t("Physical Tooling Sets and intake")}
        >
          <RequestFailurePanel failure={collection.failure} />
          {canRetry(collection.failure) ? (
            <Button
              onClick={() => {
                setCollection({ kind: "loading" });
                setAttempt((value) => value + 1);
              }}
            >
              {t("Retry")}
            </Button>
          ) : null}
        </Panel>
      );
    }
    return (
      <Panel
        id="tooling-live-sets"
        title={t("Physical Tooling Sets and intake")}
      >
        <p aria-busy="true" role="status">
          {t("Loading physical Tooling Sets")}
        </p>
      </Panel>
    );
  }

  const processing = command.kind === "processing";
  const canCreateSet =
    collection.value.permissions.createSet &&
    eligibleRequirements.length > 0 &&
    sessionCommandContext !== null;
  const canCreateIntake =
    Boolean(selectedSet) &&
    collection.value.permissions.createIntake &&
    sessionCommandContext !== null;
  const canAttachEvidence =
    Boolean(latestIntake) &&
    collection.value.permissions.attachEvidence &&
    documentDataSource !== undefined &&
    sessionCommandContext !== null;
  const canBindSourceRevision =
    Boolean(selectedSet) &&
    Boolean(
      loadedDetail && "state" in loadedDetail.toolingSet.sourceRevision,
    ) &&
    revisionCollection.kind === "loaded" &&
    revisionCollection.value.permissions.bindSetSource &&
    revisionCollection.value.items.length > 0 &&
    sessionCommandContext !== null;
  const fileOptions =
    documentDetail.kind === "loaded"
      ? documentDetail.value.revisions.flatMap((revision) =>
          revision.files.filter(
            (file) =>
              file.scanState === "clean" &&
              file.capabilities.integrity.state === "available",
          ),
        )
      : [];
  const evidenceIntake =
    editor?.kind === "evidence"
      ? (loadedDetail?.intakes.find(
          (item) => item.globalId === editor.intakeGlobalId,
        ) ?? null)
      : null;

  return (
    <Panel id="tooling-live-sets" title={t("Physical Tooling Sets and intake")}>
      <div className="tooling-set__toolbar">
        <div>
          <strong>{t("Physical Set repository")}</strong>
          <small>
            {t(
              "Set custody, arrival inspection, differences and exact file evidence are retained without lifecycle or ERPNext inference.",
            )}
          </small>
        </div>
        <div className="detail-actions">
          <Button
            disabled={!canCreateSet || processing}
            onClick={(event) => {
              openEditor("set", event.currentTarget);
            }}
          >
            {t("Create physical Set")}
          </Button>
          <Button
            disabled={!canCreateIntake || processing}
            onClick={(event) => {
              openEditor("intake", event.currentTarget);
            }}
          >
            {t("Record intake")}
          </Button>
          <Button
            disabled={!canAttachEvidence || processing}
            onClick={(event) => {
              openEditor("evidence", event.currentTarget);
            }}
          >
            {t("Attach evidence")}
          </Button>
          <Button
            disabled={!canBindSourceRevision || processing}
            onClick={(event) => {
              openEditor("binding", event.currentTarget);
            }}
          >
            {t("Bind source Tooling Revision")}
          </Button>
        </div>
      </div>
      {revisionCollection.kind === "failed" ? (
        <RequestFailurePanel failure={revisionCollection.failure} />
      ) : null}
      {!sessionCommandContext &&
      (collection.value.permissions.createSet ||
        collection.value.permissions.createIntake ||
        collection.value.permissions.attachEvidence) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          {t("Physical Set data is read only until this session is verified.")}
        </div>
      ) : null}
      {eligibleRequirements.length === 0 ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          {t(
            "Create a customer-owned intake or copy/additional Set requirement before recording a physical Set.",
          )}
        </div>
      ) : null}
      {command.kind === "processing" ? (
        <div
          aria-busy="true"
          className="scenario-banner scenario-banner--processing"
          role="status"
        >
          {command.label}
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <div className="tooling-command-failure">
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button onClick={() => latestCommand.current?.()}>
              {t("Retry exact command")}
            </Button>
          ) : null}
        </div>
      ) : null}
      {collection.value.items.length ? (
        <div
          aria-label={t("Physical Tooling Sets")}
          className="table-scroll"
          tabIndex={0}
        >
          <table className="data-table data-table--compact">
            <thead>
              <tr>
                <th>{t("Physical serial")}</th>
                <th>{t("Requirement kind")}</th>
                <th>{t("Customer")}</th>
                <th>{t("Intake versions")}</th>
                <th>{t("Evidence references")}</th>
              </tr>
            </thead>
            <tbody>
              {collection.value.items.map((item) => (
                <tr
                  aria-selected={selectedSet?.globalId === item.globalId}
                  key={item.globalId}
                >
                  <td>
                    <button
                      className="table-link"
                      data-language-exempt="business-data"
                      onClick={() => {
                        setDetail({ kind: "loading" });
                        setSelectedSetId(item.globalId);
                      }}
                      type="button"
                    >
                      {item.physicalSerial}
                    </button>
                  </td>
                  <td>
                    {item.requirementKind === "customer_owned_intake"
                      ? t("Customer-owned Tooling intake")
                      : t("Copy or additional Set")}
                  </td>
                  <td
                    data-language-exempt={
                      item.customer ? "business-data" : undefined
                    }
                  >
                    {item.customer?.sourceObjectId ?? t("Not linked")}
                  </td>
                  <td>
                    {selectedSet?.globalId === item.globalId && loadedDetail
                      ? formatNumber(locale, loadedDetail.intakes.length, 0)
                      : t("Select to inspect")}
                  </td>
                  <td>
                    {selectedSet?.globalId === item.globalId && loadedDetail
                      ? formatNumber(locale, loadedDetail.evidence.length, 0)
                      : t("Select to inspect")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state" role="status">
          <strong>
            {t("No physical Tooling Set has been recorded for this Master.")}
          </strong>
          <span>
            {t(
              "Physical Set truth remains empty; no downstream success is inferred.",
            )}
          </span>
        </div>
      )}
      {detail.kind === "loading" ? (
        <p aria-busy="true" role="status">
          {t("Loading exact Set intake history")}
        </p>
      ) : null}
      {detail.kind === "failed" ? (
        <RequestFailurePanel failure={detail.failure} />
      ) : null}
      {loadedDetail ? (
        <div className="tooling-set__detail-grid">
          <div className="tooling-set__history">
            <Panel title={t("Arrival intake history")}>
              {loadedDetail.intakes.length ? (
                <div className="table-scroll" tabIndex={0}>
                  <table className="data-table data-table--compact">
                    <thead>
                      <tr>
                        <th>{t("Version")}</th>
                        <th>{t("Arrived")}</th>
                        <th>{t("Transport")}</th>
                        <th>{t("Differences")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadedDetail.intakes.map((item) => (
                        <tr key={item.globalId}>
                          <td>{formatNumber(locale, item.version, 0)}</td>
                          <td>
                            <time dateTime={item.arrivedAt}>
                              {formatDateTime(locale, item.arrivedAt)}
                            </time>
                          </td>
                          <td data-language-exempt="business-data">
                            {item.transportProvider} · {item.transportReference}
                          </td>
                          <td>
                            {formatNumber(locale, item.differences.length, 0)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>{t("No arrival intake has been recorded for this Set.")}</p>
              )}
            </Panel>
            <Panel title={t("Governed intake evidence")}>
              {loadedDetail.evidence.length ? (
                <div className="table-scroll" tabIndex={0}>
                  <table className="data-table data-table--compact">
                    <thead>
                      <tr>
                        <th>{t("Role")}</th>
                        <th>{t("File Revision")}</th>
                        <th>{t("File")}</th>
                        <th>{t("Bound differences")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadedDetail.evidence.map((item) => (
                        <tr key={item.globalId}>
                          <td>{evidenceRoleLabel(t, item.evidenceRole)}</td>
                          <td data-language-exempt="identifier">
                            {item.fileRevisionGlobalId}
                          </td>
                          <td data-language-exempt="business-data">
                            {item.fileName}
                          </td>
                          <td>
                            {formatNumber(
                              locale,
                              item.differenceGlobalIds.length,
                              0,
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>{t("No governed evidence reference has been attached.")}</p>
              )}
            </Panel>
          </div>
          <aside
            aria-label={t("Physical Set truth inspector")}
            className="tooling-set__inspector"
          >
            <strong>{t("Physical Set truth inspector")}</strong>
            <DefinitionList
              rows={[
                {
                  label: t("Physical serial"),
                  value: loadedDetail.toolingSet.physicalSerial,
                  exempt: "business-data",
                },
                {
                  label: t("Custody responsibility"),
                  value: loadedDetail.toolingSet.custodyResponsibility,
                  exempt: "business-data",
                },
                {
                  label: t("Repair authorization reference"),
                  value: loadedDetail.toolingSet.repairAuthorizationReference,
                  exempt: "business-data",
                },
                {
                  label: t("Return conditions"),
                  value: loadedDetail.toolingSet.returnConditions,
                  exempt: "business-data",
                },
                {
                  label: t("Set snapshot hash"),
                  value: loadedDetail.toolingSet.snapshotHash,
                  exempt: "identifier",
                },
              ]}
            />
            {"state" in loadedDetail.toolingSet.sourceRevision ? (
              <div className="tooling-live__downstream-row">
                <SemanticStatus label={t("Unavailable")} tone="warning" />
                <span>
                  {unavailableLabel(
                    t,
                    loadedDetail.toolingSet.sourceRevision.reasonCode,
                  )}
                </span>
              </div>
            ) : (
              <DefinitionList
                rows={[
                  {
                    label: t("Source Tooling Revision"),
                    value:
                      loadedDetail.toolingSet.sourceRevision
                        .toolingRevisionGlobalId,
                    exempt: "identifier",
                  },
                  {
                    label: t("Binding reason"),
                    value: loadedDetail.toolingSet.sourceRevision.reason,
                    exempt: "business-data",
                  },
                ]}
              />
            )}
            {[
              loadedDetail.toolingSet.supplier,
              loadedDetail.toolingSet.lifecycle,
              loadedDetail.toolingSet.erpLocationAndAsset,
            ].map((field) => (
              <div
                className="tooling-live__downstream-row"
                key={field.reasonCode}
              >
                <SemanticStatus label={t("Unavailable")} tone="warning" />
                <span>{unavailableLabel(t, field.reasonCode)}</span>
              </div>
            ))}
          </aside>
        </div>
      ) : null}
      {editor ? (
        <Panel
          title={
            editor.kind === "set"
              ? t("Create physical Tooling Set")
              : editor.kind === "intake"
                ? t("Record arrival intake")
                : editor.kind === "evidence"
                  ? t("Attach governed intake evidence")
                  : t("Bind source Tooling Revision")
          }
        >
          <form
            className="ebom-form tooling-set__form"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            {editor.kind === "set" ? (
              <>
                <label>
                  <span>{t("Tooling requirement")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        toolingRequirementGlobalId: event.currentTarget.value,
                      });
                    }}
                    value={editor.toolingRequirementGlobalId}
                  >
                    {eligibleRequirements.map((item) => (
                      <option
                        data-language-exempt="business-data"
                        key={item.globalId}
                        value={item.globalId}
                      >
                        {item.title}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Physical serial")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={80}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        physicalSerial: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.physicalSerial}
                  />
                </label>
                <label>
                  <span>{t("Customer source")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        customerSourceSystem: event.currentTarget
                          .value as SetEditorState["customerSourceSystem"],
                      });
                    }}
                    value={editor.customerSourceSystem}
                  >
                    <option value="">{t("Not linked")}</option>
                    <option value="NPI_ONE">{t("NPI One")}</option>
                    <option value="ERPNEXT">{t("ERPNext")}</option>
                  </Select>
                </label>
                <label>
                  <span>{t("Customer reference")}</span>
                  <TextInput
                    disabled={processing || !editor.customerSourceSystem}
                    maxLength={128}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        customerSourceObjectId: event.currentTarget.value,
                      });
                    }}
                    value={editor.customerSourceObjectId}
                  />
                </label>
                <label className="ebom-form__wide">
                  <span>{t("Custody responsibility")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={500}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        custodyResponsibility: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.custodyResponsibility}
                  />
                </label>
                <label className="ebom-form__wide">
                  <span>{t("Repair authorization reference")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={500}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        repairAuthorizationReference: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.repairAuthorizationReference}
                  />
                </label>
                <label className="ebom-form__wide">
                  <span>{t("Return conditions")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={500}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        returnConditions: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.returnConditions}
                  />
                </label>
              </>
            ) : null}
            {editor.kind === "intake" ? (
              <>
                <label>
                  <span>{t("Transport provider")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={140}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        transportProvider: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.transportProvider}
                  />
                </label>
                <label>
                  <span>{t("Transport reference")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={140}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        transportReference: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.transportReference}
                  />
                </label>
                <label>
                  <span>{t("Arrived at")}</span>
                  <TextInput
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        arrivedAt: event.currentTarget.value,
                      });
                    }}
                    required
                    type="datetime-local"
                    value={editor.arrivedAt}
                  />
                </label>
                <label className="ebom-form__wide">
                  <span>{t("Custody handover")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={500}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        custodyHandover: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.custodyHandover}
                  />
                </label>
                <fieldset className="ebom-form__wide tooling-set__inspection-grid">
                  <legend>{t("Five-category arrival inspection")}</legend>
                  {editor.inspections.map((inspection, index) => (
                    <div
                      className="tooling-set__inspection-row"
                      key={inspection.globalId}
                    >
                      <label className="tooling-set__inspection-observation">
                        <span>{inspectionLabel(t, inspection.category)}</span>
                        <TextInput
                          disabled={processing}
                          maxLength={500}
                          onChange={(event) => {
                            const inspections = [...editor.inspections];
                            inspections[index] = {
                              ...inspection,
                              observation: event.currentTarget.value,
                            };
                            setEditor({ ...editor, inspections });
                          }}
                          required
                          value={inspection.observation}
                        />
                      </label>
                      <label className="checkbox-field">
                        <input
                          checked={inspection.differenceObserved}
                          disabled={processing}
                          onChange={(event) => {
                            const inspections = [...editor.inspections];
                            inspections[index] = {
                              ...inspection,
                              differenceObserved: event.currentTarget.checked,
                              customerConfirmationRequired: event.currentTarget
                                .checked
                                ? inspection.customerConfirmationRequired
                                : false,
                            };
                            setEditor({ ...editor, inspections });
                          }}
                          type="checkbox"
                        />
                        <span>{t("Difference observed")}</span>
                      </label>
                      <label className="checkbox-field">
                        <input
                          checked={inspection.customerConfirmationRequired}
                          disabled={
                            processing || !inspection.differenceObserved
                          }
                          onChange={(event) => {
                            const inspections = [...editor.inspections];
                            inspections[index] = {
                              ...inspection,
                              customerConfirmationRequired:
                                event.currentTarget.checked,
                            };
                            setEditor({ ...editor, inspections });
                          }}
                          type="checkbox"
                        />
                        <span>{t("Customer confirmation required")}</span>
                      </label>
                    </div>
                  ))}
                </fieldset>
                <fieldset className="ebom-form__wide tooling-set__accessories">
                  <legend>{t("Declared and received accessories")}</legend>
                  {editor.accessories.map((accessory, index) => (
                    <div
                      className="tooling-set__accessory-row"
                      key={accessory.globalId}
                    >
                      <label>
                        <span>{t("Accessory")}</span>
                        <TextInput
                          disabled={processing}
                          maxLength={200}
                          onChange={(event) => {
                            const accessories = [...editor.accessories];
                            accessories[index] = {
                              ...accessory,
                              description: event.currentTarget.value,
                            };
                            setEditor({ ...editor, accessories });
                          }}
                          required
                          value={accessory.description}
                        />
                      </label>
                      <label>
                        <span>{t("Declared")}</span>
                        <TextInput
                          disabled={processing}
                          min="0"
                          onChange={(event) => {
                            const accessories = [...editor.accessories];
                            accessories[index] = {
                              ...accessory,
                              declaredQuantity: event.currentTarget.value,
                            };
                            setEditor({ ...editor, accessories });
                          }}
                          required
                          type="number"
                          value={accessory.declaredQuantity}
                        />
                      </label>
                      <label>
                        <span>{t("Received")}</span>
                        <TextInput
                          disabled={processing}
                          min="0"
                          onChange={(event) => {
                            const accessories = [...editor.accessories];
                            accessories[index] = {
                              ...accessory,
                              receivedQuantity: event.currentTarget.value,
                            };
                            setEditor({ ...editor, accessories });
                          }}
                          required
                          type="number"
                          value={accessory.receivedQuantity}
                        />
                      </label>
                      <label>
                        <span>{t("Unit")}</span>
                        <TextInput
                          disabled={processing}
                          maxLength={24}
                          onChange={(event) => {
                            const accessories = [...editor.accessories];
                            accessories[index] = {
                              ...accessory,
                              unit: event.currentTarget.value,
                            };
                            setEditor({ ...editor, accessories });
                          }}
                          required
                          value={accessory.unit}
                        />
                      </label>
                      <Button
                        disabled={processing}
                        onClick={() => {
                          setEditor({
                            ...editor,
                            accessories: editor.accessories.filter(
                              (_, candidate) => candidate !== index,
                            ),
                          });
                        }}
                        type="button"
                      >
                        {t("Remove accessory")}
                      </Button>
                    </div>
                  ))}
                  <Button
                    disabled={processing || editor.accessories.length >= 100}
                    onClick={() => {
                      setEditor({
                        ...editor,
                        accessories: [
                          ...editor.accessories,
                          {
                            globalId: globalThis.crypto.randomUUID(),
                            description: "",
                            declaredQuantity: "",
                            receivedQuantity: "",
                            unit: "",
                          },
                        ],
                      });
                    }}
                    type="button"
                  >
                    {t("Add accessory")}
                  </Button>
                </fieldset>
              </>
            ) : null}
            {editor.kind === "evidence" ? (
              <>
                <label>
                  <span>{t("Intake version")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        intakeGlobalId: event.currentTarget.value,
                        differenceGlobalIds: [],
                      });
                    }}
                    value={editor.intakeGlobalId}
                  >
                    {loadedDetail?.intakes.map((item) => (
                      <option key={item.globalId} value={item.globalId}>
                        {formatNumber(locale, item.version, 0)} ·{" "}
                        {formatDateTime(locale, item.arrivedAt)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Evidence role")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        evidenceRole: event.currentTarget
                          .value as ToolingIntakeEvidenceRole,
                      });
                    }}
                    value={editor.evidenceRole}
                  >
                    {(
                      [
                        "arrival_photo",
                        "transport_document",
                        "accessory_document",
                        "inspection_evidence",
                        "customer_confirmation",
                      ] as const
                    ).map((role) => (
                      <option key={role} value={role}>
                        {evidenceRoleLabel(t, role)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Controlled document")}</span>
                  <Select
                    disabled={processing || documents.kind !== "loaded"}
                    onChange={(event) => {
                      const documentGlobalId = event.currentTarget.value;
                      setDocumentDetail(
                        documentGlobalId
                          ? { kind: "loading" }
                          : { kind: "idle" },
                      );
                      setEditor({
                        ...editor,
                        documentGlobalId,
                        fileRevisionGlobalId: "",
                      });
                    }}
                    value={editor.documentGlobalId}
                  >
                    <option value="">
                      {documents.kind === "loading"
                        ? t("Loading controlled documents")
                        : t("Select controlled document")}
                    </option>
                    {documents.kind === "loaded"
                      ? documents.value.items.map((item) => (
                          <option
                            data-language-exempt="business-data"
                            key={item.globalId}
                            value={item.globalId}
                          >
                            {item.documentNumber} · {item.title}
                          </option>
                        ))
                      : null}
                  </Select>
                </label>
                <label>
                  <span>{t("Exact File Revision")}</span>
                  <Select
                    disabled={processing || documentDetail.kind !== "loaded"}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        fileRevisionGlobalId: event.currentTarget.value,
                      });
                    }}
                    value={editor.fileRevisionGlobalId}
                  >
                    <option value="">
                      {documentDetail.kind === "loading"
                        ? t("Loading exact File Revisions")
                        : t("Select clean exact File Revision")}
                    </option>
                    {fileOptions.map((file) => (
                      <option
                        data-language-exempt="business-data"
                        key={file.globalId}
                        value={file.globalId}
                      >
                        {file.fileName} · v{file.revision}
                      </option>
                    ))}
                  </Select>
                </label>
                {documents.kind === "failed" ? (
                  <div className="ebom-form__wide">
                    <RequestFailurePanel failure={documents.failure} />
                  </div>
                ) : null}
                {documentDetail.kind === "failed" ? (
                  <div className="ebom-form__wide">
                    <RequestFailurePanel failure={documentDetail.failure} />
                  </div>
                ) : null}
                {evidenceIntake?.differences.length ? (
                  <fieldset className="ebom-form__wide tooling-set__difference-picker">
                    <legend>{t("Bind exact intake differences")}</legend>
                    {evidenceIntake.differences.map((difference) => (
                      <label
                        className="checkbox-field"
                        key={difference.globalId}
                      >
                        <input
                          checked={editor.differenceGlobalIds.includes(
                            difference.globalId,
                          )}
                          disabled={processing}
                          onChange={(event) => {
                            setEditor({
                              ...editor,
                              differenceGlobalIds: event.currentTarget.checked
                                ? [
                                    ...editor.differenceGlobalIds,
                                    difference.globalId,
                                  ]
                                : editor.differenceGlobalIds.filter(
                                    (item) => item !== difference.globalId,
                                  ),
                            });
                          }}
                          type="checkbox"
                        />
                        <span data-language-exempt="business-data">
                          {difference.description}
                        </span>
                      </label>
                    ))}
                  </fieldset>
                ) : null}
              </>
            ) : null}
            {editor.kind === "binding" ? (
              <>
                <label>
                  <span>{t("Source Tooling Revision")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        toolingRevisionGlobalId: event.currentTarget.value,
                      });
                    }}
                    value={editor.toolingRevisionGlobalId}
                  >
                    {revisionCollection.kind === "loaded"
                      ? revisionCollection.value.items.map((item) => (
                          <option key={item.globalId} value={item.globalId}>
                            {item.revisionLabel} · {item.revisionNumber}
                          </option>
                        ))
                      : null}
                  </Select>
                </label>
                <label className="ebom-form__wide">
                  <span>{t("Binding reason")}</span>
                  <TextInput
                    disabled={processing}
                    maxLength={500}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        reason: event.currentTarget.value,
                      });
                    }}
                    required
                    value={editor.reason}
                  />
                </label>
              </>
            ) : null}
            {formError ? (
              <p className="ebom-form__wide form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions ebom-form__wide">
              <Button
                disabled={processing || !sessionCommandContext}
                type="submit"
                visual="primary"
              >
                {editor.kind === "set"
                  ? t("Create physical Set")
                  : editor.kind === "intake"
                    ? t("Record intake")
                    : editor.kind === "evidence"
                      ? t("Attach evidence")
                      : t("Bind exact source Revision")}
              </Button>
              <Button disabled={processing} onClick={closeEditor} type="button">
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
    </Panel>
  );
}
