import { describe, expect, it, vi } from "vitest";

import type {
  ErpProjectionCollectionViewModel,
  ErpProjectionsDataSource,
} from "../../src/api/erp-projections-data-source";
import {
  FORMAL_QUALITY_LINK_ACKNOWLEDGEMENT,
  LiveFormalQualityLinkDataSource,
  formalQualityCandidate,
  isFormalQualityLinkCollection,
  type FormalQualitySourceReference,
} from "../../src/api/formal-quality-link-data-source";
import { NpiHttpClient } from "../../src/api/http";

const ids = {
  project: "10000000-0000-4000-8000-000000000001",
  source: "10000000-0000-4000-8000-000000000002",
  scope: "10000000-0000-4000-8000-000000000003",
  observation: "10000000-0000-4000-8000-000000000004",
  projectionHead: "10000000-0000-4000-8000-000000000005",
  link: "10000000-0000-4000-8000-000000000006",
  revision: "10000000-0000-4000-8000-000000000007",
} as const;
const hash = (value: string): string => value.repeat(64);
const source: FormalQualitySourceReference = {
  scopeGlobalId: ids.scope,
  scopeKind: "trial_round",
  sourceCapability: true,
  sourceGlobalId: ids.source,
  sourceKind: "trial_defect",
  sourceSnapshotHash: hash("a"),
  sourceVersion: 3,
};

function projection(): ErpProjectionCollectionViewModel {
  const values = {
    recordKind: "quality_inspection" as const,
    statusCode: "Completed",
    resultCode: "Accepted",
    observedAt: "2026-08-26T08:00:00Z",
  };
  return {
    projectGlobalId: ids.project,
    accessState: "available",
    reasonCode: null,
    permissions: { view: true, edit: false, refresh: false },
    items: [
      {
        observationGlobalId: ids.observation,
        projectionKind: "formal_quality_status",
        scopeKind: "trial_round",
        scopeGlobalId: ids.scope,
        availability: "available",
        freshness: "fresh",
        disposition: "applied_current",
        sourceSystem: "ERPNEXT",
        sourceObjectType: "Quality Inspection",
        sourceObjectId: "QI-SANDBOX",
        sourceVersion: "erp-v2",
        sourceModifiedAt: "2026-08-26T08:00:00Z",
        receivedAt: "2026-08-26T08:01:00Z",
        payloadHash: hash("b"),
        unavailableReasonCode: null,
        values,
        currentTruth: {
          observationGlobalId: ids.observation,
          headGlobalId: ids.projectionHead,
          headOptimisticVersion: 2,
          headHash: hash("c"),
          sourceVersion: "erp-v2",
          sourceModifiedAt: "2026-08-26T08:00:00Z",
          receivedAt: "2026-08-26T08:01:00Z",
          payloadHash: hash("b"),
          values,
        },
        editable: false,
      },
    ],
  };
}

function collection() {
  return {
    projectGlobalId: ids.project,
    permissions: { view: true, link: true },
    items: [],
  };
}

describe("formal quality link data source", () => {
  it("selects only one fresh current observation with exact head identity", () => {
    const item = projection().items[0];
    expect(item).toBeDefined();
    if (!item) throw new Error("projection fixture missing");
    expect(formalQualityCandidate(item, source)).toMatchObject({
      observationGlobalId: ids.observation,
      headGlobalId: ids.projectionHead,
      headOptimisticVersion: 2,
      headHash: hash("c"),
    });
    const missingHead = structuredClone(item);
    if (!missingHead.currentTruth) throw new Error("current truth missing");
    delete missingHead.currentTruth.headGlobalId;
    expect(formalQualityCandidate(missingHead, source)).toBeNull();
    expect(
      formalQualityCandidate({ ...item, freshness: "stale" }, source),
    ).toBeNull();
  });

  it("loads Project-contained link and projection truth and sends one exact command", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(collection());
    const loadProjectProjections = vi.fn().mockResolvedValue(projection());
    const projections: ErpProjectionsDataSource = { loadProjectProjections };
    const dataSource = new LiveFormalQualityLinkDataSource(http, projections);
    const signal = new AbortController().signal;
    const loaded = await dataSource.load(ids.project, source, signal);
    expect(loaded.candidate?.headGlobalId).toBe(ids.projectionHead);
    expect(request.mock.calls[0]?.[0]).toBe(
      `/projects/${ids.project}/formal-quality-links`,
    );
    expect(loadProjectProjections).toHaveBeenCalledWith(
      ids.project,
      signal,
      "formal_quality_status",
    );
  });

  it("rejects extra collection fields and preserves the fixed acknowledgement", () => {
    expect(isFormalQualityLinkCollection(collection(), ids.project)).toBe(true);
    expect(
      isFormalQualityLinkCollection(
        { ...collection(), secret: "x" },
        ids.project,
      ),
    ).toBe(false);
    expect(FORMAL_QUALITY_LINK_ACKNOWLEDGEMENT).toContain(
      "does not write ERPNext",
    );
    expect(FORMAL_QUALITY_LINK_ACKNOWLEDGEMENT).toContain(
      "interpret a formal pass",
    );
  });
});
