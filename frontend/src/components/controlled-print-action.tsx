import { useCallback, useEffect, useRef, useState } from "react";

import type {
  ControlledPrintCapabilityViewModel,
  ControlledPrintDataSource,
  ControlledPrintSnapshotViewModel,
  ControlledPrintSourceIdentity,
} from "../api/controlled-print-data-source";
import { ControlledPrintCancelledError } from "../api/controlled-print-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { useI18n, type SessionCommandContext } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import { ImpactReview, SemanticStatus } from "./primitives";

type ControlledPrintActionState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "unavailable" }
  | { kind: "no_permission"; failure: RequestFailure }
  | { kind: "ready"; capability: ControlledPrintCapabilityViewModel }
  | { kind: "review"; capability: ControlledPrintCapabilityViewModel }
  | { kind: "creating"; capability: ControlledPrintCapabilityViewModel }
  | {
      kind: "retained";
      replayed: boolean;
      snapshot: ControlledPrintSnapshotViewModel;
    }
  | { kind: "downloading"; snapshot: ControlledPrintSnapshotViewModel }
  | { kind: "downloaded"; snapshot: ControlledPrintSnapshotViewModel }
  | {
      kind: "failed";
      failure: RequestFailure;
      operation: "capability" | "create" | "download";
      capability?: ControlledPrintCapabilityViewModel;
      snapshot?: ControlledPrintSnapshotViewModel;
    }
  | { kind: "conflict"; failure: RequestFailure };

function classifyFailure(
  error: unknown,
  operation: "capability" | "create" | "download",
  context: {
    capability?: ControlledPrintCapabilityViewModel;
    snapshot?: ControlledPrintSnapshotViewModel;
  } = {},
): ControlledPrintActionState {
  const failure = toRequestFailure(error);
  const status = failure.problem?.status;
  if (operation === "capability" && status === 404)
    return { kind: "unavailable" };
  if (status === 401 || status === 403)
    return { failure, kind: "no_permission" };
  if (status === 409) return { failure, kind: "conflict" };
  return { failure, kind: "failed", operation, ...context };
}

function failureReferenceLabel(
  failure: RequestFailure,
  t: ReturnType<typeof useI18n>["t"],
): string {
  if (failure.referenceKind === "trace") return t("Trace ID");
  if (failure.referenceKind === "request") return t("Request ID");
  return t("Client reference ID");
}

