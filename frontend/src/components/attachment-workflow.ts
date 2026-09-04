import { useCallback, useEffect, useRef, useState } from "react";

import { toRequestFailure, type RequestFailure } from "../api/http";

const ATTACHMENT_TRANSPORT_SKIPPED = Symbol("attachment-transport-skipped");

export type AttachmentScanState = "pending" | "clean" | "infected" | "failed";
export type AttachmentCapabilityState = "available" | "blocked" | "unavailable";

export type AttachmentTruthValue<T> =
  | { readonly kind: "known"; readonly value: T }
  | {
      readonly kind: "unavailable";
      readonly reasonCode?: string;
    };

export interface AttachmentCapabilityTruth {
  readonly state: AttachmentCapabilityState;
  readonly reasonCode: string | null;
}

export interface RegisteredAttachmentTruth {
  readonly fileName: string;
  readonly mimeType: string;
  readonly sizeBytes: number;
  readonly exactRevision: string;
  readonly sha256: string;
  readonly scanState: AttachmentScanState;
  readonly scanObservedAt: AttachmentTruthValue<string | null>;
  readonly private: AttachmentTruthValue<boolean>;
  readonly confidentiality: AttachmentTruthValue<{
    readonly key: string;
  }>;
  readonly provenance: AttachmentTruthValue<string>;
  readonly permission: AttachmentTruthValue<{
    readonly attach: boolean;
    readonly reasonCode: string | null;
  }>;
  readonly capabilities: AttachmentTruthValue<{
    readonly preview: AttachmentCapabilityTruth;
    readonly download: AttachmentCapabilityTruth;
  }>;
}

export type AttachmentFailureStage =
  | "selection"
  | "transport"
  | "registration"
  | "scan";
export type AttachmentWriteState = "none" | "unconfirmed" | "registered";

export type AttachmentWorkflowState =
  | { readonly kind: "loading" }
  | { readonly kind: "empty" }
  | {
      readonly kind: "local_selected";
      readonly file: File;
    }
  | {
      readonly kind: "local_invalid";
      readonly file: File;
      readonly message: string;
    }
  | {
      readonly kind: "transporting";
      readonly file: File;
      readonly progress: {
        readonly loadedBytes: number;
        readonly totalBytes: number | null;
      } | null;
    }
  | {
      readonly kind: "registering";
      readonly file: File;
    }
  | {
      readonly kind: "registered";
      readonly attachment: RegisteredAttachmentTruth;
    }
  | ({
      readonly kind: "failed";
      readonly file: File | null;
      readonly failure: RequestFailure;
    } & (
      | {
          readonly retryable: boolean;
          readonly stage: "selection" | "transport" | "registration";
          readonly writeState: "none";
        }
      | {
          readonly retryable: false;
          readonly stage: "registration";
          readonly writeState: "unconfirmed";
        }
      | {
          readonly retryable: false;
          readonly stage: "registration" | "scan";
          readonly writeState: "registered";
        }
    ))
  | {
      readonly kind: "conflict";
      readonly file: File | null;
      readonly stage: "registration";
      readonly writeState: "unconfirmed";
      readonly failure: RequestFailure;
    }
  | {
      readonly kind: "denied";
      readonly reason: string;
    };

export type AttachmentTransportResult =
  | {
      readonly kind: "registered";
      readonly attachment: RegisteredAttachmentTruth;
    }
  | ({
      readonly kind: "failed";
      readonly failure: RequestFailure;
    } & (
      | {
          readonly retryable: boolean;
          readonly stage: "transport" | "registration";
          readonly writeState: "none";
        }
      | {
          readonly retryable: false;
          readonly stage: "registration";
          readonly writeState: "unconfirmed";
        }
    ))
  | {
      readonly kind: "conflict";
      readonly failure: RequestFailure;
    };

export interface AttachmentTransportContext {
  readonly signal: AbortSignal;
  readonly reportProgress: (
    loadedBytes: number,
    totalBytes: number | null,
  ) => void;
  readonly reportRegistrationStarted: () => void;
}

export type AttachmentTransport = (
  file: File,
  context: AttachmentTransportContext,
) => Promise<AttachmentTransportResult>;

export interface AttachmentWorkflowController {
  readonly state: AttachmentWorkflowState;
  readonly transportAvailable: boolean;
  readonly selectFile: (file: File) => void;
  readonly clearLocal: () => void;
  readonly start: () => void;
  readonly retry: () => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isBoundedString(
  value: unknown,
  minimum = 1,
  maximum = 2048,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum
  );
}

