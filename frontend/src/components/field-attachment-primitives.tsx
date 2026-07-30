import { useId, useRef, type InputHTMLAttributes, type ReactNode } from "react";

import type { SourceStatus, SourceSystem } from "../domain/view-models";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { CompactAction } from "../ui-adapters/npi-ui";
import {
  normalizeAttachmentWorkflowState,
  type AttachmentCapabilityTruth,
  type AttachmentFailureStage,
  type AttachmentScanState,
  type AttachmentTruthValue,
  type AttachmentWorkflowController,
  type AttachmentWorkflowState,
  type AttachmentWriteState,
  type RegisteredAttachmentTruth,
} from "./attachment-workflow";
import { RequestFailurePanel } from "./problem-details-panel";
import {
  DefinitionList,
  SemanticStatus,
  SourceSystemIdentity,
} from "./primitives";

export type FieldEditability =
  | { readonly kind: "editable" }
  | { readonly kind: "read_only"; readonly reason: string }
  | {
      readonly kind: "conditional";
      readonly editable: boolean;
      readonly condition: string;
    }
  | { readonly kind: "denied"; readonly reason: string };

export type FieldValidation =
  | { readonly kind: "not_validated" }
  | { readonly kind: "valid"; readonly message?: string }
  | { readonly kind: "invalid"; readonly message: string };

export type FieldEffectivity =
  | {
      readonly kind: "effective";
      readonly effectiveDate?: string;
    }
  | {
      readonly kind: "future";
      readonly effectiveDate: string;
    }
  | {
      readonly kind: "superseded";
      readonly effectiveDate?: string;
    }
  | { readonly kind: "not_applicable" }
  | { readonly kind: "unavailable" };

export interface FieldControlAccessibility {
  readonly id: string;
  readonly required: boolean;
  readonly readOnly: boolean;
  readonly disabled: boolean;
  readonly "aria-required": true | undefined;
  readonly "aria-invalid": true | undefined;
  readonly "aria-describedby": string;
}

function fieldEditabilityLabel(
  editability: FieldEditability,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (editability.kind) {
    case "editable":
      return t("Editable");
    case "read_only":
      return t("Read only");
    case "conditional":
      return editability.editable
        ? t("Conditionally editable")
        : t("Conditionally read only");
    case "denied":
      return t("Access denied");
  }
}

function fieldValidationLabel(
  validation: FieldValidation,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (validation.kind) {
    case "not_validated":
      return t("Not validated");
    case "valid":
      return t("Valid");
    case "invalid":
      return t("Validation error");
  }
}

function fieldEffectivityLabel(
  effectivity: FieldEffectivity,
  locale: ReturnType<typeof useI18n>["locale"],
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (effectivity.kind) {
    case "effective":
      return effectivity.effectiveDate
        ? t("Effective from {{date}}", {
            date: formatDate(locale, effectivity.effectiveDate),
          })
        : t("Effective");
    case "future":
      return t("Effective from {{date}}", {
        date: formatDate(locale, effectivity.effectiveDate),
      });
    case "superseded":
      return effectivity.effectiveDate
        ? t("Superseded on {{date}}", {
            date: formatDate(locale, effectivity.effectiveDate),
          })
        : t("Superseded");
    case "not_applicable":
      return t("Not applicable");
    case "unavailable":
      return t("Not provided by this workspace");
  }
}

