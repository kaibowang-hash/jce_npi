import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ErpProjectionsRequestCancelledError,
  isErpProjectionCollection,
  LiveErpProjectionsDataSource,
  type ErpProjectionCollectionViewModel,
} from "../../src/api/erp-projections-data-source";
import { NpiTransportError } from "../../src/api/http";
import {
  erpProjectionCollectionFixture,
  projectControlIds,
} from "../support/project-controls-fixture";

function required<T>(value: T | undefined, message: string): T {
  if (value === undefined) throw new Error(message);
  return value;
}

function governedResponse(value: unknown, init?: RequestInit): Response {
  const requestId = new Headers(init?.headers).get("X-Request-ID") ?? "";
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-erp-projection-source-test",
    },
    status: 200,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ERP projection response validation", () => {
  it("accepts the exact sorted seven-kind collection", () => {
    const value = erpProjectionCollectionFixture();
    expect(isErpProjectionCollection(value, projectControlIds.project)).toBe(
      true,
    );
    expect(value.items.map((item) => item.projectionKind)).toEqual([
      "customer_master",
      "formal_item_master",
      "formal_quality_status",
      "project_cost",
      "supplier_master",
      "tool_asset_status",
      "tooling_procurement_cost",
    ]);
  });

  it("rejects extra fields, secrets, source substitution and escaped containment", () => {
    const extra = structuredClone(
      erpProjectionCollectionFixture(),
    ) as unknown as Record<string, unknown>;
    extra.rawUrl = "https://erp.example.invalid/private";
    expect(isErpProjectionCollection(extra, projectControlIds.project)).toBe(
      false,
    );

    const secret = structuredClone(
      erpProjectionCollectionFixture(),
    ) as unknown as Record<string, unknown>;
    secret.apiSecret = "do-not-expose";
    expect(isErpProjectionCollection(secret, projectControlIds.project)).toBe(
      false,
    );

    const substituted = structuredClone(erpProjectionCollectionFixture());
    const asset = substituted.items.find(
      (item) => item.projectionKind === "tool_asset_status",
    );
    if (!asset) throw new Error("The Asset fixture is required.");
    asset.sourceSystem = "NPI_ONE" as "ERPNEXT";
    expect(
      isErpProjectionCollection(substituted, projectControlIds.project),
    ).toBe(false);

    const escaped = structuredClone(erpProjectionCollectionFixture());
    escaped.projectGlobalId = "ffffffff-ffff-4fff-8fff-ffffffffffff";
    expect(isErpProjectionCollection(escaped, projectControlIds.project)).toBe(
      false,
    );
  });

  it("rejects unknown kinds, wrong source types, ordering drift and duplicate identity", () => {
    const unknown = structuredClone(erpProjectionCollectionFixture());
    const first = unknown.items[0];
    if (!first) throw new Error("The projection fixture is required.");
    first.projectionKind = "unknown_projection" as typeof first.projectionKind;
    expect(isErpProjectionCollection(unknown)).toBe(false);

    const sourceType = structuredClone(erpProjectionCollectionFixture());
    const customer = sourceType.items[0];
    if (!customer) throw new Error("The customer fixture is required.");
    customer.sourceObjectType = "Supplier";
    expect(isErpProjectionCollection(sourceType)).toBe(false);

    const ordering = structuredClone(erpProjectionCollectionFixture());
    const reversed = { ...ordering, items: [...ordering.items].reverse() };
    expect(isErpProjectionCollection(reversed)).toBe(false);

    const duplicate = structuredClone(erpProjectionCollectionFixture());
    const duplicateSource = required(
      duplicate.items[0],
      "The duplicate projection fixture is required.",
    );
    const duplicated = {
      ...duplicate,
      items: [...duplicate.items, structuredClone(duplicateSource)],
    };
    expect(isErpProjectionCollection(duplicated)).toBe(false);

    const invalidCalendarDate = structuredClone(
      erpProjectionCollectionFixture(),
    );
    required(
      invalidCalendarDate.items[0],
      "The invalid-date projection fixture is required.",
    ).receivedAt = "2026-02-31T00:00:00Z";
    expect(isErpProjectionCollection(invalidCalendarDate)).toBe(false);
  });

  it("accepts honest unavailable, stale, synthetic and conflict observations without promoting them", () => {
    const states: ErpProjectionCollectionViewModel[] = [];

    const unavailable = structuredClone(erpProjectionCollectionFixture());
    const unavailableItem = required(
      unavailable.items[0],
      "The unavailable projection fixture is required.",
    );
    unavailableItem.availability = "unavailable";
    unavailableItem.freshness = "unknown";
    unavailableItem.disposition = "unavailable_current";
    unavailableItem.sourceVersion = null;
    unavailableItem.sourceModifiedAt = null;
    unavailableItem.unavailableReasonCode = "source_not_observed";
    unavailableItem.values = null;
    unavailableItem.currentTruth = null;
    states.push(unavailable);

    const stale = structuredClone(erpProjectionCollectionFixture());
    required(
      stale.items[0],
      "The stale projection fixture is required.",
    ).freshness = "stale";
    states.push(stale);

    const synthetic = structuredClone(erpProjectionCollectionFixture());
    const syntheticItem = required(
      synthetic.items[0],
      "The synthetic projection fixture is required.",
    );
    syntheticItem.availability = "synthetic";
    syntheticItem.freshness = "unknown";
    syntheticItem.disposition = "synthetic_retained";
    states.push(synthetic);

    const conflict = structuredClone(erpProjectionCollectionFixture());
    required(
      conflict.items[0],
      "The conflict projection fixture is required.",
    ).disposition = "conflicted";
    states.push(conflict);

    expect(
      states.every((value) =>
        isErpProjectionCollection(value, projectControlIds.project),
      ),
    ).toBe(true);

    const promotedConflict = structuredClone(conflict);
    const promotedItem = required(
      promotedConflict.items[0],
      "The promoted conflict fixture is required.",
    );
    promotedItem.disposition = "applied_current";
    const promotedTruth = promotedItem.currentTruth;
    if (!promotedTruth)
      throw new Error("The promoted current truth is required.");
    promotedTruth.payloadHash = "f".repeat(64);
    expect(isErpProjectionCollection(promotedConflict)).toBe(false);
  });

  it("accepts only the closed redacted access state", () => {
    const redacted: ErpProjectionCollectionViewModel = {
      projectGlobalId: projectControlIds.project,
      accessState: "redacted",
      reasonCode: "projection_access_redacted",
      permissions: { view: false, edit: false, refresh: false },
      items: [],
    };
    expect(isErpProjectionCollection(redacted, projectControlIds.project)).toBe(
      true,
    );
    expect(
      isErpProjectionCollection({
        ...redacted,
        permissions: { ...redacted.permissions, view: true },
      }),
    ).toBe(false);
    expect(
      isErpProjectionCollection({
        ...redacted,
        items: erpProjectionCollectionFixture().items,
      }),
    ).toBe(false);
  });

  it("accepts formal-quality head identity only as one complete closed tuple", () => {
    const identified = structuredClone(erpProjectionCollectionFixture());
    const quality = identified.items.find(
      (item) => item.projectionKind === "formal_quality_status",
    );
    if (!quality?.currentTruth) {
      throw new Error("The formal-quality current truth fixture is required.");
    }
    quality.currentTruth.headGlobalId = "a86ce132-f344-49c9-9f26-183dd1f36fd8";
    quality.currentTruth.headOptimisticVersion = 3;
    quality.currentTruth.headHash = "a".repeat(64);
    expect(isErpProjectionCollection(identified)).toBe(true);

    const partial = structuredClone(identified);
    const partialQuality = partial.items.find(
      (item) => item.projectionKind === "formal_quality_status",
    );
    if (!partialQuality?.currentTruth) {
      throw new Error("The partial formal-quality current truth is required.");
    }
    delete partialQuality.currentTruth.headHash;
    expect(isErpProjectionCollection(partial)).toBe(false);

    const extra = structuredClone(identified) as unknown as {
      items: {
        projectionKind: string;
        currentTruth: Record<string, unknown> | null;
      }[];
    };
    const extraQuality = extra.items.find(
      (item) => item.projectionKind === "formal_quality_status",
    );
    if (!extraQuality?.currentTruth) {
      throw new Error("The extra formal-quality current truth is required.");
    }
    extraQuality.currentTruth.erpStatus = "Accepted";
    expect(isErpProjectionCollection(extra)).toBe(false);
  });
});

