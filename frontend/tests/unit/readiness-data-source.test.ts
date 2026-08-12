import { afterEach, describe, expect, it, vi } from "vitest";

import { NpiTransportError } from "../../src/api/http";
import {
  isCanonicalReadinessTemplateCatalog,
  isCanonicalReadinessTemplateVersion,
  isCanonicalReadinessWorkspace,
  isReadinessTemplateCatalog,
  isReadinessTemplateVersion,
  isReadinessWorkspace,
  LiveReadinessDataSource,
  ReadinessRequestCancelledError,
  type CreateReadinessTemplateCommand,
  type ReadinessTemplateVersion,
  type ReviseProjectReadinessItemCommand,
} from "../../src/api/readiness-data-source";
import {
  readinessIds,
  readinessInitializationWorkspace,
  readinessRevisionOne,
  readinessWorkspace,
} from "../support/readiness-fixture";

const templateIds = {
  revision: "d3b3c792-a812-503a-82a0-91cecd72d3f9",
  root: "71000000-0000-4000-8000-000000000002",
  request: "71000000-0000-4000-8000-000000000003",
} as const;

function templateCommand(): CreateReadinessTemplateCommand {
  return {
    applicability: {
      customerReferenceKeys: [],
      industryKeys: ["automotive"],
      projectTypes: ["new_tool"],
    },
    categories: [{ key: "engineering", title: "Engineering readiness" }],
    items: [
      {
        applicability: {
          customerReferenceKeys: [],
          industryKeys: ["automotive"],
          projectTypes: ["new_tool"],
        },
        blockingLevel: "P0",
        categoryKey: "engineering",
        completionRule: "exact_evidence",
        evidenceRequirements: [
          {
            acceptedSourceKinds: ["released_document"],
            key: "released_design",
            minimumCount: 1,
            unavailableBlocks: true,
          },
        ],
        gateKey: "G5",
        key: "design_release",
        required: true,
        title: "Released design baseline",
        weight: 100,
      },
    ],
    templateCode: "AUTO-RDY",
    title: "Automotive readiness",
  };
}

function templateVersion(
  overrides: Partial<ReadinessTemplateVersion> = {},
): ReadinessTemplateVersion {
  const command = templateCommand();
  const publicationState = overrides.publicationState ?? "draft";
  const optimisticVersion = overrides.optimisticVersion ?? 1;
  const snapshotHash =
    overrides.snapshotHash ??
    (optimisticVersion === 2
      ? publicationState === "published"
        ? "365b49a3fc6da6b8dfcfd9779f44a8f4060bc5844637a35c906fa542960c87c1"
        : "02f47ce2ce917e172e507774ebe5732e23ba1bb07e284578a1a8b6811722f786"
      : "484e98417044208227c4d25256c976975733ddfe0afb24301f232b890a723b75");
  return {
    ...command,
    changedAt: "2026-08-11T10:00:00Z",
    changedByUserId: "system.manager@example.invalid",
    globalId: templateIds.revision,
    optimisticVersion,
    publicationState,
    requestId: templateIds.request,
    snapshotHash,
    templateGlobalId: templateIds.root,
    templateVersion: 1,
    traceId: "trace-readiness-template",
    ...overrides,
  };
}

function reviseCommand(): ReviseProjectReadinessItemCommand {
  const predecessor = readinessRevisionOne();
  return {
    confirmationValue: null,
    dueDate: "2026-08-20",
    expectedInstanceVersion: 1,
    expectedRevisionGlobalId: readinessIds.revisionOne,
    expectedRevisionSnapshotHash: predecessor.snapshotHash,
    itemKey: "trial_conclusion",
    ownerMemberGlobalId: readinessIds.qualityMember,
    sources: [
      {
        globalId: readinessIds.trialConclusionSource,
        kind: "trial_conclusion",
        requirementKey: "approved_trial_conclusion",
        snapshotHash: "b".repeat(64),
        sourceVersion: 2,
      },
    ],
    state: "complete",
  };
}

