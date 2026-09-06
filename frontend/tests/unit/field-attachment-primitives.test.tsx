import { act, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { RequestFailure } from "../../src/api/http";
import type { SourceStatus } from "../../src/domain/view-models";
import {
  AttachmentField,
  FieldTruth,
  type FieldControlAccessibility,
  type FieldEditability,
  type FieldEffectivity,
} from "../../src/components/field-attachment-primitives";
import {
  useAttachmentWorkflow,
  type AttachmentTransport,
  type AttachmentTransportContext,
  type AttachmentTransportResult,
  type AttachmentWorkflowController,
  type AttachmentWorkflowState,
  type RegisteredAttachmentTruth,
} from "../../src/components/attachment-workflow";
import { renderWithLocale } from "../support/render";

const trialLabel = "Trial photo evidence";

const retryableFailure: RequestFailure = {
  kind: "network",
  referenceId: "request-transport-001",
  referenceKind: "request",
};

const finalFailure: RequestFailure = {
  kind: "unexpected",
  referenceId: "client-scan-001",
  referenceKind: "client",
};

const conflictFailure: RequestFailure = {
  kind: "problem",
  problem: {
    code: "ATTACHMENT_VERSION_CONFLICT",
    detail: "The registered revision changed before registration completed.",
    retryable: false,
    status: 409,
    title: "Attachment revision conflict",
    traceId: "trace-attachment-conflict-001",
    type: "urn:npi:problem:attachment-version-conflict",
  },
  referenceId: "trace-attachment-conflict-001",
  referenceKind: "trace",
};

function localFile(name = "SYN-TRIAL-PHOTO.jpg", type = "image/jpeg"): File {
  return new File(["synthetic trial evidence"], name, { type });
}

function registeredAttachment(
  scanState: RegisteredAttachmentTruth["scanState"] = "clean",
): RegisteredAttachmentTruth {
  return {
    capabilities: {
      kind: "known",
      value: {
        download: {
          reasonCode: "DOWNLOAD_PERMISSION_BLOCKED",
          state: "blocked",
        },
        preview: {
          reasonCode: "PREVIEW_SCAN_BLOCKED",
          state: "unavailable",
        },
      },
    },
    confidentiality: {
      kind: "known",
      value: {
        key: "CUSTOMER_RESTRICTED",
      },
    },
    exactRevision: "REV-7",
    fileName: "SYN-REGISTERED-EVIDENCE.pdf",
    mimeType: "application/pdf",
    permission: {
      kind: "known",
      value: {
        attach: false,
        reasonCode: "ATTACH_PERMISSION_DENIED",
      },
    },
    private: { kind: "known", value: true },
    provenance: {
      kind: "known",
      value: "gate-review:file-revision:REV-7",
    },
    scanObservedAt: {
      kind: "known",
      value: "2026-07-27T09:30:00.000Z",
    },
    scanState,
    sha256: "4".repeat(64),
    sizeBytes: 23,
  };
}

function unavailableRegisteredAttachment(): RegisteredAttachmentTruth {
  return {
    ...registeredAttachment(),
    capabilities: {
      kind: "unavailable",
      reasonCode: "CAPABILITY_FACTS_NOT_EXPOSED",
    },
    confidentiality: {
      kind: "unavailable",
      reasonCode: "CONFIDENTIALITY_NOT_EXPOSED",
    },
    permission: {
      kind: "unavailable",
      reasonCode: "PERMISSION_NOT_EXPOSED",
    },
    private: {
      kind: "unavailable",
      reasonCode: "PRIVACY_NOT_EXPOSED",
    },
    provenance: {
      kind: "unavailable",
      reasonCode: "PROVENANCE_NOT_EXPOSED",
    },
    scanObservedAt: {
      kind: "unavailable",
      reasonCode: "SCAN_OBSERVATION_NOT_EXPOSED",
    },
  };
}

function deferred<T>(): {
  promise: Promise<T>;
  reject: (reason: unknown) => void;
  resolve: (value: T) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function WorkflowAttachmentFixture({
  access = "editable",
  initialState,
  transport,
  validateFile,
}: {
  access?: "editable" | "read_only";
  initialState?: AttachmentWorkflowState;
  transport: AttachmentTransport | null;
  validateFile?: (file: File) => string | null;
}): React.JSX.Element {
  const workflow = useAttachmentWorkflow({
    transport,
    ...(initialState ? { initialState } : {}),
    ...(validateFile ? { validateFile } : {}),
  });
  return (
    <AttachmentField
      accept="image/jpeg"
      access={access}
      guidance="Select one JPEG trial photo."
      id="trial-photo-evidence"
      label={trialLabel}
      workflow={workflow}
    />
  );
}

function WorkflowSelectionProbe({
  initialState,
}: {
  initialState: AttachmentWorkflowState;
}): React.JSX.Element {
  const workflow = useAttachmentWorkflow({
    initialState,
    transport: null,
  });
  return (
    <>
      <button
        onClick={() => {
          workflow.selectFile(localFile("SYN-REPLACEMENT.jpg"));
        }}
        type="button"
      >
        Attempt replacement
      </button>
      <output aria-label="Workflow state">{workflow.state.kind}</output>
    </>
  );
}

function WorkflowControllerProbe({
  onController,
  transport,
}: {
  onController: (controller: AttachmentWorkflowController) => void;
  transport: AttachmentTransport;
}): React.JSX.Element {
  const workflow = useAttachmentWorkflow({ transport });
  onController(workflow);
  return <output aria-label="Workflow state">{workflow.state.kind}</output>;
}

function RequiredAttachmentForm(): React.JSX.Element {
  const [state, setState] = useState<AttachmentWorkflowState>({
    kind: "empty",
  });
  return (
    <form
      aria-label="Required attachment form"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <FieldTruth
        editableIn="NPI_ONE"
        editability={{ kind: "editable" }}
        effectivity={{ kind: "not_applicable" }}
        exactVersion={null}
        id="required-evidence"
        label="Required evidence"
        lockReason={null}
        renderControl={(properties) => (
          <AttachmentField
            id={properties.id}
            inputAccessibility={properties}
            label="Required evidence"
            onClearLocal={() => {
              setState({ kind: "empty" });
            }}
            onSelectFile={(file) => {
              setState({ file, kind: "local_selected" });
            }}
            state={state}
          />
        )}
        required
        sourceSystem="NPI_ONE"
        unit={null}
        validation={{ kind: "not_validated" }}
      />
    </form>
  );
}

function definitionValue(scope: HTMLElement, label: string): HTMLElement {
  const term = within(scope).getByText(label, { selector: "dt" });
  const value = term.nextElementSibling;
  if (!(value instanceof HTMLElement)) {
    throw new Error(`No definition value was rendered for ${label}.`);
  }
  return value;
}

function requiredTransportContext(
  context: AttachmentTransportContext | undefined,
): AttachmentTransportContext {
  if (!context) throw new Error("The transport context was not captured.");
  return context;
}

const fieldTruthCases = [
  {
    disabled: false,
    editableIn: "NPI_ONE",
    editableInLabel: "LaunchFlow platform",
    editability: { kind: "editable" },
    editabilityLabel: "Editable",
    effectivity: { kind: "effective" },
    effectivityLabel: "Effective",
    readOnly: false,
  },
  {
    disabled: false,
    editableIn: "ERPNEXT",
    editableInLabel: "JCE Core",
    editability: {
      condition: "The planning window is open.",
      editable: true,
      kind: "conditional",
    },
    editabilityLabel: "Conditionally editable",
    effectivity: {
      effectiveDate: "2026-07-30T00:00:00.000Z",
      kind: "superseded",
    },
    effectivityLabel: "Superseded on Jul 30, 2026",
    readOnly: false,
  },
  {
    disabled: false,
    editableIn: "NONE",
    editableInLabel: "No editable system",
    editability: {
      condition: "A released input is immutable.",
      editable: false,
      kind: "conditional",
    },
    editabilityLabel: "Conditionally read only",
    effectivity: { kind: "unavailable" },
    effectivityLabel: "Not provided by this workspace",
    readOnly: true,
  },
  {
    disabled: true,
    editableIn: "NPI_ONE",
    editableInLabel: "LaunchFlow platform",
    editability: {
      kind: "denied",
      reason: "Your role cannot edit this field.",
    },
    editabilityLabel: "Access denied",
    effectivity: { kind: "not_applicable" },
    effectivityLabel: "Not applicable",
    readOnly: false,
  },
] as const satisfies readonly {
  disabled: boolean;
  editableIn: SourceStatus["editableIn"];
  editableInLabel: string;
  editability: FieldEditability;
  editabilityLabel: string;
  effectivity: FieldEffectivity;
  effectivityLabel: string;
  readOnly: boolean;
}[];

describe("FieldTruth", () => {
  it("associates the control with read-only, validation, unit, version, and effectivity truth", () => {
    renderWithLocale(
      <FieldTruth
        editableIn="NONE"
        editability={{
          kind: "read_only",
          reason: "Released baseline fields cannot be edited.",
        }}
        effectivity={{
          effectiveDate: "2026-07-30T00:00:00.000Z",
          kind: "future",
        }}
        exactVersion="REV-C"
        help="Use the approved tooling specification."
        id="clamp-force"
        label="Clamp force"
        lockReason={null}
        required
        sourceSystem="ERPNEXT"
        unit="kN"
        validation={{
          kind: "invalid",
          message: "The value does not match the released baseline.",
        }}
        renderControl={(properties) => <input {...properties} />}
      />,
    );

    const control = screen.getByRole("textbox", { name: "Clamp force" });
    expect(control).toHaveAttribute("id", "clamp-force");
    expect(control).toBeRequired();
    expect(control).toHaveAttribute("aria-required", "true");
    expect(control).toHaveAttribute("aria-invalid", "true");
    expect(control).toHaveAttribute("readonly");
    expect(control).not.toBeDisabled();

    const describedBy = control.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const description = (describedBy ?? "")
      .split(" ")
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ");
    expect(description).toContain("Use the approved tooling specification.");
    expect(description).toContain("kN");
    expect(description).toContain("Released baseline fields cannot be edited.");
    expect(description).toContain(
      "The value does not match the released baseline.",
    );
    expect(description).toContain("REV-C");
    expect(description).toContain("Effective from Jul 30, 2026");

    expect(screen.getByText("Required")).toBeVisible();
    expect(screen.getByText("Read only")).toBeVisible();
    expect(screen.getByRole("img", { name: "JCE Core" })).toHaveAttribute(
      "data-brand-context",
      "erp-source",
    );
    expect(screen.getByText("No editable system")).toBeVisible();
  });

  it.each(fieldTruthCases)(
    "renders optional $editabilityLabel and $effectivityLabel truth without inventing unit or version",
    ({
      disabled,
      editableIn,
      editableInLabel,
      editability,
      editabilityLabel,
      effectivity,
      effectivityLabel,
      readOnly,
    }) => {
      renderWithLocale(
        <FieldTruth
          editableIn={editableIn}
          editability={editability}
          effectivity={effectivity}
          exactVersion={null}
          id="review-note"
          label="Review note"
          lockReason={null}
          required={false}
          sourceSystem="NPI_ONE"
          unit={null}
          validation={{ kind: "not_validated" }}
          renderControl={(properties) => <input {...properties} />}
        />,
      );

      const control = screen.getByRole("textbox", { name: "Review note" });
      expect(control).not.toBeRequired();
      expect(control).not.toHaveAttribute("aria-required");
      expect(control).not.toHaveAttribute("aria-invalid");
      if (readOnly) {
        expect(control).toHaveAttribute("readonly");
      } else {
        expect(control).not.toHaveAttribute("readonly");
      }
      if (disabled) {
        expect(control).toBeDisabled();
      } else {
        expect(control).not.toBeDisabled();
      }

      const field = screen.getByRole("region", { name: "Review note" });
      expect(within(field).getByText("Optional")).toBeVisible();
      expect(within(field).getByText(editabilityLabel)).toBeVisible();
      const editableInValue = definitionValue(field, "Editable in");
      if (editableIn === "ERPNEXT") {
        expect(
          within(editableInValue).getByRole("img", { name: editableInLabel }),
        ).toHaveAttribute("data-brand-context", "erp-source");
      } else {
        expect(editableInValue).toHaveTextContent(editableInLabel);
      }
      expect(definitionValue(field, "Unit")).toHaveTextContent(
        "Not applicable",
      );
      expect(definitionValue(field, "Exact version")).toHaveTextContent(
        "Not provided by this workspace",
      );
      expect(definitionValue(field, "Effectivity")).toHaveTextContent(
        effectivityLabel,
      );
      expect(within(field).getByText("Not validated")).toBeVisible();
    },
  );
});

describe("AttachmentField local selection", () => {
  it("supports picker validation, labelled drop, clear, focus recovery, and reselection", async () => {
    const user = userEvent.setup();
    renderWithLocale(
      <WorkflowAttachmentFixture
        transport={null}
        validateFile={(file) =>
          file.name.includes("INVALID")
            ? "Only validated trial photos are accepted."
            : null
        }
      />,
    );

    const picker = screen.getByLabelText("Choose a local file");
    const invalid = localFile("SYN-INVALID-PHOTO.jpg");
    await user.upload(picker, invalid);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Only validated trial photos are accepted.",
    );
    expect(screen.getByText("Local validation failed")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Clear local selection" }),
    );
    expect(picker).toHaveFocus();
    expect(screen.getByText("No local selection")).toBeVisible();

    const dropped = localFile("SYN-DROPPED-PHOTO.jpg");
    fireEvent.drop(
      screen.getByRole("group", {
        name: "Drop a file for Trial photo evidence",
      }),
      { dataTransfer: { files: [dropped] } },
    );

    expect(screen.getByText("Local selection")).toBeVisible();
    expect(screen.getAllByText(dropped.name)).not.toHaveLength(0);
    expect(screen.getByText("image/jpeg")).toBeVisible();
    expect(
      screen.getByText(
        "This file is selected locally and has not been uploaded.",
      ),
    ).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Clear local selection" }),
    );
    expect(picker).toHaveFocus();

    await user.upload(picker, dropped);
    expect(screen.getAllByText(dropped.name)).not.toHaveLength(0);
    expect(
      screen.getByText("File transport is not available in this workspace."),
    ).toBeVisible();
  });

  it("uses FieldTruth accessibility as a complete mutation boundary", () => {
    const onClearLocal = vi.fn();
    const onRetry = vi.fn();
    const onSelectFile = vi.fn();
    const onStart = vi.fn();
    const readOnlyAccessibility: FieldControlAccessibility = {
      "aria-describedby": "read-only-description",
      "aria-invalid": undefined,
      "aria-required": undefined,
      disabled: false,
      id: "read-only-composed-attachment",
      readOnly: true,
      required: false,
    };
    const readOnly = renderWithLocale(
      <AttachmentField
        id="read-only-composed-attachment"
        inputAccessibility={readOnlyAccessibility}
        label="Composed read-only attachment"
        onClearLocal={onClearLocal}
        onSelectFile={onSelectFile}
        onStart={onStart}
        state={{ file: localFile(), kind: "local_selected" }}
      />,
    );

    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("group", {
        name: "Drop a file for Composed read-only attachment",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();
    expect(onClearLocal).not.toHaveBeenCalled();
    expect(onSelectFile).not.toHaveBeenCalled();
    expect(onStart).not.toHaveBeenCalled();

    readOnly.unmount();
    const retryReadOnly = renderWithLocale(
      <AttachmentField
        id="read-only-retry-attachment"
        inputAccessibility={readOnlyAccessibility}
        label="Composed read-only retry"
        onRetry={onRetry}
        state={{
          failure: retryableFailure,
          file: localFile(),
          kind: "failed",
          retryable: true,
          stage: "transport",
          writeState: "none",
        }}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(onRetry).not.toHaveBeenCalled();

    retryReadOnly.unmount();
    const disabledAccessibility: FieldControlAccessibility = {
      ...readOnlyAccessibility,
      disabled: true,
      id: "disabled-composed-attachment",
      readOnly: false,
    };
    renderWithLocale(
      <AttachmentField
        id="disabled-composed-attachment"
        inputAccessibility={disabledAccessibility}
        label="Composed denied attachment"
        onSelectFile={onSelectFile}
        state={{ kind: "empty" }}
      />,
    );

    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("group", {
        name: "Drop a file for Composed denied attachment",
      }),
    ).not.toBeInTheDocument();
    expect(onSelectFile).not.toHaveBeenCalled();
  });

  it("hides controlled mutation affordances when their handlers are absent", () => {
    const empty = renderWithLocale(
      <AttachmentField
        id="controlled-empty-attachment"
        label="Controlled empty attachment"
        state={{ kind: "empty" }}
      />,
    );
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("group", {
        name: "Drop a file for Controlled empty attachment",
      }),
    ).not.toBeInTheDocument();

    empty.unmount();
    renderWithLocale(
      <AttachmentField
        id="controlled-local-attachment"
        label="Controlled local attachment"
        state={{ file: localFile(), kind: "local_selected" }}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start file transport" }),
    ).not.toBeInTheDocument();
  });

  it("announces loading as busy without exposing any mutation path", () => {
    const onClearLocal = vi.fn();
    const onRetry = vi.fn();
    const onSelectFile = vi.fn();
    const onStart = vi.fn();
    renderWithLocale(
      <AttachmentField
        id="loading-attachment"
        label="Loading attachment"
        onClearLocal={onClearLocal}
        onRetry={onRetry}
        onSelectFile={onSelectFile}
        onStart={onStart}
        state={{ kind: "loading" }}
      />,
    );

    const field = screen.getByRole("group", { name: "Loading attachment" });
    expect(field).toHaveAttribute("aria-busy", "true");
    expect(within(field).getByRole("status")).toHaveTextContent(
      "Loading attachment truth",
    );
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(onClearLocal).not.toHaveBeenCalled();
    expect(onRetry).not.toHaveBeenCalled();
    expect(onSelectFile).not.toHaveBeenCalled();
    expect(onStart).not.toHaveBeenCalled();
  });

  it("keeps native requiredness aligned with drag-and-drop selection and clear", async () => {
    const user = userEvent.setup();
    renderWithLocale(<RequiredAttachmentForm />);
    const form = screen.getByRole("form", {
      name: "Required attachment form",
    });
    const picker = screen.getByLabelText("Choose a local file");

    expect(picker).toBeRequired();
    expect(form).not.toBeValid();

    fireEvent.drop(
      screen.getByRole("group", {
        name: "Drop a file for Required evidence",
      }),
      { dataTransfer: { files: [localFile("SYN-REQUIRED-DROP.jpg")] } },
    );

    expect(screen.getByText("Local selection")).toBeVisible();
    expect(picker).not.toHaveAttribute("required");
    expect(picker).toHaveAttribute("aria-required", "true");
    expect(form).toBeValid();

    await user.click(
      screen.getByRole("button", { name: "Clear local selection" }),
    );
    expect(picker).toHaveAttribute("required");
    expect(form).not.toBeValid();
  });
});

describe("useAttachmentWorkflow transport truth", () => {
  it("retains conflict and registered-write truth when replacement is attempted", async () => {
    const user = userEvent.setup();
    const conflict = renderWithLocale(
      <WorkflowSelectionProbe
        initialState={{
          failure: conflictFailure,
          file: localFile(),
          kind: "conflict",
          stage: "registration",
          writeState: "unconfirmed",
        }}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Attempt replacement" }),
    );
    expect(
      screen.getByRole("status", { name: "Workflow state" }),
    ).toHaveTextContent("conflict");

    conflict.unmount();
    renderWithLocale(
      <WorkflowSelectionProbe
        initialState={{
          failure: finalFailure,
          file: localFile(),
          kind: "failed",
          retryable: false,
          stage: "scan",
          writeState: "registered",
        }}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Attempt replacement" }),
    );
    expect(
      screen.getByRole("status", { name: "Workflow state" }),
    ).toHaveTextContent("failed");
  });

  it("does not invoke a queued transport after immediate unmount", async () => {
    const user = userEvent.setup();
    const transport = vi.fn<AttachmentTransport>().mockResolvedValue({
      attachment: registeredAttachment(),
      kind: "registered",
    });
    const rendered = renderWithLocale(
      <WorkflowAttachmentFixture transport={transport} />,
    );

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );
    rendered.unmount();
    await act(async () => {
      await Promise.resolve();
    });

    expect(transport).not.toHaveBeenCalled();
  });

  it("guards retained controller actions with the latest workflow state", async () => {
    const operation = deferred<AttachmentTransportResult>();
    const transport = vi
      .fn<AttachmentTransport>()
      .mockReturnValue(operation.promise);
    let captured: AttachmentWorkflowController | undefined;
    renderWithLocale(
      <WorkflowControllerProbe
        onController={(controller) => {
          captured = controller;
        }}
        transport={transport}
      />,
    );
    if (!captured) throw new Error("The workflow controller was not captured.");
    const retainedController = captured;
    const file = localFile();

    act(() => {
      retainedController.selectFile(file);
      retainedController.start();
      retainedController.start();
      retainedController.clearLocal();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(transport).toHaveBeenCalledTimes(1);
    expect(transport.mock.calls[0]?.[0]).toBe(file);
    expect(
      screen.getByRole("status", { name: "Workflow state" }),
    ).toHaveTextContent("transporting");

    await act(async () => {
      operation.resolve({
        attachment: registeredAttachment(),
        kind: "registered",
      });
      await Promise.resolve();
    });
    expect(
      screen.getByRole("status", { name: "Workflow state" }),
    ).toHaveTextContent("registered");

    act(() => {
      retainedController.selectFile(localFile("SYN-LATE-REPLACEMENT.jpg"));
      retainedController.start();
      retainedController.clearLocal();
    });
    expect(transport).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("status", { name: "Workflow state" }),
    ).toHaveTextContent("registered");
  });

  it("renders reported bytes, registration, and the exact registered result", async () => {
    const user = userEvent.setup();
    const operation = deferred<AttachmentTransportResult>();
    let transportContext: AttachmentTransportContext | undefined;
    const transport = vi.fn<AttachmentTransport>((_file, context) => {
      transportContext = context;
      return operation.promise;
    });
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    const file = localFile();
    await user.upload(screen.getByLabelText("Choose a local file"), file);
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    expect(transport).toHaveBeenCalledTimes(1);
    expect(transport.mock.calls[0]?.[0]).toBe(file);
    expect(screen.getByRole("group", { name: trialLabel })).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(
      screen.getByText(
        "Transport is active. Byte progress was not provided by the transport.",
      ),
    ).toBeVisible();
    const field = screen.getByRole("group", { name: trialLabel });
    expect(definitionValue(field, "File name")).toHaveTextContent(file.name);

    const context = requiredTransportContext(transportContext);
    act(() => {
      context.reportProgress(42, 100);
    });
    const progress = screen.getByRole("progressbar", {
      name: "Actual file transport progress",
    });
    expect(progress).toHaveAttribute("value", "42");
    expect(progress).toHaveAttribute("max", "100");
    expect(
      screen.getByText("42 of 100 bytes were reported by the transport."),
    ).toBeVisible();

    act(() => {
      context.reportProgress(21, 100);
    });
    expect(progress).toHaveAttribute("value", "42");

    act(() => {
      context.reportRegistrationStarted();
    });
    expect(screen.getByText("Registering file")).toBeVisible();
    expect(
      screen.getByText(
        "Transport completed and registration is awaiting a verified server result.",
      ),
    ).toBeVisible();
    expect(definitionValue(field, "File name")).toHaveTextContent(file.name);

    await act(async () => {
      operation.resolve({
        attachment: registeredAttachment(),
        kind: "registered",
      });
      await Promise.resolve();
    });

    const truth = await screen.findByRole("region", {
      name: "Registered attachment truth",
    });
    expect(truth).toHaveTextContent("REV-7");
    expect(truth).toHaveTextContent("4".repeat(64));
    expect(within(truth).getByRole("status")).toHaveTextContent(
      "The scanner reported no threat for this exact registered revision.",
    );
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();

    act(() => {
      context.reportRegistrationStarted();
    });
    expect(truth).toBeVisible();
    expect(screen.queryByText("Registering file")).not.toBeInTheDocument();
  });

  it("keeps progress indeterminate when total bytes are absent and aborts stale work on unmount", async () => {
    const user = userEvent.setup();
    const operation = deferred<AttachmentTransportResult>();
    let transportContext: AttachmentTransportContext | undefined;
    const transport = vi.fn<AttachmentTransport>((_file, context) => {
      transportContext = context;
      return operation.promise;
    });
    const rendered = renderWithLocale(
      <WorkflowAttachmentFixture transport={transport} />,
    );

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );
    const context = requiredTransportContext(transportContext);

    act(() => {
      context.reportProgress(48, null);
    });
    expect(
      screen.queryByRole("progressbar", {
        name: "Actual file transport progress",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "48 bytes were reported by the transport; total size was not provided.",
      ),
    ).toBeVisible();

    rendered.unmount();
    expect(context.signal.aborted).toBe(true);
    await act(async () => {
      operation.resolve({
        attachment: registeredAttachment(),
        kind: "registered",
      });
      await Promise.resolve();
    });
  });

  it("keeps registration and unconfirmed-write truth monotonic after a contradictory result", async () => {
    const user = userEvent.setup();
    const operation = deferred<AttachmentTransportResult>();
    let transportContext: AttachmentTransportContext | undefined;
    const transport = vi.fn<AttachmentTransport>((_file, context) => {
      transportContext = context;
      return operation.promise;
    });
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );
    const context = requiredTransportContext(transportContext);
    act(() => {
      context.reportRegistrationStarted();
    });

    await act(async () => {
      operation.resolve({
        failure: retryableFailure,
        kind: "failed",
        retryable: true,
        stage: "transport",
        writeState: "none",
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File registration")).toBeVisible();
    expect(screen.getByText("Server write is unconfirmed")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
  });

  it("normalizes a contradictory direct unconfirmed result to a final failure", async () => {
    const user = userEvent.setup();
    const contradictoryResult = {
      failure: retryableFailure,
      kind: "failed",
      retryable: true,
      stage: "registration",
      writeState: "unconfirmed",
    } as unknown as AttachmentTransportResult;
    const transport = vi
      .fn<AttachmentTransport>()
      .mockResolvedValue(contradictoryResult);
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File registration")).toBeVisible();
    expect(screen.getByText("Server write is unconfirmed")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
  });

  it("fails closed when a transport resolves null instead of leaving the field busy", async () => {
    const user = userEvent.setup();
    const transport = vi.fn<AttachmentTransport>(() =>
      Promise.resolve(null as unknown as AttachmentTransportResult),
    );
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    const file = localFile("SYN-NULL-RESULT.jpg");
    await user.upload(screen.getByLabelText("Choose a local file"), file);
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    const field = screen.getByRole("group", { name: trialLabel });
    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File transport")).toBeVisible();
    expect(screen.getByText("No server write occurred")).toBeVisible();
    expect(definitionValue(field, "File name")).toHaveTextContent(file.name);
    expect(field).not.toHaveAttribute("aria-busy");
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
  });

  it("fails closed with unconfirmed write truth for a malformed registered envelope", async () => {
    const user = userEvent.setup();
    const transport = vi.fn<AttachmentTransport>(() =>
      Promise.resolve({
        kind: "registered",
      } as unknown as AttachmentTransportResult),
    );
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    const file = localFile("SYN-MALFORMED-REGISTERED.jpg");
    await user.upload(screen.getByLabelText("Choose a local file"), file);
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    const field = screen.getByRole("group", { name: trialLabel });
    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File registration")).toBeVisible();
    expect(screen.getByText("Server write is unconfirmed")).toBeVisible();
    expect(definitionValue(field, "File name")).toHaveTextContent(file.name);
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
  });

  it("preserves registered-write truth from an out-of-contract failed result", async () => {
    const user = userEvent.setup();
    const transport = vi.fn<AttachmentTransport>(() =>
      Promise.resolve({
        failure: retryableFailure,
        kind: "failed",
        retryable: true,
        stage: "transport",
        writeState: "registered",
      } as unknown as AttachmentTransportResult),
    );
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    const file = localFile("SYN-REGISTERED-WRITE.jpg");
    await user.upload(screen.getByLabelText("Choose a local file"), file);
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    const field = screen.getByRole("group", { name: trialLabel });
    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File registration")).toBeVisible();
    expect(screen.getByText("Registered revision retained")).toBeVisible();
    expect(definitionValue(field, "File name")).toHaveTextContent(file.name);
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
  });

  it("retries only a retryable failure and keeps its structured request reference", async () => {
    const user = userEvent.setup();
    const transport = vi
      .fn<AttachmentTransport>()
      .mockResolvedValueOnce({
        failure: retryableFailure,
        kind: "failed",
        retryable: true,
        stage: "transport",
        writeState: "none",
      })
      .mockResolvedValueOnce({
        attachment: registeredAttachment(),
        kind: "registered",
      });
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    expect(await screen.findByText("Retryable failure")).toBeVisible();
    expect(screen.getByText("File transport")).toBeVisible();
    expect(screen.getByText("No server write occurred")).toBeVisible();
    expect(
      definitionValue(
        screen.getByRole("group", { name: trialLabel }),
        "File name",
      ),
    ).toHaveTextContent("SYN-TRIAL-PHOTO.jpg");
    expect(screen.getByText("Request ID", { exact: false })).toBeVisible();
    expect(screen.getByText("request-transport-001")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Retry file transport" }),
    );
    expect(transport).toHaveBeenCalledTimes(2);
    expect(
      await screen.findByRole("region", {
        name: "Registered attachment truth",
      }),
    ).toBeVisible();
  });

  it("turns a synchronous transport exception into a final truthful failure", async () => {
    const user = userEvent.setup();
    const transport = vi.fn<AttachmentTransport>(() => {
      throw new Error("Synthetic synchronous transport failure");
    });
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File transport")).toBeVisible();
    expect(screen.getByText("No server write occurred")).toBeVisible();
    expect(screen.getByRole("group", { name: trialLabel })).not.toHaveAttribute(
      "aria-busy",
    );
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
  });

  it("retains unconfirmed registration truth when registration reports before a synchronous exception", async () => {
    const user = userEvent.setup();
    const transport = vi.fn<AttachmentTransport>((_file, context) => {
      context.reportRegistrationStarted();
      throw new Error("Synthetic registration exception");
    });
    renderWithLocale(<WorkflowAttachmentFixture transport={transport} />);

    await user.upload(
      screen.getByLabelText("Choose a local file"),
      localFile(),
    );
    await user.click(
      screen.getByRole("button", { name: "Start file transport" }),
    );

    expect(await screen.findByText("Final failure")).toBeVisible();
    expect(screen.getByText("File registration")).toBeVisible();
    expect(screen.getByText("Server write is unconfirmed")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
  });
});

describe("AttachmentField failure truth", () => {
  it("renders a final failure without retry or clear actions", () => {
    renderWithLocale(
      <AttachmentField
        id="final-attachment"
        label="Final attachment"
        state={{
          failure: finalFailure,
          file: localFile(),
          kind: "failed",
          retryable: false,
          stage: "scan",
          writeState: "registered",
        }}
      />,
    );

    expect(screen.getByText("Final failure")).toBeVisible();
    expect(screen.getByText("File scanning")).toBeVisible();
    expect(screen.getByText("Registered revision retained")).toBeVisible();
    expect(
      screen.getByText("Client reference ID", { exact: false }),
    ).toBeVisible();
    expect(screen.getByText("client-scan-001")).toBeVisible();
    expect(
      definitionValue(
        screen.getByRole("group", { name: "Final attachment" }),
        "File name",
      ),
    ).toHaveTextContent("SYN-TRIAL-PHOTO.jpg");
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();
  });

  it("normalizes an impossible scan failure to registered and removes every local mutation path", () => {
    const onClearLocal = vi.fn();
    const onRetry = vi.fn();
    const onSelectFile = vi.fn();
    const impossibleState = {
      failure: retryableFailure,
      file: localFile("SYN-SCAN-IMPOSSIBLE.jpg"),
      kind: "failed",
      retryable: true,
      stage: "scan",
      writeState: "none",
    } as unknown as AttachmentWorkflowState;
    renderWithLocale(
      <AttachmentField
        id="impossible-scan-attachment"
        label="Impossible scan attachment"
        onClearLocal={onClearLocal}
        onRetry={onRetry}
        onSelectFile={onSelectFile}
        state={impossibleState}
      />,
    );

    const field = screen.getByRole("group", {
      name: "Impossible scan attachment",
    });
    expect(screen.getByText("Final failure")).toBeVisible();
    expect(screen.getByText("File scanning")).toBeVisible();
    expect(screen.getByText("Registered revision retained")).toBeVisible();
    expect(definitionValue(field, "File name")).toHaveTextContent(
      "SYN-SCAN-IMPOSSIBLE.jpg",
    );
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(onClearLocal).not.toHaveBeenCalled();
    expect(onRetry).not.toHaveBeenCalled();
    expect(onSelectFile).not.toHaveBeenCalled();
  });

  it("defensively renders contradictory unconfirmed state as final and reload-only", async () => {
    const user = userEvent.setup();
    const onReload = vi.fn();
    const onRetry = vi.fn();
    const contradictoryState = {
      failure: retryableFailure,
      file: localFile(),
      kind: "failed",
      retryable: true,
      stage: "registration",
      writeState: "unconfirmed",
    } as unknown as AttachmentWorkflowState;
    renderWithLocale(
      <AttachmentField
        id="unconfirmed-attachment"
        label="Unconfirmed attachment"
        onReload={onReload}
        onRetry={onRetry}
        state={contradictoryState}
      />,
    );

    expect(screen.getByText("Final failure")).toBeVisible();
    expect(screen.getByText("Server write is unconfirmed")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry file transport" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Reload attachment truth" }),
    );
    expect(onReload).toHaveBeenCalledTimes(1);
    expect(onRetry).not.toHaveBeenCalled();
  });

  it("renders an unconfirmed registration conflict and its explicit reload action", async () => {
    const user = userEvent.setup();
    const onReload = vi.fn();
    renderWithLocale(
      <AttachmentField
        id="conflicted-attachment"
        label="Conflicted attachment"
        onReload={onReload}
        state={{
          failure: conflictFailure,
          file: localFile(),
          kind: "conflict",
          stage: "registration",
          writeState: "unconfirmed",
        }}
      />,
    );

    expect(screen.getByText("Version conflict")).toBeVisible();
    expect(screen.getByText("File registration")).toBeVisible();
    expect(screen.getByText("Server write is unconfirmed")).toBeVisible();
    expect(screen.getByText("Attachment revision conflict")).toBeVisible();
    expect(
      screen.getByText(
        "The registered revision changed before registration completed.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Trace ID", { exact: false })).toBeVisible();
    expect(screen.getByText("trace-attachment-conflict-001")).toBeVisible();
    expect(
      definitionValue(
        screen.getByRole("group", { name: "Conflicted attachment" }),
        "File name",
      ),
    ).toHaveTextContent("SYN-TRIAL-PHOTO.jpg");
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Reload attachment truth" }),
    );
    expect(onReload).toHaveBeenCalledTimes(1);
  });
});

describe("registered attachment truth", () => {
  const scanCases = [
    {
      label: "Scan pending",
      notice:
        "The registered revision is awaiting a scanner result. No safe-file capability is implied.",
      scanState: "pending",
    },
    {
      label: "No threat found",
      notice:
        "The scanner reported no threat for this exact registered revision.",
      scanState: "clean",
    },
    {
      label: "Threat detected",
      notice:
        "The scanner detected a threat. The registered revision remains visible for recovery, but no file action is available.",
      scanState: "infected",
    },
    {
      label: "Scan failed",
      notice:
        "File scanning failed. Recovery requires an authorized server action; no retry or replacement is assumed.",
      scanState: "failed",
    },
  ] as const;

  it.each(scanCases)(
    "renders immutable $scanState scan, privacy, policy, provenance, permission, and capability truth",
    ({ label, notice, scanState }) => {
      const { container } = renderWithLocale(
        <AttachmentField
          id={`registered-${scanState}`}
          label="Registered evidence"
          state={{
            attachment: registeredAttachment(scanState),
            kind: "registered",
          }}
        />,
      );

      const truth = screen.getByRole("region", {
        name: "Registered attachment truth",
      });
      expect(within(truth).getAllByText(label)).not.toHaveLength(0);
      expect(within(truth).getByText(notice)).toBeVisible();
      expect(definitionValue(truth, "File name")).toHaveTextContent(
        "SYN-REGISTERED-EVIDENCE.pdf",
      );
      expect(definitionValue(truth, "Exact revision")).toHaveTextContent(
        "REV-7",
      );
      expect(definitionValue(truth, "File hash")).toHaveTextContent(
        "4".repeat(64),
      );
      expect(definitionValue(truth, "Privacy")).toHaveTextContent("Private");
      expect(definitionValue(truth, "Confidentiality")).toHaveTextContent(
        "CUSTOMER_RESTRICTED",
      );
      expect(definitionValue(truth, "Provenance")).toHaveTextContent(
        "gate-review:file-revision:REV-7",
      );
      expect(definitionValue(truth, "Attachment permission")).toHaveTextContent(
        "Attachment not permitted",
      );
      expect(definitionValue(truth, "Attachment permission")).toHaveTextContent(
        "ATTACH_PERMISSION_DENIED",
      );
      expect(definitionValue(truth, "Preview capability")).toHaveTextContent(
        "Unavailable",
      );
      expect(definitionValue(truth, "Preview capability")).toHaveTextContent(
        "PREVIEW_SCAN_BLOCKED",
      );
      expect(definitionValue(truth, "Download capability")).toHaveTextContent(
        "Blocked",
      );
      expect(definitionValue(truth, "Download capability")).toHaveTextContent(
        "DOWNLOAD_PERMISSION_BLOCKED",
      );

      expect(container.querySelectorAll("[href], [src]")).toHaveLength(0);
      expect(container.innerHTML).not.toContain("/private/files/");
      expect(container.innerHTML).not.toContain("https://");
      expect(
        screen.queryByRole("button", { name: "Clear local selection" }),
      ).not.toBeInTheDocument();
    },
  );

  it("renders unavailable registered facts explicitly without inferring capabilities", () => {
    renderWithLocale(
      <AttachmentField
        id="registered-unavailable"
        label="Registered evidence"
        state={{
          attachment: unavailableRegisteredAttachment(),
          kind: "registered",
        }}
      />,
    );

    const truth = screen.getByRole("region", {
      name: "Registered attachment truth",
    });
    expect(definitionValue(truth, "Privacy")).toHaveTextContent(
      "Not provided by this workspace",
    );
    expect(definitionValue(truth, "Privacy")).toHaveTextContent(
      "PRIVACY_NOT_EXPOSED",
    );
    expect(definitionValue(truth, "Confidentiality")).toHaveTextContent(
      "CONFIDENTIALITY_NOT_EXPOSED",
    );
    expect(definitionValue(truth, "Provenance")).toHaveTextContent(
      "PROVENANCE_NOT_EXPOSED",
    );
    expect(definitionValue(truth, "Scan observed")).toHaveTextContent(
      "SCAN_OBSERVATION_NOT_EXPOSED",
    );
    expect(definitionValue(truth, "Attachment permission")).toHaveTextContent(
      "PERMISSION_NOT_EXPOSED",
    );
    expect(definitionValue(truth, "Preview capability")).toHaveTextContent(
      "CAPABILITY_FACTS_NOT_EXPOSED",
    );
    expect(definitionValue(truth, "Download capability")).toHaveTextContent(
      "CAPABILITY_FACTS_NOT_EXPOSED",
    );
  });

  it("renders a known confidentiality value as an exact key without ungoverned language copy", () => {
    renderWithLocale(
      <AttachmentField
        id="registered-confidentiality-zh"
        label="已注册证据"
        state={{
          attachment: registeredAttachment(),
          kind: "registered",
        }}
      />,
      "zh",
    );

    const truth = screen.getByRole("region", { name: "已注册附件事实" });
    expect(within(truth).getByText("保密级别")).toBeVisible();
    expect(within(truth).getByText("CUSTOMER_RESTRICTED")).toBeVisible();
    expect(
      within(truth).queryByText("Customer restricted"),
    ).not.toBeInTheDocument();
  });

  it.each(["pending", "infected", "failed"] as const)(
    "fails closed when a %s scan conflicts with an available capability",
    (scanState) => {
      const attachment = registeredAttachment(scanState);
      renderWithLocale(
        <AttachmentField
          id={`registered-conflict-${scanState}`}
          label="Registered evidence"
          state={{
            attachment: {
              ...attachment,
              capabilities: {
                kind: "known",
                value: {
                  download: { reasonCode: null, state: "available" },
                  preview: { reasonCode: null, state: "available" },
                },
              },
            },
            kind: "registered",
          }}
        />,
      );

      const truth = screen.getByRole("region", {
        name: "Registered attachment truth",
      });
      expect(definitionValue(truth, "Preview capability")).toHaveTextContent(
        "Source reported available; blocked by scan state",
      );
      expect(definitionValue(truth, "Download capability")).toHaveTextContent(
        "Source reported available; blocked by scan state",
      );
      expect(truth.querySelectorAll("[href], [src]")).toHaveLength(0);
    },
  );
});

describe("AttachmentField access boundaries", () => {
  it("removes mutation paths for read-only and denied attachment fields", () => {
    const readOnly = renderWithLocale(
      <AttachmentField
        access="read_only"
        id="read-only-attachment"
        label="Read-only attachment"
        state={{ kind: "empty" }}
      />,
    );

    expect(
      screen.getByRole("group", { name: "Read-only attachment" }),
    ).toHaveTextContent(
      "This field is read only and has no registered attachment.",
    );
    expect(
      screen.getByText("This attachment field is read only."),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();

    readOnly.unmount();
    renderWithLocale(
      <AttachmentField
        id="denied-attachment"
        label="Denied attachment"
        state={{
          kind: "denied",
          reason: "Your project role cannot view this attachment truth.",
        }}
      />,
    );

    expect(
      screen.getByRole("group", { name: "Denied attachment" }),
    ).toHaveTextContent("Access denied");
    expect(
      screen.getByText("Your project role cannot view this attachment truth."),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear local selection" }),
    ).not.toBeInTheDocument();
  });
});
