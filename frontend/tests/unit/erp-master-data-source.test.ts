import { describe, expect, it, vi } from "vitest";
import {
  isERPMasterPage,
  LiveERPMasterDataSource,
} from "../../src/api/erp-master-data-source";
import { isERPSourceId } from "../../src/api/erp-source-id";
import { NpiHttpClient } from "../../src/api/http";
import { masterPage } from "../support/erp-master-fixture";

describe("ERP master catalog contract", () => {
  it.each(["customer", "supplier", "item_group", "item", "machine"] as const)(
    "accepts only the closed %s record shape",
    (kind) => {
      const page = masterPage(kind);
      expect(isERPMasterPage(page, kind)).toBe(true);
      expect(isERPMasterPage({ ...page, unexpected: true }, kind)).toBe(false);
      expect(
        isERPMasterPage(
          { ...page, items: [{ ...page.items[0], unexpected: true }] },
          kind,
        ),
      ).toBe(false);
      expect(
        isERPMasterPage(
          { ...page, total: 2, items: [page.items[0], page.items[0]] },
          kind,
        ),
      ).toBe(false);
      expect(
        isERPMasterPage({ ...page, lastSynchronizedAt: "invalid" }, kind),
      ).toBe(false);
    },
  );
  it("accepts uninitialized empty catalogs but not fabricated timestamps or rows", () => {
    const page = masterPage("machine", {
      sourceVersion: 0,
      sourceModifiedAt: null,
      lastSynchronizedAt: null,
      total: 0,
      items: [],
    });
    expect(isERPMasterPage(page, "machine")).toBe(true);
    expect(
      isERPMasterPage(
        { ...page, items: masterPage("machine").items },
        "machine",
      ),
    ).toBe(false);
  });
  it("preserves ERP Unicode and spaces but rejects controls and oversized identifiers", () => {
    expect(isERPSourceId("机台 550-02")).toBe(true);
    for (const value of ["", " foo", "foo\nbar", "x".repeat(129), null])
      expect(isERPSourceId(value)).toBe(false);
  });
  it("uses the private BFF query API and preserves the encoded query and project scope", async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_input, init) =>
      Promise.resolve(
        new Response(
          JSON.stringify(masterPage("customer", { offset: 20, total: 21 })),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "Cache-Control": "private, no-store",
              "X-Request-ID":
                new Headers(init?.headers).get("X-Request-ID") ?? "",
              "X-Trace-ID": "trace-master-select-test",
            },
          },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    try {
      const source = new LiveERPMasterDataSource(new NpiHttpClient());
      const signal = new AbortController().signal;
      await expect(
        source.load(
          "customer",
          "客户 & A",
          20,
          signal,
          "00000000-0000-0000-0000-000000000001",
        ),
      ).resolves.toMatchObject({ catalogKind: "customer", offset: 20 });
      expect(fetcher).toHaveBeenCalledWith(
        "/api/npi/v1/integration/erpnext/master-data?kind=customer&limit=20&offset=20&projectId=00000000-0000-0000-0000-000000000001&query=%E5%AE%A2%E6%88%B7+%26+A",
        expect.objectContaining({ signal, credentials: "same-origin" }),
      );
      expect(() =>
        source.load("customer", "x".repeat(101), 0, signal),
      ).toThrow();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