function isRequestFailure(value: unknown): value is RequestFailure {
  if (!isRecord(value)) return false;
  if (
    !(
      value.kind === "problem" ||
      value.kind === "network" ||
      value.kind === "invalid_response" ||
      value.kind === "request_not_ready" ||
      value.kind === "unexpected"
    ) ||
    !(
      value.referenceKind === "trace" ||
      value.referenceKind === "request" ||
      value.referenceKind === "client"
    ) ||
    !isBoundedString(value.referenceId, 1, 256)
  ) {
    return false;
  }
  if (value.kind !== "problem") return value.problem === undefined;
  if (!isRecord(value.problem)) return false;
  const problem = value.problem;
  return (
    isBoundedString(problem.type, 1) &&
    isBoundedString(problem.title, 1, 280) &&
    Number.isInteger(problem.status) &&
    Number(problem.status) >= 400 &&
    Number(problem.status) <= 599 &&
    isBoundedString(problem.code, 1, 100) &&
    isBoundedString(problem.traceId, 1, 128) &&
    typeof problem.retryable === "boolean" &&
    (problem.detail === undefined ||
      isBoundedString(problem.detail, 0, 4000)) &&
    (problem.instance === undefined ||
      isBoundedString(problem.instance, 1, 2048)) &&
    (problem.fieldErrors === undefined ||
      (Array.isArray(problem.fieldErrors) &&
        problem.fieldErrors.length <= 100 &&
        problem.fieldErrors.every(
          (fieldError) =>
            isRecord(fieldError) &&
            isBoundedString(fieldError.path, 1, 500) &&
            isBoundedString(fieldError.message, 1, 1000),
        )))
  );
}

function isTruthValue<T>(
  value: unknown,
  isKnownValue: (candidate: unknown) => candidate is T,
): value is AttachmentTruthValue<T> {
  if (!isRecord(value)) return false;
  if (value.kind === "known") return isKnownValue(value.value);
  return (
    value.kind === "unavailable" &&
    (value.reasonCode === undefined ||
      isBoundedString(value.reasonCode, 1, 256))
  );
}

function isReasonCode(value: unknown): value is string | null {
  return value === null || isBoundedString(value, 1, 256);
}

function isAttachmentCapabilityTruth(
  value: unknown,
): value is AttachmentCapabilityTruth {
  return (
    isRecord(value) &&
    (value.state === "available" ||
      value.state === "blocked" ||
      value.state === "unavailable") &&
    isReasonCode(value.reasonCode)
  );
}

function isRegisteredAttachmentTruth(
  value: unknown,
): value is RegisteredAttachmentTruth {
  if (!isRecord(value)) return false;
  return (
    isBoundedString(value.fileName, 1, 1024) &&
    isBoundedString(value.mimeType, 1, 255) &&
    Number.isSafeInteger(value.sizeBytes) &&
    Number(value.sizeBytes) >= 0 &&
    isBoundedString(value.exactRevision, 1, 256) &&
    typeof value.sha256 === "string" &&
    /^[0-9A-Fa-f]{64}$/u.test(value.sha256) &&
    (value.scanState === "pending" ||
      value.scanState === "clean" ||
      value.scanState === "infected" ||
      value.scanState === "failed") &&
    isTruthValue(
      value.scanObservedAt,
      (candidate): candidate is string | null =>
        candidate === null || isBoundedString(candidate, 1, 128),
    ) &&
    isTruthValue(
      value.private,
      (candidate): candidate is boolean => typeof candidate === "boolean",
    ) &&
    isTruthValue(
      value.confidentiality,
      (candidate): candidate is { readonly key: string } =>
        isRecord(candidate) && isBoundedString(candidate.key, 1, 256),
    ) &&
    isTruthValue(value.provenance, (candidate): candidate is string =>
      isBoundedString(candidate, 1, 2048),
    ) &&
    isTruthValue(
      value.permission,
      (
        candidate,
      ): candidate is {
        readonly attach: boolean;
        readonly reasonCode: string | null;
      } =>
        isRecord(candidate) &&
        typeof candidate.attach === "boolean" &&
        isReasonCode(candidate.reasonCode),
    ) &&
    isTruthValue(
      value.capabilities,
      (
        candidate,
      ): candidate is {
        readonly preview: AttachmentCapabilityTruth;
        readonly download: AttachmentCapabilityTruth;
      } =>
        isRecord(candidate) &&
        isAttachmentCapabilityTruth(candidate.preview) &&
        isAttachmentCapabilityTruth(candidate.download),
    )
  );
}

function isAttachmentTransportResult(
  value: unknown,
): value is AttachmentTransportResult {
  if (!isRecord(value)) return false;
  if (value.kind === "registered")
    return isRegisteredAttachmentTruth(value.attachment);
  if (value.kind === "conflict") return isRequestFailure(value.failure);
  if (value.kind !== "failed" || !isRequestFailure(value.failure)) return false;
  if (
    value.writeState === "none" &&
    (value.stage === "transport" || value.stage === "registration")
  ) {
    return typeof value.retryable === "boolean";
  }
  return (
    value.writeState === "unconfirmed" &&
    value.stage === "registration" &&
    value.retryable === false
  );
}

