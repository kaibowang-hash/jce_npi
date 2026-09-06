import { describe, expect, it, vi } from "vitest";

import {
  GateEvidenceRequestCancelledError,
  isGateEvidenceResponse,
  isGateEvidenceResponseForRoute,
  LiveGateEvidenceDataSource,
} from "../../src/api/gate-evidence-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import type { GateEvidenceViewModel } from "../../src/domain/view-models";
import { gateEvidenceFixture as legacyGateEvidenceFixture } from "../support/gate-evidence-fixture";

const requirementGlobalIds = [
  "d1111111-1111-1111-1111-111111111111",
  "d2222222-2222-2222-2222-222222222222",
  "d3333333-3333-3333-3333-333333333333",
] as const;

function gateEvidenceFixture(): GateEvidenceViewModel {
  const fixture = legacyGateEvidenceFixture();
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

function releaseBaselineFixture(): GateEvidenceViewModel {
  const fixture = cloneFixture();
  const requirement = fixture.requirements[0];
  if (!requirement) throw new Error("The fixture requires a Gate requirement.");
  const baselineId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
  const baselineHash = "5".repeat(64);
  return {
    ...fixture,
    requirements: fixture.requirements.map((candidate, index) =>
      index === 0
        ? {
            ...requirement,
            allowedEvidenceKinds: ["release_baseline"],
            evidence: [
              {
                globalId: "99999999-9999-4999-8999-999999999999",
                kind: "release_baseline",
                sourceObjectType: "release_baseline",
                sourceGlobalId: baselineId,
                revision: 1,
                objectHash: baselineHash,
                createdAt: "2026-07-31T12:00:00Z",
                createdBy: "Administrator",
                baseline: {
                  globalId: baselineId,
                  label: "G2 release package",
                  version: 1,
                  snapshotHash: baselineHash,
                  policy: {
                    globalId: "abababab-abab-4bab-8bab-abababababab",
                    version: 1,
                    snapshotHash: "6".repeat(64),
                  },
                  createdByUserId: "Administrator",
                  createdAt: "2026-07-31T11:59:00Z",
                  members: [
                    {
                      globalId: "acacacac-acac-4cac-8cac-acacacacacac",
                      sequence: 1,
                      documentGlobalId: "adadadad-adad-4dad-8dad-adadadadadad",
                      revisionGlobalId: "aeaeaeae-aeae-4eae-8eae-aeaeaeaeaeae",
                      major: 1,
                      minor: 0,
                      revisionSnapshotHash: "7".repeat(64),
                      lifecycleVersion: 4,
                      releaseEventGlobalId:
                        "afafafaf-afaf-4faf-8faf-afafafafafaf",
                      releaseSnapshotHash: "8".repeat(64),
                      memberHash: "9".repeat(64),
                      files: [
                        {
                          fileRevisionGlobalId:
                            "b0b0b0b0-b0b0-40b0-80b0-b0b0b0b0b0b0",
                          fileDocumentGlobalId:
                            "b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1",
                          fileName: "released-drawing.pdf",
                          mimeType: "application/pdf",
                          sizeBytes: 1024,
                          sha256: "a".repeat(64),
                          scanState: "clean",
                        },
                      ],
                    },
                  ],
                },
              },
            ],
          }
        : candidate,
    ),
  };
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

  it("accepts an exact URL-free release baseline and rejects identity drift", () => {
    const fixture = releaseBaselineFixture();
    expect(isGateEvidenceResponse(fixture)).toBe(true);

    const drifted = structuredClone(fixture);
    const baseline = drifted.requirements[0]?.evidence[0]?.baseline;
    if (!baseline) throw new Error("The fixture requires baseline evidence.");
    baseline.snapshotHash = "0".repeat(64);
    expect(isGateEvidenceResponse(drifted)).toBe(false);
  });

  it("accepts newest-first explicit successor impact lineage only", () => {
    const fixture = releaseBaselineFixture();
    const reference = fixture.requirements[0]?.evidence[0];
    if (!reference)
      throw new Error("The fixture requires release baseline evidence.");
    fixture.baselineImpacts = [
      {
        globalId: "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0",
        eventType: "invalidated",
        dependencyGlobalId: "c1c1c1c1-c1c1-41c1-81c1-c1c1c1c1c1c1",
        baselineGlobalId: reference.sourceGlobalId,
        baselineSnapshotHash: reference.objectHash,
        oldRevisionGlobalId: "c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2",
        oldRevisionSnapshotHash: "b".repeat(64),
        newRevisionGlobalId: "c3c3c3c3-c3c3-43c3-83c3-c3c3c3c3c3c3",
        newRevisionSnapshotHash: "c".repeat(64),
        gateGlobalId: fixture.gate.globalId,
        requirementGlobalId: fixture.requirements[0]?.globalId ?? "",
        evidenceReferenceGlobalId: reference.globalId,
        initiatedByUserId: "Administrator",
        occurredAt: "2026-08-01T08:00:00Z",
        eventHash: "d".repeat(64),
      },
    ];
    expect(isGateEvidenceResponse(fixture)).toBe(true);

    const inferred = structuredClone(fixture);
    const inferredImpact = inferred.baselineImpacts[0];
    if (!inferredImpact)
      throw new Error("The fixture requires impact lineage.");
    inferredImpact.evidenceReferenceGlobalId =
      "ffffffff-ffff-4fff-8fff-ffffffffffff";
    expect(isGateEvidenceResponse(inferred)).toBe(false);
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
                evidenceState,
                evidence: [
                  {
                    ...reference,
                    file: {
                      ...file,
                      scanState,
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
