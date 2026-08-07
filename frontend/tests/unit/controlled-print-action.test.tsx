import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ControlledPrintCapabilityViewModel,
  ControlledPrintDataSource,
} from "../../src/api/controlled-print-data-source";
import { NpiApiError, type ProblemDetails } from "../../src/api/http";
import { ControlledPrintAction } from "../../src/components/controlled-print-action";
import {
  controlledPrintCapabilityFixture,
  controlledPrintProjectId,
  controlledPrintSnapshotFixture,
  controlledPrintSourceFixture,
} from "../support/controlled-print-fixture";
import { renderWithLocale } from "../support/render";

function problem(status: number, code: string, retryable = false): NpiApiError {
  const value: ProblemDetails = {
    code,
    retryable,
    status,
    title: `Controlled ${code} response`,
    traceId: `trace-${code.toLowerCase()}`,
    type: `urn:npi:problem:${code.toLowerCase()}`,
  };
  return new NpiApiError(value);
}

function dataSource(
  overrides: Partial<ControlledPrintDataSource> = {},
): ControlledPrintDataSource {
  const snapshot = controlledPrintSnapshotFixture();
  return {
    createSnapshot: vi.fn(() => Promise.resolve({ replayed: false, snapshot })),
    download: vi.fn(() =>
      Promise.resolve({
        blob: new Blob(["%PDF"], { type: "application/pdf" }),
        fileName: snapshot.output.fileName,
        outputHash: snapshot.output.sha256,
        snapshotHash: snapshot.snapshotHash,
      }),
    ),
    loadCapability: vi.fn(() =>
      Promise.resolve(controlledPrintCapabilityFixture()),
    ),
    loadSnapshot: vi.fn(() => Promise.resolve(snapshot)),
    ...overrides,
  };
}

const commandContext = {
  csrfToken: "csrf-controlled-print-component-value",
  userId: "printer@example.invalid",
};

const createObjectUrl = vi.fn(() => "blob:controlled");
const revokeObjectUrl = vi.fn((_url: string) => undefined);

function renderAction(source = dataSource()) {
  return {
    source,
    ...renderWithLocale(
      <ControlledPrintAction
        commandContext={commandContext}
        dataSource={source}
        projectId={controlledPrintProjectId}
        source={controlledPrintSourceFixture()}
      />,
    ),
  };
}