function strongestRuntimeWriteState(
  value: unknown,
  registrationStarted: boolean,
): AttachmentWriteState {
  if (isRecord(value) && value.writeState === "registered") return "registered";
  if (
    registrationStarted ||
    (isRecord(value) &&
      (value.kind === "registered" ||
        value.kind === "conflict" ||
        value.writeState === "unconfirmed"))
  ) {
    return "unconfirmed";
  }
  return "none";
}

export function normalizeAttachmentWorkflowState(
  state: AttachmentWorkflowState,
): AttachmentWorkflowState {
  if (state.kind !== "failed") return state;
  const runtimeState = state as unknown as {
    readonly retryable: unknown;
    readonly stage: unknown;
    readonly writeState: unknown;
  };
  const base = {
    failure: state.failure,
    file: state.file,
    kind: "failed" as const,
  };
  if (
    runtimeState.stage === "scan" ||
    runtimeState.writeState === "registered"
  ) {
    return {
      ...base,
      retryable: false,
      stage: runtimeState.stage === "scan" ? "scan" : "registration",
      writeState: "registered",
    };
  }
  if (runtimeState.writeState === "unconfirmed") {
    return {
      ...base,
      retryable: false,
      stage: "registration",
      writeState: "unconfirmed",
    };
  }
  if (
    runtimeState.writeState === "none" &&
    typeof runtimeState.retryable === "boolean" &&
    (runtimeState.stage === "selection" ||
      runtimeState.stage === "transport" ||
      runtimeState.stage === "registration")
  ) {
    return {
      ...base,
      retryable: runtimeState.retryable,
      stage: runtimeState.stage,
      writeState: "none",
    };
  }
  return {
    ...base,
    retryable: false,
    stage: "registration",
    writeState: "unconfirmed",
  };
}

