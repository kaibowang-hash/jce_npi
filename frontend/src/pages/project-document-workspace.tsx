import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentSummaryViewModel,
  ControlledDocumentWorkspaceViewModel,
  DocumentDataSource,
  DocumentRelationshipKind,
  DocumentRevisionFileViewModel,
  DocumentRevisionViewModel,
} from "../api/document-data-source";
import { DocumentRequestCancelledError } from "../api/document-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../app/workspace-navigation";
import { DockedInspector } from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
  SourceSystemIdentity,
} from "../components/primitives";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n, type Locale } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type EditorKind = "create" | "revision" | "recover" | null;

type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

type ContentState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "unavailable"; reasonCode: string }
  | {
      kind: "ready";
      fileName: string;
      mimeType: string;
      objectUrl: string;
    }
  | { kind: "failed"; failure: RequestFailure };

interface CreateFormState {
  policyVersionId: string;
  documentTypeKey: string;
  confidentialityKey: string;
  title: string;
}

interface RevisionFormState {
  major: string;
  minor: string;
  reason: string;
  effectiveDate: string;
  file: File | null;
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function documentRevisionLabel(
  revision: DocumentRevisionViewModel | null,
): string {
  return revision ? `${String(revision.major)}.${String(revision.minor)}` : "—";
}

function capabilityTone(
  state: "available" | "unavailable" | "blocked",
): "success" | "warning" | "danger" {
  return state === "available"
    ? "success"
    : state === "blocked"
      ? "danger"
      : "warning";
}

function relationshipKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: DocumentRelationshipKind,
): string {
  switch (kind) {
    case "project":
      return t("Project");
    case "project_reference":
      return t("Project reference");
    case "gate":
      return t("Gate");
    case "wbs_item":
      return t("WBS item");
    case "domain_work_item":
      return t("Domain work item");
  }
}

function fileSize(locale: Locale, value: number): string {
  if (value < 1_024) return `${formatNumber(locale, value, 0)} B`;
  if (value < 1_048_576) return `${formatNumber(locale, value / 1_024, 1)} KB`;
  return `${formatNumber(locale, value / 1_048_576, 1)} MB`;
}