function commandContext(signal = new AbortController().signal) {
  return {
    csrfToken: "c".repeat(32),
    idempotencyKey: "readiness-command-12345678",
    signal,
  };
}

function response(
  value: unknown,
  init: RequestInit | undefined,
  status: 200 | 201,
  replayed?: boolean,
): Response {
  const requestId = new Headers(init?.headers).get("X-Request-ID") ?? "";
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(replayed === undefined
        ? {}
        : { "Idempotency-Replayed": String(replayed) }),
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-readiness-transport",
    },
    status,
  });
}

function requestUrl(request: RequestInfo | URL): string {
  if (typeof request === "string") return request;
  if (request instanceof URL) return request.href;
  return request.url;
}

function requestBody(init: RequestInit | undefined): unknown {
  if (typeof init?.body !== "string")
    throw new Error("The exact readiness command body is required.");
  return JSON.parse(init.body) as unknown;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("readiness response validation", () => {
  it("accepts the exact canonical template, catalog and Project history", async () => {
    const published = templateVersion({
      optimisticVersion: 2,
      publicationState: "published",
    });
    expect(isReadinessTemplateVersion(published)).toBe(true);
    await expect(isCanonicalReadinessTemplateVersion(published)).resolves.toBe(
      true,
    );
    expect(
      isReadinessTemplateCatalog({
        projectGlobalId: readinessIds.project,
        templates: [published],
      }),
    ).toBe(true);
    await expect(
      isCanonicalReadinessTemplateCatalog({
        projectGlobalId: readinessIds.project,
        templates: [published],
      }),
    ).resolves.toBe(true);
    expect(isReadinessWorkspace(readinessWorkspace())).toBe(true);
    await expect(
      isCanonicalReadinessWorkspace(readinessWorkspace()),
    ).resolves.toBe(true);
  });

  it("rejects score, blocker and ready values that were not derived from exact items", () => {
    expect(
      isReadinessWorkspace({
        ...readinessWorkspace(),
        callerScore: 10_000,
      }),
    ).toBe(false);
    const scoreDrift = structuredClone(readinessWorkspace());
    if (!scoreDrift.currentRevision)
      throw new Error("The fixture requires a current revision.");
    scoreDrift.currentRevision.evaluation.totalScore.basisPoints = 10_000;
    expect(isReadinessWorkspace(scoreDrift)).toBe(false);

    const blockerSuppression = structuredClone(readinessWorkspace());
    if (!blockerSuppression.currentRevision)
      throw new Error("The fixture requires a current revision.");
    blockerSuppression.currentRevision.evaluation.blockers = [];
    blockerSuppression.currentRevision.evaluation.ready = true;
    expect(isReadinessWorkspace(blockerSuppression)).toBe(false);
  });

  it("rejects coordinated hash-chain tampering and invalid canonical identities at the Promise boundary", async () => {
    const coordinated = structuredClone(readinessWorkspace());
    const predecessor = coordinated.revisions[0];
    const successor = coordinated.revisions[1];
    if (!predecessor || !successor)
      throw new Error("The fixture requires a successor pair.");
    predecessor.snapshotHash = "f".repeat(64);
    successor.predecessorSnapshotHash = predecessor.snapshotHash;
    coordinated.currentRevision = successor;
    expect(isReadinessWorkspace(coordinated)).toBe(true);
    await expect(isCanonicalReadinessWorkspace(coordinated)).resolves.toBe(
      false,
    );

    const wrongVersionKey = structuredClone(readinessWorkspace());
    const wrongVersionRevision = wrongVersionKey.revisions[0];
    if (!wrongVersionRevision)
      throw new Error("The fixture requires one revision.");
    wrongVersionRevision.versionKeyHash = "e".repeat(64);
    await expect(isCanonicalReadinessWorkspace(wrongVersionKey)).resolves.toBe(
      false,
    );

    const wrongItemIdentity = structuredClone(readinessWorkspace());
    for (const revision of wrongItemIdentity.revisions) {
      const design = revision.items.find(
        (item) => item.definition.key === "design_release",
      );
      if (!design) throw new Error("The fixture requires the design item.");
      design.globalId = "71000000-0000-4000-8000-000000000099";
    }
    wrongItemIdentity.currentRevision =
      wrongItemIdentity.revisions.at(-1) ?? null;
    expect(isReadinessWorkspace(wrongItemIdentity)).toBe(true);
    await expect(
      isCanonicalReadinessWorkspace(wrongItemIdentity),
    ).resolves.toBe(false);

    const wrongTemplateIdentity = templateVersion({
      globalId: "71000000-0000-4000-8000-000000000098",
    });
    expect(isReadinessTemplateVersion(wrongTemplateIdentity)).toBe(true);
    await expect(
      isCanonicalReadinessTemplateVersion(wrongTemplateIdentity),
    ).resolves.toBe(false);

    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_request, init) =>
        Promise.resolve(response(coordinated, init, 200)),
      ),
    );
    await expect(
      new LiveReadinessDataSource().loadWorkspace(
        readinessIds.project,
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });

  it("rejects broken successor links, duplicate source options and anything but the five exact external holds", () => {
    const brokenChain = structuredClone(readinessWorkspace());
    const current = brokenChain.revisions[1];
    if (!current) throw new Error("The fixture requires a successor.");
    current.predecessorSnapshotHash = "f".repeat(64);
    brokenChain.currentRevision = current;
    expect(isReadinessWorkspace(brokenChain)).toBe(false);

    const duplicateOption = structuredClone(readinessWorkspace());
    const option = duplicateOption.sourceOptions[0];
    if (!option) throw new Error("The fixture requires a source option.");
    duplicateOption.sourceOptions = [
      ...duplicateOption.sourceOptions,
      structuredClone(option),
    ];
    expect(isReadinessWorkspace(duplicateOption)).toBe(false);

    const missingProjection = structuredClone(readinessWorkspace());
    missingProjection.unavailableProjections =
      missingProjection.unavailableProjections.slice(0, -1);
    expect(isReadinessWorkspace(missingProjection)).toBe(false);
  });

  it("rejects latest-like, identity-free internal and caller-owned unavailable truth", () => {
    const latest = structuredClone(readinessWorkspace());
    const source = latest.currentRevision?.items[0]?.sources[0];
    if (!source) throw new Error("The fixture requires exact evidence.");
    source.sourceVersion = null;
    source.snapshotHash = null;
    expect(isReadinessWorkspace(latest)).toBe(false);

    const callerUnavailable = structuredClone(readinessWorkspace());
    const unavailable = callerUnavailable.currentRevision?.items[2]?.sources[0];
    if (!unavailable)
      throw new Error("The fixture requires an unavailable projection.");
    unavailable.globalId = readinessIds.workItemSource;
    expect(isReadinessWorkspace(callerUnavailable)).toBe(false);
  });
});