export function ControlledPrintAction({
  commandContext: commandContextOverride,
  dataSource,
  projectId,
  source,
}: {
  commandContext?: SessionCommandContext | null | undefined;
  dataSource: ControlledPrintDataSource;
  projectId: string;
  source: ControlledPrintSourceIdentity;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const commandContext = commandContextOverride ?? sessionCommandContext;
  const [state, setState] = useState<ControlledPrintActionState>({
    kind: "idle",
  });
  const activeRequest = useRef<AbortController | null>(null);
  const actionGroupRef = useRef<HTMLDivElement | null>(null);
  const idempotencyKey = useRef<string | null>(null);

  const cancelActiveRequest = useCallback((): void => {
    activeRequest.current?.abort();
    activeRequest.current = null;
  }, []);

  useEffect(() => {
    cancelActiveRequest();
    idempotencyKey.current = null;
    setState({ kind: "idle" });
    return cancelActiveRequest;
  }, [
    cancelActiveRequest,
    dataSource,
    locale,
    projectId,
    source.sourceGlobalId,
    source.sourceKind,
    source.sourceVersion,
  ]);

  const checkCapability = useCallback((): void => {
    cancelActiveRequest();
    const controller = new AbortController();
    activeRequest.current = controller;
    setState({ kind: "checking" });
    void dataSource
      .loadCapability(projectId, source, locale, controller.signal)
      .then((capability) => {
        if (controller.signal.aborted || activeRequest.current !== controller)
          return;
        activeRequest.current = null;
        setState(
          capability.available && capability.permissions.create
            ? { capability, kind: "ready" }
            : { kind: "unavailable" },
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          activeRequest.current !== controller ||
          error instanceof ControlledPrintCancelledError
        ) {
          return;
        }
        activeRequest.current = null;
        setState(classifyFailure(error, "capability"));
      });
  }, [cancelActiveRequest, dataSource, locale, projectId, source]);

  const createSnapshot = useCallback(
    (capability: ControlledPrintCapabilityViewModel): void => {
      if (!commandContext) return;
      cancelActiveRequest();
      const controller = new AbortController();
      activeRequest.current = controller;
      const key =
        idempotencyKey.current ??
        `controlled-print-${globalThis.crypto.randomUUID()}`;
      idempotencyKey.current = key;
      setState({ capability, kind: "creating" });
      void dataSource
        .createSnapshot(projectId, source, locale, {
          csrfToken: commandContext.csrfToken,
          idempotencyKey: key,
          signal: controller.signal,
        })
        .then(({ replayed, snapshot }) => {
          if (controller.signal.aborted || activeRequest.current !== controller)
            return;
          activeRequest.current = null;
          setState({ kind: "retained", replayed, snapshot });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            activeRequest.current !== controller ||
            error instanceof ControlledPrintCancelledError
          ) {
            return;
          }
          activeRequest.current = null;
          setState(classifyFailure(error, "create", { capability }));
        });
    },
    [
      cancelActiveRequest,
      commandContext,
      dataSource,
      locale,
      projectId,
      source,
    ],
  );

  const downloadSnapshot = useCallback(
    (snapshot: ControlledPrintSnapshotViewModel): void => {
      cancelActiveRequest();
      const controller = new AbortController();
      activeRequest.current = controller;
      setState({ kind: "downloading", snapshot });
      void dataSource
        .download(projectId, snapshot, controller.signal)
        .then((result) => {
          if (controller.signal.aborted || activeRequest.current !== controller)
            return;
          activeRequest.current = null;
          const url = globalThis.URL.createObjectURL(result.blob);
          const anchor = document.createElement("a");
          anchor.download = result.fileName;
          anchor.href = url;
          anchor.rel = "noopener";
          anchor.click();
          globalThis.URL.revokeObjectURL(url);
          setState({ kind: "downloaded", snapshot });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            activeRequest.current !== controller ||
            error instanceof ControlledPrintCancelledError
          ) {
            return;
          }
          activeRequest.current = null;
          setState(classifyFailure(error, "download", { snapshot }));
        });
    },
    [cancelActiveRequest, dataSource, projectId],
  );

  const retainedSnapshot =
    state.kind === "retained" ||
    state.kind === "downloading" ||
    state.kind === "downloaded"
      ? state.snapshot
      : state.kind === "failed" && state.operation === "download"
        ? state.snapshot
        : undefined;
  const failure =
    state.kind === "failed" ||
    state.kind === "conflict" ||
    state.kind === "no_permission"
      ? state.failure
      : null;

  let status = <SemanticStatus label={t("Controlled print not checked")} />;
  let buttonLabel = t("Check controlled print availability");
  let buttonIcon: "document" | "refresh" = "document";
  let buttonDisabled = false;
  let buttonAction = checkCapability;

  if (state.kind === "checking") {
    status = (
      <SemanticStatus
        label={t("Checking controlled print availability")}
        tone="info"
      />
    );
    buttonLabel = t("Checking controlled print availability");
    buttonDisabled = true;
  } else if (state.kind === "unavailable") {
    status = <SemanticStatus label={t("Controlled print is unavailable")} />;
    buttonLabel = t("Check again");
    buttonIcon = "refresh";
  } else if (state.kind === "no_permission") {
    status = (
      <SemanticStatus
        label={t("Controlled print permission unavailable")}
        tone="warning"
      />
    );
    buttonLabel = t("Check again");
    buttonIcon = "refresh";
  } else if (state.kind === "ready" || state.kind === "review") {
    status = (
      <SemanticStatus label={t("Controlled print is ready")} tone="info" />
    );
    buttonLabel = t("Create controlled PDF");
    buttonDisabled = commandContext === null;
    buttonAction = () => {
      setState({ capability: state.capability, kind: "review" });
    };
  } else if (state.kind === "creating") {
    status = (
      <SemanticStatus label={t("Creating controlled PDF")} tone="info" />
    );
    buttonLabel = t("Creating controlled PDF");
    buttonDisabled = true;
  } else if (retainedSnapshot) {
    status = (
      <SemanticStatus
        label={
          state.kind === "downloading"
            ? t("Downloading retained PDF")
            : state.kind === "downloaded"
              ? t("Retained PDF downloaded")
              : state.kind === "retained" && state.replayed
                ? t("Controlled PDF replayed from retained output")
                : t("Controlled PDF retained")
        }
        tone="success"
      />
    );
    buttonLabel =
      state.kind === "downloading"
        ? t("Downloading retained PDF")
        : state.kind === "failed"
          ? t("Retry retained PDF download")
          : t("Download retained PDF");
    buttonDisabled = state.kind === "downloading";
    buttonAction = () => {
      downloadSnapshot(retainedSnapshot);
    };
  } else if (state.kind === "conflict") {
    status = (
      <SemanticStatus label={t("Controlled print conflict")} tone="warning" />
    );
    buttonLabel = t("Check again");
    buttonIcon = "refresh";
  } else if (state.kind === "failed") {
    status = (
      <SemanticStatus
        label={t("Controlled print could not be completed safely")}
        tone="danger"
      />
    );
    buttonLabel =
      state.operation === "create"
        ? t("Retry controlled PDF creation")
        : t("Retry controlled print");
    buttonIcon = "refresh";
    if (state.operation === "create" && state.capability) {
      const capability = state.capability;
      buttonAction = () => {
        createSnapshot(capability);
      };
    } else {
      buttonAction = checkCapability;
    }
  }

  return (
    <div
      aria-label={t("Controlled print")}
      className="controlled-print-action"
      ref={actionGroupRef}
      role="group"
    >
      <div className="controlled-print-action__truth" role="status">
        {status}
        {state.kind === "unavailable" ? (
          <small>
            {t(
              "No approved controlled print is available for this exact source, version, and language.",
            )}
          </small>
        ) : state.kind === "no_permission" ? (
          <small>
            {t(
              "You do not have permission to use controlled print for this source.",
            )}
          </small>
        ) : state.kind === "ready" && !commandContext ? (
          <small>
            {t(
              "An authenticated session is required to create a controlled PDF.",
            )}
          </small>
        ) : retainedSnapshot ? (
          <small data-language-exempt="business-data">
            {retainedSnapshot.output.fileName}
          </small>
        ) : state.kind === "conflict" ? (
          <small>
            {t("Reload the Project before creating another controlled print.")}
          </small>
        ) : null}
        {failure ? (
          <small className="controlled-print-action__reference">
            {failureReferenceLabel(failure, t)}:{" "}
            <code data-language-exempt="identifier">{failure.referenceId}</code>
          </small>
        ) : null}
      </div>
      <Button
        disabled={buttonDisabled}
        icon={buttonIcon}
        onClick={buttonAction}
        visual="secondary"
      >
        {buttonLabel}
      </Button>
      {state.kind === "review" ? (
        <ImpactReview
          confirmLabel={t("Create retained PDF")}
          contextRows={[
            {
              exempt: "identifier",
              label: t("Language"),
              value: state.capability.language,
            },
            {
              exempt: "identifier",
              label: t("Mapping version"),
              value: state.capability.registry?.version ?? "—",
            },
          ]}
          details={{
            audit: t("Creation and each retained download are recorded."),
            failureHandling: t(
              "No success is shown unless the snapshot, private file, output, audit, and receipt are sealed atomically.",
            ),
            impact: t(
              "Creates one immutable controlled snapshot and retains one private PDF.",
            ),
            irreversible: t(
              "The snapshot, output, and audit history cannot be replaced or deleted.",
            ),
            objectIdentity: source.sourceGlobalId,
            permission: t("Exact controlled-print policy printer authority."),
            version: String(source.sourceVersion),
          }}
          onCancel={() => {
            setState({ capability: state.capability, kind: "ready" });
          }}
          onConfirm={() => {
            createSnapshot(state.capability);
          }}
          reasonRequired={false}
          returnFocusTarget={() =>
            actionGroupRef.current?.querySelector<HTMLElement>("ix-button") ??
            actionGroupRef.current
          }
          title={t("Create immutable controlled PDF")}
        />
      ) : null}
    </div>
  );
}