function DocumentResourceFailure({
  failure,
  retry,
}: {
  failure: RequestFailure;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const unavailable =
    failure.problem?.status === 401 ||
    failure.problem?.status === 403 ||
    failure.problem?.status === 404;
  return (
    <section className="workspace-resource-state" role="alert">
      <SemanticStatus
        label={unavailable ? t("Unavailable") : t("Error")}
        tone={unavailable ? "warning" : "danger"}
      />
      <h2>
        {unavailable
          ? t("Project documents are not available")
          : t("Project documents could not be loaded")}
      </h2>
      <p>
        {unavailable
          ? t(
              "No protected document identity or file information was displayed.",
            )
          : t(
              "No document data was displayed. Use the reference ID for support.",
            )}
      </p>
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={retry}>
          {failure.problem?.status === 409 ? t("Reload") : t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function CommandStatus({
  state,
  retry,
}: {
  state: CommandState;
  retry: () => void;
}): React.JSX.Element | null {
  const { t } = useI18n();
  if (state.kind === "idle") return null;
  if (state.kind === "processing") {
    return (
      <div aria-live="polite" className="document-command-state" role="status">
        <SemanticStatus label={t("Processing")} tone="info" />
        <span>{state.label}</span>
      </div>
    );
  }
  return (
    <div
      className="document-command-state document-command-state--error"
      role="alert"
    >
      <SemanticStatus
        label={
          state.failure.problem?.status === 409 ? t("Conflict") : t("Error")
        }
        tone="danger"
      />
      <RequestFailurePanel failure={state.failure} />
      {canRetry(state.failure) ? (
        <Button icon="refresh" onClick={retry}>
          {t("Reload")}
        </Button>
      ) : null}
    </div>
  );
}

function EmptyDocuments({
  canCreate,
  hasPolicy,
  startCreate,
}: {
  canCreate: boolean;
  hasPolicy: boolean;
  startCreate: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section className="document-empty-state" role="status">
      <SemanticStatus label={t("Empty")} />
      <h2>{t("No controlled documents")}</h2>
      <p>
        {hasPolicy
          ? t("Create the first controlled document for this Project.")
          : t(
              "Document creation is unavailable because no accepted document policy is configured.",
            )}
      </p>
      {canCreate && hasPolicy ? (
        <Button icon="add" onClick={startCreate} visual="primary">
          {t("Create document")}
        </Button>
      ) : null}
    </section>
  );
}

function DocumentList({
  page,
  selectedDocumentId,
  selectDocument,
}: {
  page: ControlledDocumentPageViewModel;
  selectedDocumentId: string | null;
  selectDocument: (
    document: ControlledDocumentSummaryViewModel,
    returnFocusTarget: HTMLElement,
  ) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <table className="data-table data-table--compact document-list-table">
      <thead>
        <tr>
          <th>{t("Document number")}</th>
          <th>{t("Title")}</th>
          <th>{t("Revision")}</th>
          <th>{t("Lock")}</th>
        </tr>
      </thead>
      <tbody>
        {page.items.map((document) => (
          <tr
            aria-selected={selectedDocumentId === document.globalId}
            className={
              selectedDocumentId === document.globalId ? "is-selected" : ""
            }
            key={document.globalId}
          >
            <td>
              <button
                className="table-link"
                data-language-exempt="identifier"
                onClick={(event) => {
                  selectDocument(document, event.currentTarget);
                }}
                type="button"
              >
                {document.documentNumber}
              </button>
            </td>
            <td data-language-exempt="business-data">{document.title}</td>
            <td data-language-exempt="identifier">
              {document.currentRevision
                ? `${String(document.currentRevision.major)}.${String(
                    document.currentRevision.minor,
                  )}`
                : "—"}
            </td>
            <td>
              {document.currentLock ? (
                <SemanticStatus label={t("Checked out")} tone="warning" />
              ) : (
                <SemanticStatus label={t("Available")} tone="success" />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ProjectDocumentWorkspace({
  dataSource,
  projectId,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: {
  dataSource?: DocumentDataSource | undefined;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  requestWorkspaceTransition?: RequestWorkspaceTransition | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [pageState, setPageState] = useState<
    ResourceState<ControlledDocumentPageViewModel>
  >({ kind: "loading" });
  const [detailState, setDetailState] = useState<
    ResourceState<ControlledDocumentWorkspaceViewModel> | { kind: "idle" }
  >({ kind: "idle" });
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null,
  );
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(
    null,
  );
  const [editor, setEditor] = useState<EditorKind>(null);
  const [editorTouched, setEditorTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [contentState, setContentState] = useState<ContentState>({
    kind: "idle",
  });
  const [createForm, setCreateForm] = useState<CreateFormState>({
    policyVersionId: "",
    documentTypeKey: "",
    confidentialityKey: "",
    title: "",
  });
  const [revisionForm, setRevisionForm] = useState<RevisionFormState>({
    major: "0",
    minor: "1",
    reason: "",
    effectiveDate: "",
    file: null,
  });
  const [recoverReason, setRecoverReason] = useState("");
  const firstEditorControl = useRef<HTMLElement | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);
  const page = pageState.kind === "loaded" ? pageState.value : null;
  const detail = detailState.kind === "loaded" ? detailState.value : null;
  const selectedPolicy = useMemo(
    () =>
      page?.policies.find(
        (policy) => policy.versionId === createForm.policyVersionId,
      ) ?? null,
    [createForm.policyVersionId, page?.policies],
  );
  const selectedRevision = useMemo(
    () =>
      detail?.revisions.find(
        (revision) => revision.globalId === selectedRevisionId,
      ) ??
      detail?.revisions[0] ??
      null,
    [detail?.revisions, selectedRevisionId],
  );
  const dirty = editor !== null && editorTouched;

  const clearEditor = useCallback((): void => {
    setEditor(null);
    setEditorTouched(false);
    setFormError(null);
    setRecoverReason("");
    setRevisionForm({
      major: "0",
      minor: "1",
      reason: "",
      effectiveDate: "",
      file: null,
    });
  }, []);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!dirty) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity:
        editor === "create"
          ? `${projectId}:new-document`
          : (detail?.document.globalId ?? projectId),
      version:
        editor === "create"
          ? "unsaved-document"
          : `document-v${String(detail?.document.optimisticVersion ?? 0)}`,
      returnFocusTarget: () =>
        firstEditorControl.current ??
        document.getElementById("project-workspace-tab-documents"),
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [
    detail?.document.globalId,
    detail?.document.optimisticVersion,
    dirty,
    editor,
    projectId,
    reportWorkspaceDirty,
  ]);

  useEffect(() => {
    return () => {
      if (contentState.kind === "ready") {
        URL.revokeObjectURL(contentState.objectUrl);
      }
    };
  }, [contentState]);

  useEffect(() => {
    if (!dataSource) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadDocuments(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setPageState({ kind: "loaded", value });
        setSelectedDocumentId(
          (current) => current ?? value.items[0]?.globalId ?? null,
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof DocumentRequestCancelledError
        )
          return;
        setPageState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, projectId]);

  useEffect(() => {
    if (!dataSource || !selectedDocumentId) {
      return undefined;
    }
    const controller = new AbortController();
    void dataSource
      .loadDocument(projectId, selectedDocumentId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setDetailState({ kind: "loaded", value });
        setSelectedRevisionId(
          value.document.currentRevision?.globalId ??
            value.revisions[0]?.globalId ??
            null,
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof DocumentRequestCancelledError
        )
          return;
        setDetailState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, detailAttempt, projectId, selectedDocumentId]);

  const reload = useCallback((): void => {
    clearEditor();
    setCommandState({ kind: "idle" });
    setContentState({ kind: "idle" });
    setPageState({ kind: "loading" });
    setDetailState(selectedDocumentId ? { kind: "loading" } : { kind: "idle" });
    setAttempt((current) => current + 1);
    setDetailAttempt((current) => current + 1);
  }, [clearEditor, selectedDocumentId]);

  const updateWorkspace = useCallback(
    (workspace: ControlledDocumentWorkspaceViewModel): void => {
      setSelectedDocumentId(workspace.document.globalId);
      setDetailState({ kind: "loaded", value: workspace });
      setSelectedRevisionId(
        workspace.document.currentRevision?.globalId ??
          workspace.revisions[0]?.globalId ??
          null,
      );
      setPageState((current) => {
        if (current.kind !== "loaded") return current;
        const items = current.value.items.some(
          (item) => item.globalId === workspace.document.globalId,
        )
          ? current.value.items.map((item) =>
              item.globalId === workspace.document.globalId
                ? workspace.document
                : item,
            )
          : [workspace.document, ...current.value.items];
        return {
          kind: "loaded",
          value: {
            ...current.value,
            project: workspace.project,
            permissions: workspace.permissions,
            items,
          },
        };
      });
      clearEditor();
      setCommandState({ kind: "idle" });
    },
    [clearEditor],
  );

  const runCommand = useCallback(
    (
      label: string,
      command: (
        signal: AbortSignal,
      ) => Promise<ControlledDocumentWorkspaceViewModel>,
    ): void => {
      const run = (): void => {
        const controller = new AbortController();
        setCommandState({ kind: "processing", label });
        void command(controller.signal)
          .then(updateWorkspace)
          .catch((error: unknown) => {
            if (
              controller.signal.aborted ||
              error instanceof DocumentRequestCancelledError
            )
              return;
            setCommandState({
              failure: toRequestFailure(error),
              kind: "failed",
            });
          });
      };
      latestCommand.current = run;
      run();
    },
    [updateWorkspace],
  );

  const startCreate = (): void => {
    const policy = page?.policies[0];
    if (!policy) return;
    setCreateForm({
      policyVersionId: policy.versionId,
      documentTypeKey: policy.documentTypes[0]?.key ?? "",
      confidentialityKey: policy.confidentialityKeys[0] ?? "",
      title: "",
    });
    setEditor("create");
    setEditorTouched(false);
    setFormError(null);
    globalThis.queueMicrotask(() => {
      firstEditorControl.current?.focus();
    });
  };

  const startRevision = (): void => {
    if (!detail) return;
    setRevisionForm({
      major: String(detail.document.currentRevision?.major ?? 0),
      minor: String((detail.document.currentRevision?.minor ?? 0) + 1),
      reason: "",
      effectiveDate: "",
      file: null,
    });
    setEditor("revision");
    setEditorTouched(false);
    setFormError(null);
    globalThis.queueMicrotask(() => {
      firstEditorControl.current?.focus();
    });
  };

  const selectDocument = (
    documentSummary: ControlledDocumentSummaryViewModel,
    returnFocusTarget: HTMLElement,
  ): void => {
    if (documentSummary.globalId === selectedDocumentId) return;
    const perform = (): void => {
      clearEditor();
      setContentState({ kind: "idle" });
      setDetailState({ kind: "loading" });
      setSelectedDocumentId(documentSummary.globalId);
    };
    if (requestWorkspaceTransition) {
      requestWorkspaceTransition(perform, returnFocusTarget);
    } else {
      perform();
    }
  };

  const submitCreate = (): void => {
    if (!dataSource || !page || !selectedPolicy || !sessionCommandContext)
      return;
    const title = createForm.title.trim();
    if (
      !title ||
      !selectedPolicy.documentTypes.some(
        (option) => option.key === createForm.documentTypeKey,
      ) ||
      !selectedPolicy.confidentialityKeys.includes(
        createForm.confidentialityKey,
      )
    ) {
      setFormError(t("Complete every required document field."));
      return;
    }
    runCommand(t("Creating controlled document"), (signal) =>
      dataSource.createDocument(
        projectId,
        {
          policyGlobalId: selectedPolicy.globalId,
          policyVersion: selectedPolicy.version,
          policySnapshotHash: selectedPolicy.snapshotHash,
          documentTypeKey: createForm.documentTypeKey,
          title,
          confidentialityKey: createForm.confidentialityKey,
          objectLinks: [
            {
              kind: "project",
              targetIdentity: projectId,
              targetVersion: page.project.optimisticVersion,
            },
          ],
        },
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: `document-${globalThis.crypto.randomUUID()}`,
          signal,
        },
      ),
    );
  };

  const submitRevision = (): void => {
    if (!dataSource || !detail || !sessionCommandContext || !selectedPolicy)
      return;
    const major = Number(revisionForm.major);
    const minor = Number(revisionForm.minor);
    const reason = revisionForm.reason.trim();
    const file = revisionForm.file;
    if (
      !Number.isInteger(major) ||
      major < 0 ||
      !Number.isInteger(minor) ||
      minor < 0 ||
      !reason ||
      !file
    ) {
      setFormError(t("Complete every required revision field."));
      return;
    }
    if (
      file.size > selectedPolicy.maximumFileBytes ||
      !selectedPolicy.allowedMimeTypes.includes(file.type)
    ) {
      setFormError(
        t("The selected file does not match the active document policy."),
      );
      return;
    }
    const currentLock = detail.document.currentLock;
    if (!currentLock) {
      setFormError(t("Check out the document before creating a revision."));
      return;
    }
    runCommand(t("Creating immutable document revision"), (signal) =>
      dataSource.createRevision(
        projectId,
        detail.document.globalId,
        {
          expectedDocumentVersion: detail.document.optimisticVersion,
          expectedLockVersion: currentLock.version,
          major,
          minor,
          reason,
          effectiveDate: revisionForm.effectiveDate || null,
          predecessorRevisionId:
            detail.document.currentRevision?.globalId ?? null,
          file,
        },
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: `revision-${globalThis.crypto.randomUUID()}`,
          signal,
        },
      ),
    );
  };

  const submitRecovery = (): void => {
    if (!dataSource || !detail || !sessionCommandContext) return;
    const currentLock = detail.document.currentLock;
    const reason = recoverReason.trim();
    if (!currentLock || !reason) {
      setFormError(t("Enter a lock recovery reason."));
      return;
    }
    runCommand(t("Recovering document lock"), (signal) =>
      dataSource.recoverLock(
        projectId,
        detail.document.globalId,
        detail.document.optimisticVersion,
        currentLock.version,
        reason,
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: `lock-recovery-${globalThis.crypto.randomUUID()}`,
          signal,
        },
      ),
    );
  };

  const checkOut = (): void => {
    if (!dataSource || !detail || !sessionCommandContext) return;
    runCommand(t("Checking out document"), (signal) =>
      dataSource.checkOut(
        projectId,
        detail.document.globalId,
        detail.document.optimisticVersion,
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: `check-out-${globalThis.crypto.randomUUID()}`,
          signal,
        },
      ),
    );
  };

  const checkIn = (): void => {
    if (!dataSource || !detail || !sessionCommandContext) return;
    const currentLock = detail.document.currentLock;
    if (!currentLock) return;
    runCommand(t("Checking in document"), (signal) =>
      dataSource.checkIn(
        projectId,
        detail.document.globalId,
        detail.document.optimisticVersion,
        currentLock.version,
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: `check-in-${globalThis.crypto.randomUUID()}`,
          signal,
        },
      ),
    );
  };

  const requestContent = (
    file: DocumentRevisionFileViewModel,
    disposition: "inline" | "attachment",
  ): void => {
    if (!dataSource || !detail || !selectedRevision || !sessionCommandContext)
      return;
    const label =
      disposition === "inline"
        ? t("Preparing secure preview")
        : t("Preparing secure download");
    setContentState({ kind: "processing", label });
    const controller = new AbortController();
    const idempotencyKey = `${disposition}-${globalThis.crypto.randomUUID()}`;
    void dataSource
      .loadCapabilities(
        projectId,
        detail.document.globalId,
        selectedRevision.globalId,
        file.globalId,
        controller.signal,
      )
      .then((result) => {
        const capability =
          disposition === "inline"
            ? result.capabilities.preview
            : result.capabilities.download;
        if (capability.state !== "available") {
          setContentState({
            kind: "unavailable",
            reasonCode: capability.reasonCode,
          });
          return null;
        }
        return dataSource.loadContent(
          projectId,
          detail.document.globalId,
          selectedRevision.globalId,
          detail.document.optimisticVersion,
          file,
          disposition,
          {
            csrfToken: sessionCommandContext.csrfToken,
            idempotencyKey,
            signal: controller.signal,
          },
        );
      })
      .then((blob) => {
        if (!blob || controller.signal.aborted) return;
        const objectUrl = URL.createObjectURL(blob);
        if (disposition === "attachment") {
          const anchor = document.createElement("a");
          anchor.download = file.fileName;
          anchor.href = objectUrl;
          anchor.rel = "noopener";
          anchor.click();
          URL.revokeObjectURL(objectUrl);
          setContentState({ kind: "idle" });
          return;
        }
        setContentState({
          fileName: file.fileName,
          kind: "ready",
          mimeType: file.mimeType,
          objectUrl,
        });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof DocumentRequestCancelledError
        )
          return;
        setContentState({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      });
  };

  if (!dataSource) {
    return (
      <section className="workspace-resource-state" role="status">
        <SemanticStatus label={t("Unavailable")} tone="warning" />
        <p>
          {t("The live controlled document data source is not configured.")}
        </p>
      </section>
    );
  }
  if (pageState.kind === "loading") {
    return (
      <section
        aria-busy="true"
        aria-label={t("Loading project documents")}
        className="workspace-resource-state workspace-resource-state--loading"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <div className="skeleton" />
        <span className="visually-hidden">
          {t("Loading project documents")}
        </span>
      </section>
    );
  }
  if (pageState.kind === "failed") {
    return (
      <DocumentResourceFailure
        failure={pageState.failure}
        retry={() => {
          setPageState({ kind: "loading" });
          setAttempt((current) => current + 1);
        }}
      />
    );
  }

  const canCreate =
    pageState.value.permissions.create && sessionCommandContext !== null;
  const documentPolicy =
    detail === null
      ? null
      : (pageState.value.policies.find(
          (policy) =>
            policy.globalId === detail.document.documentPolicyRef.globalId &&
            policy.version === detail.document.documentPolicyRef.version &&
            policy.snapshotHash ===
              detail.document.documentPolicyRef.snapshotHash,
        ) ?? null);
  const editorPolicy = editor === "create" ? selectedPolicy : documentPolicy;
  const commandProcessing = commandState.kind === "processing";

  return (
    <section
      aria-label={t("Project design and documents")}
      className="document-workspace"
    >
      <header className="document-workspace__toolbar">
        <div>
          <h2>{t("Design and documents")}</h2>
          <span className="document-workspace__summary">
            {t("Controlled documents")}:{" "}
            {formatNumber(locale, pageState.value.items.length, 0)}
          </span>
        </div>
        <div className="detail-actions">
          <Button
            disabled={
              !canCreate ||
              pageState.value.policies.length === 0 ||
              commandProcessing
            }
            icon="add"
            onClick={startCreate}
            visual="primary"
          >
            {t("Create document")}
          </Button>
          <Button disabled={commandProcessing} icon="refresh" onClick={reload}>
            {t("Reload")}
          </Button>
        </div>
      </header>
      <CommandStatus
        retry={() => {
          if (commandState.kind === "failed" && canRetry(commandState.failure))
            reload();
          else latestCommand.current?.();
        }}
        state={commandState}
      />
      {pageState.value.policies.length === 0 ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus label={t("Unavailable")} tone="warning" />
          <span>
            {t(
              "Document creation is unavailable because no accepted document policy is configured.",
            )}
          </span>
        </div>
      ) : null}
      {pageState.value.items.length === 0 ? (
        <EmptyDocuments
          canCreate={canCreate}
          hasPolicy={pageState.value.policies.length > 0}
          startCreate={startCreate}
        />
      ) : (
        <div className="document-workspace__layout">
          <Panel scrollableBody title={t("Controlled documents")}>
            <DocumentList
              page={pageState.value}
              selectDocument={selectDocument}
              selectedDocumentId={selectedDocumentId}
            />
          </Panel>
          {detailState.kind === "loading" || detailState.kind === "idle" ? (
            <DockedInspector title={t("Document inspector")}>
              <div
                aria-busy="true"
                className="workspace-resource-state workspace-resource-state--loading"
                role="status"
              >
                <div className="skeleton skeleton--title" />
                <div className="skeleton" />
              </div>
            </DockedInspector>
          ) : detailState.kind === "failed" ? (
            <DockedInspector title={t("Document inspector")}>
              <DocumentResourceFailure
                failure={detailState.failure}
                retry={() => {
                  setDetailState({ kind: "loading" });
                  setDetailAttempt((current) => current + 1);
                }}
              />
            </DockedInspector>
          ) : (
            <DockedInspector title={t("Document inspector")}>
              <div className="document-inspector__header">
                <div>
                  <strong data-language-exempt="identifier">
                    {detailState.value.document.documentNumber}
                  </strong>
                  <span
                    className="document-inspector__title"
                    data-language-exempt="business-data"
                  >
                    {detailState.value.document.title}
                  </span>
                </div>
                <SourceSystemIdentity
                  sourceSystem={detailState.value.document.source.sourceSystem}
                />
              </div>
              <DefinitionList
                rows={[
                  {
                    label: t("Document type"),
                    value:
                      documentPolicy?.documentTypes.find(
                        (option) =>
                          option.key ===
                          detailState.value.document.documentTypeKey,
                      )?.titleSource ??
                      detailState.value.document.documentTypeKey,
                    exempt: "business-data",
                  },
                  {
                    label: t("Confidentiality"),
                    value: detailState.value.document.confidentialityKey,
                    exempt: "identifier",
                  },
                  {
                    label: t("Current revision"),
                    value: documentRevisionLabel(
                      detailState.value.revisions.find(
                        (revision) =>
                          revision.globalId ===
                          detailState.value.document.currentRevision?.globalId,
                      ) ?? null,
                    ),
                    exempt: "identifier",
                  },
                  {
                    label: t("Editability"),
                    value: t("Editable in NPI One"),
                  },
                  {
                    label: t("Lock"),
                    value: detailState.value.document.currentLock
                      ? t("Checked out")
                      : t("Available"),
                  },
                  {
                    label: t("Lock holder"),
                    value:
                      detailState.value.document.currentLock?.holderUserId ??
                      "—",
                    exempt: "business-data",
                  },
                  {
                    label: t("External retrieval"),
                    value: t("Unavailable"),
                  },
                  {
                    label: t("CAD/PDM connector"),
                    value: t("Unavailable"),
                  },
                ]}
              />
              <div className="detail-actions document-inspector__actions">
                {detailState.value.document.currentLock ? (
                  <Button
                    disabled={
                      !detailState.value.permissions.lock ||
                      !sessionCommandContext ||
                      commandProcessing
                    }
                    onClick={checkIn}
                  >
                    {t("Check in")}
                  </Button>
                ) : (
                  <Button
                    disabled={
                      !detailState.value.permissions.lock ||
                      !sessionCommandContext ||
                      commandProcessing
                    }
                    onClick={checkOut}
                  >
                    {t("Check out")}
                  </Button>
                )}
                <Button
                  disabled={
                    !detailState.value.permissions.revise ||
                    !detailState.value.document.currentLock ||
                    !sessionCommandContext ||
                    commandProcessing
                  }
                  onClick={startRevision}
                >
                  {t("New revision")}
                </Button>
                <Button
                  disabled={
                    !detailState.value.permissions.recoverLock ||
                    !detailState.value.document.currentLock ||
                    !sessionCommandContext ||
                    commandProcessing
                  }
                  onClick={() => {
                    setEditor("recover");
                    setEditorTouched(false);
                    setFormError(null);
                  }}
                >
                  {t("Recover lock")}
                </Button>
              </div>
            </DockedInspector>
          )}
        </div>
      )}

      {editor === "create" && selectedPolicy ? (
        <Panel title={t("Create controlled document")}>
          <form
            className="document-form"
            onSubmit={(event) => {
              event.preventDefault();
              submitCreate();
            }}
          >
            <label>
              <span>{t("Document policy")}</span>
              <Select
                onChange={(event) => {
                  const policy = pageState.value.policies.find(
                    (candidate) =>
                      candidate.versionId === event.currentTarget.value,
                  );
                  if (!policy) return;
                  setCreateForm({
                    policyVersionId: policy.versionId,
                    documentTypeKey: policy.documentTypes[0]?.key ?? "",
                    confidentialityKey: policy.confidentialityKeys[0] ?? "",
                    title: createForm.title,
                  });
                  setEditorTouched(true);
                }}
                value={createForm.policyVersionId}
              >
                {pageState.value.policies.map((policy) => (
                  <option
                    data-language-exempt="business-data"
                    key={policy.versionId}
                    value={policy.versionId}
                  >
                    {policy.title} · v{String(policy.version)}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Document type")}</span>
              <Select
                onChange={(event) => {
                  setCreateForm({
                    ...createForm,
                    documentTypeKey: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                value={createForm.documentTypeKey}
              >
                {selectedPolicy.documentTypes.map((option) => (
                  <option
                    data-language-exempt="business-data"
                    key={option.key}
                    value={option.key}
                  >
                    {option.titleSource}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Confidentiality")}</span>
              <Select
                onChange={(event) => {
                  setCreateForm({
                    ...createForm,
                    confidentialityKey: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                value={createForm.confidentialityKey}
              >
                {selectedPolicy.confidentialityKeys.map((key) => (
                  <option
                    data-language-exempt="identifier"
                    key={key}
                    value={key}
                  >
                    {key}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Title")}</span>
              <TextInput
                maxLength={280}
                onChange={(event) => {
                  setCreateForm({
                    ...createForm,
                    title: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                ref={(element) => {
                  firstEditorControl.current = element;
                }}
                required
                value={createForm.title}
              />
            </label>
            {formError ? (
              <p className="form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions">
              <Button
                disabled={commandProcessing}
                type="submit"
                visual="primary"
              >
                {t("Create document")}
              </Button>
              <Button
                disabled={commandProcessing}
                onClick={clearEditor}
                type="button"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {editor === "revision" && detail && editorPolicy ? (
        <Panel title={t("Create immutable revision")}>
          <form
            className="document-form document-form--revision"
            onSubmit={(event) => {
              event.preventDefault();
              submitRevision();
            }}
          >
            <label>
              <span>{t("Major revision")}</span>
              <TextInput
                inputMode="numeric"
                min="0"
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    major: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                ref={(element) => {
                  firstEditorControl.current = element;
                }}
                required
                type="number"
                value={revisionForm.major}
              />
            </label>
            <label>
              <span>{t("Minor revision")}</span>
              <TextInput
                inputMode="numeric"
                min="0"
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    minor: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                required
                type="number"
                value={revisionForm.minor}
              />
            </label>
            <label>
              <span>{t("Effective date")}</span>
              <TextInput
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    effectiveDate: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                type="date"
                value={revisionForm.effectiveDate}
              />
            </label>
            <label className="document-form__wide">
              <span>{t("Revision reason")}</span>
              <textarea
                maxLength={2_000}
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    reason: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                required
                rows={3}
                value={revisionForm.reason}
              />
            </label>
            <label className="document-form__wide">
              <span>{t("Private revision file")}</span>
              <input
                accept={editorPolicy.allowedMimeTypes.join(",")}
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    file: event.currentTarget.files?.[0] ?? null,
                  });
                  setEditorTouched(true);
                }}
                required
                type="file"
              />
              <small>
                {t("Maximum file size: {{size}}", {
                  size: fileSize(locale, editorPolicy.maximumFileBytes),
                })}
              </small>
            </label>
            {formError ? (
              <p className="form-error document-form__wide" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions document-form__wide">
              <Button
                disabled={commandProcessing}
                type="submit"
                visual="primary"
              >
                {t("Create revision")}
              </Button>
              <Button
                disabled={commandProcessing}
                onClick={clearEditor}
                type="button"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {editor === "recover" && detail?.document.currentLock ? (
        <Panel title={t("Recover document lock")}>
          <form
            className="document-form"
            onSubmit={(event) => {
              event.preventDefault();
              submitRecovery();
            }}
          >
            <label className="document-form__wide">
              <span>{t("Recovery reason")}</span>
              <textarea
                maxLength={1_000}
                onChange={(event) => {
                  setRecoverReason(event.currentTarget.value);
                  setEditorTouched(true);
                }}
                ref={(element) => {
                  firstEditorControl.current = element;
                }}
                required
                rows={3}
                value={recoverReason}
              />
            </label>
            {formError ? (
              <p className="form-error document-form__wide" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions document-form__wide">
              <Button
                disabled={commandProcessing}
                type="submit"
                visual="primary"
              >
                {t("Recover lock")}
              </Button>
              <Button
                disabled={commandProcessing}
                onClick={clearEditor}
                type="button"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {detail && detail.revisions.length > 0 ? (
        <Panel scrollableBody title={t("Immutable revision history")}>
          <table className="data-table data-table--compact">
            <thead>
              <tr>
                <th>{t("Revision")}</th>
                <th>{t("State")}</th>
                <th>{t("Reason")}</th>
                <th>{t("Effective date")}</th>
                <th>{t("Created by")}</th>
                <th>{t("Created")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.revisions.map((revision) => (
                <tr
                  aria-selected={
                    selectedRevision?.globalId === revision.globalId
                  }
                  className={
                    selectedRevision?.globalId === revision.globalId
                      ? "is-selected"
                      : ""
                  }
                  key={revision.globalId}
                >
                  <td>
                    <button
                      className="table-link"
                      data-language-exempt="identifier"
                      onClick={() => {
                        setSelectedRevisionId(revision.globalId);
                        setContentState({ kind: "idle" });
                      }}
                      type="button"
                    >
                      {documentRevisionLabel(revision)}
                    </button>
                  </td>
                  <td>
                    <SemanticStatus label={t("Draft")} tone="info" />
                  </td>
                  <td data-language-exempt="business-data">
                    {revision.reason}
                  </td>
                  <td>
                    {revision.effectiveDate
                      ? formatDate(locale, revision.effectiveDate)
                      : "—"}
                  </td>
                  <td data-language-exempt="business-data">
                    {revision.createdByUserId}
                  </td>
                  <td>{formatDateTime(locale, revision.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : null}

      {selectedRevision && detail ? (
        <div className="document-workspace__evidence-grid">
          <Panel scrollableBody title={t("Exact private files")}>
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th>{t("File")}</th>
                  <th>{t("Size")}</th>
                  <th>{t("Scan")}</th>
                  <th>{t("Integrity")}</th>
                  <th>{t("Preview")}</th>
                  <th>{t("Actions")}</th>
                </tr>
              </thead>
              <tbody>
                {selectedRevision.files.map((file) => (
                  <tr key={file.associationId}>
                    <td>
                      <strong data-language-exempt="business-data">
                        {file.fileName}
                      </strong>
                      <small
                        className="document-file__hash"
                        data-language-exempt="identifier"
                      >
                        SHA-256 {file.sha256}
                      </small>
                    </td>
                    <td>{fileSize(locale, file.sizeBytes)}</td>
                    <td>
                      <SemanticStatus
                        label={
                          file.scanState === "clean"
                            ? t("Clean")
                            : file.scanState === "pending"
                              ? t("Pending")
                              : file.scanState === "infected"
                                ? t("Infected")
                                : t("Failed")
                        }
                        tone={
                          file.scanState === "clean"
                            ? "success"
                            : file.scanState === "pending"
                              ? "warning"
                              : "danger"
                        }
                      />
                    </td>
                    <td>
                      <SemanticStatus
                        label={
                          file.capabilities.integrity.state === "available"
                            ? t("Available")
                            : file.capabilities.integrity.state === "blocked"
                              ? t("Blocked")
                              : t("Unavailable")
                        }
                        tone={capabilityTone(file.capabilities.integrity.state)}
                      />
                    </td>
                    <td>
                      <SemanticStatus
                        label={
                          file.capabilities.preview.state === "available"
                            ? t("Available")
                            : file.capabilities.preview.state === "blocked"
                              ? t("Blocked")
                              : t("Unavailable")
                        }
                        tone={capabilityTone(file.capabilities.preview.state)}
                      />
                    </td>
                    <td>
                      <div className="table-actions">
                        <Button
                          disabled={
                            !detail.permissions.preview ||
                            file.capabilities.preview.state !== "available" ||
                            !sessionCommandContext ||
                            contentState.kind === "processing"
                          }
                          onClick={() => {
                            requestContent(file, "inline");
                          }}
                          visual="ghost"
                        >
                          {t("Preview")}
                        </Button>
                        <Button
                          disabled={
                            !detail.permissions.download ||
                            file.capabilities.download.state !== "available" ||
                            !sessionCommandContext ||
                            contentState.kind === "processing"
                          }
                          onClick={() => {
                            requestContent(file, "attachment");
                          }}
                          visual="ghost"
                        >
                          {t("Download")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel title={t("Provider boundaries")}>
            <DefinitionList
              rows={[
                {
                  label: t("External retrieval"),
                  value: t("Unavailable"),
                },
                {
                  label: t("External policy"),
                  value: t("Not configured"),
                },
                {
                  label: t("CAD/PDM connector"),
                  value: t("Unavailable"),
                },
                {
                  label: t("Connector isolation"),
                  value: t("No outbound request was made"),
                },
              ]}
            />
          </Panel>
        </div>
      ) : null}

      {contentState.kind === "processing" ? (
        <div
          aria-live="polite"
          className="document-content-state"
          role="status"
        >
          <SemanticStatus label={t("Processing")} tone="info" />
          <span>{contentState.label}</span>
        </div>
      ) : contentState.kind === "unavailable" ? (
        <div className="document-content-state" role="status">
          <SemanticStatus label={t("Unavailable")} tone="warning" />
          <span>{t("The requested file capability is not available.")}</span>
          <code data-language-exempt="identifier">
            {contentState.reasonCode}
          </code>
        </div>
      ) : contentState.kind === "failed" ? (
        <div className="document-content-state" role="alert">
          <SemanticStatus label={t("Error")} tone="danger" />
          <RequestFailurePanel failure={contentState.failure} />
        </div>
      ) : contentState.kind === "ready" ? (
        <Panel title={t("Secure native preview")}>
          <div className="document-native-preview">
            <iframe
              sandbox=""
              src={contentState.objectUrl}
              title={t("Preview of {{fileName}}", {
                fileName: contentState.fileName,
              })}
            />
            <span data-language-exempt="identifier">
              {contentState.mimeType}
            </span>
          </div>
        </Panel>
      ) : null}

      {detail ? (
        <div className="document-workspace__history-grid">
          <Panel scrollableBody title={t("Typed relationships")}>
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th>{t("Relationship")}</th>
                  <th>{t("Target identity")}</th>
                  <th>{t("Version")}</th>
                </tr>
              </thead>
              <tbody>
                {detail.relationships.map((relationship) => (
                  <tr key={relationship.globalId}>
                    <td>{relationshipKindLabel(t, relationship.kind)}</td>
                    <td data-language-exempt="identifier">
                      {relationship.targetIdentity}
                    </td>
                    <td>
                      {formatNumber(locale, relationship.targetVersion, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel scrollableBody title={t("Lock history")}>
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th>{t("Event")}</th>
                  <th>{t("Holder")}</th>
                  <th>{t("Actor")}</th>
                  <th>{t("Occurred")}</th>
                </tr>
              </thead>
              <tbody>
                {detail.lockHistory.map((event) => (
                  <tr key={event.globalId}>
                    <td>
                      {event.eventType === "acquired"
                        ? t("Acquired")
                        : event.eventType === "released"
                          ? t("Released")
                          : event.eventType === "recovered"
                            ? t("Recovered")
                            : t("Expired")}
                    </td>
                    <td data-language-exempt="business-data">
                      {event.holderUserId}
                    </td>
                    <td data-language-exempt="business-data">
                      {event.actorUserId}
                    </td>
                    <td>{formatDateTime(locale, event.occurredAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </div>
      ) : null}
    </section>
  );
}