describe("ERP projection live data source", () => {
  it("uses the governed Project route, kind filter and private response controls", async () => {
    const fetch = vi.fn((_request: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(
        governedResponse(
          {
            ...erpProjectionCollectionFixture(),
            items: erpProjectionCollectionFixture().items.filter(
              (item) => item.projectionKind === "tool_asset_status",
            ),
          },
          init,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetch);

    const result =
      await new LiveErpProjectionsDataSource().loadProjectProjections(
        projectControlIds.project,
        new AbortController().signal,
        "tool_asset_status",
      );

    expect(result.items).toHaveLength(1);
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0]?.[0]).toBe(
      `/api/npi/v1/projects/${projectControlIds.project}/erp-projections?kind=tool_asset_status`,
    );
    expect(fetch.mock.calls[0]?.[1]?.method ?? "GET").toBe("GET");
  });

  it("fails closed for invalid inputs, cancellation and invalid payloads", async () => {
    const source = new LiveErpProjectionsDataSource();
    await expect(
      source.loadProjectProjections(
        "not-a-project-id",
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);

    const cancelled = new AbortController();
    cancelled.abort();
    await expect(
      source.loadProjectProjections(
        projectControlIds.project,
        cancelled.signal,
      ),
    ).rejects.toBeInstanceOf(ErpProjectionsRequestCancelledError);

    vi.stubGlobal(
      "fetch",
      vi.fn((_request: RequestInfo | URL, init?: RequestInit) =>
        Promise.resolve(
          governedResponse(
            { ...erpProjectionCollectionFixture(), unexpected: true },
            init,
          ),
        ),
      ),
    );
    await expect(
      source.loadProjectProjections(
        projectControlIds.project,
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });
});
