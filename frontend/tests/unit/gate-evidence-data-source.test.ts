import { describe, expect, it, vi } from "vitest";

import {
  GateEvidenceRequestCancelledError,
  isGateEvidenceResponse,
  isGateEvidenceResponseForRoute,
  LiveGateEvidenceDataSource,
} from "../../src/api/gate-evidence-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import type {
  GateEvidenceScanState,
  GateEvidenceViewModel,
  GateRequirementEvidenceState,
} from "../../src/domain/view-models";
import { gateEvidenceFixture as legacyGateEvidenceFixture } from "../support/gate-evidence-fixture";

const requirementGlobalIds = [
  "d1111111-1111-1111-1111-111111111111",
  "d2222222-2222-2222-2222-222222222222",
  "d3333333-3333-3333-3333-333333333333",
] as const;

function gateEvidenceFixture(): GateEvidenceViewModel {
  const fixture =
    legacyGateEvidenceFixture() as unknown as GateEvidenceViewModel;
  return {
    ...fixture,
    requirements: fixture.requirements.map((requirement, index) => ({
      ...requirement,
      globalId:
        requirementGlobalIds[index] ?? "dfffffff-ffff-ffff-ffff-ffffffffffff",
    })),
  };
}

function cloneFixture(): GateEvidenceViewModel {
  return structuredClone(gateEvidenceFixture());
}

function recordAt(
  values: readonly Record<string, unknown>[],
  index: number,
): Record<string, unknown> {
  const value = values[index];
  if (!value)
    throw new Error(`Missing fixture record at index ${String(index)}.`);
  return value;
}