describe("LiveReadinessDataSource", () => {
  it("loads only the Project-correlated catalog and workspace through private no-store routes", async () => {
    const published = templateVersion({
      optimisticVersion: 2,
      publicationState: "published",
    });
    const catalog = {
      projectGlobalId: readinessIds.project,
      templates: [published],
    };
    const workspace = readinessWorkspace();
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementationOnce((request, init) => {
        expect(requestUrl(request)).toBe(
          `/api/npi/v1/npi-readiness/templates?projectId=${readinessIds.project}`,
        );
        expect(new Headers(init?.headers).has("X-Frappe-CSRF-Token")).toBe(
          false,
        );
        return Promise.resolve(response(catalog, init, 200));
      })
      .mockImplementationOnce((request, init) => {
        expect(requestUrl(request)).toBe(
          `/api/npi/v1/projects/${readinessIds.project}/npi-readiness`,
        );
        return Promise.resolve(response(workspace, init, 200));
      });
    vi.stubGlobal("fetch", fetchMock);
    const source = new LiveReadinessDataSource();
    const signal = new AbortController().signal;

    await expect(
      source.listEligibleTemplates(readinessIds.project, signal),
    ).resolves.toEqual(catalog);
    await expect(
      source.loadWorkspace(readinessIds.project, signal),
    ).resolves.toEqual(workspace);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("sends a closed template command with CSRF, idempotency and replay evidence", async () => {
    const command = templateCommand();
    const result = templateVersion();
    const context = commandContext();
    const fetchMock = vi.fn<typeof fetch>((request, init) => {
      expect(requestUrl(request)).toBe("/api/npi/v1/npi-readiness/templates");
      expect(init?.method).toBe("POST");
      const headers = new Headers(init?.headers);
      expect(headers.get("X-Frappe-CSRF-Token")).toBe(context.csrfToken);
      expect(headers.get("Idempotency-Key")).toBe(context.idempotencyKey);
      expect(requestBody(init)).toEqual(command);
      return Promise.resolve(response(result, init, 201, false));
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveReadinessDataSource().createTemplate(command, context),
    ).resolves.toEqual({ replayed: false, template: result });
  });

  it("edits and publishes only the exact routed template version", async () => {
    const create = templateCommand();
    const edit = {
      applicability: create.applicability,
      categories: create.categories,
      expectedOptimisticVersion: 1,
      items: create.items,
      title: create.title,
    };
    const publish = { expectedOptimisticVersion: 1 };
    const edited = templateVersion({ optimisticVersion: 2 });
    const published = templateVersion({
      optimisticVersion: 2,
      publicationState: "published",
    });
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementationOnce((request, init) => {
        expect(requestUrl(request)).toBe(
          `/api/npi/v1/npi-readiness/templates/${templateIds.root}/versions/1`,
        );
        expect(init?.method).toBe("PUT");
        expect(requestBody(init)).toEqual(edit);
        return Promise.resolve(response(edited, init, 200, false));
      })
      .mockImplementationOnce((request, init) => {
        expect(requestUrl(request)).toBe(
          `/api/npi/v1/npi-readiness/templates/${templateIds.root}/versions/1:publish`,
        );
        expect(init?.method).toBe("POST");
        expect(requestBody(init)).toEqual(publish);
        return Promise.resolve(response(published, init, 200, true));
      });
    vi.stubGlobal("fetch", fetchMock);
    const source = new LiveReadinessDataSource();

    await expect(
      source.editTemplate(templateIds.root, 1, edit, commandContext()),
    ).resolves.toEqual({ replayed: false, template: edited });
    await expect(
      source.publishTemplate(templateIds.root, 1, publish, commandContext()),
    ).resolves.toEqual({ replayed: true, template: published });
  });

  it("preserves one exact body and idempotency key across a safe same-key retry", async () => {
    const workspace = readinessWorkspace();
    const command = reviseCommand();
    const context = commandContext();
    const bodies: unknown[] = [];
    const keys: (string | null)[] = [];
    let call = 0;
    const fetchMock = vi.fn<typeof fetch>((request, init) => {
      expect(requestUrl(request)).toBe(
        `/api/npi/v1/projects/${readinessIds.project}/npi-readiness/${readinessIds.instance}/revisions`,
      );
      bodies.push(requestBody(init));
      keys.push(new Headers(init?.headers).get("Idempotency-Key"));
      const replayed = call > 0;
      call += 1;
      return Promise.resolve(response(workspace, init, 201, replayed));
    });
    vi.stubGlobal("fetch", fetchMock);
    const source = new LiveReadinessDataSource();

    await expect(
      source.reviseItem(
        readinessIds.project,
        readinessIds.instance,
        command,
        context,
      ),
    ).resolves.toEqual({ replayed: false, workspace });
    await expect(
      source.reviseItem(
        readinessIds.project,
        readinessIds.instance,
        command,
        context,
      ),
    ).resolves.toEqual({ replayed: true, workspace });
    expect(bodies).toEqual([command, command]);
    expect(keys).toEqual([context.idempotencyKey, context.idempotencyKey]);
  });

  it("rejects a successor that changes a different item even when the command target already matches", async () => {
    const misrouted = structuredClone(readinessWorkspace());
    const predecessor = misrouted.revisions[0];
    const current = misrouted.revisions[1];
    if (!predecessor || !current)
      throw new Error("The fixture requires an exact successor pair.");
    const trialIndex = current.items.findIndex(
      (item) => item.definition.key === "trial_conclusion",
    );
    const supplierIndex = current.items.findIndex(
      (item) => item.definition.key === "supplier_execution",
    );
    const currentTrial = current.items[trialIndex];
    const priorSupplier = predecessor.items[supplierIndex];
    const currentSupplier = current.items[supplierIndex];
    if (!currentTrial || !priorSupplier || !currentSupplier)
      throw new Error("The fixture requires trial and supplier items.");
    predecessor.items = predecessor.items.map((item, index) =>
      index === trialIndex ? structuredClone(currentTrial) : item,
    );
    predecessor.evaluation = structuredClone(current.evaluation);
    current.items = current.items.map((item, index) =>
      index === supplierIndex
        ? {
            ...currentSupplier,
            itemVersion: priorSupplier.itemVersion + 1,
            state: "in_progress" as const,
          }
        : item,
    );
    misrouted.currentRevision = current;
    expect(isReadinessWorkspace(misrouted)).toBe(true);

    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_request, init) =>
        Promise.resolve(response(misrouted, init, 201, false)),
      ),
    );
    await expect(
      new LiveReadinessDataSource().reviseItem(
        readinessIds.project,
        readinessIds.instance,
        reviseCommand(),
        commandContext(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });

  it("correlates initialization to the exact Project/template/assignments", async () => {
    const workspace = readinessInitializationWorkspace();
    const first = workspace.currentRevision;
    if (!first) throw new Error("The fixture requires an initial revision.");
    const command = {
      assignments: first.items.map((item) => ({
        dueDate: item.dueDate ?? "",
        itemKey: item.definition.key,
        ownerMemberGlobalId: item.owner?.globalId ?? "",
      })),
      industryKey: first.project.industryKey,
      templateRevisionGlobalId: first.templateRevision.globalId,
      templateSnapshotHash: first.templateRevision.snapshotHash,
      templateVersion: first.templateRevision.version,
    };
    const fetchMock = vi.fn<typeof fetch>((request, init) => {
      expect(requestUrl(request)).toBe(
        `/api/npi/v1/projects/${readinessIds.project}/npi-readiness`,
      );
      expect(requestBody(init)).toEqual(command);
      return Promise.resolve(response(workspace, init, 201, false));
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveReadinessDataSource().initialize(
        readinessIds.project,
        command,
        commandContext(),
      ),
    ).resolves.toEqual({ replayed: false, workspace });
  });

  it("rejects client score/blocker/source-state authority before transport", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    const source = new LiveReadinessDataSource();
    const context = commandContext();

    await expect(
      source.reviseItem(
        readinessIds.project,
        readinessIds.instance,
        {
          ...reviseCommand(),
          score: 10_000,
        } as unknown as ReviseProjectReadinessItemCommand,
        context,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.reviseItem(
        readinessIds.project,
        readinessIds.instance,
        {
          ...reviseCommand(),
          sources: [
            {
              kind: "erp_quality_result",
              requirementKey: "formal_quality",
              state: "satisfied",
            },
          ],
        } as unknown as ReviseProjectReadinessItemCommand,
        context,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("normalizes aborts to the readiness cancellation boundary", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveReadinessDataSource().loadWorkspace(
        readinessIds.project,
        controller.signal,
      ),
    ).rejects.toBeInstanceOf(ReadinessRequestCancelledError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