export function FieldTruth({
  id,
  label,
  required,
  editability,
  sourceSystem,
  editableIn,
  lockReason,
  validation,
  unit,
  exactVersion,
  effectivity,
  help,
  renderControl,
}: {
  id: string;
  label: string;
  required: boolean;
  editability: FieldEditability;
  sourceSystem: SourceSystem;
  editableIn: SourceStatus["editableIn"];
  lockReason: string | null;
  validation: FieldValidation;
  unit: string | null;
  exactVersion: string | null;
  effectivity: FieldEffectivity;
  help?: string;
  renderControl: (properties: FieldControlAccessibility) => ReactNode;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const generatedId = useId().replaceAll(":", "");
  const descriptionIds = {
    condition: `${id}-${generatedId}-condition`,
    effectivity: `${id}-${generatedId}-effectivity`,
    help: `${id}-${generatedId}-help`,
    lock: `${id}-${generatedId}-lock`,
    unit: `${id}-${generatedId}-unit`,
    validation: `${id}-${generatedId}-validation`,
    version: `${id}-${generatedId}-version`,
  };
  const describedBy = [
    help ? descriptionIds.help : null,
    descriptionIds.unit,
    descriptionIds.validation,
    lockReason ||
    editability.kind === "read_only" ||
    editability.kind === "denied" ||
    (editability.kind === "conditional" && !editability.editable)
      ? descriptionIds.lock
      : null,
    editability.kind === "conditional" ? descriptionIds.condition : null,
    descriptionIds.version,
    descriptionIds.effectivity,
  ]
    .filter((value): value is string => value !== null)
    .join(" ");
  const readOnly =
    editability.kind === "read_only" ||
    (editability.kind === "conditional" && !editability.editable);
  const disabled = editability.kind === "denied";
  const validationTone =
    validation.kind === "invalid"
      ? "danger"
      : validation.kind === "valid"
        ? "success"
        : "neutral";

  return (
    <section
      aria-labelledby={`${id}-${generatedId}-label`}
      className="field-truth"
      data-field-editability={editability.kind}
    >
      <div className="field-truth__heading">
        <label
          className="field-truth__label"
          htmlFor={id}
          id={`${id}-${generatedId}-label`}
        >
          {label}
        </label>
        <SemanticStatus
          label={required ? t("Required") : t("Optional")}
          tone={required ? "info" : "neutral"}
        />
        <SemanticStatus
          label={fieldEditabilityLabel(editability, t)}
          tone={disabled ? "warning" : "neutral"}
        />
      </div>
      {renderControl({
        id,
        required,
        readOnly,
        disabled,
        "aria-required": required ? true : undefined,
        "aria-invalid": validation.kind === "invalid" ? true : undefined,
        "aria-describedby": describedBy,
      })}
      <dl className="field-truth__metadata">
        <div className="field-truth__metadata-cell">
          <dt>{t("Source")}</dt>
          <dd>
            <SourceSystemIdentity sourceSystem={sourceSystem} />
          </dd>
        </div>
        <div className="field-truth__metadata-cell">
          <dt>{t("Editable in")}</dt>
          <dd>
            {editableIn === "NONE" ? (
              t("No editable system")
            ) : (
              <SourceSystemIdentity sourceSystem={editableIn} />
            )}
          </dd>
        </div>
        <div className="field-truth__metadata-cell" id={descriptionIds.unit}>
          <dt>{t("Unit")}</dt>
          <dd data-language-exempt={unit ? "unit" : undefined}>
            {unit ?? t("Not applicable")}
          </dd>
        </div>
        <div className="field-truth__metadata-cell" id={descriptionIds.version}>
          <dt>{t("Exact version")}</dt>
          <dd data-language-exempt={exactVersion ? "identifier" : undefined}>
            {exactVersion ?? t("Not provided by this workspace")}
          </dd>
        </div>
        <div
          className="field-truth__metadata-cell"
          id={descriptionIds.effectivity}
        >
          <dt>{t("Effectivity")}</dt>
          <dd>{fieldEffectivityLabel(effectivity, locale, t)}</dd>
        </div>
      </dl>
      {help ? (
        <p className="field-truth__help" id={descriptionIds.help}>
          {help}
        </p>
      ) : null}
      {editability.kind === "conditional" ? (
        <p className="field-truth__condition" id={descriptionIds.condition}>
          <strong>{t("Edit condition")}:</strong> {editability.condition}
        </p>
      ) : null}
      {lockReason ||
      editability.kind === "read_only" ||
      editability.kind === "denied" ||
      (editability.kind === "conditional" && !editability.editable) ? (
        <p className="field-truth__lock" id={descriptionIds.lock}>
          <strong>{t("Lock reason")}:</strong>{" "}
          {lockReason ??
            (editability.kind === "read_only" || editability.kind === "denied"
              ? editability.reason
              : editability.kind === "conditional"
                ? editability.condition
                : t("Not provided by this workspace"))}
        </p>
      ) : null}
      <div className="field-truth__validation" id={descriptionIds.validation}>
        <SemanticStatus
          label={fieldValidationLabel(validation, t)}
          tone={validationTone}
        />
        {validation.kind !== "not_validated" && validation.message ? (
          <span>{validation.message}</span>
        ) : null}
      </div>
    </section>
  );
}

export type {
  AttachmentCapabilityState,
  AttachmentCapabilityTruth,
  AttachmentFailureStage,
  AttachmentScanState,
  AttachmentTransport,
  AttachmentTransportContext,
  AttachmentTransportResult,
  AttachmentTruthValue,
  AttachmentWorkflowController,
  AttachmentWorkflowState,
  AttachmentWriteState,
  RegisteredAttachmentTruth,
} from "./attachment-workflow";

function localFileFromState(state: AttachmentWorkflowState): File | null {
  switch (state.kind) {
    case "local_selected":
    case "local_invalid":
    case "transporting":
    case "registering":
      return state.file;
    case "failed":
    case "conflict":
      return state.file;
    default:
      return null;
  }
}

function LocalAttachmentFile({ file }: { file: File }): React.JSX.Element {
  const { locale, t } = useI18n();
  return (
    <DefinitionList
      rows={[
        {
          label: t("File name"),
          value: file.name,
          exempt: "business-data",
        },
        {
          label: t("File media type"),
          value: file.type || t("Not provided"),
          ...(file.type ? { exempt: "identifier" as const } : {}),
        },
        {
          label: t("File size"),
          value: (
            <>
              {formatNumber(locale, file.size, 0)}{" "}
              <span data-language-exempt="unit">B</span>
            </>
          ),
        },
      ]}
    />
  );
}

function attachmentScanLabel(
  state: AttachmentScanState,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (state) {
    case "pending":
      return t("Scan pending");
    case "clean":
      return t("No threat found");
    case "failed":
      return t("Scan failed");
    case "infected":
      return t("Threat detected");
  }
}

function attachmentScanTone(
  state: AttachmentScanState,
): "info" | "success" | "warning" | "danger" {
  switch (state) {
    case "pending":
      return "info";
    case "clean":
      return "success";
    case "failed":
      return "warning";
    case "infected":
      return "danger";
  }
}

function attachmentFailureStageLabel(
  stage: AttachmentFailureStage,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (stage) {
    case "selection":
      return t("Local selection");
    case "transport":
      return t("File transport");
    case "registration":
      return t("File registration");
    case "scan":
      return t("File scanning");
  }
}

function attachmentWriteStateLabel(
  state: AttachmentWriteState,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (state) {
    case "none":
      return t("No server write occurred");
    case "unconfirmed":
      return t("Server write is unconfirmed");
    case "registered":
      return t("Registered revision retained");
  }
}

function capabilityLabel(
  capability: AttachmentCapabilityTruth,
  scanState: AttachmentScanState,
  t: ReturnType<typeof useI18n>["t"],
): ReactNode {
  const label =
    scanState !== "clean" && capability.state === "available"
      ? t("Source reported available; blocked by scan state")
      : capability.state === "available"
        ? t("Available")
        : capability.state === "blocked"
          ? t("Blocked")
          : t("Unavailable");
  return (
    <span className="controlled-code-value">
      <span>{label}</span>
      {capability.reasonCode ? (
        <code data-language-exempt="identifier">{capability.reasonCode}</code>
      ) : null}
    </span>
  );
}

function unavailableTruth(
  value: AttachmentTruthValue<unknown>,
  t: ReturnType<typeof useI18n>["t"],
): ReactNode {
  if (value.kind === "known") return null;
  return (
    <span className="controlled-code-value">
      <span>{t("Not provided by this workspace")}</span>
      {value.reasonCode ? (
        <code data-language-exempt="identifier">{value.reasonCode}</code>
      ) : null}
    </span>
  );
}

function RegisteredAttachment({
  attachment,
}: {
  attachment: RegisteredAttachmentTruth;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const privateValue =
    attachment.private.kind === "known"
      ? attachment.private.value
        ? t("Private")
        : t("Not private")
      : unavailableTruth(attachment.private, t);
  const confidentialityValue =
    attachment.confidentiality.kind === "known" ? (
      <code data-language-exempt="identifier">
        {attachment.confidentiality.value.key}
      </code>
    ) : (
      unavailableTruth(attachment.confidentiality, t)
    );
  const provenanceValue =
    attachment.provenance.kind === "known" ? (
      <code data-language-exempt="identifier">
        {attachment.provenance.value}
      </code>
    ) : (
      unavailableTruth(attachment.provenance, t)
    );
  const permissionValue =
    attachment.permission.kind === "known" ? (
      <span className="controlled-code-value">
        <span>
          {attachment.permission.value.attach
            ? t("Attachment permitted")
            : t("Attachment not permitted")}
        </span>
        {attachment.permission.value.reasonCode ? (
          <code data-language-exempt="identifier">
            {attachment.permission.value.reasonCode}
          </code>
        ) : null}
      </span>
    ) : (
      unavailableTruth(attachment.permission, t)
    );
  const previewValue =
    attachment.capabilities.kind === "known"
      ? capabilityLabel(
          attachment.capabilities.value.preview,
          attachment.scanState,
          t,
        )
      : unavailableTruth(attachment.capabilities, t);
  const downloadValue =
    attachment.capabilities.kind === "known"
      ? capabilityLabel(
          attachment.capabilities.value.download,
          attachment.scanState,
          t,
        )
      : unavailableTruth(attachment.capabilities, t);

  return (
    <section
      aria-label={t("Registered attachment truth")}
      className="attachment-truth__registered"
    >
      <SemanticStatus
        label={attachmentScanLabel(attachment.scanState, t)}
        tone={attachmentScanTone(attachment.scanState)}
      />
      <DefinitionList
        rows={[
          {
            label: t("File name"),
            value: attachment.fileName,
            exempt: "business-data",
          },
          {
            label: t("File media type"),
            value: attachment.mimeType,
            exempt: "identifier",
          },
          {
            label: t("File size"),
            value: (
              <>
                {formatNumber(locale, attachment.sizeBytes, 0)}{" "}
                <span data-language-exempt="unit">B</span>
              </>
            ),
          },
          {
            label: t("Exact revision"),
            value: attachment.exactRevision,
            exempt: "identifier",
          },
          {
            label: t("File hash"),
            value: attachment.sha256,
            exempt: "identifier",
          },
          {
            label: t("Scan State"),
            value: attachmentScanLabel(attachment.scanState, t),
          },
          {
            label: t("Scan observed"),
            value:
              attachment.scanObservedAt.kind === "unavailable"
                ? unavailableTruth(attachment.scanObservedAt, t)
                : attachment.scanObservedAt.value
                  ? formatDateTime(locale, attachment.scanObservedAt.value)
                  : t("Not observed"),
          },
          { label: t("Privacy"), value: privateValue },
          { label: t("Confidentiality"), value: confidentialityValue },
          { label: t("Provenance"), value: provenanceValue },
          { label: t("Attachment permission"), value: permissionValue },
          { label: t("Preview capability"), value: previewValue },
          { label: t("Download capability"), value: downloadValue },
        ]}
      />
      {attachment.scanState === "pending" ? (
        <p aria-live="polite" className="attachment-truth__notice">
          {t(
            "The registered revision is awaiting a scanner result. No safe-file capability is implied.",
          )}
        </p>
      ) : attachment.scanState === "infected" ? (
        <p className="attachment-truth__notice" role="alert">
          {t(
            "The scanner detected a threat. The registered revision remains visible for recovery, but no file action is available.",
          )}
        </p>
      ) : attachment.scanState === "failed" ? (
        <p className="attachment-truth__notice" role="alert">
          {t(
            "File scanning failed. Recovery requires an authorized server action; no retry or replacement is assumed.",
          )}
        </p>
      ) : (
        <p className="attachment-truth__notice" role="status">
          {t(
            "The scanner reported no threat for this exact registered revision.",
          )}
        </p>
      )}
    </section>
  );
}

type FileInputCapture = InputHTMLAttributes<HTMLInputElement>["capture"];

interface AttachmentFieldCommonProps {
  readonly id: string;
  readonly label: string;
  readonly access?: "editable" | "read_only";
  readonly accept?: string;
  readonly capture?: FileInputCapture;
  readonly guidance?: string;
  readonly inputAccessibility?: FieldControlAccessibility;
  readonly onReload?: () => void;
}

type AttachmentFieldWorkflowProps = AttachmentFieldCommonProps & {
  readonly workflow: AttachmentWorkflowController;
  readonly state?: never;
  readonly onSelectFile?: never;
  readonly onClearLocal?: never;
  readonly onStart?: never;
  readonly onRetry?: never;
};

type AttachmentFieldControlledProps = AttachmentFieldCommonProps & {
  readonly workflow?: never;
  readonly state: AttachmentWorkflowState;
  readonly onSelectFile?: (file: File) => void;
  readonly onClearLocal?: () => void;
  readonly onStart?: () => void;
  readonly onRetry?: () => void;
};

export type AttachmentFieldProps =
  | AttachmentFieldWorkflowProps
  | AttachmentFieldControlledProps;

export function AttachmentField({
  id,
  label,
  workflow,
  state: controlledState,
  access = "editable",
  accept,
  capture,
  guidance,
  inputAccessibility,
  onSelectFile,
  onClearLocal,
  onStart,
  onRetry,
  onReload,
}: AttachmentFieldProps): React.JSX.Element {
  const { locale, t } = useI18n();
  const inputRef = useRef<HTMLInputElement | null>(null);
  if ((workflow === undefined) === (controlledState === undefined)) {
    throw new Error("AttachmentField requires exactly one state source.");
  }
  const state = normalizeAttachmentWorkflowState(
    workflow === undefined ? controlledState : workflow.state,
  );
  const selectFile =
    workflow === undefined ? onSelectFile : workflow.selectFile;
  const clearLocal =
    workflow === undefined ? onClearLocal : workflow.clearLocal;
  const start = workflow === undefined ? onStart : workflow.start;
  const retry = workflow === undefined ? onRetry : workflow.retry;
  const transportAvailable =
    workflow === undefined
      ? onStart !== undefined
      : workflow.transportAvailable;
  const localFile = localFileFromState(state);
  const mutationAllowed =
    access === "editable" &&
    inputAccessibility?.readOnly !== true &&
    inputAccessibility?.disabled !== true;
  const clearable =
    mutationAllowed &&
    clearLocal !== undefined &&
    (state.kind === "local_selected" ||
      state.kind === "local_invalid" ||
      (state.kind === "failed" &&
        state.file !== null &&
        state.writeState === "none"));
  const selectable =
    mutationAllowed &&
    selectFile !== undefined &&
    (state.kind === "empty" ||
      state.kind === "local_selected" ||
      state.kind === "local_invalid" ||
      (state.kind === "failed" && state.writeState === "none"));
  const inputDisabled = inputAccessibility?.disabled === true || !selectable;

  const choose = (file: File | undefined): void => {
    if (!file || !selectable) return;
    selectFile(file);
  };

  const clear = (): void => {
    if (!clearable) return;
    clearLocal();
    if (inputRef.current) {
      inputRef.current.value = "";
      inputRef.current.focus();
    }
  };

  if (state.kind === "denied") {
    return (
      <div
        aria-label={label}
        className="attachment-truth attachment-truth--denied"
        role="group"
      >
        <SemanticStatus label={t("Access denied")} tone="warning" />
        <p>{state.reason}</p>
      </div>
    );
  }

  return (
    <div
      aria-busy={
        state.kind === "loading" ||
        state.kind === "transporting" ||
        state.kind === "registering"
          ? true
          : undefined
      }
      aria-label={label}
      className={`attachment-truth attachment-truth--${state.kind}`}
      role="group"
    >
      {guidance ? (
        <p className="attachment-truth__guidance">{guidance}</p>
      ) : null}
      {selectable ? (
        <div
          aria-label={t("Drop a file for {{field}}", { field: label })}
          className="attachment-truth__drop"
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
          }}
          onDrop={(event) => {
            event.preventDefault();
            choose(event.dataTransfer.files[0]);
          }}
          role="group"
        >
          <label className="attachment-truth__picker" htmlFor={id}>
            <input
              accept={accept}
              aria-describedby={inputAccessibility?.["aria-describedby"]}
              aria-invalid={inputAccessibility?.["aria-invalid"]}
              aria-label={t("Choose a local file")}
              aria-required={inputAccessibility?.["aria-required"]}
              capture={capture}
              className="visually-hidden"
              disabled={inputDisabled}
              id={id}
              onChange={(event) => {
                choose(event.currentTarget.files?.[0]);
              }}
              ref={inputRef}
              required={
                inputAccessibility?.required === true && localFile === null
              }
              type="file"
            />
            <span className="attachment-truth__picker-button">
              {t("Choose a local file")}
            </span>
          </label>
          <span>{t("or drop one file here")}</span>
        </div>
      ) : null}

      {state.kind === "loading" ? (
        <div className="attachment-truth__state" role="status">
          <SemanticStatus label={t("Loading")} tone="info" />
          <span>{t("Loading attachment truth")}</span>
        </div>
      ) : state.kind === "empty" ? (
        <div className="attachment-truth__state">
          <SemanticStatus label={t("No local selection")} />
          <span>
            {access === "read_only"
              ? t("This field is read only and has no registered attachment.")
              : t("No file is selected and no transport has started.")}
          </span>
        </div>
      ) : state.kind === "local_selected" || state.kind === "local_invalid" ? (
        <>
          <div
            className="attachment-truth__state"
            role={state.kind === "local_invalid" ? "alert" : "status"}
          >
            <SemanticStatus
              label={
                state.kind === "local_invalid"
                  ? t("Local validation failed")
                  : t("Local selection")
              }
              tone={state.kind === "local_invalid" ? "danger" : "info"}
            />
            <span>
              {state.kind === "local_invalid"
                ? state.message
                : t("This file is selected locally and has not been uploaded.")}
            </span>
          </div>
          <LocalAttachmentFile file={state.file} />
          <div className="attachment-truth__actions">
            {state.kind === "local_selected" &&
            transportAvailable &&
            mutationAllowed ? (
              <CompactAction
                icon="upload"
                intent="familiar-low-risk"
                label={t("Start file transport")}
                onClick={() => {
                  start?.();
                }}
                prominence="primary"
              />
            ) : null}
            {clearable ? (
              <CompactAction
                icon="clear"
                intent="familiar-low-risk"
                label={t("Clear local selection")}
                onClick={clear}
              />
            ) : null}
          </div>
          {!transportAvailable && state.kind === "local_selected" ? (
            <p className="attachment-truth__notice">
              {t("File transport is not available in this workspace.")}
            </p>
          ) : null}
        </>
      ) : state.kind === "transporting" ? (
        <>
          <div className="attachment-truth__state" role="status">
            <SemanticStatus label={t("Transporting file")} tone="info" />
            {state.progress && state.progress.totalBytes !== null ? (
              <>
                <progress
                  aria-label={t("Actual file transport progress")}
                  max={state.progress.totalBytes}
                  value={state.progress.loadedBytes}
                />
                <span>
                  {t(
                    "{{loaded}} of {{total}} bytes were reported by the transport.",
                    {
                      loaded: formatNumber(
                        locale,
                        state.progress.loadedBytes,
                        0,
                      ),
                      total: formatNumber(locale, state.progress.totalBytes, 0),
                    },
                  )}
                </span>
              </>
            ) : state.progress ? (
              <span>
                {t(
                  "{{loaded}} bytes were reported by the transport; total size was not provided.",
                  {
                    loaded: formatNumber(locale, state.progress.loadedBytes, 0),
                  },
                )}
              </span>
            ) : (
              <span>
                {t(
                  "Transport is active. Byte progress was not provided by the transport.",
                )}
              </span>
            )}
          </div>
          <LocalAttachmentFile file={state.file} />
        </>
      ) : state.kind === "registering" ? (
        <>
          <div className="attachment-truth__state" role="status">
            <SemanticStatus label={t("Registering file")} tone="info" />
            <span>
              {t(
                "Transport completed and registration is awaiting a verified server result.",
              )}
            </span>
          </div>
          <LocalAttachmentFile file={state.file} />
        </>
      ) : state.kind === "registered" ? (
        <RegisteredAttachment attachment={state.attachment} />
      ) : (
        <div className="attachment-truth__failure" role="alert">
          <SemanticStatus
            label={
              state.kind === "conflict"
                ? t("Version conflict")
                : state.retryable
                  ? t("Retryable failure")
                  : t("Final failure")
            }
            tone={
              state.kind === "conflict" || state.retryable
                ? "warning"
                : "danger"
            }
          />
          {state.file ? <LocalAttachmentFile file={state.file} /> : null}
          <DefinitionList
            rows={[
              {
                label: t("Failed step"),
                value: attachmentFailureStageLabel(state.stage, t),
              },
              {
                label: t("Write confirmation"),
                value: attachmentWriteStateLabel(state.writeState, t),
              },
            ]}
          />
          <RequestFailurePanel announce={false} failure={state.failure} />
          <div className="attachment-truth__actions">
            {state.kind === "failed" &&
            state.retryable &&
            retry &&
            mutationAllowed ? (
              <CompactAction
                icon="refresh"
                intent="familiar-low-risk"
                label={t("Retry file transport")}
                onClick={retry}
              />
            ) : null}
            {(state.kind === "conflict" ||
              state.writeState === "unconfirmed") &&
            onReload ? (
              <CompactAction
                icon="refresh"
                intent="ambiguous"
                label={t("Reload attachment truth")}
                onClick={onReload}
              />
            ) : null}
            {clearable ? (
              <CompactAction
                icon="clear"
                intent="familiar-low-risk"
                label={t("Clear local selection")}
                onClick={clear}
              />
            ) : null}
          </div>
        </div>
      )}

      {access === "read_only" && state.kind !== "registered" ? (
        <p className="attachment-truth__notice">
          {t("This attachment field is read only.")}
        </p>
      ) : null}
    </div>
  );
}