describe("live Gate evidence data source", () => {
  it("loads the exact same-origin BFF path with strict route-bound validation", async () => {
    const fixture = gateEvidenceFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const dataSource = new LiveGateEvidenceDataSource(http);
    const controller = new AbortController();

    await expect(
      dataSource.load(
        fixture.project.globalId,
        fixture.gate.globalId,
        controller.signal,
      ),
    ).resolves.toEqual(fixture);
    expect(request).toHaveBeenCalledOnce();
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${fixture.project.globalId}/gates/${fixture.gate.globalId}/evidence`,
    );
    expect(init).toEqual({ signal: controller.signal });
    expect(options).toMatchObject({
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(options?.validate?.(fixture)).toBe(true);
    expect(
      options?.validate?.({
        ...fixture,
        gate: {
          ...fixture.gate,
          globalId: "55555555-5555-4555-8555-555555555555",
        },
      }),
    ).toBe(false);
  });

  it.each([
    ["not-a-project-uuid", "44444444-4444-4444-8444-444444444444"],
    ["11111111-1111-4111-8111-111111111111", "not-a-gate-uuid"],
  ])(
    "rejects invalid route identities before issuing a request",
    async (projectGlobalId, gateGlobalId) => {
      const http = new NpiHttpClient();
      const request = vi.spyOn(http, "request");
      const dataSource = new LiveGateEvidenceDataSource(http);

      await expect(
        dataSource.load(
          projectGlobalId,
          gateGlobalId,
          new AbortController().signal,
        ),
      ).rejects.toMatchObject({
        kind: "request_not_ready",
        name: "NpiTransportError",
        referenceKind: "client",
      });
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("converts an aborted transport into a cancellation result", async () => {
    const fixture = gateEvidenceFixture();
    const http = new NpiHttpClient();
    vi.spyOn(http, "request").mockImplementation(
      <T>(_path: string, init: RequestInit = {}): Promise<T> =>
        new Promise<T>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(
              new NpiTransportError("network", "request-aborted", "request"),
            );
          });
        }),
    );
    const dataSource = new LiveGateEvidenceDataSource(http);
    const controller = new AbortController();
    const request = dataSource.load(
      fixture.project.globalId,
      fixture.gate.globalId,
      controller.signal,
    );

    controller.abort();
    await expect(request).rejects.toBeInstanceOf(
      GateEvidenceRequestCancelledError,
    );
  });
});

describe("Gate evidence response validation", () => {
  it("accepts the exact frozen requirement and evidence contract", () => {
    const fixture = gateEvidenceFixture();
    expect(isGateEvidenceResponse(fixture)).toBe(true);
    expect(
      isGateEvidenceResponseForRoute(
        fixture,
        fixture.project.globalId,
        fixture.gate.globalId,
      ),
    ).toBe(true);
  });

  it.each([
    [
      "unknown top-level fields",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        rawPrivateUrl: "/private/files/unsafe.pdf",
      }),
    ],
    [
      "unknown evidence fields",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const requirement = recordAt(requirements, 1);
        const evidence = requirement.evidence as Record<string, unknown>[];
        evidence[0] = { ...evidence[0], url: "/private/files/unsafe.pdf" };
        return fixture;
      },
    ],
    [
      "latest instead of an exact revision",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const requirement = recordAt(requirements, 0);
        const evidence = requirement.evidence as Record<string, unknown>[];
        evidence[0] = { ...evidence[0], revision: "latest" };
        return fixture;
      },
    ],
    [
      "a file reference without file metadata",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const requirement = recordAt(requirements, 1);
        const evidence = requirement.evidence as Record<string, unknown>[];
        const reference = { ...recordAt(evidence, 0) };
        delete reference.file;
        evidence[0] = reference;
        return fixture;
      },
    ],
    [
      "a WBS reference with client file metadata",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const requirement = recordAt(requirements, 0);
        const evidence = requirement.evidence as Record<string, unknown>[];
        evidence[0] = {
          ...evidence[0],
          file: {
            fileName: "unsafe.pdf",
            mimeType: "application/pdf",
            sizeBytes: 12,
            scanState: "clean",
          },
        };
        return fixture;
      },
    ],
    [
      "a mismatched source object type",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const requirement = recordAt(requirements, 0);
        const evidence = requirement.evidence as Record<string, unknown>[];
        evidence[0] = {
          ...evidence[0],
          sourceObjectType: "file_revision",
        };
        return fixture;
      },
    ],
    [
      "a mismatched summary",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        summary: {
          ...(fixture.summary as Record<string, unknown>),
          unsafeScanCount: 0,
        },
      }),
    ],
    [
      "duplicate evidence identities",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const first = recordAt(requirements, 0);
        const second = recordAt(requirements, 1);
        const firstEvidence = first.evidence as Record<string, unknown>[];
        const secondEvidence = second.evidence as Record<string, unknown>[];
        secondEvidence[0] = {
          ...secondEvidence[0],
          globalId: recordAt(firstEvidence, 0).globalId,
        };
        return fixture;
      },
    ],
    [
      "a missing requirement with attached evidence",
      (fixture: Record<string, unknown>) => {
        const requirements = fixture.requirements as Record<string, unknown>[];
        const first = recordAt(requirements, 0);
        first.evidenceState = "missing";
        return fixture;
      },
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = cloneFixture() as unknown as Record<string, unknown>;
    expect(isGateEvidenceResponse(mutate(fixture))).toBe(false);
  });

  it.each([
    ["pending", "scan_pending", 1],
    ["clean", "scan_clean", 0],
    ["failed", "scan_failed", 1],
    ["infected", "scan_infected", 1],
  ] as const)(
    "preserves the real %s file scan state",
    (scanState, evidenceState, unsafeScanCount) => {
      const fixture = cloneFixture();
      const requirement = fixture.requirements[1];
      const reference = requirement?.evidence[0];
      const file = reference?.file;
      if (!requirement || !reference || !file) {
        throw new Error("The test fixture must contain file evidence.");
      }
      const next: GateEvidenceViewModel = {
        ...fixture,
        requirements: fixture.requirements.map((candidate, index) =>
          index === 1
            ? {
                ...candidate,
                evidenceState: evidenceState as GateRequirementEvidenceState,
                evidence: [
                  {
                    ...reference,
                    file: {
                      ...file,
                      scanState: scanState as GateEvidenceScanState,
                    },
                  },
                ],
              }
            : candidate,
        ),
        summary: { ...fixture.summary, unsafeScanCount },
      };
      expect(isGateEvidenceResponse(next)).toBe(true);
    },
  );
});