export function useAttachmentWorkflow({
  transport,
  validateFile,
  initialState = { kind: "empty" },
}: {
  transport: AttachmentTransport | null;
  validateFile?: (file: File) => string | null;
  initialState?: AttachmentWorkflowState;
}): AttachmentWorkflowController {
  const normalizedInitialState = normalizeAttachmentWorkflowState(initialState);
  const [state, setState] = useState<AttachmentWorkflowState>(
    normalizedInitialState,
  );
  const stateRef = useRef<AttachmentWorkflowState>(normalizedInitialState);
  const operationGeneration = useRef(0);
  const activeController = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const updateState = useCallback(
    (
      update:
        | AttachmentWorkflowState
        | ((candidate: AttachmentWorkflowState) => AttachmentWorkflowState),
    ): void => {
      const candidate = stateRef.current;
      const next = normalizeAttachmentWorkflowState(
        typeof update === "function" ? update(candidate) : update,
      );
      if (next === candidate) return;
      stateRef.current = next;
      setState(next);
    },
    [],
  );

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      operationGeneration.current += 1;
      activeController.current?.abort();
    };
  }, []);

  const selectFile = useCallback(
    (file: File): void => {
      if (!mounted.current) return;
      const currentState = stateRef.current;
      const selectable =
        currentState.kind === "empty" ||
        currentState.kind === "local_selected" ||
        currentState.kind === "local_invalid" ||
        (currentState.kind === "failed" && currentState.writeState === "none");
      if (!selectable) {
        return;
      }
      operationGeneration.current += 1;
      activeController.current?.abort();
      activeController.current = null;
      const message = validateFile?.(file) ?? null;
      updateState(
        message
          ? { file, kind: "local_invalid", message }
          : { file, kind: "local_selected" },
      );
    },
    [updateState, validateFile],
  );

  const clearLocal = useCallback((): void => {
    if (!mounted.current) return;
    const currentState = stateRef.current;
    const clearable =
      currentState.kind === "local_selected" ||
      currentState.kind === "local_invalid" ||
      (currentState.kind === "failed" &&
        currentState.file !== null &&
        currentState.writeState === "none");
    if (!clearable) return;
    operationGeneration.current += 1;
    activeController.current?.abort();
    activeController.current = null;
    updateState({ kind: "empty" });
  }, [updateState]);

  const runTransport = useCallback(
    (file: File): void => {
      if (!transport || !mounted.current) return;
      operationGeneration.current += 1;
      const generation = operationGeneration.current;
      activeController.current?.abort();
      const controller = new AbortController();
      activeController.current = controller;
      let registrationStarted = false;
      let settled = false;
      updateState({ file, kind: "transporting", progress: null });

      const current = (): boolean =>
        mounted.current &&
        operationGeneration.current === generation &&
        !controller.signal.aborted &&
        !settled;

      void Promise.resolve()
        .then<AttachmentTransportResult | typeof ATTACHMENT_TRANSPORT_SKIPPED>(
          () => {
            if (!current()) return ATTACHMENT_TRANSPORT_SKIPPED;
            return transport(file, {
              signal: controller.signal,
              reportProgress: (loadedBytes, totalBytes) => {
                if (
                  !current() ||
                  !Number.isSafeInteger(loadedBytes) ||
                  loadedBytes < 0 ||
                  (totalBytes !== null &&
                    (!Number.isSafeInteger(totalBytes) ||
                      totalBytes <= 0 ||
                      loadedBytes > totalBytes))
                ) {
                  return;
                }
                updateState((candidate) => {
                  if (
                    !current() ||
                    candidate.kind !== "transporting" ||
                    candidate.file !== file ||
                    (candidate.progress !== null &&
                      loadedBytes < candidate.progress.loadedBytes)
                  ) {
                    return candidate;
                  }
                  const resolvedTotal =
                    totalBytes ?? candidate.progress?.totalBytes ?? null;
                  if (resolvedTotal !== null && loadedBytes > resolvedTotal) {
                    return candidate;
                  }
                  return {
                    file,
                    kind: "transporting",
                    progress: {
                      loadedBytes,
                      totalBytes: resolvedTotal,
                    },
                  };
                });
              },
              reportRegistrationStarted: () => {
                if (!current() || registrationStarted) return;
                registrationStarted = true;
                updateState((candidate) => {
                  if (
                    !current() ||
                    candidate.kind !== "transporting" ||
                    candidate.file !== file
                  ) {
                    return candidate;
                  }
                  return { file, kind: "registering" };
                });
              },
            });
          },
        )
        .then((rawResult) => {
          if (rawResult === ATTACHMENT_TRANSPORT_SKIPPED || !current()) return;
          const result: unknown = rawResult;
          const validResult = isAttachmentTransportResult(result);
          if (!validResult) {
            const writeState = strongestRuntimeWriteState(
              result,
              registrationStarted,
            );
            settled = true;
            activeController.current = null;
            const failure = toRequestFailure(
              new Error("Attachment transport returned an invalid result."),
            );
            if (writeState === "registered") {
              updateState({
                failure,
                file,
                kind: "failed",
                retryable: false,
                stage:
                  isRecord(result) && result.stage === "scan"
                    ? "scan"
                    : "registration",
                writeState,
              });
              return;
            }
            if (writeState === "unconfirmed") {
              updateState({
                failure,
                file,
                kind: "failed",
                retryable: false,
                stage: "registration",
                writeState,
              });
              return;
            }
            updateState({
              failure,
              file,
              kind: "failed",
              retryable: false,
              stage: "transport",
              writeState,
            });
            return;
          }
          settled = true;
          activeController.current = null;
          if (result.kind === "registered") {
            updateState({
              attachment: result.attachment,
              kind: "registered",
            });
            return;
          }
          if (result.kind === "conflict") {
            updateState({
              failure: result.failure,
              file,
              kind: "conflict",
              stage: "registration",
              writeState: "unconfirmed",
            });
            return;
          }
          if (registrationStarted || result.writeState === "unconfirmed") {
            updateState({
              failure: result.failure,
              file,
              kind: "failed",
              retryable: false,
              stage: "registration",
              writeState: "unconfirmed",
            });
            return;
          }
          updateState({
            failure: result.failure,
            file,
            kind: "failed",
            retryable: result.retryable,
            stage: result.stage,
            writeState: "none",
          });
        })
        .catch((error: unknown) => {
          if (!current()) return;
          settled = true;
          activeController.current = null;
          const failure = toRequestFailure(error);
          if (registrationStarted) {
            updateState({
              failure,
              file,
              kind: "failed",
              retryable: false,
              stage: "registration",
              writeState: "unconfirmed",
            });
            return;
          }
          updateState({
            failure,
            file,
            kind: "failed",
            retryable: false,
            stage: "transport",
            writeState: "none",
          });
        });
    },
    [transport, updateState],
  );

  const start = useCallback((): void => {
    const currentState = stateRef.current;
    if (currentState.kind === "local_selected") {
      runTransport(currentState.file);
    }
  }, [runTransport]);

  const retry = useCallback((): void => {
    const currentState = stateRef.current;
    if (
      currentState.kind !== "failed" ||
      !currentState.retryable ||
      currentState.file === null
    ) {
      return;
    }
    runTransport(currentState.file);
  }, [runTransport]);

  const presentedState =
    state.kind === "local_invalid" && validateFile
      ? {
          ...state,
          message: validateFile(state.file) ?? state.message,
        }
      : state;

  return {
    state: presentedState,
    transportAvailable: transport !== null,
    selectFile,
    clearLocal,
    start,
    retry,
  };
}