beforeEach(() => {
  createObjectUrl.mockClear();
  revokeObjectUrl.mockClear();
  vi.spyOn(globalThis.URL, "createObjectURL").mockImplementation(
    createObjectUrl,
  );
  vi.spyOn(globalThis.URL, "revokeObjectURL").mockImplementation(
    revokeObjectUrl,
  );
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
    () => undefined,
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("controlled-print action truth", () => {
  it("starts without an implicit request and fails closed when no mapping is available", async () => {
    const loadCapability = vi.fn(() =>
      Promise.resolve(controlledPrintCapabilityFixture(false)),
    );
    const createSnapshot = vi.fn<ControlledPrintDataSource["createSnapshot"]>();
    const source = dataSource({
      createSnapshot,
      loadCapability,
    });
    const user = userEvent.setup();
    renderAction(source);

    expect(loadCapability).not.toHaveBeenCalled();
    expect(screen.getByText("Controlled print not checked")).toBeVisible();
    await user.click(
      screen.getByRole("button", {
        name: "Check controlled print availability",
      }),
    );
    expect(
      await screen.findByText("Controlled print is unavailable"),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No approved controlled print is available for this exact source, version, and language.",
      ),
    ).toBeVisible();
    expect(createSnapshot).not.toHaveBeenCalled();
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
  });

  it("reviews one immutable create, exposes replay truth and downloads retained bytes", async () => {
    const createSnapshot = vi.fn<ControlledPrintDataSource["createSnapshot"]>(
      () =>
        Promise.resolve({
          replayed: true,
          snapshot: controlledPrintSnapshotFixture(),
        }),
    );
    const download = vi.fn<ControlledPrintDataSource["download"]>(() => {
      const snapshot = controlledPrintSnapshotFixture();
      return Promise.resolve({
        blob: new Blob(["%PDF"], { type: "application/pdf" }),
        fileName: snapshot.output.fileName,
        outputHash: snapshot.output.sha256,
        snapshotHash: snapshot.snapshotHash,
      });
    });
    const source = dataSource({
      createSnapshot,
      download,
    });
    const user = userEvent.setup();
    renderAction(source);

    await user.click(
      screen.getByRole("button", {
        name: "Check controlled print availability",
      }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Create controlled PDF" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Create immutable controlled PDF" }),
    ).toBeVisible();
    expect(
      screen.getByText("Exact controlled-print policy printer authority."),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Create retained PDF" }),
    );

    expect(
      await screen.findByText("Controlled PDF replayed from retained output"),
    ).toBeVisible();
    expect(screen.getByText("controlled-project-001.pdf")).toBeVisible();
    expect(createSnapshot).toHaveBeenCalledOnce();
    const createContext = createSnapshot.mock.calls[0]?.[3];
    expect(createContext).toMatchObject({
      csrfToken: commandContext.csrfToken,
    });
    expect(createContext?.idempotencyKey).toMatch(/^controlled-print-/u);

    await user.click(
      screen.getByRole("button", { name: "Download retained PDF" }),
    );
    expect(await screen.findByText("Retained PDF downloaded")).toBeVisible();
    expect(download).toHaveBeenCalledOnce();
    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:controlled");
  });

  it("retains the actor-bound idempotency key across a retryable create failure", async () => {
    const createSnapshot = vi
      .fn<ControlledPrintDataSource["createSnapshot"]>()
      .mockRejectedValueOnce(problem(503, "CONTROLLED_PRINT_RETRY", true))
      .mockResolvedValueOnce({
        replayed: false,
        snapshot: controlledPrintSnapshotFixture(),
      });
    const source = dataSource({ createSnapshot });
    const user = userEvent.setup();
    renderAction(source);

    await user.click(
      screen.getByRole("button", {
        name: "Check controlled print availability",
      }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Create controlled PDF" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Create retained PDF" }),
    );
    expect(
      await screen.findByText("Controlled print could not be completed safely"),
    ).toBeVisible();
    expect(screen.getByText("trace-controlled_print_retry")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry controlled PDF creation" }),
    );
    await screen.findByText("Controlled PDF retained");

    expect(createSnapshot).toHaveBeenCalledTimes(2);
    expect(createSnapshot.mock.calls[0]?.[3].idempotencyKey).toBe(
      createSnapshot.mock.calls[1]?.[3].idempotencyKey,
    );
  });

  it("distinguishes protected denial and conflict without leaking source truth", async () => {
    const denied = dataSource({
      loadCapability: vi.fn(() =>
        Promise.reject(problem(403, "CONTROLLED_PRINT_DENIED")),
      ),
    });
    const user = userEvent.setup();
    const rendered = renderAction(denied);
    await user.click(
      screen.getByRole("button", {
        name: "Check controlled print availability",
      }),
    );
    expect(
      await screen.findByText("Controlled print permission unavailable"),
    ).toBeVisible();
    expect(document.body).not.toHaveTextContent("private/files");

    rendered.unmount();
    const conflict = dataSource({
      loadCapability: vi.fn(() =>
        Promise.reject(problem(409, "CONTROLLED_PRINT_CONFLICT")),
      ),
    });
    renderAction(conflict);
    await user.click(
      screen.getByRole("button", {
        name: "Check controlled print availability",
      }),
    );
    expect(await screen.findByText("Controlled print conflict")).toBeVisible();
    expect(
      screen.getByText(
        "Reload the Project before creating another controlled print.",
      ),
    ).toBeVisible();
  });

  it("aborts an active capability request on unmount", async () => {
    let signal: AbortSignal | undefined;
    const loadCapability = vi.fn<ControlledPrintDataSource["loadCapability"]>(
      (_project, _source, _language, requestSignal) => {
        signal = requestSignal;
        return new Promise<ControlledPrintCapabilityViewModel>(() => undefined);
      },
    );
    const source = dataSource({
      loadCapability,
    });
    const user = userEvent.setup();
    const rendered = renderAction(source);
    await user.click(
      screen.getByRole("button", {
        name: "Check controlled print availability",
      }),
    );
    await waitFor(() => {
      expect(signal?.aborted).toBe(false);
    });
    rendered.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
